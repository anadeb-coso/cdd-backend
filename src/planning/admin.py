from django.contrib import admin
import shortuuid as uuid
from django import forms

from planning.models import *
# Register your models here.



class ValidationGroupsProcessAdmin(admin.ModelAdmin):
    fields = (
        'name',
        'planners_groups',
        'validators_groups',
        'project',
    )
    list_display = (
        'id',
        'name',
        'project',
    )
    search_fields = (
        'id',
        'name',
        'planners_groups',
        'validators_groups',
        'project',
    )


admin.site.register(ValidationGroupsProcess, ValidationGroupsProcessAdmin)
