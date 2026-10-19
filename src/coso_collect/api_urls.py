from django.urls import path

from . import api_views

app_name = 'coso_collect_api'

urlpatterns = [
    path('auth/token/', api_views.token_view, name='token'),
    path('forms/', api_views.forms_view, name='forms'),
    path('forms/<int:pk>/', api_views.form_view, name='form'),
    path('forms/<int:pk>/submissions/', api_views.my_submissions_view, name='my_submissions'),
    path('forms/<int:pk>/submissions/sync/', api_views.sync_view, name='sync'),
    path('attachments/upload/', api_views.upload_view, name='upload'),
    path('attachments/<int:pk>/', api_views.attachment_view, name='attachment'),
]
