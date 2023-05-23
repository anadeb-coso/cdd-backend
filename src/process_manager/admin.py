from django.contrib import admin
from .models import *
# Register your models here.

admin.site.register(Project)
admin.site.register(Phase)
admin.site.register(Activity)
admin.site.register(Task)


admin.site.register(Wave)
admin.site.register(Deployment)
admin.site.register(AdministrativeLevelWave)
admin.site.register(FacilitatorWave)
admin.site.register(FacilitatorDeployment)
