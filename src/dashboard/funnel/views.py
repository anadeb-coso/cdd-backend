from django.views.generic import FormView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from dashboard.mixins import PageMixin
from django.utils.translation import gettext_lazy
from authentication.models import Facilitator
from dashboard.diagnostics.forms import DiagnosticsForm
from dashboard.mixins import PageMixin, AJAXRequestMixin, JSONResponseMixin
from process_manager.models import Phase, AggregatedStatus, Activity, Task
from administrativelevels.models import AdministrativeLevel
from .functions import get_item_phase, get_region_id


class FunnelsView(PageMixin, LoginRequiredMixin, FormView):
    
    template_name = 'funnel/funnels.html'
    context_object_name = 'funnels'
    active_level1 = 'funnels'
    form_class = DiagnosticsForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['list_fields'] = ["phase", "activity", "task", "region", "prefecture", "commune", "canton", "village"]

        return context
    



class GetFunnelsView(AJAXRequestMixin, LoginRequiredMixin, ListView):
    template_name = 'funnel/funnel_list.html'
    context_object_name = 'funnels'

    def get_queryset(self):
        _type = self.request.GET.get('type')
        type_header = _type
        sql_id = self.request.GET.get('sql_id')
        if _type and not sql_id:
            raise Exception("The value of the element must be not null!!!")
        
        search_by_locality = False
        phases = Phase.objects.all()
        regions = AdministrativeLevel.objects.using('mis').filter(type='Region')
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
        if _type in ["region", "prefecture", "commune", "canton", "village"]:
            search_by_locality = True
            status = AggregatedStatus.objects.filter(administrative_level_id=int(sql_id))

        elif _type in ["phase", "activity", "task"]:
            tasks = []
            if _type == "phase":
                tasks = Phase.objects.get(id=int(sql_id)).task_set.get_queryset()
            elif _type == "activity":
                tasks = Activity.objects.get(id=int(sql_id)).task_set.get_queryset()
            else:
                tasks.append(Task.objects.get(id=int(sql_id)))
                             
            for t in tasks:
                [status.append(o) for o in AggregatedStatus.objects.filter(task_id=t.id) if o.administrative_level_id in regions_id]
        else:
            for r_id in regions_id:
                [status.append(o) for o in AggregatedStatus.objects.filter(administrative_level_id=r_id)]
        
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

        print(dict_phases)
        if search_by_locality:
            return {
                "type": type_header.title(),
                "data": dict_phases
            }
        
        return {
            "type": type_header,
            "data": dict_phases 
        }