import time

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User, AbstractUser, Permission, Group
from django.db import models
from django.db.models.signals import post_delete
from django.utils.translation import gettext_lazy as _

from authentication import FACILITATORS_TYPES
from cdd.models_base import BaseModel


class Facilitator(BaseModel):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='facilitator',
        null=True,  # null during migration; remove at the end of PHASE 3
        blank=True,
    )

    # CouchDB fields — keep during migration, remove in PHASE 3
    no_sql_user = models.CharField(max_length=150, unique=True)
    no_sql_pass = models.CharField(max_length=128)
    no_sql_db_name = models.CharField(max_length=150, unique=True)
    no_sql_dbs_names = models.JSONField(null=True, blank=True)

    # username is kept for historical reference during migration
    username = models.CharField(max_length=150, unique=True, verbose_name=_('username'))

    # The Facilitator password is no longer used for authentication — remove it in PHASE 3
    password = models.CharField(max_length=128, verbose_name=_('password'))
    code = models.CharField(max_length=100, unique=True, verbose_name=_('code'))
    active = models.BooleanField(default=False, verbose_name=_('active'))  # Remove it in PHASE 3
    develop_mode = models.BooleanField(default=False, verbose_name=_('develop mode'))
    training_mode = models.BooleanField(default=False, verbose_name=_('test mode'))
    administrative_levels = models.JSONField(null=True, blank=True)
    administrative_levels_ids = models.JSONField(null=True, blank=True)
    geographical_units = models.JSONField(
        default=list,
        blank=True,
        help_text="""
            Geographical units assigned with their CVD groups.
            Structure: [
                {
                    "sql_id": "111",
                    "name": "TIMANGA (CINKASSE)/KALYADA",
                    "villages": ["1986"],
                    "cvd_groups": [
                        {
                            "sql_id": "208",
                            "name": "TIMANGA (CINKASSE)",
                            "village_cvd": 1986,
                            "villages": ["1986"]
                        }
                    ]
                }
            ]
            """
    )

    facilitator_type = models.CharField(max_length=100, choices=FACILITATORS_TYPES, default='community_facilitator')

    name = models.CharField(max_length=200, null=True, blank=True, verbose_name=_('name'))  # Remove it in PHASE 3
    email = models.CharField(max_length=100, null=True, blank=True, verbose_name=_('email'))  # Remove it in PHASE 3
    phone = models.CharField(max_length=20, null=True, blank=True, verbose_name=_('phone'))
    sex = models.CharField(max_length=5, null=True, blank=True, verbose_name=_('sex'))

    total_tasks_current_project = None
    total_tasks_completed_current_project = None
    last_activity_current_project = None
    total_tasks_stabilized = None
    total_tasks_completed_stabilized = None
    last_activity_stabilized = None
    total_tasks = None
    total_tasks_completed = None
    last_activity = None

    total_tasks_validated_current_project = None
    total_tasks_invalidated_current_project = None
    total_tasks_invalidated_review_current_project = None
    total_tasks_invalidated_unreview_current_project = None
    total_tasks_waiting_validation_current_project = None

    total_tasks_validated_stabilized = None
    total_tasks_invalidated_stabilized = None
    total_tasks_invalidated_review_stabilized = None
    total_tasks_invalidated_unreview_stabilized = None
    total_tasks_waiting_validation_stabilized = None

    total_tasks_validated = None
    total_tasks_invalidated = None
    total_tasks_invalidated_review = None
    total_tasks_invalidated_unreview = None
    total_tasks_waiting_validation = None

    cvds_number_current_project = None
    villages_number_current_project = None
    cvds_number_stabilized = None
    villages_number_stabilized = None
    cvds_number = None
    villages_number = None

    last_task_done_current_project = None
    last_task_done_stabilized = None
    last_task_done = None

    __current_password = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__current_password = self.password
        self.cvds_number = 0
        self.villages_number = 0

    def __str__(self):
        return self.username

    def set_no_sql_user(self):
        now = str(int(time.time()))

        # Added to avoid repeating the same value for no_sql_user when bulk creating facilitators
        while Facilitator.objects.filter(no_sql_user=now).exists():
            now = str(int(time.time()))

        self.no_sql_user = now

    def simple_save(self, *args, **kwargs):
        return super().save(*args, **kwargs)

    def save_and_return_object(self, *args, **kwargs):
        if "user" in kwargs:
            user = kwargs.pop("user")
            self.users_history(user)
        super().save(*args, **kwargs)
        return self

    def save(self, *args, **kwargs):
        if "user" in kwargs:
            user = kwargs.pop("user")
            self.users_history(user)

        if not self.id and not self.code:
            self.code = self.get_code(self.no_sql_user)

        super().save(*args, **kwargs)

        return self

    def hash_password(self, *args, **kwargs):
        self.password = make_password(self.password, salt=None, hasher='default')
        return super().save(*args, **kwargs)

    def create_without_no_sql_db(self, *args, **kwargs):

        if not self.code:
            self.code = self.get_code(self.no_sql_user)

        if not self.password:
            self.password = f'ChangeItNow{self.code}'

        self.password = make_password(self.password, salt=None, hasher='default')

        return super().save(*args, **kwargs)

    @staticmethod
    def get_code(seed):
        import zlib
        return str(zlib.adler32(str(seed).encode('utf-8')))  # [:6]

    @property
    def is_active(self):
        return self.active

    def get_name(self):
        return f'{self.user.first_name} {self.user.last_name}'

    def get_name_with_sex(self):
        return f"{self.sex} {self.get_name()}" if {self.sex} else self.get_name()

    def get_email(self):
        return self.email

    def get_type(self):
        if self.develop_mode and self.training_mode:
            return "develop-training"
        elif self.develop_mode:
            return "develop"
        elif self.training_mode:
            return "training"
        else:
            return "deploy"

    def get_all_infos(self):

        _percent_current_project = self.total_tasks_completed_current_project / self.total_tasks_current_project if self.total_tasks_current_project else 0
        percent_current_project = float("%.2f" % ((_percent_current_project if _percent_current_project else 0) * 100))

        _percent_stabilized = self.total_tasks_completed_stabilized / self.total_tasks_stabilized if self.total_tasks_stabilized else 0
        percent_stabilized = float("%.2f" % ((_percent_stabilized if _percent_stabilized else 0) * 100))

        _percent = self.total_tasks_completed / self.total_tasks if self.total_tasks else 0
        percent = float("%.2f" % ((_percent if _percent else 0) * 100))

        return {
            "name": self.name,
            "sex": "F" if self.sex == "Mme" else "M",
            "username": self.username,
            "tel": self.phone,
            'last_activity_date': self.last_activity,
            "percent_current_project": percent_current_project,
            "percent_stabilized": percent_stabilized,
            "percent": percent,
            "cvd_current_project": f"{self.cvds_number_current_project}/{self.villages_number_current_project}",
            "cvd_stabilized": f"{self.cvds_number_stabilized}/{self.villages_number_stabilized}",
            "cvd": f"{self.cvds_number}/{self.villages_number}"
        }

    def get_facilitators_with_no_sql_dbs_names(self):
        return Facilitator.objects.filter(
            no_sql_db_name__in=self.no_sql_dbs_names
        )

    def get_facilitators_with_no_sql_db_name(self):
        return Facilitator.objects.filter(
            no_sql_dbs_names__contains=self.no_sql_db_name
        )

    class Meta:
        verbose_name = _('Facilitator')
        verbose_name_plural = _('Facilitators')


def delete_user(sender, instance, **kwargs):
    try:
        user = User.objects.using('mis').get(username=instance.username)
        user.delete(using="mis")
    except Exception as exc:
        pass


post_delete.connect(delete_user, sender=User)
