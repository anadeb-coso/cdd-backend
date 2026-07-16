from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from dashboard.mixins import PageMixin
from django.utils.translation import gettext_lazy as _


class ReportsIndexView(PageMixin, LoginRequiredMixin, TemplateView):
    
    template_name = 'reports/reports/index.html'
    title = _('reports')
    active_level1 = 'reports'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context['breadcrumb'] = False

        return context