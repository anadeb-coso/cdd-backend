from django.db import models
from django.utils.translation import gettext_lazy as _
from storages.backends.s3boto3 import S3Boto3Storage
import os

from cdd.models_base import BaseModel


# Create your models here.
def app_path(instance, filename):
    return f'proof_of_work/{filename}'

class Subject(BaseModel):
    name = models.CharField(max_length=100, verbose_name=_('Subject Name'))
    parent = models.ForeignKey('Subject', null=True, blank=True, on_delete=models.CASCADE)
    rank = models.IntegerField(verbose_name=_('Rank'))
    image = models.ImageField(upload_to=app_path, storage=S3Boto3Storage(), verbose_name=_('Illustration Image'), null=True, blank=True)
    description = models.TextField(verbose_name=_('Subject Description'), blank=True, null=True)
    
    def subjects(self):
        return self.subject_set.get_queryset().order_by('rank', 'name')
    
    def lessons(self):
        return self.lesson_set.get_queryset().order_by('rank', 'name')
    
    def __str__(self):
        return self.name
    
    class Meta:
        unique_together = [['parent', 'name'], ['parent', 'rank']]
        
    
class Lesson(BaseModel):
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE, verbose_name=_('Subject'))
    name = models.CharField(max_length=100, verbose_name=_('Lesson Name'))
    rank = models.IntegerField(verbose_name=_('Rank'))
    image = models.ImageField(upload_to=app_path, storage=S3Boto3Storage(), verbose_name=_('Illustration Image'), null=True, blank=True)
    description = models.TextField(verbose_name=_('Lesson Description'), blank=True, null=True)
    
    
    def supportingmaterials(self):
        return self.supportingmaterial_set.get_queryset().order_by('rank', 'name')
    
    def __str__(self):
        return self.name
    
    class Meta:
        unique_together = [['subject', 'name'], ['subject', 'rank']]


class SupportingMaterial(BaseModel):
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE, verbose_name=_('Subject'), blank=True, null=True)
    lesson = models.ForeignKey('Lesson', on_delete=models.CASCADE, verbose_name=_('Lesson'), blank=True, null=True)
    name = models.CharField(max_length=100, verbose_name=_('Name of resource'))
    rank = models.IntegerField(verbose_name=_('Rank'))
    file = models.FileField(upload_to=app_path, storage=S3Boto3Storage(), verbose_name=_('File'))
    file_aws_s3_url = models.CharField(max_length=255, blank=True, null=True, verbose_name=_('File AWS S3 Url'))
    description = models.TextField(verbose_name=_('Supporting Material Description'), blank=True, null=True)
    
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.file:
            self.file_aws_s3_url = self.file.url
        return super().save(*args, **kwargs)
    
    class Meta:
        unique_together = [
            ['subject', 'name'], ['subject', 'rank'], 
            ['lesson', 'name'], ['lesson', 'rank']
        ]