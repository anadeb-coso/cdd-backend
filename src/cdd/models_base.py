from django.db import models
from django.forms.models import model_to_dict


# Create your models here.
class BaseModel(models.Model):
    created_date = models.DateTimeField(auto_now_add = True, blank=True, null=True)
    updated_date = models.DateTimeField(auto_now = True, blank=True, null=True)
    create_by_user = models.JSONField(blank=True, null=True)
    update_by_user = models.JSONField(blank=True, null=True)
    users_involved = models.JSONField(blank=True, null=True)

    class Meta:
        abstract = True
    
    def save_and_return_object(self, user=None, force_insert=False, force_update=False, using=None, update_fields=None):
        return self.users_history(user, force_insert, force_update, using, update_fields)
    
    def save(self, force_insert=False, force_update=False, using=None, update_fields=None, user=None):
        self.users_history(user, force_insert, force_update, using, update_fields)
            
    
    def users_history(self, user, force_insert=False, force_update=False, using=None, update_fields=None):
        """
        Save users stories
        user_json = {
            "type": "facilitator", # or user
            "date": self.updated_date,
            "data": self
        }
        """
        # if user:
        # user_json = user.__dict__ if user else {'is_superuser': True}
        # self_json = self.__dict__

        # if user_json.get('is_superuser'):
        #     user_json['type'] = "user"
        # else:
        #     user_json['type'] = "facilitator"
        # user_json['date'] = self.updated_date
        # user_json['data'] = self_json


        # users_involved = self.users_involved if self.users_involved else []

        # if self.created_date == self.updated_date:
        #     self.create_by_user = user_json
            
        # self.update_by_user = user_json
        
        # users_involved.append(user_json)

        # self.users_involved = users_involved

        super().save(force_insert, force_update, using, update_fields)

        return self




class CustomQuerySet(models.QuerySet):
    
    def get_objects_by_general_filtre(self, request, attrs, *args, **kwargs):
        if self.first():
            if self.first().__class__.__name__ in ["Phase", "Activity", "Task"]:
                return self.get_process_manager_actifs(request, attrs, *args, **kwargs)
            elif self.first().__class__.__name__ in ["AdministrativeLevel"]:
                return self.get_adl_actifs(request, attrs, *args, **kwargs)
        return self.filter()
    
    def get_adl_actifs(self, request, attrs, *args, **kwargs):
        if attrs:
            if 'project_id' in attrs:
                attrs['administrative_levels_projects__in'] = [attrs.get('project_id')]
                del attrs['project_id']
            if 'cycle_id' in attrs:
                attrs['administrative_levels_cycles__in'] = [attrs.get('cycle_id')]
                del attrs['cycle_id']
            return self.filter(**attrs)
        else:
            return self.filter(
                administrative_levels_projects__in=[request.session.get('project_mis_id')], 
                administrative_levels_cycles__in=[request.session.get('cycle_mis_id')]
            )
    
    def get_process_manager_actifs(self, request, attrs, *args, **kwargs):
        if attrs:
            if 'cycle_id' in attrs:
                attrs['cycles__in'] = [attrs.get('cycle_id')]
                del attrs['cycle_id']
            return self.filter(**attrs)
        else:
            return self.filter(project_id=request.session.get('project_id'), cycles__in=[request.session.get('cycle_id')])