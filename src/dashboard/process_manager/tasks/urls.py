from django.urls import path

from dashboard.process_manager.tasks import views


app_name = 'tasks'
urlpatterns = [
    path('phases/', views.PhaseListView.as_view(), name='phase_list'),
    path('phase-create/', views.CreateUpdatePhaseFormView.as_view(), name='phase_create'),
    path('phase/<slug:id>/update/', views.CreateUpdatePhaseFormView.as_view(), name='phase_update'),
    path('phase/<slug:id>/delete/', views.DeletePhaseFormView.as_view(), name='phase_delete'),
    
    path('activities/', views.ActivityListView.as_view(), name='activity_list'),
    path('activity-create/', views.CreateUpdateActivityFormView.as_view(), name='activity_create'),
    path('activity/<slug:id>/update/', views.CreateUpdateActivityFormView.as_view(), name='activity_update'),
    path('activity/<slug:id>/delete/', views.DeleteActivityFormView.as_view(), name='activity_delete'),
    
    path('tasks/', views.TaskListView.as_view(), name='task_list'),
    path('task-create/', views.CreateUpdateTaskFormView.as_view(), name='task_create'),
    path('task/<slug:id>/update/', views.CreateUpdateTaskFormView.as_view(), name='task_update'),
    path('task/<slug:id>/delete/', views.DeleteTaskFormView.as_view(), name='task_delete')
]
