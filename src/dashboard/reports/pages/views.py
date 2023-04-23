from django.views.generic import FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from dashboard.mixins import PageMixin
from django.utils.translation import gettext_lazy
from .forms import ReportsFacilitatorsStatusForm
from authentication.models import Facilitator
from dashboard.facilitators.forms import FilterFacilitatorForm


class ReportsFacilitatorsStatusView(PageMixin, LoginRequiredMixin, FormView):
    
    template_name = 'reports/pages/facilitators.html'
    context_object_name = 'reports'
    title = gettext_lazy('reports')
    active_level1 = 'reports'
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

