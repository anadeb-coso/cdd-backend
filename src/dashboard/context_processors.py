from django.conf import settings
from django.db.models import Sum
from process_manager.models import Project, Cycle, AggregatedStatus
from authentication import FACILITATORS_TYPES_PLURAL
from administrativelevels.models import AdministrativeLevel
from cdd.call_objects_from_other_db import mis_objects_call
from subprojects.models import Project as MisProject, Cycle as MisCycle


def settings_vars(request):

    invalidation_notifications = {}
    total_tasks_waiting_validation = 0
    total_tasks_invalidated_review = 0
    total_tasks_invalidated_review_completed = 0
    total_tasks_invalidated_review_in_pending = 0
    if 'cantons_stabilized_ids' in request.session and request.session['cantons_stabilized_ids'] and request.user.groups.filter(name__in=["Supervisor"]).exists():
        projects = Project.objects.filter(users__in=[request.user.id]).prefetch_related("cycle_set")
        
        aggregated_data = (
            AggregatedStatus.objects
            .filter(
                project_id__in=[p.id for p in projects],
                cycle_id__in=[c.id for p in projects for c in p.cycle_set.all()],
                facilitator=None,
                task=None,
                administrative_level_id__in=[int(_id) for _id in request.session['cantons_stabilized_ids']]
            ).distinct()
            .values("project_id", "cycle_id")
            .annotate(
                total_tasks_waiting_validation=Sum("total_tasks_waiting_validation"),
                total_tasks_invalidated_review=Sum("total_tasks_invalidated_review"),
                total_tasks_invalidated_review_completed=Sum("total_tasks_invalidated_review_completed"),
                total_tasks_invalidated_review_in_pending=Sum("total_tasks_invalidated_review_in_pending"),
            )
        )
        aggregated_map = {
            (item["project_id"], item["cycle_id"]): item
            for item in aggregated_data
        }
        
        for project in projects:
            
            invalidation_notifications[project.name] = {'project_id': project.name}

            for cycle in project.cycle_set.all():

                invalidation_notifications[project.name][cycle.name] = {'cycle_id': cycle.name}
                
                invalidation_notifications[project.name][cycle.name]['total_tasks_waiting_validation'] = aggregated_map.get((project.id, cycle.id), {}).get('total_tasks_waiting_validation') or 0
                invalidation_notifications[project.name][cycle.name]['total_tasks_invalidated_review'] = aggregated_map.get((project.id, cycle.id), {}).get('total_tasks_invalidated_review') or 0
                invalidation_notifications[project.name][cycle.name]['total_tasks_invalidated_review_completed'] = aggregated_map.get((project.id, cycle.id), {}).get('total_tasks_invalidated_review_completed') or 0
                invalidation_notifications[project.name][cycle.name]['total_tasks_invalidated_review_in_pending'] = aggregated_map.get((project.id, cycle.id), {}).get('total_tasks_invalidated_review_in_pending') or 0
                
                total_tasks_waiting_validation += invalidation_notifications[project.name][cycle.name]['total_tasks_waiting_validation']
                total_tasks_invalidated_review += invalidation_notifications[project.name][cycle.name]['total_tasks_invalidated_review']
                total_tasks_invalidated_review_completed += invalidation_notifications[project.name][cycle.name]['total_tasks_invalidated_review_completed']
                total_tasks_invalidated_review_in_pending += invalidation_notifications[project.name][cycle.name]['total_tasks_invalidated_review_in_pending']


    return {
        'OTHER_LANGUAGES': settings.OTHER_LANGUAGES,
        'DOMAIN_PATH': ("http://" if "127." in request.get_host() else "https://") + (request.get_host()),

        "PROJECT_ID": request.session.get('project_id'),
        "PROJECT_NAME": request.session.get('project_name'),
        "PROJECT_COUCH_ID": request.session.get('project_couch_id'),
        
        "PROJECT_MIS_ID": request.session.get('project_mis_id'),

        "CYCLE_ID": request.session.get('cycle_id'),
        "CYCLE_NAME": request.session.get('cycle_name'),
        "CYCLE_COUCH_ID": request.session.get('cycle_couch_id'),
        
        "CYCLE_MIS_ID": request.session.get('cycle_mis_id'),
        
        "PROJECTS": Project.objects.filter(users__in=[request.user.id]) if request.user.is_authenticated else [],
        "CYCLES": Cycle.objects.filter(project_id=request.session.get('project_id')),

        "PROJECTS_IDS": request.session.get('tree_structure_projects_ids'),
        "PROJECTS_NAMES": request.session.get('tree_structure_projects_names'),
        "PROJECTS_MIS_IDS": request.session.get('tree_structure_projects_mis_ids'),
        
        "CDD_URL_BASE": settings.CDD_URL_BASE,
        "MIS_URL_BASE": settings.MIS_URL_BASE,
        "GRM_URL_BASE": settings.GRM_URL_BASE,

        "FACILITATORS_TYPES_PLURAL": dict(FACILITATORS_TYPES_PLURAL),

        "INVALIDATION_NOTIFICATIONS": invalidation_notifications,
        "TOTAL_TASKS_WAITING_VALIDATION": total_tasks_waiting_validation,
        "TOTAL_TASKS_INVALIDATED_REVIEW": total_tasks_invalidated_review,
        "TOTAL_TASKS_INVALIDATED_REVIEW_COMPLETED": total_tasks_invalidated_review_completed,
        "TOTAL_TASKS_INVALIDATED_REVIEW_IN_PENDING": total_tasks_invalidated_review_in_pending

    }
