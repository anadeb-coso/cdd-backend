from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab
from datetime import datetime

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cdd.settings')

app = Celery('cdd')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')



# CELERY_BEAT_SCHEDULE = { # scheduler configuration 
#     'Test_schedule' : {  # whatever the name you want 
#         'task': 'dashboard.tasks.test', # name of task with path
#         'schedule': 10, #crontab(), # crontab() runs the tasks every minute
#         'args' : {4, 8}
#     },
#     # 'Task_two_schedule' : {  # whatever the name you want 
#     #     'task': 'test_app.tasks.task_two', # name of task with path
#     #     'schedule': 30, # 30 runs this task every 30 seconds
#     #     'args' : {datetime.now()} # arguments for the task
#     # },
# }
app.conf.beat_schedule = { # scheduler configuration 
    'Sync_celery_tasks_schedule' : {  # whatever the name you want 
        'task': 'dashboard.tasks.sync_celery_tasks', # name of task with path
        'schedule': crontab(minute=0, hour=0), #120, #crontab(), # crontab() runs the tasks every minute
        # 'args' : {4, 8}
    }
}



# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

