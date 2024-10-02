from django.urls import path

from . import views

app_name = 'planning'

urlpatterns = [
    path('save-activity/', views.RestSaveActivity.as_view(), name="save_activity"),
    path('save-activity-file/', views.RestSaveActivityFile.as_view(), name="save_activity_file"),
    path('save-activity-comments/', views.RestSaveActivityComment.as_view(), name="save_activity_comment"),
    path('get-activities/', views.RestGetActivityByAttributes.as_view(), name="get_activities_by_attributes"),
    path('get-activity/<int:pk>/', views.RestGetActivityById.as_view(), name="get_activity_by_id"),
    path('delete-activity/', views.DeleteActivityAPIView.as_view(), name="delete_activity"),
    path('delete-activity-file/', views.DeleteActivityFileAPIView.as_view(), name="delete_activity_file"),
]


