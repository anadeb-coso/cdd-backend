from django.db import models
from django.utils.translation import gettext_lazy as _
from storages.backends.s3boto3 import S3Boto3Storage
import os

from cdd.models_base import BaseModel


# Create your models here.
def app_path(instance, filename):
    # print(instance)
    # print(filename)
    # # print(instance.apk.storage.filename)
    # file_directory_within_bucket = 'proof_of_work/'
    # file_path_within_bucket = os.path.join(
    #     file_directory_within_bucket,
    #     filename
    # )
    # media_storage = S3Boto3Storage()
    # if not media_storage.exists(file_path_within_bucket):  # avoid overwriting existing file
    #     media_storage.save(file_path_within_bucket, instance.apk.storage)
    #     file_url = media_storage.url(file_path_within_bucket)
    #     print(file_url)
    #     return file_url
    # raise Exception('error')
    return f'proof_of_work/{filename}'

class StoreProject(BaseModel):
    name = models.CharField(max_length=100, unique=True, verbose_name=_('Project Name'))
    image = models.ImageField(upload_to=app_path, storage=S3Boto3Storage(), verbose_name=_('Image'))
    package = models.CharField(max_length=100,unique=True, verbose_name=_('Project Package'))
    description = models.TextField(verbose_name=_('Project Description'))
    
    def __str__(self):
        return self.name
    
    
class StoreApp(BaseModel):
    project = models.ForeignKey('StoreProject', on_delete=models.CASCADE, verbose_name=_('Project'))
    version_code = models.IntegerField(unique=True, verbose_name=_('Version Code'))
    app_version = models.CharField(max_length=45, verbose_name=_('Version'))
    apk = models.FileField(upload_to=app_path, blank=True, null=True, storage=S3Boto3Storage(), verbose_name=_('APK'))
    apk_aws_s3_url = models.CharField(max_length=255, blank=True, null=True, verbose_name=_('APK AWS S3 Url'))
    app_code = models.CharField(max_length=255, unique=True, verbose_name=_('App Code'))
    description = models.TextField(verbose_name=_('App Description'))
    
    def __str__(self):
        return f"{self.project.name} {self.version_code}({self.app_version})"

    @property
    def name(self):
        return self.__str__()
    
    def save(self, *args, **kwargs):
        if self.apk:
            self.apk_aws_s3_url = self.apk.url
        return super().save(*args, **kwargs)