import secrets
import time
from datetime import datetime

from django.contrib.auth.hashers import make_password
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models import Q

from no_sql_client import NoSQLClient
# from dashboard.facilitators.functions import get_cvds
from cdd.functions import datetime_complet_str
from django.contrib.auth.models import User, AbstractUser, Permission, Group
# from django.db import IntegrityError
# from django.forms.models import model_to_dict
from authentication import FACILITATORS_TYPES
from cdd.models_base import BaseModel

class Facilitator(BaseModel):
    no_sql_user = models.CharField(max_length=150, unique=True)
    no_sql_pass = models.CharField(max_length=128)
    no_sql_db_name = models.CharField(max_length=150, unique=True)
    no_sql_dbs_names = models.JSONField(null=True, blank=True)
    username = models.CharField(max_length=150, unique=True, verbose_name=_('username'))
    password = models.CharField(max_length=128, verbose_name=_('password'))
    code = models.CharField(max_length=100, unique=True, verbose_name=_('code'))
    active = models.BooleanField(default=False, verbose_name=_('active'))
    develop_mode = models.BooleanField(default=False, verbose_name=_('develop mode'))
    training_mode = models.BooleanField(default=False, verbose_name=_('test mode'))
    administrative_levels = models.JSONField(null=True, blank=True)
    administrative_levels_ids = models.JSONField(null=True, blank=True)
    stabilization_administrative_ids = models.JSONField(null=True, blank=True)
    additional_administrative_ids = models.JSONField(null=True, blank=True)
    # Choix tels que saisis (page « Localités » de CDD ou fiche EADL du GRM), avant calcul des villages
    # stockés ci-dessus : niveau principal de l'EADL (1er choisi, de tout type ; "1" = TOGO) et niveaux
    # choisis (régions, préfectures, communes, cantons, villages). Miroir de GovernmentWorker.administrative_id
    # et Adl.administrative_region_ids / additional_administrative_region_ids côté GRM.
    main_administrative_id = models.CharField(max_length=255, null=True, blank=True)
    stabilization_administrative_choices = models.JSONField(null=True, blank=True)
    additional_administrative_choices = models.JSONField(null=True, blank=True)

    facilitator_type = models.CharField(max_length=100, choices=FACILITATORS_TYPES, default='community_facilitator')

    # Compte Django permettant à ce Facilitator de se connecter au Web DCC
    # (accès limité à quelques menus, cf. sidebar.html + PROFESSIONAL_GROUPS
    # "CommunityFacilitator"/"TechnicalFacilitator"). Nullable : les
    # Facilitators déjà en base n'ont pas encore de User associé tant que la
    # commande `link_facilitators_to_users` n'a pas tourné, et un
    # rattachement peut être perdu (`SET_NULL`) sans supprimer le Facilitator
    # si son User est supprimé côté admin Django. Peuplé/maintenu par
    # `authentication.functions.ensure_facilitator_user`, appelée à la
    # création et à la modification d'un Facilitator (dashboard/facilitators/views.py).
    user = models.OneToOneField(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="facilitator",
    )

    name = models.CharField(max_length=200, null=True, blank=True, verbose_name=_('name'))
    email = models.CharField(max_length=100, null=True, blank=True, verbose_name=_('email'))
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
    total_tasks_invalidated_review_completed_current_project = None
    total_tasks_invalidated_review_in_pending_current_project = None
    total_tasks_invalidated_unreview_current_project = None
    total_tasks_invalidated_unreview_completed_current_project = None
    total_tasks_invalidated_unreview_in_pending_current_project = None
    total_tasks_waiting_validation_current_project = None

    total_tasks_validated_stabilized = None
    total_tasks_invalidated_stabilized = None
    total_tasks_invalidated_review_stabilized = None
    total_tasks_invalidated_review_completed_stabilized = None
    total_tasks_invalidated_review_in_pending_stabilized = None
    total_tasks_invalidated_unreview_stabilized = None
    total_tasks_invalidated_unreview_completed_stabilized = None
    total_tasks_invalidated_unreview_in_pending_stabilized = None
    total_tasks_waiting_validation_stabilized = None
    
    total_tasks_validated = None
    total_tasks_invalidated = None
    total_tasks_invalidated_review = None
    total_tasks_invalidated_review_completed = None
    total_tasks_invalidated_review_in_pending = None
    total_tasks_invalidated_unreview = None
    total_tasks_invalidated_unreview_completed = None
    total_tasks_invalidated_unreview_in_pending = None
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
        now = int(time.time())

        # Added to avoid repeating the same value for no_sql_user when bulk creating facilitators.
        # Le code (`get_code`, adler32 de cet identifiant) doit lui aussi être libre : adler32 de deux horodatages
        # coïncide souvent (une seconde sur dix environ avec les ~240 codes en base), et la création échouait alors
        # sur la contrainte d'unicité de `code`. On prend la seconde suivante plutôt que d'attendre l'horloge.
        while (Facilitator.objects.filter(no_sql_user=str(now)).exists()
               or Facilitator.objects.filter(code=self.get_code(str(now))).exists()):
            now += 1

        self.no_sql_user = str(now)

    def simple_save(self, *args, **kwargs):
        return super().save(*args, **kwargs)
    
    def save_and_return_object(self, *args, **kwargs):
        if "user" in kwargs:
            user = kwargs.pop("user")
            self.users_history(user)
        super().save(*args, **kwargs)
        return self

    def save(self, *args, **kwargs):
        replicate_design = True
        if "replicate_design" in kwargs:
            replicate_design = kwargs.pop("replicate_design")
        if "user" in kwargs:
            user = kwargs.pop("user")
            self.users_history(user)

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

        super().save(*args, **kwargs)
        
        return self

    # def users_history(self, user):
    #     """
    #     Save users stories
    #     user_json = {
    #         "type": "facilitator", # or user
    #         "date": self.updated_date,
    #         "data": self
    #     }
    #     """
        
    #     # user_json = user.__dict__ if user else {'is_superuser': True}
    #     # self_json = self.__dict__

    #     # if user_json.get('is_superuser'):
    #     #     user_json['type'] = "user"
    #     # else:
    #     #     user_json['type'] = "facilitator"
    #     # user_json['date'] = self.updated_date
    #     # user_json['data'] = self_json


    #     # users_involved = self.users_involved if self.users_involved else []

    #     # if self.created_date == self.updated_date:
    #     #     self.create_by_user = user_json
            
    #     # self.update_by_user = user_json
        
    #     # users_involved.append(user_json)

    #     # self.users_involved = users_involved

    #     super().save()


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
        return str(zlib.adler32(str(seed).encode('utf-8'))) #[:6]

    @property
    def is_active(self):
        return self.active
        
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
        
        _percent_current_project = self.total_tasks_completed_current_project/self.total_tasks_current_project if self.total_tasks_current_project else 0
        percent_current_project = float("%.2f" % ((_percent_current_project if _percent_current_project else 0)*100))
        
        _percent_stabilized = self.total_tasks_completed_stabilized/self.total_tasks_stabilized if self.total_tasks_stabilized else 0
        percent_stabilized = float("%.2f" % ((_percent_stabilized if _percent_stabilized else 0)*100))
        
        _percent = self.total_tasks_completed/self.total_tasks if self.total_tasks else 0
        percent = float("%.2f" % ((_percent if _percent else 0)*100))

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
            no_sql_dbs_names__contains=[self.no_sql_db_name]
        )
    
    def get_headquarters_village(self):
        if self.administrative_levels:
            return list(set([
                adl['name'] for adl in self.administrative_levels if adl.get('is_headquarters_village')
            ]))
        return []
        
        
    # def get_all_infos(self):
    #     import json
    #     nsc = NoSQLClient()
    #     facilitator_db = nsc.get_db(self.no_sql_db_name)


    #     _percent = 0
    #     last_activity_date = "0000-00-00 00:00:00"
        
    #     try:
    #         tasks_infos = json.loads(facilitator_db.get_list_function_result("_design/tasks_number", "completed_to_total_ratio", "tasks"))

    #         _percent = tasks_infos.get('percent')
    #         _last_activity_date = tasks_infos.get('last_activity_date')
    #     except:
    #         _percent = 0
    #         _last_activity_date = "0000-00-00 00:00:00"
        
    #     if _last_activity_date and _last_activity_date != "0000-00-00 00:00:00":
    #         last_activity_date = datetime.strptime(_last_activity_date, '%Y-%m-%d %H:%M:%S')
    #     else:
    #         last_activity_date = None
            

    #     percent = float("%.2f" % ((_percent if _percent else 0)*100))

    #     return {
    #         "name": self.name, "sex": "F" if self.sex == "Mme" else "M", "username": self.username, "tel": self.phone, 
    #         'last_activity_date': last_activity_date, "percent": percent, 
    #         "cvd": f"{self.cvds_number}/{self.villages_number}"
    #     }
    
    # def get_all_infos(self):
    #     nsc = NoSQLClient()
    #     facilitator_db = nsc.get_db(self.no_sql_db_name)

    #     name = None
    #     email = None
    #     sex = None
    #     phone = None
    #     name_with_sex = None
    #     cvds = []

    #     total_tasks_completed = 0
    #     total_tasks_uncompleted = 0
    #     total_tasks = 0
    #     last_activity_date = "0000-00-00 00:00:00"
        
    #     ok = True
    #     try:
    #         total_tasks_completed = facilitator_db.get_view_result('tasks_number', 'tasks_completed')[:][0]['value']
    #     except:
    #         total_tasks_completed = 0
        
    #     try:
    #         total_tasks = facilitator_db.get_view_result('tasks_number', 'tasks_total')[:][0]['value']
    #     # print(facilitator_db.get_view_result('tasks_number', 'last_activities_on_numbers')[:][0]['value'])
    #     except:
    #         total_tasks = 0
    #     #     ok = False

    #     # if self.show_last_activity:
    #     #     try:
    #     #         last_activities_date = facilitator_db.get_view_result('tasks_number', 'last_activities')[:]
    #     #         for _d in last_activities_date:
    #     #             _last_updated = datetime_complet_str(_d['value'])
    #     #             if _last_updated and last_activity_date < _last_updated:
    #     #                 last_activity_date = _last_updated
    #     #     except:
    #     #         pass
    #     #     print(last_activities_date)

    #     if ok:
    #         # query_result = facilitator_db.get_query_result({
    #         #     "type": 'facilitator'
    #         #     })[:]
    #         # if query_result:
    #         #     _ = query_result[0]
    #         #     name = _["name"]
    #         #     sex = _["sex"]
    #         #     email = _["email"]
    #         #     phone = _["phone"]
    #         #     name_with_sex = f"{_['sex']} {_['name']}" if _.get('sex') else _['name']
    #         #     cvds = get_cvds(_)
    #         # for assign in get_assign_adl_by_facilitatr(self.id, project_id=1, activated=True):
    #         #     adl = mis_objects_call.filter_objects(AdministrativeLevel, id=assign.administrative_level_id).first()
    #         #     if adl and adl.cvd:
    #         #         cvds.append(adl.cvd)
    #         pass
    #     else:
    #         # docs = facilitator_db.all_docs(include_docs=True)['rows']
    #         # for doc in docs:
    #         #     _ = doc.get('doc')
    #         #     if _.get('type') == "facilitator":
    #         #         name = _["name"]
    #         #         email = _["email"]
    #         #         phone = _["phone"]
    #         #         name_with_sex = f"{_['sex']} {_['name']}" if _.get('sex') else _['name']
    #         #         cvds = get_cvds(_)
    #         #         break

    #         # for doc in docs:
    #         #     _ = doc.get('doc')
    #         #     if _.get('type') == "task":
    #         #         last_updated = datetime_complet_str(_.get('last_updated'))
    #         #         if last_updated and last_activity_date < last_updated:
    #         #             last_activity_date = last_updated

    #         #         for administrative_level_cvd in cvds:
    #         #             village = administrative_level_cvd['village']
    #         #             if village and str(village.get("id")) == str(_["administrative_level_id"]):
    #         #                 if _.get("completed"):
    #         #                     total_tasks_completed += 1
    #         #                 else:
    #         #                     total_tasks_uncompleted += 1
    #         #                 total_tasks += 1
    #         pass
            
            

    #     percent = float("%.2f" % (((total_tasks_completed/total_tasks)*100) if total_tasks else 0))

    #     if last_activity_date == "0000-00-00 00:00:00":
    #         last_activity_date = None
    #     else:
    #         last_activity_date = datetime.strptime(last_activity_date, '%Y-%m-%d %H:%M:%S')
        
    #     return {
    #         "name": self.name, "sex": "F" if self.sex == "Mme" else "M", "username": self.username, "tel": self.phone, 
    #         'last_activity_date': last_activity_date, "percent": percent, 
    #         # "cvd": f"{len(cvds)}/{sum([len(cvd['villages']) for cvd in cvds])}"
    #         # "cvd": "11"
    #     }

    
    class Meta:
        verbose_name = _('Facilitator')
        verbose_name_plural = _('Facilitators')


class UserLocalities(models.Model):
    """Localités d'intervention d'un utilisateur du dashboard (superviseurs surtout), copiées par email
    avec le GRM (GovernmentWorker.administrative_id/administrative_ids/additional_administrative_ids du
    compte GRM de même email). Pas d'enregistrement, ou aucun choix : superviseur = aucune localité,
    autres utilisateurs = tout le pays. `administrative_id` "1" (TOGO) = tout le pays."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='intervention_localities')
    administrative_id = models.CharField(max_length=255, null=True, blank=True)
    administrative_choices = models.JSONField(null=True, blank=True)
    additional_administrative_choices = models.JSONField(null=True, blank=True)
    village_ids = models.JSONField(null=True, blank=True)
    additional_village_ids = models.JSONField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        verbose_name = _('User localities')
        verbose_name_plural = _('Users localities')


class LocalityHistory(models.Model):
    """Trajet des facilitateurs et utilisateurs : une ligne par changement de localités (affectation,
    stabilisation, additionnelles, intervention), avec l'état avant/après, qui et d'où. Ajout seulement."""
    SECTIONS = (
        ('assignment', _('Assignment villages')),
        ('stabilization', _('Stabilization villages')),
        ('additional', _('Additional villages')),
        ('intervention', _('Intervention localities')),
        ('intervention_additional', _('Additional intervention localities')),
    )
    SOURCES = (
        ('localities_page', _('Localities page')),
        ('facilitator_form', _('Facilitator form')),
        ('facilitator_creation', _('Facilitator creation')),
        ('user_localities_page', _('User localities page')),
        ('grm', _('GRM')),
        ('mis_import', _('Imported from the MIS assignments')),
        ('initial_state', _('Initial state')),
        ('couchdb_rebuild', _('Rebuilt from CouchDB')),
        ('excel_import', _('Excel import')),
    )
    facilitator = models.ForeignKey(Facilitator, null=True, blank=True, on_delete=models.SET_NULL, related_name='localities_history')
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='localities_history')
    # copies : l'historique reste lisible si le facilitateur/l'utilisateur est supprimé
    email = models.CharField(max_length=150, null=True, blank=True)
    name = models.CharField(max_length=200, null=True, blank=True)
    section = models.CharField(max_length=30, choices=SECTIONS)
    main_before = models.CharField(max_length=255, null=True, blank=True)
    main_after = models.CharField(max_length=255, null=True, blank=True)
    choices_before = models.JSONField(null=True, blank=True)
    choices_after = models.JSONField(null=True, blank=True)
    # None avant = état antérieur inconnu (1re définition ou état initial constaté)
    villages_before = models.JSONField(null=True, blank=True)
    villages_after = models.JSONField(default=list, blank=True)
    added = models.JSONField(default=list, blank=True)
    removed = models.JSONField(default=list, blank=True)
    project_id = models.IntegerField(null=True, blank=True)
    source = models.CharField(max_length=30, choices=SOURCES)
    changed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    changed_by_label = models.CharField(max_length=200, null=True, blank=True)
    changed_at = models.DateTimeField(db_index=True)
    # dates reconstituées (import des affectations du SIG : date de désaffectation = dernière modification)
    approximate_date = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Locality history')
        verbose_name_plural = _('Localities history')
        ordering = ['-changed_at', '-id']
        indexes = [
            models.Index(fields=['facilitator', 'changed_at']),
            models.Index(fields=['user', 'changed_at']),
        ]


class PasswordChangeRequirement(models.Model):
    """Mot de passe initial à changer à la première connexion, quelle que soit la plateforme (DCC web et mobile,
    MGP web et mobile, SIG). Une ligne par compte créé dans le DCC (utilisateur web ou facilitateur), reconnue
    par l'e-mail (en minuscules, commun aux trois plateformes) et, sans e-mail, par le compte lui-même. Un
    changement de mot de passe fait sur une plateforme vaut pour toutes : `changed_at` est alors renseigné sur
    toutes les lignes de la personne (cf. authentication/accounts.py).

    Lue aussi par le SIG (même base) et par le MGP (connexion `mis` vers cette base) en SQL brut : ne pas
    renommer la table ni les colonnes `email`, `user_id`, `changed_at`."""
    email = models.CharField(max_length=254, null=True, blank=True, db_index=True)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name='+')
    facilitator = models.ForeignKey(Facilitator, null=True, blank=True, on_delete=models.CASCADE, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    changed_at = models.DateTimeField(null=True, blank=True)
    # plateforme du changement : dcc_web, dcc_mobile, mgp_web, mgp_mobile, sig_web, profile, password_reset
    changed_on = models.CharField(max_length=30, null=True, blank=True)

    class Meta:
        db_table = 'authentication_passwordchangerequirement'
        verbose_name = _('Password change requirement')
        verbose_name_plural = _('Password change requirements')


class PlatformAccessToken(models.Model):
    """Jeton de session du mobile DCC, valable sur les trois plateformes (DCC, SIG, MGP) : délivré par le DCC à la
    connexion (authentication/platform_tokens.py), puis envoyé à chaque appel à la place du mot de passe. Seule son
    empreinte SHA-256 est rangée. Il ne vaut plus après sa date d'expiration, sa révocation (déconnexion,
    renouvellement) ou un changement du mot de passe du compte (empreinte du hash du mot de passe différente).

    Lue aussi par le SIG (même base) et par le MGP (connexion `mis` vers cette base) en SQL brut : ne pas renommer la
    table ni les colonnes `key_hash`, `account_kind`, `account_id`, `email`, `password_fingerprint`, `expires_at`,
    `revoked_at`, `last_used_at`."""
    KIND_FACILITATOR = 'facilitator'
    KIND_USER = 'user'

    key_hash = models.CharField(max_length=64, unique=True)
    account_kind = models.CharField(max_length=12, choices=[(KIND_FACILITATOR, 'Facilitator'), (KIND_USER, 'User')])
    account_id = models.IntegerField()
    # compte MGP de la même personne (e-mail en minuscules)
    email = models.CharField(max_length=254, blank=True, default='')
    username = models.CharField(max_length=150, blank=True, default='')
    password_fingerprint = models.CharField(max_length=64)
    client = models.CharField(max_length=50, default='dcc_mobile')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'authentication_platformaccesstoken'
        indexes = [models.Index(fields=['account_kind', 'account_id'], name='auth_platformtoken_account')]
        verbose_name = _('Platform access token')
        verbose_name_plural = _('Platform access tokens')




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


# Ancien signal `post_delete` `delete_user` retiré : il re-supprimait le compte via l'alias `mis`.
# Depuis la fusion cdd + cosomis, `mis` est la MÊME base que `default` (cdd/settings.py) : la copie
# n'existe plus, et cette seconde connexion attendait les verrous de la suppression en cours sur
# `default` (transaction encore ouverte, elle-même en attente du signal) — interblocage que
# PostgreSQL ne détecte pas, la suppression d'un utilisateur ne se terminait jamais.