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

class ActivityDeadlineAdmin(admin.ModelAdmin):
    fields = (
        'name',
        'day',
        'hour',
        'activities_deadline_groups',
        'project',
    )
    list_display = (
        'id',
        'name',
        'day',
        'hour',
        'project',
    )
    search_fields = (
        'id',
        'name',
        'day',
        'hour',
        'activities_deadline_groups',
        'project',
    )

admin.site.register(ValidationGroupsProcess, ValidationGroupsProcessAdmin)
admin.site.register(ActivityDeadline, ActivityDeadlineAdmin)


# from .functions import alert_users


# alert_users()