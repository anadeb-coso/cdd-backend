from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy
from django.views import generic
from datetime import datetime

from process_manager.models import Phase, Activity
from authentication.models import Facilitator
from dashboard.facilitators.forms import FilterTaskForm
from dashboard.mixins import AJAXRequestMixin, PageMixin
from no_sql_client import NoSQLClient
from .functions import get_cvds, single_task_by_cvd
from cdd.functions import datetime_complet_str


class FacilitatorMixin:
    doc = None
    obj = None
    facilitator_db = None
    facilitator_db_name = None
    cvds = None

    def dispatch(self, request, *args, **kwargs):
        nsc = NoSQLClient()
        try:
            self.facilitator_db_name = kwargs['id']
            self.facilitator_db = nsc.get_db(self.facilitator_db_name)
            query_result = self.facilitator_db.get_query_result({"type": 'facilitator'})[:]
            self.doc = self.facilitator_db[query_result[0]['_id']]
            self.obj = get_object_or_404(Facilitator, no_sql_db_name=kwargs['id'])
            self.cvds = get_cvds(self.doc)
        except Exception:
            raise Http404
        return super().dispatch(request, *args, **kwargs)



class FacilitatorDetailView(FacilitatorMixin, PageMixin, LoginRequiredMixin, generic.DetailView):
    template_name = 'facilitators/old_profile/profile.html'
    context_object_name = 'facilitator_doc'
    title = gettext_lazy('Facilitator Profile')
    active_level1 = 'facilitators'
    model = Facilitator
    breadcrumb = [
        {
            'url': reverse_lazy('dashboard:facilitators:list'),
            'title': gettext_lazy('Facilitators')
        },
        {
            'url': '',
            'title': title
        }
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['facilitator'] = self.obj
        context['form'] = FilterTaskForm(initial={'facilitator_db_name': self.facilitator_db_name, 'project_id': self.request.session.get('project_id')})
        context['breadcrumb'] = False

        facilitator_docs = self.facilitator_db.all_docs(include_docs=True)['rows']
        last_activity_date = "0000-00-00 00:00:00"
        total_tasks = 0
        for doc in facilitator_docs:
            doc = doc.get('doc')
            if doc.get('type') == "task" and doc.get('last_updated') and last_activity_date < datetime_complet_str(doc.get('last_updated')):
                last_activity_date = datetime_complet_str(doc.get('last_updated'))
            total_tasks += 1

        if last_activity_date == "0000-00-00 00:00:00":
            context['facilitator_doc']['last_activity_date'] = None
        else:
            context['facilitator_doc']['last_activity_date'] = datetime.strptime(last_activity_date, '%Y-%m-%d %H:%M:%S')

        context['total_tasks'] = total_tasks

        return context

    def get_object(self, queryset=None):
        return self.doc


class FacilitatorTaskListView(FacilitatorMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'facilitators/old_profile/task_list.html'
    context_object_name = 'tasks'

    def get_results(self):
        administrative_level_id = self.request.GET.get('administrative_level')
        phase_name = self.request.GET.get('phase')
        activity_name = self.request.GET.get('activity')
        task_name = self.request.GET.get('task')
        is_validated = self.request.GET.get('is_validated', None)

        selector = {
            "type": "task"
        }

        if administrative_level_id:
            selector["administrative_level_id"] = administrative_level_id
        if phase_name:
            selector["phase_name"] = phase_name
        if activity_name:
            selector["activity_name"] = activity_name
        if task_name:
            selector["name"] = task_name
        if is_validated not in (None, ''):
            if is_validated == "Validated":
                selector["validated"] = True
            elif is_validated == "Invalidated":
                selector["validated"] = False
            elif is_validated == "Completed":
                selector["completed"] = True
            elif is_validated == "Pending":
                selector["completed"] = False
            elif is_validated == "Untouched":
                q_r = self.facilitator_db.get_query_result(selector)
                r = []
                for task in q_r:
                    if task.get('validated') == None:
                        r.append(task)
                return r

        return self.facilitator_db.get_query_result(selector)

    def get_queryset(self):
        index = int(self.request.GET.get('index'))
        offset = int(self.request.GET.get('offset'))
        phases = Phase.objects.filter(project_id=self.request.session.get('project_id'))
        activities = Activity.objects.filter(project_id=self.request.session.get('project_id'))

        object_list = single_task_by_cvd(self.get_results(), self.cvds)

        if object_list:
            for _ in object_list:
                _["phase_order"] = 0
                _["activity_order"] = 0
                for phase_obj in phases:
                    if phase_obj.name == _["phase_name"]:
                        _["phase_order"]=phase_obj.order
                        break
                for activity_obj in activities:
                    if activity_obj.name == _["activity_name"]:
                        _["activity_order"]=activity_obj.order
                        break


        return sorted(object_list, key=lambda obj: (str(obj["phase_order"])+str(obj["activity_order"])+str(obj["order"])))[index:index + offset]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        total_tasks_completed = 0
        total_tasks_uncompleted = 0
        total_tasks = 0
        dict_administrative_levels_with_infos = {}

        object_list = self.get_results()

        if object_list:
            for _ in object_list:

                for administrative_level_cvd in self.cvds:
                    village = administrative_level_cvd['village']
                    if village and str(village.get("id")) == str(_.get("administrative_level_id")):
                        if _.get("completed"):
                            total_tasks_completed += 1
                        else:
                            total_tasks_uncompleted += 1
                        total_tasks += 1

                        if dict_administrative_levels_with_infos.get(administrative_level_cvd.get("name")):
                            if _.get("completed"):
                                dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks_completed'] += 1
                            else:
                                dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks_uncompleted'] += 1
                            dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks'] += 1
                        else:
                            if _.get("completed"):
                                dict_administrative_levels_with_infos[administrative_level_cvd.get("name")] = {
                                    'total_tasks_completed': 1,
                                    'total_tasks_uncompleted': 0
                                }
                            else:
                                dict_administrative_levels_with_infos[administrative_level_cvd.get("name")] = {
                                    'total_tasks_completed': 0,
                                    'total_tasks_uncompleted': 1
                                }
                            dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks'] = 1
                        dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['cvd'] = administrative_level_cvd


        context['total_tasks_completed'] = total_tasks_completed
        context['total_tasks_uncompleted'] = total_tasks_uncompleted
        context['total_tasks'] = total_tasks
        context['percentage_tasks_completed'] = ((total_tasks_completed/total_tasks)*100) if total_tasks else 0
        context['nbr_villages'] = 0

        for key, value in dict_administrative_levels_with_infos.items():
            dict_administrative_levels_with_infos[key]["percentage_tasks_completed"] = ((value["total_tasks_completed"]/value["total_tasks"])*100) if value["total_tasks"] else 0
            del dict_administrative_levels_with_infos[key]["total_tasks"]

            context['nbr_villages'] += len(dict_administrative_levels_with_infos[key]['cvd']['villages'])

        context['dict_administrative_levels_with_infos'] = dict_administrative_levels_with_infos
        context['facilitator_db_name'] = self.facilitator_db_name

        return context