from django.urls import path

from dashboard.facilitators import views

app_name = 'facilitators'
urlpatterns = [
    path('', views.FacilitatorListView.as_view(), name='list'),
    path('<slug:id>/', views.FacilitatorDetailView.as_view(), name='detail'),
    path('task-list/<slug:id>/', views.FacilitatorTaskListView.as_view(), name='task_list'),
]
