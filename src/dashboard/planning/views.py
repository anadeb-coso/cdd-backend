from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy
from django.views import generic
from datetime import datetime, timedelta
from django.contrib import messages
from django.shortcuts import render
from django.http import Http404

from authentication.models import Facilitator
from no_sql_client import NoSQLClient
from dashboard.mixins import AJAXRequestMixin, PageMixin, JSONResponseMixin, ModalFormMixin
from dashboard.facilitators.forms import FilterFacilitatorForm
from dashboard.administrative_levels.functions import get_cascade_villages_by_administrative_level_id
from assignments.models import AssignAdministrativeLevelToFacilitator
from authentication.functions import get_assign_adl_by_facilitatr
from administrativelevels import models as administrativelevels_models
from cdd.call_objects_from_other_db import mis_objects_call
from cdd.constants import PHASES_COLORS, PHASES_WITH_THEIR_NUMBERS
from cdd.utils import elements_communs
from dashboard.planning.forms import TaskPlanCommentForm



class PlanMixin:
    task = None
    facilitator_db = None

    def get_query_result(self, **kwargs):
        return self.facilitator_db.get_query_result({
            "_id": kwargs['task__id']
        })
    
    def dispatch(self, request, *args, **kwargs):
        nsc = NoSQLClient()
        self.facilitator_db = nsc.get_db(kwargs['no_sql_db_name'])
        docs = self.get_query_result(**kwargs)
        try:
            self.task = self.facilitator_db[docs[0][0]['_id']]
        except Exception:
            raise Http404

        return super().dispatch(request, *args, **kwargs)


class PlanningListView(PageMixin, LoginRequiredMixin, generic.ListView):
    model = Facilitator
    queryset = Facilitator.objects.filter(active=True)
    template_name = 'planning/list.html'
    context_object_name = 'facilitators'
    title = gettext_lazy('Planning')
    active_level1 = 'planning'
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
        context['PHASES_COLORS'] = PHASES_COLORS
        context['PHASES_WITH_THEIR_NUMBERS'] = PHASES_WITH_THEIR_NUMBERS

        context['is_training'] = bool(self.request.GET.get('training', '0') != '0')
        context['is_develop'] = bool(self.request.GET.get('develop', '0') != '0')
        context['region_id'] = self.request.GET.get('region_id')

            
        return context
    




class PlanningListTableView(LoginRequiredMixin, generic.ListView):
    template_name = 'planning/calendar.html'
    context_object_name = 'planning'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        current_week = self.request.GET.get('current_week')
        current_monday_date = self.request.GET.get('current_monday_date')

        if current_week and current_week != 'null':
            context['currentWeek'] = current_week
            context['currentMondayDate'] = datetime.strptime(current_monday_date, "%Y/%m/%d").date()
        else:
            today = datetime.today()
            context['currentWeek'] = today.isocalendar()[1]
            context['currentMondayDate'] = today - timedelta(days=today.weekday())
        
        return context

    def get_results(self):
        
        id_region = self.request.GET.get('id_region')
        id_prefecture = self.request.GET.get('id_prefecture')
        id_commune = self.request.GET.get('id_commune')
        id_canton = self.request.GET.get('id_canton')
        id_village = self.request.GET.get('id_village')
        type_field = self.request.GET.get('type_field')

        current_week = self.request.GET.get('current_week')
        current_monday_date = self.request.GET.get('current_monday_date')
        show_my_calendar = self.request.GET.get('show_my_calendar')
        task_status = self.request.GET.get('task_status', 'All')
        id_facilitator = self.request.GET.get('id_facilitator', 'All')
        
        if (id_village in (None, 'null', '', 'All') and current_week in (None, 'null', '', 'All') and \
            task_status in (None, 'null', '', 'All') and id_facilitator in (None, 'null', '', 'All')):
            id_canton = id_canton if id_canton != '' else '1973'
            type_field = type_field if type_field != 'all' else 'canton'
        
        
        if current_week and current_week != 'null':
            current_week = current_week
            current_monday_date_object = datetime.strptime(current_monday_date, "%Y/%m/%d").date()
        else:
            today = datetime.today()
            current_week = today.isocalendar()[1]
            current_monday_date_object = today - timedelta(days=today.weekday())
        week_dates = [(current_monday_date_object + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

        _id = 0
        facilitators = []

        if (id_region or id_prefecture or id_commune or id_canton or id_village) and type_field != 'clear':
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

            liste_prefectures = []
            liste_communes = []
            liste_cantons = []
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
                    develop_mode=False, training_mode=False, active=True
                )
            else:
                _facilitators = Facilitator.objects.filter(develop_mode=False, training_mode=False, active=True)

            facilitators = _facilitators
        else:
            is_training = bool(self.request.GET.get('is_training', "False") == "True")
            is_develop = bool(self.request.GET.get('is_develop', "False") == "True")
            facilitators = (Facilitator.objects.filter(develop_mode=is_develop, training_mode=is_training, active=True))

        if id_facilitator not in  ('All', ''):
            facilitators = facilitators.filter(id=int(id_facilitator))

        _facilitators =  {
            str(current_week): [
                # {
                #     "person": "DJOLOGUE Kanfiguin",
                #     "tasks": [
                #         { "day": 0, "task": "Tâche 1", "color": "#b2dfdb", "datetime": "2024-08-13T08:00" },
                #         { "day": 0, "task": "Tâche 11", "color": "#b2dfdb", "datetime": "2024-08-13T17:00" },
                #         { "day": 4, "task": "Tâche 2", "color": "#ffccbc", "datetime": "2024-08-13T12:00" }
                #     ]
                # }
            ]
        }
        
        nsc = NoSQLClient()
        for f in facilitators:
            facilitator_database = nsc.get_db(f.no_sql_db_name)
            query_result = facilitator_database.get_query_result({
                "type": {
                    "$in": ['task', 'free_task']
                },
                "planning_dates": {
                    # "$exists": True
                    "$in": week_dates
                }
            })
            _f = None
            if query_result and query_result[:]:
                tasks_planed = []
                
                for task in query_result[:]:
                    tasks_planed += [
                        {
                            "planning": p,
                            "day": datetime.strptime(p['planned_date'], "%Y-%m-%d").date().weekday(),
                            "task": task['name'],
                            "color": PHASES_COLORS[PHASES_WITH_THEIR_NUMBERS[task['phase_name']]],
                            "datetime": p['planned_datetime_start'],
                            "task_order": task.get('task_order'),
                            "task__id": task.get('_id'),
                            "no_sql_db_name": f.no_sql_db_name
                        } for p in task['planning'] if p['planned_date'] in week_dates and (
                            (task_status == 'completed' and (p.get('completed') or p.get('is_another'))) or (task_status == 'pending' and (not p.get('completed') and not p.get('is_another'))) or (task_status in  ('All', ''))
                        )
                    ]

                _f = {
                    # 'facilitator': f, 
                    'person': f.name, 'tasks': tasks_planed}

            
            if _f:
                _facilitators[str(current_week)].append(_f)

        return _facilitators

    def get_queryset(self):

        return self.get_results()
    



class TaskPlanDetailView(AJAXRequestMixin, ModalFormMixin, LoginRequiredMixin, JSONResponseMixin, generic.TemplateView):
    template_name = "planning/task_detail_modal.html"
    id_form = "task_plan_comment"
    title = gettext_lazy('Detail')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        no_sql_db_name = kwargs['no_sql_db_name']
        task_plan_datetime = kwargs['task_plan_datetime']
        task__id = kwargs['task__id']
        nsc = NoSQLClient()
        
        facilitator_database = nsc.get_db(no_sql_db_name)
        try:
            task = facilitator_database.get_query_result({
                "_id": task__id,
            })[:][0]
        except Exception:
            raise Http404

        context['task'] = task
        context['task_plan'] = None

        task_planning = [p for p in task['planning'] if p['planned_datetime_start'] == task_plan_datetime]
        
        if task_planning:
            context['task_plan'] = task_planning[0]
            context['task_plan']['planned_datetime_start'] = datetime.strptime(context['task_plan']['planned_datetime_start'], "%Y-%m-%dT%H:%M:%S.%fZ")
            context['task_plan']['planned_datetime_end'] = datetime.strptime(context['task_plan']['planned_datetime_end'], "%Y-%m-%dT%H:%M:%S.%fZ")
            context['task_plan']['created_date'] = datetime.strptime(context['task_plan']['created_date'], "%Y-%m-%dT%H:%M:%S.%fZ")
            context['task_plan']['updated_date'] = datetime.strptime(context['task_plan']['updated_date'], "%Y-%m-%dT%H:%M:%S.%fZ") if 'updated_date' in context['task_plan'] else context['task_plan']['created_date']
            context['task_plan']['comments'] = context['task_plan']['comments'] if 'comments' in context['task_plan'] else list()

            context['colors'] = ['warning', 'mediumslateblue', 'gray', 'mediumpurple', 'plum', 'primary', 'danger']
            users = {c['user_id'] for c in context['task_plan']['comments']} | {self.request.user.id}
            indexed_users = {}
            for index, user_id in enumerate(users):
                indexed_users[user_id] = index
            context['indexed_users'] = indexed_users

        context['no_sql_db_name'] = no_sql_db_name
        context['task_plan_datetime'] = task_plan_datetime
        context['task__id'] = task__id
        return context
    


class SaveCommentView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
    def post(self, request, *args, **kwargs):
        no_sql_db_name = self.request.POST.get('no_sql_db_name')
        task_plan_datetime = self.request.POST.get('task_plan_datetime')
        task__id = self.request.POST.get('task__id')
        comment = self.request.POST.get('comment').strip()
        nsc = NoSQLClient()
        
        facilitator_database = nsc.get_db(no_sql_db_name)
        try:
            docs = facilitator_database.get_query_result({
                "_id": task__id,
            })
            task = facilitator_database[docs[0][0]['_id']]
        except Exception:
            raise Http404

        save = False
        for i in range(len(task['planning'])):
            p = task['planning'][i]
            if p['planned_datetime_start'] == task_plan_datetime:
                due_at = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
                comments = p['comments'] if 'comments' in p else list()
                comments.insert(0, {
                    "user_name": f"{request.user.first_name} {request.user.last_name}",
                    "user_id": request.user.id,
                    "comment": comment,
                    "created_date": due_at,
                    "type": "comment",
                    "comments_read": False
                })

                task['planning'][i]['comments'] = comments
                task['planning'][i]['comments_read'] = False
                task.save()
                save = True
                break
            
        
        msg = gettext_lazy("The comment was successfully saved." if save else "The comment was not successfully saved.")
        messages.add_message(self.request, messages.SUCCESS if save else messages.WARNING, msg, extra_tags='success' if save else 'warning')
        context = {
            'msg': render(self.request, 'common/messages.html').content.decode("utf-8"),
            'comments': comments
        }
        return self.render_to_json_response(context, safe=False)
    

class TaskPlanCommentListView(PlanMixin, AJAXRequestMixin, LoginRequiredMixin, generic.TemplateView):
    
    template_name = 'planning/comments.html'
    context_object_name = 'comments'


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        task_plan_datetime = kwargs['task_plan_datetime']
        context['colors'] = ['warning', 'mediumslateblue', 'gray', 'mediumpurple', 'plum', 'primary', 'danger']

        
        task_planning = [p for p in self.task['planning'] if p['planned_datetime_start'] == task_plan_datetime]
        if task_planning:
            context['task_plan'] = task_planning[0]

            comments = context['task_plan']['comments'] if 'comments' in context['task_plan'] else list()

            users = {c['user_id'] for c in comments} | {self.request.user.id}

            indexed_users = {}
            for index, user_id in enumerate(users):
                indexed_users[user_id] = index
            context['indexed_users'] = indexed_users

            context['comments'] = comments

        return context