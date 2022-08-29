from django.urls import path

from attachments import views

app_name = 'attachments'
urlpatterns = [
    path('<str:id>/<str:name>', views.GetAttachmentAPIView.as_view(), name='get-attachment'),
    path('upload-to-task', views.UploadTaskAttachmentAPIView.as_view(), name='upload-task-attachment'),
    path('upload-to-issue', views.UploadIssueAttachmentAPIView.as_view(), name='upload-issue-attachment'),
]