from django.urls import path

from dashboard.planning import facilitator_followup_map

app_name = 'map'
urlpatterns = [
    path('', facilitator_followup_map.PlanningListView.as_view(), name='list'),
    path('planning-map-list/', facilitator_followup_map.PlanningListTableView.as_view(), name='planning_map_list'),
]
