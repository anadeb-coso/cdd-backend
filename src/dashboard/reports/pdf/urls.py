from django.urls import path

from dashboard.reports.pdf import views

app_name = 'pdf'
urlpatterns = [
    path('facilitators-status/', views.GeneratePDF.as_view(), name="app_pdf_facilitators_status"),
    path('facilitator-status/<str:facilitator_db_name>/', views.GeneratePDF.as_view(), name="app_pdf_facilitator_status"),

]
