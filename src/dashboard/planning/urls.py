from django.urls import path

from dashboard.planning import views

app_name = 'planning'
urlpatterns = [
    path('', views.PlanningListView.as_view(), name='list'),
    path('planning-list/', views.PlanningListTableView.as_view(), name='planning_list'),
    path('plan-task-detail/<str:no_sql_db_name>/<str:task__id>/<str:task_plan_datetime>/', views.TaskPlanDetailView.as_view(), name='plan_task_detail'),
    path('add-comment-to-plan-task/', views.SaveCommentView.as_view(), name='add_comment_to_plan_task'),
    path('task_plan-comments/', views.TaskPlanCommentListView.as_view(), name='task_plan_comments'),

]
