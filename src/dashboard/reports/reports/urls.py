from django.urls import path

from dashboard.reports.reports import views
from dashboard.reports.reports import views_committees

app_name = 'reports'
urlpatterns = [
    path('', views.ReportsIndexView.as_view(), name='index'),
    
    path('committees/', views_committees.CommitteesListView.as_view(), name='committees'),
    path('committees-list/', views_committees.CommitteesListTableView.as_view(), name='committees_list'),
    
]
