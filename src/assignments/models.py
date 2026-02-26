from django.db import models

from administrativelevels.models import BaseModel
from authentication.models import Facilitator


class AssignAdministrativeLevelToFacilitator(BaseModel):
    administrative_level_id = models.IntegerField()
    facilitator_id = models.IntegerField()
    project_id = models.IntegerField()
    activated = models.BooleanField(default=True)
    assign_date = models.DateField(null=True, blank=True)
    unassign_date = models.DateField(null=True, blank=True)
