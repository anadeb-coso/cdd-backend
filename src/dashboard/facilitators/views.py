from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import generic

from authentication.models import Facilitator
from dashboard.mixins import PageMixin
from no_sql_client import NoSQLClient


class FacilitatorListView(PageMixin, LoginRequiredMixin, generic.ListView):
    model = Facilitator
    queryset = Facilitator.objects.all()
    template_name = 'facilitators/list.html'
    context_object_name = 'facilitators'
    title = _('Facilitators')
    active_level1 = 'facilitators'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def get_queryset(self):
        return super().get_queryset()


class FacilitatorMixin(object):
    doc = None
    obj = None

    def dispatch(self, request, *args, **kwargs):
        nsc = NoSQLClient()
        try:
            facilitator_db = nsc.get_db(kwargs['id'])  # id = facilitator_db_name
            query_result = facilitator_db.get_query_result({"type": 'facilitator'})[:]
            self.doc = facilitator_db[query_result[0]['_id']]
            self.obj = get_object_or_404(Facilitator, no_sql_db_name=kwargs['id'])
        except Exception:
            raise Http404
        return super().dispatch(request, *args, **kwargs)


class FacilitatorDetailView(FacilitatorMixin, PageMixin, LoginRequiredMixin, generic.DetailView):
    template_name = 'facilitators/profile.html'
    context_object_name = 'facilitator_doc'
    title = _('Facilitator Profile')
    active_level1 = 'facilitators'
    model = Facilitator
    breadcrumb = [
        {
            'url': reverse_lazy('dashboard:facilitators:list'),
            'title': _('Facilitators')
        },
        {
            'url': '',
            'title': title
        }
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['facilitator'] = self.obj
        return context

    def get_object(self, queryset=None):
        return self.doc
