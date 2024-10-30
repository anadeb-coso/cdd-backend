from process_manager.models import Task, Phase, Activity

def get_cascade_phase_activity_task_by_their_id(phase_id, activity_id, task_id, project_id, show_all_if_none=True):

    if activity_id and phase_id: 
        phase = Phase.objects.get(id=phase_id)
        activity = Activity.objects.get(id=activity_id)
        phases = Phase.objects.filter(project_id=project_id).order_by("order")
        activies = phase.activity_set.get_queryset().order_by("phase__order", "order")
        tasks = activity.task_set.get_queryset().order_by("phase__order", "activity__order", "order")
    elif phase_id:
        phase = Phase.objects.get(id=phase_id)
        phases = Phase.objects.filter(project_id=project_id).order_by("order")
        activies = phase.activity_set.get_queryset().order_by("phase__order", "order")
        tasks = phase.task_set.get_queryset().order_by("phase__order", "activity__order", "order")
    elif activity_id:
        activity = Activity.objects.get(id=activity_id)
        phases = Phase.objects.filter(project_id=project_id).order_by("order")
        activies = Activity.objects.filter(project_id=project_id).order_by("phase__order", "order")
        tasks = activity.task_set.get_queryset().order_by("phase__order", "activity__order", "order")
    else:
        if show_all_if_none:
            phases = Phase.objects.filter(project_id=project_id).order_by("order")
            activies = Activity.objects.filter(project_id=project_id).order_by("phase__order", "order")
            tasks = Task.objects.filter(project_id=project_id).order_by("phase__order", "activity__order", "order")
        else:
            phases = []
            activies = []
            tasks = []

    datas = {'phases': [], 'activities': [], 'tasks': []}

    for p in phases:
        datas['phases'].append((p.id, p.name))
    
    for a in activies:
        datas['activities'].append((a.id, a.name))
    
    for t in tasks:
        datas['tasks'].append((t.id, t.name))

    return datas
