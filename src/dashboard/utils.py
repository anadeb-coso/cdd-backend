from datetime import datetime
from operator import itemgetter

from django.template.defaultfilters import date as _date
from django.contrib.auth.hashers import make_password
from authentication.models import Facilitator
from no_sql_client import NoSQLClient
from process_manager.models import Task, Phase, Activity, Project
from cloudant.document import Document


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

def get_administrative_levels_by_type(administrative_levels_db, level, empty_choice=True, attrs={}):
    filters = {
        "type": 'administrative_level',
        "administrative_level": level
    }
    for attr, value in attrs.items():
        filters[attr] = value
    query_result = administrative_levels_db.get_query_result(filters)
    return query_result


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

def get_region_of_village_by_sql_id(administrative_levels_db, village_sql_id):
    canton = get_parent_administrative_level(administrative_levels_db, village_sql_id)
    if canton:
        commune = get_parent_administrative_level(administrative_levels_db, canton['administrative_id'])
        if commune:
            prefecture = get_parent_administrative_level(administrative_levels_db, commune['administrative_id'])
            if prefecture:
                return get_parent_administrative_level(administrative_levels_db, prefecture['administrative_id'])

    return None

def get_documents_by_type(db, _type, empty_choice=True, attrs={}):
    filters = {"type": _type}
    for attr, value in attrs.items():
        filters[attr] = value
    query_result = db.get_query_result(filters)
    return query_result

# # TODO Refactor para la nueva logica
# def create_task_all_facilitators(database, task_model, develop_mode=False, trainning_mode=False):
#     facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=trainning_mode)
#     nsc = NoSQLClient()
#     nsc_database = nsc.get_db(database)
#     task = nsc_database.get_query_result({"_id": task_model.couch_id})[0]
#     activity = nsc_database.get_query_result({"_id": task_model.activity.couch_id})[0]
#     phase = nsc_database.get_query_result({"_id": task_model.phase.couch_id})[0]
#     project = nsc_database.get_query_result({"_id": task_model.project.couch_id})[0]
#     for facilitator in facilitators:
#         facilitator_database = nsc.get_db(facilitator.no_sql_db_name)
#         print(facilitator.no_sql_db_name, facilitator.username)
#         facilitator_administrative_levels = facilitator_database.get_query_result(
#             {"type": "facilitator"}
#         )[0]
#         fc_project = facilitator_database.get_query_result(
#             {"type": "project", "name": project[0]['name']}
#         )[0]

#         # check if the project exists
#         if not fc_project:
#             # create the project on the facilitator database
#             nsc.create_document(facilitator_database, project[0])

#         # Iterate every administrative level assigned to the facilitator
#         for administrative_level in facilitator_administrative_levels[0]['administrative_levels']:

#             # Get phase
#             new_phase = phase[0].copy()
#             del new_phase['_id']
#             del new_phase['_rev']
#             new_phase['administrative_level_id'] = administrative_level['id']
#             new_phase['project_id'] = project[0]['_id']
#             fc_phase = facilitator_database.get_query_result(new_phase)[0]
#             # Check if the phase was found
#             if len(fc_phase) < 1:
#                 # create the phase
#                 nsc.create_document(facilitator_database, new_phase)
#                 # Get phase
#                 fc_phase = facilitator_database.get_query_result(new_phase)[0]
#             # Get or create  activity
#             new_activity = activity[0].copy()
#             del new_activity['_id']
#             del new_activity['_rev']
#             new_activity['administrative_level_id'] = administrative_level['id']
#             new_activity['project_id'] = project[0]['_id']
#             new_activity['phase_id'] = fc_phase[0]['_id']

#             fc_activity = facilitator_database.get_query_result(new_activity)[0]

#             # Check if the activity was found
#             if len(fc_activity) < 1:
#                 # create the activity
#                 nsc.create_document(facilitator_database, new_activity)
#                 # Get activity
#                 fc_activity = facilitator_database.get_query_result(new_activity)[0]

#             # Get or create  task
#             new_task = task[0].copy()
#             del new_task['_id']
#             del new_task['_rev']
#             new_task['administrative_level_id'] = administrative_level['id']
#             new_task['administrative_level_name'] = administrative_level['name']
#             new_task['project_id'] = project[0]['_id']
#             new_task['phase_id'] = fc_phase[0]['_id']
#             new_task['activity_id'] = fc_activity[0]['_id']

#             fc_task = facilitator_database.get_query_result(new_task)[0]

#             # Check if the task was found
#             if len(fc_task) < 1:
#                 # create the activity
#                 nsc.create_document(facilitator_database, new_task)
#                 # Get activity
#                 fc_task = facilitator_database.get_query_result(new_task)[0]
#             print(fc_task)
#             print(administrative_level)


# TODO Refactor para la nueva logica
def create_task_all_facilitators(database, task_model, develop_mode=False, trainning_mode=False):
    facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=trainning_mode)
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
            new_phase['sql_id'] = task_model.phase.id #Add sql_id 
            # fc_phase = facilitator_database.get_query_result(new_phase)[0]

            #Search phase include id
            fc_phase = facilitator_database.get_query_result({
                "administrative_level_id": administrative_level['id'],
                "project_id": project[0]['_id'],
                "type": new_phase['type'], "sql_id": task_model.phase.id
            })[0]
            if len(fc_phase) < 1: #if any phase find by "Search phase include id"
                #Search phase include order
                fc_phase = facilitator_database.get_query_result({
                    "administrative_level_id": administrative_level['id'],
                    "project_id": project[0]['_id'],
                    "type": new_phase['type'], "order": new_phase['order']
                })[0]


            # Check if the phase was found
            if len(fc_phase) < 1:
                # create the phase
                nsc.create_document(facilitator_database, new_phase)
                # Get phase
                fc_phase = facilitator_database.get_query_result(new_phase)[0]
            else:
                #Update phase if it exists
                _fc_phase = fc_phase[0].copy()
                _fc_phase['name'] = task_model.phase.name
                _fc_phase['description'] = task_model.phase.description
                _fc_phase['order'] = task_model.phase.order
                _fc_phase['sql_id'] = task_model.phase.id #update doc by adding sql_id 

                nsc.update_cloudant_document(facilitator_database,  _fc_phase["_id"], _fc_phase) # Update phase for the facilitator

            
        

            # Get or create  activity
            new_activity = activity[0].copy()
            del new_activity['_id']
            del new_activity['_rev']
            new_activity['administrative_level_id'] = administrative_level['id']
            new_activity['project_id'] = project[0]['_id']
            new_activity['phase_id'] = fc_phase[0]['_id']
            new_activity['sql_id'] = task_model.activity.id #Add sql_id 

            # fc_activity = facilitator_database.get_query_result(new_activity)[0]

            #Search activity include id
            fc_activity = facilitator_database.get_query_result({
                "administrative_level_id": administrative_level['id'],
                "project_id": project[0]['_id'], "phase_id": fc_phase[0]['_id'],
                "type": new_activity['type'], "sql_id": task_model.activity.id
            })[0]
            if len(fc_activity) < 1: #if any activity find by "Search activity include id"
                #Search activity include order
                fc_activity = facilitator_database.get_query_result({
                    "administrative_level_id": administrative_level['id'],
                    "project_id": project[0]['_id'], "phase_id": fc_phase[0]['_id'],
                    "type": new_activity['type'], "order": new_activity['order']
                })[0]

            # Check if the activity was found
            if len(fc_activity) < 1:
                # create the activity
                nsc.create_document(facilitator_database, new_activity)
                # Get activity
                fc_activity = facilitator_database.get_query_result(new_activity)[0]
            else:
                #Update activity if it exists
                _fc_activity = fc_activity[0].copy()
                _fc_activity['name'] = task_model.activity.name
                _fc_activity['description'] = task_model.activity.description
                _fc_activity['order'] = task_model.activity.order
                _fc_activity['total_tasks'] = task_model.activity.total_tasks
                _fc_activity['sql_id'] = task_model.activity.id #update doc by adding sql_id 
                
                nsc.update_cloudant_document(facilitator_database,  _fc_activity["_id"], _fc_activity) # Update activity for the facilitator

            # Get or create  task
            new_task = task[0].copy()
            del new_task['_id']
            del new_task['_rev']
            new_task['administrative_level_id'] = administrative_level['id']
            new_task['administrative_level_name'] = administrative_level['name']
            new_task['project_id'] = project[0]['_id']
            new_task['phase_id'] = fc_phase[0]['_id']
            new_task['activity_id'] = fc_activity[0]['_id']
            new_task['sql_id'] = task_model.id #Add sql_id 

            # fc_task = facilitator_database.get_query_result(new_task)[0]

            #Search task include id
            fc_task = facilitator_database.get_query_result({
                "administrative_level_id": administrative_level['id'],
                "project_id": project[0]['_id'], "phase_id": fc_phase[0]['_id'],
                "activity_id": fc_activity[0]['_id'],
                "type": new_task['type'], "sql_id": task_model.id
            })[0]
            if len(fc_task) < 1: #if any task find by "Search task include id"
                 #Search task include order
                fc_task = facilitator_database.get_query_result({
                    "administrative_level_id": administrative_level['id'],
                    "project_id": project[0]['_id'], "phase_id": fc_phase[0]['_id'],
                    "activity_id": fc_activity[0]['_id'],
                    "type": new_task['type'], "order": new_task['order']
                })[0]

            # Check if the task was found
            if len(fc_task) < 1:
                # create the activity
                nsc.create_document(facilitator_database, new_task)
                # Get activity
                fc_task = facilitator_database.get_query_result(new_task)[0]
                print(fc_task)
            else:
                #Update task if it exists
                _fc_task = fc_task[0].copy()
                _fc_task['name'] = task_model.name
                _fc_task['description'] = task_model.description
                _fc_task['phase_name'] = task_model.phase.name
                _fc_task['activity_name'] = task_model.activity.name
                if task_model.form:
                    _fc_task['form'] = task_model.form
                elif new_task.get("form"):
                    _fc_task['form'] = new_task.get("form")
                _fc_task['attachments'] = new_task.get("attachments")
                _fc_task['order'] = task_model.order
                _fc_task['sql_id'] = task_model.id #update doc by adding sql_id 

                nsc.update_cloudant_document(facilitator_database,  _fc_task["_id"], _fc_task, 
                    {"attachments": ["name"]}, fc_task[0]['attachments'])  # Update task for the facilitator
                print(_fc_task)
            print(administrative_level)


def add_news_attr_to_doc(db_name, objects_list, attrs_to_add = ["sql_id"]):
    nsc = NoSQLClient()
    db = nsc.get_db(db_name)

    nsc = NoSQLClient()
    for obj in objects_list:
        docs = db.get_query_result({"_id": obj.couch_id})[0]
        if len(docs) > 0:
            doc = docs[0].copy()
            for attr in attrs_to_add:
                if attr == "sql_id":
                    doc[attr] = obj.id #update doc by adding sql_id 
            nsc.update_cloudant_document(db,  doc["_id"], doc) # Update doc of process_design


def over_documents(develop_mode=False, training_mode=False):
    """Method to override the documents by adding 'sql_id' by default"""
    phases = Phase.objects.all()
    activities = Activity.objects.all()
    tasks = Task.objects.all().prefetch_related()
    projects = Project.objects.all()

    print("Syncing: phases - process_design")
    add_news_attr_to_doc("process_design", phases)

    print("Syncing: activities - process_design")
    add_news_attr_to_doc("process_design", activities)

    print("Syncing: tasks - process_design")
    add_news_attr_to_doc("process_design", tasks)

    print("Syncing: projects - process_design")
    add_news_attr_to_doc("process_design", projects)

    for task in tasks:
        print('syncing: ', task.phase.order, task.activity.order, task.order)
        create_task_all_facilitators("process_design", task, develop_mode, training_mode)


def add_news_attrs_to_facilitators():
    nsc = NoSQLClient()
    facilitators = Facilitator.objects.all()
    print("Wait...")
    for facilitator in facilitators:
        facilitator_database = nsc.get_db(facilitator.no_sql_db_name)
        docs = facilitator_database.get_query_result({"type": "facilitator"})[:]
        if docs:
            doc = docs[0].copy()
            doc["sql_id"] = facilitator.id
            doc["develop_mode"] = facilitator.develop_mode
            doc["training_mode"] = facilitator.training_mode

            nsc.update_cloudant_document(facilitator_database,  doc["_id"], doc)
    print("")
    print("Done!")


def create_task_one_facilitator(database, task_model, no_sql_db):
    facilitators = Facilitator.objects.filter(no_sql_db_name=no_sql_db)
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
def sync_tasks(develop_mode=False, training_mode=False, no_sql_db=False):
    tasks = Task.objects.all().prefetch_related()
    for task in tasks:
        print('syncing: ', task.phase.order, task.activity.order, task.order)
        if no_sql_db:
            create_task_one_facilitator("process_design", task, no_sql_db)
        else:
            create_task_all_facilitators("process_design", task, develop_mode, training_mode)
        
# from dashboard.utils import reset_tasks
def reset_tasks():
    projects = Project.objects.all()
    projects.update(couch_id="")
    phases = Phase.objects.all()
    phases.update(couch_id="")
    activities = Activity.objects.all()
    activities.update(couch_id="")
    tasks = Task.objects.all()
    tasks.update(couch_id="")

    for project in projects:
        project.save()

    for phase in phases:
        phase.save()

    for activity in activities:
        activity.save()

    for task in tasks:
        task.save()


def create_training_facilitators(start=1, amount=1):
    count = start
    while count <= amount:
        facilitator = Facilitator(
            username="training" + str(count),
            password="123learn",
            active=True,
            training_mode=True,
        )
        facilitator.save(replicate_design=False)
        password = make_password(facilitator.password, salt=None, hasher='default')
        query_facilitator = Facilitator.objects.filter(id=facilitator.id).update(password=password)
        doc = {
            "name": "Training Acccount",
            "email": "training@test.com",
            "phone": "123456",
            "administrative_levels": [
                {
                    "name": "SANFATOUTE CENTRE",
                    "id": "7e15f10d6da4ede08fa6a6810300c9ad"
                }
            ],
            "type": "facilitator"
        }
        nsc = NoSQLClient()
        facilitator_database = nsc.get_db(facilitator.no_sql_db_name)
        nsc.create_document(facilitator_database, doc)
        count = count + 1
        print(count)
    return True

# TODO: Test this well
def delete_training_facilitators():
    training_facilitators = Facilitator.objects.filter(training_mode=True)
    nsc = NoSQLClient()
    for facilitator in training_facilitators:
        nsc.delete_db(facilitator.no_sql_db_name)
        nsc.delete_user(facilitator.no_sql_user)
        facilitator.delete()
    return True


def clear_facilitator_database(develop_mode=False, training_mode=False):
    facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode)
    nsc = NoSQLClient()
    for facilitator in facilitators:
        print(facilitator)
        nsc_database = nsc.get_db(facilitator.no_sql_db_name)
        phases = nsc_database.get_query_result({"type": "phase"})
        for phase in phases:
            nsc.delete_document(nsc_database, phase["_id"])
        activities = nsc_database.get_query_result({"type": "activity"})
        for activity in activities:
            nsc.delete_document(nsc_database, activity["_id"])
        tasks = nsc_database.get_query_result({"type": "task"})
        for task in tasks:
            nsc.delete_document(nsc_database, task["_id"])
        projects = nsc_database.get_query_result({"type": "project"})
        for project in projects:
            nsc.delete_document(nsc_database, project["_id"])