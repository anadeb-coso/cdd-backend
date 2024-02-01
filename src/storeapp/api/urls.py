from django.urls import path

from . import views

app_name = 'storeapp'

urlpatterns = [
    path('get-store-projects/', views.RestGetStoreProjects.as_view(), name="get_store_projects"),
    path('get-store-project-by-package/<str:package>/', views.RestGetStoreProjectByPackage.as_view(), name="get_store_project_by_package")
    
]


