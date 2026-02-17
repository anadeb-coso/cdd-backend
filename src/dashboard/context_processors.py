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
    if 'cantons_stabilized_ids' in request.session and request.user.groups.filter(name__in=["Supervisor"]).exists():
        for project in Project.objects.filter(users__in=[request.user.id]):
            
            project_mis = mis_objects_call.filter_objects(MisProject, name=project.name)
            project_mis_id = project_mis.first().id if project_mis.count() >= 1 else 1
            invalidation_notifications[project.name] = {'project_id': project.name}

            for cycle in project.cycle_set.all():

                invalidation_notifications[project.name][cycle.name] = {'cycle_id': cycle.name}
                cycle_mis = mis_objects_call.filter_objects(MisCycle, order=cycle.order, project_id=project_mis_id)
                cycle_mis_id = cycle_mis.first().id if cycle_mis.exists() else None
                
                aggregated_status_project = AggregatedStatus.objects.filter(
                    project_id=project.id, facilitator=None, task=None,
                    administrative_level_id__in=list(mis_objects_call.filter_objects(
                        AdministrativeLevel, 
                        id__in=request.session['cantons_stabilized_ids'], 
                        administrative_levels_projects__in=[project_mis_id], 
                        administrative_levels_cycles__in=[cycle_mis_id]).values_list('id', flat=True)
                    )
                ).aggregate(
                    total_tasks_waiting_validation=Sum('total_tasks_waiting_validation'),
                    total_tasks_invalidated_review=Sum('total_tasks_invalidated_review')
                )
                
                invalidation_notifications[project.name][cycle.name]['total_tasks_waiting_validation'] = aggregated_status_project['total_tasks_waiting_validation'] or 0
                invalidation_notifications[project.name][cycle.name]['total_tasks_invalidated_review'] = aggregated_status_project['total_tasks_invalidated_review'] or 0
                
                total_tasks_waiting_validation += invalidation_notifications[project.name][cycle.name]['total_tasks_waiting_validation']
                total_tasks_invalidated_review += invalidation_notifications[project.name][cycle.name]['total_tasks_invalidated_review']


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
        "TOTAL_TASKS_INVALIDATED_REVIEW": total_tasks_invalidated_review

    }
