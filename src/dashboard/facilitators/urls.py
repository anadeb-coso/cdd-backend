from django.urls import path

from dashboard.facilitators import views, views_stabilized

app_name = 'facilitators'
urlpatterns = [
    path('', views.FacilitatorListView.as_view(), name='list'),
    path('facilitators-list/', views.FacilitatorListTableView.as_view(), name='facilitators_list'),
    path('facilitators-percent/<slug:id>/', views.FacilitatorsPercentListView.as_view(), name='facilitator_percent'),
    path('facilitators-percent/', views.FacilitatorsPercentView.as_view(), name='facilitators_percent'),
    path('create/', views.CreateFacilitatorFormView.as_view(), name='create'),
    path('<int:pk>/update/', views.UpdateFacilitatorView.as_view(), name='update'),
    path('<slug:id>/detail/', views.FacilitatorDetailView.as_view(), name='detail'),
    path('task-list/<slug:id>/', views.FacilitatorTaskListView.as_view(), name='task_list'),
    path('facilitator-detail-list/<slug:id>/', views.FacilitatorDetailForListView.as_view(), name='facilitator_detail_for_list'),
    
    path('stabilized/', views_stabilized.FacilitatorStabilizedListView.as_view(), name='stabilized_list'),
    path('facilitators-stabilized-list/', views_stabilized.FacilitatorStabilizedListTableView.as_view(), name='facilitators_stabilized_list'),
]
