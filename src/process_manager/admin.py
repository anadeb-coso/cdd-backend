from django.contrib import admin
from .models import Phase, Project, Activity
# Register your models here.

admin.site.register(Project)
admin.site.register(Phase)
admin.site.register(Activity)
