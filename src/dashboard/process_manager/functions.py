from process_manager.models import Task, Phase, Activity

def get_cascade_phase_activity_task_by_their_id(phase_id, activity_id, task_id):

    if activity_id and phase_id:
        phase = Phase.objects.get(id=phase_id)
        activity = Activity.objects.get(id=activity_id)
        phases = Phase.objects.all().order_by("order")
        activies = phase.activity_set.get_queryset().order_by("phase__order", "order")
        tasks = activity.task_set.get_queryset().order_by("phase__order", "activity__order", "order")
    elif phase_id:
        phase = Phase.objects.get(id=phase_id)
        phases = Phase.objects.all().order_by("order")
        activies = phase.activity_set.get_queryset().order_by("phase__order", "order")
        tasks = phase.task_set.get_queryset().order_by("phase__order", "activity__order", "order")
    elif activity_id:
        activity = Activity.objects.get(id=activity_id)
        phases = Phase.objects.all().order_by("order")
        activies = Activity.objects.all().order_by("phase__order", "order")
        tasks = activity.task_set.get_queryset().order_by("phase__order", "activity__order", "order")
    else:
        phases = Phase.objects.all().order_by("order")
        activies = Activity.objects.all().order_by("phase__order", "order")
        tasks = Task.objects.all().order_by("phase__order", "activity__order", "order")

    datas = {'phases': [], 'activities': [], 'tasks': []}

    for p in phases:
        datas['phases'].append((p.id, p.name))
    
    for a in activies:
        datas['activities'].append((a.id, a.name))
    
    for t in tasks:
        datas['tasks'].append((t.id, t.name))

    return datas
