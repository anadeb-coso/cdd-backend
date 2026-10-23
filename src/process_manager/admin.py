from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _
from dashboard.process_manager.forms import ProjectFullForm
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


class ProjectAdmin(admin.ModelAdmin):
    # Formulaire complet partagé avec la page « Projets » du Web DCC (dashboard/process_manager/forms.py) : statut,
    # financeurs et niveaux administratifs (COSOMIS) en plus des facilitateurs et des utilisateurs. L'ancien
    # formulaire reprenait les facilitateurs/utilisateurs du parent quand la liste était vide, et plantait sans
    # parent ; c'est désormais la case « Lier aussi ceux du projet parent ».
    form = ProjectFullForm
    fieldsets = (
        (None, {'fields': ('name', 'description', 'parent', 'status', 'financiers', 'administrative_levels')}),
        (_('Facilitators and users'), {'fields': ('facilitators', 'users', 'inherit_from_parent')}),
    )
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

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # sélecteur à deux listes (les champs déclarés par le formulaire ne passent pas par filter_horizontal) ;
        # copie : ces champs sont partagés avec le formulaire de la page « Projets »
        import copy
        from django.contrib.admin.widgets import FilteredSelectMultiple
        for name in ('facilitators', 'users', 'financiers', 'administrative_levels'):
            field = form.base_fields[name] = copy.deepcopy(form.base_fields[name])
            field.widget = FilteredSelectMultiple(field.label, False)
        return form

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.save_links(form.instance)
        if form.inherited['facilitators'] or form.inherited['users']:
            messages.info(request, _("%(facilitators)s facilitator(s) and %(users)s user(s) of the parent project were "
                                     "also linked.") % form.inherited)



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
        'non_blocking',
        'visibility_condition',
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
    filter_horizontal = ('groups_collectors',)

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
