from django.http import HttpResponse
from django.views.generic import View
from django.template.loader import get_template
from datetime import datetime
from django.conf import settings
from django.shortcuts import redirect

from no_sql_client import NoSQLClient
from cdd.my_librairies.pdf.loader import render_to_pdf
from dashboard.administrative_levels.functions import get_cascade_villages_by_administrative_level_id
from authentication.models import Facilitator
from dashboard.facilitators.functions import get_cvds
from cdd.functions import datetime_complet_str
from django.forms.models import model_to_dict

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
from dashboard.facilitators.functions import (
    get_cvds, single_task_by_cvd, get_db_task,
    get_search_for_stabilized_facilitator_dbs
)
from cdd.constants import VALIDATION_PROCESS_COLORS
from administrativelevels import models as administrativelevels_models
from assignments.models import AssignAdministrativeLevelToFacilitator
from dashboard.administrative_levels.functions import get_cascade_villages_by_administrative_level_id
from cdd.functions import datetime_complet_str, exists_id_in_a_dict, exists_id_in_a_dict_by_project_and_cycle, is_datetime_in_past_or_now
from cdd.call_objects_from_other_db import mis_objects_call
from authentication.functions import get_assign_adl_by_facilitatr, get_assigns_adl_by_facilitatrs
from dashboard.tasks import sync_celery_tasks_re

from dashboard.facilitators.repository.facilitator_criteria import FacilitatorCriteria
from dashboard.facilitators.repository.db_facilitator_repository import FacilitatorRepository
from subprojects.models import Project as MisProject
from cdd.views_manage_url_parse import redirect_user_to_login, redirect_to_an_url
from cdd.my_librairies.functions import get_datas_dict
from process_manager.models import AggregatedStatus, Task, Cycle, Project, AggregatedStatusFacilitator
from planning.models import Activity as ActivityPlanning




class Generate(View):
    def generate(self, request, facilitator_db_name=None):
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

        
        projects = Project.objects.get(id=(self.request.session.get('project_id') or 4)).build_the_tree_structure()

        projects_mis = mis_objects_call.filter_objects(MisProject, name__in=[p.name for p in projects])
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
                    project_id__in=[p.id for p in projects_mis],
                    activated=True
                ).values_list('facilitator_id', flat=True)
                criteria = FacilitatorCriteria(
                    id__in=list(set([int(facilitator_id) for facilitator_id in assign_facilitators_id_list])),
                    develop_mode=False,
                    training_mode=False,
                    active=(False if type_facilitator=='inactive' else True),
                    projects__id=[p.id for p in projects],
                    facilitator_type=type_of_facilitator_list
                )

            else:
                assign_facilitators_id_list = AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(
                    project_id__in=[p.id for p in projects_mis],
                    activated=True
                ).values_list('facilitator_id', flat=True)
                criteria = FacilitatorCriteria(
                    id__in=list(set([int(facilitator_id) for facilitator_id in assign_facilitators_id_list])),
                    develop_mode=False,
                    training_mode=False,
                    active=(False if type_facilitator=='inactive' else True),
                    projects__id=[p.id for p in projects],
                    facilitator_type=type_of_facilitator_list
                )

        else:
            assign_facilitators_id_list = AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(
                project_id__in=[p.id for p in projects_mis],
                activated=True
            ).values_list('facilitator_id', flat=True)
            is_training = bool(self.request.GET.get('is_training', "False") == "True")
            is_develop = bool(self.request.GET.get('is_develop', "False") == "True")
            criteria = FacilitatorCriteria(
                id__in=list(set([int(facilitator_id) for facilitator_id in assign_facilitators_id_list])),
                develop_mode=is_develop,
                training_mode=is_training,
                active=(False if type_facilitator=='inactive' else True),
                projects__id=[p.id for p in projects],
                facilitator_type=type_of_facilitator_list
            )

        _facilitators = {}

        # Récupérer tous les facilitateurs en une seule requête
        facilitators = FacilitatorRepository().find_by_criteria(criteria=criteria)

        
        agg_s_fs = AggregatedStatusFacilitator.objects.filter(facilitator__in=facilitators)

        for f in facilitators.order_by('name'):
            _facilitators[f.email] = {'facilitator': model_to_dict(f), 'projects': {}}
            for p in projects:
                _f = agg_s_fs.filter(facilitator_id=f.id, project_id=p.id).first()
                if _f:
                    dict_f = model_to_dict(f)
                    dict_f['total_tasks_current_project'] = _f.total_tasks_current_project
                    dict_f['total_tasks_completed_current_project'] = _f.total_tasks_completed_current_project
                    dict_f['last_activity_current_project'] = _f.last_activity_current_project
                    dict_f['total_tasks_stabilized'] = _f.total_tasks_stabilized
                    dict_f['total_tasks_completed_stabilized'] = _f.total_tasks_completed_stabilized
                    dict_f['last_activity_stabilized'] = _f.last_activity_stabilized
                    dict_f['total_tasks'] = _f.total_tasks
                    dict_f['total_tasks_completed'] = _f.total_tasks_completed
                    dict_f['last_activity'] = _f.last_activity

                    dict_f['total_tasks_validated_current_project'] = _f.total_tasks_validated_current_project
                    dict_f['total_tasks_invalidated_current_project'] = _f.total_tasks_invalidated_current_project
                    dict_f['total_tasks_invalidated_review_current_project'] = _f.total_tasks_invalidated_review_current_project
                    dict_f['total_tasks_invalidated_review_completed_current_project'] = _f.total_tasks_invalidated_review_completed_current_project
                    dict_f['total_tasks_invalidated_review_in_pending_current_project'] = _f.total_tasks_invalidated_review_in_pending_current_project
                    dict_f['total_tasks_invalidated_unreview_current_project'] = _f.total_tasks_invalidated_unreview_current_project
                    dict_f['total_tasks_invalidated_unreview_completed_current_project'] = _f.total_tasks_invalidated_unreview_completed_current_project
                    dict_f['total_tasks_invalidated_unreview_in_pending_current_project'] = _f.total_tasks_invalidated_unreview_in_pending_current_project
                    dict_f['total_tasks_waiting_validation_current_project'] = _f.total_tasks_waiting_validation_current_project

                    dict_f['total_tasks_validated_stabilized'] = _f.total_tasks_validated_stabilized
                    dict_f['total_tasks_invalidated_stabilized'] = _f.total_tasks_invalidated_stabilized
                    dict_f['total_tasks_invalidated_review_stabilized'] = _f.total_tasks_invalidated_review_stabilized
                    dict_f['total_tasks_invalidated_review_completed_stabilized'] = _f.total_tasks_invalidated_review_completed_stabilized
                    dict_f['total_tasks_invalidated_review_in_pending_stabilized'] = _f.total_tasks_invalidated_review_in_pending_stabilized
                    dict_f['total_tasks_invalidated_unreview_stabilized'] = _f.total_tasks_invalidated_unreview_stabilized
                    dict_f['total_tasks_invalidated_unreview_completed_stabilized'] = _f.total_tasks_invalidated_unreview_completed_stabilized
                    dict_f['total_tasks_invalidated_unreview_in_pending_stabilized'] = _f.total_tasks_invalidated_unreview_in_pending_stabilized
                    dict_f['total_tasks_waiting_validation_stabilized'] = _f.total_tasks_waiting_validation_stabilized
                    
                    dict_f['total_tasks_validated'] = _f.total_tasks_validated
                    dict_f['total_tasks_invalidated'] = _f.total_tasks_invalidated
                    dict_f['total_tasks_invalidated_review'] = _f.total_tasks_invalidated_review
                    dict_f['total_tasks_invalidated_review_completed'] = _f.total_tasks_invalidated_review_completed
                    dict_f['total_tasks_invalidated_review_in_pending'] = _f.total_tasks_invalidated_review_in_pending
                    dict_f['total_tasks_invalidated_unreview'] = _f.total_tasks_invalidated_unreview
                    dict_f['total_tasks_invalidated_unreview_completed'] = _f.total_tasks_invalidated_unreview_completed
                    dict_f['total_tasks_invalidated_unreview_in_pending'] = _f.total_tasks_invalidated_unreview_in_pending
                    dict_f['total_tasks_waiting_validation'] = _f.total_tasks_waiting_validation
                    
                    dict_f['cvds_number_current_project'] = _f.cvds_number_current_project
                    dict_f['villages_number_current_project'] = _f.villages_number_current_project
                    dict_f['cvds_number_stabilized'] = _f.cvds_number_stabilized
                    dict_f['villages_number_stabilized'] = _f.villages_number_stabilized
                    dict_f['cvds_number'] = _f.cvds_number
                    dict_f['villages_number'] = _f.villages_number

                    dict_f['last_task_done_current_project'] = _f.last_task_done_current_project
                    dict_f['last_task_done_stabilized'] = _f.last_task_done_stabilized
                    dict_f['last_task_done'] = _f.last_task_done
                    dict_f['administrative_level_headquarters_villages_infos'] = _f.administrative_level_headquarters_villages_infos

                    dict_f['percent_current_project'] = float("%.2f" % (((_f.total_tasks_completed_current_project/_f.total_tasks_current_project)*100) if _f.total_tasks_current_project else 0))
                    dict_f['percent_stabilized'] = float("%.2f" % (((_f.total_tasks_completed_stabilized/_f.total_tasks_stabilized)*100) if _f.total_tasks_stabilized else 0))
                    dict_f['percent'] = float("%.2f" % (((_f.total_tasks_completed/_f.total_tasks)*100) if _f.total_tasks else 0))

                    _facilitators[f.email]['projects'][p.name] = dict_f
            
            
            _facilitators[f.email]['facilitator']['total_tasks_completed_current_project'] = 0
            _facilitators[f.email]['facilitator']['total_tasks_completed_stabilized'] = 0
            _facilitators[f.email]['facilitator']['total_tasks_completed'] = 0
            _facilitators[f.email]['facilitator']['total_tasks_current_project'] = 0
            _facilitators[f.email]['facilitator']['total_tasks_stabilized'] = 0
            _facilitators[f.email]['facilitator']['total_tasks'] = 0
            for k_p, v_f in _facilitators[f.email]['projects'].items():
                _facilitators[f.email]['facilitator']['total_tasks_completed_current_project'] += v_f['total_tasks_completed_current_project']
                _facilitators[f.email]['facilitator']['total_tasks_completed_stabilized'] += v_f['total_tasks_completed_stabilized']
                _facilitators[f.email]['facilitator']['total_tasks_completed'] += v_f['total_tasks_completed']
                _facilitators[f.email]['facilitator']['total_tasks_current_project'] += v_f['total_tasks_current_project']
                _facilitators[f.email]['facilitator']['total_tasks_stabilized'] += v_f['total_tasks_stabilized']
                _facilitators[f.email]['facilitator']['total_tasks'] += v_f['total_tasks']

                _facilitators[f.email]['facilitator']['percent_current_project'] = float("%.2f" % (((_facilitators[f.email]['facilitator']['total_tasks_completed_current_project']/_facilitators[f.email]['facilitator']['total_tasks_current_project'])*100) if _facilitators[f.email]['facilitator']['total_tasks_current_project'] else 0))
                _facilitators[f.email]['facilitator']['percent_stabilized'] = float("%.2f" % (((_facilitators[f.email]['facilitator']['total_tasks_completed_stabilized']/_facilitators[f.email]['facilitator']['total_tasks_stabilized'])*100) if _facilitators[f.email]['facilitator']['total_tasks_stabilized'] else 0))
                _facilitators[f.email]['facilitator']['percent'] = float("%.2f" % (((_facilitators[f.email]['facilitator']['total_tasks_completed']/_facilitators[f.email]['facilitator']['total_tasks'])*100) if _facilitators[f.email]['facilitator']['total_tasks'] else 0))

        return {
            'request' : request,
            'DOMAIN_PATH': ("http://" if "127." in request.get_host() else "https://") + (request.get_host()),
            'facilitators': _facilitators,
            'today': datetime.today(),
            'last_update': AggregatedStatus.objects.filter(project_id=(self.request.session.get('project_id') or 4), cycle_id=(self.request.session.get('cycle_id') or 1)).first().updated_date
        }


class GeneratePDF(Generate):
    def get(self, request, facilitator_db_name=None, *args, **kwargs):
        id_in_details = request.GET.get("id_in_details")
        template_page = "reports/pdf/facilitators_details_status.html"
        
        template = get_template(template_page)
        context = Generate.generate(self, request, facilitator_db_name)
       
        html = template.render(context)
        pdf = render_to_pdf(template_page, context)
        if pdf:
            response = HttpResponse(pdf, content_type='application/pdf')
            nom = '{}'.format('report_facilitators' if id_in_details == "0" else (context['facilitators'][0].get("facilitator").get('name') if len(context['facilitators']) == 1 else 'report_facilitator'))
            filename = "%s_%s.pdf" %(nom.replace(" ", "_").replace("/", "_").replace("'", "_"), str(context['last_update'].replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_"))
            content = "inline; filename=%s" %(filename)
            download = request.GET.get("download")
            if download:
                content = "attachment; filename=%s" %(filename)
            response['Content-Disposition'] = content
            return response
        return HttpResponse(html)