from django.urls import path
from django.conf.urls import include

from . import views_api_send_mail

app_name = 'api'

urlpatterns = [
    path('storeapp/', include('storeapp.api.urls')),
    path('supportmaterial/', include('supportmaterial.api.urls')),
    path('news/', include('news.api.urls')),
    path('administrative-levels/', include('administrativelevels.urls')),
    path('process_manager/', include('process_manager.urls')),
    path('planning/', include('planning.api.urls')),
    path('', include('usermanager.api.urls')),
    
    path('send-mail/', views_api_send_mail.RestSendMail.as_view(), name="send_mail"),
]
