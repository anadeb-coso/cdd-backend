from django.urls import path

from dashboard.reports.pages import views

app_name = 'pages'
urlpatterns = [
    path('facilitators-status', views.ReportsFacilitatorsStatusView.as_view(), name='facilitators_status'),
    
]
