from django.contrib import admin
from django import forms
from .models import *
# Register your models here.

from cdd import FORM_FIELDS_TO_EXCLUDE



class FacilitatorWaveAdmin(admin.ModelAdmin):
    fields = (
        'facilitator',
        'wave',
        'project',
        'begin',
        'end',
        'description',
    )
    # raw_id_fields = (
    #     'facilitator',
    # )
    autocomplete_fields = ['facilitator']
    list_display = (
        'id',
        'facilitator',
        'wave',
        'project',
        'begin',
        'end',
        'description',
    )
    search_fields = (
        'id',
        'facilitator__username',
        'wave__number',
        'wave__description',
        'project__name',
        'project__description',
        'begin',
        'end',
        'description',
    )

    def get_queryset(self, request):
        return super().get_queryset(request) #.select_related('user')

class FacilitatorDeploymentAdmin(admin.ModelAdmin):
    fields = (
        'administrative_level_wave',
        'facilitator_wave',
        'deployment',
        'begin',
        'end',
        'description',
    )
    raw_id_fields = (
        'administrative_level_wave',
    )
    autocomplete_fields = ['facilitator_wave']
    list_display = (
        'id',
        'administrative_level_wave',
        'facilitator_wave',
        'deployment',
        'begin',
        'end',
        'description',
    )
    search_fields = (
        'id',
        'administrative_level_wave__administrative_level_id',
        'administrative_level_wave__wave__number',
        'administrative_level_wave__wave__description',
        'administrative_level_wave__project__name',
        'administrative_level_wave__project__description',
        'facilitator_wave__facilitator__username',
        'facilitator_wave__wave__number',
        'facilitator_wave__wave__description',
        'facilitator_wave__project__name',
        'facilitator_wave__project__description',
        'deployment__number',
        'deployment__description',
        'begin',
        'end',
        'description',
    )

    def get_queryset(self, request):
        return super().get_queryset(request) #.select_related('user')


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        exclude = FORM_FIELDS_TO_EXCLUDE

    def clean_facilitators(self):
        parent = self.cleaned_data['parent']
        facilitators = self.cleaned_data['facilitators']

        if not facilitators:
            facilitators = parent.facilitators.all()
        
        return facilitators
    
    def clean_users(self):
        parent = self.cleaned_data['parent']
        users = self.cleaned_data['users']

        if not users:
            users = parent.users.all()
        
        return users

    # def save(self, commit=True):
    #     instance = super(ProjectForm, self).save(commit=False)
        
    #     instance = Project.objects.get(id=instance.id)
        
    #     if instance.id and instance.parent:
    #         instance.users.add(*instance.parent.users.all())
    #         instance.facilitators.add(*instance.parent.facilitators.all())
    #         instance = instance.save_and_return_object()

    #     return instance


class ProjectAdmin(admin.ModelAdmin):
    form = ProjectForm
    list_display = (
        'id',
        'name',
        'description',
    )
    search_fields = (
        'id',
        'name',
        'description',
    )
    
    # raw_id_fields = (
    #     'facilitators',
    #     'users',
    # )
    filter_horizontal  = ['facilitators', 'users']



class PhaseAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'name',
        'description',
        'project',
    )
    search_fields = (
        'id',
        'name',
        'description',
        'project__name',
        'project__description',
    )


class ActivityAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'phase',
        'name',
        'description',
        'project',
    )
    search_fields = (
        'id',
        'name',
        'phase_name',
        'phase_description',
        'project__name',
        'project__description',
    )
    
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'activity',
        'name',
        'project',
    )
    search_fields = (
        'id',
        'name',
        'description',
        'activity_name',
        'activity_description',
        'phase_name',
        'phase_description',
        'project__name',
        'project__description',
    )

class EmailAddressesWhichSendEmailsAdmin(admin.ModelAdmin):
    fields = (
        'name',
        'email_addresses',
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
        'email_addresses',
        'project__name',
        'project__description',
    )

admin.site.register(Project, ProjectAdmin)
admin.site.register(Phase, PhaseAdmin)
admin.site.register(Activity, ActivityAdmin)
admin.site.register(Task, TaskAdmin)


admin.site.register(Cycle)
admin.site.register(Wave)
admin.site.register(Deployment)
admin.site.register(AdministrativeLevelWave)
admin.site.register(FacilitatorWave, FacilitatorWaveAdmin)
admin.site.register(FacilitatorDeployment, FacilitatorDeploymentAdmin)
admin.site.register(EmailAddressesWhichSendEmails, EmailAddressesWhichSendEmailsAdmin)
