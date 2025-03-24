from django.db import models
from django.utils.translation import gettext_lazy as _


from cdd.models_base import BaseModel


class ValidationCode(BaseModel):
    code = models.CharField(max_length=128, verbose_name=_('Code'))
    email = models.CharField(max_length=100, verbose_name=_('Email'))
    asking_datetime = models.DateTimeField(verbose_name=_("Asking datetime"))
    validation_code_ending_datetime = models.DateTimeField(verbose_name=_("Validation Code Ending datetime"))
    motif = models.TextField(verbose_name=_('Motif'))
    already_use = models.BooleanField(default=False, verbose_name=_('Already Use?'))