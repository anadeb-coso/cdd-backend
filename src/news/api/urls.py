from django.urls import path

from . import views
from process_manager.views_rest import RestGetProjects

app_name = 'news'

urlpatterns = [
    path('save-news/', views.RestSaveNews.as_view(), name="save_news"),
    path('save-news-file/', views.RestSaveNewsFile.as_view(), name="save_news_file"),
    path('get-categories/', views.RestGetCategories.as_view(), name="get_categories"),
    path('get-category/<int:pk>/', views.RestGetCategoryById.as_view(), name="get_category_by_id"),
    path('get-news/', views.RestGetNews.as_view(), name="get_news"),
    path('get-news/<int:pk>/', views.RestGetNewById.as_view(), name="get_new_by_id"),
    path('search-news/', views.RestGetNewsByAttributes.as_view(), name="search_news"),
    path('get-tags/', views.RestGetTags.as_view(), name="get_tags"),
    path('get-news-files/', views.RestGetNewsFiles.as_view(), name="get_news_files"),
    path('search-news-files/', views.RestGetNewsFilesByAttributes.as_view(), name="search_news_files"),
    path('delete-news/', views.DeleteNewsAPIView.as_view(), name="delete_news"),
    path('delete-news-file/', views.DeleteNewsFileAPIView.as_view(), name="delete_news_file"),

    
    path('get-projects/', RestGetProjects.as_view(), name="get_projects"),
    
    path('get-subscriptions-by-user/', views.RestGetSubscriptionsByUser.as_view(), name="get_subscriptions_by_user"),
    path('subscription/', views.SubscriptionAPIView.as_view(), name="subscription"),
    path('delete-subscription/', views.DeleteSubscriptionAPIView.as_view(), name="delete_subscription"),
]


