from django.urls import path

from dashboard.reports.pdf import views, views_status, views_status_global

app_name = 'pdf'
urlpatterns = [
    path('facilitators-status/', views.GeneratePDF.as_view(), name="app_pdf_facilitators_status"),
    path('facilitator-status/<str:facilitator_db_name>/', views.GeneratePDF.as_view(), name="app_pdf_facilitator_status"),

    
    path('facilitators-status-month/', views_status.GeneratePDF.as_view(), name="app_pdf_facilitators_status_month"),
    path('facilitators-status-global-month/', views_status_global.GeneratePDF.as_view(), name="app_pdf_facilitators_status_global_month"),

]
