from django.urls import path

from cdd import views_super

app_name = 'super'

urlpatterns = [
    path('aggregated_status/', views_super.RequestSaveAggregatedStatusView.as_view(), name='aggregated_status'),
]
