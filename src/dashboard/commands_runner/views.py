"""Menu « Commandes / sync » (SUPERUTILISATEURS SEULEMENT) : choisir une commande de gestion, voir ce qu'elle fait
et ses options, la lancer en arrière-plan et suivre son avancement (comme l'onglet « Import vers les tâches » de
COSOCollect). Les commandes et leurs options sont décrites dans registry.py ; l'exécution dans runner.py."""
import re

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _, gettext_lazy
from django.views import generic

from dashboard.mixins import PageMixin
from process_manager.models import CommandRun, Cycle, Project, Task

from . import registry, runner


class SuperuserOnlyMixin(LoginRequiredMixin):
    """Non connecté : page de connexion ; connecté sans être superutilisateur : 403."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_superuser:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


def _fmt(dt):
    return timezone.localtime(dt).strftime("%d/%m/%Y %H:%M:%S") if dt else None


def run_json(run, with_log=True):
    now = timezone.now()
    status = "interrupted" if run.is_stale() else run.status
    user = run.started_by
    command = registry.BY_NAME.get(run.command, {})
    data = {
        "id": run.id, "command": run.command, "title": command.get("title", run.command),
        "status": status, "active": status in CommandRun.ACTIVE_STATUSES,
        "writes": run.writes, "command_line": run.command_line,
        "started_at": _fmt(run.started_at), "finished_at": _fmt(run.finished_at),
        "elapsed": int(((run.finished_at or now) - run.started_at).total_seconds()),
        "silent_for": int((now - run.heartbeat).total_seconds()),
        "started_by": (user.get_full_name() or user.username) if user else "",
        "host": run.host, "phase": run.phase, "done": run.done, "total": run.total, "current": run.current,
        "error": run.error, "peak_memory_mb": run.peak_memory_mb, "cancel_requested": run.cancel_requested,
        "cancel_url": reverse("dashboard:commands_runner:cancel", args=[run.id]),
    }
    if with_log:
        data["log"] = run.log
    return data


class CommandsView(SuperuserOnlyMixin, PageMixin, generic.TemplateView):
    template_name = "commands_runner/index.html"
    title = gettext_lazy("Commands / sync")
    active_level1 = "commands_sync"
    breadcrumb = [{"url": "", "title": title}]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from coso_collect.models import CollectForm
        session_project = self.request.session.get("project_id")
        tasks = Task.objects.select_related("project").order_by("project__name", "order", "id")
        wanted = self.request.GET.get("command")
        ctx["commands_config"] = {
            "commands": registry.public_commands(),
            "selected": wanted if wanted in registry.BY_NAME else "",
            "projects": [{"id": p.id, "text": p.name} for p in Project.objects.order_by("name")],
            "default_project": session_project,
            "cycles": [{"id": c.id, "project": c.project_id, "text": str(c.name or c)}
                       for c in Cycle.objects.order_by("project__name", "order")],
            "tasks": [{"id": t.id, "text": f"#{t.id} {t.name} ({t.project.name if t.project else '—'})"} for t in tasks],
            "collect_forms": [{"id": f.id, "text": f"#{f.id} {f.title}"} for f in CollectForm.objects.order_by("id")],
            "max_memory_mb": runner.max_memory_mb(),
            "urls": {
                "start": reverse("dashboard:commands_runner:start"),
                "status": reverse("dashboard:commands_runner:status"),
                "couch_dbs": reverse("dashboard:commands_runner:couch_dbs"),
                "cantons": reverse("dashboard:commands_runner:cantons"),
            },
            "i18n": {
                "starting": _("Starting"), "running": _("In progress"), "done": _("Finished"), "failed": _("Failed"),
                "cancelled": _("Stopped"), "interrupted": _("Interrupted (no news from the process)"),
                "writes": _("Writes"), "read_only": _("Simulation / read only"),
                "duration": _("Duration"), "started_by": _("started by"), "elapsed": _("duration"),
                "silent": _("last news"), "memory": _("peak memory"), "log": _("Command output"),
                "no_run": _("No run yet for this command."), "error": _("Error"), "stop": _("Stop"),
                "stop_confirm": _("Stop this command? What is already written stays written."),
                "stop_requested": _("Stop requested…"),
                "confirm_write": _("This command WRITES (database, CouchDB or S3). Run it?"),
                "busy": _("Another command is running: wait for it to finish (one command at a time)."),
                "all": _("(all)"), "search": _("Type at least 2 characters"), "no_option": _("No option."),
                "equivalent": _("Equivalent command"), "run": _("Run in the background"),
                "invalid": _("Invalid options."), "step": _("Step"), "choose": _("Choose a command above."),
            },
        }
        return ctx


class StartView(SuperuserOnlyMixin, generic.View):
    """POST command=<nom> + champs -> nouvelle exécution. 400 : options invalides ; 409 : une commande tourne."""

    def post(self, request, *args, **kwargs):
        command = registry.BY_NAME.get(request.POST.get("command"))
        if command is None:
            return JsonResponse({"ok": False, "message": _("Unknown command.")}, status=400)
        try:
            values = registry.clean(command, request.POST)
        except ValidationError as exc:
            errors = exc.message_dict if hasattr(exc, "error_dict") else {"__all__": exc.messages}
            return JsonResponse({"ok": False, "message": _("Invalid options."),
                                 "errors": {k: " ".join(v) for k, v in errors.items()}}, status=400)
        options, answers, line, writes = registry.build(command, values)
        try:
            run = runner.create_run(command["name"], options, answers, line, writes, request.user)
        except runner.AlreadyRunning as exc:
            return JsonResponse({"ok": False, "message": _("Another command is running: wait for it to finish "
                                                           "(one command at a time)."),
                                 "run": run_json(exc.run, with_log=False)}, status=409)
        return JsonResponse({"ok": True, "run": run_json(run)})


class StatusView(SuperuserOnlyMixin, generic.View):
    """GET ?command= : exécution en cours (toutes commandes), dernière exécution et historique de la commande."""

    def get(self, request, *args, **kwargs):
        active = [runner.check_startup(r) for r in
                  CommandRun.objects.filter(status__in=CommandRun.ACTIVE_STATUSES).select_related("started_by")]
        active = next((r for r in active if r.is_active() and not r.is_stale()), None)
        name = request.GET.get("command") or ""
        runs = list(CommandRun.objects.filter(command=name).select_related("started_by")[:10]) if name else []
        return JsonResponse({
            "active": run_json(active) if active else None,
            "runs": [run_json(r, with_log=(i == 0)) for i, r in enumerate(runs)],
        })


class CancelView(SuperuserOnlyMixin, generic.View):
    def post(self, request, *args, **kwargs):
        run = CommandRun.objects.filter(pk=kwargs["pk"]).first()
        if run is None:
            return JsonResponse({"ok": False}, status=404)
        run = runner.request_cancel(run)
        return JsonResponse({"ok": True, "run": run_json(run, with_log=False)})


class CouchDbsView(SuperuserOnlyMixin, generic.View):
    """GET ?q= : bases CouchDB dont le nom, ou le nom / l'identifiant du facilitateur, contient q."""

    def get(self, request, *args, **kwargs):
        from authentication.models import Facilitator
        from no_sql_client import NoSQLClient
        term = (request.GET.get("q") or "").strip().lower()
        if len(term) < 2:
            return JsonResponse({"results": []})
        try:
            names = NoSQLClient().get_dbs()
        except Exception as exc:  # noqa: BLE001 - CouchDB injoignable : message dans la liste
            return JsonResponse({"results": [], "error": str(exc)})
        people = {db: f"{name or ''} ({username or ''})".strip() for db, name, username in
                  Facilitator.objects.exclude(no_sql_db_name__isnull=True)
                  .values_list("no_sql_db_name", "name", "username")}
        results = []
        for db in names:
            label = people.get(db, "")
            if term in db.lower() or term in label.lower():
                results.append({"id": db, "text": f"{db} — {label}" if label else db})
            if len(results) >= 50:
                break
        return JsonResponse({"results": results})


class CantonsView(SuperuserOnlyMixin, generic.View):
    """GET ?q= : cantons par nom ou identifiant, avec commune et préfecture."""

    def get(self, request, *args, **kwargs):
        from administrativelevels.models import AdministrativeLevel
        term = (request.GET.get("q") or "").strip()
        if len(term) < 2 and not term.isdigit():
            return JsonResponse({"results": []})
        query = Q(name__icontains=term) | (Q(id=int(term)) if re.fullmatch(r"\d+", term) else Q(pk__in=[]))
        cantons = AdministrativeLevel.objects.filter(type="Canton").filter(query) \
            .select_related("parent", "parent__parent").order_by("name")[:40]
        results = []
        for canton in cantons:
            path = " / ".join(p.name for p in (canton.parent, getattr(canton.parent, "parent", None)) if p)
            results.append({"id": canton.id, "text": f"{canton.name}{' (' + path + ')' if path else ''} #{canton.id}"})
        return JsonResponse({"results": results})
