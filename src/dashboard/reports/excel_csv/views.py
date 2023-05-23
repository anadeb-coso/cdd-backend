from django.views.generic import FormView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from dashboard.mixins import PageMixin
from django.utils.translation import gettext_lazy
from django.contrib import messages
from django.shortcuts import redirect
from django.http import Http404

from cdd.my_librairies import download_file
from .functions import get_facilitator_excel_csv_under_file_excel_or_csv



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
