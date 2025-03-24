from django.conf import settings
from process_manager.models import Project
from authentication import FACILITATORS_TYPES_PLURAL


def settings_vars(request):
    return {
        'OTHER_LANGUAGES': settings.OTHER_LANGUAGES,
        'DOMAIN_PATH': ("http://" if "127." in request.get_host() else "https://") + (request.get_host()),

        "PROJECT_ID": request.session.get('project_id'),
        "PROJECT_NAME": request.session.get('project_name'),
        "PROJECT_COUCH_ID": request.session.get('project_couch_id'),
        
        "PROJECTS": Project.objects.all(),

        "CDD_URL_BASE": settings.CDD_URL_BASE,
        "MIS_URL_BASE": settings.MIS_URL_BASE,
        "GRM_URL_BASE": settings.GRM_URL_BASE,

        "FACILITATORS_TYPES_PLURAL": dict(FACILITATORS_TYPES_PLURAL)

    }
