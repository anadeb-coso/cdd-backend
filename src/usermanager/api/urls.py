from django.urls import path

from usermanager.api import views_change_password


app_name = 'user_manager'

urlpatterns = [
    path('change-password/', views_change_password.RestChangePassword.as_view(), name='change_password'),
    path('user-manager-email-notification/', views_change_password.RestSendChangePasswordCode.as_view(), name='user_manager_email_notification'),

]