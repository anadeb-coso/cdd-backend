from django.urls import path

from . import views

app_name = 'supportmaterial'

urlpatterns = [
    path('get-subjects/', views.RestGetSubjects.as_view(), name="get_subjects"),
    
]


