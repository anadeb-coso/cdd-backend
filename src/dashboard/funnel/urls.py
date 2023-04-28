from django.urls import path

from dashboard.funnel import views

app_name = 'funnel'
urlpatterns = [
    path('', views.FunnelsView.as_view(), name='funnels'),
    path('get-funnels-view/', views.GetFunnelsView.as_view(), name='get_funnels_view'),
]
