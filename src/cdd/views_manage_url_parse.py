from django.shortcuts import resolve_url
from urllib.parse import urlparse
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import ImproperlyConfigured
from django.conf import settings




def redirect_user_to_login(request):
    path = request.build_absolute_uri()
    login_url = settings.LOGIN_URL
    if not login_url:
        raise ImproperlyConfigured(
            "The LOGIN_URL is missing the login_url attribute. Define settings.LOGIN_URL"
        )
    resolved_login_url = resolve_url(str(login_url))
    
    login_scheme, login_netloc = urlparse(resolved_login_url)[:2]
    current_scheme, current_netloc = urlparse(path)[:2]
    if (not login_scheme or login_scheme == current_scheme) and (
        not login_netloc or login_netloc == current_netloc
    ):
        path = request.get_full_path()
    return redirect_to_login(
        path,
        resolved_login_url,
        REDIRECT_FIELD_NAME,
    )


def redirect_to_an_url(request, url):
    path = request.build_absolute_uri()
    if not url:
        raise ImproperlyConfigured(
            "The URL is missing the url argument attribute. Define it"
        )
    resolved_url = resolve_url(str(url))
    
    url_scheme, url_netloc = urlparse(resolved_url)[:2]
    current_scheme, current_netloc = urlparse(path)[:2]
    if (not url_scheme or url_scheme == current_scheme) and (
        not url_netloc or url_netloc == current_netloc
    ):
        path = request.get_full_path()
    return redirect_to_login(
        path,
        resolved_url,
        REDIRECT_FIELD_NAME,
    )