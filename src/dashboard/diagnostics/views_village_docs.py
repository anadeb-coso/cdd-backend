"""Pages « Documents sans village » et « Villages sans documents » (diagnostics) : voir dashboard/diagnostics/village_docs.py.

Menu « Contrôle des villages » : pages, données, commentaires, transferts et synchronisations réservés aux
super-administrateurs. Seul le suivi de l'encart de progression (`?tracked=1` : déplacements déclenchés par
l'utilisateur en enregistrant des villages d'affectation) reste ouvert aux utilisateurs du tableau de bord hors FC/FT."""
import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.utils.translation import gettext, gettext_lazy
from django.views import generic

from authentication.models import Facilitator
from dashboard.administrative_levels.views_checking import user_projects
from dashboard.diagnostics import village_docs as vd
from dashboard.mixins import PageMixin
from process_manager.models import Cycle, Project, Task, VillageDocsComment, VillageDocsOperation

FACILITATOR_GROUPS = ("CommunityFacilitator", "TechnicalFacilitator")
MAX_ITEMS = 300


def _int_list(values):
    out = []
    for value in values:
        try:
            out.append(int(value))
        except (TypeError, ValueError):
            continue
    return out


class _AccessMixin(LoginRequiredMixin):
    """Super-administrateurs seulement."""

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if user.is_authenticated and not user.is_superuser:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class _StaffAccessMixin(LoginRequiredMixin):
    """Utilisateurs du tableau de bord hors comptes FC/FT (encart de progression de base.html)."""

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if user.is_authenticated and not user.is_superuser and user.groups.filter(name__in=FACILITATOR_GROUPS).exists():
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


def _json_body(request):
    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
    except (ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _error(message, status=422, **extra):
    return JsonResponse(dict({'ok': False, 'errors': [str(message)]}, **extra), status=status)


class VillageDocsPageView(PageMixin, _AccessMixin, generic.TemplateView):
    template_name = 'diagnostics/village_docs.html'
    page = vd.PAGE_ORPHANS
    active_level1 = 'village_docs'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        projects = list(user_projects(self.request.user))
        cycles = Cycle.objects.filter(project__in=projects).select_related('project').order_by('project__name', 'order')
        session_project = self.request.session.get('project_id')
        context.update({
            'page': self.page,
            'projects': projects,
            'cycles': cycles,
            'default_project': int(session_project) if str(session_project or '').isdigit() else None,
            'kinds': [('real', gettext_lazy('Real accounts')), ('training', gettext_lazy('Training accounts')),
                      ('develop', gettext_lazy('Development accounts'))],
            'can_act': self.request.user.is_superuser,
            'other_page': 'missing' if self.page == vd.PAGE_ORPHANS else 'orphans',
        })
        return context


class VillageDocsOrphansView(VillageDocsPageView):
    page = vd.PAGE_ORPHANS
    title = gettext_lazy('Documents without village')
    active_level2 = 'village_docs_orphans'
    breadcrumb = [{'url': '', 'title': title}]


class VillageDocsMissingView(VillageDocsPageView):
    page = vd.PAGE_MISSING
    title = gettext_lazy('Villages without documents')
    active_level2 = 'village_docs_missing'
    breadcrumb = [{'url': '', 'title': title}]


class VillageDocsDataView(_AccessMixin, generic.View):
    """GET ?page=orphans|missing&project=..&cycle=..&kind=.. -> lignes (JSON). Lit toutes les bases des FC choisis."""

    def get(self, request, *args, **kwargs):
        page = request.GET.get('page')
        if page not in (vd.PAGE_ORPHANS, vd.PAGE_MISSING):
            return _error('page', status=400)
        allowed = list(user_projects(request.user))
        wanted = set(_int_list(request.GET.getlist('project')))
        projects = [p for p in allowed if p.id in wanted] or allowed
        kinds = [k for k in request.GET.getlist('kind') if k in vd.ACCOUNT_KINDS] or ['real']
        cycle_ids = _int_list(request.GET.getlist('cycle'))
        try:
            data = vd.scan(page, projects, cycle_ids=cycle_ids, kinds=kinds)
        except (vd.CouchError, Exception) as exc:  # noqa: BLE001 - lecture CouchDB : message à l'écran
            return _error(gettext('Could not read CouchDB: %(error)s') % {'error': exc}, status=502)
        return JsonResponse(dict(data, ok=True))


def _allowed_project(user, project_id):
    return next((p for p in user_projects(user) if p.id == project_id), None)


class VillageDocsCommentView(_AccessMixin, generic.View):
    """POST JSON {page, key, text, assigned_facilitator_id} -> commentaire créé."""

    def post(self, request, *args, **kwargs):
        data = _json_body(request)
        if data is None:
            return _error('JSON', status=400)
        page = data.get('page')
        text = (data.get('text') or '').strip()
        if page not in (vd.PAGE_ORPHANS, vd.PAGE_MISSING) or not text:
            return _error(gettext('Write a comment.'))
        try:
            db, village, project_couch, cycle_couch = vd.parse_row_key(data.get('key'))
        except ValueError:
            return _error('key', status=400)
        project = Project.objects.filter(couch_id=project_couch).first()
        if not project or not _allowed_project(request.user, project.id):
            return _error(gettext('Unknown project.'), status=404)
        cycle = Cycle.objects.filter(couch_id=cycle_couch, project=project).first() if cycle_couch else None
        assigned = None
        if str(data.get('assigned_facilitator_id') or '').isdigit():
            assigned = Facilitator.objects.filter(pk=int(data['assigned_facilitator_id'])).first()
        comment = VillageDocsComment.objects.create(
            page=page, administrative_level_id=int(village), project=project, cycle=cycle,
            facilitator=Facilitator.objects.filter(no_sql_db_name=db).first(), no_sql_db_name=db,
            assigned_facilitator=assigned, text=text[:5000], author=request.user,
        )
        return JsonResponse({'ok': True, 'comment': vd.comment_json(comment)})


class VillageDocsOperationStatusView(_StaffAccessMixin, generic.View):
    """GET -> dernières opérations (JSON), interrogé toutes les 3 s par la page pendant une opération. Toutes les
    opérations : super-administrateurs ; `?tracked=1` (celles de la session de l'utilisateur) : tableau de bord."""

    def get(self, request, *args, **kwargs):
        if not request.GET.get('tracked') and not request.user.is_superuser:
            raise PermissionDenied
        if request.GET.get('tracked'):
            # Encart de progression (layouts/base.html) : opérations déclenchées par cet utilisateur dans sa session
            ops = [vd.operation_json(op) for op in vd.tracked_operations(request)]
        else:
            # Pages de diagnostic : opérations actives (la plus ancienne d'abord), sinon la dernière
            active = list(VillageDocsOperation.objects.filter(status__in=VillageDocsOperation.ACTIVE_STATUSES)
                          .select_related('started_by').order_by('id'))
            ops = [vd.operation_json(op) for op in active if not op.is_stale()]
            if not ops:
                ops = [vd.operation_json(op) for op in VillageDocsOperation.objects.select_related('started_by')[:1]]
        return JsonResponse({'operations': ops, 'running': any(o['running'] for o in ops)})

    def post(self, request, *args, **kwargs):
        """Fermeture de l'encart : les opérations terminées indiquées ne sont plus suivies."""
        data = _json_body(request) or {}
        vd.untrack_operations(request, _int_list(data.get('ids') or []))
        return JsonResponse({'ok': True})


class VillageDocsOperationStartView(_AccessMixin, generic.View):
    """POST JSON {kind, items: [{key, source?, backup_cycle?, label}], tasks: {"projet|cycle": [ids]}}.
    Super-administrateurs seulement ; une opération à la fois (409)."""

    def post(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return _error(gettext('Reserved for super administrators.'), status=403)
        data = _json_body(request)
        if data is None:
            return _error('JSON', status=400)
        kind = data.get('kind')
        if kind not in dict(VillageDocsOperation.KIND_CHOICES):
            return _error('kind', status=400)
        raw_items = data.get('items') or []
        if not isinstance(raw_items, list) or not raw_items:
            return _error(gettext('Select at least one line.'))
        if len(raw_items) > MAX_ITEMS:
            return _error(gettext('At most %(n)s lines at a time.') % {'n': MAX_ITEMS})

        allowed = {p.couch_id: p for p in user_projects(request.user) if p.couch_id}
        items = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                return _error('items', status=400)
            try:
                db, village, project_couch, cycle_couch = vd.parse_row_key(raw.get('key'))
            except ValueError:
                return _error('key', status=400)
            if project_couch not in allowed:
                return _error(gettext('Unknown project.'), status=404)
            if not Facilitator.objects.filter(no_sql_db_name=db).exists():
                return _error(gettext('Unknown facilitator database: %(db)s') % {'db': db}, status=404)
            item = {'key': raw['key'], 'db': db, 'village': village, 'project': project_couch, 'cycle': cycle_couch,
                    'label': str(raw.get('label') or village)[:200]}
            if kind == VillageDocsOperation.KIND_FROM_BACKUP:
                item['source'] = str(raw.get('source') or '')
                item['backup_cycle'] = str(raw.get('backup_cycle') if raw.get('backup_cycle') is not None else cycle_couch)
                if item['backup_cycle'] not in (cycle_couch, ''):
                    return _error('backup_cycle', status=400)
            items.append(item)
        if len({i['key'] for i in items}) != len(items):
            return _error(gettext('The same line is selected twice.'))

        if kind == VillageDocsOperation.KIND_SYNC:
            return self.start_sync(request, items, data.get('tasks') or {})
        try:
            op = vd.create_operation(kind, request.user, {'items': items}, len(items))
        except vd.OperationBusy as busy:
            return _error(gettext('Another transfer or synchronization is running; wait for it to finish.'),
                          status=409, operation=vd.operation_json(busy.operation))
        vd.start_in_thread(op.id, vd.run_transfers, kind, items, request.user)
        return JsonResponse({'ok': True, 'operation': vd.operation_json(op)})

    def start_sync(self, request, items, tasks):
        if not isinstance(tasks, dict):
            return _error('tasks', status=400)
        groups = {}
        for item in items:
            project = Project.objects.filter(couch_id=item['project']).first()
            cycle = Cycle.objects.filter(couch_id=item['cycle'], project=project).first() if item['cycle'] else None
            if not cycle:
                return _error(gettext('A cycle is required to synchronize %(village)s.') % {'village': item['label']})
            wanted = _int_list(tasks.get(f"{project.id}|{cycle.id}") or [])
            valid = list(Task.objects.filter(id__in=wanted, project=project, cycles=cycle).values_list('id', flat=True).distinct())
            if not valid:
                return _error(gettext('Choose the tasks to synchronize for %(project)s / %(cycle)s.') % {
                    'project': project.name, 'cycle': cycle.name})
            facilitator = Facilitator.objects.get(no_sql_db_name=item['db'])
            group = groups.setdefault((item['db'], project.id, cycle.id), {
                'db': item['db'], 'project_id': project.id, 'cycle_id': cycle.id, 'tasks': sorted(valid),
                'develop_mode': facilitator.develop_mode, 'training_mode': facilitator.training_mode,
                'villages': [], 'keys': [], 'labels': []})
            group['villages'].append(item['village'])
            group['keys'].append(item['key'])
            group['labels'].append(item['label'])
        groups = list(groups.values())
        try:
            op = vd.create_operation(VillageDocsOperation.KIND_SYNC, request.user,
                                     {'items': items, 'groups': groups}, len(items))
        except vd.OperationBusy as busy:
            return _error(gettext('Another transfer or synchronization is running; wait for it to finish.'),
                          status=409, operation=vd.operation_json(busy.operation))
        VillageDocsOperation.objects.filter(pk=op.id).update(
            units_total=sum(len(g['villages']) * len(g['tasks']) for g in groups))
        op.refresh_from_db()
        vd.start_in_thread(op.id, vd.run_sync, groups)
        return JsonResponse({'ok': True, 'operation': vd.operation_json(op)})
