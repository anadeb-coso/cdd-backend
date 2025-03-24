from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy
from django.views import generic
from datetime import datetime, timedelta
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.contrib import messages
from django.shortcuts import render
from django.http import Http404, HttpResponse
from django.db.models import Q
from django.forms.models import model_to_dict
import json
import pytz
from django.shortcuts import redirect
from django.conf import settings
import locale

from authentication.models import Facilitator
from dashboard.facilitators.repository.db_facilitator_repository import FacilitatorRepository
from dashboard.facilitators.repository.facilitator_criteria import FacilitatorCriteria
from no_sql_client import NoSQLClient
from dashboard.mixins import AJAXRequestMixin, PageMixin, JSONResponseMixin, ModalFormMixin
from dashboard.facilitators.forms import FilterFacilitatorFormMultiChoices
from dashboard.administrative_levels.functions import get_cascade_villages_by_administrative_level_id
from assignments.models import AssignAdministrativeLevelToFacilitator
from authentication.functions import get_assign_adl_by_facilitatr
from administrativelevels import models as administrativelevels_models
from cdd.call_objects_from_other_db import mis_objects_call
from cdd.constants import (
    PHASES_COLORS, PHASES_WITH_THEIR_NUMBERS, VALIDATION_PROCESS_COLORS, TYPES_VACATION,
    COMPONENTS, VALIDATION_PROCESS_COLORS_DESCRIPTION
)
from cdd.utils import elements_communs
from dashboard.planning.forms import TaskPlanCommentForm, DownloadAnonymePlanningForm
from subprojects.models import Project as MisProject
from process_manager.models import Project, Phase, Activity as ProcessActivity
from planning.models import Activity, ActivityComment, ActivityValidate, ActivityFile
from cdd.functions import is_datetime_in_past_or_now, times_split, get_dates_between
from dashboard.planning.functions_reports import planning_csv
from cdd.my_librairies.mail.send_mail import send_email
from dashboard.templatetags.custom_tags import get_group_high


class PlanMixin:
    task = None
    facilitator_db = None

    def get_query_result(self, **kwargs):
        # return self.facilitator_db.get_query_result({
        #     "_id": kwargs['task__id']
        # })
        return Activity.objects.get(id=int(kwargs['task__id']))
    
    def dispatch(self, request, *args, **kwargs):
        # nsc = NoSQLClient()
        # self.facilitator_db = nsc.get_db(kwargs['no_sql_db_name'])
        # docs = self.get_query_result(**kwargs)
        # try:
        #     self.task = self.facilitator_db[docs[0][0]['_id']]
        # except Exception:
        #     raise Http404

        # return super().dispatch(request, *args, **kwargs)
        
        try:
            self.task = Activity.objects.get(id=int(kwargs['task__id']))
        except Exception:
            raise Http404

        return super().dispatch(request, *args, **kwargs)


class PlanningListView(PageMixin, LoginRequiredMixin, generic.ListView):
    model = Facilitator
    queryset = [] #Facilitator.objects.filter(active=True)
    template_name = 'planning/facilitator_followup_map/list.html'
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
        context['form'] = FilterFacilitatorFormMultiChoices()
        context['breadcrumb'] = False
        context['PHASES_COLORS'] = PHASES_COLORS
        context['PHASES_WITH_THEIR_NUMBERS'] = PHASES_WITH_THEIR_NUMBERS

        context['is_training'] = bool(self.request.GET.get('training', '0') != '0')
        context['is_develop'] = bool(self.request.GET.get('develop', '0') != '0')
        context['region_id'] = self.request.GET.get('region_id')
         
        context['facilitators'] = Facilitator.objects.filter(
            projects__in=[self.request.session.get('project_id')], 
            develop_mode=context['is_develop'],
            training_mode=context['is_training'],
        )
        context['users'] = User.objects.filter(
            projects__in=[self.request.session.get('project_id')]
        )
        context['facilitators_users'] = sorted([
            {'username': f_u.username, 'name': f_u.name if hasattr(f_u, 'no_sql_user') else f"{f_u.last_name} {f_u.first_name}"} for f_u in (list(context['facilitators']) + list(context['users']))
        ], key=lambda obj: obj["name"] if obj["name"] else '')

        context['access_token'] = settings.MAPBOX_ACCESS_TOKEN
        context['lat'] = settings.DIAGNOSTIC_MAP_LATITUDE
        context['lng'] = settings.DIAGNOSTIC_MAP_LONGITUDE
        context['zoom'] = settings.DIAGNOSTIC_MAP_ZOOM
        context['ws_bound'] = settings.DIAGNOSTIC_MAP_WS_BOUND
        context['en_bound'] = settings.DIAGNOSTIC_MAP_EN_BOUND
        context['country_iso_code'] = settings.DIAGNOSTIC_MAP_ISO_CODE
            
        return context
    




class PlanningListTableView(LoginRequiredMixin, generic.ListView):
    template_name = 'planning/facilitator_followup_map/map.html'
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
    
    def get_color_status_number(self, elt):
        if elt.type == "vacation":
            # return 0 if elt.validated != True  else (5 if is_datetime_in_past_or_now(elt.vacation_return_datetime) else 6)
            return (2 if elt.validated == False else 0) if elt.validated != True  else 6

        if elt.validated == None:
            return 0
        elif elt.validated == True:
            if elt.completed or elt.is_another:
                return 3
            elif elt.undo:
                return 4
            elif is_datetime_in_past_or_now(elt.planned_datetime_end):
                return 5
            else:
                return 1
        else:
            return 2
    
    def get_results(self):
        
        project = Project.objects.get(id=self.request.session.get('project_id'))
        project_mis = mis_objects_call.filter_objects(MisProject, name=self.request.session.get('project_name'))
        project_mis_id = project_mis.first().id if project_mis.count() >= 1 else 1

        id_region = self.request.GET.get('id_region')
        id_prefecture = self.request.GET.get('id_prefecture')
        id_commune = self.request.GET.get('id_commune')
        id_canton = self.request.GET.get('id_canton')
        id_village = self.request.GET.get('id_village')
        type_field = self.request.GET.get('type_field')

        ids_canton = self.request.GET.getlist('id_canton[]')
        ids_village = self.request.GET.getlist('id_village[]')

        date_start_selected = self.request.GET.get('date_start_selected')
        date_end_selected = self.request.GET.get('date_end_selected')
        show_my_calendar = self.request.GET.get('show_my_calendar') in ('true', True)
        task_status = self.request.GET.get('task_status', 'All')
        task_type = self.request.GET.get('task_type', 'All')
        username_facilitator_user = self.request.GET.getlist('username_facilitator_user[]')

        is_training = bool(self.request.GET.get('is_training', "False") == "True")
        is_develop = bool(self.request.GET.get('is_develop', "False") == "True")
        
        date_start, date_end = None, None
        if date_start_selected and date_start_selected not in ('null', 'undefined'):
            date_start = datetime.strptime(date_start_selected, "%Y/%m/%d").date()
        if date_end_selected and date_end_selected not in ('null', 'undefined'):
            date_end = datetime.strptime(date_end_selected, "%Y/%m/%d").date()

        if date_start and date_end:
            pass

        if current_week and current_week != 'null':
            pass
            # current_week = current_week
            # current_monday_date_object = datetime.strptime(current_monday_date, "%Y/%m/%d").date()
        else:
            today = datetime.today()
            current_week = today.isocalendar()[1]
            current_monday_date_object = today - timedelta(days=today.weekday())
        week_dates = [(current_monday_date_object + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

        _id = []
        facilitators = []
        liste_villages_ids = None
        
        if (id_region or id_prefecture or id_commune or ids_canton or ids_village) and type_field != 'clear':
            if id_region:
                _id = id_region
            if id_prefecture:
                _id = id_prefecture
            if id_commune:
                _id = id_commune
            if ids_canton:
                _id = ids_canton
            if ids_village:
                _id = ids_village

            liste_prefectures = []
            liste_communes = []
            liste_cantons = []
            liste_villages = []

            liste_villages = get_cascade_villages_by_administrative_level_id(_id)
            liste_villages_ids = [int(v['administrative_id']) for v in liste_villages]

            if type(_id) is list and _id:
                assign_facilitators = AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(
                    administrative_level_id__in=liste_villages_ids,
                    project_id=project_mis_id,
                    activated=True
                )

                criteria = FacilitatorCriteria(
                    id__in=list(set([int(f.facilitator_id) for f in assign_facilitators])),
                    develop_mode=is_develop,
                    training_mode=is_training,
                    # active=True,
                    projects__id=[self.request.session.get('project_id')]
                )
            else:
                criteria = FacilitatorCriteria(
                    develop_mode=is_develop,
                    training_mode=is_training,
                    # active=True,
                    projects__id=[self.request.session.get('project_id')]
                )
        else:
            is_training = bool(self.request.GET.get('is_training', "False") == "True")
            is_develop = bool(self.request.GET.get('is_develop', "False") == "True")
            criteria = FacilitatorCriteria(
                develop_mode=is_develop,
                training_mode=is_training,
                # active=True,
                projects__id=[self.request.session.get('project_id')]
            )
        facilitators = []
        users = []
        
        if username_facilitator_user:
            facilitators = FacilitatorRepository().find_by_criteria(criteria=criteria)
            users = User.objects.filter(projects__in=[self.request.session.get('project_id')])
            if 'All' not in username_facilitator_user and '' not in username_facilitator_user:
                facilitators = facilitators.filter(username__in=username_facilitator_user)
                users = users.filter(username__in=((username_facilitator_user+[self.request.user.id]) if show_my_calendar else username_facilitator_user))
            
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
        
        """
        # nsc = NoSQLClient()
        # for f in facilitators:
        #     facilitator_database = nsc.get_db(f.no_sql_db_name)
        #     query_result = facilitator_database.get_query_result({
        #         "type": {
        #             "$in": ['task', 'free_task']
        #         },
        #         "planning_dates": {
        #             # "$exists": True
        #             "$in": week_dates
        #         }
        #     })
        #     _f = None
        #     if query_result and query_result[:]:
        #         tasks_planed = []

        #         for task in query_result[:]:
        #             tasks_planed += [
        #                 {
        #                     "planning": p,
        #                     "day": datetime.strptime(p['planned_date'], "%Y-%m-%d").date().weekday(),
        #                     "task": task['name'],
        #                     "color": PHASES_COLORS[PHASES_WITH_THEIR_NUMBERS[task['phase_name']]],
        #                     "datetime": p['planned_datetime_start'],
        #                     "task_order": task.get('task_order'),
        #                     "task__id": task.get('_id'),
        #                     "no_sql_db_name": f.no_sql_db_name
        #                 } for p in task['planning'] if p['planned_date'] in week_dates and (
        #                         (task_status == 'completed' and (p.get('completed') or p.get('is_another'))) or (task_status == 'pending' and (not p.get('completed') and not p.get('is_another'))) or (task_status in  ('All', ''))
        #                 )
        #             ]

        #         _f = {
        #             # 'facilitator': f, 
        #             'person': f.name, 'tasks': tasks_planed}


        #     if _f:
        #         _facilitators[str(current_week)].append(_f)

        # return _facilitators
        """

        planned_date_list = [datetime.strptime(d, '%Y-%m-%d').date() for d in week_dates]
        planned_datetime_list = [parse_datetime(f"{d}T00:00:00.000000Z").replace(tzinfo=pytz.UTC) for d in week_dates]
        planned_datetime_list_query = Q()
        # planned_datetime_list_query |= (Q(planned_datetime_start__lte=planned_datetime_list[0]) & Q(planned_datetime_end__gte=planned_datetime_list[0]))
        # planned_datetime_list_query |= (Q(planned_datetime_start__lte=planned_datetime_list[-1]) & Q(planned_datetime_end__gte=planned_datetime_list[-1]))
        for _date in planned_datetime_list:
            planned_datetime_list_query |= (Q(planned_datetime_start__lte=_date) & Q(planned_datetime_end__gte=_date))

        activities = Activity.objects.filter(Q(planned_date__in=planned_date_list) | Q(Q(type="vacation") & planned_datetime_list_query), project_id=project.id)
        
        if show_my_calendar:
            activities = activities.filter(Q(facilitator_id=self.request.user.id) | Q(user_id=self.request.user.id))
        
        if facilitators:
            activities.filter(facilitator_id__in=[f.id for f in facilitators])
        
        if task_type == "free_tasks":
            activities = activities.filter(type="free_task")
        elif task_type == "existing_tasks":
            activities = activities.filter(type="task")
        elif task_type == "vacations":
            activities = activities.filter(type="vacation")

        if task_status == 'completed':
            activities = activities.filter(Q(completed=True) | Q(is_another=True))
        elif task_status == 'validated':
            activities = activities.filter(validated=True)
        elif task_status == 'not_validated':
            activities = activities.filter(validated=False)
        elif task_status == 'undo':
            activities = activities.filter(undo=True)
        elif task_status == 'pending':
            activities = activities.filter(Q(completed=True) | Q(is_another=True))
        elif task_status == 'deadline_passed':
            activities = activities.filter(planned_datetime_end__lte=timezone.now())
            
        if liste_villages_ids != None:
            query = Q()
            for item in liste_villages_ids:
                query |= Q(administrative_level_ids__contains=[item])
            activities = activities.filter(query)
        
        if not show_my_calendar:
            activities_facilitators = activities.filter(facilitator__in=facilitators)
            for f in facilitators:
                activities_f = activities_facilitators.filter(facilitator_id=f.id)
                if activities_f.exists():
                    _f = None
                    tasks_planed = []

                    for activity in activities_f:

                        # if activity.type == "vacation" and activity.planned_datetime_start and activity.planned_datetime_end:
                        if (
                            activity.planned_datetime_start and activity.planned_datetime_end and 
                            datetime.strftime(activity.planned_datetime_start, "%Y-%m-%dT%H:%M:%S.%fZ").split("T")[0] != datetime.strftime(activity.planned_datetime_end, "%Y-%m-%dT%H:%M:%S.%fZ").split("T")[0]
                            ):
                            elt_dates = get_dates_between(activity.planned_datetime_start, activity.planned_datetime_end, planned_date_list)
                            
                            for current_date_elt in elt_dates:
                                color_index = self.get_color_status_number(activity)
                                tasks_planed.append(
                                    {
                                        "planning": dict([(k,datetime.strftime(v, "%Y-%m-%dT%H:%M:%S.%fZ") if ('date' in k and 'dated' not in k and v and k not in ('is_period_dates',)) else v) for k, v in model_to_dict(activity).items()]),
                                        "day": current_date_elt.weekday(),
                                        "task": f"{activity.name} ({activity.vacation_type})" if activity.type == "vacation" else activity.name,
                                        "color": VALIDATION_PROCESS_COLORS[color_index],
                                        "text_color": "white" if color_index in [5, 6] else "black",
                                        "datetime": datetime.strftime(current_date_elt, "%Y-%m-%dT%H:%M:%S.%fZ"),
                                        "task_order": activity.activity.order if activity.activity else 0,
                                        "task__id": activity.id,
                                        "no_sql_db_name": f.no_sql_db_name,
                                        "is_geolocation": bool(next((g for g in activity.get_geolocations() if g.planning_date == current_date_elt and g.latitude_start), None))
                                    }
                                )
                        else:
                            color_index = self.get_color_status_number(activity)
                            tasks_planed.append(
                                {
                                    "planning": dict([(k,datetime.strftime(v, "%Y-%m-%dT%H:%M:%S.%fZ") if ('date' in k and 'dated' not in k and v and k not in ('is_period_dates',)) else v) for k, v in model_to_dict(activity).items()]),
                                    "day": activity.planned_date.weekday(),
                                    "task": activity.name,
                                    "color": VALIDATION_PROCESS_COLORS[color_index],
                                    "text_color": "white" if color_index in [5, 6] else "black",
                                    "datetime": datetime.strftime(activity.planned_datetime_start, "%Y-%m-%dT%H:%M:%S.%fZ"),
                                    "task_order": activity.activity.order if activity.activity else 0,
                                    "task__id": activity.id,
                                    "no_sql_db_name": f.no_sql_db_name,
                                    "is_geolocation": activity.get_geolocations().filter(latitude_start__isnull=False).exists()
                                }
                            )

                    _f = {
                        'type': "facilitator", 
                        'person': f"{f.sex} {f.name}" if f.sex else f.name, 'tasks': tasks_planed}

                    if _f:
                        _facilitators[str(current_week)].append(_f)


        activities_users = activities.filter(user__in=users)
        # users = User.objects.filter(id__in=list(set([u[0] for u in activities.values_list('user')])))
        for u in users:
            activities_u = activities_users.filter(user_id=u.id)
            if activities_u.exists():
                _u = None
                tasks_planed = []

                for activity in activities_u:
                    # if activity.type == "vacation" and activity.planned_datetime_start and activity.planned_datetime_end:
                    if (
                        activity.planned_datetime_start and activity.planned_datetime_end and 
                        datetime.strftime(activity.planned_datetime_start, "%Y-%m-%dT%H:%M:%S.%fZ").split("T")[0] != datetime.strftime(activity.planned_datetime_end, "%Y-%m-%dT%H:%M:%S.%fZ").split("T")[0]
                        ):
                            
                        elt_dates = get_dates_between(activity.planned_datetime_start, activity.planned_datetime_end, planned_date_list)
                        
                        for current_date_elt in elt_dates:
                            color_index = self.get_color_status_number(activity)
                            tasks_planed.append(
                                {
                                    "planning": dict([(k,datetime.strftime(v, "%Y-%m-%dT%H:%M:%S.%fZ") if ('date' in k and 'dated' not in k and v and k not in ('is_period_dates',)) else v) for k, v in model_to_dict(activity).items()]),
                                    "day": current_date_elt.weekday(),
                                    "task": f"{activity.name} ({activity.vacation_type})" if activity.type == "vacation" else activity.name,
                                    "color": VALIDATION_PROCESS_COLORS[color_index],
                                    "text_color": "white" if color_index in [5, 6] else "black",
                                    "datetime": datetime.strftime(current_date_elt, "%Y-%m-%dT%H:%M:%S.%fZ"),
                                    "task_order": activity.activity.order if activity.activity else 0,
                                    "task__id": activity.id,
                                    "no_sql_db_name": "no_sql_db_name",
                                    "is_geolocation": bool(next((g for g in activity.get_geolocations() if g.planning_date == current_date_elt and g.latitude_start), None))
                                }
                            )
                    else:
                        color_index = self.get_color_status_number(activity)
                        tasks_planed.append(
                            {
                                "planning": dict([(k,datetime.strftime(v, "%Y-%m-%dT%H:%M:%S.%fZ") if ('date' in k and 'dated' not in k and v and k not in ('is_period_dates',)) else v) for k, v in model_to_dict(activity).items()]),
                                "day": activity.planned_date.weekday(),
                                "task": activity.name,
                                "color": VALIDATION_PROCESS_COLORS[color_index],
                                "text_color": "white" if color_index in [5, 6] else "black",
                                "datetime": datetime.strftime(activity.planned_datetime_start, "%Y-%m-%dT%H:%M:%S.%fZ"),
                                "task_order": activity.activity.order if activity.activity else 0,
                                "task__id": activity.id,
                                "no_sql_db_name": "no_sql_db_name",
                                "is_geolocation": activity.get_geolocations().filter(latitude_start__isnull=False).exists()
                            })

                _u = {
                    'type': "user", 
                    'person': f"{u.last_name} {u.first_name}", 'tasks': tasks_planed}

                if _u:
                    _facilitators[str(current_week)].append(_u)

    

        return json.dumps(_facilitators)

    def get_queryset(self):

        return self.get_results()
    