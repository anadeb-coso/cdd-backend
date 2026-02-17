from django.db import models

from cdd.models_base import BaseModel


class VillageCommittee(BaseModel):
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    cvd_id = models.IntegerField()
    cvd_name = models.CharField(max_length=100)
    village_headquarters_id = models.IntegerField()
    village_headquarters_name = models.CharField(max_length=100)
    canton = models.CharField(max_length=100)
    commune = models.CharField(max_length=100)
    prefecture = models.CharField(max_length=100)
    region = models.CharField(max_length=100)
    project_name = models.CharField(max_length=100)
    members = models.JSONField(default=dict)
    number_of_members = models.IntegerField(default=0)
    members_included_women = models.BooleanField(default=False)
    method_used_to_select_members = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return self.name