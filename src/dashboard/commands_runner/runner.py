"""Lancement des commandes du menu « Commandes / sync » dans un processus séparé et lecture de leur suivi.

Pourquoi un processus et pas un thread du serveur web : `update_funnel` lancé sur une instance web de production
(t3.small) l'a déjà figée. Le processus enfant (`manage.py run_tracked_command <id>`) tourne à priorité basse, dans
sa propre session (le redémarrage d'un worker gunicorn ne le tue pas), et s'arrête lui-même s'il dépasse le plafond
mémoire COMMANDS_RUNNER_MAX_MEMORY_MB. Le suivi passe par la table CommandRun : la page peut être servie par un
autre processus, voire une autre instance, que celui qui exécute."""
import logging
import os
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from process_manager.models import CommandRun

logger = logging.getLogger(__name__)

# Une seule commande à la fois, toutes commandes confondues (protège le serveur web).
ADVISORY_LOCK_KEY = 72_046_118
STARTUP_TIMEOUT_SECONDS = 90


class AlreadyRunning(Exception):
    def __init__(self, run):
        super().__init__("Une commande est déjà en cours.")
        self.run = run


def output_path(run_id):
    """Sortie brute du processus (erreurs avant le démarrage du suivi, sortie des programmes externes)."""
    return os.path.join(tempfile.gettempdir(), f"command_run_{run_id}.out")


def max_memory_mb():
    value = getattr(settings, "COMMANDS_RUNNER_MAX_MEMORY_MB", None) or os.environ.get("COMMANDS_RUNNER_MAX_MEMORY_MB")
    try:
        return int(value) if value else 800
    except ValueError:
        return 800


def _mark_stale(run):
    run.status = CommandRun.STATUS_FAILED
    run.finished_at = timezone.now()
    run.error = run.error or "Interrompue : aucune nouvelle du processus depuis plus de 2 minutes (processus tué, " \
                             "serveur redémarré ou plafond mémoire du système atteint)."
    run.save(update_fields=["status", "finished_at", "error"])


def create_run(command, options, answers, command_line, writes, user):
    """Crée la ligne de suivi, ou lève AlreadyRunning si une commande tourne déjà. Le processus est lancé après
    validation de la transaction (spawn)."""
    with transaction.atomic():
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", [ADVISORY_LOCK_KEY])
        for run in CommandRun.objects.select_for_update().filter(status__in=CommandRun.ACTIVE_STATUSES):
            if run.is_stale():
                _mark_stale(run)
            else:
                raise AlreadyRunning(run)
        run = CommandRun.objects.create(
            command=command, params={"options": options, "answers": answers}, command_line=command_line,
            writes=writes, started_by=user if user and user.is_authenticated else None,
        )
    transaction.on_commit(lambda: spawn(run.id))
    return run


def _remove_old_outputs(keep_id):
    """Sorties brutes des exécutions terminées (Windows : le processus ne peut pas supprimer sa propre sortie)."""
    folder = tempfile.gettempdir()
    try:
        names = [n for n in os.listdir(folder) if n.startswith("command_run_") and n.endswith(".out")]
    except OSError:
        return
    ids = {}
    for name in names:
        number = name[len("command_run_"):-len(".out")]
        if number.isdigit() and int(number) != keep_id:
            ids[int(number)] = name
    active = set(CommandRun.objects.filter(pk__in=ids, status__in=CommandRun.ACTIVE_STATUSES).values_list("pk", flat=True))
    for run_id, name in ids.items():
        if run_id not in active:
            try:
                os.remove(os.path.join(folder, name))
            except OSError:
                pass


def spawn(run_id):
    _remove_old_outputs(run_id)
    python = getattr(settings, "COMMANDS_RUNNER_PYTHON", None) or sys.executable
    manage = Path(settings.BASE_DIR) / "manage.py"
    kwargs = {"stdin": subprocess.DEVNULL, "stderr": subprocess.STDOUT, "cwd": str(settings.BASE_DIR),
              "close_fds": True}
    if os.name == "posix":
        kwargs["start_new_session"] = True  # propre groupe de processus : arrêt de tout l'arbre, indépendant du worker
    else:
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | \
            getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        with open(output_path(run_id), "ab") as out:
            proc = subprocess.Popen([python, str(manage), "run_tracked_command", str(run_id)], stdout=out, **kwargs)
    except Exception as exc:  # noqa: BLE001 - affiché dans la page
        logger.exception("CommandRun %s : lancement impossible", run_id)
        CommandRun.objects.filter(pk=run_id).update(status=CommandRun.STATUS_FAILED, finished_at=timezone.now(),
                                                    error=f"Lancement impossible : {exc}")
        return
    CommandRun.objects.filter(pk=run_id).update(pid=proc.pid, host=socket.gethostname())
    # Récupère le code de sortie (pas de processus zombie sous le worker).
    threading.Thread(target=proc.wait, name=f"command-run-wait-{run_id}", daemon=True).start()


def check_startup(run):
    """Processus lancé sur CETTE machine mais jamais démarré (erreur Python avant le suivi) : échec, avec la fin
    de sa sortie brute."""
    if run.status != CommandRun.STATUS_STARTING or run.host != socket.gethostname():
        return run
    if (timezone.now() - run.started_at).total_seconds() < STARTUP_TIMEOUT_SECONDS:
        return run
    tail = ""
    try:
        with open(output_path(run.id), "rb") as fh:
            fh.seek(0, os.SEEK_END)
            fh.seek(max(0, fh.tell() - 4000))
            tail = fh.read().decode("utf-8", "replace")
    except OSError:
        pass
    run.status, run.finished_at = CommandRun.STATUS_FAILED, timezone.now()
    run.error = "Le processus n'a pas démarré." + (f"\n{tail}" if tail else "")
    run.save(update_fields=["status", "finished_at", "error"])
    return run


def request_cancel(run):
    """Le processus lit la demande à son prochain battement (quelques secondes) et s'arrête avec ses enfants."""
    if not run.is_active():
        return run
    if run.is_stale():
        _mark_stale(run)
        return run
    CommandRun.objects.filter(pk=run.pk).update(cancel_requested=True)
    run.cancel_requested = True
    return run
