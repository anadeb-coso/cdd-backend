from django.urls import path

from dashboard.diagnostics import views, views_global, views_administrativelevels, views_village_docs

app_name = 'diagnostics'
urlpatterns = [
    path('', views.DashboardDiagnosticsCDDView.as_view(), name='diagnostics'),
    path('global', views_global.DashboardDiagnosticsCDDView.as_view(), name='diagnostics_global'),

    path('get-tasks-diagnostics-view', views.GetTasksDiagnosticsView.as_view(), name='get_tasks_diagnostics_view'),
    path('get-tasks-diagnostics-view-global', views_global.GetTasksDiagnosticsView.as_view(), name='get_tasks_diagnostics_view_global'),
    path('get-diagnostics-stats-view', views.DiagnosticsStatsTableView.as_view(), name='get_diagnostics_tasks_view'),
    
    path('adl-tasks', views_administrativelevels.DashboardDiagnosticsADLView.as_view(), name='tasks_adl_diagnostics'),
    path('get-diagnostics-cantons-view', views_administrativelevels.DiagnosticsCantonsView.as_view(), name='get_diagnostics_cantons_view'),
    # Documents de villages : phases/activités/tâches sans village d'affectation, villages sièges sans documents
    path('village-docs/orphans/', views_village_docs.VillageDocsOrphansView.as_view(), name='village_docs_orphans'),
    path('village-docs/missing/', views_village_docs.VillageDocsMissingView.as_view(), name='village_docs_missing'),
    path('village-docs/data/', views_village_docs.VillageDocsDataView.as_view(), name='village_docs_data'),
    path('village-docs/comment/', views_village_docs.VillageDocsCommentView.as_view(), name='village_docs_comment'),
    path('village-docs/operation/', views_village_docs.VillageDocsOperationStartView.as_view(), name='village_docs_operation'),
    path('village-docs/operation/status/', views_village_docs.VillageDocsOperationStatusView.as_view(), name='village_docs_operation_status'),
    path('get-diagnostics-villages-view', views_administrativelevels.CantonDetailForListView.as_view(), name='get_diagnostics_villages_view'),
]
