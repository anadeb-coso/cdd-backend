from django.contrib.auth.mixins import LoginRequiredMixin

from django.utils.translation import gettext_lazy
from django.views import generic
from dashboard.mixins import PageMixin

from authentication.permissions import SuperAdminPermissionRequiredMixin
from dashboard.tasks import sync_celery_tasks_re

class RequestSaveAggregatedStatusView(PageMixin, SuperAdminPermissionRequiredMixin, generic.TemplateView):
    template_name = 'super/aggregated_status.html'
    context_object_name = 'aggregated_status'
    title = gettext_lazy('aggregated_status')
    active_level1 = 'aggregated_status'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        sync_celery_tasks_re()
        
        return context