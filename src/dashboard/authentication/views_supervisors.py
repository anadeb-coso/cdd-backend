from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.translation import gettext_lazy
from django.views import generic
from django.contrib.auth.models import User
import itertools
from collections import defaultdict
from django.db.models import Q, Sum

from dashboard.facilitators.forms import FilterFacilitatorForm
from dashboard.mixins import PageMixin
import grm_client
from dashboard.administrative_levels.functions import get_cascade_villages_by_administrative_level_id
from process_manager.models import AggregatedStatus, Project
from cdd.functions import list_with_and
from administrativelevels.models import AdministrativeLevel
from cdd.call_objects_from_other_db import mis_objects_call

# Situation affichée pour un projet, un canton ou un village (mêmes colonnes que la ligne du superviseur)
STATS_FIELDS = [
    'total_tasks', 'total_tasks_completed', 'total_tasks_validated', 'total_tasks_invalidated',
    'total_tasks_waiting_validation', 'total_tasks_invalidated_review', 'total_tasks_invalidated_review_completed',
    'total_tasks_invalidated_review_in_pending',
]


def _stats(row):
    stats = {field: (row or {}).get(field) or 0 for field in STATS_FIELDS}
    completed, validated, invalidated = stats['total_tasks_completed'], stats['total_tasks_validated'], stats['total_tasks_invalidated']
    stats['validation_percent'] = float("%.2f" % ((validated / completed * 100) if completed else 0))
    stats['decision_percent'] = float("%.2f" % (((validated + invalidated) / completed * 100) if completed else 0))
    return stats


def attach_cantons_details(supervisors, projects):
    """Situation par canton, puis par village siège, de chaque superviseur pour chaque projet et cycle (déroulé d'un
    projet puis d'un canton sur /supervisors/, comme /diagnostics/adl-tasks) : `supervisor['cantons_details'][projet]
    [cycle]` = cantons de sa zone avec leurs villages sièges (un par CVD : leurs chiffres s'additionnent pour donner
    ceux du canton). Chaque village siège porte la base CouchDB du facilitateur qui lui est affecté dans le SIG pour
    ce projet (lien « Voir » vers ses tâches). Quelques requêtes pour tous les superviseurs."""
    from assignments.models import AssignAdministrativeLevelToFacilitator
    from authentication.models import Facilitator
    from subprojects.models import Project as MisProject

    cycles = {cycle.id: (project, cycle.name) for project in projects for cycle in project.cycle_set.all()}
    canton_ids = {canton_id for supervisor in supervisors for canton_id in supervisor.get('_canton_ids', [])}
    names, villages_by_canton = {}, defaultdict(list)
    if canton_ids:
        names.update(mis_objects_call.filter_objects(AdministrativeLevel, id__in=canton_ids).values_list('id', 'name'))
        for village_id, name, parent_id, cvd_name in mis_objects_call.filter_objects(
            AdministrativeLevel, parent_id__in=canton_ids, type="Village", headquarters_village_of_the_cvd__isnull=False,
        ).distinct().values_list('id', 'name', 'parent_id', 'cvd__name'):
            names[village_id] = name if not cvd_name or name == cvd_name else f"{name} [{cvd_name}]"
            villages_by_canton[parent_id].append(village_id)
    village_ids = {v for vs in villages_by_canton.values() for v in vs}
    level_ids = canton_ids | village_ids
    stats = {
        (row['administrative_level_id'], row['cycle_id']): row
        for row in AggregatedStatus.objects.filter(
            facilitator=None, task=None, administrative_level_id__in=level_ids, cycle_id__in=list(cycles),
        ).values('administrative_level_id', 'cycle_id').annotate(**{field: Sum(field) for field in STATS_FIELDS})
    } if level_ids and cycles else {}

    # Facilitateur affecté à chaque village siège dans le SIG, par projet (mêmes critères que /diagnostics/adl-tasks)
    mis_projects = dict(mis_objects_call.filter_objects(MisProject, name__in={p.name for p, _ in cycles.values()}).values_list('name', 'id'))
    assignments = list(mis_objects_call.filter_objects(
        AssignAdministrativeLevelToFacilitator, project_id__in=list(mis_projects.values()), administrative_level_id__in=village_ids,
        activated=True,
    ).values_list('project_id', 'administrative_level_id', 'facilitator_id')) if village_ids and mis_projects else []
    databases = dict(Facilitator.objects.filter(
        id__in={int(f) for _, _, f in assignments if str(f).isdigit()}, facilitator_type='community_facilitator',
        develop_mode=False, training_mode=False,
    ).values_list('id', 'no_sql_db_name'))
    database_of = {(project_id, village_id): databases.get(int(f)) for project_id, village_id, f in assignments if str(f).isdigit()}

    for supervisor in supervisors:
        details = {}
        for cycle_id, (project, cycle_name) in cycles.items():
            mis_project_id = mis_projects.get(project.name)
            cantons = []
            for canton_id in sorted(supervisor.get('_canton_ids', []), key=lambda i: names.get(i, '')):
                if (canton_id, cycle_id) not in stats:
                    continue  # canton hors de ce projet / cycle
                villages = sorted((v for v in villages_by_canton[canton_id] if (v, cycle_id) in stats), key=lambda i: names.get(i, ''))
                cantons.append(dict(
                    _stats(stats[(canton_id, cycle_id)]), id=canton_id, name=names.get(canton_id, canton_id),
                    villages=[
                        dict(_stats(stats[(v, cycle_id)]), id=v, name=names.get(v, v), db=database_of.get((mis_project_id, v)))
                        for v in villages
                    ],
                ))
            details.setdefault(project.name, {})[cycle_name] = cantons
        supervisor['cantons_details'] = details
        supervisor['cantons_details_id'] = f"cantons_details_{supervisor['user_object_cdd_id']}"


class SupervisrosListView(PageMixin, LoginRequiredMixin, generic.ListView):
    model = User
    queryset = []
    template_name = 'authentication/supervisors.html'
    context_object_name = 'supervisors'
    title = gettext_lazy('Supervisors')
    active_level1 = 'facilitators'
    active_level2 = 'supervisors'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def get_queryset(self):
        return super().get_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = FilterFacilitatorForm()
        context['breadcrumb'] = False

        context['region_id'] = self.request.GET.get('region_id')
        agg = AggregatedStatus.objects.filter(project_id=self.request.session.get('project_id'), cycle_id=self.request.session.get('cycle_id'), task__isnull=False, facilitator=None).order_by('-updated_date').first()
        context['last_update'] = agg.updated_date if agg else None
        
        return context
    


class SupervisorsListTableView(LoginRequiredMixin, generic.ListView):
    template_name = 'authentication/supervisors_list.html'
    context_object_name = 'supervisors'

    def get_results(self):
        id_region = self.request.GET.get('id_region')
        id_prefecture = self.request.GET.get('id_prefecture')
        id_commune = self.request.GET.get('id_commune')
        id_canton = self.request.GET.get('id_canton')
        id_village = self.request.GET.get('id_village')
        type_field = self.request.GET.get('type_field')
        
        _id = 0

        supervisors = []
        _supervisors = {s[1]: list(s) for s in User.objects.filter(
            groups__name__in=['Supervisor'],
            is_active=True,
            projects__in=[self.request.session.get('project_id')]
        ).values_list('id', 'email', 'username', 'last_name', 'first_name')}
        adls_emails = list(_supervisors.keys())

        def get_supervisors(docs=None):

            if docs is not None:
                return [
                    doc for doc in docs if doc.get('representative').get('email') in adls_emails
                ]
            else:
                return [
                    doc for doc in grm_client.get_all_facilitators()
                    if doc.get('representative') and doc.get('representative').get('email') in adls_emails
                ]
        
        if (id_region or id_prefecture or id_commune or id_canton or id_village) and type_field:
            _type = None
            if id_region and type_field == "region":
                _type = "region"
                _id = id_region
            elif id_prefecture and type_field == "prefecture":
                _type = "prefecture"
                _id = id_prefecture
            elif id_commune and type_field == "commune":
                _type = "commune"
                _id = id_commune
            elif id_canton and type_field == "canton":
                _type = "canton"
                _id = id_canton
            elif id_village and type_field == "village":
                _type = "village"
                _id = id_village
                
            
            if type(_id) is not list:
                liste_villages = []
                liste_villages = get_cascade_villages_by_administrative_level_id(_id)

                supervisors = grm_client.get_facilitator_by_village([v['administrative_id'] for v in liste_villages])

                if supervisors:
                    _f_s = []
                    for elt in supervisors:
                        if elt.get('representative', {}).get('email') in adls_emails and elt not in _f_s:
                            _f_s.append(elt)
                            
                    supervisors = get_supervisors(_f_s)
                
            else:
                supervisors = get_supervisors()
        else:
            supervisors = get_supervisors()

        projects = Project.objects.filter(users__in=[self.request.user.id]).prefetch_related("cycle_set")

        for supervisor in supervisors:
            grm_client.attach_administrative_regions_objects(supervisor)
            supervisor['user_object_cdd_id'] = _supervisors[supervisor['representative']['email']][0]
            supervisor['user_object_cdd_username'] = _supervisors[supervisor['representative']['email']][2]
            supervisor['user_object_cdd_full_name'] = f"{_supervisors[supervisor['representative']['email']][3]} {_supervisors[supervisor['representative']['email']][4]}"


            administrative_regions_objects = supervisor.get('administrative_regions_objects')
            cantons_stabilized_ids = list(set(
                list(itertools.chain(*[[str(ad['id'])] for ad in (administrative_regions_objects if administrative_regions_objects else []) if ad and type(ad) is dict and 'id' in ad]))
            ))
            cantons_stabilized_names = list(set(
                list(itertools.chain(*[[str(ad['name'])] for ad in (administrative_regions_objects if administrative_regions_objects else []) if ad and type(ad) is dict and 'name' in ad]))
            ))
            supervisor['_canton_ids'] = sorted({int(_id) for _id in cantons_stabilized_ids if str(_id).isdigit()})
            
            invalidation_notifications = {}
            supervisor['total_tasks'] = 0
            supervisor['total_tasks_completed'] = 0
            supervisor['total_tasks_validated'] = 0
            supervisor['total_tasks_invalidated'] = 0
            supervisor['total_tasks_waiting_validation'] = 0
            supervisor['total_tasks_invalidated_review'] = 0
            supervisor['total_tasks_invalidated_review_completed'] = 0
            supervisor['total_tasks_invalidated_review_in_pending'] = 0
            supervisor['validation_percent'] = 0
            supervisor['decision_percent'] = 0

            aggregated_data = (
                AggregatedStatus.objects
                .filter(
                    project_id__in=[p.id for p in projects],
                    cycle_id__in=[c.id for p in projects for c in p.cycle_set.all()],
                    facilitator=None,
                    task=None,
                    administrative_level_id__in=[int(_id) for _id in cantons_stabilized_ids]
                ).distinct()
                .values("project_id", "cycle_id")
                .annotate(
                    total_tasks=Sum('total_tasks'),
                    total_tasks_completed=Sum('total_tasks_completed'),
                    total_tasks_validated=Sum('total_tasks_validated'),
                    total_tasks_invalidated=Sum('total_tasks_invalidated'),
                    total_tasks_waiting_validation=Sum("total_tasks_waiting_validation"),
                    total_tasks_invalidated_review=Sum("total_tasks_invalidated_review"),
                    total_tasks_invalidated_review_completed=Sum("total_tasks_invalidated_review_completed"),
                    total_tasks_invalidated_review_in_pending=Sum("total_tasks_invalidated_review_in_pending")
                )
            )
            aggregated_map = {
                (item["project_id"], item["cycle_id"]): item
                for item in aggregated_data
            }
            
            for project in projects:
                
                invalidation_notifications[project.name] = {'project_id': project.name}

                for cycle in project.cycle_set.all():

                    invalidation_notifications[project.name][cycle.name] = {'cycle_id': cycle.name}
                    
                    invalidation_notifications[project.name][cycle.name]['total_tasks'] = aggregated_map.get((project.id, cycle.id), {}).get('total_tasks') or 0
                    invalidation_notifications[project.name][cycle.name]['total_tasks_completed'] = aggregated_map.get((project.id, cycle.id), {}).get('total_tasks_completed') or 0
                    invalidation_notifications[project.name][cycle.name]['total_tasks_validated'] = aggregated_map.get((project.id, cycle.id), {}).get('total_tasks_validated') or 0
                    invalidation_notifications[project.name][cycle.name]['total_tasks_invalidated'] = aggregated_map.get((project.id, cycle.id), {}).get('total_tasks_invalidated') or 0
                    invalidation_notifications[project.name][cycle.name]['total_tasks_waiting_validation'] = aggregated_map.get((project.id, cycle.id), {}).get('total_tasks_waiting_validation') or 0
                    invalidation_notifications[project.name][cycle.name]['total_tasks_invalidated_review'] = aggregated_map.get((project.id, cycle.id), {}).get('total_tasks_invalidated_review') or 0
                    invalidation_notifications[project.name][cycle.name]['total_tasks_invalidated_review_completed'] = aggregated_map.get((project.id, cycle.id), {}).get('total_tasks_invalidated_review_completed') or 0
                    invalidation_notifications[project.name][cycle.name]['total_tasks_invalidated_review_in_pending'] = aggregated_map.get((project.id, cycle.id), {}).get('total_tasks_invalidated_review_in_pending') or 0
                    invalidation_notifications[project.name][cycle.name]['validation_percent'] = (
                        float("%.2f" % (((invalidation_notifications[project.name][cycle.name]['total_tasks_validated']/invalidation_notifications[project.name][cycle.name]['total_tasks_completed'])*100) if invalidation_notifications[project.name][cycle.name]['total_tasks_completed'] else 0))
                    )
                    invalidation_notifications[project.name][cycle.name]['decision_percent'] = (
                        float("%.2f" % ((((
                            invalidation_notifications[project.name][cycle.name]['total_tasks_validated'] + invalidation_notifications[project.name][cycle.name]['total_tasks_invalidated']
                        )/invalidation_notifications[project.name][cycle.name]['total_tasks_completed'])*100) if invalidation_notifications[project.name][cycle.name]['total_tasks_completed'] else 0))
                    )
                    
                    supervisor['total_tasks'] += invalidation_notifications[project.name][cycle.name]['total_tasks']
                    supervisor['total_tasks_completed'] += invalidation_notifications[project.name][cycle.name]['total_tasks_completed']
                    supervisor['total_tasks_validated'] += invalidation_notifications[project.name][cycle.name]['total_tasks_validated']
                    supervisor['total_tasks_invalidated'] += invalidation_notifications[project.name][cycle.name]['total_tasks_invalidated']
                    supervisor['total_tasks_waiting_validation'] += invalidation_notifications[project.name][cycle.name]['total_tasks_waiting_validation']
                    supervisor['total_tasks_invalidated_review'] += invalidation_notifications[project.name][cycle.name]['total_tasks_invalidated_review']
                    supervisor['total_tasks_invalidated_review_completed'] += invalidation_notifications[project.name][cycle.name]['total_tasks_invalidated_review_completed']
                    supervisor['total_tasks_invalidated_review_in_pending'] += invalidation_notifications[project.name][cycle.name]['total_tasks_invalidated_review_in_pending']

            supervisor['invalidation_notifications'] = invalidation_notifications
            supervisor['invalidation_notifications_id'] = f"invalidation_notifications_{supervisor['user_object_cdd_id']}"
            
            supervisor['cantons_names'] = list_with_and(cantons_stabilized_names)
            supervisor['cantons_names_id'] = f"cantons_names_{supervisor['user_object_cdd_id']}"

            supervisor['validation_percent'] = (
                float("%.2f" % (((supervisor['total_tasks_validated']/supervisor['total_tasks_completed'])*100) if supervisor['total_tasks_completed'] else 0))
            )
            supervisor['decision_percent'] = (
                float("%.2f" % ((((
                    supervisor['total_tasks_validated'] + supervisor['total_tasks_invalidated']
                )/supervisor['total_tasks_completed'])*100) if supervisor['total_tasks_completed'] else 0))
            )
            
        attach_cantons_details(supervisors, projects)
        return supervisors

    def get_queryset(self):
        return self.get_results()
    