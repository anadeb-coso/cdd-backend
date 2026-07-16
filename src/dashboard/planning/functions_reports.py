from datetime import datetime, timedelta
from django.utils.translation import gettext_lazy
from django.utils.dateparse import parse_datetime
from django.contrib.auth.models import User, Group
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db.models import Q
import pytz
import os
import pandas as pd
from sys import platform
import itertools

from dashboard.administrative_levels.functions import get_cascade_villages_by_administrative_level_id
from subprojects.models import Project as MisProject
from process_manager.models import Project
from cdd.call_objects_from_other_db import mis_objects_call
from assignments.models import AssignAdministrativeLevelToFacilitator
from dashboard.facilitators.repository.db_facilitator_repository import FacilitatorRepository
from dashboard.facilitators.repository.facilitator_criteria import FacilitatorCriteria
from planning.models import Activity, ValidationGroupsProcess
from cdd.functions import get_dates_between
from authentication.functions import get_group_high as auth_get_group_high
from authentication import PROFESSIONAL_GROUPS, FACILITATORS_TYPES_WITH_GROUP_NAME
from no_sql_client import NoSQLClient
from planning.vars import WORK_ENVIRONMENT



def planning_csv(request):
    nsc = NoSQLClient()
    eadls = nsc.get_db('eadls')

    project = Project.objects.get(id=request.session.get('project_id')) if request.user.is_authenticated else None
    tree_projects = project.build_the_tree_structure() if project else []
    tree_projects_ids = [p.id for p in tree_projects]

    ids_canton = list(filter(None, request.GET.getlist('id_canton[]')))
    ids_village = list(filter(None, request.GET.getlist('id_village[]')))
    type_field = request.GET.get('type_field')

    current_monday_date = request.GET.get('current_monday_date')
    date_start_selected = request.GET.get('date_start_selected')
    date_end_selected = request.GET.get('date_end_selected')
    show_my_calendar = request.GET.get('show_my_calendar') in ('true', True)
    my_area = request.GET.get('my_area') in ('true', True)
    task_status = request.GET.get('task_status', 'All')
    task_type = request.GET.get('task_type', 'All')
    username_facilitator_user = list(filter(None, request.GET.getlist('username_facilitator_user[]')))
    work_environment = list(filter(None, request.GET.getlist('work_environment[]')))

    user_groups = list(filter(None, request.GET.getlist('user_groups[]')))

    is_training = bool(request.GET.get('is_training', "False") == "True")
    is_develop = bool(request.GET.get('is_develop', "False") == "True")

    sheet_datas_dict_planning = {
        "Nom": {},
        "Composante": {},
        "Activité": {},
        "Description": {},
        "Date & Heure début": {},
        "Date & Heure fin": {},
    }
    previous_datas = {
        "Nom": {},
        "Composante": {},
        "Activité": {},
        "Description": {},
        "Environnement de travail": {},
        "Statut": {},
        "Rapport": {},

        _("Total men present over 35"): {},
        _("Total women present over 35"): {},
        _("Total people present over 35"): {},
        _("Total men present under 35"): {},
        _("Total women present under 35"): {},
        _("Total people present under 35"): {},
        _("Total men present"): {},
        _("Total women present"): {},
        _("Total people present"): {},

        "Date & Heure début": {},
        "Date & Heure fin": {},
        "Commentaires": {},
        "Villages": {},
        "Autre activité faite": {},
        "Composante (Autre activité)": {},
        "Villages (Autre activité)": {},
        "Environnement de travail (Autre activité)": {},
    }
    plan_datas = {
        "Nom": {},
        "Composante": {},
        "Activité": {},
        "Description": {},
        "Environnement de travail": {},
        "Date & Heure début": {},
        "Date & Heure fin": {},
        "Villages": {},
    }
    datas_dict_planning = {
        "Précédentes": previous_datas,
        "Planification": plan_datas
    }

    #AREA
    liste_my_area_villages_ids = []
    if my_area:
        try:
            facilitator_grm = eadls.get_query_result({
                "type": "adl",
                "representative.email": request.user.email
            })[:][0]
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
        facilitators_stabilized = eadls.get_view_result(
            "_design/adl_village_filter", "by_village_id", 
            keys=[int(v) for v in villages_ids], 
            include_docs=True
        )
        if facilitators_stabilized:
            f_s_emails = []
            for row in facilitators_stabilized[:]:
                elt = row['doc']
                if elt and elt.get('representative') and elt.get('representative').get('email') not in f_s_emails:
                    f_s_emails.append(elt.get('representative').get('email'))
        
        return f_s_emails
    


    if date_start_selected and date_start_selected != 'null':
        try:
            date_start_selected_object = datetime.strptime(date_start_selected, "%Y/%m/%d").date()
        except ValueError:
            date_start_selected_object = datetime.strptime(date_start_selected, "%d/%m/%Y").date()
    else:
        today = datetime.today()
        date_start_selected_object = today - timedelta(days=today.weekday())

    days_between = 7
    if date_end_selected and date_end_selected != 'null':
        try:
            date_end_selected_object = datetime.strptime(date_end_selected, "%Y/%m/%d").date()
        except ValueError:
            date_end_selected_object = datetime.strptime(date_end_selected, "%d/%m/%Y").date()
        days_between = (date_end_selected_object - date_start_selected_object).days
    
    week_dates = [(date_start_selected_object + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(-days_between, days_between)]

    _id = []
    facilitators = []
    liste_villages_ids = None
    criteria = {
        'develop_mode': is_develop,
        'training_mode': is_training
    }
    if tree_projects_ids:
        criteria['projects__id'] = tree_projects_ids

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
    criteria_users = {'projects__in': tree_projects_ids} if tree_projects_ids else {}

    if show_my_calendar:
        users = User.objects.filter(username__in=(username_facilitator_user+[request.user.username]))
    elif (username_facilitator_user or user_groups):

        if username_facilitator_user and 'All' not in username_facilitator_user and '' not in username_facilitator_user:
            criteria['username__in'] = username_facilitator_user
            criteria_users['username__in'] = ((username_facilitator_user+[request.user.username]) if show_my_calendar else username_facilitator_user)
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
        

    planned_date_list = [datetime.strptime(d, '%Y-%m-%d').date() for d in week_dates]
    planned_datetime_list = [parse_datetime(f"{d}T00:00:00.000000Z").replace(tzinfo=pytz.UTC) for d in week_dates]
    
    planned_datetime_list_query = Q()
    for _date in planned_datetime_list:
        planned_datetime_list_query |= (Q(planned_datetime_start__lte=_date) & Q(planned_datetime_end__gte=_date))

    # activities = Activity.objects.filter(Q(planned_date__in=planned_date_list) | Q(Q(type="vacation") & planned_datetime_list_query), project_id=project.id)
    
    # activities = Activity.objects.filter(Q(planned_date__in=planned_date_list) | planned_datetime_list_query, project_id__in=tree_projects_ids)
    if tree_projects_ids:
        query = Q(
            Q(planned_date__in=planned_date_list) | planned_datetime_list_query,
            project_id__in=tree_projects_ids
        )
    else:
        query = Q(
            Q(planned_date__in=planned_date_list) | planned_datetime_list_query
        )
    
    if show_my_calendar:
        # activities = activities.filter(Q(facilitator_id=request.user.id) | Q(user_id=request.user.id))
        query &= Q(Q(facilitator_id=request.user.id) | Q(user_id=request.user.id))
    
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
        
    if request.user.is_authenticated and not request.user.groups.filter(name="Supervisor").exists() and liste_villages_ids != None and not my_area:
        _query = Q()
        for item in liste_villages_ids:
            _query |= Q(administrative_level_ids__contains=[item])
        # activities = activities.filter(_query)
        query &= _query
    
    if work_environment and 'All' not in work_environment and '' not in work_environment:
        query &= Q(work_environment__in=work_environment)

    user_facilitator_query = Q()
    user_facilitator_query |= Q(user__in=users)
    if not show_my_calendar:
        user_facilitator_query  |= Q(facilitator__in=facilitators)
    # activities = activities.filter(user_facilitator_query)
    query &= user_facilitator_query
    
    activities = Activity.objects.filter(query).order_by('user__last_name', 'user__first_name', 'facilitator__name', 'planned_datetime_start', 'planned_datetime_end') #'component', 
    
    
    activities_previous = activities.filter(Q(planned_datetime_start__lte=date_start_selected_object))
    activities_previous = list(activities_previous)
    
    for i in range(len(activities_previous)):
        activity = activities_previous[i]
        datas_dict_planning['Précédentes']['Nom'][i] = f"{activity.user.last_name} {activity.user.first_name}" if activity.user else activity.facilitator.name
        datas_dict_planning['Précédentes']['Composante'][i] = activity.component
        datas_dict_planning['Précédentes']['Activité'][i] = f"{activity.name} ({activity.vacation_type})" if activity.vacation_type else activity.name
        datas_dict_planning['Précédentes']['Description'][i] = activity.description
        datas_dict_planning['Précédentes']['Environnement de travail'][i] = dict(WORK_ENVIRONMENT).get(activity.work_environment) if activity.work_environment else None
        datas_dict_planning['Précédentes']['Date & Heure début'][i] = activity.planned_datetime_start.strftime('%Y-%m-%d %H:%M:%S')
        datas_dict_planning['Précédentes']['Date & Heure fin'][i] = activity.planned_datetime_end.strftime('%Y-%m-%d %H:%M:%S')

        if activity.completed:
            datas_dict_planning['Précédentes']['Statut'][i] = gettext_lazy("Done")
        elif not activity.completed and activity.is_another and activity.another_detail:
            datas_dict_planning['Précédentes']['Statut'][i] = gettext_lazy("Superseded")
        elif activity.undo:
            datas_dict_planning['Précédentes']['Statut'][i] = gettext_lazy("Not Done")
        else:
            datas_dict_planning['Précédentes']['Statut'][i] = gettext_lazy("Pending")

        # datas_dict_planning['Précédentes']['Statut'][i] = gettext_lazy("Yes") if activity.completed else gettext_lazy("No")

        if not activity.completed and activity.is_another and activity.another_detail:
            datas_dict_planning['Précédentes']['Autre activité faite'][i] = activity.another_detail.get('name')
            datas_dict_planning['Précédentes']['Composante (Autre activité)'][i] = activity.another_detail.get('component')
            datas_dict_planning['Précédentes']['Villages (Autre activité)'][i] = " ; ".join([v.get('name') for v in activity.another_detail.get('administrative_levels')]) if activity.another_detail.get('administrative_levels') else ""
            datas_dict_planning['Précédentes']['Environnement de travail (Autre activité)'][i] = dict(WORK_ENVIRONMENT).get(activity.another_detail.get('work_environment')) if activity.another_detail.get('work_environment') else None

        if activity.undo and activity.undo_comment:
            datas_dict_planning['Précédentes']['Commentaires'][i] = activity.undo_comment
        
        
        datas_dict_planning['Précédentes']['Rapport'][i] = activity.comment

        datas_dict_planning['Précédentes'][_("Total men present over 35")][i] = activity.total_men_present_over_35
        datas_dict_planning['Précédentes'][_("Total women present over 35")][i] = activity.total_women_present_over_35
        datas_dict_planning['Précédentes'][_("Total people present over 35")][i] = activity.total_people_present_over_35
        datas_dict_planning['Précédentes'][_("Total men present under 35")][i] = activity.total_men_present_under_35
        datas_dict_planning['Précédentes'][_("Total women present under 35")][i] = activity.total_women_present_under_35
        datas_dict_planning['Précédentes'][_("Total people present under 35")][i] = activity.total_people_present_under_35
        
        datas_dict_planning['Précédentes'][_("Total men present")][i] = (activity.total_men_present_over_35 if activity.total_men_present_over_35 else 0) + (activity.total_men_present_under_35 if activity.total_men_present_under_35 else 0)
        datas_dict_planning['Précédentes'][_("Total women present")][i] = (activity.total_women_present_over_35 if activity.total_women_present_over_35 else 0) + (activity.total_women_present_under_35 if activity.total_women_present_under_35 else 0)

        datas_dict_planning['Précédentes'][_("Total people present")][i] = activity.total_people_present

        datas_dict_planning['Précédentes']['Villages'][i] = " ; ".join([v.get('name') for v in activity.administrative_levels]) if activity.administrative_levels else ""
        
        # if datas_dict_planning.get(datas_dict_planning['Précédentes']['Nom'][i]):
        #     pass
        # else:
        #     datas_dict_planning[datas_dict_planning['Précédentes']['Nom'][i]] = {
        #         "Composante": {0: datas_dict_planning['Précédentes']['Composante'][i]},
        #         "Activité": {0: datas_dict_planning['Précédentes']['Activité'][i]},
        #         "Description": {0: datas_dict_planning['Précédentes']['Description'][i]},
        #         "Statut": {0: datas_dict_planning['Précédentes']['Statut'][i]},
        #         "Rapport": {0: datas_dict_planning['Précédentes']['Rapport'][i]},
        #         "Date & Heure début": {0: datas_dict_planning['Précédentes']['Date & Heure début'][i]},
        #         "Date & Heure fin": {0: datas_dict_planning['Précédentes']['Date & Heure fin'][i]},
        #         "Commentaires": {0: datas_dict_planning['Précédentes']['Commentaires'][i]},
        #         "Villages": {0: datas_dict_planning['Précédentes']['Villages'][i]},
        #     }


    activities_planification = activities.filter(Q(planned_datetime_end__gte=date_start_selected_object))
    activities_planification = list(activities_planification)
    
    for i in range(len(activities_planification)):
        activity = activities_planification[i]
        datas_dict_planning['Planification']['Nom'][i] = f"{activity.user.last_name} {activity.user.first_name}" if activity.user else activity.facilitator.name
        datas_dict_planning['Planification']['Composante'][i] = activity.component
        datas_dict_planning['Planification']['Activité'][i] = f"{activity.name} ({activity.vacation_type})" if activity.vacation_type else activity.name
        datas_dict_planning['Planification']['Description'][i] = activity.description
        datas_dict_planning['Planification']['Environnement de travail'][i] = dict(WORK_ENVIRONMENT).get(activity.work_environment) if activity.work_environment else None
        datas_dict_planning['Planification']['Date & Heure début'][i] = activity.planned_datetime_start.strftime('%Y-%m-%d %H:%M:%S')
        datas_dict_planning['Planification']['Date & Heure fin'][i] = activity.planned_datetime_end.strftime('%Y-%m-%d %H:%M:%S')
        datas_dict_planning['Planification']['Villages'][i] = " ; ".join([v.get('name') for v in activity.administrative_levels]) if activity.administrative_levels else ""
    

    if not os.path.exists("media/statistics"):
            os.makedirs("media/statistics")
    file_path = f'statistics/planning_{str(datetime.today().replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_")}.xlsx'

    df = pd.DataFrame(datas_dict_planning['Précédentes'])

    with pd.ExcelWriter("media/"+file_path) as writer:
        df.to_excel(writer, sheet_name='Précédentes', index=False)
        
        for k, v in datas_dict_planning.items():
            if k != 'Précédentes':
                pd.DataFrame(
                    v
                ).to_excel(writer, sheet_name=k, index=False)

        
    if platform == "win32":
        # windows
        return file_path.replace("/", "\\\\")
    else:
        return file_path