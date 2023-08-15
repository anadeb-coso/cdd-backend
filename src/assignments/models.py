from django.db import models
from django.utils.translation import gettext_lazy as _

from administrativelevels.models import BaseModel
from authentication.models import Facilitator

class AssignAdministrativeLevelToFacilitator(BaseModel):
    administrative_level_id = models.IntegerField()
    facilitator = models.ForeignKey(Facilitator, on_delete=models.CASCADE)
    project_id = models.IntegerField()
    activated = models.BooleanField(default=True)
    assign_date = models.DateField(null=True, blank=True)
    unassign_date = models.DateField(null=True, blank=True)
    
