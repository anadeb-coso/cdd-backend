from django.db import models
from django.utils.translation import gettext_lazy as _
from administrativelevels.models import AdministrativeLevel, CVD

from cdd.models_base import BaseModel


class Subproject(BaseModel):
    location_subproject_realized = models.ForeignKey(AdministrativeLevel, null=True, blank=True, on_delete=models.CASCADE, related_name='location_subproject_realized', verbose_name=_("Subproject location"))
    cvd = models.ForeignKey(CVD, null=True, blank=True, on_delete=models.CASCADE, verbose_name=_("CVD"))
    projects = models.ManyToManyField('Project', default=[], blank=True, verbose_name=_("Projects"))

    infrastructure_deleted = models.BooleanField(null=True, blank=True, verbose_name=_("Infrastructure will no longer be built?"))

    def get_villages(self):
        if self.location_subproject_realized:
            return self.location_subproject_realized.cvd.administrativelevel_set.get_queryset()
        if self.cvd:
            return self.cvd.administrativelevel_set.get_queryset()

        return []

    def get_villages_ids(self):
        villages = self.get_villages()

        if villages:
            return list(villages.values_list('id', flat=True))

        return []

    

class VulnerableGroup(BaseModel):
    name = models.CharField(max_length=255)
    description = models.TextField()
    administrative_level = models.ForeignKey(AdministrativeLevel, null=False, on_delete=models.CASCADE)

    def __str__(self):
        return self.name



class VillageObstacle(BaseModel):
    administrative_level = models.ForeignKey(AdministrativeLevel, on_delete=models.CASCADE)
    focus_group = models.CharField(max_length=255)
    description = models.TextField()
    meeting = models.ForeignKey('VillageMeeting', on_delete=models.CASCADE)
    ranking = models.IntegerField(default=0)

    def __str__(self):
        return self.description


class VillageGoal(BaseModel):
    administrative_level = models.ForeignKey(AdministrativeLevel, on_delete=models.CASCADE)
    focus_group = models.CharField(max_length=255)
    description = models.TextField()
    meeting = models.ForeignKey('VillageMeeting', on_delete=models.CASCADE)
    ranking = models.IntegerField(default=0)

    def __str__(self):
        return self.description


class VillagePriority(BaseModel):
    administrative_level = models.ForeignKey(AdministrativeLevel, on_delete=models.CASCADE)
    component = models.ForeignKey('Component', null=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    proposed_men = models.IntegerField(null=True, blank=True)
    proposed_women = models.IntegerField(null=True, blank=True)
    estimated_cost = models.FloatField(null=True, blank=True)
    estimated_beneficiaries = models.IntegerField(null=True, blank=True)
    climate_changing_contribution = models.TextField(null=True, blank=True)
    eligibility = models.BooleanField(blank=True, null=True)
    sector = models.CharField(max_length=255, null=True, blank=True)
    parent = models.ForeignKey('VillagePriority', null=True, blank=True, on_delete=models.CASCADE)
    meeting = models.ForeignKey('VillageMeeting', on_delete=models.CASCADE)
    ranking = models.IntegerField(default=0)

    def __str__(self):
        return self.name


class TypeMain(BaseModel):
    village_priority = models.ForeignKey(VillagePriority, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    value = models.CharField(max_length=255)

    def __str__(self):
        return "{} : {}".format(self.name, self.value)


class VillageMeeting(BaseModel):
    description = models.TextField()
    date_conducted = models.DateTimeField()
    administrative_level = models.ForeignKey(AdministrativeLevel, on_delete=models.CASCADE)
    type = models.CharField(max_length=255)
    ranking = models.IntegerField(default=0)

    def __str__(self):
        return self.description


class Component(BaseModel):
    name = models.CharField(max_length=255)
    parent = models.ForeignKey('Component', null=True, blank=True, on_delete=models.CASCADE)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name
    


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
    order = models.IntegerField(default=1)
    
    administrative_levels = models.ManyToManyField(AdministrativeLevel, default=[], blank=True, verbose_name=_("Administrative Levels"), related_name="administrative_levels_cycles")


    def __str__(self):
        return self.name
