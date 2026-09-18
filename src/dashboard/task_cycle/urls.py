from django.urls import path

from dashboard.task_cycle import views

app_name = 'task_cycle'
urlpatterns = [
    path('', views.TaskCycleHomeView.as_view(), name='home'),
    path('<slug:id>/', views.TaskCycleCVDListView.as_view(), name='cvd_list'),
    path('<slug:id>/form/', views.TaskFormFetchView.as_view(), name='form_fetch'),
    path('<slug:id>/form/save/', views.TaskFormSaveView.as_view(), name='form_save'),
    path('<slug:id>/attachment/upload/', views.TaskAttachmentUploadView.as_view(), name='attachment_upload'),
]
