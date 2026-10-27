from django.urls import path

from . import views

app_name = "documents"
urlpatterns = [
    path("village-profile/download/", views.village_profile_download, name="village_profile_download"),
    path("village-profile/api/", views.village_profile_api, name="village_profile_api"),
]
