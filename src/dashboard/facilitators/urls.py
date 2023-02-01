from django.urls import path

from dashboard.facilitators import views

app_name = 'facilitators'
urlpatterns = [
    path('', views.FacilitatorListView.as_view(), name='list'),
    path('facilitators-list/', views.FacilitatorListTableView.as_view(), name='facilitators_list'),
    path('create/', views.CreateFacilitatorFormView.as_view(), name='create'),
    path('<int:pk>/update/', views.UpdateFacilitatorView.as_view(), name='update'),
    path('<slug:id>/', views.FacilitatorDetailView.as_view(), name='detail'),
    path('task-list/<slug:id>/', views.FacilitatorTaskListView.as_view(), name='task_list'),
]
