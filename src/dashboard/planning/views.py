from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy
from django.views import generic
from datetime import datetime, timedelta

from authentication.models import Facilitator
from no_sql_client import NoSQLClient
from dashboard.mixins import AJAXRequestMixin, PageMixin, JSONResponseMixin
from dashboard.facilitators.forms import FilterFacilitatorForm
from dashboard.administrative_levels.functions import get_cascade_villages_by_administrative_level_id
from assignments.models import AssignAdministrativeLevelToFacilitator
from authentication.functions import get_assign_adl_by_facilitatr
from administrativelevels import models as administrativelevels_models
from cdd.call_objects_from_other_db import mis_objects_call
from cdd.constants import PHASES_COLORS, PHASES_WITH_THEIR_NUMBERS
from cdd.utils import elements_communs



class PlanningListView(PageMixin, LoginRequiredMixin, generic.ListView):
    model = Facilitator
    queryset = Facilitator.objects.filter(active=True)
    template_name = 'planning/list.html'
    context_object_name = 'planning'
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
            
            if query_result:
                tasks_planed = []
                
                for task in query_result[:]:
                    tasks_planed += [
                        {
                            "planning": p,
                            "day": datetime.strptime(p['planned_date'], "%Y-%m-%d").date().weekday(),
                            "task": task['name'],
                            "color": PHASES_COLORS[PHASES_WITH_THEIR_NUMBERS[task['phase_name']]],
                            "datetime": p['planned_datetime_start'],
                            "task_order": task.get('task_order')
                         } for p in task['planning'] if p['planned_date'] in week_dates
                    ]

                _f = {
                    # 'facilitator': f, 
                    'person': f.name, 'tasks': tasks_planed}

            
            
            _facilitators[str(current_week)].append(_f)

        return _facilitators

    def get_queryset(self):

        return self.get_results()