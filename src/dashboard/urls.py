from django.conf.urls import include
from django.urls import path

app_name = 'dashboard'
urlpatterns = [
    path('', include('dashboard.authentication.urls')),
    path('administrative-levels/', include('dashboard.facilitators.urls')),
]
