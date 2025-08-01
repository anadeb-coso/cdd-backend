from django.views.generic import FormView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from dashboard.mixins import PageMixin
from django.utils.translation import gettext_lazy
from django.contrib import messages
from django.shortcuts import redirect
from django.http import Http404, HttpResponse

from dashboard.reports.pages.forms import ReportsFacilitatorsStatusForm
from authentication.models import Facilitator
from dashboard.facilitators.forms import FilterFacilitatorFormMultiChoices
from cdd.my_librairies import download_file, convert_file_to_dict
from .functions import get_global_statistic_under_file_excel_or_csv, save_csv_datas_in_db
from authentication.permissions import AdminPermissionRequiredMixin
from .functions_reports import priorities_pav_pac_situation, priorities_situation
from dashboard.reports.excel_csv.functions_cdd_datas import all_cdd_datas
from process_manager.models import Task
from cdd.utils import timeout


class StatisticView(PageMixin, LoginRequiredMixin, TemplateView):
    
    template_name = 'statistics/statistic.html'
    context_object_name = 'statistic'
    title = gettext_lazy('statistic')
    active_level1 = 'statistics'
    # form_class = FilterFacilitatorFormMultiChoices
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    # def render_to_response(self, context, **response_kwargs):
    #     """
    #     Return a response, using the `response_class` for this view, with a
    #     template rendered with the given context.
    #     Pass response_kwargs to the constructor of the response class.
    #     """
    #     response_kwargs.setdefault('content_type', self.content_type)
    #     return self.response_class(
    #         request=self.request,
    #         template=self.get_template_names(),
    #         context=context,
    #         using=self.template_engine,
    #         **response_kwargs
    #     )
    
    # def get_context_data(self, **kwargs):
    #     context = super().get_context_data(**kwargs)
    #     context['breadcrumb'] = False
    #     context['is_training'] = bool(self.request.GET.get('training', '0') != '0')
    #     context['is_develop'] = bool(self.request.GET.get('develop', '0') != '0')
    #     context['form_f'] = ReportsFacilitatorsStatusForm(Facilitator.objects.filter(develop_mode=context['is_develop'], training_mode=context['is_training'], projects__in=[self.request.session.get('project_id')]))

    #     return context



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

    # @timeout(timeout_sec=600)
    # def dispatch(self, request, *args, **kwargs):
    #     return super().dispatch(request, *args, **kwargs)

    def _get_ids_list(self, elt: str):
        if type(elt) is str:
            return [_elt for _elt in elt.split(',') if _elt and _elt not in (None, 'None', 'null', 'undefined')]
        return []

    def get(self, request, *args, **kwargs):
        facilitator_dbs_name = self._get_ids_list(request.GET.get('facilitator_db_name'))

        ids_region = self._get_ids_list(request.GET.get('id_region'))
        ids_prefecture = self._get_ids_list(request.GET.get('id_prefecture'))
        ids_commune = self._get_ids_list(request.GET.get('id_commune'))
        ids_canton = self._get_ids_list(request.GET.get('id_canton'))
        ids_village = self._get_ids_list(request.GET.get('id_village'))
        ids_administrative_level = self._get_ids_list(request.GET.get('administrative_level_id'))
        ids_administrative_level = list(set(ids_administrative_level+ids_region+ids_prefecture+ids_commune+ids_canton+ids_village))
        
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
        # try:
        file_path = get_global_statistic_under_file_excel_or_csv(
            facilitator_dbs_name=facilitator_dbs_name,
            params={
                "type": _type, "ids_administrativelevel": ids_administrative_level, 
                "session_project_id": self.request.session.get('project_id'), 
                "session_project_name": self.request.session.get('project_name'), 
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
                self.request.session.get('project_couch_id'),
                self.request.session.get('cycle_couch_id'),
                convert_file_to_dict.conversion_file_xlsx_to_dict(request.FILES.get('file'))
            )
            
            return download_file.download(request, file_path, "text/plain")
        

        raise Http404
    


class PrioritiesPAVPACSituationCSVView(PageMixin, LoginRequiredMixin, TemplateView):
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

    # def _get_ids_list(self, elt: str):
    #     if type(elt) is str:
    #         return [_elt for _elt in elt.split(',') if _elt]
    #     return []
    def _get_ids_list(self, elt: str):
        if type(elt) is str:
            return [_elt for _elt in elt.split(',') if _elt and _elt not in (None, 'None', 'null', 'undefined')]
        return []

    def get(self, request, *args, **kwargs):
        facilitator_dbs_name = self._get_ids_list(request.GET.get('facilitator_db_name'))

        ids_region = self._get_ids_list(request.GET.get('id_region'))
        ids_prefecture = self._get_ids_list(request.GET.get('id_prefecture'))
        ids_commune = self._get_ids_list(request.GET.get('id_commune'))
        ids_canton = self._get_ids_list(request.GET.get('id_canton'))
        ids_village = self._get_ids_list(request.GET.get('id_village'))
        ids_administrative_level = self._get_ids_list(request.GET.get('administrative_level_id'))
        ids_administrative_level = list(set(ids_administrative_level+ids_region+ids_prefecture+ids_commune+ids_canton+ids_village))
        
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
            file_path = priorities_pav_pac_situation(
                facilitator_dbs_name=facilitator_dbs_name,
                params={
                    "type": _type, "ids_administrativelevel": ids_administrative_level, 
                    "session_project_id": self.request.session.get('project_id'), 
                    "session_project_name": self.request.session.get('project_name'), 
                    "session_cycle_couch_id": self.request.session.get('cycle_couch_id')
                    }
            )
        except Exception as exc:
            print(exc)
            messages.info(request, gettext_lazy("An error has occurred..."))

        if not file_path:
            return redirect('dashboard:facilitators:list')
        else:
            # return download_file.download(
            #     request, 
            #     file_path,
            #     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            # )
            
            return HttpResponse(file_path)
        

class PrioritiesSituationCSVView(PageMixin, LoginRequiredMixin, TemplateView):
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

    # def _get_ids_list(self, elt: str):
    #     if type(elt) is str:
    #         return [_elt for _elt in elt.split(',') if _elt]
    #     return []
    def _get_ids_list(self, elt: str):
        if type(elt) is str:
            return [_elt for _elt in elt.split(',') if _elt and _elt not in (None, 'None', 'null', 'undefined')]
        return []

    def get(self, request, *args, **kwargs):
        facilitator_dbs_name = self._get_ids_list(request.GET.get('facilitator_db_name'))

        ids_region = self._get_ids_list(request.GET.get('id_region'))
        ids_prefecture = self._get_ids_list(request.GET.get('id_prefecture'))
        ids_commune = self._get_ids_list(request.GET.get('id_commune'))
        ids_canton = self._get_ids_list(request.GET.get('id_canton'))
        ids_village = self._get_ids_list(request.GET.get('id_village'))
        ids_administrative_level = self._get_ids_list(request.GET.get('administrative_level_id'))
        ids_administrative_level = list(set(ids_administrative_level+ids_region+ids_prefecture+ids_commune+ids_canton+ids_village))
        
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
            file_path = priorities_situation(
                facilitator_dbs_name=facilitator_dbs_name,
                params={
                    "type": _type, "ids_administrativelevel": ids_administrative_level, 
                    "session_project_id": self.request.session.get('project_id'), 
                    "session_project_name": self.request.session.get('project_name'), 
                    "session_cycle_couch_id": self.request.session.get('cycle_couch_id')
                }
            )

        except Exception as exc:
            messages.info(request, gettext_lazy("An error has occurred..."))

        if not file_path:
            return redirect('dashboard:facilitators:list')
        else:
            # return download_file.download(
            #     request, 
            #     file_path,
            #     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            # )
            return HttpResponse(file_path)
        


class CddDatasCSVView(PageMixin, LoginRequiredMixin, TemplateView):
    """Class to download all datas under excel file"""

    template_name = 'reports/pages/cdd_datas.html'
    context_object_name = 'Download'
    title = gettext_lazy("Download")
    active_level1 = 'reports'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def _get_ids_list(self, elt: str):
        if type(elt) is str:
            return [_elt for _elt in elt.split(',') if _elt and _elt not in (None, 'None', 'null', 'undefined')]
        return []

    def get(self, request, *args, **kwargs):
        facilitator_dbs_name = self._get_ids_list(request.GET.get('facilitator_db_name'))
        
        ids_region = self._get_ids_list(request.GET.get('id_region'))
        ids_prefecture = self._get_ids_list(request.GET.get('id_prefecture'))
        ids_commune = self._get_ids_list(request.GET.get('id_commune'))
        ids_canton = self._get_ids_list(request.GET.get('id_canton'))
        ids_village = self._get_ids_list(request.GET.get('id_village'))
        ids_administrative_level = self._get_ids_list(request.GET.get('administrative_level_id'))
        ids_administrative_level = list(set(ids_administrative_level+ids_region+ids_prefecture+ids_commune+ids_canton+ids_village))

        include_form_fields = request.GET.get('include_form_fields') in (1,"1")
        include_history = request.GET.get('include_history') in (1,"1")
        include_all_id_and_adl = request.GET.get('include_all_id_and_adl') in (1,"1")
        
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


        ids_phase = self._get_ids_list(request.GET.get('id_phase'))
        ids_activity = self._get_ids_list(request.GET.get('id_activity'))
        ids_task = self._get_ids_list(request.GET.get('id_task'))

        if ids_task:
            ids_task = [_[0] for _ in list(Task.objects.filter(id__in=ids_task).values_list('id'))]
        elif ids_activity:
            ids_task = [_[0] for _ in list(Task.objects.filter(activity_id__in=ids_activity).values_list('id'))]
        elif ids_phase:
            ids_task = [_[0] for _ in list(Task.objects.filter(phase_id__in=ids_phase).values_list('id'))]
        
        
        file_path = ""
        try:
            file_path = all_cdd_datas(
                facilitator_dbs_name=facilitator_dbs_name,
                params={
                    "type": _type, "ids_administrativelevel": ids_administrative_level, 
                    "session_project_id": self.request.session.get('project_id'), 
                    "session_project_couch_id": self.request.session.get('project_couch_id'), 
                    "session_project_name": self.request.session.get('project_name'), 
                    "session_cycle_couch_id": self.request.session.get('cycle_couch_id'), 
                    "include_form_fields": include_form_fields,
                    "include_history": include_history,
                    "include_all_id_and_adl": include_all_id_and_adl,
                    "ids_task": ids_task
                }
            )

        except Exception as exc:
            messages.info(request, gettext_lazy("An error has occurred..."))
        
        
        if not file_path:
            return redirect('dashboard:facilitators:list')
        else:
            return HttpResponse(file_path)