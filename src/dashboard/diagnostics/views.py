from multiprocessing import context
from django.views.generic import FormView, View as GenericView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin

from dashboard.facilitators.repository.db_facilitator_repository import FacilitatorRepository
from dashboard.facilitators.repository.facilitator_criteria import FacilitatorCriteria
from dashboard.mixins import PageMixin, AJAXRequestMixin, JSONResponseMixin
from django.utils.translation import gettext_lazy
from django.conf import settings
from dashboard.diagnostics.forms import DiagnosticsForm
from django.contrib.auth import get_user_model
from django.db.models import Sum
import itertools

from no_sql_client import NoSQLClient
from dashboard.administrative_levels.functions import (get_cascade_villages_by_administrative_level_id,
                                                       get_administrative_level_under_json)
from process_manager.models import Task, Phase, Activity, AggregatedStatus, Project, Cycle, AggregatedStatusFacilitator
from assignments.models import AssignAdministrativeLevelToFacilitator
from administrativelevels.models import CVD, AdministrativeLevel
from cdd.call_objects_from_other_db import mis_objects_call
from subprojects.models import Project as MisProject, Cycle as MisCycle
from dashboard.facilitators.functions import update_facilitators_stats

User = get_user_model()

class DashboardDiagnosticsCDDView(PageMixin, LoginRequiredMixin, FormView):
    
    template_name = 'diagnostics/diagnostics.html'
    context_object_name = 'Diagnostics'
    title = gettext_lazy('diagnostics')
    active_level1 = 'diagnostics'
    form_class = DiagnosticsForm
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['breadcrumb'] = False
        context['form'] = DiagnosticsForm(initial={'project_id': self.request.session.get('project_id'), 'cycle_id': self.request.session.get('cycle_id')})
        context['access_token'] = settings.MAPBOX_ACCESS_TOKEN
        context['lat'] = settings.DIAGNOSTIC_MAP_LATITUDE
        context['lng'] = settings.DIAGNOSTIC_MAP_LONGITUDE
        context['zoom'] = settings.DIAGNOSTIC_MAP_ZOOM
        context['ws_bound'] = settings.DIAGNOSTIC_MAP_WS_BOUND
        context['en_bound'] = settings.DIAGNOSTIC_MAP_EN_BOUND
        context['country_iso_code'] = settings.DIAGNOSTIC_MAP_ISO_CODE

        context['list_fields'] = ["phase", "activity", "task", "region", "prefecture", "commune", "canton", "village"]
        
        
        context['last_update'] = AggregatedStatus.objects.filter(project_id=self.request.session.get('project_id'), cycle_id=self.request.session.get('cycle_id'), task__isnull=False, facilitator=None).order_by('-updated_date').first().updated_date
        

        return context

    def render_to_response(self, context, **response_kwargs):
        """
        Return a response, using the `response_class` for this view, with a
        template rendered with the given context.
        Pass response_kwargs to the constructor of the response class.
        """
        response_kwargs.setdefault('content_type', self.content_type)
        return self.response_class(
            request=self.request,
            template=self.get_template_names(),
            context=context,
            using=self.template_engine,
            **response_kwargs
        )


class DiagnosticsStatsTableView(LoginRequiredMixin, ListView):
    template_name = 'diagnostics/components/stats.html'
    context_object_name = 'object'

    def get_queryset(self):
        nsc = NoSQLClient()
        eadls = nsc.get_db('eadls')

        # Infos Generales
        project = Project.objects.get(id=self.request.session.get('project_id'))
        cycle = Cycle.objects.get(id=self.request.session.get('cycle_id'))
        project_id = project.id
        project_mis = mis_objects_call.filter_objects(MisProject, name=self.request.session.get('project_name'))
        project_mis_id = project_mis.first().id if project_mis.count() >= 1 else 1
        cycle_mis = mis_objects_call.filter_objects(MisCycle, order=cycle.order, project_id=project_mis_id)
        cycle_mis_id = cycle_mis.first().id if cycle_mis.exists() else None

        community_facilitators = FacilitatorRepository().find_by_criteria(
            criteria=FacilitatorCriteria(
                facilitator_type='community_facilitator',
                develop_mode=False,
                training_mode=False,
                active=True,
                projects__id=[self.request.session.get('project_id')]
            )
        )
        community_facilitators_count = community_facilitators.count()
        technical_facilitators = FacilitatorRepository().find_by_criteria(
            criteria=FacilitatorCriteria(
                facilitator_type='technical_facilitator',
                develop_mode=False,
                training_mode=False,
                active=True,
                projects__id=[self.request.session.get('project_id')]
            )
        )
        technical_facilitators_count = technical_facilitators.count()
        supervisors = User.objects.filter(
            groups__name__in=['Supervisor'],
            is_active=True,
            projects__in=[self.request.session.get('project_id')]
        )
        supervisors_count = supervisors.count()
        CDDSpecialists = User.objects.filter(
            groups__name__in=['CDDSpecialist'],
            is_active=True,
            projects__in=[self.request.session.get('project_id')]
        )
        CDDSpecialists_count = CDDSpecialists.count()
        others_users = User.objects.filter(
            projects__in=[self.request.session.get('project_id')],
            is_active=True,
        ).exclude(
            groups__name__in=['Supervisor', 'CDDSpecialist']
        )
        others_users_count = others_users.count()
        
        total_users = community_facilitators_count + technical_facilitators_count + supervisors_count + CDDSpecialists_count + others_users_count


        aggregated_status_project = AggregatedStatus.objects.filter(
            project_id=project_id, cycle_id=self.request.session.get('cycle_id'), facilitator=None, task=None,
            administrative_level_id__in=list(mis_objects_call.filter_objects(AdministrativeLevel, type='Region', administrative_levels_projects__in=[project_mis_id], administrative_levels_cycles__in=[cycle_mis_id]).values_list('id', flat=True))
        ).aggregate(
            total_tasks_completed=Sum('total_tasks_completed'),
            total_tasks=Sum('total_tasks'),
            total_tasks_validated=Sum('total_tasks_validated'),
            total_tasks_waiting_validation=Sum('total_tasks_waiting_validation'),
            total_tasks_invalidated=Sum('total_tasks_invalidated'),
            total_tasks_invalidated_review=Sum('total_tasks_invalidated_review'),
            total_tasks_invalidated_unreview=Sum('total_tasks_invalidated_unreview'),
        )
        
        nbr_tasks_completed = aggregated_status_project['total_tasks_completed'] or 0
        nbr_tasks = aggregated_status_project['total_tasks'] or 0
        nbr_tasks_validated = aggregated_status_project['total_tasks_validated'] or 0
        nbr_tasks_waiting_validation = aggregated_status_project['total_tasks_waiting_validation'] or 0
        nbr_tasks_invalidated = aggregated_status_project['total_tasks_invalidated'] or 0
        nbr_tasks_invalidated_review = aggregated_status_project['total_tasks_invalidated_review'] or 0
        nbr_tasks_invalidated_unreview = aggregated_status_project['total_tasks_invalidated_unreview'] or 0
        percentage_tasks_completed = float("%.2f" % (nbr_tasks_completed / nbr_tasks * 100) if nbr_tasks > 0 else 0)
        percentage_tasks_completed_validated = float("%.2f" % (nbr_tasks_validated / nbr_tasks_completed * 100) if nbr_tasks_completed > 0 else 0)

        facilitators = update_facilitators_stats(
            community_facilitators, 
            [],
            self.request.session.get('project_id'), 
            self.request.session.get('cycle_id'),
            self.request.session.get('project_couch_id'),
            project_mis
        )
        facilitators_stabilized_all_docs = [
            doc.get('doc') for doc in eadls.all_docs(include_docs=True)['rows'] \
                if (
                    type(doc) is dict and doc.get('doc') and doc.get('doc').get('type') == 'adl' and \
                    doc.get('doc').get('representative') and doc.get('doc').get('representative').get('email')
                )
        ]

        adls_emaails = [
            obj.email for obj in technical_facilitators
        ]
        
        technical_facilitators_stabilized = [
            doc for doc in facilitators_stabilized_all_docs if doc.get('representative').get('email') in adls_emaails
        ]
        
        # End Infos Generales

        return {
            "community_facilitators": community_facilitators,
            "community_facilitators_count": community_facilitators_count,
            "technical_facilitators": technical_facilitators,
            "technical_facilitators_count": technical_facilitators_count,
            "supervisors": supervisors,
            "supervisors_count": supervisors_count,
            "CDDSpecialists": CDDSpecialists,
            "CDDSpecialists_count": CDDSpecialists_count,
            "others_users": others_users,
            "others_users_count": others_users_count,
            "total_users": total_users,
            "nbr_tasks_completed": nbr_tasks_completed,
            "nbr_tasks": nbr_tasks,
            "nbr_tasks_validated": nbr_tasks_validated,
            "nbr_tasks_waiting_validation": nbr_tasks_waiting_validation,
            "nbr_tasks_invalidated": nbr_tasks_invalidated,
            "nbr_tasks_invalidated_review": nbr_tasks_invalidated_review,
            "nbr_tasks_invalidated_unreview": nbr_tasks_invalidated_unreview,
            "percentage_tasks_completed": percentage_tasks_completed,
            "percentage_tasks_completed_validated": percentage_tasks_completed_validated,
            "facilitators": facilitators,
            "technical_facilitators_stabilized": technical_facilitators_stabilized
        }



class GetTasksDiagnosticsView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, GenericView):
    
    # nsc = NoSQLClient()
    # eadls = nsc.get_db('eadls')
    # docs_eadls = eadls.all_docs(include_docs=True)['rows']
    # docs_eadls_dict = {doc.get('doc').get('representative').get('email'): list(itertools.chain(*[[str(v['id']) for v in ad['villages']] for ad in doc.get('doc')['administrative_regions_objects']])) for doc in docs_eadls if doc.get('doc') and doc.get('doc').get('type') == 'adl' and doc.get('doc').get('representative') and doc.get('doc').get('administrative_regions_objects')}
    # print("ici docs_eadls_dict")
    def get_value(self, *values):
        for value in values:
            if value:
                return int(value)
        return None

    def get(self, request, *args, **kwargs):
        
        project = Project.objects.get(id=self.request.session.get('project_id'))
        cycle = Cycle.objects.get(id=self.request.session.get('cycle_id'))
        project_id = project.id
        project_mis = mis_objects_call.filter_objects(MisProject, name=self.request.session.get('project_name'))
        project_mis_id = project_mis.first().id if project_mis.count() >= 1 else 1
        cycle_mis = mis_objects_call.filter_objects(MisCycle, order=cycle.order, project_id=project_mis_id)
        cycle_mis_id = cycle_mis.first().id if cycle_mis.exists() else None

        _type = request.GET.get('type')
        type_header = _type
        sql_id = request.GET.get('sql_id')
        type_p_a_t = request.GET.get('type_p_a_t')
        type_ad_level = request.GET.get('type_ad_level')
        val_p_a_t = request.GET.get('val_p_a_t')
        val_ad_level = request.GET.get('val_ad_level')

        if not sql_id:
            raise Exception("The value of the element must be not null!!!")
        
        liste_villages = []
        nbr_tasks = 0
        nbr_tasks_completed = 0
        nbr_facilitators = 0
        nbr_villages = 0
        nbr_cvds = 0
        search_by_locality = False
        regions = {}
        for r in mis_objects_call.filter_objects(AdministrativeLevel, type='Region', administrative_levels_projects__in=[project_mis_id], administrative_levels_cycles__in=[cycle_mis_id]):
            regions[r.name] = {
                "nbr_tasks": 0,
                "nbr_tasks_completed": 0,
                "nbr_cvds": 0,
                "nbr_villages": 0,
                "nbr_tasks_validated": 0,
                "nbr_tasks_waiting_validation": 0,
                "nbr_tasks_invalidated": 0,
                "nbr_tasks_invalidated_review": 0,
                "nbr_tasks_invalidated_unreview": 0,
                "percentage_tasks_completed": 0,
                'percentage_tasks_completed_validated': 0,
            }
        
        assigns = mis_objects_call.filter_objects(AssignAdministrativeLevelToFacilitator, project_id=project_mis_id)
        assigns_adl_ids = list(assigns.values_list('administrative_level_id', flat=True))
        aggregated_status_project = AggregatedStatus.objects.filter(project_id=project_id, cycle_id=self.request.session.get('cycle_id'), facilitator=None)
        aggregated_status_project_adl_ids = list(aggregated_status_project.values_list('administrative_level_id', flat=True))
        aggregated_status_taks = None
        if _type == "all" or type_p_a_t in ["phase", "activity", "task"]:
            tasks = []
            if type_p_a_t == "phase":
                tasks = Phase.objects.get(id=self.get_value(val_p_a_t, sql_id), project_id=project_id).task_set.get_queryset()
            elif type_p_a_t == "activity":
                tasks = Activity.objects.get(id=self.get_value(val_p_a_t, sql_id), project_id=project_id).task_set.get_queryset()
            elif type_p_a_t == "task":
                tasks.append(Task.objects.get(id=self.get_value(val_p_a_t, sql_id), project_id=project_id))
            else:
                tasks = Task.objects.filter(project_id=project_id).get_objects_by_general_filtre(request=self.request, attrs=None)
            
            aggregated_status_taks = aggregated_status_project.filter(task_id__in=[t.id for t in tasks])

        if _type in ["region", "prefecture", "commune", "canton", "village"] or type_ad_level in ["region", "prefecture", "commune", "canton", "village"]:
            region = None
            if type_ad_level == "region":
                region = mis_objects_call.filter_objects(AdministrativeLevel, type='Region', id=self.get_value(val_ad_level, sql_id)).first()
            elif type_ad_level == "prefecture":
                region = mis_objects_call.filter_objects(AdministrativeLevel, type='Region', administrativelevel__in=[self.get_value(val_ad_level, sql_id)]).first()
            elif type_ad_level == "commune":
                region = mis_objects_call.filter_objects(AdministrativeLevel, type='Region', administrativelevel__administrativelevel__in=[self.get_value(val_ad_level, sql_id)]).first()
            elif type_ad_level == "canton":
                region = mis_objects_call.filter_objects(AdministrativeLevel, type='Region', administrativelevel__administrativelevel__administrativelevel__in=[self.get_value(val_ad_level, sql_id)]).first()
            elif type_ad_level == "village":
                region = mis_objects_call.filter_objects(AdministrativeLevel, type='Region', administrativelevel__administrativelevel__administrativelevel__administrativelevel__in=[self.get_value(val_ad_level, sql_id)]).first()
            
            if region:
                regions = {_k: _v for _k, _v in regions.items() if _k == region.name}
                liste_villages = get_cascade_villages_by_administrative_level_id(self.get_value(val_ad_level, sql_id))

                villages_ids = list(set([
                    v.id for v in mis_objects_call.filter_objects(
                        AdministrativeLevel,type='Village', id__in=[int(v['administrative_id']) for v in liste_villages if int(v['administrative_id']) in aggregated_status_project_adl_ids], administrative_levels_projects__in=[project_mis_id], administrative_levels_cycles__in=[cycle_mis_id]) \
                    if v.id in assigns_adl_ids
                ]))
                
                cvds = mis_objects_call.filter_objects(CVD, headquarters_village__in=villages_ids)
                
                if aggregated_status_taks:
                    aggrs_status_region = aggregated_status_taks.filter(administrative_level_id__in=[c.headquarters_village.id for c in cvds])
                else:
                    aggrs_status_region = aggregated_status_project.filter(administrative_level_id__in=[c.headquarters_village.id for c in cvds], task__isnull=True)

                sums = aggrs_status_region.aggregate(
                    total_tasks_completed=Sum('total_tasks_completed'),
                    total_tasks=Sum('total_tasks'),
                    total_tasks_validated=Sum('total_tasks_validated'),
                    total_tasks_waiting_validation=Sum('total_tasks_waiting_validation'),
                    total_tasks_invalidated=Sum('total_tasks_invalidated'),
                    total_tasks_invalidated_review=Sum('total_tasks_invalidated_review'),
                    total_tasks_invalidated_unreview=Sum('total_tasks_invalidated_unreview'),
                )
                if regions and region.name in regions:
                    regions[region.name]['nbr_tasks_completed'] = sums['total_tasks_completed'] or 0
                    regions[region.name]['nbr_tasks'] = sums['total_tasks'] or 0
                    regions[region.name]['nbr_tasks_validated'] = sums['total_tasks_validated'] or 0
                    regions[region.name]['nbr_tasks_waiting_validation'] = sums['total_tasks_waiting_validation'] or 0
                    regions[region.name]['nbr_tasks_invalidated'] = sums['total_tasks_invalidated'] or 0
                    regions[region.name]['nbr_tasks_invalidated_review'] = sums['total_tasks_invalidated_review'] or 0
                    regions[region.name]['nbr_tasks_invalidated_unreview'] = sums['total_tasks_invalidated_unreview'] or 0

                    regions[region.name]['percentage_tasks_completed'] = ((regions[region.name]["nbr_tasks_completed"]/regions[region.name]["nbr_tasks"])*100) if regions[region.name]["nbr_tasks"] else 0
                    regions[region.name]['percentage_tasks_completed_validated'] = ((regions[region.name]["nbr_tasks_validated"]/regions[region.name]["nbr_tasks_completed"])*100) if regions[region.name]["nbr_tasks_completed"] else 0
                
                    regions[region.name]['nbr_villages'] = len(villages_ids)
                    regions[region.name]['nbr_cvds'] = cvds.count()
                    
                    assign_facilitators = assigns.filter(
                        administrative_level_id__in=villages_ids,
                        project_id=project_mis_id,
                        activated=True
                    )
                    criteria = FacilitatorCriteria(
                        id__in=list(set([int(f.facilitator_id) for f in assign_facilitators])),
                        develop_mode=False,
                        training_mode=False,
                        projects__id=[self.request.session.get('project_id')]
                    )
                    _facilitators = FacilitatorRepository().find_by_criteria(criteria=criteria)
                    
                    nbr_facilitators += _facilitators.count()
                    nbr_villages += len(villages_ids)
                    nbr_cvds += cvds.count()
                    nbr_tasks += regions[region.name]['nbr_tasks']
                    nbr_tasks_completed += regions[region.name]['nbr_tasks_completed']
            

        elif _type in ["phase", "activity", "task", "all"]:

            for k, v in regions.items():
                villages_ids = list(set([
                    v.id for v in mis_objects_call.filter_objects(
                        AdministrativeLevel,type='Village', 
                        id__in=aggregated_status_project_adl_ids,
                        parent__parent__parent__parent__name=k, administrative_levels_projects__in=[project_mis_id], administrative_levels_cycles__in=[cycle_mis_id]
                    ) \
                    if v.id in assigns_adl_ids
                ]))
                cvds = mis_objects_call.filter_objects(CVD, headquarters_village__in=villages_ids)
                
                aggrs_status_region = aggregated_status_taks.filter(administrative_level_id__in=[c.headquarters_village.id for c in cvds])
                sums = aggrs_status_region.aggregate(
                    total_tasks_completed=Sum('total_tasks_completed'),
                    total_tasks=Sum('total_tasks'),
                    total_tasks_validated=Sum('total_tasks_validated'),
                    total_tasks_waiting_validation=Sum('total_tasks_waiting_validation'),
                    total_tasks_invalidated=Sum('total_tasks_invalidated'),
                    total_tasks_invalidated_review=Sum('total_tasks_invalidated_review'),
                    total_tasks_invalidated_unreview=Sum('total_tasks_invalidated_unreview'),
                )
                regions[k]['nbr_tasks_completed'] = sums['total_tasks_completed'] or 0
                regions[k]['nbr_tasks'] = sums['total_tasks'] or 0
                regions[k]['nbr_tasks_validated'] = sums['total_tasks_validated'] or 0
                regions[k]['nbr_tasks_waiting_validation'] = sums['total_tasks_waiting_validation'] or 0
                regions[k]['nbr_tasks_invalidated'] = sums['total_tasks_invalidated'] or 0
                regions[k]['nbr_tasks_invalidated_review'] = sums['total_tasks_invalidated_review'] or 0
                regions[k]['nbr_tasks_invalidated_unreview'] = sums['total_tasks_invalidated_unreview'] or 0

                regions[k]['percentage_tasks_completed'] = ((regions[k]["nbr_tasks_completed"]/regions[k]["nbr_tasks"])*100) if regions[k]["nbr_tasks"] else 0
                regions[k]['percentage_tasks_completed_validated'] = ((regions[k]["nbr_tasks_validated"]/regions[k]["nbr_tasks_completed"])*100) if regions[k]["nbr_tasks_completed"] else 0
            
                regions[k]['nbr_villages'] = len(villages_ids)
                regions[k]['nbr_cvds'] = cvds.count()
                
                assign_facilitators = assigns.filter(
                    administrative_level_id__in=villages_ids,
                    project_id=project_mis_id,
                    activated=True
                )
                criteria = FacilitatorCriteria(
                    id__in=list(set([int(f.facilitator_id) for f in assign_facilitators])),
                    develop_mode=False,
                    training_mode=False,
                    projects__id=[self.request.session.get('project_id')]
                )
                _facilitators = FacilitatorRepository().find_by_criteria(criteria=criteria)
                
                nbr_facilitators += _facilitators.count()
                nbr_villages += len(villages_ids)
                nbr_cvds += cvds.count()
                nbr_tasks += regions[k]['nbr_tasks']
                nbr_tasks_completed += regions[k]['nbr_tasks_completed']
                  

        return self.render_to_json_response({
            "type": type_header, 
            "regions": regions,
            "search_by_locality": search_by_locality,
            "nbr_facilitators": nbr_facilitators,
            "nbr_villages": nbr_villages,
            "nbr_cvds": nbr_cvds,
            "nbr_tasks": nbr_tasks,
            "nbr_tasks_completed": nbr_tasks_completed,
        }, safe=False)