from django.views.generic import FormView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from dashboard.mixins import PageMixin
from django.utils.translation import gettext_lazy
from django.contrib import messages
from django.shortcuts import redirect

from dashboard.reports.pages.forms import ReportsFacilitatorsStatusForm
from authentication.models import Facilitator
from dashboard.facilitators.forms import FilterFacilitatorForm
from cdd.my_librairies import download_file
from .functions import get_global_statistic_under_file_excel_or_csv



class StatisticView(PageMixin, LoginRequiredMixin, FormView):
    
    template_name = 'statistics/statistic.html'
    context_object_name = 'statistic'
    title = gettext_lazy('statistic')
    active_level1 = 'statistics'
    form_class = FilterFacilitatorForm
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
        file_path = get_global_statistic_under_file_excel_or_csv(
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
    