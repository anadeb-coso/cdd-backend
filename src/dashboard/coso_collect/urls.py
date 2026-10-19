from django.urls import path

from dashboard.coso_collect import views

app_name = 'coso_collect'
urlpatterns = [
    path('', views.FormListView.as_view(), name='list'),
    path('new/', views.FormCreateView.as_view(), name='create'),
    path('import/', views.FormImportCreateView.as_view(), name='import'),

    # Création / paramétrage (administrateurs du formulaire)
    path('<int:pk>/builder/', views.BuilderView.as_view(), name='builder'),
    path('<int:pk>/builder/save/', views.BuilderSaveView.as_view(), name='builder_save'),
    path('<int:pk>/builder/import/', views.BuilderImportView.as_view(), name='builder_import'),
    path('<int:pk>/builder/choices-export/', views.BuilderChoicesExportView.as_view(), name='builder_choices_export'),
    path('<int:pk>/builder/choices-import/', views.BuilderChoicesImportView.as_view(), name='builder_choices_import'),
    path('<int:pk>/builder/datasources/', views.BuilderDataSourcesView.as_view(), name='builder_datasources'),
    path('<int:pk>/builder/datasource-preview/', views.BuilderDataSourcePreviewView.as_view(),
         name='builder_datasource_preview'),
    path('<int:pk>/builder/dataset-sheet/', views.BuilderDatasetSheetView.as_view(), name='builder_dataset_sheet'),
    path('<int:pk>/file/<str:fmt>/', views.FormFileExportView.as_view(), name='form_file'),
    path('<int:pk>/settings/', views.SettingsView.as_view(), name='settings'),
    path('<int:pk>/status/', views.StatusView.as_view(), name='status'),
    path('<int:pk>/admins/', views.FormAdminsView.as_view(), name='admins'),
    path('<int:pk>/delete/', views.FormDeleteView.as_view(), name='delete'),

    # Données (administrateurs du formulaire)
    path('<int:pk>/', views.SummaryView.as_view(), name='summary'),
    path('<int:pk>/data/', views.DataView.as_view(), name='data'),
    path('<int:pk>/gallery/', views.GalleryView.as_view(), name='gallery'),
    path('<int:pk>/map/', views.MapView.as_view(), name='map'),
    path('<int:pk>/export/', views.ExportView.as_view(), name='export'),

    # Saisie (tout utilisateur ayant accès au formulaire)
    path('<int:pk>/my-records/', views.MySubmissionsView.as_view(), name='my_submissions'),
    path('<int:pk>/fill/', views.FillView.as_view(), name='fill'),
    path('<int:pk>/upload/', views.UploadView.as_view(), name='upload'),
    path('record/<uuid:uuid>/', views.SubmissionDetailView.as_view(), name='submission'),
    path('record/<uuid:uuid>/edit/', views.EditSubmissionView.as_view(), name='edit'),
    path('record/<uuid:uuid>/save/', views.SubmissionSaveView.as_view(), name='save'),
    path('record/<uuid:uuid>/editable/', views.SubmissionEditableView.as_view(), name='editable'),
    path('record/<uuid:uuid>/delete/', views.SubmissionDeleteView.as_view(), name='delete_submission'),
    # Correction des données d'une saisie par un administrateur (droit « Modifier les saisies »)
    path('record/<uuid:uuid>/admin-edit/', views.AdminEditSubmissionView.as_view(), name='admin_edit'),
    path('record/<uuid:uuid>/admin-save/', views.AdminSaveSubmissionView.as_view(), name='admin_save'),
    path('record/<uuid:uuid>/admin-upload/', views.AdminUploadView.as_view(), name='admin_upload'),
    path('attachment/<int:aid>/', views.AttachmentView.as_view(), name='attachment'),
]
