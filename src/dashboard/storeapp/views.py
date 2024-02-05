from django.utils.translation import gettext_lazy
from django.views import generic
from django.urls import reverse_lazy

from storeapp.models import StoreProject
from dashboard.mixins import PageMixin


class StoreAppsView(PageMixin, generic.ListView):
    model = StoreProject
    queryset = StoreProject.objects.all()
    template_name = 'storeapp/apps.html'
    context_object_name = 'storeapps'
    title = gettext_lazy('Applications')
    active_level1 = 'storeapp'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]


class StoreAppView(PageMixin, generic.DetailView):
    model = StoreProject
    template_name = 'storeapp/app.html'
    title = gettext_lazy('Applications')
    active_level1 = 'storeapp'
    breadcrumb = [
        {
            'url': reverse_lazy('dashboard:storeapp:store_apps'),
            'title': gettext_lazy('Applications')
        },
        {
            'url': '',
            'title': title
        }
    ]