from django.views.generic import FormView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from dashboard.mixins import PageMixin
from django.utils.translation import gettext_lazy
from django.contrib import messages
from django.shortcuts import redirect
from django.http import Http404

from cdd.my_librairies import download_file
from .functions import get_facilitator_excel_csv_under_file_excel_or_csv, get_villages_monograph_under_file_excel_or_csv



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
            params={"type": _type, "id_administrativelevel": _id}
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