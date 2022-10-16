from django.urls import path

from dashboard.administrative_levels import views

app_name = 'administrative_levels'
urlpatterns = [
    path('get-choices-for-next-administrative-level', views.GetChoicesForNextAdministrativeLevelView.as_view(),
         name='get_choices_for_next_administrative_level'),
    path('get-ancestor-administrative-levels', views.GetAncestorAdministrativeLevelsView.as_view(),
         name='get_ancestor_administrative_levels'),
]
