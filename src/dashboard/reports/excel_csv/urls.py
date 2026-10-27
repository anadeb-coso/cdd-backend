from django.urls import path

from dashboard.reports.excel_csv import views, excluded_localities

app_name = 'excel_csv'
urlpatterns = [
    path('facilitators-excel-csv/', views.GetFacilitatorExcelCSVRport.as_view(), name="app_excel_csv_facilitators_status"),
    path('facilitator-excel-csv/<str:facilitator_db_name>/', views.GetFacilitatorExcelCSVRport.as_view(), name="app_excel_csv_facilitator_status"),
    path('villages-monograph-excel-csv/', views.GetVillagesMonographExcelCSVRport.as_view(), name="app_excel_csv_villages_monograph"),
    path('villages-monograph-excel-csv/<str:facilitator_db_name>/', views.GetVillagesMonographExcelCSVRport.as_view(), name="app_excel_csv_villages_monograph_by_facilitator"),
    
    path('existences-cvd-excel-csv/', views.GetExistencesCVDExcelCSVRport.as_view(), name="app_excel_csv_existences_cvd"),
    path('villages-priorities-excel-csv/', views.GetVillagesPrioritiesExcelCSVRport.as_view(), name="app_excel_csv_villages_priorities"),


    path('facilitators-status-excel-csv/', views.GetFacilitatorStatusExcelCSVRport.as_view(), name="app_excel_csv_facilitators_status_p"),

    path('facilitators-status-fc-situation-excel-csv/', views.GetFCSituationExcelCSVReport.as_view(), name="app_excel_csv_fc_situation"),
    path('facilitators-status-fc-situation-aggregated-excel-csv/', views.GetFCSituationExcelCSVReport.as_view(source="aggregated"), name="app_excel_csv_fc_situation_aggregated"),

    # Villages / CVD à ne pas prendre en compte dans les situations (/reports/facilitators-status)
    path('excluded-localities/search/', excluded_localities.ExcludedLocalitiesSearchView.as_view(), name="excluded_localities_search"),
    path('excluded-localities/labels/', excluded_localities.ExcludedLocalitiesLabelsView.as_view(), name="excluded_localities_labels"),
    path('excluded-localities/template/', excluded_localities.ExcludedLocalitiesTemplateView.as_view(), name="excluded_localities_template"),
    path('excluded-localities/import/', excluded_localities.ExcludedLocalitiesImportView.as_view(), name="excluded_localities_import"),
]
