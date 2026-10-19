from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CosoCollectConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'coso_collect'
    verbose_name = _('COSOCollect')
