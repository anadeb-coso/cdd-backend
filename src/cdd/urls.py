"""cdd URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls import include
from django.contrib import admin
from django.urls import path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

handler400 = 'dashboard.authentication.views.handler400'
handler403 = 'dashboard.authentication.views.handler403'
handler404 = 'dashboard.authentication.views.handler404'
handler500 = 'dashboard.authentication.views.handler500'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('attachments/', include('attachments.urls')),
    path('i18n/', include('django.conf.urls.i18n')),
    path('', include('dashboard.urls')),
]

schema_view = get_schema_view(
    openapi.Info(
        title="GRM API Documentation",
        default_version='v1',
        description="Test Documentation",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

if settings.DEBUG:
    urlpatterns += [
        path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    ]