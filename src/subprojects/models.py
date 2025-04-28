from django.db import models
from django.utils.translation import gettext_lazy as _
from administrativelevels.models import AdministrativeLevel

from cdd.models_base import BaseModel



class Financier(BaseModel):
    name = models.CharField(max_length=255)
    description = models.TextField()

    def __str__(self):
        return self.name
    

class Project(BaseModel):
    name = models.CharField(max_length=255)
    description = models.TextField()
    financiers = models.ManyToManyField('Financier', default=[], blank=True, related_name="financiers_projects")

    administrative_levels = models.ManyToManyField(AdministrativeLevel, default=[], blank=True, verbose_name=_("Administrative Levels"), related_name="administrative_levels_projects")

    def __str__(self):
        return self.name


class Cycle(BaseModel):
    name = models.CharField(max_length=255)
    description = models.TextField()
    project_id = models.IntegerField()
    
    administrative_levels = models.ManyToManyField(AdministrativeLevel, default=[], blank=True, verbose_name=_("Administrative Levels"), related_name="administrative_levels_cycles")


    def __str__(self):
        return self.name
