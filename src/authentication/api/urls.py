from django.urls import path
from django.conf.urls import include

from authentication.api.first_login import RestFirstLoginPassword
from authentication.api.platform_token import RestPlatformToken, RestRenewPlatformToken, RestRevokePlatformToken

app_name = 'api'

urlpatterns = [
    path('facilitators/', include('authentication.api.facilitators.urls')),
    path('first-login-password/', RestFirstLoginPassword.as_view(), name='first_login_password'),
    # jeton de session du mobile, valable sur le DCC, le SIG et le MGP (authentication/platform_tokens.py)
    path('token/', RestPlatformToken.as_view(), name='platform_token'),
    path('token/renew/', RestRenewPlatformToken.as_view(), name='platform_token_renew'),
    path('token/revoke/', RestRevokePlatformToken.as_view(), name='platform_token_revoke'),
]
