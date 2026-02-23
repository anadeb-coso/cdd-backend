from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save

from administrativelevels.models import AdministrativeLevel
from authentication.models import Facilitator
from cdd.models_base import BaseModel, CustomQuerySet

User = get_user_model()


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
            return result[:start_index + 1] + [
                p for p in result[start_index + 1:]
                if p.parent and (p.parent == self or p.parent in result[:start_index + 1])
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


class Phase(BaseModel):
    name = models.CharField(max_length=255)
    description = models.TextField()
    project = models.ForeignKey("Project", on_delete=models.CASCADE)
    cycles = models.ManyToManyField("Cycle", related_name="phases", default=[], blank=False)
    couch_id = models.CharField(max_length=255, blank=True)
    order = models.IntegerField()
    capacity_attachments = models.JSONField(null=True, blank=True)

    objects = CustomQuerySet.as_manager()

    def __str__(self):
        return f"{self.name} ({self.project.name})"


class Activity(BaseModel):
    name = models.CharField(max_length=255)
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
        return f"{self.phase.name} - {self.name} ({self.project.name})"


class Task(BaseModel):
    name = models.CharField(max_length=255)
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


class AggregatedStatus(BaseModel):
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
    total_tasks_invalidated_unreview = models.IntegerField(default=0)
    total_tasks_waiting_validation = models.IntegerField(default=0)
    total_tasks_invalidated_revised = models.IntegerField(
        default=0,
        help_text="Total invalidated tasks that were updated after"
    )

    objects = CustomQuerySet.as_manager()

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
    total_tasks_invalidated_unreview_current_project = models.IntegerField(default=0)
    total_tasks_waiting_validation_current_project = models.IntegerField(default=0)

    total_tasks_validated_stabilized = models.IntegerField(default=0)
    total_tasks_invalidated_stabilized = models.IntegerField(default=0)
    total_tasks_invalidated_review_stabilized = models.IntegerField(default=0)
    total_tasks_invalidated_unreview_stabilized = models.IntegerField(default=0)
    total_tasks_waiting_validation_stabilized = models.IntegerField(default=0)

    total_tasks_validated = models.IntegerField(default=0)
    total_tasks_invalidated = models.IntegerField(default=0)
    total_tasks_invalidated_review = models.IntegerField(default=0)
    total_tasks_invalidated_unreview = models.IntegerField(default=0)
    total_tasks_waiting_validation = models.IntegerField(default=0)

    cvds_number_current_project = models.IntegerField(default=0)
    villages_number_current_project = models.IntegerField(default=0)
    cvds_number_stabilized = models.IntegerField(default=0)
    villages_number_stabilized = models.IntegerField(default=0)
    cvds_number = models.IntegerField(default=0)
    villages_number = models.IntegerField(default=0)

    last_task_done_current_project = models.ForeignKey("Task", blank=True, null=True, on_delete=models.SET_NULL,
                                                       related_name='last_task_done_current_project_facilitators')
    last_task_done_stabilized = models.ForeignKey("Task", blank=True, null=True, on_delete=models.SET_NULL,
                                                  related_name='last_task_done_stabilized_facilitators')
    last_task_done = models.ForeignKey("Task", blank=True, null=True, on_delete=models.SET_NULL,
                                       related_name='last_task_done_facilitators')

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
        _str = f'{self.facilitator_wave.facilitator.name} (V{self.facilitator_wave.wave.number} D{self.deployment.number} D-C{self.administrative_level_wave.wave.number} - {self.administrative_level_wave.project.name}'

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


def create_or_update_project(sender, instance, **kwargs):
    if instance.id:
        cycle = Cycle.objects.filter(project_id=instance.id).first()

        if not cycle:
            print("pass")
            cycle = Cycle()
            cycle.name = "Cycle 1"
            cycle.description = f"Cycle 1 du projet ({instance.name})"
            cycle.project_id = instance.id
            cycle.order = 1
            cycle.save()


post_save.connect(create_or_update_project, sender=Project)


class TaskSubmission(BaseModel):
    """
    It represents a task instance assigned to a facilitator at a specific
    administrative level. It stores progress, form responses, and validation
    status.
    """
    # Main relationships
    task = models.ForeignKey(
        'process_manager.Task',
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    facilitator = models.ForeignKey(
        'authentication.Facilitator',
        on_delete=models.CASCADE,
        related_name='task_submissions',
        null=True
    )
    administrative_level_id = models.IntegerField(
        help_text="ID del nivel administrativo (village/canton)"
    )
    project = models.ForeignKey(
        'process_manager.Project',
        on_delete=models.CASCADE
    )
    cycle = models.ForeignKey(
        'process_manager.Cycle',
        on_delete=models.CASCADE
    )

    # State of completeness
    completed = models.BooleanField(default=False)
    completed_date = models.DateTimeField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)

    # Form responses
    form_response = models.JSONField(
        default=list,
        help_text="Array of objects containing form responses according to JSON Schema"
    )

    # Validation
    validated = models.BooleanField(
        null=True,
        blank=True,
        help_text="null=pending, True=valid, False=invalid"
    )
    updated_after_invalidation = models.BooleanField(
        default=False,
        help_text="Indicates whether it was updated after being invalidated"
    )
    validation_comment = models.TextField(blank=True)
    validated_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='validated_task_submissions'
    )
    validated_at = models.DateTimeField(null=True, blank=True)

    # Processed attachments
    processed_attachments = models.JSONField(
        default=list,
        help_text="[{name, url, type, uploaded_at, size}]"
    )

    # Fields for migration (temporary - dual-write phase)
    synced_to_couch = models.BooleanField(
        default=False,
        help_text="TEMPORARY: For tracking during dual-write migration"
    )
    couch_rev = models.CharField(
        max_length=255,
        blank=True,
        help_text="TEMPORARY: Revision of CouchDB for sync"
    )

    class Meta:
        db_table = 'process_manager_tasksubmission'
        unique_together = [
            ['task', 'facilitator', 'administrative_level_id', 'project', 'cycle']
        ]
        indexes = [
            models.Index(fields=['task', 'administrative_level_id']),
            models.Index(fields=['facilitator', 'completed']),
            models.Index(fields=['project', 'cycle', 'completed']),
            models.Index(fields=['validated', 'completed']),
            models.Index(fields=['administrative_level_id', 'project', 'cycle']),
        ]
        verbose_name = 'Task Submission'
        verbose_name_plural = 'Task Submissions'

    def __str__(self):
        return f"{self.task.name} - {self.facilitator.name} - ADL:{self.administrative_level_id}"


class TaskSubmissionHistory(BaseModel):
    """
    History of changes made to a Task Submission.
    Enables a complete audit of modifications.
    """
    submission = models.ForeignKey(
        TaskSubmission,
        on_delete=models.CASCADE,
        related_name='history'
    )
    facilitator = models.ForeignKey(
        'authentication.Facilitator',
        on_delete=models.CASCADE,
        help_text="Facilitator who made the change",
        null=True
    )

    # Fields for migration (temporary)
    missing_facilitator = models.JSONField(
        default=dict,
        blank=True,
        help_text="TEMPORARY: For tracking missing facilitators during migration"
    )

    # Snapshot of data at the time of editing
    form_response_snapshot = models.JSONField(
        help_text="Copy of form_response at the time of the change"
    )
    form_fields_snapshot = models.JSONField(
        help_text="Form schema at the time of editing"
    )
    fields_updated = models.JSONField(
        default=list,
        help_text="List of field names that changed"
    )
    attachments_updated = models.JSONField(
        default=list,
        help_text="List of attachment names that changed"
    )
    attachments_snapshot = models.JSONField(
        default=list,
        help_text="Attachment status at the time of the change"
    )
    page = models.IntegerField(
        default=0,
        help_text="Form page number (for multi-page forms)"
    )

    # Change metadata
    intervention_type = models.CharField(
        max_length=50,
        choices=[
            ('create', 'Create'),
            ('update', 'Update'),
            ('complete', 'Complete'),
            ('reopen', 'Reopen'),
            ('validate', 'Validate'),
            ('invalidate', 'Invalidate'),
        ],
        help_text="Type of intervention performed"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'process_manager_tasksubmissionhistory'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['submission', '-created_at']),
            models.Index(fields=['facilitator', '-created_at']),
        ]
        verbose_name = 'Task Submission History'
        verbose_name_plural = 'Task Submission Histories'

    def __str__(self):
        return f"{self.submission} - {self.intervention_type} - {self.created_at}"


class TaskUserInvolvement(BaseModel):
    """
    Record which facilitators have intervened in a specific task and
    when their first and last intervention was.
    """
    submission = models.ForeignKey(
        TaskSubmission,
        on_delete=models.CASCADE,
        related_name='user_involvements'
    )
    facilitator = models.ForeignKey(
        'authentication.Facilitator',
        on_delete=models.CASCADE,
        null=True
    )

    # Fields for migration (temporary)
    missing_facilitator = models.JSONField(
        default=dict,
        blank=True,
        help_text="TEMPORARY: For tracking missing facilitators during migration"
    )

    first_intervention_date = models.DateTimeField()
    last_intervention_date = models.DateTimeField()

    class Meta:
        db_table = 'process_manager_taskuserinvolvement'
        unique_together = [['submission', 'facilitator']]
        indexes = [
            models.Index(fields=['submission', 'facilitator']),
        ]
        verbose_name = 'Task User Involvement'
        verbose_name_plural = 'Task User Involvements'

    def __str__(self):
        return f"{self.facilitator.name} - {self.submission}"


class GeolocationCapture(BaseModel):
    """
    GPS coordinate capture performed by facilitators.
    This can be for administrative levels or custom points of interest.
    """
    facilitator = models.ForeignKey(
        'authentication.Facilitator',
        on_delete=models.CASCADE,
        related_name='geolocation_captures'
    )

    # Administrative level data (if applicable)
    administrative_level_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="Administrative level ID if it is an official geolocation"
    )
    administrative_level_name = models.CharField(
        max_length=255,
        blank=True
    )

    # The custom point of interest
    poi_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Name of the point of interest (for 'others')"
    )

    # Coordinates
    latitude = models.FloatField()
    longitude = models.FloatField()
    altitude = models.FloatField(
        null=True,
        blank=True,
        help_text="Altitude in meters"
    )
    accuracy = models.FloatField(
        null=True,
        blank=True,
        help_text="Accuracy in meters"
    )

    # Timestamps
    coords_created = models.DateTimeField(
        help_text="Moment the coordinates were captured"
    )
    coords_updated = models.DateTimeField(auto_now=True)

    # Tracking
    synced = models.BooleanField(default=False)
    device_info = models.JSONField(
        default=dict,
        blank=True,
        help_text="{device_model, os_version, app_version}"
    )

    class Meta:
        db_table = 'process_manager_geolocationcapture'
        indexes = [
            models.Index(fields=['facilitator', 'administrative_level_id']),
            models.Index(fields=['facilitator', 'coords_created']),
            models.Index(fields=['latitude', 'longitude']),
            models.Index(fields=['administrative_level_id']),
        ]
        verbose_name = 'Geolocation Capture'
        verbose_name_plural = 'Geolocation Captures'

    def __str__(self):
        if self.administrative_level_id:
            return f"{self.administrative_level_name} ({self.latitude}, {self.longitude})"
        return f"{self.poi_name} ({self.latitude}, {self.longitude})"

    @property
    def is_administrative_level(self):
        return self.administrative_level_id is not None

    @property
    def is_poi(self):
        return self.poi_name != ''


class AttachmentFile(BaseModel):
    """
    Attachment uploaded by facilitators for tasks.
    """
    task = models.ForeignKey(
        'process_manager.Task',
        on_delete=models.CASCADE,
        related_name='uploaded_attachments'
    )
    submission = models.ForeignKey(
        TaskSubmission,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='uploaded_files'
    )

    # File information
    name = models.CharField(max_length=255)
    file = models.FileField(
        upload_to='task_attachments/%Y/%m/%d/',
        help_text="File or URL if using S3"
    )
    file_type = models.CharField(max_length=100)
    file_size = models.IntegerField(
        help_text="Size in bytes"
    )
    order = models.IntegerField(default=0)

    # Metadata
    uploaded_by = models.ForeignKey(
        'authentication.Facilitator',
        on_delete=models.CASCADE
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    # S3 info (si se usa)
    s3_bucket = models.CharField(max_length=255, blank=True)
    s3_key = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = 'process_manager_attachmentfile'
        ordering = ['order', '-uploaded_at']
        indexes = [
            models.Index(fields=['task', 'submission']),
            models.Index(fields=['uploaded_by', '-uploaded_at']),
        ]
        verbose_name = 'Attachment File'
        verbose_name_plural = 'Attachment Files'

    def __str__(self):
        return f"{self.name} - {self.task.name}"
