from django.views.generic import FormView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from dashboard.mixins import PageMixin
from django.utils.translation import gettext_lazy
from django.contrib import messages
from django.shortcuts import redirect
from django.http import Http404, HttpResponse

from cdd.my_librairies import download_file
from .functions import (
    get_facilitator_excel_csv_under_file_excel_or_csv, 
    get_villages_monograph_under_file_excel_or_csv,
    get_existences_cvd_under_file_excel_or_csv,
    get_village_priorities_under_file_excel_or_csv
)
from .facilitators_status import get_facilitator_status_excel_csv_under_file_excel_or_csv
from .fc_situation import build_fc_situation_workbook



class GetFacilitatorExcelCSVRport(PageMixin, LoginRequiredMixin, TemplateView):
    """Class to download Facilitator under excel file"""

    template_name = None
    context_object_name = 'Download'
    title = gettext_lazy("Download")
    active_level1 = 'reports'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def get(self, request, facilitator_db_name=None, *args, **kwargs):

        file_path = ""
        # try:
        file_path = get_facilitator_excel_csv_under_file_excel_or_csv(
            request,
            facilitator_db_name=facilitator_db_name
        )

        # except Exception as exc:
        #     messages.info(request, gettext_lazy("An error has occurred..."))

        if not file_path:
            return redirect('dashboard:facilitators:list')
        else:
            return download_file.download(
                request, 
                file_path,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )


class GetVillagesMonographExcelCSVRport(PageMixin, LoginRequiredMixin, TemplateView):
    """Class to download Facilitator under excel file"""

    template_name = None
    context_object_name = 'Download'
    title = gettext_lazy("Download")
    active_level1 = 'reports'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def get(self, request, facilitator_db_name=None, *args, **kwargs):

        id_region = request.GET.get('id_region')
        id_prefecture = request.GET.get('id_prefecture')
        id_commune = request.GET.get('id_commune')
        id_canton = request.GET.get('id_canton')
        id_village = request.GET.get('id_village')
        type_field = request.GET.get('type_field')
        
        _id = 0
        _type = "All"
        if (id_region or id_prefecture or id_commune or id_canton or id_village) and type_field:
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
                

        file_path = ""
        # try:
        file_path = get_villages_monograph_under_file_excel_or_csv(
            facilitator_db_name=facilitator_db_name,
            params={
                "type": _type, "id_administrativelevel": _id, 
                "session_project_id": self.request.session.get('project_id'),
                "session_cycle_couch_id": self.request.session.get('cycle_couch_id')
            }
        )

        # except Exception as exc:
        #     messages.info(request, gettext_lazy("An error has occurred..."))

        if not file_path:
            return redirect('dashboard:facilitators:list')
        else:
            return download_file.download(
                request, 
                file_path,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            
            

class GetExistencesCVDExcelCSVRport(PageMixin, LoginRequiredMixin, TemplateView):
    """Class to download Facilitator under excel file"""

    template_name = None
    context_object_name = 'Download'
    title = gettext_lazy("Download")
    active_level1 = 'reports'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def get(self, request, facilitator_db_name=None, *args, **kwargs):

        id_region = request.GET.get('id_region')
        id_prefecture = request.GET.get('id_prefecture')
        id_commune = request.GET.get('id_commune')
        id_canton = request.GET.get('id_canton')
        id_village = request.GET.get('id_village')
        type_field = request.GET.get('type_field')
        
        _id = 0
        _type = "All"
        if (id_region or id_prefecture or id_commune or id_canton or id_village) and type_field:
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
                

        file_path = ""
        # try:
        file_path = get_existences_cvd_under_file_excel_or_csv(
            facilitator_db_name=facilitator_db_name,
            params={
                "type": _type, "id_administrativelevel": _id, 
                "session_project_id": self.request.session.get('project_id'),
                "session_cycle_couch_id": self.request.session.get('cycle_couch_id')
            }
        )

        # except Exception as exc:
        #     messages.info(request, gettext_lazy("An error has occurred..."))

        if not file_path:
            return redirect('dashboard:facilitators:list')
        else:
            return download_file.download(
                request, 
                file_path,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            
            
class GetVillagesPrioritiesExcelCSVRport(PageMixin, LoginRequiredMixin, TemplateView):
    """Class to download Facilitator under excel file"""

    template_name = None
    context_object_name = 'Download'
    title = gettext_lazy("Download")
    active_level1 = 'reports'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def get(self, request, facilitator_db_name=None, *args, **kwargs):

        id_region = request.GET.get('id_region')
        id_prefecture = request.GET.get('id_prefecture')
        id_commune = request.GET.get('id_commune')
        id_canton = request.GET.get('id_canton')
        id_village = request.GET.get('id_village')
        type_field = request.GET.get('type_field')
        
        _id = 0
        _type = "All"
        if (id_region or id_prefecture or id_commune or id_canton or id_village) and type_field:
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
                

        file_path = ""
        # try:
        file_path = get_village_priorities_under_file_excel_or_csv(
            facilitator_db_name=facilitator_db_name,
            params={
                "type": _type, "id_administrativelevel": _id, 
                "session_project_id": self.request.session.get('project_id'),
                "session_cycle_couch_id": self.request.session.get('cycle_couch_id')
            }
        )

        # except Exception as exc:
        #     messages.info(request, gettext_lazy("An error has occurred..."))

        if not file_path:
            return redirect('dashboard:facilitators:list')
        else:
            return download_file.download(
                request, 
                file_path,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        


class GetFCSituationExcelCSVReport(PageMixin, LoginRequiredMixin, TemplateView):
    """Classeur « FC_SITUATION » (situation globale par FC + feuilles CVD) lu directement depuis CouchDB.

    Rendu sous /reports/facilitators-status (onglet Priorities). Le périmètre de tâches est
    paramétrable via id_phase / id_activity / id_task (une ou plusieurs valeurs).
    """

    template_name = None
    context_object_name = 'Download'
    title = gettext_lazy("Download")
    active_level1 = 'reports'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def _get_ids_list(self, elt):
        if isinstance(elt, str):
            return [_elt for _elt in elt.split(',') if _elt and _elt not in (None, 'None', 'null', 'undefined')]
        return []

    def get(self, request, facilitator_db_name=None, *args, **kwargs):
        ids_region = self._get_ids_list(request.GET.get('id_region'))
        ids_prefecture = self._get_ids_list(request.GET.get('id_prefecture'))
        ids_commune = self._get_ids_list(request.GET.get('id_commune'))
        ids_canton = self._get_ids_list(request.GET.get('id_canton'))
        ids_village = self._get_ids_list(request.GET.get('id_village'))
        ids_administrative_level = self._get_ids_list(request.GET.get('administrative_level_id'))
        ids_administrative_level = list(set(
            ids_administrative_level + ids_region + ids_prefecture + ids_commune + ids_canton + ids_village
        ))

        facilitator_dbs_name = self._get_ids_list(request.GET.get('facilitator_db_name'))
        if facilitator_db_name:
            facilitator_dbs_name.append(facilitator_db_name)

        project_names = self._get_ids_list(request.GET.get('projects')) or None
        three_priorities_rule = request.GET.get('three_priorities_rule')
        if three_priorities_rule in ('1', 'true', 'True'):
            three_priorities_rule = True
        elif three_priorities_rule in ('0', 'false', 'False'):
            three_priorities_rule = False
        else:
            three_priorities_rule = None

        file_path = ""
        try:
            file_path = build_fc_situation_workbook({
                "session_project_id": request.session.get('project_id'),
                "session_project_name": request.session.get('project_name'),
                "session_project_couch_id": request.session.get('project_couch_id'),
                "session_cycle_couch_id": request.session.get('cycle_couch_id'),
                "cycle_id": request.session.get('cycle_id'),
                "type": request.GET.get('type_field') or "All",
                "ids_administrativelevel": ids_administrative_level,
                "facilitator_dbs_name": facilitator_dbs_name,
                "ids_phase": self._get_ids_list(request.GET.get('id_phase')),
                "ids_activity": self._get_ids_list(request.GET.get('id_activity')),
                "ids_task": self._get_ids_list(request.GET.get('id_task')),
                "cdd_project_names": project_names,
                "three_priorities_rule": three_priorities_rule,
            })
        except Exception as exc:
            print(exc)
            messages.info(request, gettext_lazy("An error has occurred..."))

        if not file_path:
            return redirect('dashboard:facilitators:list')
        # Le fichier vient d'être écrit par ce même process : on le renvoie directement
        # dans cette réponse (une seule requête HTTP) au lieu de faire suivre son chemin
        # au client pour un second aller-retour vers download_file_view. Ça élimine le
        # risque qu'une instance différente (derrière l'ALB) serve la seconde requête
        # sans avoir le fichier sur son disque local.
        return download_file.download(
            request,
            file_path,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


class GetFacilitatorStatusExcelCSVRport(PageMixin, LoginRequiredMixin, TemplateView):
    """Class to download Facilitator under excel file"""

    template_name = None
    context_object_name = 'Download'
    title = gettext_lazy("Download")
    active_level1 = 'reports'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def get(self, request, facilitator_db_name=None, *args, **kwargs):

        file_path = ""
        # try:
        file_path = get_facilitator_status_excel_csv_under_file_excel_or_csv(
            request,
            facilitator_db_name=facilitator_db_name
        )

        # except Exception as exc:
        #     messages.info(request, gettext_lazy("An error has occurred..."))

        if not file_path:
            return redirect('dashboard:facilitators:list')
        else:
            return download_file.download(
                request, 
                file_path,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )