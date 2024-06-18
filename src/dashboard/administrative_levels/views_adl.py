from django.contrib.auth.hashers import make_password
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import redirect, render
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
from dashboard.facilitators.functions import (
    get_cvds, get_cvd_name_by_village_id, is_village_principal, single_task_by_cvd,
    clear_facilitator_docs_by_administrativelevels_and_save_to_backup_db, 
    get_headquarters_village_id
)
from administrativelevels import models as administrativelevels_models
from assignments.models import AssignAdministrativeLevelToFacilitator
from dashboard.administrative_levels.functions import get_administrative_levels_under_json, get_cascade_villages_by_administrative_level_id
from cdd.functions import datetime_complet_str, exists_id_in_a_dict
from cdd.call_objects_from_other_db import mis_objects_call
from authentication.functions import get_assign_adl_by_facilitatr
from dashboard.tasks import sync_celery_tasks_re
from dashboard.facilitators.views import FacilitatorMixin


class AdministrativeLevelListView(PageMixin, LoginRequiredMixin, generic.TemplateView):
    template_name = 'administrative_levels/list.html'
    context_object_name = 'adls'
    title = gettext_lazy('Villages')
    active_level1 = 'administrative_levels'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = FilterFacilitatorForm()
        context['breadcrumb'] = False

        context['is_training'] = bool(self.request.GET.get('training', '0') != '0')
        context['is_develop'] = bool(self.request.GET.get('develop', '0') != '0')
        context['region_id'] = self.request.GET.get('region_id')
        
        return context


class AdministrativeLevelListTableView(LoginRequiredMixin, generic.ListView):
    template_name = 'administrative_levels/administrative_level_list.html'
    context_object_name = 'administrative_levels'

    def get_results(self):
        id_region = self.request.GET.get('id_region')
        id_prefecture = self.request.GET.get('id_prefecture')
        id_commune = self.request.GET.get('id_commune')
        id_canton = self.request.GET.get('id_canton')
        id_village = self.request.GET.get('id_village')
        type_field = self.request.GET.get('type_field')
        _id = 0
        assign_facilitators = mis_objects_call.filter_objects(AssignAdministrativeLevelToFacilitator,
            project_id=1,
            activated=True
        )

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
            liste_villages = []
            
            liste_villages = get_cascade_villages_by_administrative_level_id(_id)

            if type(_id) is not list:
                assign_facilitators = assign_facilitators.filter(
                    administrative_level_id__in=[int(v['administrative_id']) for v in liste_villages]
                )

                administrativelels = mis_objects_call.filter_objects(administrativelevels_models.CVD,
                    headquarters_village__id__in=list(set([int(f.administrative_level_id) for f in assign_facilitators]))
                )
            else:
                administrativelels = mis_objects_call.filter_objects(administrativelevels_models.CVD,
                    headquarters_village__id__in=list(set([int(f.administrative_level_id) for f in assign_facilitators]))
                )
            
        else:
            is_training = bool(self.request.GET.get('is_training', "False") == "True")
            is_develop = bool(self.request.GET.get('is_develop', "False") == "True")
            administrativelels = mis_objects_call.filter_objects(administrativelevels_models.CVD,
                headquarters_village__id__in=list(set([int(f.administrative_level_id) for f in assign_facilitators]))
            )


        return administrativelels

    def get_queryset(self):

        return self.get_results()


class AdministrativeLevelDetailForListView(FacilitatorMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'administrative_levels/administrative_level_detail_for_list.html'
    context_object_name = 'administrative_level_detail_for_list'

    def get_results(self):
        administrative_level_id = self.request.GET.get('administrative_level')
        selector = {
            "type": "task",
        }
        print("administrative_level_id")
        if administrative_level_id:
            print(type(administrative_level_id))
            headquarters_village_id = get_headquarters_village_id(self.cvds, administrative_level_id)
            print(headquarters_village_id)
            selector["administrative_level_id"] = headquarters_village_id

        return self.facilitator_db.get_query_result(selector)

    def get_queryset(self):
        index = int(self.request.GET.get('index'))
        offset = int(self.request.GET.get('offset'))

        object_list = single_task_by_cvd(self.get_results(), self.cvds)

        if object_list:
            for _ in object_list:
                _["phase_order"] = 0
                _["activity_order"] = 0


        return sorted(object_list,
                      key=lambda obj: (str(obj["phase_order"]) + str(obj["activity_order"]) + str(obj["order"])))[
               index:index + offset]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        total_tasks_completed = 0
        total_tasks_uncompleted = 0
        total_tasks = 0
        dict_administrative_levels_with_infos = {'villages': {}, 'upcomingEvents': {}}
        object_list = self.get_results()

        context['facilitator_id'] = self.kwargs.get('id')
        context['village_name'] = self.request.GET.get('villageName')

        if object_list:
            for _ in object_list:

                for administrative_level_cvd in self.cvds:
                    for village in administrative_level_cvd['villages']:

                        if village and str(village.get("id")) == str(_.get("administrative_level_id")):
                            if _.get("completed"):
                                total_tasks_completed += 1
                            else:
                                total_tasks_uncompleted += 1
                            total_tasks += 1

                            if dict_administrative_levels_with_infos.get('villages').get(village.get('name')):
                                if _.get("completed"):
                                    dict_administrative_levels_with_infos.get('villages').get(village.get('name'))[
                                        'total_tasks_completed'] += 1
                                else:
                                    dict_administrative_levels_with_infos.get('villages').get(village.get('name'))[
                                        'total_tasks_uncompleted'] += 1
                                dict_administrative_levels_with_infos.get('villages').get(village.get('name'))[
                                    'total_tasks'] += 1
                                
                                last_activity_date = dict_administrative_levels_with_infos.get('villages').get(village.get('name'))[
                                    'last_activity_date']
                                last_updated = datetime_complet_str(_.get('last_updated'))
                                if last_updated and last_activity_date < last_updated:
                                    dict_administrative_levels_with_infos.get('villages').get(village.get('name'))[
                                    'last_activity_date'] = last_updated
                                    dict_administrative_levels_with_infos.get('villages').get(village.get('name'))[
                                    'last_activity_task'] = f"{_['phase_name']} ; {_['activity_name']} ; {_['name']}"
                            
                            else:
                                if _.get("completed"):
                                    dict_administrative_levels_with_infos['villages'][village.get('name')] = {
                                        'total_tasks_completed': 1,
                                        'total_tasks_uncompleted': 0,
                                        'last_activity_date': datetime_complet_str(_.get('last_updated')),
                                        'last_activity_task': f"{_['phase_name']} ; {_['activity_name']} ; {_['name']}"
                                    }

                                else:
                                    dict_administrative_levels_with_infos['villages'][village.get('name')] = {
                                        'total_tasks_completed': 0,
                                        'total_tasks_uncompleted': 1,
                                        'last_activity_date': datetime_complet_str(_.get('last_updated')),
                                        'last_activity_task': f"{_['phase_name']} ; {_['activity_name']} ; {_['name']}"
                                    }
                                dict_administrative_levels_with_infos.get('villages').get(village.get('name'))[
                                    'total_tasks'] = 1
                                dict_administrative_levels_with_infos.get('villages').get(village.get('name'))[
                                    'phase_name'] = _.get('phase_name')

                            if _.get("phase_name") == "VISITES PREALABLES" and _.get("name") == 'Etablissement du profil du village':
                                form_response =  _.get('form_response')
                                if form_response:
                                    dict_administrative_levels_with_infos['villages'][village.get('name')]['populationVillage'] = form_response[0]['generalitiesSurVillage']['populationVillage']
                                else:
                                    dict_administrative_levels_with_infos['villages'][village.get('name')][
                                        'populationVillage'] = 0

                            dict_administrative_levels_with_infos.get('villages').get(village.get('name'))[
                                'percentage_tasks_completed'] = ((dict_administrative_levels_with_infos.get('villages').get(village.get('name'))[
                                        'total_tasks_completed'] / dict_administrative_levels_with_infos.get('villages').get(village.get('name'))[
                                        'total_tasks']) * 100) if dict_administrative_levels_with_infos.get('villages').get(village.get('name'))[
                                        'total_tasks'] else 0

                            # if _.get('completed') is False:
                            #     _["planned_date"] = "2024-2-28 23:17:2"
                            # else:
                            #     _["planned_date"] = "2024-2-28 13:17:2"

                            if (_.get('completed') is False and _.get('planned_date')
                                    and (
                                            self.request.GET.get('villageName') == ''
                                            or self.request.GET.get('villageName') is None
                                            or village.get('name') == self.request.GET.get('villageName')
                                    )
                            ):
                                date = datetime.strptime(_.get('planned_date').split(' ')[0], '%Y-%m-%d')
                                hour =  datetime.strptime(_.get('planned_date'), '%Y-%m-%d %H:%M:%S')

                                if dict_administrative_levels_with_infos.get('upcomingEvents').get(date) is not None:
                                    if dict_administrative_levels_with_infos.get('upcomingEvents').get(
                                            date).get(hour) is not None:
                                        dict_administrative_levels_with_infos.get('upcomingEvents')[date][hour].append(

                                                    {
                                                        "village": village.get('name'),
                                                        "name": _.get('name'),
                                                        "phase_name": _.get('phase_name'),
                                                        "percentage_tasks_completed": dict_administrative_levels_with_infos.get('villages').get(
                                                            village.get('name'))[
                                                            'percentage_tasks_completed']
                                                                }

                                            )
                                    else:
                                        dict_administrative_levels_with_infos.get('upcomingEvents')[date][hour] = [
                                            {
                                                "village": village.get('name'),
                                                "name": _.get('name'),
                                                "phase_name": _.get('phase_name'),
                                                "percentage_tasks_completed": dict_administrative_levels_with_infos.get('villages').get(
                                                    village.get('name'))[
                                                    'percentage_tasks_completed']
                                                }
                                        ]
                                else:
                                    dict_administrative_levels_with_infos.get('upcomingEvents')[date] = {}
                                    dict_administrative_levels_with_infos.get('upcomingEvents')[date][hour] = [
                                        {
                                            "village": village.get('name'),
                                            "name": _.get('name'),
                                            "phase_name": _.get('phase_name'),
                                            "percentage_tasks_completed": dict_administrative_levels_with_infos.get('villages').get(
                                                village.get('name'))[
                                                'percentage_tasks_completed']
                                        }
                                    ]


        context['total_tasks_completed'] = total_tasks_completed
        context['total_tasks_uncompleted'] = total_tasks_uncompleted
        context['total_tasks'] = total_tasks
        context['percentage_tasks_completed'] = ((total_tasks_completed / total_tasks) * 100) if total_tasks else 0
        context['dict_administrative_levels_with_infos'] = dict_administrative_levels_with_infos
        context['facilitator_db_name'] = self.facilitator_db_name


        return context
