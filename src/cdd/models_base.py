from django.db import models


# Create your models here.
class BaseModel(models.Model):
    created_date = models.DateTimeField(auto_now_add = True, blank=True, null=True)
    updated_date = models.DateTimeField(auto_now = True, blank=True, null=True)
    create_by_user = models.JSONField(blank=True, null=True)
    update_by_user = models.JSONField(blank=True, null=True)
    users_involved = models.JSONField(blank=True, null=True)

    class Meta:
        abstract = True
    
    def save_and_return_object(self, user=None):
        super().save()
        if user:
            self.users_history(user)
            

        return self
    
    def save(self, force_insert=False, force_update=False, using=None, update_fields=None, user=None):
        super().save(force_insert, force_update, using, update_fields)
        if user:
            self.users_history(user)


    
    def users_history(self, user):
        """
        Save users stories
        user_json = {
            "type": "facilitator", # or user
            "date": self.updated_date,
            "data": self
        }
        """
        
        user_json = user.__dict__ if user else {'is_superuser': True}
        self_json = self.__dict__

        if user_json.get('is_superuser'):
            user_json['type'] = "user"
        else:
            user_json['type'] = "facilitator"
        user_json['date'] = self.updated_date
        user_json['data'] = self_json


        users_involved = self.users_involved if self.users_involved else []

        if self.created_date == self.updated_date:
            self.create_by_user = user_json
            
        self.update_by_user = user_json
        
        users_involved.append(user_json)

        self.users_involved = users_involved

        super().save()