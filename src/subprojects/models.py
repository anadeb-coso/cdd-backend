from django.db import models
from django.utils.translation import gettext_lazy as _


from cdd.models_base import BaseModel



class Financier(BaseModel):
    name = models.CharField(max_length=255)
    description = models.TextField()

    def __str__(self):
        return self.name
    

class Project(BaseModel):
    name = models.CharField(max_length=255)
    description = models.TextField()
    financier = models.ForeignKey('Financier', null=True, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

