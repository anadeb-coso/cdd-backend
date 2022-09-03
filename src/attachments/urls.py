from django.urls import path

from attachments import views

app_name = 'attachments'
urlpatterns = [
    path('upload-to-issue', views.UploadIssueAttachmentAPIView.as_view(), name='upload-issue-attachment'),
]
