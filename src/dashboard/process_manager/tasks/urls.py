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
    path('task/<slug:id>/delete/', views.DeleteTaskFormView.as_view(), name='task_delete'),

    path('task/<slug:id>/form-builder/', views.TaskFormBuilderView.as_view(), name='task_form_builder'),
    path('task/<slug:id>/form-builder/save/', views.TaskFormBuilderSaveView.as_view(), name='task_form_builder_save'),
    path('task/<slug:id>/form-builder/export/', views.TaskFormXlsExportView.as_view(), name='task_form_builder_export'),
    path('task/<slug:id>/form-builder/import/', views.TaskFormXlsImportView.as_view(), name='task_form_builder_import'),
    path('task/<slug:id>/form-builder/choices-export/', views.TaskFormChoicesExportView.as_view(), name='task_form_builder_choices_export'),
    path('task/<slug:id>/form-builder/choices-import/', views.TaskFormChoicesImportView.as_view(), name='task_form_builder_choices_import'),
    path('task/<slug:id>/form-builder/datasources/', views.TaskFormDataSourcesView.as_view(), name='task_form_builder_datasources'),
    path('task/<slug:id>/form-builder/other-tasks/', views.TaskFormOtherTasksView.as_view(), name='task_form_builder_other_tasks'),
    path('task/<slug:id>/form-builder/task-fields/<slug:other_id>/', views.TaskFormTaskFieldsView.as_view(), name='task_form_builder_task_fields'),
    path('task/<slug:id>/form-builder/datasource-preview/', views.TaskFormDataSourcePreviewView.as_view(), name='task_form_builder_datasource_preview'),
    path('task/<slug:id>/form-builder/dataset-sheet/', views.TaskFormDatasetSheetView.as_view(), name='task_form_builder_dataset_sheet'),
    path('task/<slug:id>/form-builder/sync/', views.TaskFormSyncView.as_view(), name='task_form_builder_sync'),
]
