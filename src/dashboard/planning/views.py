from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User, Group
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
from cdd.my_librairies import download_file
from django.forms.models import model_to_dict
import json
import pytz
from django.shortcuts import redirect
import locale
import itertools

from authentication.models import Facilitator
from dashboard.facilitators.repository.db_facilitator_repository import FacilitatorRepository
from dashboard.facilitators.repository.facilitator_criteria import FacilitatorCriteria
from no_sql_client import NoSQLClient
import grm_client
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
from planning.models import Activity, ActivityComment, ActivityValidate, ActivityFile, ValidationGroupsProcess
from cdd.functions import is_datetime_in_past_or_now, times_split, get_dates_between
from dashboard.planning.functions_reports import planning_csv
from cdd.my_librairies.mail.send_mail import send_email
from dashboard.templatetags.custom_tags import get_group_high
from authentication.functions import get_group_high as auth_get_group_high
from authentication import PROFESSIONAL_GROUPS, FACILITATORS_TYPES_WITH_GROUP_NAME
from planning.vars import WORK_ENVIRONMENT


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
        context['form'] = FilterFacilitatorFormMultiChoices()
        context['breadcrumb'] = False
        context['PHASES_COLORS'] = PHASES_COLORS
        context['PHASES_WITH_THEIR_NUMBERS'] = PHASES_WITH_THEIR_NUMBERS
        context['WORK_ENVIRONMENT_LIST'] = [{'name': 'All', 'label': gettext_lazy('All')} if self.request.user.groups.filter(name="SecuritySpecialist").exists() else {'name': 'All', 'label': gettext_lazy('All'), 'attr': 'selected'}] + [
            {'name': k, 'label': v, 'attr': 'selected'} if k == 'Field' and self.request.user.groups.filter(name="SecuritySpecialist").exists() else {'name': k, 'label': v} for k, v in WORK_ENVIRONMENT
        ]

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
        
        context['user_groups'] = sorted([
            {'name': g.name, 'label': auth_get_group_high(g)} for g in Group.objects.all() if auth_get_group_high(g) != gettext_lazy("User").__str__()
        ], key=lambda item: item['label'])

        context['user_groups'].append({'name': 'Others', 'label': gettext_lazy("Others").__str__()})
        
        validators_g_process = ValidationGroupsProcess.objects.filter(
            validators_groups__in=set(self.request.user.groups.values_list('id', flat=True)),
            project__in=self.request.session.get('tree_structure_projects_ids')
        )

        planners_groups = [p_g.name for v_g_p in validators_g_process for p_g in v_g_p.planners_groups.all()]

        for user_group in context['user_groups']:
            if user_group['name'] in planners_groups:
                user_group['attr'] = 'selected'

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
        tree_projects = project.build_the_tree_structure()
        tree_projects_names = [p.name for p in tree_projects]
        tree_projects_ids = [p.id for p in tree_projects]

        project_mis = mis_objects_call.filter_objects(MisProject, name=self.request.session.get('project_name'))
        tree_projects_mis = mis_objects_call.filter_objects(MisProject, name__in=tree_projects_names)

        project_mis_id = project_mis.first().id if project_mis.count() >= 1 else 1
        tree_projects_mis_ids = [p.id for p in tree_projects_mis]

        type_field = self.request.GET.get('type_field')

        ids_canton = list(filter(None, self.request.GET.getlist('id_canton[]')))
        ids_village = list(filter(None, self.request.GET.getlist('id_village[]')))

        current_week = self.request.GET.get('current_week')
        current_monday_date = self.request.GET.get('current_monday_date')
        show_my_calendar = self.request.GET.get('show_my_calendar') in ('true', True)
        my_area = self.request.GET.get('my_area') in ('true', True)
        task_status = self.request.GET.get('task_status', 'All')
        task_type = self.request.GET.get('task_type', 'All')
        username_facilitator_user = list(filter(None, self.request.GET.getlist('username_facilitator_user[]')))
        work_environment = list(filter(None, self.request.GET.getlist('work_environment[]')))

        user_groups = list(filter(None, self.request.GET.getlist('user_groups[]')))

        is_training = bool(self.request.GET.get('is_training', "False") == "True")
        is_develop = bool(self.request.GET.get('is_develop', "False") == "True")

        
        #AREA
        liste_my_area_villages_ids = []
        if my_area:
            try:
                facilitator_grm = grm_client.get_facilitator_by_email(self.request.user.email)
                grm_client.attach_administrative_regions_objects(facilitator_grm)
                liste_my_area_villages_ids = facilitator_grm['administrative_regions']
                administrative_regions_objects = facilitator_grm.get('administrative_regions_objects')
                liste_my_area_villages_ids = list(set(
                    (liste_my_area_villages_ids if liste_my_area_villages_ids else []) + list(itertools.chain(*[[str(v['id']) for v in ad['villages']] for ad in (administrative_regions_objects if administrative_regions_objects else [])]))
                ))
            except:
                pass
            liste_my_area_villages_ids = [int(ad) for ad in liste_my_area_villages_ids if str(ad).isdigit()]
            
        #END AREA
        
        def get_facilitators_emails(villages_ids):
            facilitators_stabilized = grm_client.get_facilitator_by_village([int(v) for v in villages_ids])
            
            return list(set([
                elt['representative']['email'] for elt in facilitators_stabilized if elt and elt.get('representative', {}).get('email')
            ]))
        
        if current_week and current_week != 'null':
            current_week = current_week
            current_monday_date_object = datetime.strptime(current_monday_date, "%Y/%m/%d").date()
        else:
            today = datetime.today()
            current_week = today.isocalendar()[1]
            current_monday_date_object = today - timedelta(days=today.weekday())
        week_dates = [(current_monday_date_object + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

        _id = []
        facilitators = []
        liste_villages_ids = None
        criteria = {
            'develop_mode': is_develop,
            'training_mode': is_training,
            'projects__id': tree_projects_ids
        }

        if (ids_canton or ids_village) and type_field != 'clear':
            if ids_canton:
                _id = ids_canton
            if ids_village:
                _id = ids_village
                
            liste_villages = []

            liste_villages = get_cascade_villages_by_administrative_level_id(_id)
            liste_villages_ids = [int(v['administrative_id']) for v in liste_villages]
            
            liste_villages_ids = list(set(liste_villages_ids) & set(liste_my_area_villages_ids)) if liste_my_area_villages_ids else liste_villages_ids
            
            criteria['email__in'] = get_facilitators_emails(liste_villages_ids)

        if liste_my_area_villages_ids and 'email__in' not in criteria:
            criteria['email__in'] = get_facilitators_emails(liste_my_area_villages_ids)
        

        facilitators = []
        users = []
        criteria_users = {'projects__in': tree_projects_ids}

        if show_my_calendar:
            users = User.objects.filter(username__in=(username_facilitator_user+[self.request.user.username]))
        elif (username_facilitator_user or user_groups):

            if username_facilitator_user and 'All' not in username_facilitator_user and '' not in username_facilitator_user:
                criteria['username__in'] = username_facilitator_user
                criteria_users['username__in'] = ((username_facilitator_user+[self.request.user.username]) if show_my_calendar else username_facilitator_user)
            if user_groups and 'All' not in user_groups and '' not in user_groups:
                groups = user_groups.copy()
                if 'Others' in user_groups:
                    groups = Group.objects.exclude(name__in=PROFESSIONAL_GROUPS).values_list('name', flat=True)
                criteria_users['groups__name__in'] = groups
                
                roles = [FACILITATORS_TYPES_WITH_GROUP_NAME.get(r) for r in user_groups if r in FACILITATORS_TYPES_WITH_GROUP_NAME]
                if roles:
                    criteria['facilitator_type__in'] = roles
                else:
                    criteria['facilitator_type__in'] = groups

            facilitators = FacilitatorRepository().find_by_criteria(criteria=FacilitatorCriteria(**criteria)).distinct()
            users = User.objects.filter(**criteria_users).distinct()

        _facilitators =  {
            str(current_week): []
        }

        planned_date_list = [datetime.strptime(d, '%Y-%m-%d').date() for d in week_dates]
        planned_datetime_list = [parse_datetime(f"{d}T00:00:00.000000Z").replace(tzinfo=pytz.UTC) for d in week_dates]
        planned_datetime_list_query = Q()
        
        for _date in planned_datetime_list:
            planned_datetime_list_query |= (Q(planned_datetime_start__lte=_date) & Q(planned_datetime_end__gte=_date))

        # activities = Activity.objects.filter(Q(planned_date__in=planned_date_list) | Q(Q(type="vacation") & planned_datetime_list_query), project_id__in=tree_projects_ids)#, project_id=project.id)
        query = Q(
            Q(planned_date__in=planned_date_list) | planned_datetime_list_query,
            project_id__in=tree_projects_ids
        )

        if show_my_calendar:
            # activities = activities.filter(Q(facilitator_id=self.request.user.id) | Q(user_id=self.request.user.id))
            query &= Q(Q(facilitator_id=self.request.user.id) | Q(user_id=self.request.user.id))
        
        # if task_type == "free_tasks":
        #     activities = activities.filter(type="free_task")
        # elif task_type == "existing_tasks":
        #     activities = activities.filter(type="task")
        # elif task_type == "vacations":
        #     activities = activities.filter(type="vacation")
        type_map = {"free_tasks": "free_task", "existing_tasks": "task", "vacations": "vacation"}
        if task_type in type_map:
            query &= Q(type=type_map[task_type])

        # if task_status == 'completed':
        #     activities = activities.filter(Q(completed=True) | Q(is_another=True))
        # elif task_status == 'validated':
        #     activities = activities.filter(validated=True)
        # elif task_status == 'not_validated':
        #     activities = activities.filter(validated=False)
        # elif task_status == 'pending':
        #     activities = activities.filter(validated=None)
        # elif task_status == 'pending_to_review':
        #     activities = activities.filter(edit_after_invalidation=True)
        # elif task_status == 'undo':
        #     activities = activities.filter(undo=True)
        # elif task_status == 'pending_to_do':
        #     activities = activities.filter(Q(completed=None) & Q(is_another=None) & Q(validated=True))
        # elif task_status == 'deadline_passed':
        #     activities = activities.filter(Q(completed=None) & Q(is_another=None) & Q(planned_datetime_end__lte=timezone.now())).exclude(undo=True)
        status_filters = {
            'completed': Q(Q(completed=True) | Q(is_another=True)),
            'validated': Q(validated=True),
            'not_validated': Q(validated=False),
            'pending': Q(validated=None),
            'pending_to_review': Q(edit_after_invalidation=True),
            'undo': Q(undo=True),
            'pending_to_do': Q(completed=None, is_another=None, validated=True),
            'deadline_passed': Q(Q(completed=None, is_another=None, planned_datetime_end__lte=timezone.now()) & ~Q(undo=True)),
        }
        if task_status in status_filters:
            query &= status_filters[task_status]
            
        if not self.request.user.groups.filter(name="Supervisor").exists() and liste_villages_ids != None and not my_area:
            _query = Q()
            for item in liste_villages_ids:
                _query |= Q(administrative_level_ids__contains=[item])
            # activities = activities.filter(_query)
            query &= _query
        
        if work_environment and 'All' not in work_environment and '' not in work_environment:
            query &= Q(work_environment__in=work_environment)
        
        activities = Activity.objects.filter(query)

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
    



class TaskPlanDetailView(AJAXRequestMixin, ModalFormMixin, LoginRequiredMixin, JSONResponseMixin, generic.TemplateView):
    template_name = "planning/task_detail_modal.html"
    id_form = "plan_task_detail"
    title = gettext_lazy('Detail')

    def get_color_status_number(self, elt):
        if elt.type == "vacation":
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
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        no_sql_db_name = kwargs['no_sql_db_name']
        task_plan_datetime = kwargs['task_plan_datetime']
        # task__id = kwargs['task__id']
        # nsc = NoSQLClient()
        
        # facilitator_database = nsc.get_db(no_sql_db_name)
        # try:
        #     task = facilitator_database.get_query_result({
        #         "_id": task__id,
        #     })[:][0]
        # except Exception:
        #     raise Http404

        # context['task'] = task
        # context['task_plan'] = None

        # task_planning = [p for p in task['planning'] if p['planned_datetime_start'] == task_plan_datetime]
        
        # if task_planning:
        #     context['task_plan'] = task_planning[0]
        #     context['task_plan']['planned_datetime_start'] = datetime.strptime(context['task_plan']['planned_datetime_start'], "%Y-%m-%dT%H:%M:%S.%fZ")
        #     context['task_plan']['planned_datetime_end'] = datetime.strptime(context['task_plan']['planned_datetime_end'], "%Y-%m-%dT%H:%M:%S.%fZ")
        #     context['task_plan']['created_date'] = datetime.strptime(context['task_plan']['created_date'], "%Y-%m-%dT%H:%M:%S.%fZ")
        #     context['task_plan']['updated_date'] = datetime.strptime(context['task_plan']['updated_date'], "%Y-%m-%dT%H:%M:%S.%fZ") if 'updated_date' in context['task_plan'] else context['task_plan']['created_date']
        #     context['task_plan']['comments'] = context['task_plan']['comments'] if 'comments' in context['task_plan'] else list()

        #     context['colors'] = ['warning', 'mediumslateblue', 'gray', 'mediumpurple', 'plum', 'primary', 'danger']
        #     users = {c['user_id'] for c in context['task_plan']['comments']} | {self.request.user.id}
        #     indexed_users = {}
        #     for index, user_id in enumerate(users):
        #         indexed_users[user_id] = index
        #     context['indexed_users'] = indexed_users

        # context['no_sql_db_name'] = no_sql_db_name
        # context['task_plan_datetime'] = task_plan_datetime
        # context['task__id'] = task__id

        # task_plan_datetime = kwargs['task_plan_datetime']
        task__id = kwargs['task__id']
        
        try:
            activity = Activity.objects.get(id=int(task__id))
        except Exception:
            raise Http404
        
        task_plan_date_object = datetime.strptime(task_plan_datetime, "%Y-%m-%dT%H:%M:%S.%fZ").date()
        geolocation = next((g for g in activity.get_geolocations() if g.planning_date == task_plan_date_object and g.latitude_start), None)
        context['geolocation'] = geolocation


        context['task'] = model_to_dict(activity)
        context['task']['project_name'] = activity.project.name
        context['task']['phase_name'] = activity.phase.name if activity.phase else None
        context['task']['activity_name'] = activity.name
        context['task']['user'] = model_to_dict(activity.user) if activity.user else None
        context['task']['facilitator'] = model_to_dict(activity.facilitator) if activity.facilitator else None

        
        context['task_plan'] = model_to_dict(activity)
        context['task_plan']['planned_datetime_start'] = activity.planned_datetime_start
        context['task_plan']['planned_datetime_end'] = activity.planned_datetime_end
        context['task_plan']['created_date'] = activity.created_date
        context['task_plan']['updated_date'] = activity.updated_date
        context['task_plan']['comments'] = activity.get_activities_and_comments()
        context['task_plan']['files'] = activity.get_files()
        context['task']['files'] = context['task_plan']['files']

        context['colors'] = ['warning', 'mediumslateblue', 'gray', 'mediumpurple', 'plum', 'primary', 'danger']
        users = {c.user.id if c.user else (c.facilitator.id if c.facilitator else 0) for c in context['task_plan']['comments']} | {self.request.user.id}
        indexed_users = {}
        for index, user_id in enumerate(users):
            indexed_users[user_id] = index
        context['indexed_users'] = indexed_users

        context['no_sql_db_name'] = no_sql_db_name
        context['task_plan_datetime'] = task_plan_datetime
        context['task__id'] = task__id
        
        context['administrativelevls'] = mis_objects_call.filter_objects(administrativelevels_models.AdministrativeLevel, type="Village")
        context['phases'] = Phase.objects.filter(project_id=self.request.session.get('project_id'))
        context['activities'] = ProcessActivity.objects.filter(project_id=self.request.session.get('project_id'))
        context['activity_status_color'] = VALIDATION_PROCESS_COLORS[self.get_color_status_number(activity)]
        context['activity_status_color_description'] = VALIDATION_PROCESS_COLORS_DESCRIPTION[
            context['activity_status_color']
        ]
        context['COMPONENTS'] = COMPONENTS
        context['WORK_ENVIRONMENT'] = WORK_ENVIRONMENT
        context['WORK_ENVIRONMENT_DICT'] = dict(WORK_ENVIRONMENT)

        return context


class SaveCommentView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
    def post(self, request, *args, **kwargs):
        # no_sql_db_name = self.request.POST.get('no_sql_db_name')
        # task_plan_datetime = self.request.POST.get('task_plan_datetime')
        # task__id = self.request.POST.get('task__id')
        # comment = self.request.POST.get('comment').strip()
        # nsc = NoSQLClient()
        
        # facilitator_database = nsc.get_db(no_sql_db_name)
        # try:
        #     docs = facilitator_database.get_query_result({
        #         "_id": task__id,
        #     })
        #     task = facilitator_database[docs[0][0]['_id']]
        # except Exception:
        #     raise Http404

        # save = False
        # for i in range(len(task['planning'])):
        #     p = task['planning'][i]
        #     if p['planned_datetime_start'] == task_plan_datetime:
        #         due_at = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        #         comments = p['comments'] if 'comments' in p else list()
        #         comments.insert(0, {
        #             "user_name": f"{request.user.first_name} {request.user.last_name}",
        #             "user_id": request.user.id,
        #             "comment": comment,
        #             "created_date": due_at,
        #             "type": "comment",
        #             "comments_read": False
        #         })

        #         task['planning'][i]['comments'] = comments
        #         task['planning'][i]['comments_read'] = False
        #         task.save()
        #         save = True
        #         break


        activity_id = self.request.POST.get('task__id')
        _comment = self.request.POST.get('comment').strip()
        save = False
        
        try:
            activity = Activity.objects.get(id=int(activity_id))

            comment = ActivityComment()
            comment.activity = activity
            comment.comment = _comment
            comment.type = "comment"
            comment.user = self.request.user
            comment.save(user=self.request.user)

            save = True
        except Exception:
            raise Http404
            
        
        msg = gettext_lazy("The comment was successfully saved." if save else "The comment was not successfully saved.")
        messages.add_message(self.request, messages.SUCCESS if save else messages.WARNING, msg, extra_tags='success' if save else 'warning')
        context = {
            'msg': render(self.request, 'common/messages.html').content.decode("utf-8"),
            'comments': [model_to_dict(c) for c in activity.get_activities_and_comments()]
        }
        return self.render_to_json_response(context, safe=False)
    

class TaskPlanCommentListView(PlanMixin, AJAXRequestMixin, LoginRequiredMixin, generic.TemplateView):
    
    template_name = 'planning/comments.html'
    context_object_name = 'comments'


    def get_context_data(self, **kwargs):
        # context = super().get_context_data(**kwargs)
        # task_plan_datetime = kwargs['task_plan_datetime']
        # context['colors'] = ['warning', 'mediumslateblue', 'gray', 'mediumpurple', 'plum', 'primary', 'danger']

        # task_planning = [p for p in self.task['planning'] if p['planned_datetime_start'] == task_plan_datetime]
        # if task_planning:
        #     context['task_plan'] = task_planning[0]

        #     comments = context['task_plan']['comments'] if 'comments' in context['task_plan'] else list()

        #     users = {c['user_id'] for c in comments} | {self.request.user.id}

        #     indexed_users = {}
        #     for index, user_id in enumerate(users):
        #         indexed_users[user_id] = index
        #     context['indexed_users'] = indexed_users

        #     context['comments'] = comments

        # return context
        context = super().get_context_data(**kwargs)
        task_plan_datetime = kwargs['task_plan_datetime']
        context['colors'] = ['warning', 'mediumslateblue', 'gray', 'mediumpurple', 'plum', 'primary', 'danger']

        # date_obj = datetime.strptime(task_plan_datetime, '%Y-%m-%dT%H:%M:%SZ')
        comments = list(self.task.get_activities_and_comments())

        users = {c.user.id if c.user else (c.facilitator.id if c.facilitator else 0) for c in comments} | {self.request.user.id}

        indexed_users = {}
        for index, user_id in enumerate(users):
            indexed_users[user_id] = index
        context['indexed_users'] = indexed_users

        context['comments'] = comments

        return context
    


class SaveValidationView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
    def post(self, request, *args, **kwargs):
        activity_id = self.request.POST.get('task__id')
        validated = self.request.POST.get('validated_decision') == "validate_activity"
        comment = self.request.POST.get('comment').strip()
        save = False
        try:
            activity = Activity.objects.get(id=int(activity_id))

            activity_validate = ActivityValidate()
            activity_validate.activity = activity
            activity_validate.comment = comment
            activity_validate.validated = validated
            activity_validate.user = self.request.user
            activity_validate = activity_validate.save_and_return_object(user=self.request.user)

            activity.validated = validated
            if activity.edit_after_invalidation:
                activity.edit_after_invalidation = False
            activity = activity.save_and_return_object(user=self.request.user)

            save = True

            if validated == False:
                try:
                    locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
                    activity_plan_date = (
                        f'{activity.planned_datetime_start.strftime("%A")} {gettext_lazy("the")} {activity.planned_datetime_start.strftime("%d %B %Y")}' if activity.type != 'vacation' else \
                        f'{activity.planned_datetime_start.strftime("%A")} {gettext_lazy("the")} {activity.planned_datetime_start.strftime("%d %B %Y")} {gettext_lazy("to")} {activity.planned_datetime_end.strftime("%A")} {gettext_lazy("the")} {activity.planned_datetime_end.strftime("%d %B %Y")}'
                    )
                    msg = send_email(
                        f'[COSO Apps : {datetime.now().strftime("%Y-%m-%d")}] {gettext_lazy("Activity Invalided")} : {activity.name} ({activity_plan_date})',
                        "mail/send/comment",
                        {
                            "datas": {
                                gettext_lazy("Subject "): gettext_lazy("Activity Invalided"), 
                                gettext_lazy("Activity"): activity.name,
                                gettext_lazy("Description"): activity.description,
                                gettext_lazy("Planned on"): activity_plan_date,
                                gettext_lazy("Comment"): comment,
                                gettext_lazy("Evaluator"): f"{activity_validate.user.last_name} {activity_validate.user.first_name}" if activity_validate.user else (activity_validate.facilitator.name if activity_validate.facilitator else None),
                                gettext_lazy("Date of decision"): f'{activity_validate.updated_date.strftime("%A")} {gettext_lazy("the")} {activity_validate.updated_date.strftime("%d %B %Y")}',
                                gettext_lazy("Location"): ", ".join([v["name"] for v in activity.administrative_levels]) if activity.administrative_levels else "",
                                gettext_lazy("Comment"): comment,
                                gettext_lazy("Work Environment"): dict(WORK_ENVIRONMENT).get(activity.work_environment) if activity.work_environment else "",
                            },
                            "user": {
                                gettext_lazy("Planner"): f"{activity.user.last_name} {activity.user.first_name}" if activity.user else (activity.facilitator.name if activity.facilitator else None),
                                gettext_lazy("Planner Email"): activity.user.email if activity.user else (activity.facilitator.email if activity.facilitator else None),
                                
                                gettext_lazy("Validator"): f"{request.user.last_name} {request.user.first_name}",
                                gettext_lazy("Validator Type"): get_group_high(request.user),
                                gettext_lazy("Validator Email"): request.user.email,
                            },
                            "url": f"{request.scheme}://{request.META['HTTP_HOST']}{reverse_lazy('dashboard:planning:list')}"
                        },
                        [e for e in list([
                            activity.user.email if activity.user else (activity.facilitator.email if activity.facilitator else None)
                        ] + [(v.user.email if v.user else (v.facilitator.email if v.facilitator else None)) for v in activity.get_activities_validate()]) if e],
                        [],
                        project_name=self.request.session.get('project_name', 'COSO')
                    )
                    mail_message = gettext_lazy("Mail sent successfully")
                except:
                    mail_message = gettext_lazy("An error occurred while sending the email")
        except Exception:
            raise Http404
            
        
        msg = gettext_lazy("The comment was successfully saved." if save else "The comment was not successfully saved.")
        messages.add_message(self.request, messages.SUCCESS if save else messages.WARNING, msg, extra_tags='success' if save else 'warning')
        context = {
            'msg': render(self.request, 'common/messages.html').content.decode("utf-8"),
            'comments': [model_to_dict(c) for c in activity.get_activities_and_comments()]
        }
        return self.render_to_json_response(context, safe=False)
    


class SaveFileView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
    def post(self, request, *args, **kwargs):
        activity_id = self.request.POST.get('task__id')
        fileUrl = str(self.request.POST.get('fileUrl'))
        save = False
        files = []
        try:
            activity = Activity.objects.get(id=int(activity_id))
            files = activity.get_files()
            files_length = files.count()
            file = ActivityFile()
            file.activity = activity
            file.name = fileUrl.split("?")[0].split("/")[-1].split(".")[0]
            file.url = fileUrl
            file.order = files_length
            file.principal = files_length == 0
            file.date_taken  = datetime.now().date()
            file.username = self.request.user.username
            file.user_email = self.request.user.email
            file.save(user=self.request.user)

            save = True
        except Exception:
            raise Http404
            
        
        msg = gettext_lazy("The file was successfully saved." if save else "The file was not successfully saved.")
        messages.add_message(self.request, messages.SUCCESS if save else messages.WARNING, msg, extra_tags='success' if save else 'warning')
        context = {
            'msg': render(self.request, 'common/messages.html').content.decode("utf-8"),
            'files': [model_to_dict(elt) for elt in files]
        }
        return self.render_to_json_response(context, safe=False)
    
class DeleteFileView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
    def post(self, request, *args, **kwargs):
        file_id = self.request.POST.get('file__id')
        activity_id = self.request.POST.get('task__id')
        save = False
        files = []
        try:
            activity = Activity.objects.get(id=int(activity_id))
            files = activity.get_files()
            ActivityFile.objects.get(id=int(file_id)).delete()

            save = True
        except Exception:
            raise Http404
            
        
        msg = gettext_lazy("The file was successfully deleted." if save else "The file was not successfully deleted.")
        messages.add_message(self.request, messages.SUCCESS if save else messages.WARNING, msg, extra_tags='success' if save else 'warning')
        context = {
            'msg': render(self.request, 'common/messages.html').content.decode("utf-8"),
            'files': [model_to_dict(elt) for elt in files]
        }
        return self.render_to_json_response(context, safe=False)
    
class TaskPlanFilesListView(PlanMixin, AJAXRequestMixin, LoginRequiredMixin, generic.TemplateView):
    
    template_name = 'planning/files.html'
    context_object_name = 'files'


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context['files'] = self.task.get_files()

        return context
    

class AddTaskPlanView(AJAXRequestMixin, ModalFormMixin, LoginRequiredMixin, JSONResponseMixin, generic.TemplateView):
    template_name = "planning/add_task_modal.html"
    id_form = "add_plan_task"
    title = gettext_lazy('Add Activity')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        activity_id = self.request.GET.get('task__id')
        context['administrativelevls_ids'] = json.dumps([])
        context['cantons'] = mis_objects_call.filter_objects(administrativelevels_models.AdministrativeLevel, type="Canton")
        if activity_id not in (None, 'None', 'null', ''):
            context['task'] = Activity.objects.get(id=int(activity_id))
            administrativelevls_ids = context['task'].administrative_level_ids if context['task'].administrative_level_ids else []
            context['administrativelevls_ids'] = json.dumps(administrativelevls_ids)
            
            # context['administrativelevls'] = mis_objects_call.filter_objects(administrativelevels_models.AdministrativeLevel, type="Village", id__in=administrativelevls_ids)
            # context['task_cantons_ids'] = [adl.parent.id for adl in context['administrativelevls'] if adl.parent]
            context['task_cantons_ids'] = [adl.id for adl in mis_objects_call.filter_objects(administrativelevels_models.AdministrativeLevel, type="Canton", administrativelevel__in=administrativelevls_ids)]
            context['is_another_vacation_type'] = context['task'].vacation_type not in list(TYPES_VACATION.keys()) if context['task'] and context['task'].type == "vacation" and context['task'].vacation_type else None

            
        # context['administrativelevls'] = mis_objects_call.filter_objects(administrativelevels_models.AdministrativeLevel, type="Village")
        context['phases'] = Phase.objects.filter(project_id=self.request.session.get('project_id'))
        context['activities'] = ProcessActivity.objects.filter(project_id=self.request.session.get('project_id'))
        # context['activities_dict'] = json.dumps([model_to_dict(o) for o in context['activities']])
        activities_data = []
        for activity in context['activities']:
            d = model_to_dict(activity)
            d['cycles'] = list(activity.cycles.values("id", "name", "description", "project", "couch_id", "order", "capacity_attachments"))  # dict avec id + name
            activities_data.append(d)

        context['activities_dict'] = json.dumps(activities_data)

        TIMES_H = times_split()
        context['times_split'] = [{ 'name': TIMES_H[i], 'id': i } for i in range(len(TIMES_H))]
        context['TYPES_VACATION'] = TYPES_VACATION
        context['COMPONENTS'] = COMPONENTS
        context['WORK_ENVIRONMENT'] = WORK_ENVIRONMENT
        

        return context
    

class SaveActivityView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
    def post(self, request, *args, **kwargs):
        activity_id = self.request.POST.get('task__id')
        phase_id = self.request.POST.get('phase_id')
        process_activity_id = self.request.POST.get('process_activity_id')
        completed = self.request.POST.get('completed') in ('true', True)
        undo = self.request.POST.get('undo') in ('true', True)
        is_another = self.request.POST.get('is_another') in ('true', True)
        is_period_dates = self.request.POST.get('is_period_dates') in ('true', True)
        is_free_task = self.request.POST.get('is_free_task') in ('true', True)
        comment = self.request.POST.get('comment')
        total_men_present_over_35 = self.request.POST.get('total_men_present_over_35')
        total_women_present_over_35 = self.request.POST.get('total_women_present_over_35')
        total_people_present_over_35 = self.request.POST.get('total_people_present_over_35')
        total_men_present_under_35 = self.request.POST.get('total_men_present_under_35')
        total_women_present_under_35 = self.request.POST.get('total_women_present_under_35')
        total_people_present_under_35 = self.request.POST.get('total_people_present_under_35')
        total_people_present = self.request.POST.get('total_people_present')
        undo_comment = self.request.POST.get('undo_comment')
        free_task_title = self.request.POST.get('free_task_title')
        administrative_level_ids = self.request.POST.getlist('administrative_level_ids[]')
        type_action = self.request.POST.get('type_action')
        description_activity = self.request.POST.get('description_activity')
        plan_date = self.request.POST.get('plan_date')
        start_time = self.request.POST.get('start_time')
        end_time = self.request.POST.get('end_time')
        component = self.request.POST.get('component')
        activity_date_start = self.request.POST.get('activity_date_start')
        activity_date_end = self.request.POST.get('activity_date_end')
        
        is_vacation = self.request.POST.get('is_vacation') in ('true', True)
        vacation_type = self.request.POST.get('vacation_type')
        work_environment = self.request.POST.get('work_environment')
        work_environment_is_another_activity = self.request.POST.get('work_environment_is_another_activity')
        absence_date_start = self.request.POST.get('absence_date_start')
        absence_date_end = self.request.POST.get('absence_date_end')
        return_date = self.request.POST.get('return_date')
        vacation_type_precision = self.request.POST.get('vacation_type_precision')

        comment = comment.strip() if comment else None
        undo_comment = undo_comment.strip() if undo_comment else None

        TIMES_H = times_split()
        
        phase = Phase.objects.filter(id=int(phase_id)).first() if phase_id not in (None, '', 'null') else None
        process_activity = ProcessActivity.objects.filter(id=int(process_activity_id)).first() if process_activity_id not in (None, '', 'null') else None
        administrative_level_ids = [int(elt) for elt in administrative_level_ids] if administrative_level_ids else []
        administrative_levels = [{
            "id": elt.id,
            "name": elt.name,
            "parent": elt.parent.id if elt.parent else None
        } for elt in mis_objects_call.filter_objects(administrativelevels_models.AdministrativeLevel, id__in=administrative_level_ids)]
        
        files = []
        # try:
        if activity_id not in (None, 'None', 'null', '') and type_action == "report":
            # Report
            activity = Activity.objects.get(id=int(activity_id))
            activity.completed = completed
            activity.undo = undo
            activity.is_another = is_another
            activity.is_free_task = is_free_task

            if is_another:
                activity.another_detail = {
                    "phase": model_to_dict(phase) if phase else None,
                    "activity": model_to_dict(process_activity) if process_activity else None,
                    "name": free_task_title if is_free_task else (process_activity.name if process_activity else None),
                    "activty_sql_id": process_activity.id if process_activity else None,
                    "component": component,
                    "work_environment": work_environment_is_another_activity if work_environment_is_another_activity else None,

                    "administrative_level_ids": administrative_level_ids,
                    "administrative_levels": administrative_levels,
                }

            activity.comment = comment
            activity.total_men_present_over_35 = total_men_present_over_35
            activity.total_women_present_over_35 = total_women_present_over_35
            activity.total_people_present_over_35 = total_people_present_over_35
            activity.total_men_present_under_35 = total_men_present_under_35
            activity.total_women_present_under_35 = total_women_present_under_35
            activity.total_people_present_under_35 = total_people_present_under_35
            activity.total_people_present = total_people_present
            activity.undo_comment = undo_comment
        else:
            if activity_id not in (None, 'None', 'null', '') and type_action == "edit":
                activity = Activity.objects.get(id=int(activity_id))
                if activity.validated == False:
                    activity.edit_after_invalidation = True
                    activity = activity.save_and_return_object(user=self.request.user)
                    
                    try:
                        locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
                        activity_plan_date = (
                            f'{activity.planned_datetime_start.strftime("%A")} {gettext_lazy("the")} {activity.planned_datetime_start.strftime("%d %B %Y")}' if activity.type != 'vacation' else \
                            f'{activity.planned_datetime_start.strftime("%A")} {gettext_lazy("the")} {activity.planned_datetime_start.strftime("%d %B %Y")} {gettext_lazy("to")} {activity.planned_datetime_end.strftime("%A")} {gettext_lazy("the")} {activity.planned_datetime_end.strftime("%d %B %Y")}'
                        )
                        msg = send_email(
                            f'[COSO Apps : {datetime.now().strftime("%Y-%m-%d")}] {gettext_lazy("Activity Invalided")} : {activity.name} ({activity_plan_date})',
                            "mail/send/comment",
                            {
                                "datas": {
                                    gettext_lazy("Subject "): gettext_lazy("Invalidated activity modified by planner"), 
                                    gettext_lazy("Activity"): activity.name,
                                    gettext_lazy("Description"): activity.description,
                                    gettext_lazy("Planned on"): activity_plan_date,
                                    gettext_lazy("Updated on"): f'{activity.updated_date.strftime("%A")} {gettext_lazy("the")} {activity.updated_date.strftime("%d %B %Y")}',
                                    gettext_lazy("Location"): ", ".join([v["name"] for v in activity.administrative_levels]) if activity.administrative_levels else "",
                                    gettext_lazy("Work Environment"): dict(WORK_ENVIRONMENT).get(activity.work_environment) if activity.work_environment else "",
                                },
                                "user": {
                                    gettext_lazy("Planner"): f"{activity.user.last_name} {activity.user.first_name}" if activity.user else (activity.facilitator.name if activity.facilitator else None),
                                    gettext_lazy("Email"): activity.user.email if activity.user else (activity.facilitator.email if activity.facilitator else None),
                            
                                    gettext_lazy("Validator"): f"{request.user.last_name} {request.user.first_name}",
                                    gettext_lazy("Validator Type"): get_group_high(request.user),
                                    gettext_lazy("Validator Email"): request.user.email,
                                },
                                "url": f"{request.scheme}://{request.META['HTTP_HOST']}{reverse_lazy('dashboard:planning:list')}"
                            },
                            [e for e in list([
                                activity.user.email if activity.user else (activity.facilitator.email if activity.facilitator else None)
                            ] + [(v.user.email if v.user else (v.facilitator.email if v.facilitator else None)) for v in activity.get_activities_validate()]) if e],
                            [],
                            project_name=self.request.session.get('project_name', 'COSO')
                        )
                        mail_message = gettext_lazy("Mail sent successfully")
                    except:
                        mail_message = gettext_lazy("An error occurred while sending the email")


            else:
                activity = Activity()

            activity.is_period_dates = is_period_dates
            
            if is_vacation:
                activity.type = "vacation"
                activity.name = "Congé"
                activity.description = vacation_type_precision if vacation_type_precision else vacation_type
                activity.vacation_type = vacation_type_precision if vacation_type_precision else vacation_type
                activity.planned_datetime_start = parse_datetime(f"{absence_date_start}T00:00:00.000000Z").replace(tzinfo=pytz.UTC)
                activity.planned_datetime_end = parse_datetime(f"{absence_date_end}T23:45:00.000000Z").replace(tzinfo=pytz.UTC)
                activity.vacation_return_datetime = parse_datetime(f"{return_date}T00:00:00.000000Z").replace(tzinfo=pytz.UTC)
                activity.planned_date = None
            else:
                if start_time:
                    start_time = TIMES_H[int(start_time)]
                if end_time:
                    end_time = TIMES_H[int(end_time)]
                # New
                activity.type = "free_task" if is_free_task else "task"
                activity.phase_id = phase.id if not is_free_task and phase else None
                activity.activity_id = process_activity.id if not is_free_task and process_activity else None
                activity.name = process_activity.name if not is_free_task and process_activity else free_task_title
                activity.description = process_activity.description if not is_free_task and process_activity else description_activity
                activity.component = component
                activity.administrative_level_ids = administrative_level_ids
                activity.administrative_levels = administrative_levels
                activity.work_environment = work_environment if work_environment else None
                activity.planned_date = datetime.strptime(plan_date if plan_date else activity_date_start, '%Y-%m-%d').date()
                activity.planned_datetime_start = parse_datetime(f"{activity_date_start}T{start_time if start_time else '00:00'}:00.000000Z").replace(tzinfo=pytz.UTC) if (is_period_dates and activity_date_start) else datetime.strptime(f"{plan_date} {start_time}", '%Y-%m-%d %H:%M')
                activity.planned_datetime_end = parse_datetime(f"{activity_date_end}T{end_time if end_time else '23:45'}:00.000000Z").replace(tzinfo=pytz.UTC) if (is_period_dates and activity_date_end) else datetime.strptime(f"{plan_date} {end_time}", '%Y-%m-%d %H:%M')
            activity.user = self.request.user
            activity.project_id = self.request.session.get('project_id')

        activity.save()
        # except Exception as exc:
        #     print(exc)
        #     raise Http404
        
        
        msg = gettext_lazy("The activity was successfully saved.")
        messages.add_message(self.request, messages.SUCCESS, msg, extra_tags='success')
        context = {
            'msg': render(self.request, 'common/messages.html').content.decode("utf-8"),
            'activities': [True]
        }
        return self.render_to_json_response(context, safe=False)
    


class PlanningDownloadAnonymeView(PageMixin, generic.TemplateView):
    template_name = 'planning/download_anonyme.html'
    context_object_name = 'facilitators'
    title = gettext_lazy('Planning')
    active_level1 = 'planning'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = DownloadAnonymePlanningForm()
        context['username_facilitator_user'] = self.request.GET.get('username')

        today = datetime.today()
        context['currentMondayDate'] = today - timedelta(days=today.weekday())

        return context
    



class PlanningCSVView(PageMixin, LoginRequiredMixin, generic.TemplateView):
    """Class to download statistic under excel file"""

    template_name = 'planning/list.html'
    context_object_name = 'Download'
    title = gettext_lazy("Download")
    active_level1 = 'planning'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def get(self, request, *args, **kwargs):

        file_path = ""
        try:
            file_path = planning_csv(self.request)

        except Exception as exc:
            messages.info(request, gettext_lazy("An error has occurred..."))

        if not file_path:
            return redirect('dashboard:facilitators:list')
        else:
            # Une seule requête HTTP : le fichier vient d'être écrit par ce process, on le
            # renvoie directement au lieu de faire suivre son chemin pour un second
            # aller-retour (download_file_view), qui échoue si l'ALB route cette seconde
            # requête vers une autre instance ne l'ayant pas sur son disque local.
            return download_file.download(
                request,
                file_path,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        

class PlanningAnonymousCSVView(PageMixin, generic.TemplateView):
    """Class to download statistic under excel file"""

    template_name = 'planning/list.html'
    context_object_name = 'Download'
    title = gettext_lazy("Download")
    active_level1 = 'planning'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def get(self, request, *args, **kwargs):

        file_path = ""
        try:
            file_path = planning_csv(self.request)

        except Exception as exc:
            messages.info(request, gettext_lazy("An error has occurred..."))

        if not file_path:
            return redirect('dashboard:facilitators:list')
        else:
            # Une seule requête HTTP : le fichier vient d'être écrit par ce process, on le
            # renvoie directement au lieu de faire suivre son chemin pour un second
            # aller-retour (download_file_view), qui échoue si l'ALB route cette seconde
            # requête vers une autre instance ne l'ayant pas sur son disque local.
            return download_file.download(
                request,
                file_path,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )