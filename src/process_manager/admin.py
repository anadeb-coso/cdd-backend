from django.contrib import admin
from .models import *
# Register your models here.



class FacilitatorWaveAdmin(admin.ModelAdmin):
    fields = (
        'facilitator',
        'wave',
        'project',
        'begin',
        'end',
        'description',
    )
    raw_id_fields = (
        'facilitator',
    )
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
        'facilitator',
        'wave',
        'project',
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
        'administrative_level_wave', 'facilitator_wave',
    )
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
        'administrative_level_wave',
        'facilitator_wave',
        'deployment',
        'begin',
        'end',
        'description',
    )

    def get_queryset(self, request):
        return super().get_queryset(request) #.select_related('user')

admin.site.register(Project)
admin.site.register(Phase)
admin.site.register(Activity)
admin.site.register(Task)


admin.site.register(Wave)
admin.site.register(Deployment)
admin.site.register(AdministrativeLevelWave)
admin.site.register(FacilitatorWave, FacilitatorWaveAdmin)
admin.site.register(FacilitatorDeployment, FacilitatorDeploymentAdmin)
