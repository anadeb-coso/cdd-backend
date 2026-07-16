from django.urls import path
from django.conf.urls import include

from authentication import views

app_name = 'authentication'

urlpatterns = [
    path('obtain-auth-credentials/', views.AuthenticateAPIView.as_view(), name='obtain_auth_credentials'),

    path('get-csrf-token/', views.get_csrf_token, name='get_csrf_token'),

    path('api/', include('authentication.api.urls')),
]
