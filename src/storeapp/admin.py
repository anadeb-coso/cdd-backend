from django.contrib import admin
import shortuuid as uuid
from django import forms

from .models import *
# Register your models here.



class StoreProjectAdmin(admin.ModelAdmin):
    fields = (
        'name',
        'image',
        'package',
        'description',
    )
    list_display = (
        'id',
        'name',
        'package',
        'description',
    )
    search_fields = (
        'id',
        'name',
        'package',
        'description',
    )

    def get_queryset(self, request):
        return super().get_queryset(request) #.select_related('user')



class StoreAppForm(forms.ModelForm):
    class Meta:
        model = StoreApp
        fields = '__all__'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['app_code'].initial = str(uuid.uuid())
        # self.fields['app_code'].widget.attrs["disabled"] = "true"
    def clean_app_code(self):
        print(self.fields['app_code'].initial)
        return self.fields['app_code'].initial
        
        
class StoreAppAdmin(admin.ModelAdmin):
    form = StoreAppForm
    fields = (
        'project',
        'version_code',
        'app_version',
        'app_code',
        'apk',
        'apk_aws_s3_url',
        'description',
    )
    raw_id_fields = (
        'project',
    )
    list_display = (
        'id',
        'project',
        'version_code',
        'app_version',
        'app_code',
        'description',
    )
    search_fields = (
        'id',
        'project__name',
        'project__package',
        'version_code',
        'app_version',
        'app_code',
        'description',
    )

    def get_queryset(self, request):
        return super().get_queryset(request) #.select_related('user')



admin.site.register(StoreProject, StoreProjectAdmin)
admin.site.register(StoreApp, StoreAppAdmin)
