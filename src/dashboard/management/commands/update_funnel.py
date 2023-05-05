from django.core.management.base import BaseCommand
import os
from dashboard.tasks import sync_celery_tasks


class Command(BaseCommand):
    help = 'Update the AggregatedStatus objects for the funnel'

    def handle(self, *args, **options):
        sync_celery_tasks()
