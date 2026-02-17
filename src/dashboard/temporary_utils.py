from process_manager.models import Task, Phase, Activity
from cdd.functions import normalize_text

def update_name_normalized():
    for model in [Task, Phase, Activity]:
        for instance in model.objects.all():
            instance.name_normalized = normalize_text(instance.name)
            instance.save()


