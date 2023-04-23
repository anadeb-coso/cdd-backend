from django.urls import path
from django.conf.urls import include

app_name = 'reports'
urlpatterns = [
    path('', include('dashboard.reports.pages.urls')),

    path('pdf/', include('dashboard.reports.pdf.urls')),
]