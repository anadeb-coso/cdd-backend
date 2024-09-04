from django.urls import path

from dashboard.news import views

app_name = 'news'
urlpatterns = [
    path('', views.NewsListView.as_view(), name='list'),
    path('news-list/', views.NewsListTableView.as_view(), name='news_list'),
    path('<int:pk>/detail/', views.NewsDetailView.as_view(), name='detail'),
]
