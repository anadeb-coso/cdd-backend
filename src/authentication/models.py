import secrets
import time
from datetime import datetime

from django.contrib.auth.hashers import make_password
from django.db import models
from django.utils.translation import gettext_lazy as _

from no_sql_client import NoSQLClient
from dashboard.facilitators.functions import get_cvds
from cdd.functions import datetime_complet_str
# from django.db.models.signals import post_save
# from django.contrib.auth.models import User
# from django.db import IntegrityError
# from django.forms.models import model_to_dict

class Facilitator(models.Model):
    no_sql_user = models.CharField(max_length=150, unique=True)
    no_sql_pass = models.CharField(max_length=128)
    no_sql_db_name = models.CharField(max_length=150, unique=True)
    username = models.CharField(max_length=150, unique=True, verbose_name=_('username'))
    password = models.CharField(max_length=128, verbose_name=_('password'))
    code = models.CharField(max_length=6, unique=True, verbose_name=_('code'))
    active = models.BooleanField(default=False, verbose_name=_('active'))
    develop_mode = models.BooleanField(default=False, verbose_name=_('test mode'))
    training_mode = models.BooleanField(default=False, verbose_name=_('test mode'))
    
    name = models.CharField(max_length=200, null=True, blank=True, verbose_name=_('name'))
    email = models.CharField(max_length=100, null=True, blank=True, verbose_name=_('email'))
    phone = models.CharField(max_length=20, null=True, blank=True, verbose_name=_('phone'))
    sex = models.CharField(max_length=5, null=True, blank=True, verbose_name=_('sex'))
    total_tasks = models.IntegerField(default=0)
    total_tasks_completed = models.IntegerField(default=0)
    last_activity = models.DateTimeField(blank=True, null=True)


    __current_password = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__current_password = self.password

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

    def save(self, *args, **kwargs):
        replicate_design = True
        if "replicate_design" in kwargs:
            replicate_design = kwargs.pop("replicate_design")

        if not self.id:

            self.set_no_sql_user()

            no_sql_pass_length = 13
            self.no_sql_pass = secrets.token_urlsafe(no_sql_pass_length)

            self.no_sql_db_name = f'facilitator_{self.no_sql_user}'

            if not self.code:
                self.code = self.get_code(self.no_sql_user)

            if not self.password:
                self.password = f'ChangeItNow{self.code}'

            nsc = NoSQLClient()
            nsc.create_user(self.no_sql_user, self.no_sql_pass)
            facilitator_db = nsc.create_db(self.no_sql_db_name)
            if replicate_design:
                nsc.replicate_design_db(facilitator_db)
            nsc.add_member_to_database(facilitator_db, self.no_sql_user)

        if self.password and self.password != self.__current_password:
            self.password = make_password(self.password, salt=None, hasher='default')

        return super().save(*args, **kwargs)

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

    def create_with_no_sql_db(self, *args, **kwargs):

        if not self.id:
            self.set_no_sql_user()

            no_sql_pass_length = 13
            self.no_sql_pass = secrets.token_urlsafe(no_sql_pass_length)

            if not self.code:
                self.code = self.get_code(self.no_sql_user)

            nsc = NoSQLClient()
            nsc.create_user(self.no_sql_user, self.no_sql_pass)
            facilitator_db = nsc.get_db(self.no_sql_db_name)
            nsc.add_member_to_database(facilitator_db, self.no_sql_user)

        if self.password and self.password != self.__current_password:
            self.password = make_password(self.password, salt=None, hasher='default')

        return super().save(*args, **kwargs)

    def create_with_manually_assign_database(self, *args, **kwargs):

        if not self.id:
            self.set_no_sql_user()

            if not self.code:
                self.code = self.get_code(self.no_sql_user)

            if not self.password:
                self.password = f'ChangeItNow{self.code}'
            self.password = make_password(self.password, salt=None, hasher='default')

            nsc = NoSQLClient()
            nsc.create_user(self.no_sql_user, self.no_sql_pass)
            facilitator_db = nsc.get_db(self.no_sql_db_name)
            nsc.add_member_to_database(facilitator_db, self.no_sql_user)

        if self.password and self.password != self.__current_password:
            self.password = make_password(self.password, salt=None, hasher='default')

        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        no_sql_db = None
        if "no_sql_db" in kwargs:
            no_sql_db = kwargs.pop("no_sql_db")
        NoSQLClient().delete_user(self.no_sql_user, no_sql_db)
        # print(f'self.no_sql_user {self.no_sql_user}')
        # print(f'no_sql_db {no_sql_db}')
        super().delete(*args, **kwargs)

    @staticmethod
    def get_code(seed):
        import zlib
        return str(zlib.adler32(str(seed).encode('utf-8')))[:6]

    def get_name(self):
        try:
            nsc = NoSQLClient()
            facilitator_database = nsc.get_db(self.no_sql_db_name)
            return facilitator_database.get_query_result(
                {"type": "facilitator"}
            )[:][0]['name']
        except Exception as e:
            return None
        
    def get_name_with_sex(self):
        try:
            nsc = NoSQLClient()
            facilitator_doc = nsc.get_db(self.no_sql_db_name).get_query_result(
                {"type": "facilitator"}
            )[:][0]
            return f"{facilitator_doc['sex']} {facilitator_doc['name']}" if facilitator_doc.get('sex') else facilitator_doc['name']
        except Exception as e:
            return None
        
    def get_email(self):
        try:
            nsc = NoSQLClient()
            facilitator_database = nsc.get_db(self.no_sql_db_name)
            return facilitator_database.get_query_result(
                {"type": "facilitator"}
            )[:][0]['email']
        except Exception as e:
            return None

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
        nsc = NoSQLClient()
        facilitator_db = nsc.get_db(self.no_sql_db_name)
        docs = facilitator_db.all_docs(include_docs=True)['rows']
        name = None
        email = None
        phone = None
        name_with_sex = None
        cvds = []

        total_tasks_completed = 0
        total_tasks_uncompleted = 0
        total_tasks = 0
        last_activity_date = "0000-00-00 00:00:00"

        for doc in docs:
            _ = doc.get('doc')
            if _.get('type') == "facilitator":
                name = _["name"]
                email = _["email"]
                phone = _["phone"]
                name_with_sex = f"{_['sex']} {_['name']}" if _.get('sex') else _['name']
                cvds = get_cvds(_)
                break
            
            
        for doc in docs:
            _ = doc.get('doc')
            if _.get('type') == "task":
                last_updated = datetime_complet_str(_.get('last_updated'))
                if last_updated and last_activity_date < last_updated:
                    last_activity_date = last_updated

                for administrative_level_cvd in cvds:
                    village = administrative_level_cvd['village']
                    if village and str(village.get("id")) == str(_["administrative_level_id"]):
                        if _.get("completed"):
                            total_tasks_completed += 1
                        else:
                            total_tasks_uncompleted += 1
                        total_tasks += 1
            

        percent = float("%.2f" % (((total_tasks_completed/total_tasks)*100) if total_tasks else 0))

        if last_activity_date == "0000-00-00 00:00:00":
            last_activity_date = None
        else:
            last_activity_date = datetime.strptime(last_activity_date, '%Y-%m-%d %H:%M:%S')
            
        return {
            "name_with_sex": name_with_sex, "username": self.username, "tel": phone, 
            'last_activity_date': last_activity_date, "percent": percent
        }
    class Meta:
        verbose_name = _('Facilitator')
        verbose_name_plural = _('Facilitators')




# def create_user(sender, instance, **kwargs):
#     print("test", instance.id, kwargs['created'], kwargs)
#     if kwargs['created']:
#         a_dict = model_to_dict(instance) #instance.__dict__
        
#         del a_dict['id']
#         del a_dict['groups']
#         del a_dict['user_permissions']
        
#         user = User.objects.using('mis').create(**a_dict)
        
#         for g in instance.groups:
#             user.groups.add(g)
#         for u_p in instance.user_permissions:
#             user.user_permissions.add(u_p)
#         user.save(using='mis')
#         # if a_dict.get('_state'):
#         #     del a_dict['_state']
#         # if a_dict.get('backend'):
#         #     del a_dict['backend']
#         # if a_dict.get('_password'):
#         #     del a_dict['_password']
        
#         # try:
#         #     User.objects.using('mis').create(**a_dict)
#         # except IntegrityError as exc:
#         #     pass
#         #     # a_dict['id'] = a_dict['id'] + 1
#         #     # is_save = False
#         #     # while not is_save:
#         #     #     print(a_dict['id'])
#         #     #     try:
#         #     #         User.objects.using('mis').update_or_create(**a_dict)
#         #     #         is_save = True
#         #     #     except IntegrityError as exc:
#         #     #         a_dict['id'] += 1
#     else:
#         print("passe 0")


# post_save.connect(create_user, sender=User)
