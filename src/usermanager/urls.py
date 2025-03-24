from django.urls import path

from . import views, views_change_password, views_forget_password


app_name = 'user_manager'

urlpatterns = [
    path('user-manager/', views.user_manager, name='user_manager'),
    path('change-password/', views_change_password.RestChangePassword.as_view(), name='change_password'),
    
    path('reset-password-ask-email/', views_forget_password.reset_password_ask_email, name='reset_password_ask_email'),
    path('reset-password/', views_forget_password.RestResetPassword.as_view(), name='reset_password'),
    path('reset-password-done/', views_forget_password.reset_password_done, name='reset_password_done'),

    path('user-manager-email-notification/', views_change_password.RestSendChangePasswordCode.as_view(), name='user_manager_email_notification'),

]