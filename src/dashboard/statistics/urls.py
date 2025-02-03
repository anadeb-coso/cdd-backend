from django.urls import path

from . import views

app_name = 'statistics'
urlpatterns = [
    path('', views.StatisticView.as_view(), name='statistic'),

    path('statistics/', views.GetGlobalStatistic.as_view(), name="app_excel_statistics"),
    # path('statistics/<str:facilitator_db_name>/', views.GetGlobalStatistic.as_view(), name="app_excel_statistics_by_facilitator"),
    path('upload/', views.UploadCSVView.as_view(), name="app_excel_statistics_upload"),
    
    path('reports/prorities-pav-pac/', views.PrioritiesPAVPACSituationCSVView.as_view(), name="app_excel_reports_prorities_pav_pac_situation"),
    path('reports/prorities/', views.PrioritiesSituationCSVView.as_view(), name="app_excel_reports_prorities_situation"),
    path('reports/cdd-datas/', views.CddDatasCSVView.as_view(), name="app_excel_reports_cdd_dtas"),
]
