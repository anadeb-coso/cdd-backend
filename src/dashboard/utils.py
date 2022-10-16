from datetime import datetime
from operator import itemgetter

from django.template.defaultfilters import date as _date

from authentication.models import Facilitator
from no_sql_client import NoSQLClient
from process_manager.models import Task


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


def get_administrative_levels_by_level(administrative_levels_db, level=None):
    filters = {"type": 'administrative_level'}
    if level:
        filters['administrative_level'] = level
    else:
        filters['parent_id'] = None
    parent_id = administrative_levels_db.get_query_result(filters)[:][0]['administrative_id']
    data = administrative_levels_db.get_query_result(
        {
            "type": 'administrative_level',
            "parent_id": parent_id,
        }
    )
    data = [doc for doc in data]
    return data


def get_administrative_level_choices(administrative_levels_db, empty_choice=True):
    country_id = administrative_levels_db.get_query_result(
        {
            "type": 'administrative_level',
            "parent_id": None,
        }
    )[:][0]['administrative_id']
    query_result = administrative_levels_db.get_query_result(
        {
            "type": 'administrative_level',
            "parent_id": country_id,
        }
    )
    return get_choices(query_result, 'administrative_id', "name", empty_choice)


def get_child_administrative_levels(administrative_levels_db, parent_id):
    data = administrative_levels_db.get_query_result(
        {
            "type": 'administrative_level',
            "parent_id": parent_id,
        }
    )
    data = [doc for doc in data]
    return data


def get_parent_administrative_level(administrative_levels_db, administrative_id):
    parent = None
    docs = administrative_levels_db.get_query_result({
        "administrative_id": administrative_id,
        "type": 'administrative_level'
    })

    try:
        doc = administrative_levels_db[docs[0][0]['_id']]
        if 'parent_id' in doc and doc['parent_id']:
            administrative_id = doc['parent_id']
            docs = administrative_levels_db.get_query_result({
                "administrative_id": administrative_id,
                "type": 'administrative_level'
            })
            parent = administrative_levels_db[docs[0][0]['_id']]
    except Exception:
        pass
    return parent


# TODO Refactor para la nueva logica
def create_task_all_facilitators(database, task_model):
    facilitators = Facilitator.objects.all()
    nsc = NoSQLClient()
    nsc_database = nsc.get_db(database)
    task = nsc_database.get_query_result({"_id": task_model.couch_id})[0]
    activity = nsc_database.get_query_result({"_id": task_model.activity.couch_id})[0]
    phase = nsc_database.get_query_result({"_id": task_model.phase.couch_id})[0]
    project = nsc_database.get_query_result({"_id": task_model.project.couch_id})[0]
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
                # create the activity
                nsc.create_document(facilitator_database, new_activity)
                # Get activity
                fc_activity = facilitator_database.get_query_result(new_activity)[0]

            # Get or create  task
            new_task = task[0].copy()
            del new_task['_id']
            del new_task['_rev']
            new_task['administrative_level_id'] = administrative_level['id']
            new_task['administrative_level_name'] = administrative_level['name']
            new_task['project_id'] = project[0]['_id']
            new_task['phase_id'] = fc_phase[0]['_id']
            new_task['activity_id'] = fc_activity[0]['_id']

            fc_task = facilitator_database.get_query_result(new_task)[0]

            # Check if the task was found
            if len(fc_task) < 1:
                # create the activity
                nsc.create_document(facilitator_database, new_task)
                # Get activity
                fc_task = facilitator_database.get_query_result(new_task)[0]
            print(fc_task)
            print(administrative_level)


# from dashboard.utils import sync_tasks
def sync_tasks():
    tasks = Task.objects.all().prefetch_related()
    for task in tasks:
        print('syncing: ', task.phase.order, task.activity.order, task.order)
        create_task_all_facilitators("process_design", task)
