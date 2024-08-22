from django.urls import path

from administrativelevels import views

app_name = 'administrativelevel'

urlpatterns = [
    path('filter/', views.RestAdministrativeLevelFilter.as_view(), name='list_filter'),
    path('filter-by-administrative-region/', views.RestAdministrativeLevelFilterByADL.as_view(), name='list_filter_by_administrative_region'),
]
