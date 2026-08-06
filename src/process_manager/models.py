from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from django.db.models import Q

from authentication.models import Facilitator
from no_sql_client import NoSQLClient
from administrativelevels.models import AdministrativeLevel
from cdd.models_base import BaseModel, CustomQuerySet
from cdd.functions import normalize_text

# class BaseModel(models.Model):
#     created_date = models.DateTimeField(auto_now_add = True, blank=True, null=True)
#     updated_date = models.DateTimeField(auto_now = True, blank=True, null=True)

#     class Meta:
#         abstract = True
    
#     def save_and_return_object(self):
#         super().save()
#         return self
    
# Create your models here.
# The project object on couch looks like this
# {
#     "_id": "219e50bc41c65648039b08eb10e7b925",
#     "_rev": "1-2851220dbb9d42ee9a7d1f2889cf4f83",
#     "type": "project",
#     "name": "COSO",
#     "description": "Lorem ipsum"
# }
class Project(BaseModel):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField()
    parent = models.ForeignKey('Project', null=True, blank=True, on_delete=models.CASCADE, related_name="children")
    couch_id = models.CharField(max_length=255, blank=True)
    facilitators = models.ManyToManyField(Facilitator, related_name="projects", default=[], blank=True)
    users = models.ManyToManyField(User, related_name="projects", default=[], blank=True)
    def __str__(self):
        return self.name

    def serialize_project(self, project):
        return {
            "name": project.name,
            "type": "project",
            "description": project.description,
            "sql_id": project.id,
            "couch_id": project.couch_id,
            "parent": self.serialize_project(project.parent) if project.parent else None,
        }


    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # data = {
        #     "name": self.name,
        #     "type": "project",
        #     "description": self.description,
        #     "sql_id": self.id
        # }
        data = self.serialize_project(self)
        nsc = NoSQLClient()
        nsc_database = nsc.get_db("process_design")
        new_document = nsc_database.get_query_result(
            {"_id": self.couch_id}
        )[0]
        if not new_document:
            new_document = nsc.create_document(nsc_database, data)
            self.couch_id = new_document['_id']
        else:
            if len(new_document) > 0:
                new_document = new_document[0].copy()
                new_document['name'] = self.name
                new_document['description'] = self.description
                nsc.update_cloudant_document(nsc_database,  new_document["_id"], new_document)
        super().save(*args, **kwargs)

        return self

    def get_cycles(self):
        return self.cycle_set.get_queryset()

    @property
    def root(self):
        root = self
        while root.parent:
            root = root.parent
        return root
    
    def build_the_tree_structure(self):
        """
        Construit l'arborescence complète (ascendants + descendants)
        en partant de ce projet.
        Retourne une liste ordonnée de projets.
        """
        visited = set()

        # --- 1. Remonter jusqu'au parent racine ---
        root = self
        while root.parent:
            root = root.parent

        result = []

        # --- 2. Descente récursive depuis la racine ---
        def dfs(project):
            if project.id in visited:
                return
            visited.add(project.id)
            result.append(project)

            # On explore tous les enfants (ordre alphabétique si besoin)
            for child in project.children.all().order_by("name"):
                dfs(child)

        dfs(root)

        # --- 3. Garder seulement les projets liés à self ---
        # on coupe la liste à partir de self, et on garde descendants
        if self in result:
            start_index = result.index(self)
            return result[:start_index+1] + [
                p for p in result[start_index+1:]
                if p.parent and (p.parent == self or p.parent in result[:start_index+1])
            ]
        return result



# The Cycle object on couch looks like this
# {
#     "_id": "abc123",
#     "_rev": "2-ae3f90c1f84c91ff97a4bffd5686a9b7",
#     "type": "cycle",
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
class Cycle(BaseModel):
    name = models.CharField(max_length=255)
    description = models.TextField()
    project = models.ForeignKey("Project", on_delete=models.CASCADE)
    couch_id = models.CharField(max_length=255, blank=True)
    order = models.IntegerField()
    capacity_attachments = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = ['project', 'order']
    
    def __str__(self):
        return f"{self.name} ({self.project.name})"

    def serialize_project(self, cycle):
        return {
            "name": cycle.name,
            "type": "cycle",
            "description": cycle.description,
            "order": cycle.order,
            "capacity_attachments": cycle.capacity_attachments,
            "project_id": cycle.project.couch_id,
            "project_name": self.project.name,
            "sql_id": cycle.id
        }

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        capacity_attachments = []
        if self.capacity_attachments:
            capacity_attachments = self.capacity_attachments
        
        data = self.serialize_project(self)
        nsc = NoSQLClient()
        nsc_database = nsc.get_db("process_design")
        new_document = nsc_database.get_query_result(
            {"_id": self.couch_id}
        )[0]
        if not new_document:
            new_document = nsc.create_document(nsc_database, data)
            self.couch_id = new_document['_id']
        else:
            if len(new_document) > 0:
                new_document = new_document[0].copy()
                new_document['project_id'] = self.project.couch_id
                new_document['name'] = self.name
                new_document['order'] = self.order
                new_document['description'] = self.description
                new_document['capacity_attachments'] = capacity_attachments
                new_document['project_name'] = self.project.name
                nsc.update_cloudant_document(nsc_database,  new_document["_id"], new_document)

        super().save(*args, **kwargs)
        return self
    


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
class Phase(BaseModel):
    name = models.CharField(max_length=255)
    name_normalized = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    description = models.TextField()
    project = models.ForeignKey("Project", on_delete=models.CASCADE)
    cycles = models.ManyToManyField("Cycle", related_name="phases", default=[], blank=False)
    couch_id = models.CharField(max_length=255, blank=True)
    order = models.IntegerField()
    capacity_attachments = models.JSONField(null=True, blank=True)
    
    objects = CustomQuerySet.as_manager()

    def __str__(self):
        return f"{self.name} ({self.project.name})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        capacity_attachments = []
        if self.capacity_attachments:
            capacity_attachments = self.capacity_attachments
        self.name_normalized = normalize_text(self.name)
        data = {
            "name": self.name,
            "name_normalized": self.name_normalized,
            "type": "phase",
            "description": self.description,
            "order": self.order,
            "capacity_attachments": capacity_attachments,
            "project_id": self.project.couch_id,
            "project_name": self.project.name,
            "sql_id": self.id,
            "cycles": [c.couch_id for c in self.cycles.all()]
        }
        nsc = NoSQLClient()
        nsc_database = nsc.get_db("process_design")
        new_document = nsc_database.get_query_result(
            {"_id": self.couch_id}
        )[0]
        if not new_document:
            new_document = nsc.create_document(nsc_database, data)
            self.couch_id = new_document['_id']
        else:
            if len(new_document) > 0:
                new_document = new_document[0].copy()
                new_document['project_id'] = self.project.couch_id
                new_document['project_name'] = self.project.name
                new_document['name'] = self.name
                new_document['name_normalized'] = self.name_normalized
                new_document['order'] = self.order
                new_document['description'] = self.description
                new_document['capacity_attachments'] = capacity_attachments
                new_document['cycles'] = [c.couch_id for c in self.cycles.all()]
                nsc.update_cloudant_document(nsc_database,  new_document["_id"], new_document)

        super().save(*args, **kwargs)
        return self


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
class Activity(BaseModel):
    name = models.CharField(max_length=255)
    name_normalized = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    description = models.TextField()
    project = models.ForeignKey("Project", on_delete=models.CASCADE)
    cycles = models.ManyToManyField("Cycle", related_name="activities", default=[], blank=False)
    phase = models.ForeignKey("Phase", on_delete=models.CASCADE)
    total_tasks = models.IntegerField()
    order = models.IntegerField()
    couch_id = models.CharField(max_length=255, blank=True)
    capacity_attachments = models.JSONField(null=True, blank=True)
    
    objects = CustomQuerySet.as_manager()

    def __str__(self):
        return  f"{self.phase.name} - {self.name} ({self.project.name})"


    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        capacity_attachments = []
        if self.capacity_attachments:
            capacity_attachments = self.capacity_attachments
        self.name_normalized = normalize_text(self.name)
        data = {
            "name": self.name,
            "name_normalized": self.name_normalized,
            "type": "activity",
            "description": self.description,
            "order": self.order,
            "capacity_attachments": capacity_attachments,
            "project_id": self.project.couch_id,
            "project_name": self.project.name,
            "phase_id": self.phase.couch_id,
            "total_tasks": self.total_tasks,
            "completed_tasks": 0,
            "sql_id": self.id,
            "cycles": [c.couch_id for c in self.cycles.all()]
        }
        nsc = NoSQLClient()
        nsc_database = nsc.get_db("process_design")
        new_document = nsc_database.get_query_result(
            {"_id": self.couch_id}
        )[0]
        if not new_document:
            new_document = nsc.create_document(nsc_database, data)
            self.couch_id = new_document['_id']
        else:
            if len(new_document) > 0:
                new_document = new_document[0].copy()
                new_document['project_id'] = self.project.couch_id
                new_document['phase_id'] = self.phase.couch_id
                new_document['project_name'] = self.project.name
                new_document['phase_name'] = self.phase.name
                new_document['name'] = self.name
                new_document['name_normalized'] = self.name_normalized
                new_document['order'] = self.order
                new_document['description'] = self.description
                new_document['total_tasks'] = self.total_tasks
                new_document['capacity_attachments'] = capacity_attachments
                new_document['cycles'] = [c.couch_id for c in self.cycles.all()]
                nsc.update_cloudant_document(nsc_database,  new_document["_id"], new_document)

        super().save(*args, **kwargs)
        return self


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
class Task(BaseModel):
    name = models.CharField(max_length=255)
    name_normalized = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    description = models.TextField()
    project = models.ForeignKey("Project", on_delete=models.CASCADE)
    cycles = models.ManyToManyField("Cycle", related_name="tasks", default=[], blank=False)
    phase = models.ForeignKey("Phase", on_delete=models.CASCADE)
    activity = models.ForeignKey("Activity", on_delete=models.CASCADE)
    order = models.IntegerField()
    task_order = models.IntegerField(default=0)
    form = models.JSONField(null=True, blank=True)
    attachments = models.JSONField(null=True, blank=True)
    capacity_attachments = models.JSONField(null=True, blank=True)
    couch_id = models.CharField(max_length=255, blank=True)
    
    objects = CustomQuerySet.as_manager()

    def __str__(self):
        return f"{self.phase.name} - {self.activity.name} - {self.name} ({self.project.name})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        form = []
        if self.form:
            form = self.form
        attachments = []
        if self.attachments:
            attachments = self.attachments
        capacity_attachments = []
        if self.capacity_attachments:
            capacity_attachments = self.capacity_attachments
        self.name_normalized = normalize_text(self.name)
        data = {
            "type": "task",
            "project_id": self.project.couch_id,
            "project_name": self.project.name,
            "phase_id": self.phase.couch_id,
            "phase_name": self.phase.name,
            "activity_id": self.activity.couch_id,
            "activity_name": self.activity.name,
            "name": self.name,
            "name_normalized": self.name_normalized,
            "order": self.order,
            "task_order": self.task_order,
            "description": self.description,
            "completed": False,
            "completed_date": "",
            "capacity_attachments": capacity_attachments,
            "support_attachments": True if attachments else False,
            "attachments": attachments,
            "form": form,
            "form_response": [],
            "sql_id": self.id,
            "cycles": [c.couch_id for c in self.cycles.all()]
        }
        nsc = NoSQLClient()
        nsc_database = nsc.get_db("process_design")
        new_document = nsc_database.get_query_result(
            {"_id": self.couch_id}
        )[0]
        if not new_document:
            new_document = nsc.create_document(nsc_database, data)
            self.couch_id = new_document['_id']
        else:
            if len(new_document) > 0:
                new_document = new_document[0].copy()
                new_document['project_id'] = self.project.couch_id
                new_document['project_name'] = self.project.name
                new_document['phase_id'] = self.phase.couch_id
                new_document['phase_name'] = self.phase.name
                new_document['activity_id'] = self.activity.couch_id
                new_document['activity_name'] = self.activity.name
                new_document['name'] = self.name
                new_document['name_normalized'] = self.name_normalized
                new_document['order'] = self.order
                new_document['description'] = self.description
                new_document['support_attachments'] = True if attachments else False
                new_document['attachments'] = attachments
                new_document['capacity_attachments'] = capacity_attachments
                new_document['form'] = form
                new_document['cycles'] = [c.couch_id for c in self.cycles.all()]
                nsc.update_cloudant_document(nsc_database,  new_document["_id"], new_document)
        #     nsc.update_doc_uncontrolled(nsc_database, new_document['_id'], new_document)

        super().save(*args, **kwargs)
        return self



class SoftAggregatedStatusConsiderationManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(
            Q(task__isnull=False, its_adl_has_sub_project=False, task_needs_subproject=False) | # For tasks hasn't subproject, we get only planification tasks or before its

            # For tasks has subproject or don't know, we get all tasks of CDD cycle
            Q(task__isnull=False, its_adl_has_sub_project__isnull=True) | 
            Q(task__isnull=False, its_adl_has_sub_project=True) |

            # For aggregation status don't related to task, we get without condition
            Q(task__isnull=True)
        )

class SoftAggregatedStatusConsiderationMixin(models.Model):

    objects = SoftAggregatedStatusConsiderationManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True
        base_manager_name = 'objects'


class AggregatedStatus(BaseModel, SoftAggregatedStatusConsiderationMixin):
    """
        - if task is null, facilitator is null and administrative_level_id is present, then AggregatedStatus represents the status of the location in a specific project and cycle.
        - if task is null, administrative_level_id is null and facilitator is present, then AggregatedStatus represents the facilitator's progress status.
        - if facilitator is null, administrative_level_id and task are present, then AggregatedStatus represents the status of the task in the locality
    """
    administrative_level_id = models.IntegerField(blank=True, null=True)
    task = models.ForeignKey("Task", blank=True, null=True, on_delete=models.SET_NULL)
    facilitator = models.ForeignKey(Facilitator, blank=True, null=True, on_delete=models.SET_NULL)
    project = models.ForeignKey("Project", on_delete=models.SET_NULL, null=True)
    cycle = models.ForeignKey("Cycle", on_delete=models.SET_NULL, null=True)
    total_tasks = models.IntegerField(default=0)
    total_tasks_completed = models.IntegerField(default=0)
    last_activity = models.DateTimeField(blank=True, null=True)

    total_tasks_validated = models.IntegerField(default=0)
    total_tasks_invalidated = models.IntegerField(default=0)
    total_tasks_invalidated_review = models.IntegerField(default=0)
    total_tasks_invalidated_review_completed = models.IntegerField(default=0)
    total_tasks_invalidated_review_in_pending = models.IntegerField(default=0)
    total_tasks_invalidated_unreview = models.IntegerField(default=0)
    total_tasks_invalidated_unreview_completed = models.IntegerField(default=0)
    total_tasks_invalidated_unreview_in_pending = models.IntegerField(default=0)
    total_tasks_waiting_validation = models.IntegerField(default=0)

    task_needs_subproject = models.BooleanField(default=False)
    its_adl_has_sub_project = models.BooleanField(null=True, blank=True)
    
    # objects = CustomQuerySet.as_manager()


    def administrative_level(self):
        try:
            return AdministrativeLevel.objects.using('mis').get(id=self.administrative_level_id)
        except AdministrativeLevel.DoesNotExist as e:
            return None
        except Exception as exc:
            print(exc)
            return None
        
class AggregatedStatusFacilitator(BaseModel):
    project = models.ForeignKey("Project", on_delete=models.CASCADE)
    cycle = models.ForeignKey("Cycle", on_delete=models.CASCADE)
    facilitator = models.ForeignKey(Facilitator, on_delete=models.CASCADE)

    total_tasks_current_project = models.IntegerField(default=0)
    total_tasks_completed_current_project = models.IntegerField(default=0)
    last_activity_current_project = models.DateTimeField(blank=True, null=True)
    total_tasks_stabilized = models.IntegerField(default=0)
    total_tasks_completed_stabilized = models.IntegerField(default=0)
    last_activity_stabilized = models.DateTimeField(blank=True, null=True)
    total_tasks = models.IntegerField(default=0)
    total_tasks_completed = models.IntegerField(default=0)
    last_activity = models.DateTimeField(blank=True, null=True)

    total_tasks_validated_current_project = models.IntegerField(default=0)
    total_tasks_invalidated_current_project = models.IntegerField(default=0)
    total_tasks_invalidated_review_current_project = models.IntegerField(default=0)
    total_tasks_invalidated_review_completed_current_project = models.IntegerField(default=0)
    total_tasks_invalidated_review_in_pending_current_project = models.IntegerField(default=0)
    total_tasks_invalidated_unreview_current_project = models.IntegerField(default=0)
    total_tasks_invalidated_unreview_completed_current_project = models.IntegerField(default=0)
    total_tasks_invalidated_unreview_in_pending_current_project = models.IntegerField(default=0)
    total_tasks_waiting_validation_current_project = models.IntegerField(default=0)

    total_tasks_validated_stabilized = models.IntegerField(default=0)
    total_tasks_invalidated_stabilized = models.IntegerField(default=0)
    total_tasks_invalidated_review_stabilized = models.IntegerField(default=0)
    total_tasks_invalidated_review_completed_stabilized = models.IntegerField(default=0)
    total_tasks_invalidated_review_in_pending_stabilized = models.IntegerField(default=0)
    total_tasks_invalidated_unreview_stabilized = models.IntegerField(default=0)
    total_tasks_invalidated_unreview_completed_stabilized = models.IntegerField(default=0)
    total_tasks_invalidated_unreview_in_pending_stabilized = models.IntegerField(default=0)
    total_tasks_waiting_validation_stabilized = models.IntegerField(default=0)
    
    total_tasks_validated = models.IntegerField(default=0)
    total_tasks_invalidated = models.IntegerField(default=0)
    total_tasks_invalidated_review = models.IntegerField(default=0)
    total_tasks_invalidated_review_completed = models.IntegerField(default=0)
    total_tasks_invalidated_review_in_pending = models.IntegerField(default=0)
    total_tasks_invalidated_unreview = models.IntegerField(default=0)
    total_tasks_invalidated_unreview_completed = models.IntegerField(default=0)
    total_tasks_invalidated_unreview_in_pending = models.IntegerField(default=0)
    total_tasks_waiting_validation = models.IntegerField(default=0)
    
    cvds_number_current_project = models.IntegerField(default=0)
    villages_number_current_project = models.IntegerField(default=0)
    cvds_number_stabilized = models.IntegerField(default=0)
    villages_number_stabilized = models.IntegerField(default=0)
    cvds_number = models.IntegerField(default=0)
    villages_number = models.IntegerField(default=0)

    last_task_done_current_project = models.ForeignKey("Task", blank=True, null=True, on_delete=models.SET_NULL, related_name='last_task_done_current_project_facilitators')
    last_task_done_stabilized = models.ForeignKey("Task", blank=True, null=True, on_delete=models.SET_NULL, related_name='last_task_done_stabilized_facilitators')
    last_task_done = models.ForeignKey("Task", blank=True, null=True, on_delete=models.SET_NULL, related_name='last_task_done_facilitators')

    administrative_level_headquarters_villages_infos = models.JSONField(default=list)

    new_update_exists = models.BooleanField(default=True)


class Wave(BaseModel):
    number = models.IntegerField(blank=False, null=False)
    description = models.TextField(blank=False, null=False)

    def __str__(self) -> str:
        return f'{self.number} : {self.description}'
    
    class Meta:
        unique_together = ['number']
        
class Deployment(BaseModel):
    number = models.IntegerField(blank=False, null=False)
    description = models.TextField(blank=False, null=False)

    def __str__(self) -> str:
        return f'{self.number} : {self.description}'
    
    class Meta:
        unique_together = ['number']

class AdministrativeLevelWave(BaseModel):
    administrative_level_id = models.IntegerField()
    wave = models.ForeignKey("Wave", on_delete=models.CASCADE)
    project = models.ForeignKey("Project", on_delete=models.CASCADE)
    cycle = models.ForeignKey("Cycle", on_delete=models.SET_NULL, null=True)
    begin = models.DateField(blank=True, null=True)
    end = models.DateField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    
    class Meta:
        unique_together = ['administrative_level_id', 'wave', 'project']
    
    def administrative_level(self):
        try:
            return AdministrativeLevel.objects.using('mis').get(id=self.administrative_level_id)
        except AdministrativeLevel.DoesNotExist as e:
            return None
        except Exception as exc:
            print(exc)
            return None

    def __str__(self) -> str:
        administrative_level = self.administrative_level()
        if self.description:
            return f'V{self.wave.number} - {administrative_level.name} - {self.project.name} : {self.description}'
        
        if administrative_level:
            return f'V{self.wave.number} - {administrative_level.name} - {self.project.name}'
        
        return f'V{self.wave.number} - {administrative_level} - {self.project.name}'
    

class FacilitatorWave(BaseModel):
    facilitator = models.ForeignKey(Facilitator, on_delete=models.CASCADE)
    wave = models.ForeignKey("Wave", on_delete=models.CASCADE)
    project = models.ForeignKey("Project", on_delete=models.CASCADE)
    cycle = models.ForeignKey("Cycle", on_delete=models.SET_NULL, null=True)
    begin = models.DateField(blank=True, null=True)
    end = models.DateField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ['facilitator', 'wave', 'project']
    
    def __str__(self) -> str:
        
        _str = f'V{self.wave.number} - {self.facilitator.name} - {self.project.name}'

        if self.description:
            _str += f' : {self.description}'
        
        return _str
    

class FacilitatorDeployment(BaseModel):
    administrative_level_wave = models.ForeignKey("AdministrativeLevelWave", on_delete=models.CASCADE)
    facilitator_wave = models.ForeignKey("FacilitatorWave", on_delete=models.CASCADE)
    deployment = models.ForeignKey("Deployment", on_delete=models.CASCADE)
    begin = models.DateField(blank=True, null=True)
    end = models.DateField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
        
    class Meta:
        unique_together = ['administrative_level_wave', 'facilitator_wave', 'deployment']
    
    def __str__(self) -> str:
        
        _str =  f'{self.facilitator_wave.facilitator.name} (V{self.facilitator_wave.wave.number} D{self.deployment.number} D-C{self.administrative_level_wave.wave.number} - {self.administrative_level_wave.project.name}'
        
        if self.description:
            _str += f' : {self.description}'
        
        return _str
    

class EmailAddressesWhichSendEmails(BaseModel):
    name = models.CharField(max_length=255)
    email_addresses = models.JSONField()
    project = models.ForeignKey("Project", on_delete=models.CASCADE)


class ProcessAddOrRemoveADL(BaseModel):
    name = models.CharField(max_length=150)
    move_from = models.CharField(max_length=150)
    move_to = models.CharField(max_length=150)
    administrative_levels = models.JSONField()
    executed = models.BooleanField(default=False)
    query_action = models.CharField(max_length=25)

# def post_project(sender, instance, **kwargs):
    
#     # if kwargs['created']:
        
#     # else:
#     try:
#         facilitators = instance.facilitators.all()
#         print(facilitators)
#         if facilitators:
#             nsc = NoSQLClient()
#             for f in facilitators:
#                 print(f.name)
#                 db = nsc.get_db(f.no_sql_db_name)

#                 docs = db.get_query_result({"type": "facilitator"})[0]

#                 if len(docs) > 0:
#                     doc = docs[0].copy()
#                     projects_ids = doc["projects_ids"] if 'projects_ids' in doc else []
#                     doc["projects_ids"] = list(set(projects_ids + [instance.couch_id]))

#                     nsc.update_cloudant_document(db,  doc["_id"], doc)

#     except Exception as exc:
#         print(exc)

def create_or_update_project(sender, instance, **kwargs):
    if instance.id:
        cycle = Cycle.objects.filter(project_id=instance.id).first()

        if not cycle:
            print("pass")
            cycle = Cycle()
            cycle.name="Cycle 1"
            cycle.description=f"Cycle 1 du projet ({instance.name})"
            cycle.project_id=instance.id
            cycle.order=1
            cycle.save()
            # Cycle.objects.create(
            #     name="Cycle 1",
            #     description=f"Cycle 1 du projet ({instance.name})",
            #     project_id=instance.id,
            #     order=1,
            # )
            
        # instance = Project.objects.get(id=instance.id)
        # if instance.id and instance.parent:
        #     instance.users.add(*instance.parent.users.all())
        #     instance.facilitators.add(*instance.parent.facilitators.all())
            # instance = instance.save_and_return_object()

def delete_process_design_doc(sender, instance, **kwargs) -> bool:
    nsc = NoSQLClient()
    nsc_database = nsc.get_db("process_design")

    try:
        doc = nsc_database[
            instance.couch_id
        ]
        print(doc)

        doc.delete()
        return True
    except Exception as exc:
        return False


post_save.connect(create_or_update_project, sender=Project)
post_delete.connect(delete_process_design_doc, sender=Phase)
post_delete.connect(delete_process_design_doc, sender=Activity)
post_delete.connect(delete_process_design_doc, sender=Task)