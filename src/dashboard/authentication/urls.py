from django.contrib.auth import views as auth_views
from django.urls import path

from dashboard.authentication.forms import EmailAuthenticationForm
from dashboard.authentication import views

app_name = 'authentication'
urlpatterns = [
    path('', auth_views.LoginView.as_view(
        authentication_form=EmailAuthenticationForm,
        template_name='authentication/login.html',
        redirect_authenticated_user=True), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('users/', views.UsersListView.as_view(), name='users'),
    path('user-create/', views.CreateUserFormView.as_view(), name='user_create')
]
