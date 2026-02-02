from django.db import models
from django.contrib.auth.models import User, Group
from django.db.models.signals import post_save
from django.utils.translation import gettext_lazy as _
from itertools import chain
from django.db.models import F
from django.db.models.functions import Coalesce
from django.forms.models import model_to_dict

from authentication.models import Facilitator
from no_sql_client import NoSQLClient
from administrativelevels.models import AdministrativeLevel
from cdd.models_base import BaseModel
from process_manager.models import Phase, Activity as ProcessActivity, Project
from planning.vars import TIMES, DAYS




class Activity(BaseModel):
    type = models.CharField(max_length=50, verbose_name=_('Type'))
    phase = models.ForeignKey(Phase, null=True, blank=True, on_delete=models.SET_NULL, related_name="planning_activities")
    activity = models.ForeignKey(ProcessActivity, null=True, blank=True, on_delete=models.SET_NULL, related_name="planning_activities")
    name = models.CharField(max_length=255, verbose_name=_('Activity'))
    description = models.TextField(verbose_name=_('Description'))
    component = models.TextField(null=True, blank=True, verbose_name=_('Component'))
    vacation_type = models.CharField(max_length=100, verbose_name=_('Vacation type'), null=True, blank=True)
    administrative_level_ids = models.JSONField(null=True, blank=True, verbose_name=_("Locality ID"))
    administrative_levels = models.JSONField(null=True, blank=True, verbose_name=_("Localities"))
    planned_date = models.DateField(verbose_name=_("Plan date"), blank=True, null=True)
    is_period_dates = models.BooleanField(blank=True, null=True, verbose_name=_("Date range?"))
    planned_datetime_start = models.DateTimeField(blank=True, null=True, verbose_name=_("Start"))
    planned_datetime_end = models.DateTimeField(blank=True, null=True, verbose_name=_("End"))
    vacation_return_datetime = models.DateTimeField(blank=True, null=True, verbose_name=_("Return date"))
    completed = models.BooleanField(blank=True, null=True, verbose_name=_("Completed"))
    undo = models.BooleanField(blank=True, null=True, verbose_name=_("Undo"))
    is_another = models.BooleanField(blank=True, null=True, verbose_name=_("Another activity"))
    is_free_task = models.BooleanField(blank=True, null=True, verbose_name=_("Another activity done is free task?"))
    free_task_title = models.CharField(max_length=255, blank=True, null=True, verbose_name=_('The title of the free activity done'))
    another_detail = models.JSONField(null=True, blank=True)
    undo_comment = models.TextField(blank=True, null=True, verbose_name=_('Report (Undo)'))
    comment = models.TextField(blank=True, null=True, verbose_name=_('Report'))
    validated = models.BooleanField(default=None, blank=True, null=True, verbose_name=_("Validated"))
    edit_after_invalidation = models.BooleanField(blank=True, null=True)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="planning_activities")
    facilitator = models.ForeignKey(Facilitator, null=True, blank=True, on_delete=models.SET_NULL, related_name="planning_activities")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="planning_activities")
    
    total_men_present_over_35 = models.IntegerField(null=True, blank=True, verbose_name=_("Total men present over 35"))
    total_women_present_over_35 = models.IntegerField(null=True, blank=True, verbose_name=_("Total women present over 35"))
    total_people_present_over_35 = models.IntegerField(null=True, blank=True, verbose_name=_("Total people present over 35"))
    total_men_present_under_35 = models.IntegerField(null=True, blank=True, verbose_name=_("Total men present under 35"))
    total_women_present_under_35 = models.IntegerField(null=True, blank=True, verbose_name=_("Total women present under 35"))
    total_people_present_under_35 = models.IntegerField(null=True, blank=True, verbose_name=_("Total people present under 35"))
    total_people_present = models.IntegerField(null=True, blank=True, verbose_name=_("Total people present"))

    def get_files(self):
        return self.activityfile_set.get_queryset().order_by("-date_taken")
    
    def get_activities_validate(self):
        return self.activityvalidate_set.get_queryset().order_by("-created_date")
        
    def get_comments(self):
        return self.activitycomment_set.get_queryset().order_by("-created_date")
    
    def get_geolocations(self):
        return self.activitygeolocation_set.get_queryset().order_by("created_date")
    
    def get_activities_and_comments(self):
        # activities = self.activityvalidate_set.get_queryset().annotate(created_date_final=F('created_date'))
        # comments = self.activitycomment_set.get_queryset().annotate(created_date_final=F('created_date'))

        # combined_qs = activities.union(comments).order_by("-created_date_final")

        # return combined_qs
        return sorted((list(self.get_comments()) + list(self.get_activities_validate())), key=lambda obj: obj.created_date, reverse=True)

class ActivityValidate(BaseModel):
    activity = models.ForeignKey(Activity, null=True, blank=True, on_delete=models.SET_NULL)
    validated = models.BooleanField(default=None, verbose_name=_("Validated"))
    comment = models.TextField(null=True, blank=True, verbose_name=_('Report'))
    comment_read = models.BooleanField(default=False)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="planning_activities_validates")
    facilitator = models.ForeignKey(Facilitator, null=True, blank=True, on_delete=models.SET_NULL, related_name="planning_activities_validates")

class ActivityFile(BaseModel):
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    url = models.CharField(max_length=255)
    order = models.IntegerField(default=0)
    principal = models.BooleanField(default=False)
    date_taken = models.DateField()
    file_type = models.CharField(max_length=100, default="image")
    username = models.CharField(max_length=255)
    user_email = models.CharField(max_length=255, null=True, blank=True)


class ActivityComment(BaseModel):
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE)
    comment = models.TextField(verbose_name=_("Comment"))
    type = models.CharField(max_length=25, default="comment")
    comment_read = models.BooleanField(default=False)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="planning_activity_comments")
    facilitator = models.ForeignKey(Facilitator, null=True, blank=True, on_delete=models.SET_NULL, related_name="planning_activity_comments")


class ValidationGroupsProcess(BaseModel):
    name = models.CharField(max_length=255, null=True, blank=True, verbose_name=_("Name"))
    planners_groups = models.ManyToManyField(Group , related_name="planners_groups", default=[])
    validators_groups = models.ManyToManyField(Group , related_name="validators_groups", default=[])
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="validation_group")
    

class ActivityDeadline(BaseModel):
    name = models.CharField(max_length=255, null=True, blank=True, verbose_name=_("Name"))
    day = models.IntegerField(choices=DAYS, default=0, verbose_name=_("Day"))
    hour = models.CharField(max_length=10, choices=TIMES, default='00:00', verbose_name=_("Hour"))
    activities_deadline_groups = models.ManyToManyField(Group , related_name="activities_deadline_groups", default=[])
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="activity_deadline_group")


class ActivityGeolocation(BaseModel):
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE)

    latitude_start = models.FloatField(null=True)
    longitude_start = models.FloatField(null=True)
    taking_datetime_start = models.DateTimeField(null=True)

    latitude_end = models.FloatField(null=True, blank=True)
    longitude_end = models.FloatField(null=True, blank=True)
    taking_datetime_end = models.DateTimeField(null=True, blank=True)

    geolocation_start = models.JSONField(null=True, blank=True)
    geolocation_end = models.JSONField(null=True, blank=True)

    planning_date = models.DateField(null=True)