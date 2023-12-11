from datetime import datetime
from django import template
from django.utils.translation import gettext_lazy

from dashboard.utils import structure_the_words as utils_structure_the_words
from dashboard.functions import order_dict
from no_sql_client import NoSQLClient
from cdd.functions import datetime_complet_str

register = template.Library()


@register.filter
def facilitator_percent(facilitator):
    nsc = NoSQLClient()
    facilitator_db = nsc.get_db(facilitator.no_sql_db_name)
    try:
        total_tasks_completed = facilitator_db.get_view_result('tasks_number', 'tasks_completed')[:][0]['value']
    except:
        total_tasks_completed = 0
    
    try:
        total_tasks = facilitator_db.get_view_result('tasks_number', 'tasks_total')[:][0]['value']
    except:
        total_tasks = 0

    return float("%.2f" % (((total_tasks_completed/total_tasks)*100) if total_tasks else 0))

@register.filter
def last_activitie(facilitator):
    nsc = NoSQLClient()
    facilitator_db = nsc.get_db(facilitator.no_sql_db_name)
    last_activity_date = "0000-00-00 00:00:00"
    try:
        last_activities_date = facilitator_db.get_view_result('tasks_number', 'last_activities')[:]
        for _d in last_activities_date:
            _last_updated = datetime_complet_str(_d['value'])
            if _last_updated and last_activity_date < _last_updated:
                last_activity_date = _last_updated
    except:
        last_activity_date = "0000-00-00 00:00:00"
    
    if last_activity_date == "0000-00-00 00:00:00":
        last_activity_date = None
    else:
        last_activity_date = datetime.strptime(last_activity_date, '%Y-%m-%d %H:%M:%S')
    
    return last_activity_date