from django.urls import path
from django.conf.urls import include

app_name = 'api'

urlpatterns = [
    path('facilitators/', include('authentication.api.facilitators.urls')),
]
