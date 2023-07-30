from django.views.generic import FormView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from dashboard.mixins import PageMixin
from django.utils.translation import gettext_lazy
from django.contrib import messages
from django.shortcuts import redirect
from django.http import Http404

from dashboard.reports.pages.forms import ReportsFacilitatorsStatusForm
from authentication.models import Facilitator
from dashboard.facilitators.forms import FilterFacilitatorFormMultiChoices
from cdd.my_librairies import download_file, convert_file_to_dict
from .functions import get_global_statistic_under_file_excel_or_csv, save_csv_datas_in_db
from authentication.permissions import AdminPermissionRequiredMixin


class StatisticView(PageMixin, LoginRequiredMixin, FormView):
    
    template_name = 'statistics/statistic.html'
    context_object_name = 'statistic'
    title = gettext_lazy('statistic')
    active_level1 = 'statistics'
    form_class = FilterFacilitatorFormMultiChoices
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def render_to_response(self, context, **response_kwargs):
        """
        Return a response, using the `response_class` for this view, with a
        template rendered with the given context.
        Pass response_kwargs to the constructor of the response class.
        """
        response_kwargs.setdefault('content_type', self.content_type)
        return self.response_class(
            request=self.request,
            template=self.get_template_names(),
            context=context,
            using=self.template_engine,
            **response_kwargs
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_training'] = bool(self.request.GET.get('training', '0') != '0')
        context['is_develop'] = bool(self.request.GET.get('develop', '0') != '0')
        context['form_f'] = ReportsFacilitatorsStatusForm(Facilitator.objects.filter(develop_mode=context['is_develop'], training_mode=context['is_training']))

        return context



class GetGlobalStatistic(PageMixin, LoginRequiredMixin, TemplateView):
    """Class to download statistic under excel file"""

    template_name = 'statistics/statistic.html'
    context_object_name = 'Download'
    title = gettext_lazy("Download")
    active_level1 = 'statistics'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def _get_ids_list(self, elt: str):
        if type(elt) is str:
            return [_elt for _elt in elt.split(',') if _elt]
        return []

    def get(self, request, facilitator_db_name=None, *args, **kwargs):

        ids_region = self._get_ids_list(request.GET.get('id_region'))
        ids_prefecture = self._get_ids_list(request.GET.get('id_prefecture'))
        ids_commune = self._get_ids_list(request.GET.get('id_commune'))
        ids_canton = self._get_ids_list(request.GET.get('id_canton'))
        ids_village = self._get_ids_list(request.GET.get('id_village'))
        type_field = request.GET.get('type_field')
        _ids = []
        _type = "All"
        if (ids_region or ids_prefecture or ids_commune or ids_canton or ids_village) and type_field:
            if ids_village:
                _type = "village"
                _ids = ids_village
            elif ids_canton:
                _type = "canton"
                _ids = ids_canton
            elif ids_commune:
                _type = "commune"
                _ids = ids_commune
            elif ids_prefecture:
                _type = "prefecture"
                _ids = ids_prefecture
            elif ids_region:
                _type = "region"
                _ids = ids_region
                
        file_path = ""
        try:
            file_path = get_global_statistic_under_file_excel_or_csv(
                facilitator_db_name=facilitator_db_name,
                params={"type": _type, "ids_administrativelevel": _ids}
            )

        except Exception as exc:
            messages.info(request, gettext_lazy("An error has occurred..."))

        if not file_path:
            return redirect('dashboard:facilitators:list')
        else:
            return download_file.download(
                request, 
                file_path,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )





class UploadCSVView(PageMixin, LoginRequiredMixin, AdminPermissionRequiredMixin, TemplateView):
    """Class to upload and save the administrativelevels"""

    template_name = 'upload.html'
    context_object_name = 'Upload'
    title = gettext_lazy("Upload")
    active_level1 = 'statistics'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def post(self, request, *args, **kwargs):
        _type = request.POST.get('_type')
        if _type == "statistic_file":
            message, file_path = save_csv_datas_in_db(
                convert_file_to_dict.conversion_file_xlsx_to_dict(request.FILES.get('file'))
            )
            
            return download_file.download(request, file_path, "text/plain")
        

        raise Http404