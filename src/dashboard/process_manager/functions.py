from process_manager.models import Task, Phase, Activity

def get_cascade_phase_activity_task_by_their_id(phase_id, activity_id, task_id, project_id, cycle_id, show_all_if_none=True):

    if activity_id and phase_id: 
        _phases = Phase.objects.filter(id__in=phase_id if type(phase_id) is list else [phase_id])
        _activities = Activity.objects.filter(id__in=activity_id if type(activity_id) is list else [activity_id])
        phases = Phase.objects.get_objects_by_general_filtre(request=None, attrs={'project_id': project_id, 'cycle_id': cycle_id}).order_by("order")
        activities = [elem for sous_liste in [_phase.activity_set.get_queryset().order_by("phase__order", "order") for _phase in _phases] for elem in sous_liste]
        tasks = [elem for sous_liste in [_activity.task_set.get_queryset().order_by("phase__order", "activity__order", "order") for _activity in _activities] for elem in sous_liste]
    
    elif phase_id:
        _phases = Phase.objects.filter(id__in=phase_id if type(phase_id) is list else [phase_id])
        phases = Phase.objects.get_objects_by_general_filtre(request=None, attrs={'project_id': project_id, 'cycle_id': cycle_id}).order_by("order")
        activities = [elem for sous_liste in [_phase.activity_set.get_queryset().order_by("phase__order", "order") for _phase in _phases] for elem in sous_liste]
        tasks = [elem for sous_liste in [_phase.task_set.get_queryset().order_by("phase__order", "activity__order", "order") for _phase in _phases] for elem in sous_liste]
        
    elif activity_id:
        _activities = Activity.objects.filter(id__in=activity_id if type(activity_id) is list else [activity_id])
        phases = Phase.objects.get_objects_by_general_filtre(request=None, attrs={'project_id': project_id, 'cycle_id': cycle_id}).order_by("order")
        activities = Activity.objects.get_objects_by_general_filtre(request=None, attrs={'project_id': project_id, 'cycle_id': cycle_id}).order_by("phase__order", "order")
        tasks = [elem for sous_liste in [_activity.task_set.get_queryset().order_by("phase__order", "activity__order", "order") for _activity in _activities] for elem in sous_liste]
        
    else:
        if show_all_if_none:
            phases = Phase.objects.get_objects_by_general_filtre(request=None, attrs={'project_id': project_id, 'cycle_id': cycle_id}).order_by("order")
            activities = Activity.objects.get_objects_by_general_filtre(request=None, attrs={'project_id': project_id, 'cycle_id': cycle_id}).order_by("phase__order", "order")
            tasks = Task.objects.get_objects_by_general_filtre(request=None, attrs={'project_id': project_id, 'cycle_id': cycle_id}).order_by("phase__order", "activity__order", "order")
        else:
            phases = []
            activities = []
            tasks = []

    datas = {'phases': [], 'activities': [], 'tasks': []}

    for p in phases:
        datas['phases'].append((p.id, p.name))
    
    for a in activities:
        datas['activities'].append((a.id, a.name))
    
    for t in tasks:
        datas['tasks'].append((t.id, t.name))

    return datas
