from django.urls import path, include

from dashboard.process_manager import views

app_name = 'process_manager'
urlpatterns = [
    path('select-project/', views.ProjectListView.as_view(), name='list'),
    path('get-choices-for-next-phases-activities-tasks', views.GetChoicesForNextPhaseActivitiesTasksView.as_view(),
         name='get_choices_for_next_phases_activities_tasks'),
    path('get-choices-for-next-phases-activities-tasks-by-id', views.GetChoicesForNextPhaseActivitiesTasksByIdView.as_view(),
         name='get_choices_for_next_phases_activities_tasks_by_id'),
     path('validate_invalidate-task', views.ValidateTaskView.as_view(), name='validate_invalidate_task'),
     path('complete-uncomplete-task', views.CompleteTaskView.as_view(), name='complete_uncomplete_task'),

     
    path('', include('dashboard.process_manager.tasks.urls')),
]
