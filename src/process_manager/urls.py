from django.urls import path

from process_manager import views_rest

app_name = 'process_manager'

urlpatterns = [
    path('save-form-datas/', views_rest.SaveFormDatas.as_view(), name='save_form_datas'),
    path('save-geolocation-form-datas/', views_rest.SaveGeolocationFormDatas.as_view(), name='save_geolocation_form_datas'),
    path('get-facilitator-projects', views_rest.FacilitatorProjectListView.as_view(), name='facilitator_project'),
    path('get-facilitator-no-sql-dbs-names', views_rest.FacilitatorNOSQLDBListView.as_view(), name='facilitator_no-sql_dbs-names'),
]
