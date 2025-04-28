from django.conf import settings
from process_manager.models import Project, Cycle
from authentication import FACILITATORS_TYPES_PLURAL


def settings_vars(request):
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

        "CDD_URL_BASE": settings.CDD_URL_BASE,
        "MIS_URL_BASE": settings.MIS_URL_BASE,
        "GRM_URL_BASE": settings.GRM_URL_BASE,

        "FACILITATORS_TYPES_PLURAL": dict(FACILITATORS_TYPES_PLURAL)

    }
