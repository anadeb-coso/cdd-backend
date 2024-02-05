from django.urls import path

from dashboard.storeapp import views

app_name = 'storeapp'
urlpatterns = [
    path('', views.StoreAppsView.as_view(), name='store_apps'),
    path('<int:pk>', views.StoreAppView.as_view(), name='store_app'),
]
