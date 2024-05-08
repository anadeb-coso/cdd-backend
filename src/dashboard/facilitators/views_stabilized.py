from django.contrib.auth.hashers import make_password
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import redirect
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
from .functions import (
    get_cvds, get_cvd_name_by_village_id, is_village_principal, single_task_by_cvd,
    clear_facilitator_docs_by_administrativelevels_and_save_to_backup_db)
from administrativelevels import models as administrativelevels_models
from assignments.models import AssignAdministrativeLevelToFacilitator
from dashboard.administrative_levels.functions import get_administrative_levels_under_json, get_cascade_villages_by_administrative_level_id
from cdd.functions import datetime_complet_str, exists_id_in_a_dict
from cdd.call_objects_from_other_db import mis_objects_call
from authentication.functions import get_assign_adl_by_facilitatr


class FacilitatorStabilizedListView(PageMixin, LoginRequiredMixin, generic.ListView):
    model = Facilitator
    queryset = Facilitator.objects.all()
    template_name = 'facilitators/stabilized/list.html'
    context_object_name = 'facilitators_stabilized'
    title = gettext_lazy('Facilitators Stabilized')
    active_level1 = 'facilitators'
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

        # context['is_training'] = bool(self.request.GET.get('training', '0') != '0')
        # context['is_develop'] = bool(self.request.GET.get('develop', '0') != '0')

        return context


# class FacilitatorStabilizedMixin:
#     doc = None
#     obj = None
#     facilitator_db = None
#     facilitator_db_name = None
#     cvds = None

#     def dispatch(self, request, *args, **kwargs):
#         nsc = NoSQLClient()
#         try:
#             self.facilitator_db_name = kwargs['id']
#             self.facilitator_db = nsc.get_db(self.facilitator_db_name)
#             query_result = self.facilitator_db.get_query_result({"type": 'facilitator'})[:]
#             self.doc = self.facilitator_db[query_result[0]['_id']]
#             self.obj = get_object_or_404(Facilitator, no_sql_db_name=kwargs['id'])
#             self.cvds = get_cvds(self.doc)
#         except Exception:
#             raise Http404
#         return super().dispatch(request, *args, **kwargs)



class FacilitatorStabilizedListTableView(LoginRequiredMixin, generic.ListView):
    template_name = 'facilitators/stabilized/facilitator_list.html'
    context_object_name = 'facilitators_stabilized'

    def get_results(self):
        id_region = self.request.GET.get('id_region')
        id_prefecture = self.request.GET.get('id_prefecture')
        id_commune = self.request.GET.get('id_commune')
        id_canton = self.request.GET.get('id_canton')
        id_village = self.request.GET.get('id_village')
        type_field = self.request.GET.get('type_field')
        _id = 0
        
        nsc = NoSQLClient()
        eadls = nsc.get_db('eadls')
        facilitators_stabilized = []
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
                
            
            if type(_id) is not list:
                liste_villages = []
                liste_villages = get_cascade_villages_by_administrative_level_id(_id)
                facilitators_stabilized = eadls.get_view_result('administrative_regions', 'elements_in_list', keys=[v['administrative_id'] for v in liste_villages])
                if facilitators_stabilized:
                    facilitators_stabilized = [elt['value'] for elt in facilitators_stabilized[:]]
                
            else:
                facilitators_stabilized = eadls.get_query_result({
                    "type": 'adl',
                    "representative.email": {"$in": [obj.email for obj in Facilitator.objects.filter(develop_mode=False, training_mode=False)]}
                })[:]
        else:
            facilitators_stabilized = eadls.get_query_result({
                "type": 'adl',
                "representative.email": {"$in": [obj.email for obj in Facilitator.objects.filter(develop_mode=False, training_mode=False)]}
            })[:]

        return facilitators_stabilized

    def get_queryset(self):
        return self.get_results()
    