"""Page « Vérification des villages » (/administrative-levels/checking/) : villages des projets de l'utilisateur
qui présentent un manque, par rubrique :

- sans CVD : `AdministrativeLevel.cvd` vide ;
- non affectés : pas d'affectation active (`AssignAdministrativeLevelToFacilitator`, `activated`) du village dans
  l'un des projets choisis auxquels il appartient (la rubrique indique lesquels) ;
- aucun FC stabilisé / aucun FT stabilisé : aucun facilitateur communautaire / technique actif, hors mode test,
  n'a le village dans ses villages de stabilisation (`Facilitator.stabilization_administrative_ids` ; les villages
  additionnels ne comptent pas).

Filtres : projets (un, plusieurs, ou tous ceux de l'utilisateur — tous pour un super-administrateur) et niveaux
administratifs (région, préfecture, commune, canton, village ; plusieurs choix possibles par niveau). Un village
appartient à un projet par la table des niveaux administratifs du projet (`subprojects.Project.administrative_levels`).

Tout est lu en quelques requêtes puis croisé en mémoire (environ 3 500 niveaux administratifs).
"""
import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse, QueryDict
from django.utils.translation import gettext, gettext_lazy
from django.views import generic

from administrativelevels.models import AdministrativeLevel
from assignments.models import AssignAdministrativeLevelToFacilitator
from authentication.models import Facilitator
from dashboard.mixins import PageMixin
from process_manager.models import Project
from subprojects.models import Project as MisProject
from process_manager.models import VillageDocsOperation
from dashboard.diagnostics import village_docs as vd
from . import couch_names

GEO_LEVELS = [
    ("region", "Region", gettext_lazy("Region")),
    ("prefecture", "Prefecture", gettext_lazy("Prefecture")),
    ("commune", "Commune", gettext_lazy("Commune")),
    ("canton", "Canton", gettext_lazy("Canton")),
    ("village", "Village", gettext_lazy("Village")),
]
GEO_TYPES = {adm_type: key for key, adm_type, _ in GEO_LEVELS}

RUBRICS = [
    ("no_cvd", gettext_lazy("Villages without CVD"), "fas fa-users-slash"),
    ("unassigned", gettext_lazy("Villages not assigned to a facilitator"), "fas fa-user-times"),
    ("no_fc", gettext_lazy("Villages without stabilized community facilitator"), "fas fa-user-slash"),
    ("no_ft", gettext_lazy("Villages without stabilized technical facilitator"), "fas fa-hard-hat"),
]
RUBRIC_KEYS = [key for key, _, _ in RUBRICS]
FACILITATOR_GROUPS = ("CommunityFacilitator", "TechnicalFacilitator")


def user_projects(user):
    """Projets de l'utilisateur (Project.users), tous pour un super-administrateur."""
    if user.is_superuser:
        return Project.objects.order_by('name')
    return Project.objects.filter(users=user).distinct().order_by('name')


def _int_list(values):
    out = []
    for value in values:
        try:
            out.append(int(value))
        except (TypeError, ValueError):
            continue
    return out


class VillageCheckingView(PageMixin, LoginRequiredMixin, generic.TemplateView):
    template_name = 'administrative_levels/checking.html'
    title = gettext_lazy('Villages checking')
    active_level1 = 'village_docs'  # menu « Contrôle des villages » (avec les pages Documents des villages)
    active_level2 = 'villages_checking'
    breadcrumb = [{'url': '', 'title': title}]

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if user.is_authenticated and not user.is_superuser:  # menu « Contrôle des villages » : super-administrateurs
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    # -- périmètre ---------------------------------------------------------------------------------------------
    def selected_projects(self, projects):
        wanted = set(_int_list(self.request.GET.getlist('project')))
        chosen = [p for p in projects if p.id in wanted]
        return chosen or projects

    @staticmethod
    def project_villages(project_ids):
        """{village_id: {project_id, ...}} pour les villages liés aux projets donnés."""
        through = MisProject.administrative_levels.through
        rows = through.objects.filter(project_id__in=project_ids, administrativelevel__type='Village') \
            .values_list('administrativelevel_id', 'project_id')
        out = {}
        for village_id, project_id in rows:
            out.setdefault(village_id, set()).add(project_id)
        return out

    @staticmethod
    def levels():
        """{id: (type, parent_id, name)} de tous les niveaux administratifs."""
        return {row[0]: (row[1], row[2], row[3])
                for row in AdministrativeLevel.objects.values_list('id', 'type', 'parent_id', 'name')}

    @staticmethod
    def ancestors(village_id, levels):
        """{clé de niveau: id} : le village et ses parents (canton, commune, préfecture, région)."""
        chain, current, seen = {}, village_id, set()
        while current is not None and current in levels and current not in seen:
            seen.add(current)
            adm_type, parent_id, _ = levels[current]
            key = GEO_TYPES.get(adm_type)
            if key and key not in chain:
                chain[key] = current
            current = parent_id
        return chain

    # -- rubriques ---------------------------------------------------------------------------------------------
    @staticmethod
    def assigned_pairs(village_ids, project_ids):
        return set(AssignAdministrativeLevelToFacilitator.objects.filter(
            activated=True, project_id__in=project_ids, administrative_level_id__in=village_ids,
        ).values_list('administrative_level_id', 'project_id'))

    @staticmethod
    def stabilizing_facilitators(village_ids):
        """{village_id: {'community_facilitator': [noms], 'technical_facilitator': [noms]}} (actifs, hors test)."""
        wanted = set(village_ids)
        out = {}
        rows = Facilitator.objects.filter(active=True, training_mode=False) \
            .exclude(stabilization_administrative_ids__isnull=True) \
            .values_list('facilitator_type', 'name', 'username', 'stabilization_administrative_ids')
        for facilitator_type, name, username, ids in rows:
            for village_id in wanted.intersection(_int_list(ids or [])):
                out.setdefault(village_id, {}).setdefault(facilitator_type, []).append(name or username)
        return out

    def scope(self, params):
        """Périmètre des filtres (projets, niveaux) : villages retenus et listes des filtres."""
        projects = list(user_projects(self.request.user))
        chosen_projects = self.selected_projects(projects)
        project_ids = [p.id for p in chosen_projects]

        village_projects = self.project_villages(project_ids)
        levels = self.levels()
        chains = {v: self.ancestors(v, levels) for v in village_projects}

        # Niveaux choisis (plusieurs par niveau) ; un choix incompatible avec les niveaux au-dessus est ignoré.
        geo_selects, filters, scope = [], {}, list(village_projects)
        for key, _adm_type, label in GEO_LEVELS:
            option_ids = {chains[v][key] for v in scope if key in chains[v]}
            chosen = [i for i in _int_list(params.getlist(key)) if i in option_ids]
            options = sorted(((i, levels[i][2]) for i in option_ids), key=lambda o: (o[1] or '').lower())
            geo_selects.append({'key': key, 'label': label, 'options': options, 'selected': chosen})
            if chosen:
                filters[key] = set(chosen)
                scope = [v for v in scope if chains[v].get(key) in filters[key]]
        return {'projects': projects, 'chosen_projects': chosen_projects, 'project_ids': project_ids,
                'village_projects': village_projects, 'levels': levels, 'chains': chains,
                'geo_selects': geo_selects, 'village_ids': scope}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET
        found = self.scope(params)
        projects, chosen_projects, project_ids = found['projects'], found['chosen_projects'], found['project_ids']
        project_names = {p.id: p.name for p in projects}
        village_projects, levels, chains = found['village_projects'], found['levels'], found['chains']
        geo_selects, village_ids = found['geo_selects'], found['village_ids']
        assigned = self.assigned_pairs(village_ids, project_ids)
        stabilizing = self.stabilizing_facilitators(village_ids)
        cvd_of = dict(AdministrativeLevel.objects.filter(id__in=village_ids, cvd__isnull=False)
                      .values_list('id', 'cvd__name'))

        rows = {key: [] for key in RUBRIC_KEYS}
        for village_id in village_ids:
            chain = chains[village_id]
            names = {key: levels[chain[key]][2] if key in chain else '' for key, _, _ in GEO_LEVELS}
            in_projects = sorted(village_projects[village_id], key=lambda p: project_names.get(p, ''))
            facilitators = stabilizing.get(village_id, {})
            base = {
                'id': village_id, 'names': names, 'cvd': cvd_of.get(village_id),
                'projects': [project_names.get(p, p) for p in in_projects],
                'fc': sorted(facilitators.get('community_facilitator', [])),
                'ft': sorted(facilitators.get('technical_facilitator', [])),
            }
            if village_id not in cvd_of:
                rows['no_cvd'].append(base)
            missing = [project_names.get(p, p) for p in in_projects if (village_id, p) not in assigned]
            if missing:
                rows['unassigned'].append(dict(base, missing_projects=missing))
            if not base['fc']:
                rows['no_fc'].append(base)
            if not base['ft']:
                rows['no_ft'].append(base)
        for key in RUBRIC_KEYS:
            rows[key].sort(key=lambda r: tuple((r['names'][k] or '').lower() for k, _, _ in GEO_LEVELS))

        rubric = params.get('rubric') if params.get('rubric') in RUBRIC_KEYS else RUBRIC_KEYS[0]
        query = params.copy()
        query.pop('rubric', None)
        context.update({
            'projects': projects,
            'chosen_project_ids': [p.id for p in chosen_projects] if len(chosen_projects) != len(projects) else [],
            'geo_selects': geo_selects,
            'total_villages': len(village_ids),
            'rubrics': [{'key': key, 'label': label, 'icon': icon, 'count': len(rows[key]), 'active': key == rubric}
                        for key, label, icon in RUBRICS],
            'rubric': rubric,
            'rubric_label': dict((k, l) for k, l, _ in RUBRICS)[rubric],
            'rows': rows[rubric],
            'filters_query': query.urlencode(),
            'geo_headers': [label for _, _, label in GEO_LEVELS],
        })
        return context


def _names_operation_json(op):
    if not op:
        return None
    data = vd.operation_json(op)
    data['mode'] = (op.params or {}).get('mode')
    data['scope_villages'] = (op.params or {}).get('villages')
    data['filters'] = (op.params or {}).get('filters')
    return data


class VillageNamesView(VillageCheckingView):
    """Noms corrigés sur le SIG -> CouchDB des facilitateurs (voir couch_names).
    GET : dernière opération + dernière analyse (écarts). POST JSON :
    - {mode: "scan", filters: "<filtres de la page>"} : analyse du périmètre filtré ;
    - {mode: "apply", scan: <id de l'analyse>, keys: [...]} : mise à jour des écarts cochés de cette analyse."""

    def get(self, request, *args, **kwargs):
        scan = couch_names.last_operation(couch_names.MODE_SCAN)
        last = couch_names.last_operation()
        return JsonResponse({'operation': _names_operation_json(last), 'scan': _names_operation_json(scan)})

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body or b'{}')
        except ValueError:
            return JsonResponse({'error': 'JSON'}, status=400)
        mode = data.get('mode')
        if mode == couch_names.MODE_SCAN:
            found = self.scope(QueryDict(str(data.get('filters') or '')))
            level_ids = set(found['village_ids'])
            for village_id in found['village_ids']:
                level_ids.update(found['chains'][village_id].values())  # cantons… (tâches cantonales)
            params = {'mode': mode, 'villages': len(found['village_ids']), 'filters': str(data.get('filters') or '')}
            payload, total = sorted(level_ids), 0
        elif mode == couch_names.MODE_APPLY:
            scan = VillageDocsOperation.objects.filter(
                pk=data.get('scan') if str(data.get('scan') or '').isdigit() else None,
                kind=VillageDocsOperation.KIND_NAMES, params__mode=couch_names.MODE_SCAN,
                status=VillageDocsOperation.STATUS_DONE).first()
            if not scan:
                return JsonResponse({'error': gettext('Run the analysis again.')}, status=400)
            keys = {str(k) for k in data.get('keys') or []}
            payload = [e for e in scan.results or [] if e.get('key') in keys]
            if not payload:
                return JsonResponse({'error': gettext('Select at least one line.')}, status=400)
            params = {'mode': mode, 'scan': scan.id, 'keys': sorted(keys)}
            total = len({db for e in payload for db in e.get('dbs') or {}})
        else:
            return JsonResponse({'error': 'mode'}, status=400)
        try:
            op = vd.create_operation(VillageDocsOperation.KIND_NAMES, request.user, params, total)
        except vd.OperationBusy as busy:
            return JsonResponse({'error': gettext('Another transfer or synchronization is running; wait for it to finish.'),
                                 'operation': _names_operation_json(busy.operation)}, status=409)
        vd.start_in_thread(op.id, couch_names.run, mode, payload)
        return JsonResponse({'ok': True, 'operation': _names_operation_json(op)})
