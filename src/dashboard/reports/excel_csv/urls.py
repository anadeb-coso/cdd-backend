from django.urls import path

from dashboard.reports.excel_csv import views

app_name = 'excel_csv'
urlpatterns = [
    path('facilitators-excel-csv/', views.GetFacilitatorExcelCSVRport.as_view(), name="app_excel_csv_facilitators_status"),
    path('facilitator-excel-csv/<str:facilitator_db_name>/', views.GetFacilitatorExcelCSVRport.as_view(), name="app_excel_csv_facilitator_status"),

]