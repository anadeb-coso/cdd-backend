from django.urls import path

from . import views

app_name = "commands_runner"
urlpatterns = [
    path("", views.CommandsView.as_view(), name="index"),
    path("start/", views.StartView.as_view(), name="start"),
    path("status/", views.StatusView.as_view(), name="status"),
    path("<int:pk>/cancel/", views.CancelView.as_view(), name="cancel"),
    path("couch-dbs/", views.CouchDbsView.as_view(), name="couch_dbs"),
    path("cantons/", views.CantonsView.as_view(), name="cantons"),
]
