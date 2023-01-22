from django.urls import path

from dashboard.diagnostics import views

app_name = 'diagnostics'
urlpatterns = [
    path('', views.DashboardDiagnosticsCDDView.as_view(), name='diagnostics'),

    path('get-tasks-diagnostics-view', views.GetTasksDiagnosticsView.as_view(), name='get_tasks_diagnostics_view'),
]
