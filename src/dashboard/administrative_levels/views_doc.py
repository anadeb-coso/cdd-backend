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




class AttachmentListView(PageMixin, LoginRequiredMixin, generic.TemplateView):
    template_name = "administrative_levels/documents/attachments.html"
    context_object_name = "attachments"
    title = gettext_lazy("Gallery")
    active_level1 = 'documents'
    paginate_by = 10
    no_sql_db_name = None
    administrative_level = None
    canton = None

    def post(self, request, *args, **kwargs):
        url = reverse("dashboard:administrative_levels:documents")
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
            type='Canton'
        )

        # context["phases"] = Phase.objects.all()
        # if "administrative_level" in self.request.GET and self.request.GET[
        #     "administrative_level"
        # ] not in ["", None]:
        #     context["phases"] = context["phases"]
            # .filter(
            #     village__id=self.request.GET["administrative_level"]
            # )

        # context["activities"] = Activity.objects.all()
        # if "phase" in self.request.GET and self.request.GET["phase"] not in ["", None]:
        #     context["activities"] = context["activities"].filter(
        #         phase__id=self.request.GET["phase"]
        #     )

        # context["tasks"] = Task.objects.all()
        # if "activities" in self.request.GET and self.request.GET["activities"] not in [
        #     "",
        #     None,
        # ]:
        #     context["tasks"] = context["tasks"].filter(
        #         activity__id=self.request.GET["activities"]
        #     )

        query_params: dict = self.request.GET

        context["query_strings"] = self.get_query_strings_context()
        context["query_strings_raw"] = query_params.copy()

        # form = AttachmentFilterForm()

        # paginator: Paginator = self.__build_db_filter()

        # context["no_results"] = paginator.count == 0
        # context["current_language"] = translation.get_language()
        # page_number = query_params.get("page", 1)
        # context["attachments"] = paginator.get_page(page_number)
        context["attachments"] = self.__build_db_filter()
        # context["form"] = form
        context['administrative_level_id'] = self.administrative_level_id
        context['canton'] = self.canton
        
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
                            id__in=[int(value)], type="Canton"
                        ).values_list("name", flat=True)
                    )
                # if key == "phase":
                #     resp["Phases"] = ", ".join(
                #         Phase.objects.filter(id__in=[int(value)]).values_list(
                #             "name", flat=True
                #         )
                #     )
                # if key == "activities":
                #     resp["Activities"] = ", ".join(
                #         Activity.objects.filter(id__in=[int(value)]).values_list(
                #             "name", flat=True
                #         )
                #     )
                # if key == "tasks":
                #     resp["Tasks"] = ", ".join(
                #         Task.objects.filter(id__in=[int(value)]).values_list(
                #             "name", flat=True
                #         )
                #     )
                # if key == "types":
                #     resp["Types"] = [value]
                
                if key == "types_doc":
                    resp["Types_doc"] = [value]

        return resp

    def get_queryset(self):
        
        project_mis = mis_objects_call.filter_objects(MisProject, name=self.request.session.get('project_name'))
        project_mis_id = project_mis.first().id if project_mis.count() >= 1 else 1

        queryset = []
        nsc = NoSQLClient()
        selector = {
            "type": "task"
        }
        # if "administrative_level" in self.request.GET and self.request.GET[
        #     "administrative_level"
        # ] not in ["", None]:
        administrative_level_id = self.request.GET.get('administrative_level')
        
        no_sql_db_names = []
        if not administrative_level_id:
            administrative_level_id = "1973"
        self.administrative_level_id = administrative_level_id
        self.canton = mis_objects_call.get_object(
            administrativelevels_models.AdministrativeLevel,
            id=int(administrative_level_id)
        )
        liste_villages = get_cascade_villages_by_administrative_level_id(administrative_level_id)
        assign_facilitators = mis_objects_call.filter_objects(AssignAdministrativeLevelToFacilitator,
            administrative_level_id__in=[int(v['administrative_id']) for v in liste_villages],
            project_id=project_mis_id
        )
        no_sql_db_names = [
            f.no_sql_db_name for f in Facilitator.objects.filter(
                id__in=[a.facilitator_id for a in assign_facilitators]
            )
        ]
        
        selector["administrative_level_id"] = {
            "$in": [v['administrative_id'] for v in liste_villages]
        }
        selector["sql_id"] = {
            "$in": [45, 47]
        }
        
        object_list = []
        for no_sql_db_name in no_sql_db_names:
            facilitator_db = nsc.get_db(no_sql_db_name)
            _object_list = facilitator_db.get_query_result(selector)
            if _object_list:
                object_list += _object_list[:]
            
        attachments = []
        
        pac_libelle = "Télecharger le document du plan d'actions cantonales finalisé".lower()

        if object_list:
            for _ in object_list:
                headquarters_village = mis_objects_call.get_object(
                    administrativelevels_models.AdministrativeLevel,
                    id=int(_["administrative_level_id"])
                )
                # if 'type' in self.request.GET:
                #     if self.request.GET.get('type') == 'Photo':
                #         attachments += [i for i in (_.get("attachments") if _.get("attachments") else []) if (
                #             i.get("attachment") and i.get("type") and "image" in i.get("type")
                #         )]
                #     elif self.request.GET.get('type') == 'Document':
                #         attachments += [i for i in (_.get("attachments") if _.get("attachments") else []) if (
                #             i.get("attachment") and i.get("type") and "pdf" in str(i['type']).lower() and "word" in str(i['type']).lower() and "excel" in str(i['type']).lower()
                #         )]
                #     else:
                #         attachments += [i for i in (_.get("attachments") if _.get("attachments") else []) if (
                #             i.get("attachment") and i.get("type")
                #         )]
                # else:
                    # attachments += [i for i in (_.get("attachments") if _.get("attachments") else []) if (
                    #     i.get("attachment") and i.get("type") and "image" in i.get("type") and 'photo de la réunion' in str(i.get("name")).lower()
                    # )]
                for i in (_.get("attachments") if _.get("attachments") else []):
                    if (
                        _.get("sql_id") in (45, 47) and
                        i.get("attachment") and "document du plan d'actions" in str(i.get("name")).lower()
                    ):
                        _attachments = [a["name"].lower() for a in attachments]
                        exists_pac_on_list = (pac_libelle == i['name'].lower() and pac_libelle not in [a["name"].lower() for a in attachments])
                        if (
                                pac_libelle != i['name'].lower() or 
                                exists_pac_on_list
                            ):
                            i.update({
                                "headquarters_village": _["administrative_level_name"],
                                "headquarters_village_id": _["administrative_level_id"],
                                "villages_names": "" if headquarters_village.cvd.get_villages().count() <= 1 else headquarters_village.cvd.get_names(),
                                "canton": self.canton.name,
                                "no_sql_db_name": Facilitator.objects.get(
                                        id=mis_objects_call.filter_objects(AssignAdministrativeLevelToFacilitator,
                                            administrative_level_id=int(_["administrative_level_id"]),
                                            project_id=project_mis_id
                                        ).last().facilitator_id
                                    ).no_sql_db_name
                            })

                            # if exists_pac_on_list:
                            #     attachments.insert(0, i)
                            # else:
                            #     attachments.append(i)
                            attachments.append(i)
                            
        return sorted(attachments,  key=lambda obj: (str(obj["name"])+str(obj["headquarters_village"])))