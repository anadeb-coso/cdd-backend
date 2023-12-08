from django.contrib.auth.hashers import make_password
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import redirect
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy
from django.views import generic
from datetime import datetime

from process_manager.models import Phase, Activity
from authentication.models import Facilitator
from dashboard.facilitators.forms import FacilitatorForm, FilterTaskForm, UpdateFacilitatorForm, FilterFacilitatorForm
from dashboard.mixins import AJAXRequestMixin, PageMixin, JSONResponseMixin
from no_sql_client import NoSQLClient
from dashboard.utils import (
    sync_geographicalunits_with_cvd_on_facilittor, sync_tasks
)
from authentication.permissions import (
    CDDSpecialistPermissionRequiredMixin, SuperAdminPermissionRequiredMixin,
    AdminPermissionRequiredMixin
    )
from .functions import (
    get_cvds, get_cvd_name_by_village_id, is_village_principal, single_task_by_cvd,
    clear_facilitator_docs_by_administrativelevels_and_save_to_backup_db)
from administrativelevels import models as administrativelevels_models
from assignments.models import AssignAdministrativeLevelToFacilitator
from dashboard.administrative_levels.functions import get_administrative_levels_under_json, get_cascade_villages_by_administrative_level_id
from cdd.functions import datetime_complet_str, exists_id_in_a_dict


class FacilitatorListView(PageMixin, LoginRequiredMixin, generic.ListView):
    model = Facilitator
    queryset = Facilitator.objects.all()
    template_name = 'facilitators/list.html'
    context_object_name = 'facilitators'
    title = gettext_lazy('Facilitators')
    active_level1 = 'facilitators'
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

        context['is_training'] = bool(self.request.GET.get('training', '0') != '0')
        context['is_develop'] = bool(self.request.GET.get('develop', '0') != '0')

        return context


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



class FacilitatorListTableView(LoginRequiredMixin, generic.ListView):
    template_name = 'facilitators/facilitator_list.html'
    context_object_name = 'facilitators'

    def get_results(self):
        id_region = self.request.GET.get('id_region')
        id_prefecture = self.request.GET.get('id_prefecture')
        id_commune = self.request.GET.get('id_commune')
        id_canton = self.request.GET.get('id_canton')
        id_village = self.request.GET.get('id_village')
        type_field = self.request.GET.get('type_field')
        _id = 0
        facilitators = []
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
                
            nsc = NoSQLClient()

            liste_prefectures = []
            liste_communes = []
            liste_cantons = []
            liste_villages = []
            # administrative_levels = nsc.get_db("administrative_levels").all_docs(include_docs=True)['rows']

            # if _type == "region":
            ##    region = get_all_docs_administrative_levels_by_type_and_administrative_id(administrative_levels, _type.title(), id_region)
            ##    region = region[:][0]
            #     _type = "prefecture"
            #     liste_prefectures = get_all_docs_administrative_levels_by_type_and_parent_id(administrative_levels, _type.title(), region['administrative_id'])[:]
                    
            # if _type == "prefecture":
            #     if not liste_prefectures:
            #         liste_prefectures = get_all_docs_administrative_levels_by_type_and_administrative_id(administrative_levels, _type.title(), id_prefecture)[:]
            #     _type = "commune"
            #     for prefecture in liste_prefectures:
            #         [liste_communes.append(elt) for elt in get_all_docs_administrative_levels_by_type_and_parent_id(administrative_levels, _type.title(), prefecture['administrative_id'])[:]]

            # if _type == "commune":
            #     if not liste_communes:
            #         liste_communes = get_all_docs_administrative_levels_by_type_and_administrative_id(administrative_levels, _type.title(), id_commune)[:]
            #     _type = "canton"
            #     for commune in liste_communes:
            #         [liste_cantons.append(elt) for elt in get_all_docs_administrative_levels_by_type_and_parent_id(administrative_levels, _type.title(), commune['administrative_id'])[:]]

            # if _type == "canton":
            #     if not liste_cantons:
            #         liste_cantons = get_all_docs_administrative_levels_by_type_and_administrative_id(administrative_levels, _type.title(), id_canton)[:]
            #     _type = "village"
            #     for canton in liste_cantons:
            #         [liste_villages.append(elt) for elt in get_all_docs_administrative_levels_by_type_and_parent_id(administrative_levels, _type.title(), canton['administrative_id'])[:]]
            
            # if _type == "village":
            #     if not liste_villages:
            #         liste_villages = get_all_docs_administrative_levels_by_type_and_administrative_id(administrative_levels, _type.title(), id_village)[:]

            liste_villages = get_cascade_villages_by_administrative_level_id(_id)
            
            if type(_id) is not list:
                assign_facilitators = AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(
                    administrative_level_id__in=[int(v['administrative_id']) for v in liste_villages],
                    project_id=1,
                    activated=True
                )
                
                _facilitators = Facilitator.objects.filter(
                    id__in=list(set([int(f.facilitator_id) for f in assign_facilitators])),
                    develop_mode=False, training_mode=False
                )
            else:
                _facilitators = Facilitator.objects.filter(develop_mode=False, training_mode=False)

            for f in _facilitators:
                    already_count_facilitator = False
                    facilitator_db = nsc.get_db(f.no_sql_db_name)
                    
                    query_result = facilitator_db.get_query_result({
                        "type": 'facilitator'
                        })[:]
                    if query_result:
                        doc = query_result[0]
                        for _village in doc['administrative_levels']:
                            
                            if str(_village['id']).isdigit(): #Verify if id contain only digit
                                    
                                for village in liste_villages:
                                    if str(_village['id']) == str(village['administrative_id']):
                                        if not already_count_facilitator:
                                            facilitators.append(f)
                                            already_count_facilitator = True
        else:
            # facilitators = list(Facilitator.objects.all())
            is_training = bool(self.request.GET.get('is_training', "False") == "True")
            is_develop = bool(self.request.GET.get('is_develop', "False") == "True")
            facilitators = (Facilitator.objects.filter(develop_mode=is_develop, training_mode=is_training))
        return facilitators

    def get_queryset(self):

        return self.get_results()
    
    # def get_context_data(self, **kwargs):
    #     context = super().get_context_data(**kwargs)
    #     return context


class FacilitatorListWithLastActivityTableView(LoginRequiredMixin, generic.ListView):
    template_name = 'facilitators/facilitator_list.html'
    context_object_name = 'facilitators'

    def get_results(self):
        id_region = self.request.GET.get('id_region')
        id_prefecture = self.request.GET.get('id_prefecture')
        id_commune = self.request.GET.get('id_commune')
        id_canton = self.request.GET.get('id_canton')
        id_village = self.request.GET.get('id_village')
        type_field = self.request.GET.get('type_field')
        _id = 0
        facilitators = []
        if (id_region or id_prefecture or id_commune or id_canton or id_village) and type_field:
            if id_region and type_field == "region":
                _id = id_region
            elif id_prefecture and type_field == "prefecture":
                _id = id_prefecture
            elif id_commune and type_field == "commune":
                _id = id_commune
            elif id_canton and type_field == "canton":
                _id = id_canton
            elif id_village and type_field == "village":
                _id = id_village
                
            nsc = NoSQLClient()

            liste_villages = []
            
            liste_villages = get_cascade_villages_by_administrative_level_id(_id)
            
            if type(_id) is not list:
                assign_facilitators = AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(
                    administrative_level_id__in=[int(v['administrative_id']) for v in liste_villages],
                    project_id=1,
                    activated=True
                )
                
                _facilitators = Facilitator.objects.filter(
                    id__in=list(set([int(f.facilitator_id) for f in assign_facilitators])),
                    develop_mode=False, training_mode=False
                )
            else:
                _facilitators = Facilitator.objects.filter(develop_mode=False, training_mode=False)

            for f in _facilitators:
                already_count_facilitator = False
                facilitator_db = nsc.get_db(f.no_sql_db_name)
                
                query_result = facilitator_db.get_query_result({
                    "type": 'facilitator'
                    })[:]
                if query_result:
                    doc = query_result[0]
                    for _village in doc['administrative_levels']:
                        
                        if str(_village['id']).isdigit(): #Verify if id contain only digit
                                
                            for village in liste_villages:
                                if str(_village['id']) == str(village['administrative_id']):
                                    if not already_count_facilitator:
                                        facilitators.append(f)
                                        already_count_facilitator = True
        else:
            # facilitators = list(Facilitator.objects.all())
            is_training = bool(self.request.GET.get('is_training', "False") == "True")
            is_develop = bool(self.request.GET.get('is_develop', "False") == "True")
            facilitators = (Facilitator.objects.filter(develop_mode=is_develop, training_mode=is_training))
        
        _facilitators = []
        for f in facilitators:
            f.show_last_activity = True
            _facilitators.append(f)

        return _facilitators

    def get_queryset(self):

        return self.get_results()
    
    # def get_context_data(self, **kwargs):
    #     context = super().get_context_data(**kwargs)
    #     return context



class FacilitatorsPercentListView(FacilitatorMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'facilitators/facilitator_percent_completed.html'
    context_object_name = 'facilitator_percent_completed'
    def get_results(self):
        return self.facilitator_db.get_query_result({"type": "task"})

    def get_queryset(self):
        return []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        total_tasks_completed = 0
        total_tasks_uncompleted = 0
        total_tasks = 0

        object_list = self.get_results()

        if object_list:
            for _ in object_list:
                if _.get("completed"):
                    total_tasks_completed += 1
                else:
                    total_tasks_uncompleted += 1
                total_tasks += 1

        context['percentage_tasks_completed'] = ((total_tasks_completed/total_tasks)*100) if total_tasks else 0

        return context
        
class FacilitatorsPercentView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
    def post(self, request, *args, **kwargs):
        liste = request.POST.getlist('liste[]')
        d = {}

        nsc = NoSQLClient()
        for f in liste:
            facilitator_db = nsc.get_db(f)
            docs = facilitator_db.get_query_result({"type": "task"})

            total_tasks_completed = 0
            total_tasks_uncompleted = 0
            total_tasks = 0
            if docs:
                for _ in docs:
                    if _.get("completed"):
                        total_tasks_completed += 1
                    else:
                        total_tasks_uncompleted += 1
                    total_tasks += 1

            d[f] = ((total_tasks_completed/total_tasks)*100) if total_tasks else 0

        return self.render_to_json_response(d, safe=False)


class FacilitatorDetailView(FacilitatorMixin, PageMixin, LoginRequiredMixin, generic.DetailView):
    template_name = 'facilitators/profile.html'
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
        context['form'] = FilterTaskForm(initial={'facilitator_db_name': self.facilitator_db_name})

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

        # facilitator_docs = self.facilitator_db.all_docs(include_docs=True)['rows']

        # dict_administrative_levels_with_infos = {}
        # tasks = []
        # administrative_levels = []
        # for doc in facilitator_docs:
        #     doc = doc.get('doc')
        #     if doc.get('type') == "facilitator":
        #         administrative_levels = doc.get('administrative_levels')
        #         break

        # total_tasks_completed = 0
        # total_tasks_uncompleted = 0
        # total_tasks = 0
        # for doc in facilitator_docs:
        #     doc = doc.get('doc')
        #     if doc.get('type') == "task":
        #         tasks.append(doc)
        #         if doc.get("completed"):
        #             total_tasks_completed += 1
        #         else:
        #             total_tasks_uncompleted += 1
        #         total_tasks += 1

        #         for administrative_level in administrative_levels:
        #             if str(administrative_level.get("id")) == str(doc.get("administrative_level_id")):
        #                 if dict_administrative_levels_with_infos.get(administrative_level.get("name")):
        #                     if doc.get("completed"):
        #                         dict_administrative_levels_with_infos[administrative_level.get("name")]['total_tasks_completed'] += 1
        #                     else:
        #                         dict_administrative_levels_with_infos[administrative_level.get("name")]['total_tasks_uncompleted'] += 1
        #                     dict_administrative_levels_with_infos[administrative_level.get("name")]['total_tasks'] += 1
        #                 else:
        #                     if doc.get("completed"):
        #                         dict_administrative_levels_with_infos[administrative_level.get("name")] = {
        #                             'total_tasks_completed': 1,
        #                             'total_tasks_uncompleted': 0
        #                         }
        #                     else:
        #                         dict_administrative_levels_with_infos[administrative_level.get("name")] = {
        #                             'total_tasks_completed': 0,
        #                             'total_tasks_uncompleted': 1
        #                         }
        #                     dict_administrative_levels_with_infos[administrative_level.get("name")]['total_tasks'] = 1
        
        # context['total_tasks_completed'] = total_tasks_completed
        # context['total_tasks_uncompleted'] = total_tasks_uncompleted
        # context['total_tasks'] = total_tasks
        # context['percentage_tasks_completed'] = ((total_tasks_completed/total_tasks)*100) if total_tasks else 0

        # for key, value in dict_administrative_levels_with_infos.items():
        #     dict_administrative_levels_with_infos[key]["percentage_tasks_completed"] = ((value["total_tasks_completed"]/value["total_tasks"])*100) if value["total_tasks"] else 0
        #     del dict_administrative_levels_with_infos[key]["total_tasks"]
        # context['dict_administrative_levels_with_infos'] = dict_administrative_levels_with_infos
        
        return context

    def get_object(self, queryset=None):
        return self.doc


class FacilitatorTaskListView(FacilitatorMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'facilitators/task_list.html'
    context_object_name = 'tasks'

    def get_results(self):
        administrative_level_id = self.request.GET.get('administrative_level')
        # phase_id = self.request.GET.get('phase')
        # activity_id = self.request.GET.get('activity')
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
        phases = Phase.objects.all()
        activities = Activity.objects.all()

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
    
    # def get_context_data(self, **kwargs):
    #     context = super().get_context_data(**kwargs)
    #     total_tasks_completed = 0
    #     total_tasks_uncompleted = 0
    #     total_tasks = 0
    #     dict_administrative_levels_with_infos = {}

    #     object_list = self.get_results()
    #     administrative_levels = self.facilitator_db.get_query_result({"type": "facilitator"})[:][0]['administrative_levels']

    #     if object_list:
    #         for _ in object_list:
    #             if _.get("completed"):
    #                 total_tasks_completed += 1
    #             else:
    #                 total_tasks_uncompleted += 1
    #             total_tasks += 1


    #             for administrative_level in administrative_levels:
    #                 if str(administrative_level.get("id")) == str(_.get("administrative_level_id")):
    #                     if dict_administrative_levels_with_infos.get(administrative_level.get("name")):
    #                         if _.get("completed"):
    #                             dict_administrative_levels_with_infos[administrative_level.get("name")]['total_tasks_completed'] += 1
    #                         else:
    #                             dict_administrative_levels_with_infos[administrative_level.get("name")]['total_tasks_uncompleted'] += 1
    #                         dict_administrative_levels_with_infos[administrative_level.get("name")]['total_tasks'] += 1
    #                     else:
    #                         if _.get("completed"):
    #                             dict_administrative_levels_with_infos[administrative_level.get("name")] = {
    #                                 'total_tasks_completed': 1,
    #                                 'total_tasks_uncompleted': 0
    #                             }
    #                         else:
    #                             dict_administrative_levels_with_infos[administrative_level.get("name")] = {
    #                                 'total_tasks_completed': 0,
    #                                 'total_tasks_uncompleted': 1
    #                             }
    #                         dict_administrative_levels_with_infos[administrative_level.get("name")]['total_tasks'] = 1


    #     context['total_tasks_completed'] = total_tasks_completed
    #     context['total_tasks_uncompleted'] = total_tasks_uncompleted
    #     context['total_tasks'] = total_tasks
    #     context['percentage_tasks_completed'] = ((total_tasks_completed/total_tasks)*100) if total_tasks else 0

    #     for key, value in dict_administrative_levels_with_infos.items():
    #         dict_administrative_levels_with_infos[key]["percentage_tasks_completed"] = ((value["total_tasks_completed"]/value["total_tasks"])*100) if value["total_tasks"] else 0
    #         del dict_administrative_levels_with_infos[key]["total_tasks"]
    #     context['dict_administrative_levels_with_infos'] = dict_administrative_levels_with_infos



    #     return context
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


class CreateFacilitatorFormView(PageMixin, LoginRequiredMixin, AdminPermissionRequiredMixin, generic.FormView):
    template_name = 'facilitators/create.html'
    title = gettext_lazy('Create Facilitator')
    active_level1 = 'facilitators'
    form_class = FacilitatorForm
    success_url = reverse_lazy('dashboard:facilitators:list')
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

    def form_valid(self, form):
        data = form.cleaned_data
        password = make_password(data['password1'], salt=None, hasher='default')
        facilitator = Facilitator(username=data['username'], password=password, active=True)
        facilitator.save(replicate_design=False)

        _administrative_levels = []
        for elt in data['administrative_levels']:
            administrativelevel_obj = administrativelevels_models.AdministrativeLevel.objects.using('mis').get(id=int(elt['id']))
            if administrativelevel_obj.cvd and administrativelevel_obj.cvd.headquarters_village and str(administrativelevel_obj.cvd.headquarters_village.id) == elt['id']:
                elt['is_headquarters_village'] = True
            _administrative_levels.append(elt)

        #Assign ADL
        for adl in _administrative_levels:
            _assign = AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(administrative_level_id=int(adl['id']), project_id=1, activated=True).first()
            print(_assign)
            if (adl.get('id') and str(adl.get('id')).isdigit() and not _assign):
                    try:
                        assign = AssignAdministrativeLevelToFacilitator()
                        assign.administrative_level_id = int(adl['id'])
                        assign.facilitator_id = facilitator.id
                        assign.project_id = 1
                        assign.save(using='mis')
                    except Exception as exc:
                        print(exc)
        #End Assign ADL

        doc = {
            "name": data['name'],
            "email": data['email'],
            "phone": data['phone'],
            "sex": data['sex'],
            "administrative_levels": _administrative_levels,
            "type": "facilitator",
            "develop_mode": facilitator.develop_mode,
            "training_mode": facilitator.training_mode,
            "sql_id": int(facilitator.pk)
        }
        nsc = NoSQLClient()
        facilitator_database = nsc.get_db(facilitator.no_sql_db_name)
        nsc.create_document(facilitator_database, doc)

        
        clear_facilitator_docs_by_administrativelevels_and_save_to_backup_db(
            "backup_db_facilitators_docs", facilitator.no_sql_db_name, 
            [d.get('id') for d in _administrative_levels if d.get('is_headquarters_village')]
        ) #Copy backup db docs (for villages added that removed on facilitator before) to facilitator db and clear docs on backup

        sync_geographicalunits_with_cvd_on_facilittor(
            facilitator.develop_mode, facilitator.training_mode, facilitator.no_sql_db_name
        ) #Rebuild Unit and CVD infos on facilitator doc

        sync_tasks(
            facilitator.develop_mode, facilitator.training_mode, facilitator.no_sql_db_name,
            administrativelevel_ids=[d.get('id') for d in _administrative_levels if d.get('is_headquarters_village')]
        ) #Sync the tasks for the new villages


        return super().form_valid(form)




class UpdateFacilitatorView(PageMixin, LoginRequiredMixin, CDDSpecialistPermissionRequiredMixin, generic.UpdateView):
    model = Facilitator
    template_name = 'facilitators/update.html'
    title = gettext_lazy('Edit Facilitator')
    active_level1 = 'facilitators'
    form_class = UpdateFacilitatorForm
    # success_url = reverse_lazy('dashboard:facilitators:list')
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
    
    facilitator_db = None
    facilitator = None
    doc = None
    facilitator_db_name = None

    def dispatch(self, request, *args, **kwargs):
        nsc = NoSQLClient()
        try:
            self.facilitator = self.get_object()
            self.facilitator_db_name = self.facilitator.no_sql_db_name
            self.facilitator_db = nsc.get_db(self.facilitator_db_name)
            query_result = self.facilitator_db.get_query_result({"type": "facilitator"})[:]
            self.doc = self.facilitator_db[query_result[0]['_id']]
        except Exception:
            raise Http404
        return super().dispatch(request, *args, **kwargs)



    def get_context_data(self, **kwargs):
        ctx = super(UpdateFacilitatorView, self).get_context_data(**kwargs)
        form = ctx.get('form')
        ctx.setdefault('facilitator_doc', self.doc)
        if self.doc:
            if form:
                for label, field in form.fields.items():
                    try:
                        form.fields[label].value = self.doc[label]
                    except Exception as exc:
                        pass
                    
                ctx.setdefault('form', form)
            adls = self.doc["administrative_levels"]
            for i in range(len(adls)):
                administrativelevel_obj = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(id=int(adls[i]['id'])).first()
                if administrativelevel_obj and administrativelevel_obj.cvd:
                    adls[i]['cvd_name'] = administrativelevel_obj.cvd.name
            ctx.setdefault('facilitator_administrative_levels', adls)

        return ctx

    def post(self, request, *args, **kwargs):
        
        if not self.facilitator_db_name:
            raise Http404("We don't find the database name for the facilitators.")

        form = UpdateFacilitatorForm(request.POST, instance=self.facilitator)
        if form.is_valid():
            return self.form_valid(form)
        return self.get(request, *args, **kwargs)

    def form_valid(self, form):
        data = form.cleaned_data
        facilitator = form.save(commit=False)
        facilitator = facilitator.save_and_return_object()
        administrative_levels_old = self.doc.get('administrative_levels')
        administrative_levels_remove = []
        _administrative_levels = []
        administrative_levels_new = []
        for elt in data['administrative_levels']:
            administrativelevel_obj = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(id=int(elt['id'])).first()
            if administrativelevel_obj:
                if administrativelevel_obj.cvd and administrativelevel_obj.cvd.headquarters_village and str(administrativelevel_obj.cvd.headquarters_village.id) == elt['id']:
                    elt['is_headquarters_village'] = True

                if not exists_id_in_a_dict(_administrative_levels, elt.get('id')):
                    _administrative_levels.append(elt)
                
                if not exists_id_in_a_dict(administrative_levels_old, elt.get('id')):
                    administrative_levels_new.append(elt)
                
        for ad in administrative_levels_old:
            if ad.get('id') and not exists_id_in_a_dict(_administrative_levels, ad.get('id')):
                administrative_levels_remove.append(ad)
        
        #Assign ADL
        for adl in administrative_levels_new:
            _assign = AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(administrative_level_id=int(adl['id']), project_id=1, activated=True).first()
            if (adl.get('id') and str(adl.get('id')).isdigit() and not _assign):
                    try:
                        assign = AssignAdministrativeLevelToFacilitator()
                        assign.administrative_level_id = int(adl['id'])
                        assign.facilitator_id = facilitator.id
                        assign.project_id = 1
                        assign.save(using='mis')
                    except Exception as exc:
                        print(exc)
        #End Assign ADL

        #Unassign ADL
        for adl in administrative_levels_remove:
            assign = AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(administrative_level_id=int(adl['id']), project_id=1, activated=True).first()
            if adl.get('id') and str(adl.get('id')).isdigit() and assign:
                    try:
                        assign.activated = False
                        assign.save(using='mis')
                    except Exception as exc:
                        print(exc)
        #End Unassign ADL

        doc = {
            "phone": data['phone'],
            "email": data['email'],
            "name": data['name'],
            "sex": data['sex'],
            "administrative_levels": _administrative_levels
        }
        nsc = NoSQLClient()
        nsc.update_doc(self.facilitator_db, self.doc['_id'], doc)
        
        clear_facilitator_docs_by_administrativelevels_and_save_to_backup_db(
            "backup_db_facilitators_docs", self.facilitator_db_name, 
            [d.get('id') for d in administrative_levels_new if d.get('is_headquarters_village')]
        ) #Copy backup db docs (for villages added that removed on facilitator before) to facilitator db and clear docs on backup
        
        clear_facilitator_docs_by_administrativelevels_and_save_to_backup_db(
            self.facilitator_db_name, "backup_db_facilitators_docs",
            [d.get('id') for d in administrative_levels_remove if d.get('is_headquarters_village')]
        ) #Copy facilitator db docs (for villages removed) to backup db and clear docs on backup db
        
        sync_geographicalunits_with_cvd_on_facilittor(
            facilitator.develop_mode, facilitator.training_mode, self.facilitator_db_name
        ) #Rebuild Unit and CVD infos on facilitator doc

        # if not administrative_levels_new:
        #     administrative_levels_new.append({
        #         "is_headquarters_village": True,
        #         "id": "0"
        #     })
        # sync_tasks(
        #     facilitator.develop_mode, facilitator.training_mode, self.facilitator_db_name,
        #     administrativelevel_ids=[d.get('id') for d in administrative_levels_new if d.get('is_headquarters_village')]
        # ) #Sync the tasks for the new villages

        return redirect('dashboard:facilitators:list')