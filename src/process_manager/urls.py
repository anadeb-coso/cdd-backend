from django.urls import path

from process_manager import views_rest

app_name = 'process_manager'

urlpatterns = [
    path('save-form-datas/', views_rest.SaveFormDatas.as_view(), name='save_form_datas'),
    path('save-geolocation-form-datas/', views_rest.SaveGeolocationFormDatas.as_view(), name='save_geolocation_form_datas'),
    path('get-facilitator-projects', views_rest.FacilitatorProjectListView.as_view(), name='facilitator_project'),
    path('get-facilitator-no-sql-dbs-names', views_rest.FacilitatorNOSQLDBListView.as_view(), name='facilitator_no-sql_dbs-names'),
    # Partage des données entre villages sièges (Task.share_mode).
    path('task-share/report-completion/', views_rest.ReportTaskCompletion.as_view(), name='task_share_report_completion'),
    path('task-share/pullable-source/', views_rest.PullableTaskSource.as_view(), name='task_share_pullable_source'),
    path('task-share/pull-from/', views_rest.PullTaskData.as_view(), name='task_share_pull_from'),
]
