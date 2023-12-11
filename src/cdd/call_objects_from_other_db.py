from typing import (
    Any,
)
from django.db.models import Model

class CallObjects:
    def __init__(self, using) -> None:
        self.using = using

    def get_all_objects(self, Type: type):
        return Type.objects.using(self.using).all()

    def filter_objects(self, Type: type, *args: Any, **kwargs: Any):
        return Type.objects.using(self.using).filter(*args, **kwargs)

    def get_object(self, Type: type, *args: Any, **kwargs: Any):
        return Type.objects.using(self.using).get(*args, **kwargs)

    def save_object(self, Type: type, object_to_save: Model):
        return object_to_save.save(self.using)

    def delete_object(self, Type: type, object_to_save: Model):
        return object_to_save.delete(self.using)



mis_objects_call = CallObjects('mis')