from django.conf.urls import include
from django.urls import path

app_name = 'dashboard'
urlpatterns = [
    path('', include('dashboard.authentication.urls')),
    path('facilitators/', include('dashboard.facilitators.urls')),
    path('administrative-levels/', include('dashboard.administrative_levels.urls')),
    path('diagnostics/', include('dashboard.diagnostics.urls')),
    path('process-manager/', include('dashboard.process_manager.urls')),
    path('reports/', include('dashboard.reports.urls')),
]
