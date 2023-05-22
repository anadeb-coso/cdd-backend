from django.urls import path

from . import views

app_name = 'statistics'
urlpatterns = [
    path('', views.StatisticView.as_view(), name='statistic'),

    path('statistics/', views.GetGlobalStatistic.as_view(), name="app_excel_statistics"),
    path('statistics/<str:facilitator_db_name>/', views.GetGlobalStatistic.as_view(), name="app_excel_statistics_by_facilitator"),
    path('upload/', views.UploadCSVView.as_view(), name="app_excel_statistics_upload"),
]
