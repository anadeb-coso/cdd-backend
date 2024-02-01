from email.policy import default
from django.db import models
from cdd_client import CddClient
from django.db.models.signals import post_save
from cdd.models_base import BaseModel


# Create your models here.
    
class AdministrativeLevel(BaseModel):
    name = models.CharField(max_length=255)
    parent = models.ForeignKey('AdministrativeLevel', null=True, blank=True, on_delete=models.CASCADE)
    geographical_unit = models.ForeignKey('GeographicalUnit', null=True, blank=True, on_delete=models.CASCADE)
    cvd = models.ForeignKey('CVD', null=True, blank=True, on_delete=models.CASCADE)
    type = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True)
    frontalier = models.BooleanField(default=True)
    rural = models.BooleanField(default=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    no_sql_db_id = models.CharField(null=True, blank=True, max_length=255)

    
    class Meta:
        unique_together = ['name', 'parent', 'type']

    def __str__(self):
        return self.name

    def get_list_priorities(self):
        """Method to get the list of the all priorities that the administrative is linked"""
        return self.villagepriority_set.get_queryset()
    
    # def get_list_subprojects(self):
    #     """Method to get the list of the all subprojects that the administrative is linked"""
    #     return self.subproject_set.get_queryset()
    def get_list_subprojects(self):
        """Method to get the list of the all subprojects that the administrative is linked"""
        if self.cvd:
            return self.cvd.subproject_set.get_queryset()
        return []


class GeographicalUnit(BaseModel):
    canton = models.ForeignKey('AdministrativeLevel', null=True, blank=True, on_delete=models.CASCADE)
    attributed_number_in_canton = models.IntegerField()
    unique_code = models.CharField(max_length=100, unique=True)
    description = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ['canton', 'attributed_number_in_canton']

    def get_name(self):
        administrativelevels = self.get_villages()
        name = ""
        count = 1
        length = len(administrativelevels)
        for adl in administrativelevels:
            name += adl.name
            if length != count:
                name += "/"
            count += 1
        return name if name else self.unique_code
    
    def get_villages(self):
        return self.administrativelevel_set.get_queryset()

    def get_cvds(self):
        return self.cvd_set.get_queryset()
    
    def __str__(self):
        return self.get_name()
    

class CVD(BaseModel):
    name = models.CharField(max_length=255)
    geographical_unit = models.ForeignKey('GeographicalUnit', on_delete=models.CASCADE)
    headquarters_village = models.ForeignKey('AdministrativeLevel', null=True, blank=True, on_delete=models.CASCADE, related_name='headquarters_village_of_the_cvd')
    attributed_number_in_canton = models.IntegerField(null=True, blank=True)
    unique_code = models.CharField(max_length=100, unique=True)
    president_name_of_the_cvd = models.CharField(max_length=100, null=True, blank=True)
    president_phone_of_the_cvd = models.CharField(max_length=15, null=True, blank=True)
    treasurer_name_of_the_cvd = models.CharField(max_length=100, null=True, blank=True)
    treasurer_phone_of_the_cvd = models.CharField(max_length=15, null=True, blank=True)
    secretary_name_of_the_cvd = models.CharField(max_length=100, null=True, blank=True)
    secretary_phone_of_the_cvd = models.CharField(max_length=15, null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    def get_name(self):
        administrativelevels = self.get_villages()
        if self.name:
            return self.name
        
        name = ""
        count = 1
        length = len(administrativelevels)
        for adl in administrativelevels:
            name += adl.name
            if length != count:
                name += "/"
            count += 1
        return name if name else self.unique_code
    
    def get_villages(self):
        return self.administrativelevel_set.get_queryset()
    
    def get_canton(self):
        if self.headquarters_village:
            return self.headquarters_village.parent
            
        for obj in self.get_villages():
            return obj.parent
        return None
    
    def get_list_subprojects(self):
        """Method to get the list of the all subprojects"""
        return self.subproject_set.get_queryset()
    
    def __str__(self):
        return self.get_name()
    

def update_or_create_amd_couch(sender, instance, **kwargs):
    print("test", instance.id, kwargs['created'])
    client = CddClient()
    if kwargs['created']:
        couch_object_id = client.create_administrative_level(instance)
        to_update = AdministrativeLevel.objects.filter(id=instance.id)
        to_update.update(no_sql_db_id=couch_object_id)
    else:
        client.update_administrative_level(instance)



post_save.connect(update_or_create_amd_couch, sender=AdministrativeLevel)
