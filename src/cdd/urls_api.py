from django.urls import path
from django.conf.urls import include


app_name = 'api'

urlpatterns = [
    path('storeapp/', include('storeapp.api.urls')),
    path('supportmaterial/', include('supportmaterial.api.urls')),
]
