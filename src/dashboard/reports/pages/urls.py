from django.urls import path

from dashboard.reports.pages import views

app_name = 'pages'
urlpatterns = [
    path('facilitators-status', views.ReportsFacilitatorsStatusView.as_view(), name='facilitators_status'),
    path('facilitators-evolution', views.FacilitatorsEvolutionView.as_view(), name='facilitators_evolution'),
    path('priorites', views.PrioritiesView.as_view(), name='priorites'),
    path('cdd-datas', views.CddDatasView.as_view(), name='cdd_datas'),
    
]
