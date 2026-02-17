from django.urls import path

from dashboard.diagnostics import views, views_global

app_name = 'diagnostics'
urlpatterns = [
    path('', views.DashboardDiagnosticsCDDView.as_view(), name='diagnostics'),
    path('global', views_global.DashboardDiagnosticsCDDView.as_view(), name='diagnostics_global'),

    path('get-tasks-diagnostics-view', views.GetTasksDiagnosticsView.as_view(), name='get_tasks_diagnostics_view'),
    path('get-tasks-diagnostics-view-global', views_global.GetTasksDiagnosticsView.as_view(), name='get_tasks_diagnostics_view_global'),
    path('get-diagnostics-stats-view', views.DiagnosticsStatsTableView.as_view(), name='get_diagnostics_tasks_view'),
]
