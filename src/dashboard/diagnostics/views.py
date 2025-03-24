from django.views.generic import FormView, View as GenericView
from django.contrib.auth.mixins import LoginRequiredMixin

from dashboard.facilitators.repository.db_facilitator_repository import FacilitatorRepository
from dashboard.facilitators.repository.facilitator_criteria import FacilitatorCriteria
from dashboard.mixins import PageMixin, AJAXRequestMixin, JSONResponseMixin
from django.utils.translation import gettext_lazy
from django.conf import settings
from dashboard.diagnostics.forms import DiagnosticsForm

from no_sql_client import NoSQLClient
from dashboard.administrative_levels.functions import (get_cascade_villages_by_administrative_level_id,
                                                       get_administrative_level_under_json)
from process_manager.models import Task, Phase, Activity, AggregatedStatus, Project
from assignments.models import AssignAdministrativeLevelToFacilitator
from administrativelevels.models import CVD, AdministrativeLevel
from cdd.call_objects_from_other_db import mis_objects_call
from subprojects.models import Project as MisProject

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
        context['form'] = DiagnosticsForm(initial={'project_id': self.request.session.get('project_id')})
        context['access_token'] = settings.MAPBOX_ACCESS_TOKEN
        context['lat'] = settings.DIAGNOSTIC_MAP_LATITUDE
        context['lng'] = settings.DIAGNOSTIC_MAP_LONGITUDE
        context['zoom'] = settings.DIAGNOSTIC_MAP_ZOOM
        context['ws_bound'] = settings.DIAGNOSTIC_MAP_WS_BOUND
        context['en_bound'] = settings.DIAGNOSTIC_MAP_EN_BOUND
        context['country_iso_code'] = settings.DIAGNOSTIC_MAP_ISO_CODE

        context['list_fields'] = ["phase", "activity", "task", "region", "prefecture", "commune", "canton", "village"]

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

class GetTasksDiagnosticsView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, GenericView):
    def get(self, request, *args, **kwargs):
        
        project = Project.objects.get(id=self.request.session.get('project_id'))
        project_mis = mis_objects_call.filter_objects(MisProject, name=self.request.session.get('project_name'))
        project_mis_id = project_mis.first().id if project_mis.count() >= 1 else 1

        _type = request.GET.get('type')
        type_header = _type
        sql_id = request.GET.get('sql_id')
        if not sql_id:
            raise Exception("The value of the element must be not null!!!")
        nsc = NoSQLClient()
        liste_villages = []
        nbr_tasks = 0
        nbr_tasks_completed = 0
        percentage_tasks_completed = 0
        nbr_facilitators = 0
        nbr_villages = 0
        nbr_cvds = 0
        search_by_locality = False
        already_count_facilitator = False
        _region = None
        regions = {}
        for r in mis_objects_call.filter_objects(AdministrativeLevel, type='Region'):
            regions[r.name] = {
                "nbr_tasks": 0,
                "nbr_tasks_completed": 0,
                "percentage_tasks_completed": 0,
                "nbr_cvds": 0,
                "nbr_villages": 0
            }
        
        assigns = mis_objects_call.filter_objects(AssignAdministrativeLevelToFacilitator, project_id=project_mis_id)
        aggregated_status_project = AggregatedStatus.objects.filter(project_id=project.id)

        if _type in ["region", "prefecture", "commune", "canton", "village"]:
            search_by_locality = True
            
            liste_villages = get_cascade_villages_by_administrative_level_id(int(sql_id))
            
            assign_facilitators = assigns.filter(
                administrative_level_id__in=[int(v['administrative_id']) for v in liste_villages],
                project_id=project_mis_id,
                # activated=True
            )

            criteria = FacilitatorCriteria(
                id__in=list(set([int(f.facilitator_id) for f in assign_facilitators])),
                develop_mode=False,
                training_mode=False,
                projects__id=[self.request.session.get('project_id')]
            )
            _facilitators = FacilitatorRepository().find_by_criteria(criteria)

            nbr_facilitators = _facilitators.count()
            
            for f in _facilitators:
                villages_ids = list(set([ass.administrative_level_id for ass in assigns.filter(id__in=[a_f.id for a_f in assign_facilitators], facilitator_id=f.id) \
                                        #  if ass.activated==True
                                         ]))
                cvds = mis_objects_call.filter_objects(CVD, headquarters_village__in=villages_ids)
                aggrs_status = aggregated_status_project.filter(administrative_level_id__in=[c.headquarters_village.id for c in cvds])
                
                nbr_cvds += cvds.count()
                nbr_villages += len(villages_ids)
                nbr_tasks_completed += sum([agg.total_tasks_completed for agg in aggrs_status])
                nbr_tasks += sum([agg.total_tasks for agg in aggrs_status])
            
            #Backup
            # backup_db = nsc.get_db("backup_db_facilitators_docs")
            # backup_tasks = backup_db.get_view_result('administrative_level', 'by_administrative_level_id', keys=[v['administrative_id'] for v in liste_villages])
            # backup_adls = []
            # if backup_tasks:
            #     _backup_tasks = []
            #     for elt in backup_tasks[:]:
            #         if elt.get('value') and elt.get('value') and elt.get('value').get('type') == 'task' and elt.get('value') not in _backup_tasks:
            #             if int(elt['value']['administrative_level_id']) in list(assigns.filter(activated=False).values_list('administrative_level_id', flat=True)):
            #                 _backup_tasks.append(elt['value'])
            #                 # nbr_tasks_completed += 1 if elt['value']['completed'] else 0
            #                 # nbr_tasks += 1
            #                 backup_adls.append(elt['value']['administrative_level_id'])
            #     # backup_tasks = _backup_tasks
            #     backup_adls = list(set(backup_adls))
            #     nbr_cvds += len(backup_adls)
            #     nbr_villages += len(list(set([_elt.id for o in mis_objects_call.filter_objects(AdministrativeLevel, id__in=[int(elt) for elt in backup_adls]) for _elt in o.cvd.get_villages()])))
            #End Backup
                        
            if nbr_villages > 0:
                ad_obj = mis_objects_call.get_object(AdministrativeLevel, id=int(liste_villages[0]['administrative_id']))
                _region = get_administrative_level_under_json(
                    ad_obj.parent.parent.parent.parent
                )
                

            percentage_tasks_completed = ((nbr_tasks_completed/nbr_tasks)*100) if nbr_tasks else 0

        elif _type in ["phase", "activity", "task", "all"]:
            tasks = []
            if _type == "phase":
                tasks = Phase.objects.get(id=int(sql_id)).task_set.get_queryset()
            elif _type == "activity":
                tasks = Activity.objects.get(id=int(sql_id)).task_set.get_queryset()
            elif _type == "task":
                tasks.append(Task.objects.get(id=int(sql_id)))
            else:
                tasks = Task.objects.filter(project_id=self.request.session.get('project_id'))
            
            aggrs_status = aggregated_status_project.filter(task_id__in=[t.id for t in tasks])

            for k, v in regions.items():
                villages_ids = list(set([
                    v.id for v in mis_objects_call.filter_objects(AdministrativeLevel,type='Village', parent__parent__parent__parent__name=k) \
                    # if v.id in list(assigns.filter(activated=True).values_list('administrative_level_id', flat=True))
                    if v.id in list(assigns.values_list('administrative_level_id', flat=True))
                ]))
                cvds = mis_objects_call.filter_objects(CVD, headquarters_village__in=villages_ids)

                # aggrs_status_region = aggrs_status.filter(administrative_level_id=mis_objects_call.get_object(AdministrativeLevel, type='Region', name=k).id)
                aggrs_status_region = aggrs_status.filter(administrative_level_id__in=[c.headquarters_village.id for c in cvds])
                regions[k]['nbr_tasks'] = sum([agg.total_tasks for agg in aggrs_status_region])
                regions[k]['nbr_tasks_completed'] = sum([agg.total_tasks_completed for agg in aggrs_status_region])
                regions[k]['percentage_tasks_completed'] = ((regions[k]["nbr_tasks_completed"]/regions[k]["nbr_tasks"])*100) if regions[k]["nbr_tasks"] else 0
            
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
            
            #Backup
            # backup_db = nsc.get_db("backup_db_facilitators_docs")
            # backup_tasks = backup_db.get_view_result('task', 'by_task_id', keys=[t.id for t in tasks])
            # backup_adls = []
            # if backup_tasks:
            #     _backup_tasks = []
            #     for elt in backup_tasks[:]:
            #         if elt.get('value') and elt.get('value') and elt.get('value').get('type') == 'task' and elt.get('value') not in _backup_tasks:
            #             if int(elt['value']['administrative_level_id']) in list(assigns.filter(activated=False).values_list('administrative_level_id', flat=True)):
            #                 _backup_tasks.append(elt['value'])
            #                 # nbr_tasks_completed += 1 if elt['value']['completed'] else 0
            #                 # nbr_tasks += 1
            #                 backup_adls.append(elt['value']['administrative_level_id'])
            #     # backup_tasks = _backup_tasks
                
            #     backup_adls = list(set(backup_adls))
            #     nbr_cvds += len(backup_adls)
            #     nbr_villages += len(list(set([_elt.id for o in mis_objects_call.filter_objects(AdministrativeLevel, id__in=[int(elt) for elt in backup_adls]) for _elt in o.cvd.get_villages()])))
            #End Backup
        # else:
        #     search_by_locality = True
        #     facilitators = Facilitator.objects.filter(active=True, develop_mode=False, training_mode=False)

        #     cvds = mis_objects_call.filter_objects(CVD)
        #     aggrs_status = AggregatedStatus.objects.filter(administrative_level_id__in=[c.headquarters_village.id for c in cvds])
            
        #     nbr_cvds += cvds.count()
        #     nbr_villages += mis_objects_call.filter_objects(
        #         AdministrativeLevel, type='Village',
        #         id__in=list(assigns.filter(facilitator_id__in=list(facilitators.values_list('id', flat=True))).values_list('administrative_level_id', flat=True))
        #         ).count()
        #     nbr_tasks_completed += sum([agg.total_tasks_completed for agg in aggrs_status])
        #     nbr_tasks += sum([agg.total_tasks for agg in aggrs_status])

        #     percentage_tasks_completed = ((nbr_tasks_completed/nbr_tasks)*100) if nbr_tasks else 0

        #     nbr_facilitators = facilitators.count()

        #     type_header = gettext_lazy('All')
            
        if search_by_locality:
            return self.render_to_json_response({
                "type": type_header.title(), 
                "nbr_tasks": nbr_tasks,
                "nbr_tasks_completed": nbr_tasks_completed,
                "percentage_tasks_completed": percentage_tasks_completed,
                "region": _region["name"] if _region else None,
                "search_by_locality": search_by_locality,
                "nbr_facilitators": nbr_facilitators,
                "nbr_villages": nbr_villages,
                "nbr_cvds": nbr_cvds
            }, safe=False)
        
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