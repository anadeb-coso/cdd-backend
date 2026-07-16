from cdd.functions import times_split
from django.utils.translation import gettext_lazy as _



TIMES = tuple([(t, t) for t in times_split()])
DAYS = tuple([(d, d) for d in range(7)])
WORK_ENVIRONMENT = (
    ('Office', _('Office')),
    ('Field', _('Field')),
    ('Hotel/Workshop', _('Hotel/Workshop')),
    ('Remote', _('Remote')),
    ('Overseas assignment', _('Overseas assignment')),
    ('Other', _('Other'))
)