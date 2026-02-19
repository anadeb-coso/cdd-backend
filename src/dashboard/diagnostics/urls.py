from django.urls import path

from dashboard.diagnostics import views, views_global, views_administrativelevels

app_name = 'diagnostics'
urlpatterns = [
    path('', views.DashboardDiagnosticsCDDView.as_view(), name='diagnostics'),
    path('global', views_global.DashboardDiagnosticsCDDView.as_view(), name='diagnostics_global'),

    path('get-tasks-diagnostics-view', views.GetTasksDiagnosticsView.as_view(), name='get_tasks_diagnostics_view'),
    path('get-tasks-diagnostics-view-global', views_global.GetTasksDiagnosticsView.as_view(), name='get_tasks_diagnostics_view_global'),
    path('get-diagnostics-stats-view', views.DiagnosticsStatsTableView.as_view(), name='get_diagnostics_tasks_view'),
    
    path('adl-tasks', views_administrativelevels.DashboardDiagnosticsADLView.as_view(), name='tasks_adl_diagnostics'),
    path('get-diagnostics-cantons-view', views_administrativelevels.DiagnosticsCantonsView.as_view(), name='get_diagnostics_cantons_view'),
    path('get-diagnostics-villages-view', views_administrativelevels.CantonDetailForListView.as_view(), name='get_diagnostics_villages_view'),
]
