from django.urls import path
from django.conf.urls import include

from authentication.api.first_login import RestFirstLoginPassword
from authentication.api.password_service import RestChangePasswordAllPlatforms, RestPersonProfile
from authentication.api.platform_token import (
    RestCheckPlatformToken, RestPlatformToken, RestRenewPlatformToken, RestRevokePlatformToken,
)

app_name = 'api'

urlpatterns = [
    path('facilitators/', include('authentication.api.facilitators.urls')),
    path('first-login-password/', RestFirstLoginPassword.as_view(), name='first_login_password'),
    # Profile pages of the SIG and the MGP: password change for all platforms, DCC part of the profile
    path('change-password/', RestChangePasswordAllPlatforms.as_view(), name='change_password_all_platforms'),
    path('person-profile/', RestPersonProfile.as_view(), name='person_profile'),
    # jeton de session du mobile, valable sur le DCC, le SIG et le MGP (authentication/platform_tokens.py)
    path('token/', RestPlatformToken.as_view(), name='platform_token'),
    path('token/renew/', RestRenewPlatformToken.as_view(), name='platform_token_renew'),
    path('token/revoke/', RestRevokePlatformToken.as_view(), name='platform_token_revoke'),
    path('token/check/', RestCheckPlatformToken.as_view(), name='platform_token_check'),
]
