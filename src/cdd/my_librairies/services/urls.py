from django.urls import path
from . import views_file

app_name = 'services'

urlpatterns = [
    path('get-excel-sheets-names', views_file.get_excel_sheets_names, name='get_excel_sheets_names'),
]


