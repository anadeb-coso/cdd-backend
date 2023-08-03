from django.urls import path

from process_manager import views_rest

app_name = 'process_manager'

urlpatterns = [
    path('save-form-datas/', views_rest.SaveFormDatas.as_view(), name='save_form_datas'),
]
