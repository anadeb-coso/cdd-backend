from django.conf import settings


def settings_vars(request):
    return {
        'OTHER_LANGUAGES': settings.OTHER_LANGUAGES,
        'DOMAIN_PATH': ("http://" if "127." in request.get_host() else "https://") + (request.get_host())
    }
