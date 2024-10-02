from django.urls import path

from dashboard.planning import views

app_name = 'planning'
urlpatterns = [
    path('', views.PlanningListView.as_view(), name='list'),
    path('planning-list/', views.PlanningListTableView.as_view(), name='planning_list'),
    path('plan-task-detail/<str:no_sql_db_name>/<str:task__id>/<str:task_plan_datetime>/', views.TaskPlanDetailView.as_view(), name='plan_task_detail'),
    path('add-plan-task/', views.AddTaskPlanView.as_view(), name='add_plan_task'),
    path('add-comment-to-plan-task/', views.SaveCommentView.as_view(), name='add_comment_to_plan_task'),
    path('task-plan-comments/<str:no_sql_db_name>/<str:task__id>/<str:task_plan_datetime>/', views.TaskPlanCommentListView.as_view(), name='task_plan_comments'),
    path('validation-plan-task/', views.SaveValidationView.as_view(), name='validation_plan_task'),
    path('add-file-to-plan-task/', views.SaveFileView.as_view(), name='add_file_to_plan_task'),
    path('delete-file-to-plan-task/', views.DeleteFileView.as_view(), name='delete_file_to_plan_task'),
    path('task-plan-files/<str:no_sql_db_name>/<str:task__id>/', views.TaskPlanFilesListView.as_view(), name='task_plan_files'),
    path('save-activity-to-plan-task/', views.SaveActivityView.as_view(), name='save_activity_to_plan_task'),

]
