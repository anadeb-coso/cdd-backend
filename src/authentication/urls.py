from django.urls import path

from authentication import views

app_name = 'authentication'

urlpatterns = [
    path('obtain-auth-credentials/', views.AuthenticateAPIView.as_view(), name='obtain_auth_credentials'),
    path('logout/', views.LogoutAPIView.as_view(), name='logout'),
    path('get-csrf-token/', views.get_csrf_token, name='get_csrf_token')
]
