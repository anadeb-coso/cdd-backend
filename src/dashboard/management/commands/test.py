from django.core.management.base import BaseCommand
import os
from dashboard.tasks import sync_celery_tasks
class Command(BaseCommand):
    help = 'Creates a success.txt file in the current directory'

    def handle(self, *args, **options):
        sync_celery_tasks()
        directory = os.getcwd()
        file_path = os.path.join(directory, 'success.txt')
        with open(file_path, 'w') as f:
            f.write('Success!')
        self.stdout.write(self.style.SUCCESS('Successfully created file "%s"' % file_path))
