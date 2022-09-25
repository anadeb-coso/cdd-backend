from datetime import datetime
from operator import itemgetter
from authentication.models import Facilitator
from no_sql_client import NoSQLClient

from django.template.defaultfilters import date as _date


def sort_dictionary_list_by_field(list_to_be_sorted, field, reverse=False):
    return sorted(list_to_be_sorted, key=itemgetter(field), reverse=reverse)


def get_month_range(start, end=datetime.now(), fmt="Y F"):
    start = start.month + 12 * start.year
    end = end.month + 12 * end.year
    months = list()
    for month in range(start - 1, end):
        y, m = divmod(month, 12)
        months.insert(0, (f'{y}-{m+1}', _date(datetime(y, m + 1, 1), fmt)))
    return months


def unix_time_millis(dt):
    epoch = datetime.utcfromtimestamp(0)
    return int((dt - epoch).total_seconds() * 1000)


def get_choices(query_result, id_key="id", text_key="name", empty_choice=True):
    choices = list({(i[id_key], i[text_key]) for i in query_result})
    if empty_choice:
        choices = [('', '')] + choices
    return choices


def create_task_all_facilitators(database):
    facilitators = Facilitator.objects.all()
    nsc = NoSQLClient()
    nsc_database = nsc.get_db(database)
    task = nsc_database.get_query_result({"type": "task"})[0]
    activity = nsc_database.get_query_result({"type": "activity"})[0]
    phase = nsc_database.get_query_result({"type": "phase"})[0]
    project = nsc_database.get_query_result({"type": "project"})[0]
    for facilitator in facilitators:
        facilitator_database = nsc.get_db(facilitator.no_sql_db_name)
        print(facilitator.no_sql_db_name, facilitator.username)
        facilitator_administrative_levels = facilitator_database.get_query_result(
            {"type": "facilitator"}
        )[0]
        fc_project = facilitator_database.get_query_result(
            {"type": "project", "name": project[0]['name']}
        )[0]

        # check if the project exists
        if not fc_project:
            # create the project on the facilitator database
            nsc.create_document(facilitator_database, project[0])

        # Iterate every administrative level assigned to the facilitator
        for administrative_level in facilitator_administrative_levels[0]['administrative_levels']:

            # Get phase
            new_phase = phase[0].copy()
            del new_phase['_id']
            del new_phase['_rev']
            new_phase['administrative_level_id'] = administrative_level['id']
            new_phase['project_id'] = project[0]['_id']
            fc_phase = facilitator_database.get_query_result(new_phase)[0]
            # Check if the phase was found
            if len(fc_phase) < 1:
                # create the phase
                nsc.create_document(facilitator_database, new_phase)
                # Get phase
                fc_phase = facilitator_database.get_query_result(new_phase)[0]
            # Get or create  activity
            new_activity = activity[0].copy()
            del new_activity['_id']
            del new_activity['_rev']
            new_activity['administrative_level_id'] = administrative_level['id']
            new_activity['project_id'] = project[0]['_id']
            new_activity['phase_id'] = fc_phase[0]['_id']

            fc_activity = facilitator_database.get_query_result(new_activity)[0]

            # Check if the activity was found
            if len(fc_activity) < 1:
                # create the phase
                nsc.create_document(facilitator_database, new_activity)
                # Get phase
                fc_activity = facilitator_database.get_query_result(new_activity)[0]
            print(fc_activity)
            # Get or create  task
            print(administrative_level)