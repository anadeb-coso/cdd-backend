from django.db import models
from no_sql_client import NoSQLClient


# Create your models here.
# The project object on couch looks like this
# {
#     "_id": "219e50bc41c65648039b08eb10e7b925",
#     "_rev": "1-2851220dbb9d42ee9a7d1f2889cf4f83",
#     "type": "project",
#     "name": "COSO",
#     "description": "Lorem ipsum"
# }
class Project(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    couch_id = models.CharField(max_length=255, blank=True)

    def save(self, *args, **kwargs):
        if not self.id:
            data = {
                "name": self.name,
                "type": "project",
                "description": self.description,
            }
            nsc = NoSQLClient()
            nsc_database = nsc.get_db("process_design")
            new_document = nsc.create_document(nsc_database, data)
            self.couch_id = new_document['_id']
        return super().save(*args, **kwargs)

# The Phase object on couch looks like this
# {
#     "_id": "abc123",
#     "_rev": "2-ae3f90c1f84c91ff97a4bffd5686a9b7",
#     "type": "phase",
#     "project_id": "219e50bc41c65648039b08eb10e7b925",
#     "administrative_level_id": "adml123", NO
#     "name": "Community Mobilization",
#     "order": 1,
#     "description": "Lorem ipsum",
#     "capacity_attachments": [
#         {
#             "name": "tutorial.pdf",
#             "url": "/attachments/1253a3516c4e88550768d719be04e43d/report.pdf",
#             "bd_id": "1253a3516c4e88550768d719be04e43d"
#         }
#     ]
# }
class Phase(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    project = models.ForeignKey("Project", on_delete=models.CASCADE)
    couch_id = models.CharField(max_length=255, blank=True)
    order = models.IntegerField()

    def save(self, *args, **kwargs):
        if not self.id:
            data = {
                "name": self.name,
                "type": "phase",
                "description": self.description,
                "order": self.order,
                "capacity_attachments": [],
                "project_id": self.project.couch_id
            }
            nsc = NoSQLClient()
            nsc_database = nsc.get_db("process_design")
            new_document = nsc.create_document(nsc_database, data)
            self.couch_id = new_document['_id']
        return super().save(*args, **kwargs)


#The activity object on couch looks like this
# {
#     "_id": "219e50bc41c65648039b08eb10032af1",
#     "_rev": "357-8cacccf0cbd94ecbaf2f45242a946eb0",
#     "type": "activity",
#     "project_id": "219e50bc41c65648039b08eb10e7b925",
#     "phase_id": "abc123",
#     "administrative_level_id": "adml123",
#     "name": "Réunion cantonale",
#     "order": 1,
#     "description": "Participer à la réunion cantonale conduite par l’AADB",
#     "attachments": [
#         {
#             "name": "tutorial.pdf",
#             "url": "/attachments/1253a3516c4e88550768d719be04e43d/report.pdf",
#             "bd_id": "1253a3516c4e88550768d719be04e43d"
#         }
#     ],
#     "total_tasks": 4,
#     "completed_tasks": 0
# }
class Activity(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    project = models.ForeignKey("Project", on_delete=models.CASCADE)
    phase = models.ForeignKey("Phase", on_delete=models.CASCADE)
    total_tasks = models.IntegerField()
    order = models.IntegerField()
    couch_id = models.CharField(max_length=255, blank=True)


    def save(self, *args, **kwargs):

        if not self.id:
            data = {
                "name": self.name,
                "type": "activity",
                "description": self.description,
                "order": self.order,
                "capacity_attachments": [],
                "project_id": self.project.couch_id,
                "phase_id": self.phase.couch_id,
                "total_tasks": self.total_tasks,
                "completed_tasks": 0
            }
            nsc = NoSQLClient()
            nsc_database = nsc.get_db("process_design")
            new_document = nsc.create_document(nsc_database, data)
            self.couch_id = new_document['_id']
        return super().save(*args, **kwargs)


# The task object on couch looks like this
# {
#   "_id": "d50db81ec709d67e3b1b299ba60f2666",
#   "_rev": "28-837510813494bd487a329b9d66e693f6",
#   "type": "task",
#   "project_id": "219e50bc41c65648039b08eb10e7b925",
#   "phase_id": "abc123",
#   "phase_name": "VISITES PREALABLES",
#   "activity_id": "219e50bc41c65648039b08eb10032af1",
#   "activity_name": "Réunion cantonale",
#   "administrative_level_id": "adml123",
#   "administrative_level_name": "Sanloaga",
#   "name": "Tarea 2",
#   "order": 2,
#   "description": "Lorem ipsum https://ee.kobotoolbox.org/x/HY43dHN4",
#   "completed": false,
#   "completed_date": "15-08-2022",
#   "capacity_attachments": [],
#   "attachments": [],
#   "form": []
class Task(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    project = models.ForeignKey("Project", on_delete=models.CASCADE)
    phase = models.ForeignKey("Phase", on_delete=models.CASCADE)
    activity = models.ForeignKey("Activity", on_delete=models.CASCADE)
    order = models.IntegerField()
    couch_id = models.CharField(max_length=255, blank=True)

    def save(self, *args, **kwargs):

        if not self.id:
            data = {
                "type": "task",
                "project_id": self.project.couch_id,
                "phase_id": self.phase.couch_id,
                "phase_name": self.phase.name,
                "activity_id": self.activity.couch_id,
                "activity_name": self.activity.name,
                "name": self.name,
                "order": self.order,
                "description": self.description,
                "completed": False,
                "completed_date": "",
                "capacity_attachments": [],
                "attachments": [],
                "form": []
            }
            nsc = NoSQLClient()
            nsc_database = nsc.get_db("process_design")
            new_document = nsc.create_document(nsc_database, data)
            self.couch_id = new_document['_id']
        return super().save(*args, **kwargs)
