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

class DashboardDiagnosticsADLView(PageMixin, LoginRequiredMixin, FormView):
    
    template_name = 'diagnostics/cantons_diagnostics.html'
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
        # context['access_token'] = settings.MAPBOX_ACCESS_TOKEN
        # context['lat'] = settings.DIAGNOSTIC_MAP_LATITUDE
        # context['lng'] = settings.DIAGNOSTIC_MAP_LONGITUDE
        # context['zoom'] = settings.DIAGNOSTIC_MAP_ZOOM
        # context['ws_bound'] = settings.DIAGNOSTIC_MAP_WS_BOUND
        # context['en_bound'] = settings.DIAGNOSTIC_MAP_EN_BOUND
        # context['country_iso_code'] = settings.DIAGNOSTIC_MAP_ISO_CODE
        
        
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


class DiagnosticsCantonsView(LoginRequiredMixin, ListView):
    template_name = 'diagnostics/components/cantons.html'
    context_object_name = 'object'

    def get_queryset(self):
        nsc = NoSQLClient()
        eadls = nsc.get_db('eadls')

        if 'cantons_stabilized_ids' in self.request.session and self.request.session['cantons_stabilized_ids'] and self.request.user.groups.filter(name__in=["Supervisor"]).exists():
            projects = Project.objects.filter(users__in=[self.request.user.id]).prefetch_related("cycle_set")
            cycles_order = [c.order for p in projects for c in p.cycle_set.all()]
            projects_mis = mis_objects_call.filter_objects(MisProject, name__in=[p.name for p in projects])
            
            cantons = mis_objects_call.filter_objects(
                AdministrativeLevel, 
                id__in=[int(_id) for _id in self.request.session['cantons_stabilized_ids']], 
                type="Canton",
                administrative_levels_projects__in=[p.id for p in projects_mis], 
                administrative_levels_cycles__in=[c.id for c in mis_objects_call.filter_objects(
                    MisCycle, 
                    project_id__in=[p.id for p in projects_mis],
                    order__in=cycles_order,
                )]
            ).distinct()
            
        else:
            projects = Project.objects.filter(
                id__in=[p.id for p in Project.objects.get(id=self.request.session.get('project_id')).build_the_tree_structure()]
            ).prefetch_related("cycle_set")
            cycles_order = [c.order for p in projects for c in p.cycle_set.all()]
            projects_mis = mis_objects_call.filter_objects(MisProject, name__in=[p.name for p in projects])
            cantons = mis_objects_call.filter_objects(
                AdministrativeLevel, 
                type="Canton",
                administrative_levels_projects__in=[p.id for p in projects_mis], 
                administrative_levels_cycles__in=[c.id for c in mis_objects_call.filter_objects(
                    MisCycle, 
                    project_id__in=[p.id for p in projects_mis],
                    order__in=cycles_order,
                )]
            ).distinct()

        aggregated_data = (
            AggregatedStatus.objects
            .filter(
                project_id__in=[p.id for p in projects],
                cycle_id__in=[c.id for p in projects for c in p.cycle_set.all()],
                facilitator=None,
                task=None,
                administrative_level_id__in=[c.id for c in cantons]
            )
            .values("project_id", "cycle_id", "administrative_level_id")
            .annotate(
                total_tasks_completed=Sum('total_tasks_completed'),
                total_tasks=Sum('total_tasks'),
                total_tasks_validated=Sum('total_tasks_validated'),
                total_tasks_waiting_validation=Sum('total_tasks_waiting_validation'),
                total_tasks_invalidated=Sum('total_tasks_invalidated'),
                total_tasks_invalidated_review=Sum('total_tasks_invalidated_review'),
                total_tasks_invalidated_unreview=Sum('total_tasks_invalidated_unreview'),
            )
        )
        aggregated_map = {
            (item["project_id"], item["cycle_id"], item["administrative_level_id"]): item
            for item in aggregated_data
        }
        
        invalidation_notifications = {}
        
        for project in projects:
            
            invalidation_notifications[project.name] = {'project_id': project.id}

            for cycle in project.cycle_set.all():

                invalidation_notifications[project.name][cycle.name] = {'cycle_id': cycle.id}
                
                for canton in cantons:
                    total_tasks = aggregated_map.get((project.id, cycle.id, canton.id), {}).get('total_tasks') or 0
                    if total_tasks:
                        invalidation_notifications[project.name][cycle.name][(canton.id, canton.name)] = {}
                        invalidation_notifications[project.name][cycle.name][(canton.id, canton.name)]['total_tasks_completed'] = aggregated_map.get((project.id, cycle.id,  canton.id), {}).get('total_tasks_completed') or 0
                        invalidation_notifications[project.name][cycle.name][(canton.id, canton.name)]['total_tasks'] = total_tasks
                        invalidation_notifications[project.name][cycle.name][(canton.id, canton.name)]['total_tasks_validated'] = aggregated_map.get((project.id, cycle.id,  canton.id), {}).get('total_tasks_validated') or 0
                        invalidation_notifications[project.name][cycle.name][(canton.id, canton.name)]['total_tasks_waiting_validation'] = aggregated_map.get((project.id, cycle.id, canton.id), {}).get('total_tasks_waiting_validation') or 0
                        invalidation_notifications[project.name][cycle.name][(canton.id, canton.name)]['total_tasks_invalidated'] = aggregated_map.get((project.id, cycle.id,  canton.id), {}).get('total_tasks_invalidated') or 0
                        invalidation_notifications[project.name][cycle.name][(canton.id, canton.name)]['total_tasks_invalidated_review'] = aggregated_map.get((project.id, cycle.id, canton.id), {}).get('total_tasks_invalidated_review') or 0
                        invalidation_notifications[project.name][cycle.name][(canton.id, canton.name)]['total_tasks_invalidated_unreview'] = aggregated_map.get((project.id, cycle.id,  canton.id), {}).get('total_tasks_invalidated_unreview') or 0
                    

        return invalidation_notifications
    


class CantonDetailForListView(LoginRequiredMixin, AJAXRequestMixin, ListView):
    template_name = 'diagnostics/components/villages.html'
    context_object_name = 'canton_detail_for_list'
        
    def get_queryset(self):
        return []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['canton_id'] = self.request.GET.get('canton_id')
        context['project_id'] = self.request.GET.get('project_id')
        context['cycle_id'] = self.request.GET.get('cycle_id')

        villages = mis_objects_call.filter_objects(
            AdministrativeLevel, 
            parent_id=int(context['canton_id']), 
            type="Village",
        ).distinct()

        villages_ids = [v.id for v in villages]
        aggregated_status = AggregatedStatus.objects.filter(
            project_id=int(context['project_id']),
            cycle_id=int(context['cycle_id']),
            facilitator=None,
            task=None,
            administrative_level_id__in=villages_ids
        )

        project_mis = mis_objects_call.get_object(MisProject, name=Project.objects.get(id=context['project_id']).name)
        
        criteria = FacilitatorCriteria(
            develop_mode=False,
            training_mode=False,
            # active=True,
            projects__id=[int(context['project_id'])],
            facilitator_type='community_facilitator'
        )

        facilitators = {str(f.id): f for f in FacilitatorRepository().find_by_criteria(criteria=criteria)}

        return {
            "villages_aggregated_status": aggregated_status,
            "villages_ids_names": {v.id: v.name if v.name == v.cvd.name else f"{v.name} [{v.cvd.name}]" for v in villages},
            "assigns_adl_to_facilitators": {
                ass.administrative_level_id: facilitators.get(ass.facilitator_id, None) for ass in mis_objects_call.filter_objects(
                    AssignAdministrativeLevelToFacilitator, 
                    project_id=project_mis.id,
                    administrative_level_id__in=villages_ids,
                    activated=True
                ).distinct()
            },
            "project_name": project_mis.name
        }
