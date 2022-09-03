from django.urls import path

from authentication import views

app_name = 'authentication'

urlpatterns = [
    path('obtain-auth-credentials/', views.AuthenticateAPIView.as_view(), name='obtain_auth_credentials'),
]
