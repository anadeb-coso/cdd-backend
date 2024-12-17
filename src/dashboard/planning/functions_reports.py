from datetime import datetime, timedelta
from django.utils.translation import gettext_lazy
from django.utils.dateparse import parse_datetime
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q
import pytz
import os
import pandas as pd
from sys import platform

from dashboard.administrative_levels.functions import get_cascade_villages_by_administrative_level_id
from subprojects.models import Project as MisProject
from process_manager.models import Project
from cdd.call_objects_from_other_db import mis_objects_call
from assignments.models import AssignAdministrativeLevelToFacilitator
from dashboard.facilitators.repository.db_facilitator_repository import FacilitatorRepository
from dashboard.facilitators.repository.facilitator_criteria import FacilitatorCriteria
from planning.models import Activity
from cdd.functions import get_dates_between


def planning_csv(request):
    project = Project.objects.get(id=request.session.get('project_id'))
    project_mis = mis_objects_call.filter_objects(MisProject, name=request.session.get('project_name'))
    project_mis_id = project_mis.first().id if project_mis.count() >= 1 else 1

    id_region = request.GET.get('id_region')
    id_prefecture = request.GET.get('id_prefecture')
    id_commune = request.GET.get('id_commune')
    id_canton = request.GET.get('id_canton')
    id_village = request.GET.get('id_village')
    type_field = request.GET.get('type_field')

    ids_canton = request.GET.getlist('id_canton[]')
    ids_village = request.GET.getlist('id_village[]')

    current_monday_date = request.GET.get('current_monday_date')
    date_start_selected = request.GET.get('date_start_selected')
    date_end_selected = request.GET.get('date_end_selected')
    show_my_calendar = request.GET.get('show_my_calendar') in ('true', True)
    task_status = request.GET.get('task_status', 'All')
    task_type = request.GET.get('task_type', 'All')
    username_facilitator_user = request.GET.getlist('username_facilitator_user[]')
    print(username_facilitator_user)

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
        "Statut": {},
        "Rapport": {},
        "Date & Heure début": {},
        "Date & Heure fin": {},
        "Commentaires": {},
        "Villages": {},
    }
    plan_datas = {
        "Nom": {},
        "Composante": {},
        "Activité": {},
        "Description": {},
        "Date & Heure début": {},
        "Date & Heure fin": {},
        "Villages": {},
    }
    datas_dict_planning = {
        "Précédentes": previous_datas,
        "Planification": plan_datas
    }
    

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

    _id = 0
    facilitators = []
    liste_villages_ids = None
    
    if (id_region or id_prefecture or id_commune or ids_canton or ids_village) and type_field != 'clear':
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
        elif ids_canton and type_field == "canton":
            _type = "canton"
            _id = ids_canton
        elif ids_village and type_field == "village":
            _type = "village"
            _id = ids_village

        liste_prefectures = []
        liste_communes = []
        liste_cantons = []
        liste_villages = []

        liste_villages = get_cascade_villages_by_administrative_level_id(_id)
        liste_villages_ids = [int(v['administrative_id']) for v in liste_villages]

        if type(_id) is not list:
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
                projects__id=[request.session.get('project_id')]
            )
        else:
            criteria = FacilitatorCriteria(
                develop_mode=is_develop,
                training_mode=is_training,
                # active=True,
                projects__id=[request.session.get('project_id')]
            )
    else:
        is_training = bool(request.GET.get('is_training', "False") == "True")
        is_develop = bool(request.GET.get('is_develop', "False") == "True")
        criteria = FacilitatorCriteria(
            develop_mode=is_develop,
            training_mode=is_training,
            # active=True,
            projects__id=[request.session.get('project_id')]
        )
    facilitators = []
    users = []
    if username_facilitator_user:
        facilitators = FacilitatorRepository().find_by_criteria(criteria=criteria)
        users = User.objects.filter(projects__in=[request.session.get('project_id')])
        if 'All' not in username_facilitator_user and '' not in username_facilitator_user:
            facilitators = facilitators.filter(username__in=username_facilitator_user)
            users = users.filter(username__in=((username_facilitator_user+[request.user.id]) if show_my_calendar else username_facilitator_user))

    planned_date_list = [datetime.strptime(d, '%Y-%m-%d').date() for d in week_dates]
    planned_datetime_list = [parse_datetime(f"{d}T00:00:00.000000Z").replace(tzinfo=pytz.UTC) for d in week_dates]
    
    planned_datetime_list_query = Q()
    for _date in planned_datetime_list:
        planned_datetime_list_query |= (Q(planned_datetime_start__lte=_date) & Q(planned_datetime_end__gte=_date))

    # activities = Activity.objects.filter(Q(planned_date__in=planned_date_list) | Q(Q(type="vacation") & planned_datetime_list_query), project_id=project.id)
    activities = Activity.objects.filter(Q(planned_date__in=planned_date_list) | planned_datetime_list_query, project_id=project.id)
    
    if show_my_calendar:
        activities = activities.filter(Q(facilitator_id=request.user.id) | Q(user_id=request.user.id))
    
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

    query = Q()
    query |= Q(user__in=users)
    if not show_my_calendar:
        query |= Q(facilitator__in=facilitators)
    activities = activities.filter(query)
    
    activities = activities.order_by('component', 'user__last_name', 'user__first_name', 'facilitator__name', 'planned_datetime_start', 'planned_datetime_end')
    
    
    activities_previous = activities.filter(Q(planned_datetime_start__lte=date_start_selected_object))
    activities_previous = list(activities_previous)
    
    for i in range(len(activities_previous)):
        activity = activities_previous[i]
        datas_dict_planning['Précédentes']['Nom'][i] = f"{activity.user.last_name} {activity.user.first_name}" if activity.user else activity.facilitator.name
        datas_dict_planning['Précédentes']['Composante'][i] = activity.component
        datas_dict_planning['Précédentes']['Activité'][i] = f"{activity.name} ({activity.vacation_type})" if activity.vacation_type else activity.name
        datas_dict_planning['Précédentes']['Description'][i] = activity.description
        datas_dict_planning['Précédentes']['Date & Heure début'][i] = activity.planned_datetime_start.strftime('%Y-%m-%d %H:%M:%S')
        datas_dict_planning['Précédentes']['Date & Heure fin'][i] = activity.planned_datetime_end.strftime('%Y-%m-%d %H:%M:%S')
        datas_dict_planning['Précédentes']['Statut'][i] = gettext_lazy("Yes") if activity.completed else gettext_lazy("No")
        datas_dict_planning['Précédentes']['Commentaires'][i] = f"{gettext_lazy('Another activity is done instead: ')}{activity.another_detail.get('name') if activity.another_detail else gettext_lazy('Not defined')}" if not activity.completed and activity.is_another else activity.undo_comment
        datas_dict_planning['Précédentes']['Rapport'][i] = activity.comment
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