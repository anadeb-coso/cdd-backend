from django.contrib.auth import views as auth_views
from django.urls import path

from dashboard.authentication.forms import EmailAuthenticationForm
from dashboard.authentication import views, views_supervisors

app_name = 'authentication'
urlpatterns = [
    path('', auth_views.LoginView.as_view(
        authentication_form=EmailAuthenticationForm,
        template_name='authentication/login.html',
        redirect_authenticated_user=True), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('users/', views.UsersListView.as_view(), name='users'),
    path('user-create/', views.CreateUpdateUserFormView.as_view(), name='user_create'),
    path('user/<slug:id>/update/', views.CreateUpdateUserFormView.as_view(), name='user_update'),
    path('user/<slug:id>/delete/', views.DeleteUserFormView.as_view(), name='user_delete'),
    
    path('get-users-diagnostics-view', views.UsersDiagnosticsView.as_view(), name='get_users_diagnostics_view'),
    
    path('supervisors/', views_supervisors.SupervisrosListView.as_view(), name='supervisors'),
    path('supervisors-list/', views_supervisors.SupervisorsListTableView.as_view(), name='supervisors_list'),
]
