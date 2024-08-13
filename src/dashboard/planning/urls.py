from django.urls import path

from dashboard.planning import views

app_name = 'planning'
urlpatterns = [
    path('', views.PlanningListView.as_view(), name='list'),
    path('planning-list/', views.PlanningListTableView.as_view(), name='planning_list'),

]
