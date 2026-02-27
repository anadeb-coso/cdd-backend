from django.urls import path

from process_manager import views_rest, views

app_name = 'process_manager'

urlpatterns = [
    path('save-form-datas/', views_rest.SaveFormDatas.as_view(), name='save_form_datas'),
    path('save-geolocation-form-datas/', views_rest.SaveGeolocationFormDatas.as_view(),
         name='save_geolocation_form_datas'),
    path('get-facilitator-projects', views_rest.FacilitatorProjectListView.as_view(), name='facilitator_project'),
    path(
        'get-facilitator-no-sql-dbs-names',
        views_rest.FacilitatorNOSQLDBListView.as_view(),
        name='facilitator_no-sql_dbs-names'
    ),
    path(
        'assignments/',
        views.AssignmentsAPIView.as_view(),
        name='assignments'
    ),
    path('projects/<int:pk>/tree/', views.ProjectTreeAPIView.as_view(), name='project-tree'),
    path('tasks/<int:pk>/', views.TaskDetailAPIView.as_view(), name='task-detail'),
    path(
        'tasks/<int:pk>/submissions/<int:administrative_level_id>/toggle-completion/',
        views.TaskCompletionToggleAPIView.as_view(),
        name='task-toggle-completion'
    ),
]
