"""Interne : exécute une commande lancée depuis le menu « Commandes / sync » (ligne CommandRun <id>).

Lancé par dashboard/commands_runner/runner.py dans un processus séparé. Recopie la sortie de la commande et son
avancement (dashboard.commands_runner.progress.report) dans CommandRun, bat toutes les HEARTBEAT secondes, s'arrête
sur demande depuis la page ou au-delà du plafond mémoire (interruption propre, puis arrêt forcé : voir Tracker.stop).
Pour une commande interactive (update_funnel), les réponses enregistrées remplacent la saisie au clavier.

    python manage.py run_tracked_command 12
"""
import _thread
import builtins
import ctypes
import io
import os
import signal
import socket
import sys
import threading
import time
import traceback

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.utils import timezone

from dashboard.commands_runner import progress
from dashboard.commands_runner.runner import max_memory_mb, output_path
from process_manager.models import CommandRun

HEARTBEAT = 2.0
HARD_STOP_AFTER = 30
LOG_MAX = 200_000  # caractères gardés (la fin de la sortie)


def rss_mb():
    """Mémoire résidente du processus (Mo), None si inconnue."""
    try:
        with open("/proc/self/status") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) // 1024
    except OSError:
        pass
    if os.name == "nt":
        try:
            from ctypes import wintypes

            class Counters(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                    (name, ctypes.c_size_t) for name in (
                        "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage",
                        "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]

            counters = Counters()
            counters.cb = ctypes.sizeof(Counters)
            # Handle 64 bits : sans restype/argtypes, ctypes le tronque en entier 32 bits (appel en échec).
            kernel32, psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            handle = kernel32.GetCurrentProcess()
            if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return counters.WorkingSetSize // (1024 * 1024)
        except Exception:  # noqa: BLE001
            return None
    return None


class _Stream(io.TextIOBase):
    def __init__(self, tracker):
        self.tracker = tracker

    def write(self, text):
        self.tracker.write(text)
        return len(text)

    def isatty(self):
        return False


class Tracker:
    def __init__(self, run_id):
        self.run_id = run_id
        self.lock = threading.Lock()
        self.log = []
        self.size = 0
        self.cut = False
        self.state = {"phase": "", "done": 0, "total": 0, "current": ""}
        self.peak = 0
        self.finished = False
        self.stop_reason = None  # (statut, message) : arrêt demandé par la page ou plafond mémoire

    # -- sortie et avancement ----------------------------------------------------------------------------------
    def write(self, text):
        if not text:
            return
        with self.lock:
            self.log.append(text)
            self.size += len(text)
            if self.size > LOG_MAX * 2:
                joined = "".join(self.log)[-LOG_MAX:]
                self.log, self.size, self.cut = [joined], len(joined), True

    def log_text(self):
        with self.lock:
            joined = "".join(self.log)[-LOG_MAX:]
            cut = self.cut or self.size > LOG_MAX
        return ("… (début de la sortie coupé)\n" if cut else "") + joined

    def progress(self, phase=None, done=None, total=None, current=None):
        with self.lock:
            if phase is not None and phase != self.state["phase"]:
                self.state.update(phase=str(phase)[:255], done=0, total=0, current="")
            if total is not None:
                self.state["total"] = max(0, int(total))
            if done is not None:
                self.state["done"] = max(0, int(done))
            if current is not None:
                self.state["current"] = str(current)[:255]

    # -- battement ---------------------------------------------------------------------------------------------
    def flush(self, **extra):
        memory = rss_mb()
        if memory:
            self.peak = max(self.peak, memory)
        with self.lock:
            state = dict(self.state)
        fields = dict(state, heartbeat=timezone.now(), log=self.log_text(), **extra)
        if self.peak:
            fields["peak_memory_mb"] = self.peak
        CommandRun.objects.filter(pk=self.run_id, status__in=CommandRun.ACTIVE_STATUSES).update(**fields)
        return memory

    def beat_forever(self):
        limit = max_memory_mb()
        try:
            while not self.finished:
                time.sleep(HEARTBEAT)
                if self.finished:
                    break
                memory = self.flush()
                if self.stop_reason:
                    continue
                if memory and limit and memory > limit:
                    self.stop(CommandRun.STATUS_FAILED,
                              f"Arrêtée : mémoire {memory} Mo au-delà du plafond de {limit} Mo "
                              f"(COMMANDS_RUNNER_MAX_MEMORY_MB) pour protéger le serveur web.")
                elif CommandRun.objects.filter(pk=self.run_id, cancel_requested=True).exists():
                    self.stop(CommandRun.STATUS_CANCELLED, "Arrêtée depuis la page.")
        finally:
            connections.close_all()

    def stop(self, status, message):
        """Interrompt la commande (KeyboardInterrupt dans le fil principal, comme Ctrl+C : ses blocs `finally`
        suppriment les fichiers temporaires) ; arrêt forcé du processus et de ses enfants (aws, pg_dump…) si elle
        n'a pas rendu la main après HARD_STOP_AFTER secondes."""
        self.stop_reason = (status, message)
        self.write(f"\n{message}\n")
        if os.name == "posix":
            os.kill(os.getpid(), signal.SIGINT)  # interrompt aussi une attente système (socket, processus enfant)
        else:
            _thread.interrupt_main()
        timer = threading.Timer(HARD_STOP_AFTER, self.hard_stop)
        timer.daemon = True
        timer.start()

    def hard_stop(self):
        if self.finished:
            return
        status, message = self.stop_reason
        try:
            self.finish(status, f"{message} (arrêt forcé après {HARD_STOP_AFTER} s)")
        finally:
            connections.close_all()
            if os.name == "posix" and os.getpgrp() == os.getpid():
                os.killpg(os.getpgrp(), signal.SIGKILL)
            os._exit(1)

    def finish(self, status, error=""):
        self.finished = True
        with self.lock:
            if self.state["total"] and status == CommandRun.STATUS_DONE:
                self.state["done"] = self.state["total"]
            self.state["current"] = ""
        self.flush(status=status, error=(error or "")[:8000], finished_at=timezone.now())


class _Answers:
    """Remplace input() : réponses enregistrées, recopiées dans la sortie comme une saisie."""

    def __init__(self, answers, stream):
        self.answers = list(answers)
        self.stream = stream

    def __call__(self, prompt=""):
        if not self.answers:
            raise CommandError(f"Question inattendue de la commande (aucune réponse prévue) : {prompt}")
        answer = self.answers.pop(0)
        self.stream.write(f"{prompt}{answer}\n")
        return answer


class Command(BaseCommand):
    help = "Interne : exécute une commande lancée depuis le menu « Commandes / sync » (suivi CommandRun)."

    def add_arguments(self, parser):
        parser.add_argument("run_id", type=int)

    def handle(self, *args, **options):
        run = CommandRun.objects.filter(pk=options["run_id"]).first()
        if run is None:
            raise CommandError(f"CommandRun {options['run_id']} introuvable.")
        if run.status != CommandRun.STATUS_STARTING:
            raise CommandError(f"CommandRun {run.id} déjà {run.status}.")
        if os.name == "posix":
            signal.signal(signal.SIGINT, signal.default_int_handler)  # SIGINT -> KeyboardInterrupt (arrêt propre)
        if hasattr(os, "nice"):
            try:
                os.nice(19)  # le serveur web reste prioritaire
            except OSError:
                pass

        tracker = Tracker(run.id)
        stream = _Stream(tracker)
        CommandRun.objects.filter(pk=run.id).update(status=CommandRun.STATUS_RUNNING, heartbeat=timezone.now(),
                                                    pid=os.getpid(), host=socket.gethostname())
        progress.install(tracker.progress)
        threading.Thread(target=tracker.beat_forever, name="command-run-heartbeat", daemon=True).start()

        params = run.params or {}
        real_stdout, real_stderr, real_input = sys.stdout, sys.stderr, builtins.input
        sys.stdout = sys.stderr = stream  # print() des fonctions appelées
        builtins.input = _Answers(params.get("answers") or [], stream)
        status, error = CommandRun.STATUS_DONE, ""
        try:
            call_command(run.command, stdout=stream, stderr=stream, no_color=True, **(params.get("options") or {}))
        except BaseException as exc:  # noqa: BLE001 - CommandError compris : affiché dans la page
            if tracker.stop_reason:  # arrêt demandé par la page ou plafond mémoire
                status, error = tracker.stop_reason
            else:
                status = CommandRun.STATUS_FAILED
                error = f"{type(exc).__name__}: {exc}"
                stream.write("\n" + traceback.format_exc())
        finally:
            sys.stdout, sys.stderr, builtins.input = real_stdout, real_stderr, real_input
            progress.install(None)
        tracker.finish(status, error)
        if status == CommandRun.STATUS_DONE:
            try:
                os.remove(output_path(run.id))
            except OSError:
                pass
        if status != CommandRun.STATUS_DONE:
            sys.exit(1)
