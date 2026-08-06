from django.contrib.auth.hashers import make_password
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.http import Http404
from django.shortcuts import redirect, render
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy
from django.views import generic
from datetime import datetime, timedelta
from django.contrib.auth.models import User
import itertools
from django.db.models import Q

from process_manager.models import Phase, Activity, Project, ProcessAddOrRemoveADL, Cycle
from authentication.models import Facilitator
from dashboard.facilitators.forms import FacilitatorForm, FilterTaskForm, UpdateFacilitatorForm, FilterFacilitatorForm
from dashboard.mixins import AJAXRequestMixin, PageMixin, JSONResponseMixin
from no_sql_client import NoSQLClient
from dashboard.utils import (
    sync_geographicalunits_with_cvd_on_facilittor
)
from authentication.permissions import (
    CDDSpecialistPermissionRequiredMixin,
    AdminPermissionRequiredMixin
    )
from .functions import (
    get_cvds, single_task_by_cvd, get_db_task,
    get_search_for_stabilized_facilitator_dbs,
    update_facilitators_stats
)
from cdd.constants import VALIDATION_PROCESS_COLORS
from administrativelevels import models as administrativelevels_models
from assignments.models import AssignAdministrativeLevelToFacilitator
from dashboard.administrative_levels.functions import get_cascade_villages_by_administrative_level_id
from cdd.functions import datetime_complet_str, exists_id_in_a_dict, exists_id_in_a_dict_by_project_and_cycle, is_datetime_in_past_or_now
from cdd.call_objects_from_other_db import mis_objects_call
from authentication.functions import get_assign_adl_by_facilitatr, get_assigns_adl_by_facilitatrs
from dashboard.tasks import sync_celery_tasks_re
from .repository.db_facilitator_repository import FacilitatorRepository
from .repository.facilitator_criteria import FacilitatorCriteria
from subprojects.models import Project as MisProject
from cdd.views_manage_url_parse import redirect_user_to_login, redirect_to_an_url
from cdd.my_librairies.functions import get_datas_dict
from process_manager.models import AggregatedStatus, Task, Cycle, Project, AggregatedStatusFacilitator
from planning.models import Activity as ActivityPlanning
from dashboard.tasks import bulk_objects_create_or_update


class FacilitatorListView(PageMixin, LoginRequiredMixin, generic.ListView):
    model = Facilitator
    queryset = []
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

    # def get_queryset(self):
    #     return FacilitatorRepository().find_by_criteria(
    #         FacilitatorCriteria(
    #             active=True, projects__id=[self.request.session.get('project_id')], 
    #             facilitator_type=self.request.GET.get('type_of_facilitator_list', 'community_facilitator')
    #         )
    #     )
    def get_queryset(self):
        return super().get_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = FilterFacilitatorForm()
        context['breadcrumb'] = False

        context['is_training'] = bool(self.request.GET.get('training', '0') != '0')
        context['is_develop'] = bool(self.request.GET.get('develop', '0') != '0')
        context['region_id'] = self.request.GET.get('region_id')
        context['type_facilitator'] = self.request.GET.get('type_facilitator')
        context['type_of_facilitator_list'] = self.request.GET.get('type_of_facilitator_list', 'community_facilitator')

        context['active_level2'] = context['type_of_facilitator_list']

        is_training = bool(self.request.GET.get('is_training', "False") == "True")
        is_develop = bool(self.request.GET.get('is_develop', "False") == "True")
        criteria = FacilitatorCriteria(
            develop_mode=is_develop,
            training_mode=is_training,
            active=(False if context['type_facilitator']=='inactive' else True),
            projects__id=[self.request.session.get('project_id')],
            facilitator_type=context['type_of_facilitator_list']
        )
        context['total_facilitators'] = FacilitatorRepository().find_by_criteria(criteria=criteria).count()

        context['project_names'] = f"{', '.join([p.name for p in Project.objects.get(id=self.request.session.get('project_id')).build_the_tree_structure()])}"

        agg = AggregatedStatus.objects.filter(project_id=self.request.session.get('project_id'), cycle_id=self.request.session.get('cycle_id'), task__isnull=False, facilitator=None).order_by('-updated_date').first()
        context['last_update'] = agg.updated_date if agg else None
        self.title = f"{self.title} {context['last_update'].strftime('%Y-%m-%dT%H:%M:%S.%fZ')}" if context['last_update'] else self.title
        
        if self.request.user.is_authenticated and self.request.user.is_superuser and self.request.GET.get('sync', False) in ('1', 1):
            # sync_celery_tasks_re()
            AggregatedStatusFacilitator.objects.filter(project_id=self.request.session.get('project_id'), cycle_id=self.request.session.get('cycle_id')).update(new_update_exists=True)
            
        return context


class FacilitatorMixin(LoginRequiredMixin):
    doc = None
    obj = None
    facilitator_db = None
    facilitator_db_name = None
    cvds = None
    project_mis_id = None
    facilitator_grm = None
    no_sql_dbs_names_with_village_ids = {}

    def dispatch(self, request, *args, **kwargs):
        nsc = NoSQLClient()
        self.cvds = []
        try:
            if not self.request.user.is_authenticated:
                return redirect_user_to_login(request)
            if (
                not self.request.session.get('project_id') or 
                not self.request.session.get('cycle_id') or 
                not self.request.session.get('tree_structure_projects_ids') or 
                (request.user.groups.filter(name__in=["Supervisor"]).exists() and not self.request.session.get('cantons_stabilized_ids'))
            ):
                return redirect_to_an_url(request, 'dashboard:process_manager:list')

            self.facilitator_db_name = kwargs['id']
            self.facilitator_db = nsc.get_db(self.facilitator_db_name)
            query_result = self.facilitator_db.get_query_result({
                "type": 'facilitator',
                "$or": [
                    {"project_id": request.session.get('project_couch_id')},
                    {"projects_ids": {"$in": [request.session.get('project_couch_id')]}}
                ]
            })[:]
            self.doc = self.facilitator_db[query_result[0]['_id']]
            self.obj = get_object_or_404(Facilitator, no_sql_db_name=kwargs['id'])

            project_mis = mis_objects_call.filter_objects(MisProject, name=self.request.session.get('project_name')).first()
            self.project_mis_id = project_mis.id if project_mis else 1


            
            # eadls = nsc.get_db('eadls')
            # try:
            #     self.facilitator_grm = eadls.get_query_result({
            #         "type": "adl",
            #         "representative.email": self.doc.get('email')
            #     })[:][0]
            #     administrative_regions = self.facilitator_grm['administrative_regions']
                
            #     for adl_id in administrative_regions:
            #         if adl_id not in [elt['id'] for elt in self.doc['administrative_levels']]:
            #             assing_facilitator_object = mis_objects_call.filter_objects(
            #                 AssignAdministrativeLevelToFacilitator, 
            #                 project_id=self.project_mis_id,
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
            self.no_sql_dbs_names_with_village_ids, cvds, administratives_stabilized = get_search_for_stabilized_facilitator_dbs(self.project_mis_id, self.doc)
            self.cvds += cvds

            self.cvds += get_cvds(request.session.get('project_couch_id'), request.session.get('cycle_couch_id'), self.doc, [], administratives_stabilized)
            self.cvds = sorted(self.cvds, key=lambda obj: obj.get('name'))

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
        type_facilitator = self.request.GET.get('type_facilitator')
        type_of_facilitator_list = self.request.GET.get('type_of_facilitator_list', 'community_facilitator')
        _id = 0
        facilitators = []

        project_mis = mis_objects_call.filter_objects(MisProject, name=self.request.session.get('project_name')).first()
        project_mis_id = project_mis.id if project_mis else 1
        liste_villages = []

        if (id_region or id_prefecture or id_commune or id_canton or id_village) and type_field:
            criteria = FacilitatorCriteria()

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

            liste_villages = get_cascade_villages_by_administrative_level_id(_id)
            liste_villages = [int(v['administrative_id']) for v in liste_villages]

            if type(_id) is not list:
                assign_facilitators_id_list = AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(
                    administrative_level_id__in=liste_villages,
                    project_id=project_mis_id,
                    activated=True
                ).values_list('facilitator_id', flat=True)
                criteria = FacilitatorCriteria(
                    id__in=list(set([int(facilitator_id) for facilitator_id in assign_facilitators_id_list])),
                    develop_mode=False,
                    training_mode=False,
                    active=(False if type_facilitator=='inactive' else True),
                    projects__id=[self.request.session.get('project_id')],
                    facilitator_type=type_of_facilitator_list
                )

            else:
                assign_facilitators_id_list = AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(
                    project_id=project_mis_id,
                    activated=True
                ).values_list('facilitator_id', flat=True)
                criteria = FacilitatorCriteria(
                    id__in=list(set([int(facilitator_id) for facilitator_id in assign_facilitators_id_list])),
                    develop_mode=False,
                    training_mode=False,
                    active=(False if type_facilitator=='inactive' else True),
                    projects__id=[self.request.session.get('project_id')],
                    facilitator_type=type_of_facilitator_list
                )

        else:
            assign_facilitators_id_list = AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(
                project_id=project_mis_id,
                activated=True
            ).values_list('facilitator_id', flat=True)
            is_training = bool(self.request.GET.get('is_training', "False") == "True")
            is_develop = bool(self.request.GET.get('is_develop', "False") == "True")
            criteria = FacilitatorCriteria(
                id__in=list(set([int(facilitator_id) for facilitator_id in assign_facilitators_id_list])),
                develop_mode=is_develop,
                training_mode=is_training,
                active=(False if type_facilitator=='inactive' else True),
                projects__id=[self.request.session.get('project_id')],
                facilitator_type=type_of_facilitator_list
            )

        # Liste des facilitateurs à retourner
        # _facilitators = []

        # Récupérer tous les facilitateurs en une seule requête
        facilitators = FacilitatorRepository().find_by_criteria(criteria=criteria)
        # agg_s_fs = AggregatedStatusFacilitator.objects.filter(facilitator__in=facilitators, project_id=self.request.session.get('project_id'), cycle_id=self.request.session.get('cycle_id'))
        # dict_agg_s_fs = {str(ag.facilitator.id): ag for ag in agg_s_fs}
        # havent_update = len([ag for ag in agg_s_fs[:3] if not ag.new_update_exists]) == 3
        # if havent_update:
        #     for f in facilitators:
        #         _f = dict_agg_s_fs.get(str(f.id))
        #         if _f:
        #             f.total_tasks_current_project = _f.total_tasks_current_project
        #             f.total_tasks_completed_current_project = _f.total_tasks_completed_current_project
        #             f.last_activity_current_project = _f.last_activity_current_project
        #             f.total_tasks_stabilized = _f.total_tasks_stabilized
        #             f.total_tasks_completed_stabilized = _f.total_tasks_completed_stabilized
        #             f.last_activity_stabilized = _f.last_activity_stabilized
        #             f.total_tasks = _f.total_tasks
        #             f.total_tasks_completed = _f.total_tasks_completed
        #             f.last_activity = _f.last_activity

        #             f.total_tasks_validated_current_project = _f.total_tasks_validated_current_project
        #             f.total_tasks_invalidated_current_project = _f.total_tasks_invalidated_current_project
        #             f.total_tasks_invalidated_review_current_project = _f.total_tasks_invalidated_review_current_project
        #             f.total_tasks_invalidated_unreview_current_project = _f.total_tasks_invalidated_unreview_current_project
        #             f.total_tasks_waiting_validation_current_project = _f.total_tasks_waiting_validation_current_project

        #             f.total_tasks_validated_stabilized = _f.total_tasks_validated_stabilized
        #             f.total_tasks_invalidated_stabilized = _f.total_tasks_invalidated_stabilized
        #             f.total_tasks_invalidated_review_stabilized = _f.total_tasks_invalidated_review_stabilized
        #             f.total_tasks_invalidated_unreview_stabilized = _f.total_tasks_invalidated_unreview_stabilized
        #             f.total_tasks_waiting_validation_stabilized = _f.total_tasks_waiting_validation_stabilized
                    
        #             f.total_tasks_validated = _f.total_tasks_validated
        #             f.total_tasks_invalidated = _f.total_tasks_invalidated
        #             f.total_tasks_invalidated_review = _f.total_tasks_invalidated_review
        #             f.total_tasks_invalidated_unreview = _f.total_tasks_invalidated_unreview
        #             f.total_tasks_waiting_validation = _f.total_tasks_waiting_validation
                    
        #             f.cvds_number_current_project = _f.cvds_number_current_project
        #             f.villages_number_current_project = _f.villages_number_current_project
        #             f.cvds_number_stabilized = _f.cvds_number_stabilized
        #             f.villages_number_stabilized = _f.villages_number_stabilized
        #             f.cvds_number = _f.cvds_number
        #             f.villages_number = _f.villages_number

        #             f.last_task_done_current_project = _f.last_task_done_current_project
        #             f.last_task_done_stabilized = _f.last_task_done_stabilized
        #             f.last_task_done = _f.last_task_done

        #         _facilitators.append(f)
        # else:
        #     ag_f_bucket_create = []
        #     ag_f_bucket_update = []

        #     nsc = NoSQLClient()
        #     eadls = nsc.get_db('eadls')
        #     docs_eadls = eadls.all_docs(include_docs=True)['rows']
        #     docs_eadls_dict = {doc.get('doc').get('representative').get('email'): list(itertools.chain(*[[str(v['id']) for v in ad['villages']] for ad in doc.get('doc')['administrative_regions_objects']])) for doc in docs_eadls if doc.get('doc') and doc.get('doc').get('type') == 'adl' and doc.get('doc').get('representative') and doc.get('doc').get('administrative_regions_objects')}

        #     # adls = project_mis.administrative_levels.filter(id__in=[ad.id for ad in mis_objects_call.filter_objects(administrativelevels_models.AdministrativeLevel, id__in=liste_villages)]) if liste_villages else project_mis.administrative_levels.all()
        #     adls = project_mis.administrative_levels.filter(id__in=liste_villages) if liste_villages else project_mis.administrative_levels.all()

        #     adls_with_names = {str(adl.id): adl.name for adl in adls}

        #     adl_headquarters_villages = set(adl.cvd.headquarters_village.id for adl in adls if adl.cvd and adl.cvd.headquarters_village)
        #     adl_villages_ids = set(adl.id for adl in adls if adl.cvd)


        #     aggregs = AggregatedStatus.objects.filter(administrative_level_id__in=adl_headquarters_villages, project_id=self.request.session.get('project_id'), cycle_id=self.request.session.get('cycle_id'), facilitator=None, task__isnull=False)
            
        #     # Parcours des facilitateurs
        #     for f in facilitators:
        #         ag_f_action = "update"
        #         ag_f = dict_agg_s_fs.get(str(f.id))
        #         if not ag_f:
        #             ag_f = AggregatedStatusFacilitator()
        #             ag_f.project_id = self.request.session.get('project_id')
        #             ag_f.cycle_id = self.request.session.get('cycle_id')
        #             ag_f.facilitator_id = f.id
        #             ag_f_action = "create"

        #         administrative_levels_ids = [str(adl['id']) for adl in f.administrative_levels if adl['project_id'] == self.request.session.get('project_couch_id')] if f.administrative_levels else []
        #         administrative_levels_ids_stabilize = docs_eadls_dict.get(f.email)
        #         administrative_levels_ids_stabilize = [ad_id for ad_id in administrative_levels_ids_stabilize if int(ad_id) in adl_villages_ids] if administrative_levels_ids_stabilize else []

        #         adl_headquarters_villages_uniques_current_project = set(str(elt) for elt in adl_headquarters_villages) & set(administrative_levels_ids)
        #         children_agg_current_project = [agg for agg in aggregs if str(agg.administrative_level_id) in administrative_levels_ids]
        #         f.villages_number_current_project = len(administrative_levels_ids)
        #         f.cvds_number_current_project = len(adl_headquarters_villages_uniques_current_project)
        #         ag_f.villages_number_current_project = f.villages_number_current_project
        #         ag_f.cvds_number_current_project = f.cvds_number_current_project

        #         adl_headquarters_villages_uniques_stabilized = set(str(elt) for elt in adl_headquarters_villages) & set(administrative_levels_ids_stabilize)
        #         children_agg_stabilized = [agg for agg in aggregs if str(agg.administrative_level_id) in administrative_levels_ids_stabilize]
        #         f.villages_number_stabilized = len(administrative_levels_ids_stabilize)
        #         f.cvds_number_stabilized = len(adl_headquarters_villages_uniques_stabilized)
        #         ag_f.villages_number_stabilized = f.villages_number_stabilized
        #         ag_f.cvds_number_stabilized = f.cvds_number_stabilized


        #         _administrative_levels_ids = list(set(administrative_levels_ids + administrative_levels_ids_stabilize))
        #         adl_headquarters_villages_uniques = set(str(elt) for elt in adl_headquarters_villages) & set(_administrative_levels_ids)
        #         children_agg = [agg for agg in aggregs if str(agg.administrative_level_id) in _administrative_levels_ids]
        #         f.villages_number = len(_administrative_levels_ids)
        #         f.cvds_number = len(adl_headquarters_villages_uniques)
        #         ag_f.villages_number = f.villages_number
        #         ag_f.cvds_number = f.cvds_number

        #         # Filtrer les éléments qui ont un last_activity valide (non-None)
        #         valid_aggregs_current_project = [agg for agg in children_agg_current_project if agg.last_activity is not None]
        #         valid_aggregs_stabilized = [agg for agg in children_agg_stabilized if agg.last_activity is not None]
        #         valid_aggregs = [agg for agg in children_agg if agg.last_activity is not None]

        #         # Calculer la dernière activité si possible
        #         aggreg_last_activity_current_project = max(valid_aggregs_current_project, key=lambda x: x.last_activity, default=None) if valid_aggregs_current_project else None
        #         aggreg_last_activity_stabilized = max(valid_aggregs_stabilized, key=lambda x: x.last_activity, default=None) if valid_aggregs_stabilized else None
        #         aggreg_last_activity = max(valid_aggregs, key=lambda x: x.last_activity, default=None) if valid_aggregs else None

        #         aggreg_last_task_done_current_project = max([ag for ag in valid_aggregs_current_project if ag.total_tasks_completed], key=lambda x: x.task.task_order, default=None) if valid_aggregs_current_project else None
        #         aggreg_last_task_done_stabilized = max([ag for ag in valid_aggregs_stabilized if ag.total_tasks_completed], key=lambda x: x.task.task_order, default=None) if valid_aggregs_stabilized else None
        #         aggreg_last_task_done = max([ag for ag in valid_aggregs if ag.total_tasks_completed], key=lambda x: x.task.task_order, default=None) if valid_aggregs else None


        #         # Assigner la dernière activité et les totaux des tâches
        #         f.last_activity_current_project = aggreg_last_activity_current_project.last_activity if aggreg_last_activity_current_project else None
        #         f.total_tasks_completed_current_project = sum(agg.total_tasks_completed for agg in children_agg_current_project)
        #         f.total_tasks_current_project = sum(agg.total_tasks for agg in children_agg_current_project)
        #         f.total_tasks_validated_current_project = sum(agg.total_tasks_validated for agg in children_agg_current_project)
        #         f.total_tasks_invalidated_current_project = sum(agg.total_tasks_invalidated for agg in children_agg_current_project)
        #         f.total_tasks_invalidated_review_current_project = sum(agg.total_tasks_invalidated_review for agg in children_agg_current_project)
        #         f.total_tasks_invalidated_unreview_current_project = sum(agg.total_tasks_invalidated_unreview for agg in children_agg_current_project)
        #         f.total_tasks_waiting_validation_current_project = sum(agg.total_tasks_waiting_validation for agg in children_agg_current_project)
        #         ag_f.last_activity_current_project = f.last_activity_current_project
        #         ag_f.total_tasks_completed_current_project = f.total_tasks_completed_current_project
        #         ag_f.total_tasks_current_project = f.total_tasks_current_project
        #         ag_f.total_tasks_validated_current_project = f.total_tasks_validated_current_project
        #         ag_f.total_tasks_invalidated_current_project = f.total_tasks_invalidated_current_project
        #         ag_f.total_tasks_invalidated_review_current_project = f.total_tasks_invalidated_review_current_project
        #         ag_f.total_tasks_invalidated_unreview_current_project = f.total_tasks_invalidated_unreview_current_project
        #         ag_f.total_tasks_waiting_validation_current_project = f.total_tasks_waiting_validation_current_project
                
        #         f.last_activity_stabilized = aggreg_last_activity_stabilized.last_activity if aggreg_last_activity_stabilized else None
        #         f.total_tasks_completed_stabilized = sum(agg.total_tasks_completed for agg in children_agg_stabilized)
        #         f.total_tasks_stabilized = sum(agg.total_tasks for agg in children_agg_stabilized)
        #         f.total_tasks_validated_stabilized = sum(agg.total_tasks_validated for agg in children_agg_stabilized)
        #         f.total_tasks_invalidated_stabilized = sum(agg.total_tasks_invalidated for agg in children_agg_stabilized)
        #         f.total_tasks_invalidated_review_stabilized = sum(agg.total_tasks_invalidated_review for agg in children_agg_stabilized)
        #         f.total_tasks_invalidated_unreview_stabilized = sum(agg.total_tasks_invalidated_unreview for agg in children_agg_stabilized)
        #         f.total_tasks_waiting_validation_stabilized = sum(agg.total_tasks_waiting_validation for agg in children_agg_stabilized)
        #         ag_f.last_activity_stabilized = f.last_activity_stabilized
        #         ag_f.total_tasks_completed_stabilized = f.total_tasks_completed_stabilized
        #         ag_f.total_tasks_stabilized = f.total_tasks_stabilized
        #         ag_f.total_tasks_validated_stabilized = f.total_tasks_validated_stabilized
        #         ag_f.total_tasks_invalidated_stabilized = f.total_tasks_invalidated_stabilized
        #         ag_f.total_tasks_invalidated_review_stabilized = f.total_tasks_invalidated_review_stabilized
        #         ag_f.total_tasks_invalidated_unreview_stabilized = f.total_tasks_invalidated_unreview_stabilized
        #         ag_f.total_tasks_waiting_validation_stabilized = f.total_tasks_waiting_validation_stabilized

        #         f.last_activity = aggreg_last_activity.last_activity if aggreg_last_activity else None
        #         f.total_tasks_completed = sum(agg.total_tasks_completed for agg in children_agg)
        #         f.total_tasks = sum(agg.total_tasks for agg in children_agg)
        #         f.total_tasks_validated = sum(agg.total_tasks_validated for agg in children_agg)
        #         f.total_tasks_invalidated = sum(agg.total_tasks_invalidated for agg in children_agg)
        #         f.total_tasks_invalidated_review = sum(agg.total_tasks_invalidated_review for agg in children_agg)
        #         f.total_tasks_invalidated_unreview = sum(agg.total_tasks_invalidated_unreview for agg in children_agg)
        #         f.total_tasks_waiting_validation = sum(agg.total_tasks_waiting_validation for agg in children_agg)
        #         ag_f.last_activity = f.last_activity
        #         ag_f.total_tasks_completed = f.total_tasks_completed
        #         ag_f.total_tasks = f.total_tasks
        #         ag_f.total_tasks_validated = f.total_tasks_validated
        #         ag_f.total_tasks_invalidated = f.total_tasks_invalidated
        #         ag_f.total_tasks_invalidated_review = f.total_tasks_invalidated_review
        #         ag_f.total_tasks_invalidated_unreview = f.total_tasks_invalidated_unreview
        #         ag_f.total_tasks_waiting_validation = f.total_tasks_waiting_validation

        #         f.last_task_done_current_project = aggreg_last_task_done_current_project.task if aggreg_last_task_done_current_project else None
        #         f.last_task_done_stabilized = aggreg_last_task_done_stabilized.task if aggreg_last_task_done_stabilized else None
        #         f.last_task_done = aggreg_last_task_done.task if aggreg_last_task_done else None
        #         ag_f.last_task_done_current_project = f.last_task_done_current_project
        #         ag_f.last_task_done_stabilized = f.last_task_done_stabilized
        #         ag_f.last_task_done = f.last_task_done

        #         adl_headquarters_villages_infos = []
        #         for k, v in {'current_project': adl_headquarters_villages_uniques_current_project, 'stabilized': adl_headquarters_villages_uniques_stabilized}.items():
        #             for adl_h_id in v:
        #                 if k == 'stabilized' and adl_h_id in adl_headquarters_villages_uniques_current_project:
        #                     continue

        #                 _children_aggs = [agg for agg in aggregs if str(agg.administrative_level_id) == adl_h_id]
                        
        #                 # Filtrer les éléments qui ont un last_activity valide (non-None)
        #                 _valid_aggregs = [agg for agg in _children_aggs if agg.last_activity is not None]

        #                 # Calculer la dernière activité si possible
        #                 _aggreg_last_activity = max(_valid_aggregs, key=lambda x: x.last_activity, default=None) if _valid_aggregs else None
        #                 _aggreg_last_task_done = max([ag for ag in _valid_aggregs if ag.total_tasks_completed], key=lambda x: x.task.task_order, default=None) if _valid_aggregs else None
                        
        #                 # Assigner la dernière activité et les totaux des tâches
        #                 _last_activity = _aggreg_last_activity.last_activity if _aggreg_last_activity else None
        #                 _total_tasks_completed = sum(agg.total_tasks_completed for agg in _children_aggs)
        #                 _total_tasks = sum(agg.total_tasks for agg in _children_aggs)
        #                 _total_tasks_validated = sum(agg.total_tasks_validated for agg in _children_aggs)
        #                 _total_tasks_invalidated = sum(agg.total_tasks_invalidated for agg in _children_aggs)
        #                 _total_tasks_invalidated_review = sum(agg.total_tasks_invalidated_review for agg in _children_aggs)
        #                 _total_tasks_invalidated_unreview = sum(agg.total_tasks_invalidated_unreview for agg in _children_aggs)
        #                 _total_tasks_waiting_validation = sum(agg.total_tasks_waiting_validation for agg in _children_aggs)
        #                 _last_task_done = {
        #                     'id': _aggreg_last_task_done.task.id,
        #                     'name': _aggreg_last_task_done.task.name,
        #                     'phase_name': _aggreg_last_task_done.task.phase.name,
        #                     'activity_name': _aggreg_last_task_done.task.activity.name,
        #                     'order': _aggreg_last_task_done.task.order,
        #                     'task_order': _aggreg_last_task_done.task.task_order,
        #                 } if _aggreg_last_task_done and _aggreg_last_task_done.task else None
        #                 _type = k
                        
        #                 adl_headquarters_villages_infos.append({
        #                     'village_name': adls_with_names.get(adl_h_id),
        #                     'last_activity': _last_activity.strftime('%Y-%m-%dT%H:%M:%S.%fZ') if _last_activity else None,
        #                     'total_tasks_completed': _total_tasks_completed,
        #                     'total_tasks': _total_tasks,
        #                     'percent': float("%.2f" % (((_total_tasks_completed/_total_tasks)*100) if _total_tasks else 0)),
        #                     'total_tasks_validated': _total_tasks_validated,
        #                     'total_tasks_invalidated': _total_tasks_invalidated,
        #                     'total_tasks_invalidated_review': _total_tasks_invalidated_review,
        #                     'total_tasks_invalidated_unreview': _total_tasks_invalidated_unreview,
        #                     'total_tasks_waiting_validation': _total_tasks_waiting_validation,
        #                     'last_task_done': _last_task_done,
        #                     'type': _type,
        #                     'in_the_both': adl_h_id in adl_headquarters_villages_uniques_current_project and adl_h_id in adl_headquarters_villages_uniques_stabilized
        #                 })

        #         ag_f.administrative_level_headquarters_villages_infos = adl_headquarters_villages_infos
        #         ag_f.new_update_exists = False
        #         # ag_f.save()
        #         if ag_f_action == "create":
        #             ag_f_bucket_create.append(ag_f)
        #         else:
        #             ag_f_bucket_update.append(ag_f)
                
        #         _facilitators.append(f)

        #     if ag_f_bucket_create:
        #         bulk_objects_create_or_update(AggregatedStatusFacilitator, ag_f_bucket_create, type_bulk="create")
        #     if ag_f_bucket_update:
        #         bulk_objects_create_or_update(
        #             AggregatedStatusFacilitator, 
        #             ag_f_bucket_update, type_bulk="update", 
        #             fields=[
        #                 'villages_number_current_project', 'cvds_number_current_project', 'villages_number_stabilized', 'cvds_number_stabilized',
        #                 'villages_number', 'cvds_number', 'last_activity_current_project', 'total_tasks_completed_current_project',
        #                 'total_tasks_current_project', 'total_tasks_validated_current_project', 'total_tasks_invalidated_current_project',
        #                 'total_tasks_invalidated_review_current_project', 'total_tasks_invalidated_unreview_current_project',
        #                 'total_tasks_waiting_validation_current_project', 'last_activity_stabilized', 'total_tasks_completed_stabilized',
        #                 'total_tasks_stabilized', 'total_tasks_validated_stabilized', 'total_tasks_invalidated_stabilized',
        #                 'total_tasks_invalidated_review_stabilized', 'total_tasks_invalidated_unreview_stabilized',
        #                 'total_tasks_waiting_validation_stabilized', 'last_activity', 'total_tasks_completed', 'total_tasks', 'total_tasks_validated',
        #                 'total_tasks_invalidated', 'total_tasks_invalidated_review', 'total_tasks_invalidated_unreview', 
        #                 'total_tasks_waiting_validation', 'last_task_done_current_project', 'last_task_done_stabilized', 'last_task_done', 
        #                 'administrative_level_headquarters_villages_infos', 'new_update_exists'
        #             ]
        #         )
            

        return update_facilitators_stats(
            facilitators, 
            liste_villages,
            self.request.session.get('project_id'), 
            self.request.session.get('cycle_id'),
            self.request.session.get('project_couch_id'),
            project_mis
        )

    def get_queryset(self):
        return self.get_results()



class FacilitatorsPercentListView(FacilitatorMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'facilitators/facilitator_percent_completed.html'
    context_object_name = 'facilitator_percent_completed'
    def get_results(self):
        # return self.facilitator_db.get_query_result({"type": "task"})
        
        selector = {
            "type": "task"
        }
        
        if self.request.session.get('cycle_couch_id'):
            selector['cycle_id'] = self.request.session.get('cycle_couch_id')
        if self.request.session.get('project_couch_id'):
            selector['project_id'] = self.request.session.get('project_couch_id')

        docs = self.facilitator_db.get_query_result(selector, limit=1000000)[:]
        
        nsc = NoSQLClient()
        
        for k_db_name, v in self.no_sql_dbs_names_with_village_ids.items():
            _db = nsc.get_db(k_db_name)
            docs += _db.get_query_result(selector, limit=1000000)[:]

        return docs

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
        
        selector = {
            "type": "task"
        }
        
        if self.request.session.get('cycle_couch_id'):
            selector['cycle_id'] = self.request.session.get('cycle_couch_id')
        if self.request.session.get('project_couch_id'):
            selector['project_id'] = self.request.session.get('project_couch_id')

        for f in liste:
            facilitator_db = nsc.get_db(f)
            # docs = facilitator_db.get_query_result({"type": "task"})
            
            docs = facilitator_db.get_query_result(selector, limit=1000000)[:]
            
            nsc = NoSQLClient()
            project_mis = mis_objects_call.filter_objects(MisProject, name=self.request.session.get('project_name')).first()
            project_mis_id = project_mis.id if project_mis else 1
            query_result = facilitator_db.get_query_result({
                "type": 'facilitator',
                "$or": [
                    {"project_id": request.session.get('project_couch_id')},
                    {"projects_ids": {"$in": [request.session.get('project_couch_id')]}}
                ]
            })[:]
            no_sql_dbs_names_with_village_ids, cvds, administratives_stabilized = get_search_for_stabilized_facilitator_dbs(project_mis_id, facilitator_db[query_result[0]['_id']])
            for k_db_name, v in no_sql_dbs_names_with_village_ids.items():
                _db = nsc.get_db(k_db_name)
                docs += _db.get_query_result(selector, limit=1000000)[:]
            

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
    template_name = 'facilitators/profile/profile.html'
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
    def get_results(self):
        administrative_level_id = self.request.GET.get('administrative_level')
        
        selector = {
            "type": "task"
        }
        
        if self.request.session.get('cycle_couch_id'):
            selector['cycle_id'] = self.request.session.get('cycle_couch_id')
        if self.request.session.get('project_couch_id'):
            selector['project_id'] = self.request.session.get('project_couch_id')

        if administrative_level_id:
            selector["administrative_level_id"] = administrative_level_id

        # return self.facilitator_db.get_query_result(selector)
        results = self.facilitator_db.get_query_result(selector, limit=1000000)[:]
        
        nsc = NoSQLClient()
        # print(self.no_sql_dbs_names_with_village_ids)
        for k_db_name, v in self.no_sql_dbs_names_with_village_ids.items():
            if not administrative_level_id:
                selector["administrative_level_id"] = {"$in": v['ids']}
            _db = nsc.get_db(k_db_name)
            results += _db.get_query_result(selector, limit=1000000)[:]
        return results
    
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
        facilitator_docs = self.facilitator_db.all_docs(include_docs=True)['rows']
        facilitator_docs = [doc for doc in facilitator_docs if doc.get('doc') and doc.get('doc').get('cycle_id') == self.request.session.get('cycle_couch_id') and doc.get('doc').get('project_id') == self.request.session.get('project_couch_id')]
        
        last_activity_date = "0000-00-00 00:00:00"
        total_tasks = 0
        phases =  Phase.objects.get_objects_by_general_filtre(request=self.request, attrs=None)
        context['phases'] = phases

        activities_per_phase = {}
        for phase in phases:
            activities_per_phase[phase.order] =  Activity.objects.filter(phase__order=phase.order).get_objects_by_general_filtre(request=self.request, attrs=None).values('name', 'phase', 'description', 'order').order_by('order')

        context["activities_per_phase"] = activities_per_phase
        for doc in facilitator_docs:
            doc = doc.get('doc')

            if doc.get('type') == "task" and doc.get('last_updated') and last_activity_date < datetime_complet_str(doc.get('last_updated')):
                last_activity_date = datetime_complet_str(doc.get('last_updated'))
            total_tasks += 1
        
        for k_db_name, v in self.no_sql_dbs_names_with_village_ids.items():
            _db = nsc.get_db(k_db_name)

            _selector = {"type": "task", "administrative_level_id": {"$in": v['ids']}}
            if self.request.session.get('cycle_couch_id'):
                _selector['cycle_id'] = self.request.session.get('cycle_couch_id')
            if self.request.session.get('project_couch_id'):
                _selector['project_id'] = self.request.session.get('project_couch_id')
            facilitator_docs = _db.get_query_result(_selector, limit=1000000)[:]

            for doc in facilitator_docs:
                if doc.get('type') == "task" and doc.get('last_updated') and last_activity_date < datetime_complet_str(doc.get('last_updated')):
                    last_activity_date = datetime_complet_str(doc.get('last_updated'))
                total_tasks += 1

        if last_activity_date == "0000-00-00 00:00:00":
            context['facilitator_doc']['last_activity_date'] = None
        else:
            context['facilitator_doc']['last_activity_date'] = datetime.strptime(last_activity_date, '%Y-%m-%d %H:%M:%S')

        context['total_tasks'] = total_tasks

        total_tasks_completed = 0
        total_tasks_uncompleted = 0
        total_task_pending = 0
        total_tasks_rejected = 0
        total_tasks_validated = 0

        total_tasks = 0
        dict_administrative_levels_with_infos = {'villages': {}}

        object_list = self.get_results()

        if object_list:
            for _ in object_list:
                for administrative_level_cvd in self.cvds:
                    for village in administrative_level_cvd['villages']:
                        if village and str(village.get("id")) == str(_.get("administrative_level_id")):
                            if _.get("completed") is False:
                                total_task_pending += 1
                            elif _.get("completed") is True and _.get("validated") is True:
                                total_tasks_validated += 1
                            elif _.get("completed") is True and _.get("validated") is False:
                                total_tasks_rejected += 1
                            elif _.get("completed") is True:
                                total_tasks_completed += 1
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
                                        'total_tasks_rejected': 0,
                                        'stabilized': administrative_level_cvd.get("stabilized"),
                                        'for_another_facilitator': administrative_level_cvd.get("for_another_facilitator")
                                    }
                                elif _.get("completed") is True and _.get("validated") is False:
                                    dict_administrative_levels_with_infos.get('villages')[village.get('name')] = {
                                        'total_tasks_completed': 0,
                                        'total_tasks_uncompleted': 0,
                                        'total_tasks_validated': 0,
                                        'total_tasks_pending': 0,
                                        'total_tasks_rejected': 1,
                                        'stabilized': administrative_level_cvd.get("stabilized"),
                                        'for_another_facilitator': administrative_level_cvd.get("for_another_facilitator")
                                    }
                                elif _.get("completed") is True and _.get("validated") is True:
                                    dict_administrative_levels_with_infos.get('villages')[village.get('name')] = {
                                        'total_tasks_completed': 0,
                                        'total_tasks_uncompleted': 0,
                                        'total_tasks_validated': 1,
                                        'total_tasks_pending': 0,
                                        'total_tasks_rejected': 0,
                                        'stabilized': administrative_level_cvd.get("stabilized"),
                                        'for_another_facilitator': administrative_level_cvd.get("for_another_facilitator")
                                    }
                                elif _.get("completed") is True and _.get("validated") is False:
                                    dict_administrative_levels_with_infos.get('villages')[village.get('name')] = {
                                        'total_tasks_completed': 0,
                                        'total_tasks_uncompleted': 0,
                                        'total_tasks_validated': 0,
                                        'total_tasks_pending': 0,
                                        'total_tasks_rejected': 1,
                                        'stabilized': administrative_level_cvd.get("stabilized"),
                                        'for_another_facilitator': administrative_level_cvd.get("for_another_facilitator")
                                    }
                                elif _.get('completed') is True:
                                    dict_administrative_levels_with_infos.get('villages')[village.get('name')] = {
                                        'total_tasks_completed': 1,
                                        'total_tasks_uncompleted': 0,
                                        'total_tasks_validated': 0,
                                        'total_tasks_pending': 0,
                                        'total_tasks_rejected': 0,
                                        'stabilized': administrative_level_cvd.get("stabilized"),
                                        'for_another_facilitator': administrative_level_cvd.get("for_another_facilitator")
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

        context['total_tasks_completed'] = total_tasks_completed
        context['total_tasks_uncompleted'] = total_tasks_uncompleted
        context['total_tasks_validated'] = total_tasks_validated
        context['total_tasks_rejected'] = total_tasks_rejected
        context['total_task_pending'] = total_task_pending
        context['percentage_tasks_completed'] = ((total_tasks_completed / total_tasks) * 100) if total_tasks else 0
        context['nbr_villages'] = 0

        context['dict_administrative_levels_with_infos'] = dict_administrative_levels_with_infos
        context['facilitator_db_name'] = self.facilitator_db_name

        return context

    def set_progress_data(self, dict_administrative_levels_with_infos, village_name, phase_name, completed):
        dict_administrative_levels_with_infos['villages'][village_name][phase_name] = completed

    def get_object(self, queryset=None):
        return self.doc


class FacilitatorTaskListView(FacilitatorMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'facilitators/task_list.html'
    context_object_name = 'tasks'

    def get_results(self):
        administrative_level_id = self.request.GET.get('administrative_level')
        phase_id = self.request.GET.get('phase')
        activity_id = self.request.GET.get('activity')
        task_name = self.request.GET.get('task')
        is_validated = self.request.GET.get('is_validated', None)
        is_pending = self.request.GET.get('is_pending', None)
        is_completed = self.request.GET.get('is_completed', None)
        is_rejected = self.request.GET.get('is_rejected', None)

        selector = {
            "type": "task"
        }
        if self.request.session.get('project_couch_id'):
            selector['project_id'] = self.request.session.get('project_couch_id')
        if self.request.session.get('cycle_couch_id'):
            selector['cycle_id'] = self.request.session.get('cycle_couch_id')

        if administrative_level_id:
            selector["administrative_level_id"] = administrative_level_id
        # if phase_id:
        #     selector["order"] = int(phase_id)
        if activity_id:
            selector["activity_name"] = Activity.objects.filter(order=activity_id, phase__order=phase_id).get_objects_by_general_filtre(request=self.request, attrs=None)[0].name
        if task_name:
            selector["name"] = task_name

        if is_pending == 'true':
            selector["completed"] = False
            selector["validated"] = { "$exists": False }
        if is_validated == 'true':
            selector["completed"] = True
            selector["validated"] = True
        if is_completed == 'true':
            selector["completed"] = True
            selector["validated"] = { "$exists": False }
        if is_rejected == 'true':
            selector["completed"] = True
            selector["validated"] = False
            
        # return self.facilitator_db.get_query_result(selector)
        results = self.facilitator_db.get_query_result(selector, limit=1000000)[:]
        
        nsc = NoSQLClient()
        for k_db_name, v in self.no_sql_dbs_names_with_village_ids.items():
            if not administrative_level_id:
                selector["administrative_level_id"] = {"$in": v['ids']}
            _db = nsc.get_db(k_db_name)
            results += _db.get_query_result(selector, limit=1000000)[:]
        return results

    def get_queryset(self):
        phases = Phase.objects.get_objects_by_general_filtre(request=self.request, attrs=None)
        activities = Activity.objects.get_objects_by_general_filtre(request=self.request, attrs=None)

        object_list = single_task_by_cvd(self.get_results(), self.cvds)
        
        if object_list:
            for _ in object_list:
                _["phase_order"] = 0
                _["activity_order"] = 0
                for phase_obj in phases:
                    if phase_obj.order == _["order"]:
                        _["phase_order"]=phase_obj.order
                        break
                for activity_obj in activities:
                    if activity_obj.couch_id == _["activity_id"]:
                        _["activity_name"]=activity_obj.name
                        break
        return sorted(object_list, key=lambda obj: (str(obj["phase_order"])+str(obj["activity_order"])+str(obj["order"])))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = FilterTaskForm(
            initial={
                'facilitator_db_name': self.facilitator_db_name, 
                'project_id': self.request.session.get('project_id'),
                'cycle_id': self.request.session.get('cycle_id'),
                'cvds': self.cvds
            }
        )
        context['adminLevelId'] = self.request.GET.get('administrative_level')

        context['facilitator_db_name'] = self.facilitator_db_name
        context['village_name'] = self.object_list[0]['administrative_level_name'] if len(self.object_list) > 0 else None

        index = int(self.request.GET.get('index'))
        offset = int(self.request.GET.get('offset'))
        context['total_act_tasks'] = len(self.object_list)
        context['tasks'] = self.object_list[index: index + offset]
        return context

    def set_progress_data(self, dict_administrative_levels_with_infos, village_name, phase_name, completed):
        dict_administrative_levels_with_infos['villages'][village_name][phase_name] = completed


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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = FacilitatorForm(initial={
            'project_id': self.request.session.get('project_id'),
            'user_id': self.request.user.id
        })
        return context

    def form_valid(self, form):
        data = form.cleaned_data
        password = make_password(data['password1'], salt=None, hasher='default')
        facilitator = Facilitator(username=data['username'], password=password, active=True)
        facilitator.name = data['name']
        facilitator.email = data['email']
        facilitator.phone = data['phone']
        facilitator.sex = data['sex']
        facilitator.facilitator_type = data['facilitator_type']
        facilitator.save(replicate_design=False)

        project_cdd = Project.objects.get(id=self.request.session.get('project_id'))
        cycle_cdd = Cycle.objects.get(id=self.request.session.get('cycle_id'), project_id=self.request.session.get('project_id'))

        project_mis = mis_objects_call.filter_objects(MisProject, name=self.request.session.get('project_name')).first()
        project_mis_id = project_mis.id if project_mis else 1

        _administrative_levels = []
        if 'administrative_levels' in data and data['administrative_levels']:
            for elt in data['administrative_levels']:
                administrativelevel_obj = administrativelevels_models.AdministrativeLevel.objects.using('mis').get(id=int(elt['id']))
                if administrativelevel_obj.cvd and administrativelevel_obj.cvd.headquarters_village and str(administrativelevel_obj.cvd.headquarters_village.id) == elt['id']:
                    elt['is_headquarters_village'] = True

                if project_mis and project_mis.administrative_levels.filter(id=int(elt['id'])).exists():
                    elt["project_id"] = project_cdd.couch_id
                    elt["project_name"] = project_cdd.name
                    elt["cycle_id"] = cycle_cdd.couch_id
                    elt["cycle_name"] = cycle_cdd.name

                _administrative_levels.append(elt)

        #Assign ADL
        for adl in _administrative_levels:
            _assign = AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(administrative_level_id=int(adl['id']), project_id=project_mis_id, activated=True).first()
            
            if (adl.get('id') and str(adl.get('id')).isdigit() and not _assign):
                    try:
                        assign = AssignAdministrativeLevelToFacilitator()
                        assign.administrative_level_id = int(adl['id'])
                        assign.facilitator_id = facilitator.id
                        assign.project_id = project_mis_id
                        assign.save(using='mis')
                    except Exception as exc:
                        print(exc)
        #End Assign ADL
        doc = {
            "name": data['name'],
            "email": data['email'],
            "phone": data['phone'],
            "sex": data['sex'],
            "facilitator_type": data['facilitator_type'],
            "administrative_levels": _administrative_levels,
            "type": "facilitator",
            "develop_mode": facilitator.develop_mode,
            "training_mode": facilitator.training_mode,
            "sql_id": int(facilitator.pk),
            "project_id": self.request.session.get('project_couch_id'),
            "project_name": self.request.session.get('project_name'),
            "projects_ids": [
                p.couch_id for p in data['projects'] 
            ] if 'projects' in data and data['projects'] else [],
            "projects_names": [
                p.name for p in data['projects'] 
            ] if 'projects' in data and data['projects'] else []
        }

        facilitator.administrative_levels = _administrative_levels
        facilitator.administrative_levels_ids = [int(_adl['id']) for _adl in _administrative_levels]
        facilitator.simple_save()


        nsc = NoSQLClient()
        facilitator_database = nsc.get_db(facilitator.no_sql_db_name)
        nsc.create_document(facilitator_database, doc)


        # clear_facilitator_docs_by_administrativelevels_and_save_to_backup_db(
        #     "backup_db_facilitators_docs", facilitator.no_sql_db_name,
        #     [d.get('id') for d in _administrative_levels if d.get('is_headquarters_village')]
        # ) #Copy backup db docs (for villages added that removed on facilitator before) to facilitator db and clear docs on backup

        process_adls = [d.get('id') for d in _administrative_levels if d.get('is_headquarters_village')]
        if process_adls:
            process_add_or_remove_adl = ProcessAddOrRemoveADL(
                name = f"backup_db_facilitators_docs_{facilitator.no_sql_db_name}",
                move_from = "backup_db_facilitators_docs",
                move_to = facilitator.no_sql_db_name,
                administrative_levels = process_adls,
                query_action = "create"
            )
            process_add_or_remove_adl.save()


        sync_geographicalunits_with_cvd_on_facilittor(
            self.request.session.get('project_id'),
            facilitator.develop_mode, facilitator.training_mode, facilitator.no_sql_db_name
        ) #Rebuild Unit and CVD infos on facilitator doc

        # sync_tasks(
        #     self.request.session.get('project_id'),
        #     facilitator.develop_mode, facilitator.training_mode, facilitator.no_sql_db_name,
        #     administrativelevel_ids=[d.get('id') for d in _administrative_levels if d.get('is_headquarters_village')]
        # ) #Sync the tasks for the new villages
        
        try:
            user = User.objects.get(email=facilitator.email)
            user.password = facilitator.password
            user.username = facilitator.username
            user.last_name = facilitator.name.split(' ')[0]
            user.first_name = ' '.join(facilitator.name.split(' ')[1:])
            user.is_active = facilitator.active
            user.save()
        except:
            pass
        
        if 'projects' in data and data['projects']:
            for p in data['projects']:
                p.facilitators.add(facilitator)
                p.save()

                
                try:
                    nsc_database = nsc.get_db("process_design")
                    project = nsc_database.get_query_result({"_id": p.couch_id})[0]

                    fc_project = facilitator_database.get_query_result(
                        {"type": "project", "name": project[0]['name']}
                    )[0]

                    # check if the project exists
                    if not fc_project:
                        # create the project on the facilitator database
                        nsc.create_document(facilitator_database, project[0])
                except:
                    pass



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
    project_mis_id = None

    def dispatch(self, request, *args, **kwargs):
        nsc = NoSQLClient()
        try:
            self.facilitator = self.get_object()
            self.facilitator_db_name = self.facilitator.no_sql_db_name
            self.facilitator_db = nsc.get_db(self.facilitator_db_name)
            query_result = self.facilitator_db.get_query_result({"type": "facilitator"})[:]
            self.doc = self.facilitator_db[query_result[0]['_id']]

            project_mis = mis_objects_call.filter_objects(MisProject, name=self.request.session.get('project_name')).first()
            self.project_mis_id = project_mis.id if project_mis else 1
        except Exception:
            raise Http404
        return super().dispatch(request, *args, **kwargs)



    def get_context_data(self, **kwargs):
        ctx = super(UpdateFacilitatorView, self).get_context_data(**kwargs)
        form = ctx.get('form')
        ctx.setdefault('facilitator_doc', self.doc)
        if self.doc:
            ctx['form'] = UpdateFacilitatorForm(initial={
                'facilitator_doc': self.doc, 'facilitator_projects': self.facilitator.projects.all(),
                'project_id': self.request.session.get('project_id')
            })
            if form:
                for label, field in form.fields.items():
                    try:
                        if label == "projects":
                            form.fields[label].initial = self.facilitator.projects.all()
                        else:
                            form.fields[label].value = self.doc[label]
                    except Exception as exc:
                        print(exc)
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
        facilitator_email = self.facilitator.email
        facilitator = form.save(commit=False)
        facilitator.name = data['name']
        facilitator.email = data['email']
        facilitator.phone = data['phone']
        facilitator.sex = data['sex']
        facilitator.facilitator_type = data['facilitator_type']
        facilitator = facilitator.save_and_return_object(user=self.request.user)
        administrative_levels_old = self.doc.get('administrative_levels')
        administrative_levels_remove = []
        _administrative_levels = []
        administrative_levels_new = []
        
        project_cdd = Project.objects.get(id=self.request.session.get('project_id'))
        cycle_cdd = Cycle.objects.get(id=self.request.session.get('cycle_id'), project_id=self.request.session.get('project_id'))

        if 'administrative_levels' in data and data['administrative_levels']:
            
            project_mis = mis_objects_call.filter_objects(MisProject, name=self.request.session.get('project_name')).first()
            villages_ids = [o.id for o in project_mis.administrative_levels.filter(type="Village")] if project_mis else []

            for elt in data['administrative_levels']:
                administrativelevel_obj = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(id=int(elt['id'])).first()
                if administrativelevel_obj:
                    if administrativelevel_obj.cvd and administrativelevel_obj.cvd.headquarters_village and str(administrativelevel_obj.cvd.headquarters_village.id) == elt['id']:
                        elt['is_headquarters_village'] = True

                    if elt.get("project_id") == project_cdd.couch_id and elt.get("cycle_id") == cycle_cdd.couch_id:
                        _elt = exists_id_in_a_dict_by_project_and_cycle(administrative_levels_old, elt.get('id'), elt.get('project_id'), elt.get('cycle_id'))
                        if not _elt: # Useless
                            # if project_mis and project_mis.administrative_levels.filter(id=int(elt['id'])).exists():
                            if int(elt['id']) in villages_ids:
                                elt["project_id"] = project_cdd.couch_id
                                elt["project_name"] = project_cdd.name
                                elt["cycle_id"] = cycle_cdd.couch_id
                                elt["cycle_name"] = cycle_cdd.name
                            administrative_levels_new.append(elt)
                                
                        else:
                            elt["project_id"] = _elt["project_id"]
                            elt["project_name"] = _elt["project_name"]
                            elt["cycle_id"] = _elt["cycle_id"]
                            elt["cycle_name"] = _elt["cycle_name"]
                            # elt = _elt
                        # if not exists_id_in_a_dict_by_project_and_cycle(_administrative_levels, elt.get('id'), elt.get('project_id'), elt.get('cycle_id')):
                    _administrative_levels.append(elt)


        for ad in administrative_levels_old:
            if ad.get('id') and not exists_id_in_a_dict_by_project_and_cycle(_administrative_levels, ad.get('id'), ad.get('project_id'), ad.get('cycle_id')):
                administrative_levels_remove.append(ad)

        #Assign ADL
        for adl in administrative_levels_new:
            _assign = AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(administrative_level_id=int(adl['id']), project_id=self.project_mis_id, activated=True).first()
            if (adl.get('id') and str(adl.get('id')).isdigit() and not _assign):
                    try:
                        assign = AssignAdministrativeLevelToFacilitator()
                        assign.administrative_level_id = int(adl['id'])
                        assign.facilitator_id = facilitator.id
                        assign.project_id = self.project_mis_id
                        assign.save(using='mis')
                    except Exception as exc:
                        print(exc)
        #End Assign ADL

        #Unassign ADL
        for adl in administrative_levels_remove:
            assign = AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(administrative_level_id=int(adl['id']), project_id=self.project_mis_id, activated=True).first()
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
            "facilitator_type": data['facilitator_type'],
            "administrative_levels": _administrative_levels,

            "project_id": self.request.session.get('project_couch_id'),
            "project_name": self.request.session.get('project_name'),
            "projects_ids": [
                p.couch_id for p in data['projects'] 
            ] if 'projects' in data and data['projects'] else []
        }

        facilitator.administrative_levels = _administrative_levels
        facilitator.administrative_levels_ids = [int(_adl['id']) for _adl in _administrative_levels]
        facilitator.simple_save()

        nsc = NoSQLClient()
        nsc.update_doc(self.facilitator_db, self.doc['_id'], doc)

        # clear_facilitator_docs_by_administrativelevels_and_save_to_backup_db(
        #     "backup_db_facilitators_docs", self.facilitator_db_name,
        #     [d.get('id') for d in administrative_levels_new if d.get('is_headquarters_village')]
        # ) #Copy backup db docs (for villages added that removed on facilitator before) to facilitator db and clear docs on backup

        # clear_facilitator_docs_by_administrativelevels_and_save_to_backup_db(
        #     self.facilitator_db_name, "backup_db_facilitators_docs",
        #     [d.get('id') for d in administrative_levels_remove if d.get('is_headquarters_village')]
        # ) #Copy facilitator db docs (for villages removed) to backup db and clear docs on backup db

        process_adls = [d.get('id') for d in administrative_levels_new if d.get('is_headquarters_village')]
        if process_adls:
            process_add_or_remove_adl = ProcessAddOrRemoveADL(
                name = f"backup_db_facilitators_docs_{self.facilitator_db_name}",
                move_from = "backup_db_facilitators_docs",
                move_to = self.facilitator_db_name,
                administrative_levels = process_adls,
                query_action = "update"
            )
            process_add_or_remove_adl.save()

        process_adls = [d.get('id') for d in administrative_levels_remove if d.get('is_headquarters_village')]
        if process_adls:
            process_add_or_remove_adl = ProcessAddOrRemoveADL(
                name = f"{self.facilitator_db_name}_backup_db_facilitators_docs",
                move_from = self.facilitator_db_name,
                move_to = "backup_db_facilitators_docs",
                administrative_levels = process_adls,
                query_action = "update"
            )
            process_add_or_remove_adl.save()


        sync_geographicalunits_with_cvd_on_facilittor(
            self.request.session.get('project_id'),
            facilitator.develop_mode, facilitator.training_mode, self.facilitator_db_name
        ) #Rebuild Unit and CVD infos on facilitator doc

        if not administrative_levels_new:
            administrative_levels_new.append({
                "is_headquarters_village": True,
                "id": "0"
            })
        # sync_tasks(
        #     self.request.session.get('project_id'),
        #     facilitator.develop_mode, facilitator.training_mode, self.facilitator_db_name,
        #     administrativelevel_ids=[d.get('id') for d in administrative_levels_new if d.get('is_headquarters_village')]
        # ) #Sync the tasks for the new villages

        try:
            user = User.objects.get(email=facilitator_email)
            user.password = facilitator.password
            user.username = facilitator.username
            user.last_name = facilitator.name.split(' ')[0]
            user.first_name = ' '.join(facilitator.name.split(' ')[1:])
            user.is_active = facilitator.active
            user.save()
        except:
            pass
        
        
        if 'projects' in data and data['projects']:
            for p in data['projects']:
                p.facilitators.add(facilitator)
                p.save()
    
        return redirect('dashboard:facilitators:list')

class FacilitatorDetailForListView(FacilitatorMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'facilitators/facilitator_detail_for_list.html'
    context_object_name = 'facilitator_detail_for_list'

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
        
    def get_results(self):
        administrative_level_id = self.request.GET.get('administrative_level')
        selector = {
            "type": "task",
        }
        
        if self.request.session.get('project_couch_id'):
            selector['project_id'] = self.request.session.get('project_couch_id')
        if self.request.session.get('cycle_couch_id'):
            selector['cycle_id'] = self.request.session.get('cycle_couch_id')

        if administrative_level_id:
            selector["administrative_level_id"] = administrative_level_id

        # return self.facilitator_db.get_query_result(selector)
        results = self.facilitator_db.get_query_result(selector, limit=1000000)[:]
        
        nsc = NoSQLClient()
        for k_db_name, v in self.no_sql_dbs_names_with_village_ids.items():
            if not administrative_level_id:
                selector["administrative_level_id"] = {"$in": v['ids']}
            _db = nsc.get_db(k_db_name)
            results += _db.get_query_result(selector, limit=1000000)[:]
        return results

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
        context['adminLevelId'] = self.request.GET.get('administrative_level')
        context['facilitator_id'] = self.kwargs.get('id')
        context['village_name'] = self.request.GET.get('villageName')
        context['village_id'] = self.request.GET.get('villageId')

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
                            else:
                                if _.get("completed"):
                                    dict_administrative_levels_with_infos['villages'][village.get('name')] = {
                                        'total_tasks_completed': 1,
                                        'total_tasks_uncompleted': 0
                                    }

                                else:
                                    dict_administrative_levels_with_infos['villages'][village.get('name')] = {
                                        'total_tasks_completed': 0,
                                        'total_tasks_uncompleted': 1

                                    }
                                dict_administrative_levels_with_infos.get('villages').get(village.get('name'))[
                                    'total_tasks'] = 1
                                dict_administrative_levels_with_infos.get('villages').get(village.get('name'))[
                                    'phase_name'] = _.get('phase_name')

                            self.set_progress_data(
                                dict_administrative_levels_with_infos,
                                village.get('name'),
                                _.get("phase_name"),
                                _.get("completed")
                            )

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
                            dict_administrative_levels_with_infos.get('villages').get(village.get('name'))['villageId'] = village.get("id")


                            # if (_.get('completed') is False and _.get('planned_date')
                            #         and (
                            #                 self.request.GET.get('villageName') == ''
                            #                 or self.request.GET.get('villageName') is None
                            #                 or village.get('name') == self.request.GET.get('villageName')
                            #         )
                            # ):
                            #     date = datetime.strptime(_.get('planned_date').split(' ')[0], '%Y-%m-%d')
                            #     hour =  datetime.strptime(_.get('planned_date'), '%Y-%m-%d %H:%M:%S')

                            #     if dict_administrative_levels_with_infos.get('upcomingEvents').get(date) is not None:
                            #         if dict_administrative_levels_with_infos.get('upcomingEvents').get(
                            #                 date).get(hour) is not None:
                            #             dict_administrative_levels_with_infos.get('upcomingEvents')[date][hour].append(

                            #                         {
                            #                             "village": village.get('name'),
                            #                             "name": _.get('name'),
                            #                             "phase_name": _.get('phase_name'),
                            #                             "percentage_tasks_completed": dict_administrative_levels_with_infos.get('villages').get(
                            #                                 village.get('name'))[
                            #                                 'percentage_tasks_completed']
                            #                                     }

                            #                 )
                            #         else:
                            #             dict_administrative_levels_with_infos.get('upcomingEvents')[date][hour] = [
                            #                 {
                            #                     "village": village.get('name'),
                            #                     "name": _.get('name'),
                            #                     "phase_name": _.get('phase_name'),
                            #                     "percentage_tasks_completed": dict_administrative_levels_with_infos.get('villages').get(
                            #                         village.get('name'))[
                            #                         'percentage_tasks_completed']
                            #                     }
                            #             ]
                            #     else:
                            #         dict_administrative_levels_with_infos.get('upcomingEvents')[date] = {}
                            #         dict_administrative_levels_with_infos.get('upcomingEvents')[date][hour] = [
                            #             {
                            #                 "village": village.get('name'),
                            #                 "name": _.get('name'),
                            #                 "phase_name": _.get('phase_name'),
                            #                 "percentage_tasks_completed": dict_administrative_levels_with_infos.get('villages').get(
                            #                     village.get('name'))[
                            #                     'percentage_tasks_completed']
                            #             }
                            #         ]

        
        today = datetime.today()
        current_monday_date_object = today - timedelta(days=today.weekday())
        week_dates = [(current_monday_date_object + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
        planned_date_list = [datetime.strptime(d, '%Y-%m-%d').date() for d in week_dates]

        activities = ActivityPlanning.objects.filter(
            Q(facilitator__no_sql_db_name=self.facilitator_db_name) & 
            Q(planned_date__in=planned_date_list) & 
            (
                Q(validated=None) | Q(validated=True, completed=None)
            )
        )
        if context['village_id'] and str(context['village_id']).isdigit():
            query = Q()
            query |= Q(administrative_level_ids__contains=[int(context['village_id'])])
            activities = activities.filter(query)

        if activities.exists():
            for activity in activities:
                date = activity.planned_datetime_start
                hour =  activity.planned_datetime_start
                color_index = self.get_color_status_number(activity)

                if dict_administrative_levels_with_infos.get('upcomingEvents').get(date) is not None:
                    if dict_administrative_levels_with_infos.get('upcomingEvents').get(
                            date).get(hour) is not None:
                        dict_administrative_levels_with_infos.get('upcomingEvents')[date][hour].append(

                                    {
                                        "village": ", ".join([adm['name'] for adm in activity.administrative_levels]) if activity.administrative_levels else None,
                                        "name": activity.name,
                                        "color": VALIDATION_PROCESS_COLORS[color_index],
                                        "text_color": "white" if color_index in [5, 6] else "black",
                                        "phase_name": None,
                                        "percentage_tasks_completed": None
                                                }

                            )
                    else:
                        dict_administrative_levels_with_infos.get('upcomingEvents')[date][hour] = [
                            {
                                "village": ", ".join([adm['name'] for adm in activity.administrative_levels]) if activity.administrative_levels else None,
                                "name": activity.name,
                                "color": VALIDATION_PROCESS_COLORS[color_index],
                                "text_color": "white" if color_index in [5, 6] else "black",
                                "phase_name": None,
                                "percentage_tasks_completed": None
                                }
                        ]
                else:
                    dict_administrative_levels_with_infos.get('upcomingEvents')[date] = {}
                    dict_administrative_levels_with_infos.get('upcomingEvents')[date][hour] = [
                        {
                            "village": ", ".join([adm['name'] for adm in activity.administrative_levels]) if activity.administrative_levels else None,
                            "name": activity.name,
                            "color": VALIDATION_PROCESS_COLORS[color_index],
                            "text_color": "white" if color_index in [5, 6] else "black",
                            "phase_name": None,
                            "percentage_tasks_completed": None
                        }
                    ]



        context['total_tasks_completed'] = total_tasks_completed
        context['total_tasks_uncompleted'] = total_tasks_uncompleted
        context['total_tasks'] = total_tasks
        context['percentage_tasks_completed'] = ((total_tasks_completed / total_tasks) * 100) if total_tasks else 0
        context['dict_administrative_levels_with_infos'] = dict_administrative_levels_with_infos
        context['facilitator_db_name'] = self.facilitator_db_name


        return context

    def set_progress_data(self, dict_administrative_levels_with_infos, village_name, phase_name, completed):
        dict_administrative_levels_with_infos['villages'][village_name][phase_name] = completed


class TaskCommentListView(FacilitatorMixin, AJAXRequestMixin, LoginRequiredMixin, generic.TemplateView):
    
    template_name = 'facilitators/comments.html'
    context_object_name = 'comments'


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        nsc = NoSQLClient()
        db = self.facilitator_db
        task__id = kwargs['task__id']
        context['colors'] = ['warning', 'mediumslateblue', 'gray', 'mediumpurple', 'plum', 'primary', 'danger']

        query_result = db.get_query_result({
                "type": 'task',
                "_id": task__id
        })[:]

        if not query_result:
            db_name, query_result = get_db_task(self.no_sql_dbs_names_with_village_ids, task__id)
            db = nsc.get_db(db_name)

        if query_result:
            task = db[query_result[0]['_id']]

            comments = task['actions_by'] if 'actions_by' in task else list()
        else:
            comments = []

        context['comments'] = comments

        return context