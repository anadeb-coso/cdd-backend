from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.translation import gettext_lazy
from django.views import generic
from django.contrib.auth.models import User
import itertools
from django.db.models import Sum

from dashboard.facilitators.forms import FilterFacilitatorForm
from dashboard.mixins import PageMixin
from no_sql_client import NoSQLClient
from dashboard.administrative_levels.functions import get_cascade_villages_by_administrative_level_id
from process_manager.models import AggregatedStatus, Project
from cdd.functions import list_with_and



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
        context['last_update'] = AggregatedStatus.objects.filter(project_id=self.request.session.get('project_id'), cycle_id=self.request.session.get('cycle_id'), task__isnull=False, facilitator=None).order_by('-updated_date').first().updated_date
        
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
        
        nsc = NoSQLClient()
        eadls = nsc.get_db('eadls')
        supervisors = []
        _supervisors = {s[1]: list(s) for s in User.objects.filter(
            groups__name__in=['Supervisor'],
            is_active=True,
            projects__in=[self.request.session.get('project_id')]
        ).values_list('id', 'email', 'username')}
        
        def get_supervisors(docs=None):
            adls_emails = list(_supervisors.keys())

            if docs:
                return [
                    doc for doc in docs if doc.get('representative').get('email') in adls_emails
                ]
            else:
                return list(eadls.get_query_result({
                    "representative.email": {"$in": adls_emails},
                    "type": 'adl'
                }))
        
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
                
                supervisors = eadls.get_view_result(
                    "_design/adl_village_filter", "by_village_id", 
                    keys=[int(v['administrative_id']) for v in liste_villages], 
                    include_docs=True
                )
                if supervisors:
                    _f_s = []
                    for row in supervisors[:]:
                        elt = row['doc']
                        if elt not in _f_s:
                            _f_s.append(elt)
                    supervisors = get_supervisors(_f_s)
                
            else:
                supervisors = get_supervisors()
        else:
            supervisors = get_supervisors()

        projects = Project.objects.filter(users__in=[self.request.user.id]).prefetch_related("cycle_set")

        for supervisor in supervisors:
            supervisor['user_object_cdd_id'] = _supervisors[supervisor['representative']['email']][0]
            supervisor['user_object_cdd_username'] = _supervisors[supervisor['representative']['email']][2]


            administrative_regions_objects = supervisor.get('administrative_regions_objects')
            cantons_stabilized_ids = list(set(
                list(itertools.chain(*[[str(ad['id'])] for ad in (administrative_regions_objects if administrative_regions_objects else []) if ad and type(ad) is dict and 'id' in ad]))
            ))
            cantons_stabilized_names = list(set(
                list(itertools.chain(*[[str(ad['name'])] for ad in (administrative_regions_objects if administrative_regions_objects else []) if ad and type(ad) is dict and 'name' in ad]))
            ))
            
            invalidation_notifications = {}
            supervisor['total_tasks'] = 0
            supervisor['total_tasks_completed'] = 0
            supervisor['total_tasks_validated'] = 0
            supervisor['total_tasks_invalidated'] = 0
            supervisor['total_tasks_waiting_validation'] = 0
            supervisor['total_tasks_invalidated_review'] = 0
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
                    total_tasks_invalidated_review=Sum("total_tasks_invalidated_review")
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
            
        return supervisors

    def get_queryset(self):
        return self.get_results()
    