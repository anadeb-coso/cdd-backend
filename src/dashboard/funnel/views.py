from django.views.generic import FormView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from dashboard.mixins import PageMixin
from django.utils.translation import gettext_lazy
from authentication.models import Facilitator
from dashboard.diagnostics.forms import DiagnosticsForm
from dashboard.mixins import PageMixin, AJAXRequestMixin, JSONResponseMixin
from process_manager.models import Phase, AggregatedStatus, Activity, Task, Project, Cycle
from administrativelevels.models import AdministrativeLevel
from .functions import get_item_phase, get_region_id
from .forms import CascadeForm
from subprojects.models import Project as MisProject, Cycle as MisCycle
from cdd.call_objects_from_other_db import mis_objects_call

class FunnelsView(PageMixin, LoginRequiredMixin, FormView):
    
    template_name = 'funnel/funnels.html'
    context_object_name = 'funnels'
    active_level1 = 'funnels'
    title = gettext_lazy('Funnel')
     
    form_class = DiagnosticsForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['breadcrumb'] = False
        context['form'] = DiagnosticsForm(initial={'project_id': self.request.session.get('project_id'), 'cycle_id': self.request.session.get('cycle_id')})

        context['list_fields'] = ["phase", "activity", "task", "region", "prefecture", "commune", "canton", "village"]

        return context
    



class GetFunnelsView(AJAXRequestMixin, LoginRequiredMixin, ListView):
    template_name = 'funnel/funnel_list.html'
    context_object_name = 'funnels'

    def get_queryset(self):
        
        project = Project.objects.get(id=self.request.session.get('project_id'))
        cycle = Cycle.objects.get(id=self.request.session.get('cycle_id'))
        project_id = project.id
        project_mis = mis_objects_call.filter_objects(MisProject, name=self.request.session.get('project_name'))
        project_mis_id = project_mis.first().id if project_mis.count() >= 1 else 1
        cycle_mis = mis_objects_call.filter_objects(MisCycle, order=cycle.order, project_id=project_mis_id)
        cycle_mis_id = cycle_mis.first().id if cycle_mis.exists() else None

        _type = self.request.GET.get('type')
        type_header = _type
        sql_id = self.request.GET.get('sql_id')
        
        type_p_a_t = self.request.GET.get('type_p_a_t')
        type_ad_level = self.request.GET.get('type_ad_level')
        val_p_a_t = self.request.GET.get('val_p_a_t')
        val_ad_level = self.request.GET.get('val_ad_level')

        if _type and not sql_id:
            raise Exception("The value of the element must be not null!!!")
        
        search_by_locality = False
        phases = Phase.objects.get_objects_by_general_filtre(request=self.request, attrs=None)
        regions = AdministrativeLevel.objects.using('mis').filter(type='Region', administrative_levels_projects__in=[project_mis_id], administrative_levels_cycles__in=[cycle_mis_id])
        regions_id = []
        [regions_id.append(elt.id) for elt in regions]
        dict_phases = {}
        for p in phases:
            dict_phases[p.name] = {
                'id': p.id,
                "nbr_tasks": 0,
                "nbr_tasks_completed": 0
            }
            for r in regions:
                dict_phases[p.name][r.name] = {
                    "id": r.id,
                    "type": r.type,
                    "nbr_tasks": 0,
                    "nbr_tasks_completed": 0
                }

        status = []

        aggregated_status_project = AggregatedStatus.all_objects.filter(project_id=self.request.session.get('project_id'), cycle_id=self.request.session.get('cycle_id'), facilitator=None)
        if _type in ["region", "prefecture", "commune", "canton", "village"]:
            search_by_locality = True
            status = aggregated_status_project.filter(administrative_level_id=int(sql_id), task__isnull=False)
            if val_p_a_t and type_p_a_t:
                tasks = []
                if type_p_a_t == "phase":
                    tasks = Phase.objects.get(id=int(val_p_a_t)).task_set.get_queryset()
                elif type_p_a_t == "activity":
                    tasks = Activity.objects.get(id=int(val_p_a_t)).task_set.get_queryset()
                else:
                    tasks.append(Task.objects.get(id=int(val_p_a_t)))
                status = status.filter(task_id__in=[o.id for o in tasks])

        elif _type in ["phase", "activity", "task"]:
            tasks = []
            if _type == "phase":
                tasks = Phase.objects.get(id=int(sql_id)).task_set.get_queryset()
            elif _type == "activity":
                tasks = Activity.objects.get(id=int(sql_id)).task_set.get_queryset()
            else:
                tasks.append(Task.objects.get(id=int(sql_id)))

            if val_ad_level:
                for t in tasks:
                    [status.append(o) for o in aggregated_status_project.filter(task_id=t.id) if o.administrative_level_id == int(val_ad_level)]
            else:
                for t in tasks:
                    [status.append(o) for o in aggregated_status_project.filter(task_id=t.id) if o.administrative_level_id in regions_id]
        else:
            for r_id in regions_id:
                [status.append(o) for o in aggregated_status_project.filter(administrative_level_id=r_id, task__isnull=False)]
                
        # for key, value in dict_phases.items():
        #     if type(value) is dict:
        #         for k, v in value.items():
        #             for s in status:
        #                 if type(v) is dict:
        #                     if dict_phases[key]['id'] == s.task.phase_id and dict_phases[key][k]['id'] == get_region_id(s.administrative_level()):
        #                         dict_phases[key][k]['nbr_tasks_completed'] += s.total_tasks_completed
        #                         dict_phases[key][k]['nbr_tasks'] += s.total_tasks
        # print(len(status))
        for s in status:
            # print()
            # print(s.total_tasks_completed)
            # print(s.total_tasks)
            _name, item = get_item_phase(dict_phases, s.task.phase_id)
            if item:
                for key, value in item.items():
                    if type(value) is dict:
                        if dict_phases[_name]['id'] == s.task.phase_id and dict_phases[_name][key]['id'] == get_region_id(s.administrative_level()):
                            dict_phases[_name][key]['nbr_tasks_completed'] += s.total_tasks_completed
                            dict_phases[_name][key]['nbr_tasks'] += s.total_tasks
                            break

        for key, value in dict_phases.items():
            for k, v in value.items():
                if type(v) is dict:
                    dict_phases[key][k]['percentage_tasks_completed'] = float("%.2f" % ((dict_phases[key][k]['nbr_tasks_completed']/dict_phases[key][k]['nbr_tasks'])*100) if dict_phases[key][k]['nbr_tasks'] else 0)

                    dict_phases[key]['nbr_tasks_completed'] += dict_phases[key][k]['nbr_tasks_completed']
                    dict_phases[key]['nbr_tasks'] += dict_phases[key][k]['nbr_tasks']
            dict_phases[key]['percentage_tasks_completed'] = float("%.2f" % ((dict_phases[key]['nbr_tasks_completed']/dict_phases[key]['nbr_tasks'])*100) if dict_phases[key]['nbr_tasks'] else 0)


        if search_by_locality:
            return {
                "type": type_header.title(),
                "data": dict_phases
            }
        
        return {
            "type": type_header,
            "data": dict_phases 
        }
    


class GetFunnelsFieldsView(AJAXRequestMixin, LoginRequiredMixin, ListView):
    template_name = 'funnel/filters.html'
    context_object_name = 'form'

    def get_queryset(self):
        _type = self.request.GET.get('type')
        sql_id = self.request.GET.get('sql_id')
        
        type_p_a_t = self.request.GET.get('type_p_a_t')
        type_ad_level = self.request.GET.get('type_ad_level')
        val_p_a_t = self.request.GET.get('val_p_a_t')
        val_ad_level = self.request.GET.get('val_ad_level')

        ad_id, phase_id, activity_id, task_id = None, None, None, None
        if _type and not sql_id:
            raise Exception("The value of the element must be not null!!!")
        
        if type_ad_level in ["region", "prefecture", "commune", "canton", "village"] and val_ad_level:
            ad_id = int(val_ad_level)
        if type_p_a_t in ["phase", "activity", "task"] and val_p_a_t:
            if type_p_a_t == "phase":
                phase_id = int(val_p_a_t)
            elif type_p_a_t == "activity":
                activity_id = int(val_p_a_t)
            else:
                task_id = int(val_p_a_t)
        
        return CascadeForm(ad_id, phase_id, activity_id, task_id, self.request.session.get('project_id'), self.request.session.get('cycle_id'))

class GetFunnelsFieldsGlobalView(AJAXRequestMixin, LoginRequiredMixin, ListView):
    template_name = 'funnel/filters.html'
    context_object_name = 'form'

    def get_queryset(self):
        _type = self.request.GET.get('type')
        sql_id = self.request.GET.get('sql_id')
        
        type_p_a_t = self.request.GET.get('type_p_a_t')
        type_ad_level = self.request.GET.get('type_ad_level')
        val_p_a_t = self.request.GET.get('val_p_a_t')
        val_ad_level = self.request.GET.get('val_ad_level')

        ad_id, phase_id, activity_id, task_id = None, None, None, None
        if _type and not sql_id:
            raise Exception("The value of the element must be not null!!!")
        
        if type_ad_level in ["region", "prefecture", "commune", "canton", "village"] and val_ad_level:
            ad_id = int(val_ad_level)
        if type_p_a_t in ["phase", "activity", "task"] and val_p_a_t:
            if type_p_a_t == "phase":
                phase_id = int(val_p_a_t)
            elif type_p_a_t == "activity":
                activity_id = int(val_p_a_t)
            else:
                task_id = int(val_p_a_t)
        
        return CascadeForm(ad_id, phase_id, activity_id, task_id, self.request.session.get('project_id'), self.request.session.get('cycle_id'))
