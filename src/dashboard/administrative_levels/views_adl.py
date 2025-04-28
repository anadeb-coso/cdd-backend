from django.contrib.auth.hashers import make_password
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import redirect, render
from django.shortcuts import get_object_or_404
from urllib.parse import urlencode
from django.urls import reverse
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy
from django.utils import translation
from django.views import generic
from rest_framework import response, generics as rest_generics
from datetime import datetime
from django.core.paginator import Paginator
from django.db.models import Q, QuerySet
import re as re_module
from functools import reduce
from django.db.models import Sum
from django.forms.models import model_to_dict
from django.db.models import OuterRef, Subquery


from process_manager.models import Phase, Activity, Task, Project
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
from dashboard.administrative_levels.forms import AttachmentFilterForm
from cdd.my_librairies.functions import strip_accents, get_datas_dict
from dashboard.reports.constants import IGNORES, PEULS
from subprojects.models import Project as MisProject
from process_manager.models import AggregatedStatus


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

        
        project_mis = mis_objects_call.filter_objects(MisProject, name=self.request.session.get('project_name')).first()
        project_mis_id = project_mis.id if project_mis else 1
        
        # assign_facilitators = mis_objects_call.filter_objects(AssignAdministrativeLevelToFacilitator,
        #     project_id=project_mis_id,
        #     # activated=True
        # )
        # _ll = list(set([
        #     Facilitator.objects.get(id=a_f.facilitator_id).name for a_f in assign_facilitators
        # ]))
        # print(_ll)
        # print(len(_ll))
        # _adls = mis_objects_call.filter_objects(administrativelevels_models.AdministrativeLevel,
        #         id__in=list(set([int(f.administrative_level_id) for f in assign_facilitators]))
        # )
        # print("_adls", len(_adls))
        # purs = mis_objects_call.get_object(MisProject, name="PURS")
        # print(
        #     [adl_purs.name for adl_purs in purs.administrative_levels.all() for adl_coso in _adls if adl_coso.id == adl_purs.id]
        # )

        # print("_cvd", len(mis_objects_call.filter_objects(administrativelevels_models.CVD,
        #         headquarters_village__id__in=list(set([int(adl.id) for adl in _adls]))
        # )))

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
                # assign_facilitators = assign_facilitators.filter(
                #     administrative_level_id__in=[int(v['administrative_id']) for v in liste_villages]
                # )

                administrativelels = mis_objects_call.filter_objects(administrativelevels_models.CVD,
                    # headquarters_village__id__in=list(set([int(f.administrative_level_id) for f in assign_facilitators]))
                    headquarters_village__id__in=[adl.id for adl in project_mis.administrative_levels.filter(id__in=[int(v['administrative_id']) for v in liste_villages])]
                )
            else:
                administrativelels = mis_objects_call.filter_objects(administrativelevels_models.CVD,
                    # headquarters_village__id__in=list(set([int(f.administrative_level_id) for f in assign_facilitators]))
                    headquarters_village__id__in=[adl.id for adl in project_mis.administrative_levels.all()]
                )
            
        else:
            is_training = bool(self.request.GET.get('is_training', "False") == "True")
            is_develop = bool(self.request.GET.get('is_develop', "False") == "True")
            administrativelels = mis_objects_call.filter_objects(administrativelevels_models.CVD,
                # headquarters_village__id__in=list(set([int(f.administrative_level_id) for f in assign_facilitators]))
                headquarters_village__id__in=[adl.id for adl in project_mis.administrative_levels.all()]
            )


        # # Récupérer les IDs des villages du quartier général dans une liste
        # _headquarters_village_ids = [adl_cvd.headquarters_village_id for adl_cvd in administrativelels]

        # # Récupérer les IDs des niveaux administratifs assignés à un facilitateur
        # _administrative_level_ids_and_facilitator_ids_assigned = list(mis_objects_call.filter_objects(AssignAdministrativeLevelToFacilitator,
        #         administrative_level_id__in=_headquarters_village_ids,
        #         project_id=self.request.session.get("project_mis_id"),
        #         activated=True
        #     ).values_list('administrative_level_id', 'facilitator_id'))
        
        # _administrative_level_ids_assigned = set(_adl_f[0] for _adl_f in _administrative_level_ids_and_facilitator_ids_assigned)
        # _facilitators = list(facilitator._asdict() for facilitator in Facilitator.objects.filter(id__in=[_adl_f[1] for _adl_f in _administrative_level_ids_and_facilitator_ids_assigned]).values_list('id', 'name', 'no_sql_db_name', 'phone', named=True))

        # _facilitator_ids_assigned = [
        #     {**_f, 'administrative_level_id': _adl_f[0], 'facilitator_id': int(_adl_f[1])} 
        #     for _adl_f in _administrative_level_ids_and_facilitator_ids_assigned for _f in _facilitators if int(_adl_f[1]) == _f['id']
        # ]
        
        # # Récupérer les agrégations associées aux quartiers généraux de villages
        # aggregs = AggregatedStatus.objects.filter(
        #     administrative_level_id__in=_headquarters_village_ids,
        #     project__id=self.request.session.get("project_id"),
        #     cycle__id=self.request.session.get("cycle_id"),
        #     task=None,
        #     facilitator=None
        # ).values('administrative_level_id').annotate(
        #     total_tasks_completed=Sum('total_tasks_completed'),
        #     total_tasks=Sum('total_tasks')
        # )

        # # Créer un dictionnaire des agrégations par ID de niveau administratif
        # aggregs_dict = {
        #     agg['administrative_level_id']: {
        #         'total_tasks_completed': agg['total_tasks_completed'] or 0,
        #         'total_tasks': agg['total_tasks'] or 1
        #     }
        #     for agg in aggregs
        # }

        # # Ajouter des informations aux éléments administratifs
        # _administrativelels = []
        # for _adl in administrativelels:
        #     if _adl.headquarters_village_id in _administrative_level_ids_assigned:
        #         _adl.is_facilitator_on_this_cvd = True
        #         _fs = [_f for _f in _facilitator_ids_assigned if _f['administrative_level_id'] == _adl.headquarters_village_id]
        #         if _fs:
        #             print(_fs)
        #             _adl.last_facilitator = _fs[0]


        #     # Vérifier s'il existe une agrégation pour ce village
        #     if _adl.headquarters_village_id in aggregs_dict:
        #         totals = aggregs_dict[_adl.headquarters_village_id]
        #         t_t_c = totals['total_tasks_completed']
        #         t_t = totals['total_tasks']
                
        #         # Calculer le pourcentage de tâches CDD et la dernière activité
        #         _adl.percent_cdd = round((t_t_c / t_t) * 100, 2)

        #         # Trouver la dernière activité à partir des agrégations existantes
        #         _aggregs = aggregs.filter(administrative_level_id=_adl.headquarters_village_id)
        #         _adl.last_activity_cdd = _aggregs.latest('last_activity') if _aggregs.exists() else None

        #     # Ajouter l'élément administratif à la liste
        #     _administrativelels.append(_adl)




        # # Récupérer les IDs des villages du quartier général dans une liste
        # _headquarters_village_ids = [adl_cvd.headquarters_village_id for adl_cvd in administrativelels]

        # # Récupérer les IDs des niveaux administratifs assignés à un facilitateur et les facilitators
        # _assigned_data = mis_objects_call.filter_objects(AssignAdministrativeLevelToFacilitator,
        #     administrative_level_id__in=_headquarters_village_ids,
        #     project_id=self.request.session.get("project_mis_id"),
        #     activated=True
        # ).values_list('administrative_level_id', 'facilitator_id')

        # # Créer un set pour les niveaux administratifs assignés et un dictionnaire pour les facilitators
        # _administrative_level_ids_assigned = {adl_f[0] for adl_f in _assigned_data}
        # _facilitator_ids_assigned = {adl_f[1] for adl_f in _assigned_data}

        # # Créer un dictionnaire facilitators pour un accès rapide
        # facilitators = {f.id: f._asdict() for f in Facilitator.objects.filter(id__in=_facilitator_ids_assigned).values_list('id', 'name', 'no_sql_db_name', 'phone', named=True)}

        # # Créer un dictionnaire de liaisons entre administrative_level_id et facilitators
        # facilitator_assignments = {
        #     adl_f[0]: {
        #         'facilitator_id': int(adl_f[1]),
        #         'facilitator': facilitators.get(int(adl_f[1]))
        #     }
        #     for adl_f in _assigned_data
        # }

        # # Récupérer les agrégations associées aux quartiers généraux de villages
        # aggregs_by_project = AggregatedStatus.objects.filter(
        #     administrative_level_id__in=_headquarters_village_ids,
        #     project__id=self.request.session.get("project_id"),
        #     cycle__id=self.request.session.get("cycle_id"),
        #     task=None,
        #     facilitator=None
        # )
        
        # aggregs = aggregs_by_project.values('administrative_level_id').annotate(
        #     total_tasks_completed=Sum('total_tasks_completed'),
        #     total_tasks=Sum('total_tasks')
        # )

        # # Créer un dictionnaire des agrégations par ID de niveau administratif
        # aggregs_dict = {
        #     agg['administrative_level_id']: {
        #         'total_tasks_completed': agg['total_tasks_completed'] or 0,
        #         'total_tasks': agg['total_tasks'] or 1
        #     }
        #     for agg in aggregs
        # }

        # # Ajouter des informations aux éléments administratifs
        # _administrativelels = []
        # for _adl in administrativelels:
        #     # Si un facilitateur est assigné à ce village, l'ajouter
        #     if _adl.headquarters_village_id in _administrative_level_ids_assigned:
        #         _adl.is_facilitator_on_this_cvd = True
        #         facilitator_data = facilitator_assignments.get(_adl.headquarters_village_id)
        #         if facilitator_data and facilitator_data['facilitator']:
        #             _adl.last_facilitator = facilitator_data['facilitator'] if facilitator_data['facilitator'] else {}
            
        #     # Vérifier si une agrégation existe pour ce village
        #     if _adl.headquarters_village_id in aggregs_dict:
        #         totals = aggregs_dict[_adl.headquarters_village_id]
        #         t_t_c = totals['total_tasks_completed']
        #         t_t = totals['total_tasks']
                
        #         # Calculer le pourcentage de tâches CDD et la dernière activité
        #         _adl.percent_cdd = round((t_t_c / t_t) * 100, 2)

        #         # Trouver la dernière activité à partir des agrégations existantes
        #         _aggregs = aggregs_by_project.filter(administrative_level_id=_adl.headquarters_village_id)
        #         _adl.last_activity_cdd = _aggregs.latest('last_activity').last_activity if _aggregs.exists() else None

        #     # Ajouter l'élément administratif à la liste
        #     _administrativelels.append(_adl)





        # Récupérer les IDs des villages du quartier général
        _headquarters_village_ids = [adl_cvd.headquarters_village_id for adl_cvd in administrativelels]

        # # Récupérer les niveaux administratifs assignés à un facilitateur et les facilitateurs associés
        # _assigned_data = mis_objects_call.filter_objects(
        #     AssignAdministrativeLevelToFacilitator,
        #     administrative_level_id__in=_headquarters_village_ids,
        #     project_id=self.request.session.get("project_mis_id"),
        #     activated=True
        # ).values_list('administrative_level_id', 'facilitator_id')
        # Récupérer les IDs des villages du quartier général

        # Sous-requête pour obtenir la dernière affectation désactivée
        last_deactivated_subquery = mis_objects_call.filter_objects(
            AssignAdministrativeLevelToFacilitator,
            administrative_level_id=OuterRef('administrative_level_id'),
            project_id=self.request.session.get("project_mis_id"),
            activated=False
        ).order_by('-updated_date').values('facilitator_id')[:1]  # Prendre le plus récent

        # Requête principale : récupérer les affectations actives ou la dernière désactivée si aucune active n'existe
        _assigned_data = mis_objects_call.filter_objects(
            AssignAdministrativeLevelToFacilitator,
            administrative_level_id__in=_headquarters_village_ids,
            project_id=self.request.session.get("project_mis_id")
        ).annotate(
            last_deactivated_facilitator=Subquery(last_deactivated_subquery)
        ).values_list('administrative_level_id', 'facilitator_id', 'last_deactivated_facilitator')

        # Construire la liste finale avec priorité aux affectations actives
        final_assignments = [
            (adl_id, facilitator_id if facilitator_id else last_deactivated_facilitator)
            for adl_id, facilitator_id, last_deactivated_facilitator in _assigned_data
        ]



        # Création des dictionnaires pour accès rapide
        _administrative_level_ids_assigned = {adl_f[0] for adl_f in final_assignments}
        _facilitator_ids_assigned = {int(adl_f[1]) for adl_f in final_assignments}

        # Récupérer les facilitateurs en une seule requête
        facilitators = Facilitator.objects.filter(id__in=_facilitator_ids_assigned).in_bulk(field_name='id')
        
        # Création d'un dictionnaire des affectations
        facilitator_assignments = {
            adl_id: {
                'facilitator_id': int(fac_id),
                'facilitator':  model_to_dict(facilitators.get(int(fac_id))) if facilitators.get(int(fac_id)) else {}
            }
            for adl_id, fac_id in final_assignments
        }

        # Récupérer les agrégations associées aux quartiers généraux des villages
        aggregs_by_project = AggregatedStatus.objects.filter(
            administrative_level_id__in=_headquarters_village_ids,
            project_id=self.request.session.get("project_id"),
            cycle_id=self.request.session.get("cycle_id"),
            task=None,
            facilitator=None
        )

        # Agréger les tâches et stocker les résultats sous forme de dictionnaire
        aggregs_dict = {
            agg['administrative_level_id']: {
                'total_tasks_completed': agg['total_tasks_completed'] or 0,
                'total_tasks': agg['total_tasks'] or 1
            }
            for agg in aggregs_by_project.values('administrative_level_id').annotate(
                total_tasks_completed=Sum('total_tasks_completed'),
                total_tasks=Sum('total_tasks')
            )
        }

        # Récupérer les dernières activités des villages
        latest_activities = {
            agg.administrative_level_id: agg.last_activity
            for agg in aggregs_by_project.order_by('administrative_level_id', '-last_activity')
        }

        # Ajout des informations aux niveaux administratifs
        _administrativelels = []
        for _adl in administrativelels:
            hq_village_id = _adl.headquarters_village_id

            # Vérifier si un facilitateur est assigné
            if hq_village_id in _administrative_level_ids_assigned:
                _adl.is_facilitator_on_this_cvd = True
                facilitator_data = facilitator_assignments.get(hq_village_id)
                _adl.last_facilitator = facilitator_data['facilitator'] if facilitator_data and facilitator_data['facilitator'] else {}
                
            # Vérifier si une agrégation existe pour ce village
            if hq_village_id in aggregs_dict:
                totals = aggregs_dict[hq_village_id]
                _adl.percent_cdd = round((totals['total_tasks_completed'] / totals['total_tasks']) * 100, 2)

                # Récupérer la dernière activité enregistrée
                _adl.last_activity_cdd = latest_activities.get(hq_village_id)

            _administrativelels.append(_adl)



        return _administrativelels

    def get_queryset(self):

        return self.get_results()


class AdministrativeLevelDetailForListView(FacilitatorMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'administrative_levels/administrative_level_detail_for_list.html'
    context_object_name = 'administrative_level_detail_for_list'

    def get_results(self):
        administrative_level_id = self.request.GET.get('administrative_level')
        selector = {
            "type": "task",
            "project_id": self.request.session.get('project_couch_id')
        }
        if self.request.session.get('cycle_couch_id'):
            selector['cycle_id'] = self.request.session.get('cycle_couch_id')
        
        if administrative_level_id:
            headquarters_village_id = get_headquarters_village_id(self.cvds, administrative_level_id)
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
                                old_forms = _.get('old_forms')
                                old_form_response = old_forms[-1].get("form_response") if old_forms else []
                                if form_response or old_form_response:
                                    _populationVillage = None
                                    _generalitiesSurVillage = get_datas_dict(form_response, "generalitiesSurVillage", 1)
                                    if not _generalitiesSurVillage:
                                        _generalitiesSurVillage = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)
                                    if _generalitiesSurVillage:
                                        _populationVillage = _generalitiesSurVillage["populationVillage"]
                                    dict_administrative_levels_with_infos['villages'][village.get('name')]['populationVillage'] = _populationVillage
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



class AdministrativeLevelDetailView(FacilitatorMixin, PageMixin, LoginRequiredMixin, generic.DetailView):
    template_name = 'administrative_levels/profile/profile.html'
    context_object_name = 'adl_doc'
    title = gettext_lazy('CVD')
    active_level1 = 'administrative_levels'
    model = None #Facilitator
    # breadcrumb = [
    #     {
    #         'url': reverse_lazy('dashboard:facilitators:list'),
    #         'title': gettext_lazy('Facilitators')
    #     },
    #     {
    #         'url': '',
    #         'title': title
    #     }
    # ]
    def get_results(self):
        administrative_level_id = self.request.GET.get('administrative_level')
        selector = {
            "type": "task",
            "project_id": self.request.session.get('project_couch_id')
        }
        if self.request.session.get('cycle_couch_id'):
            selector['cycle_id'] = self.request.session.get('cycle_couch_id')
        if administrative_level_id:
            selector["administrative_level_id"] = administrative_level_id

        return self.facilitator_db.get_query_result(selector)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
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
        context['facilitator_db_name'] = self.facilitator_db_name
        context['administrative_level_id'] = self.request.GET.get('administrative_level')
        last_activity_date = "0000-00-00 00:00:00"
        total_tasks_completed = 0
        total_tasks_uncompleted = 0
        total_task_pending = 0
        total_tasks_rejected = 0
        total_tasks_validated = 0
        _attachments = []
        attachments = []
        context['population'] = 0
        context['nbr_menages'] = 0
        context['nbr_men'] = 0
        context['nbr_women'] = 0
        context['young'] = 0
        context['elderly'] = 0
        context['handicap'] = 0
        context['households_added'] = 0
        context['households_added_due_to_conflict'] = 0
        context['liste_minorities'] = []
        context['languages'] = []

        total_tasks = 0
        dict_administrative_levels_with_infos = {'villages': {}}

        phases =  Phase.objects.get_objects_by_general_filtre(request=self.request, attrs=None)
        context['phases'] = phases

        activities_per_phase = {}
        for phase in phases:
            activities_per_phase[phase.order] =  Activity.objects.filter(phase__order=phase.order).get_objects_by_general_filtre(request=self.request, attrs=None).values('name', 'phase', 'description', 'order').order_by('order')

        context["activities_per_phase"] = activities_per_phase


        object_list = self.get_results()

        if object_list:
            for _ in object_list:
                for administrative_level_cvd in self.cvds:
                    for village in administrative_level_cvd['villages']:
                        if village and str(village.get("id")) == str(_.get("administrative_level_id")):
                            
                            _attachments += [i for i in (_.get("attachments") if _.get("attachments") else []) if i.get("attachment")]
                            
                            if _.get("completed") is False:
                                total_task_pending += 1
                            elif _.get("completed") is True and _.get("validated") is True:
                                total_tasks_validated += 1
                            elif _.get("completed") is True and _.get("validated") is False:
                                total_tasks_rejected += 1
                            elif _.get("completed") is True:
                                total_tasks_completed += 1
                                
                            if _.get('type') == "task" and _.get('last_updated') and last_activity_date < datetime_complet_str(_.get('last_updated')):
                                last_activity_date = datetime_complet_str(_.get('last_updated'))
                                context['last_activity'] = _
                                
                            total_tasks += 1

                            if dict_administrative_levels_with_infos.get('villages').get(village.get('name')):
                                if _.get("completed") is False:
                                    dict_administrative_levels_with_infos.get('villages')[village.get('name')][
                                        'total_tasks_pending'] += 1
                                if _.get("completed") is True and _.get("validated") is False:
                                    dict_administrative_levels_with_infos.get('villages')[village.get('name')][
                                        'total_tasks_rejected'] += 1
                                elif _.get("completed") is True and _.get("validated") is True:
                                    dict_administrative_levels_with_infos.get('villages')[village.get('name')][
                                        'total_tasks_validated'] += 1
                                elif _.get('completed') is True:
                                    dict_administrative_levels_with_infos.get('villages')[village.get('name')][
                                        'total_tasks_completed'] += 1

                                dict_administrative_levels_with_infos.get('villages')[village.get('name')][
                                    'total_tasks'] += 1
                            else:
                                if _.get("completed") is False:
                                    dict_administrative_levels_with_infos.get('villages')[village.get('name')] = {
                                        'total_tasks_completed': 0,
                                        'total_tasks_uncompleted': 0,
                                        'total_tasks_validated': 0,
                                        'total_tasks_pending': 1,
                                        'total_tasks_rejected': 0
                                    }
                                elif _.get("completed") is True and _.get("validated") is False:
                                    dict_administrative_levels_with_infos.get('villages')[village.get('name')] = {
                                        'total_tasks_completed': 0,
                                        'total_tasks_uncompleted': 0,
                                        'total_tasks_validated': 0,
                                        'total_tasks_pending': 0,
                                        'total_tasks_rejected': 1
                                    }
                                elif _.get("completed") is True and _.get("validated") is True:
                                    dict_administrative_levels_with_infos.get('villages')[village.get('name')] = {
                                        'total_tasks_completed': 0,
                                        'total_tasks_uncompleted': 0,
                                        'total_tasks_validated': 1,
                                        'total_tasks_pending': 0,
                                        'total_tasks_rejected': 0
                                    }
                                elif _.get("completed") is True and _.get("validated") is False:
                                    dict_administrative_levels_with_infos.get('villages')[village.get('name')] = {
                                        'total_tasks_completed': 0,
                                        'total_tasks_uncompleted': 0,
                                        'total_tasks_validated': 0,
                                        'total_tasks_pending': 0,
                                        'total_tasks_rejected': 1
                                    }
                                elif _.get('completed') is True:
                                    dict_administrative_levels_with_infos.get('villages')[village.get('name')] = {
                                        'total_tasks_completed': 1,
                                        'total_tasks_uncompleted': 0,
                                        'total_tasks_validated': 0,
                                        'total_tasks_pending': 0,
                                        'total_tasks_rejected': 0
                                    }
                                dict_administrative_levels_with_infos.get('villages')[village.get('name')][
                                    'total_tasks'] = 1

                            self.set_progress_data(
                                dict_administrative_levels_with_infos,
                                village.get('name'),
                                _.get("phase_name"),
                                _.get("completed")
                            )
                            dict_administrative_levels_with_infos.get('villages')[village.get('name')]['id'] = str(
                                village.get("id"))

                            if _.get("phase_name") == "VISITES PREALABLES" and _.get(
                                    "name") == 'Etablissement du profil du village':
                                form_response = _.get('form_response')
                                old_forms = _.get('old_forms')
                                old_form_response = old_forms[-1].get("form_response") if old_forms else []
                                if form_response or old_form_response:
                                    _populationVillage = None
                                    _generalitiesSurVillage = get_datas_dict(form_response, "generalitiesSurVillage", 1)
                                    if not _generalitiesSurVillage:
                                        _generalitiesSurVillage = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)
                                    if _generalitiesSurVillage:
                                        _populationVillage = _generalitiesSurVillage["populationVillage"]
                                    dict_administrative_levels_with_infos['villages'][village.get('name')]['populationVillage'] = _populationVillage
                                else:
                                    dict_administrative_levels_with_infos['villages'][village.get('name')][
                                        'populationVillage'] = 0

                            dict_administrative_levels_with_infos['villages'][village.get('name')][
                                'percentage_tasks_completed'] = (
                                        (dict_administrative_levels_with_infos['villages'][village.get('name')][
                                             'total_tasks_completed'] /
                                         dict_administrative_levels_with_infos['villages'][village.get('name')][
                                             'total_tasks']) * 100) if \
                            dict_administrative_levels_with_infos['villages'][village.get('name')][
                                'total_tasks'] else 0

                            context['administrative_level_name'] = village.get('name')
        
                            if _.get('sql_id') == 20: #Etablissement du profil du village
                                if not form_response or (form_response and not form_response[0]):
                                    old_forms = _.get('old_forms')
                                    form_response = old_forms[-1].get("form_response") if old_forms else []
                                try:
                                    try:
                                        _data = get_datas_dict(form_response, "population", 1)["populationTotaleDuVillage"]
                                    except:
                                        _data = get_datas_dict(form_response, "generalitiesSurVillage", 1)["populationVillage"]
                                    context['population'] += (_data if _data else 0)
                                except Exception as exc:
                                    context['population'] = context['population']
                                
                                try:
                                    _nbr_menages = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalHouseHolds"]
                                    context['nbr_menages'] += (_nbr_menages if _nbr_menages else 0)
                                except Exception as exc:
                                    context['nbr_menages'] = context['nbr_menages']
                                
                                try:
                                    try:
                                        _nbr_men = get_datas_dict(form_response, "population", 1)["populationNombreDeHommes"]
                                    except:
                                        _nbr_men = (
                                            get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalHommesMoins35"] + \
                                            get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalHommesPlus35"]
                                        )
                                    context['nbr_men'] += (_nbr_men if _nbr_men else 0)
                                except Exception as exc:
                                    context['nbr_men'] = context['nbr_men']
                                
                                try:
                                    try:
                                        _nbr_women = get_datas_dict(form_response, "population", 1)["populationNombreDeFemmes"]
                                    except:
                                        _nbr_women = (
                                            get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalFemmesMoins35"] + \
                                            get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalFemmesPlus35"]
                                        )
                                        context['nbr_women'] += (_nbr_women if _nbr_women else 0)
                                except Exception as exc:
                                    context['nbr_women'] = context['nbr_women']
                                
                                try:
                                    try:
                                        _young = get_datas_dict(form_response, "populationPersonnesJeunes", 2)["populationPersonnesJeunesTotal"]
                                    except:
                                        _young = (
                                            get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalHommesMoins35"] + \
                                            get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalFemmesMoins35"]
                                        )
                                        context['young'] += (_young if _young else 0)
                                except Exception as exc:
                                    context['young'] = context['young']
                                
                                try:
                                    try:
                                        _elderly = get_datas_dict(form_response, "populationPersonnesAgees", 2)["populationPersonnesAgeesTotal"]
                                    except:
                                        _elderly = 0
                                    context['elderly'] += (_elderly if _elderly else 0)
                                except Exception as exc:
                                    context['elderly'] = context['elderly']
                                
                                try:
                                    try:
                                        _handicap = get_datas_dict(form_response, "populationPersonnesHandicape", 2)["populationPersonnesHandicapeTotal"]
                                    except:
                                        _handicap = 0
                                    context['handicap'] += (_handicap if _handicap else 0)
                                except Exception as exc:
                                    context['handicap'] = context['handicap']
                                
                                try:
                                    try:
                                        _households_added = get_datas_dict(form_response, "situationDesMenages", 1)['totalNouveauxMenages']
                                    except:
                                        _households_added = 0
                                    context['households_added'] += (_households_added if _households_added else 0)
                                except Exception as exc:
                                    context['households_added'] = context['households_added']
                                
                                try:
                                    try:
                                        _households_added_due_to_conflict = get_datas_dict(form_response, "situationDesMenages", 1)['nbrNouveauxMenagesRaisonConflits']
                                    except:
                                        _households_added_due_to_conflict = 0
                                    context['households_added_due_to_conflict'] += (_households_added_due_to_conflict if _households_added_due_to_conflict else 0)
                                except Exception as exc:
                                    context['households_added_due_to_conflict'] = context['households_added_due_to_conflict']
                                
                                
                                try:
                                    _data = get_datas_dict(form_response, "population", 1)["populationEthniqueMinoritaire"]
                                    if _:
                                        _copy = (strip_accents(_data).strip()).title().replace('-', ' ')
                                        if _copy and _copy not in context['liste_minorities'] and _copy not in IGNORES and 'Pas De ' not in _copy:
                                            context['liste_minorities'] += [i.strip() for i in re_module.split('[,;/]|Et', _copy)]
                                except Exception as exc:
                                    pass
                                
                                try:
                                    ethnicite = get_datas_dict(form_response, "Ethnicité", 1)
                                    _l = []
                                    if ethnicite:
                                        for ethnic in ethnicite:
                                            if ethnic and ethnic.get("NomEthnicité"):
                                                _copy = (strip_accents(ethnic["NomEthnicité"]).strip()).title().replace('-', ' ')
                                                if _copy and _copy not in _l and _copy not in IGNORES and 'Pas De ' not in _copy:
                                                    _l += [i.strip() for i in re_module.split('[,;/]|Et', _copy)]
                                    else:
                                        for i in range(1, 4):
                                            lang = get_datas_dict(form_response, "principaleLanguesParlees", 1)[f"principaleLangueParlee{i}"]
                                            if not lang:
                                                lang = get_datas_dict(form_response, "principaleLanguesParlees", 1)[f"autrePrincipaleLangueParlee{i}"]
                                                if lang in ('-', None, ''):
                                                    lang = None
                                            if lang:
                                                _l.append(lang)
                                    context['languages'] += _l
                                    if 'Autres' in _l:
                                        _l.remove('Autres')
                                        _l.append('Autres')
                                except Exception as exc:
                                    pass
                                        
                                        
                                        
        context['total_tasks_completed'] = total_tasks_completed
        context['total_tasks_uncompleted'] = total_tasks_uncompleted
        context['total_tasks_validated'] = total_tasks_validated
        context['total_tasks_rejected'] = total_tasks_rejected
        context['total_task_pending'] = total_task_pending
        context['total_tasks'] = total_tasks
        context['percentage_tasks_completed'] = ((total_tasks_completed / total_tasks) * 100) if total_tasks else 0
        context['nbr_villages'] = 0

        context['dict_administrative_levels_with_infos'] = dict_administrative_levels_with_infos
        if last_activity_date == "0000-00-00 00:00:00":
            context['last_activity_date'] = None
        else:
            context['last_activity_date'] = datetime.strptime(last_activity_date, '%Y-%m-%d %H:%M:%S')

        attachment_image_principal = None
        for attach in _attachments:
            attach_name = str(attach.get("name")).lower()
            if attach and attach.get("type") and "image" in attach.get("type") and attach.get("attachment") and 'photo de la réunion' in attach_name:
                attachment_image_principal = attach
                attachments.append(attach)
        
        context["images_data"] = {
                "images": attachments,
                "exists_at_least_image": len(attachments) != 0,
                "first_image": attachment_image_principal if attachment_image_principal else None,
            }
        
        
        context['liste_minorities'] = ", ".join(list(set(reduce(lambda a, b : a + ['Peuhl'] if b in PEULS else a + [b], context['liste_minorities'] , []))))
        context['languages'] = ", ".join(list(set(reduce(lambda a, b : a + ['Peuhl'] if b in PEULS else a + [b], context['languages'] , []))))
                
        return context

    def set_progress_data(self, dict_administrative_levels_with_infos, village_name, phase_name, completed):
        dict_administrative_levels_with_infos['villages'][village_name][phase_name] = completed

    def get_object(self, queryset=None):
        return self.doc
    
    
class TaskDetailAjaxView(generic.TemplateView):
    template_name = 'administrative_levels/profile/task_detail.html'  # Define your template location

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Get task id from URL parameters
        task_id = self.kwargs.get('pk', None)
        task = Task.objects.filter(id=task_id).first()

        if task:
            # Ensure dict_form_responses is a valid JSON string or dict
            # Adding task details to the context
            context['task'] = {
                'name': task.name,
                'description': task.description,
                'status': task.status,
                'task': {
                    'form_response': task.form_responses,  # This is now a properly formatted JSON string or a dict
                    'form': task.form,  # This is now a properly formatted JSON string or a dict
                    'attachments': task.attachments,  # This is now a properly formatted JSON string or a dict
                },  # This is now a properly formatted JSON string or a dict
            }
        else:
            # Optionally handle the case where the task is not found
            context['error'] = 'Task not found'

        return context
    
class AttachmentListView(PageMixin, LoginRequiredMixin, generic.TemplateView):
    template_name = "administrative_levels/attachments/attachments.html"
    context_object_name = "attachments"
    title = gettext_lazy("Gallery")
    paginate_by = 10
    no_sql_db_name = None
    administrative_level = None
    cvd = None

    def post(self, request, *args, **kwargs):
        url = reverse("dashboard:administrative_levels:attachments")
        final_querystring = request.GET.copy()

        for key, value in request.GET.items():
            if (
                key in request.POST
                and value != request.POST[key]
                and request.POST[key] != ""
            ):
                final_querystring.pop(key)

        post_dict = request.POST.copy()
        post_dict.update(final_querystring)
        post_dict.pop("csrfmiddlewaretoken")
        if "reset-hidden" in post_dict and post_dict["reset-hidden"] == "true":
            return redirect(url)

        for key, value in request.POST.items():
            if value == "":
                post_dict.pop(key)
        final_querystring.update(post_dict)
        if final_querystring:
            url = "{}?{}".format(url, urlencode(final_querystring))
        return redirect(url)

    def get_context_data(self, **kwargs):
        context = super(AttachmentListView, self).get_context_data(**kwargs)

        context["administrative_levels"] = mis_objects_call.filter_objects(administrativelevels_models.AdministrativeLevel,
            type='Village'
        )

        context["phases"] = Phase.objects.get_objects_by_general_filtre(request=self.request, attrs=None)
        if "administrative_level" in self.request.GET and self.request.GET[
            "administrative_level"
        ] not in ["", None]:
            context["phases"] = context["phases"]
            # .filter(
            #     village__id=self.request.GET["administrative_level"]
            # )

        context["activities"] = Activity.objects.get_objects_by_general_filtre(request=self.request, attrs=None)
        if "phase" in self.request.GET and self.request.GET["phase"] not in ["", None]:
            context["activities"] = context["activities"].filter(
                phase__id=self.request.GET["phase"]
            )

        context["tasks"] = Task.objects.get_objects_by_general_filtre(request=self.request, attrs=None)
        if "activities" in self.request.GET and self.request.GET["activities"] not in [
            "",
            None,
        ]:
            context["tasks"] = context["tasks"].filter(
                activity__id=self.request.GET["activities"]
            )

        query_params: dict = self.request.GET

        context["query_strings"] = self.get_query_strings_context()
        context["query_strings_raw"] = query_params.copy()

        form = AttachmentFilterForm()

        # paginator: Paginator = self.__build_db_filter()

        # context["no_results"] = paginator.count == 0
        # context["current_language"] = translation.get_language()
        # page_number = query_params.get("page", 1)
        # context["attachments"] = paginator.get_page(page_number)
        context["attachments"] = self.__build_db_filter()
        context["form"] = form
        context['no_sql_db_name'] = self.no_sql_db_name
        context['administrative_level_id'] = self.administrative_level_id
        context['cvd'] = self.cvd
        return context

    def get_template_names(self, *args, **kwargs):
        # if self.request.htmx:
        #     return "administrative_levels/attachments/_grid.html"
        # else:
            return self.template_name

    def __build_db_filter(self) -> Paginator:
        query: QuerySet = self.get_queryset()

        # query = query.order_by("created_date")
        paginator = Paginator(query, 36)

        return query

    def get_query_strings_context(self):
        resp = dict()
        for key, value in self.request.GET.items():
            if value not in [None, ""]:
                if key == "administrative_level":
                    resp["Administrative-levels"] = ", ".join(
                        mis_objects_call.filter_objects(administrativelevels_models.AdministrativeLevel,
                            id__in=[int(value)], type="Village"
                        ).values_list("name", flat=True)
                    )
                if key == "phase":
                    resp["Phases"] = ", ".join(
                        Phase.objects.filter(id__in=[int(value)]).get_objects_by_general_filtre(request=self.request, attrs=None).values_list(
                            "name", flat=True
                        )
                    )
                if key == "activities":
                    resp["Activities"] = ", ".join(
                        Activity.objects.filter(id__in=[int(value)]).get_objects_by_general_filtre(request=self.request, attrs=None).values_list(
                            "name", flat=True
                        )
                    )
                if key == "tasks":
                    resp["Tasks"] = ", ".join(
                        Task.objects.filter(id__in=[int(value)]).get_objects_by_general_filtre(request=self.request, attrs=None).values_list(
                            "name", flat=True
                        )
                    )
                if key == "types":
                    resp["Types"] = [value]

        return resp

    def get_queryset(self):
        
        project_mis = mis_objects_call.filter_objects(MisProject, name=self.request.session.get('project_name'))
        project_mis_id = project_mis.first().id if project_mis.count() >= 1 else 1

        queryset = []
        nsc = NoSQLClient()
        selector = {
            "type": "task"
        }
        if "administrative_level" in self.request.GET and self.request.GET[
            "administrative_level"
        ] not in ["", None]:
            administrative_level_id = self.request.GET['administrative_level']
            self.cvd = mis_objects_call.get_object(administrativelevels_models.CVD, headquarters_village__id=int(administrative_level_id))
            assign_facilitators = mis_objects_call.filter_objects(AssignAdministrativeLevelToFacilitator,
                    administrative_level_id=int(administrative_level_id),
                    project_id=project_mis_id
                )
            self.administrative_level_id = administrative_level_id
            self.no_sql_db_name = Facilitator.objects.get(id=assign_facilitators.last().facilitator_id).no_sql_db_name
            self.facilitator_db = nsc.get_db(self.no_sql_db_name)
            
            if administrative_level_id:
                selector["administrative_level_id"] = administrative_level_id
            
            if "task" in self.request.GET and self.request.GET["task"] not in [
                "",
                None,
            ]:
                selector["name"] = Task.objects.get(id=self.request.GET["task"]).name
            elif "activity" in self.request.GET and self.request.GET[
                "activity"
            ] not in ["", None]:
                selector["activity_name"] = Activity.objects.get(id=self.request.GET["activity"]).name
            elif "phase" in self.request.GET and self.request.GET["phase"] not in [
                "",
                None,
            ]:
                selector["phase_name"] = Phase.objects.get(id=self.request.GET["phase"], project_id=self.request.session.get('project_id')).name
        # else:
        #     if "phase" in self.request.GET and self.request.GET["phase"] not in [
        #         "",
        #         None,
        #     ]:
        #         queryset = queryset.filter(
        #             adm__id=self.request.GET["administrative_level"]
        #         )
        #     elif "activities" in self.request.GET and self.request.GET[
        #         "activities"
        #     ] not in ["", None]:
        #         queryset = queryset.filter(
        #             adm__id=self.request.GET["administrative_level"]
        #         )
        #     elif "tasks" in self.request.GET and self.request.GET["tasks"] not in [
        #         "",
        #         None,
        #     ]:
        #         queryset = queryset.filter(
        #             adm__id=self.request.GET["administrative_level"]
        #         )

        # ordering = self.get_ordering()
        # if ordering:
        #     if isinstance(ordering, str):
        #         ordering = (ordering,)
        #     queryset = queryset.order_by(*ordering)
        
        object_list = self.facilitator_db.get_query_result(selector)
        attachments = []
        
        if object_list:
            for _ in object_list:
                if 'type' in self.request.GET:
                    if self.request.GET.get('type') == 'Photo':
                        attachments += [i for i in (_.get("attachments") if _.get("attachments") else []) if (
                            i.get("attachment") and i.get("type") and "image" in i.get("type")
                        )]
                    elif self.request.GET.get('type') == 'Document':
                        attachments += [i for i in (_.get("attachments") if _.get("attachments") else []) if (
                            i.get("attachment") and i.get("type") and "pdf" in str(i['type']).lower() and "word" in str(i['type']).lower() and "excel" in str(i['type']).lower()
                        )]
                    else:
                        attachments += [i for i in (_.get("attachments") if _.get("attachments") else []) if (
                            i.get("attachment") and i.get("type")
                        )]
                else:
                    attachments += [i for i in (_.get("attachments") if _.get("attachments") else []) if (
                        i.get("attachment") and i.get("type") and "image" in i.get("type") and 'photo de la réunion' in str(i.get("name")).lower()
                    )]
        
        return attachments
    
    
    
class TaskDetailAjaxView(generic.TemplateView):
    template_name = 'administrative_levels/profile/task_detail.html'  # Define your template location

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Get task id from URL parameters
        task_id = self.kwargs.get('pk', None)
        task = Task.objects.filter(id=task_id).first()

        if task:
            # Ensure dict_form_responses is a valid JSON string or dict
            # Adding task details to the context
            context['task'] = {
                'name': task.name,
                'description': task.description,
                'status': task.status,
                'task': {
                    'form_response': task.form_responses,  # This is now a properly formatted JSON string or a dict
                    'form': task.form,  # This is now a properly formatted JSON string or a dict
                    'attachments': task.attachments,  # This is now a properly formatted JSON string or a dict
                },  # This is now a properly formatted JSON string or a dict
            }
        else:
            # Optionally handle the case where the task is not found
            context['error'] = 'Task not found'

        return context
    

class FillAttachmentSelectFilters(rest_generics.GenericAPIView):
    """
    Region -> Prefecture -> Commune -> Canton -> Village
    """

    def post(self, request, *args, **kwargs):
        select_type = request.POST['type']
        child_qs = list()
        if select_type == 'administrative_level':
            parent_obj = mis_objects_call.get_object(administrativelevels_models.AdministrativeLevel, id=request.POST['value'])
            child_qs = Phase.objects.get_objects_by_general_filtre(request=self.request, attrs=None) #village=parent_obj, 
        elif select_type == 'phase':
            parent_obj = Phase.objects.get(id=request.POST['value'])
            child_qs = Activity.objects.filter(phase=parent_obj).get_objects_by_general_filtre(request=self.request, attrs=None)
        elif select_type == 'activity': 
            parent_obj = Activity.objects.get(id=request.POST['value'])
            child_qs = Task.objects.filter(activity=parent_obj).get_objects_by_general_filtre(request=self.request, attrs=None)

        return response.Response({
            'values': [{'id': child.id, 'name': child.name} for child in child_qs]
        })