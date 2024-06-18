from django.urls import path

from dashboard.administrative_levels import views, views_adl

app_name = 'administrative_levels'
urlpatterns = [
    path('get-choices-for-next-administrative-level', views.GetChoicesForNextAdministrativeLevelView.as_view(),
         name='get_choices_for_next_administrative_level'),
    path('get-ancestor-administrative-levels', views.GetAncestorAdministrativeLevelsView.as_view(),
         name='get_ancestor_administrative_levels'),
     path('get-choices-for-next-administrative-level-all', views.GetChoicesForNextAdministrativeLevelAllView.as_view(),
         name='get_choices_for_next_administrative_level_all'),
     
     
    path('', views_adl.AdministrativeLevelListView.as_view(), name='list'),
    path('administrative-level-list/', views_adl.AdministrativeLevelListTableView.as_view(), name='administrative_levels_list'),
    path('administrative-level-detail-list/<slug:id>/', views_adl.AdministrativeLevelDetailForListView.as_view(), name='administrative_level_detail_for_list'),
]
