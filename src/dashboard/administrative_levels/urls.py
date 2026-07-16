from django.urls import path

from dashboard.administrative_levels import views, views_adl, views_doc, views_export

app_name = 'administrative_levels'
urlpatterns = [
    path('get-choices-for-next-administrative-level', views.GetChoicesForNextAdministrativeLevelView.as_view(),
         name='get_choices_for_next_administrative_level'),
    path('get-ancestor-administrative-levels', views.GetAncestorAdministrativeLevelsView.as_view(),
         name='get_ancestor_administrative_levels'),
     path('get-choices-for-next-administrative-level-all', views.GetChoicesForNextAdministrativeLevelAllView.as_view(),
         name='get_choices_for_next_administrative_level_all'),
     path('get-choices-for-next-administratives-level-all', views.GetChoicesForNextAdministrativeLevelsAllView.as_view(),
         name='get_choices_for_next_administrative_levels_all'),
     path('get-choices-villages-all', views.GetChoicesVillagesAllView.as_view(),
         name='get_choices_villages_all'),
     
     
    path('', views_adl.AdministrativeLevelListView.as_view(), name='list'),
    path('administrative-level-list/', views_adl.AdministrativeLevelListTableView.as_view(), name='administrative_levels_list'),
    path('administrative-level-detail-list/<slug:id>/', views_adl.AdministrativeLevelDetailForListView.as_view(), name='administrative_level_detail_for_list'),
    path('<slug:id>/detail/', views_adl.AdministrativeLevelDetailView.as_view(), name='detail'),
    
    path('attachments/', views_adl.AttachmentListView.as_view(), name='attachments'),
    path('task-detail/<int:pk>', views_adl.TaskDetailAjaxView.as_view(), name='task_detail'),
    path('attachments-filter', views_adl.FillAttachmentSelectFilters.as_view(), name='attachment_filter'),
    
    path('documents/', views_doc.AttachmentListView.as_view(), name='documents'),

    path('export-situations/', views_export.export_administrativelels_situation_to_excel, name='export_administrativelels_situation_to_excel'),
]
