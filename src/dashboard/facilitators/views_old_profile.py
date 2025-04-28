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
from .functions import get_cvds, single_task_by_cvd, get_search_for_stabilized_facilitator_dbs
from cdd.functions import datetime_complet_str
from cdd.views_manage_url_parse import redirect_user_to_login, redirect_to_an_url
from assignments.models import AssignAdministrativeLevelToFacilitator
from cdd.call_objects_from_other_db import mis_objects_call
from subprojects.models import Project as MisProject


class FacilitatorMixin(LoginRequiredMixin):
    doc = None
    obj = None
    facilitator_db = None
    facilitator_db_name = None
    cvds = None
    facilitator_grm = None
    no_sql_dbs_names_with_village_ids = {}

    def dispatch(self, request, *args, **kwargs):
        nsc = NoSQLClient()
        self.cvds = []
        try:
            if not self.request.user.is_authenticated:
                return redirect_user_to_login(request)
            if not self.request.session.get('project_id') or not self.request.session.get('cycle_id'):
                return redirect_to_an_url(request, 'dashboard:process_manager:list')
                
            self.facilitator_db_name = kwargs['id']
            self.facilitator_db = nsc.get_db(self.facilitator_db_name)
            query_result = self.facilitator_db.get_query_result({"type": 'facilitator'})[:]
            self.doc = self.facilitator_db[query_result[0]['_id']]
            self.obj = get_object_or_404(Facilitator, no_sql_db_name=kwargs['id'])
            
            # eadls = nsc.get_db('eadls')
            # try:
            #     self.facilitator_grm = eadls.get_query_result({
            #         "type": "adl",
            #         "representative.email": self.doc.get('email')
            #     })[:][0]
            #     administrative_regions = self.facilitator_grm['administrative_regions']
                
            #     project_mis = mis_objects_call.filter_objects(MisProject, name=self.request.session.get('project_name'))
            #     project_mis_id = project_mis.first().id if project_mis.count() >= 1 else 1
                
            #     for adl_id in administrative_regions:
            #         if adl_id not in [elt['id'] for elt in self.doc['administrative_levels']]:
            #             assing_facilitator_object = mis_objects_call.filter_objects(
            #                 AssignAdministrativeLevelToFacilitator, 
            #                 project_id=project_mis_id,
            #                 administrative_level_id=int(adl_id)
            #             ).last()
            #             if assing_facilitator_object:
            #                 _facilitator = Facilitator.objects.get(id=assing_facilitator_object.facilitator_id)
            #                 _ids = self.no_sql_dbs_names_with_village_ids[_facilitator.no_sql_db_name]['ids'] if _facilitator.no_sql_db_name in self.no_sql_dbs_names_with_village_ids else []
            #                 _ids.append(adl_id)
            #                 _ids = list(set(_ids))
            #                 self.no_sql_dbs_names_with_village_ids[_facilitator.no_sql_db_name] = {}
            #                 self.no_sql_dbs_names_with_village_ids[_facilitator.no_sql_db_name]['ids'] = list(set(_ids))
            #                 self.no_sql_dbs_names_with_village_ids[_facilitator.no_sql_db_name]['facilitator'] = _facilitator


            #     for k, v in self.no_sql_dbs_names_with_village_ids.items():
            #         self.cvds += get_cvds(nsc.get_db(k).get_query_result({"type": 'facilitator'})[:][0], v['ids'])
                
                
            # except Exception as exc:
            #     print(exc)
            project_mis = mis_objects_call.filter_objects(MisProject, name=self.request.session.get('project_name'))
            project_mis_id = project_mis.first().id if project_mis.count() >= 1 else 1
            self.no_sql_dbs_names_with_village_ids, cvds, administratives_stabilized = get_search_for_stabilized_facilitator_dbs(project_mis_id, self.doc)
            self.cvds += cvds

            self.cvds += get_cvds(self.doc, [], administratives_stabilized)
            self.cvds = sorted(self.cvds, key=lambda obj: obj.get('name'))
                
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
        nsc = NoSQLClient()

        context['facilitator'] = self.obj
        context['form'] = FilterTaskForm(
            initial={
                'facilitator_db_name': self.facilitator_db_name, 
                'project_id': self.request.session.get('project_id'),
                'cycle_id': self.request.session.get('cycle_id'),
                'cvds': self.cvds
            }
        )
        context['breadcrumb'] = False
        context['colors'] = ['warning', 'mediumslateblue', 'gray', 'mediumpurple', 'plum', 'primary', 'danger']

        facilitator_docs = self.facilitator_db.all_docs(include_docs=True)['rows']
        facilitator_docs = [doc for doc in facilitator_docs if doc.get('doc') and doc.get('doc').get('cycle_id') == self.request.session.get('cycle_couch_id') and doc.get('doc').get('project_id') == self.request.session.get('project_couch_id')]

        last_activity_date = "0000-00-00 00:00:00"
        total_tasks = 0
        for doc in facilitator_docs:
            doc = doc.get('doc')
            if doc.get('type') == "task" and doc.get('last_updated') and last_activity_date < datetime_complet_str(doc.get('last_updated')):
                last_activity_date = datetime_complet_str(doc.get('last_updated'))
            total_tasks += 1
        
        for k_db_name, v in self.no_sql_dbs_names_with_village_ids.items():
            _db = nsc.get_db(k_db_name)
            facilitator_docs = _db.get_query_result(
                {"type": "task", 'cycle_id': self.request.session.get('cycle_couch_id'), 'project_id': self.request.session.get('project_couch_id'), "administrative_level_id": {"$in": v['ids']}}, 
                limit=10000
            )[:]
            for doc in facilitator_docs:
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
            "type": "task",
            "project_id": self.request.session.get('project_couch_id')
        }
        
        if self.request.session.get('cycle_couch_id'):
            selector['cycle_id'] = self.request.session.get('cycle_couch_id')

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

        results = self.facilitator_db.get_query_result(selector, limit=10000)[:]
        
        nsc = NoSQLClient()
        for k_db_name, v in self.no_sql_dbs_names_with_village_ids.items():
            if not administrative_level_id:
                selector["administrative_level_id"] = {"$in": v['ids']}
            _db = nsc.get_db(k_db_name)
            results += _db.get_query_result(selector, limit=10000)[:]
        return results
    

    def get_queryset(self):
        index = int(self.request.GET.get('index'))
        offset = int(self.request.GET.get('offset'))
        phases = Phase.objects.get_objects_by_general_filtre(request=self.request, attrs=None)
        activities = Activity.objects.get_objects_by_general_filtre(request=self.request, attrs=None)

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
        total_tasks_validated = 0
        total_tasks_invalidated = 0
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
                            if _.get("validated") == True:
                                total_tasks_validated += 1
                            elif _.get("validated") == False:
                                total_tasks_invalidated += 1
                        else:
                            total_tasks_uncompleted += 1
                        total_tasks += 1

                        if dict_administrative_levels_with_infos.get(administrative_level_cvd.get("name")):
                            if _.get("completed"):
                                dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks_completed'] += 1
                                if _.get("validated") == True:
                                    dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks_validated'] += 1
                                elif _.get("validated") == False:
                                    dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks_invalidated'] += 1
                            else:
                                dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks_uncompleted'] += 1
                            dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks'] += 1
                        else:
                            if _.get("completed"):
                                if _.get("validated") == True:
                                    dict_administrative_levels_with_infos[administrative_level_cvd.get("name")] = {
                                        'total_tasks_completed': 1,
                                        'total_tasks_uncompleted': 0,
                                        'total_tasks_validated': 1,
                                        'total_tasks_invalidated': 0,
                                        'stabilized': administrative_level_cvd.get("stabilized"),
                                        'for_another_facilitator': administrative_level_cvd.get("for_another_facilitator")
                                    }
                                elif _.get("validated") == False:
                                    dict_administrative_levels_with_infos[administrative_level_cvd.get("name")] = {
                                        'total_tasks_completed': 1,
                                        'total_tasks_uncompleted': 0,
                                        'total_tasks_validated': 0,
                                        'total_tasks_invalidated': 1,
                                        'stabilized': administrative_level_cvd.get("stabilized"),
                                        'for_another_facilitator': administrative_level_cvd.get("for_another_facilitator")
                                    }
                                else:
                                    dict_administrative_levels_with_infos[administrative_level_cvd.get("name")] = {
                                        'total_tasks_completed': 1,
                                        'total_tasks_uncompleted': 0,
                                        'total_tasks_validated': 0,
                                        'total_tasks_invalidated': 0,
                                        'stabilized': administrative_level_cvd.get("stabilized"),
                                        'for_another_facilitator': administrative_level_cvd.get("for_another_facilitator")
                                    }
                                
                            else:
                                dict_administrative_levels_with_infos[administrative_level_cvd.get("name")] = {
                                    'total_tasks_completed': 0,
                                    'total_tasks_uncompleted': 1,
                                    'total_tasks_validated': 0,
                                    'total_tasks_invalidated': 0,
                                    'stabilized': administrative_level_cvd.get("stabilized"),
                                    'for_another_facilitator': administrative_level_cvd.get("for_another_facilitator")
                                }
                            dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks'] = 1
                        dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['cvd'] = administrative_level_cvd


        context['total_tasks_completed'] = total_tasks_completed
        context['total_tasks_uncompleted'] = total_tasks_uncompleted
        context['total_tasks_validated'] = total_tasks_validated
        context['total_tasks_invalidated'] = total_tasks_invalidated
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