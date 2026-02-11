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
    if 'cdd' in filename.lower() or 'dcc' in filename.lower():
        return f'apk/cdd/{filename}'
    elif 'grm' in filename.lower() or 'mgp' in filename.lower():
        return f'apk/grm/{filename}'
    return f'proof_of_work/{filename}'

class StoreProject(BaseModel):
    name = models.CharField(max_length=100, unique=True, verbose_name=_('Project Name'))
    image = models.ImageField(upload_to=app_path, storage=S3Boto3Storage(), verbose_name=_('Image'))
    package = models.CharField(max_length=100,unique=True, verbose_name=_('Project Package'))
    playstore_url = models.CharField(max_length=255, blank=True, null=True, verbose_name=_('PlayStore Url'))
    description = models.TextField(verbose_name=_('Project Description'))
    
    def last_version(self):
        return self.storeapp_set.get_queryset().order_by('-created_date').first()
    
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
        super().save(*args, **kwargs)
        if self.apk:
            self.apk_aws_s3_url = self.apk.url
        return super().save(*args, **kwargs)


class SyncLog(BaseModel):
    """
    Log of synchronization operations between mobile app and backend.
    Useful for debugging and auditing.
    """
    facilitator = models.ForeignKey(
        'authentication.Facilitator',
        on_delete=models.CASCADE,
        related_name='sync_logs'
    )

    sync_timestamp = models.DateTimeField(auto_now_add=True)
    sync_type = models.CharField(
        max_length=50,
        choices=[
            ('delta', 'Delta Sync'),
            ('batch', 'Batch Upload'),
            ('full', 'Full Sync'),
        ]
    )

    # Statistics
    entities_synced = models.JSONField(
        default=dict,
        help_text='{"task_submissions": 10, "geolocations": 5}'
    )
    conflicts_count = models.IntegerField(default=0)
    conflicts_data = models.JSONField(
        default=list,
        help_text="Details of conflicts encountered"
    )
    errors_count = models.IntegerField(default=0)
    errors_data = models.JSONField(
        default=list,
        help_text="Details of errors that occurred"
    )
    duration_ms = models.IntegerField(
        help_text="Synchronization duration in milliseconds"
    )

    # Request info
    device_info = models.JSONField(default=dict, blank=True)
    app_version = models.CharField(max_length=50, blank=True)

    class Meta:
        db_table = 'process_manager_synclog'
        ordering = ['-sync_timestamp']
        indexes = [
            models.Index(fields=['facilitator', '-sync_timestamp']),
            models.Index(fields=['-sync_timestamp']),
        ]
        verbose_name = 'Sync Log'
        verbose_name_plural = 'Sync Logs'

    def __str__(self):
        return f"{self.facilitator.name} - {self.sync_type} - {self.sync_timestamp}"