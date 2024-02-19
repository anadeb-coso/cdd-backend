from django.contrib import admin
import shortuuid as uuid
from django import forms

from .models import *
# Register your models here.



class SubjectAdmin(admin.ModelAdmin):
    fields = (
        'name',
        'parent',
        'rank',
        'image',
        'description',
    )
    list_display = (
        'id',
        'name',
        'parent',
        'rank',
        'description',
    )
    raw_id_fields = (
        'parent',
    )
    search_fields = (
        'id',
        'name',
        'parent__name',
        'rank',
        'description',
    )

    def get_queryset(self, request):
        return super().get_queryset(request) #.select_related('user')


        
        
class LessonAdmin(admin.ModelAdmin):
    fields = (
        'subject',
        'name',
        'rank',
        'image',
        'description',
    )
    raw_id_fields = (
        'subject',
    )
    list_display = (
        'id',
        'subject',
        'name',
        'rank',
        'description',
    )
    search_fields = (
        'id',
        'subject__name',
        'name',
        'rank',
        'description',
    )

    def get_queryset(self, request):
        return super().get_queryset(request)


        
        
class SupportingMaterialAdmin(admin.ModelAdmin):
    fields = (
        'subject',
        'lesson',
        'name',
        'rank',
        'file',
        'description',
    )
    raw_id_fields = (
        'subject',
        'lesson',
    )
    list_display = (
        'id',
        'subject',
        'lesson',
        'name',
        'rank',
        'file_aws_s3_url',
        'description',
    )
    search_fields = (
        'id',
        'subject__name',
        'lesson__name',
        'name',
        'rank',
        'file_aws_s3_url',
        'description',
    )

    def get_queryset(self, request):
        return super().get_queryset(request)


admin.site.register(Subject, SubjectAdmin)
admin.site.register(Lesson, LessonAdmin)
admin.site.register(SupportingMaterial, SupportingMaterialAdmin)
