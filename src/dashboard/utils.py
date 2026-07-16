from datetime import datetime
from operator import itemgetter
import re
import itertools

from django.template.defaultfilters import date as _date
from django.contrib.auth.hashers import make_password
from authentication.models import Facilitator
from no_sql_client import NoSQLClient
from process_manager.models import Task, Phase, Activity, Project, AggregatedStatus, Cycle
from cloudant.document import Document
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy

from administrativelevels import models as administrativelevels_models
from dashboard.facilitators.functions import get_cvds
from assignments.models import AssignAdministrativeLevelToFacilitator
from cdd.functions import datetime_complet_str
from cdd.call_objects_from_other_db import mis_objects_call
from subprojects.models import Cycle as CycleMis, Project as ProjectMis
from cdd.my_librairies.mail.send_mail import send_email
from dashboard.statistics.utils import comparer_chaines, normaliser_chaine
from cdd.my_librairies.functions import get_datas_dict
from subprojects.models import Project as MisProject, Cycle as MisCycle
from administrativelevels.models import AdministrativeLevel, CVD


def structure_the_words(word):
    return (" ").join(re.findall(r'[A-Z][^A-Z]*|[^A-Z]+', word)).lower().capitalize()
    
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
    # choices = list({(i[id_key], i[text_key]) for i in query_result})
    choices = []
    [choices.append((i[id_key], i[text_key])) for i in query_result if i not in choices]
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

def get_all_docs_administrative_levels_by_type_and_parent_id(administrative_levels, level, parent_id):
    result = []
    for doc in administrative_levels:
        doc = doc.get('doc')
        if doc.get('type') == 'administrative_level' and doc.get('administrative_level') == level and doc.get('parent_id') == parent_id:
            result.append(doc)
    return result

def get_all_docs_administrative_levels_by_type_and_administrative_id(administrative_levels, level, administrative_id):
    result = []
    for doc in administrative_levels:
        doc = doc.get('doc')
        if doc.get('type') == 'administrative_level' and doc.get('administrative_level') == level and doc.get('administrative_id') == administrative_id:
            result.append(doc)
    return result

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

def get_administrative_level_choices_mis(project_id, empty_choice=True):
    if project_id:
        project = Project.objects.get(id=project_id)
        query_result = mis_objects_call.filter_objects(administrativelevels_models.AdministrativeLevel, parent=None, administrative_levels_projects__in=[mis_objects_call.get_object(ProjectMis, name=project.name).id])
    else:
        query_result = mis_objects_call.filter_objects(administrativelevels_models.AdministrativeLevel, parent=None)
    
    return get_choices(list(query_result.values()), empty_choice=empty_choice)


def get_child_administrative_levels(administrative_levels_db, parent_id, project_id=0, cycle_id=0):
    data = administrative_levels_db.get_query_result(
        {
            "type": 'administrative_level',
            "parent_id": parent_id,
        }
    )
    data = data #[{**d, "ville": "Lomé"} for d in data]
    project = Project.objects.get(id=project_id)
    project_mis = mis_objects_call.get_object(ProjectMis, name=project.name)
    cycle = Cycle.objects.get(id=cycle_id, project_id=project_id)

    data = [{
            **doc, 
            "project_id": project.couch_id,
            "project_name": project.name,
            "cycle_id": cycle.couch_id,
            "cycle_name": cycle.name
        } for doc in data if (((project_id == 0) or (doc.get('administrative_level') != 'Village') or \
        (
        doc.get('administrative_id') and not AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(
            administrative_level_id=int(doc.get('administrative_id')), project_id=project_mis.id, activated=True
        ))) and project_mis.administrative_levels.filter(id=int(doc.get('administrative_id'))).exists())
    ] 
    obj = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(id=int(parent_id)).first()
    if not data and obj and obj.type != "Village":
        data.append({
            "administrative_id": "0",
            "name": "",
            "administrative_level": "-",
            "type": "administrative_level",
            "parent_id": "1",
            "project_id": project.couch_id,
            "project_name": project.name,
            "cycle_id": cycle.couch_id,
            "cycle_name": cycle.name
        })
                
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
def get_parent_administrative_level_mis(administrative_id, project_id):
    parent = None
    project = Project.objects.get(id=project_id)
    try:
        adls = mis_objects_call.filter_objects(administrativelevels_models.AdministrativeLevel, id=int(administrative_id), administrative_levels_projects__in=[mis_objects_call.get_object(ProjectMis, name=project.name).id])
        adl = adls.first()
        if adl.parent:
            administrative_id = adl.parent.id
            adls = mis_objects_call.filter_objects(administrativelevels_models.AdministrativeLevel, id=int(administrative_id), administrative_levels_projects__in=[mis_objects_call.get_object(ProjectMis, name=project.name).id])
            parent = adls.first()
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
def get_region_of_village_by_sql_id_mis(village_sql_id, project_id):
    canton = get_parent_administrative_level_mis(village_sql_id, project_id)
    if canton:
        commune = get_parent_administrative_level_mis(canton.id, project_id)
        if commune:
            prefecture = get_parent_administrative_level_mis(commune.id, project_id)
            if prefecture:
                return get_parent_administrative_level_mis(prefecture.id, project_id)

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
def create_task_all_facilitators(database, task_model, develop_mode=False, trainning_mode=False, no_sql_dbs=False, administrativelevel_ids=[], project_id=None, cycle_id=None):
    if no_sql_dbs:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=trainning_mode, no_sql_db_name__in=no_sql_dbs)
    else:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=trainning_mode, projects__in=[project_id])

    if not cycle_id:
        raise Exception("ID Cycle can't be unknow")
    if not task_model.cycles.all().filter(id=cycle_id).exists():
        raise Exception("Undefined ID Cycle")
    cycle_object = Cycle.objects.get(id=cycle_id)

    nsc = NoSQLClient()
    nsc_database = nsc.get_db(database)
    task = nsc_database.get_query_result({"_id": task_model.couch_id})[0]
    activity = nsc_database.get_query_result({"_id": task_model.activity.couch_id})[0]
    phase = nsc_database.get_query_result({"_id": task_model.phase.couch_id})[0]
    project = nsc_database.get_query_result({"_id": task_model.project.couch_id})[0]
    cycle = nsc_database.get_query_result({"_id": cycle_object.couch_id})[0]

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


        fc_cycle = facilitator_database.get_query_result(
            {"type": "cycle", "name": cycle[0]['name'], "project_id": project[0]['_id']}
        )[0]
        # check if the cycle exists
        if not fc_cycle:
            # create the cycle on the facilitator database
            nsc.create_document(facilitator_database, cycle[0])


        # Iterate every administrative level assigned to the facilitator
        for administrative_level in facilitator_administrative_levels[0]['administrative_levels']:
            canton_sql_id = None
            try:
                administrativelevel_obj = administrativelevels_models.AdministrativeLevel.objects.using('mis').get(id=int(administrative_level['id']))
                canton_sql_id = str(administrativelevel_obj.parent.id)
            except Exception as e:
                pass

            if(administrative_level.get('project_name') == project[0]['name'] and administrative_level.get('cycle_name') == cycle[0]['name'] and (
                (administrative_level.get('is_headquarters_village') and not administrativelevel_ids)
                or
                (administrative_level.get('is_headquarters_village') and administrativelevel_ids and str(administrative_level['id']) in administrativelevel_ids)
                or
                (administrative_level.get('is_headquarters_village') and administrativelevel_ids and canton_sql_id and canton_sql_id in administrativelevel_ids)
               )):
                # Get phase
                new_phase = phase[0].copy()
                del new_phase['_id']
                del new_phase['_rev']
                new_phase['administrative_level_id'] = administrative_level['id']
                new_phase['project_id'] = project[0]['_id']
                new_phase['sql_id'] = task_model.phase.id #Add sql_id 
                new_phase['project_name'] = task_model.project.name
                # fc_phase = facilitator_database.get_query_result(new_phase)[0]
                new_phase['cycle_id'] = cycle[0]['_id']
                new_phase['cycle_name'] = cycle_object.name

                #Search phase include id
                fc_phase = facilitator_database.get_query_result({
                    "administrative_level_id": administrative_level['id'],
                    "project_id": project[0]['_id'],
                    "cycle_id": cycle[0]['_id'],
                    "type": new_phase['type'], "sql_id": task_model.phase.id
                })[0]
                if len(fc_phase) < 1: #if any phase find by "Search phase include id"
                    #Search phase include order
                    fc_phase = facilitator_database.get_query_result({
                        "administrative_level_id": administrative_level['id'],
                        "project_id": project[0]['_id'],
                        "cycle_id": cycle[0]['_id'],
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
                    _fc_phase['project_name'] = task_model.project.name
                    _fc_phase['cycle_name'] = cycle_object.name
                    _fc_phase['cycle_id'] = cycle[0]['_id']

                    nsc.update_cloudant_document(facilitator_database,  _fc_phase["_id"], _fc_phase) # Update phase for the facilitator

                
            

                # Get or create  activity
                new_activity = activity[0].copy()
                del new_activity['_id']
                del new_activity['_rev']
                new_activity['administrative_level_id'] = administrative_level['id']
                new_activity['project_id'] = project[0]['_id']
                new_activity['phase_id'] = fc_phase[0]['_id']
                new_activity['sql_id'] = task_model.activity.id #Add sql_id 
                new_activity['project_name'] = task_model.project.name
                new_activity['cycle_id'] = cycle[0]['_id']
                new_activity['cycle_name'] = cycle_object.name

                # fc_activity = facilitator_database.get_query_result(new_activity)[0]

                #Search activity include id
                fc_activity = facilitator_database.get_query_result({
                    "administrative_level_id": administrative_level['id'],
                    "project_id": project[0]['_id'], 
                    "cycle_id": cycle[0]['_id'],
                    "phase_id": fc_phase[0]['_id'],
                    "type": new_activity['type'], "sql_id": task_model.activity.id
                })[0]
                if len(fc_activity) < 1: #if any activity find by "Search activity include id"
                    #Search activity include order
                    fc_activity = facilitator_database.get_query_result({
                        "administrative_level_id": administrative_level['id'],
                        "project_id": project[0]['_id'], 
                        "cycle_id": cycle[0]['_id'],
                        "phase_id": fc_phase[0]['_id'],
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
                    _fc_activity['project_name'] = task_model.project.name
                    _fc_activity['cycle_name'] = cycle_object.name
                    _fc_activity['cycle_id'] = cycle[0]['_id']
                    
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
                new_task['phase_sql_id'] = task_model.phase.id
                new_task['activity_sql_id'] = task_model.activity.id
                new_task['project_name'] = task_model.project.name
                new_task['cycle_id'] = cycle[0]['_id']
                new_task['cycle_name'] = cycle_object.name

                # fc_task = facilitator_database.get_query_result(new_task)[0]

                #Search task include id
                fc_task = facilitator_database.get_query_result({
                    "administrative_level_id": administrative_level['id'],
                    "project_id": project[0]['_id'], 
                    "cycle_id": cycle[0]['_id'],
                    "phase_id": fc_phase[0]['_id'],
                    "activity_id": fc_activity[0]['_id'],
                    "type": new_task['type'], "sql_id": task_model.id
                })[0]
                if len(fc_task) < 1: #if any task find by "Search task include id"
                    #Search task include order
                    fc_task = facilitator_database.get_query_result({
                        "administrative_level_id": administrative_level['id'],
                        "project_id": project[0]['_id'], 
                        "cycle_id": cycle[0]['_id'],
                        "phase_id": fc_phase[0]['_id'],
                        "activity_id": fc_activity[0]['_id'],
                        "type": new_task['type'], "order": new_task['order']
                    })[0]


                # Check if the task was found
                if len(fc_task) < 1:
                    # create the task
                    new_task['completed_date'] = None #Add completed_date 
                    new_task['last_updated'] = None #Add last_updated 

                    if canton_sql_id:
                        new_task['canton_sql_id'] = canton_sql_id #Add canton_sql_id 

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
                    _fc_task['administrative_level_name'] = administrative_level['name']
                    # if task_model.form:
                    #     _fc_task['form'] = task_model.form
                    # elif new_task.get("form"):
                    #     _fc_task['form'] = new_task.get("form")
                    _fc_task['form'] = new_task.get("form")

                    _fc_task['attachments'] = new_task.get("attachments")
                    _fc_task['order'] = task_model.order
                    _fc_task['sql_id'] = task_model.id #update doc by adding sql_id 
                    _fc_task['support_attachments'] = new_task.get("support_attachments")
                    _fc_task['task_order'] = new_task.get("task_order") #Task order
                    
                    #Start management of the dates of the last update and completed

                    datetime_now = datetime.now()
                    datetime_str = f"{str(datetime_now.year)}-{str(datetime_now.month)}-{str(datetime_now.day)} {str(datetime_now.hour)}:{str(datetime_now.minute)}:{str(datetime_now.second)}"
                    
                    if not _fc_task.get('last_updated'):
                        if _fc_task.get('completed'):
                            _fc_task['last_updated'] = datetime_str #update doc by adding last_updated 
                        else:
                            _fc_task['last_updated'] = "0000-00-00 00:00:00" #update doc by adding last_updated 
                    
                    if not _fc_task.get('completed_date'):
                        if _fc_task.get('completed'):
                            _fc_task['completed_date'] = datetime_str #update doc by adding completed_date 
                        else:
                            _fc_task['completed_date'] = "0000-00-00 00:00:00" #update doc by adding completed_date 
                    
                    #End management of the dates of the last update and completed

                    
                    _fc_task['phase_sql_id'] = task_model.phase.id
                    _fc_task['activity_sql_id'] = task_model.activity.id
                    _fc_task['project_name'] = task_model.project.name
                    _fc_task['cycle_name'] = cycle_object.name
                    _fc_task['cycle_id'] = cycle[0]['_id']

                    if canton_sql_id:
                        _fc_task['canton_sql_id'] = canton_sql_id #Add canton_sql_id 

                    nsc.update_cloudant_document(facilitator_database,  _fc_task["_id"], _fc_task, 
                        {"attachments": ["name", "order"]}, fc_task[0]['attachments'])  # Update task for the facilitator
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
                elif attr in ["completed_date", "last_updated"]:
                    doc[attr] = "0000-00-00 00:00:00"
            nsc.update_cloudant_document(db,  doc["_id"], doc) # Update doc of process_design


def over_documents(project_id, develop_mode=False, training_mode=False):
    """Method to override the documents by adding 'sql_id' by default"""
    phases = Phase.objects.filter(project_id=project_id)
    activities = Activity.objects.filter(project_id=project_id)
    tasks = Task.objects.filter(project_id=project_id).prefetch_related()
    projects = Project.objects.filter(id=project_id)

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
        create_task_all_facilitators("process_design", task, develop_mode, training_mode, project_id=project_id)


def over_documents_to_add_completed_date_and_last_updated_attrs(project_id, develop_mode=False, training_mode=False):
    """Method to override the documents by adding 'completed_date' and 'last_updated' attributes"""

    tasks = Task.objects.filter(project_id=project_id).prefetch_related()

    print("Syncing: tasks - process_design")
    add_news_attr_to_doc("process_design", tasks, ["completed_date", "last_updated"])

    for task in tasks:
        print('syncing: ', task.phase.order, task.activity.order, task.order)
        create_task_all_facilitators("process_design", task, develop_mode, training_mode, project_id=project_id)


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
def sync_tasks(project_id, cycle_id, develop_mode=False, training_mode=False, no_sql_dbs=False, administrativelevel_ids=[], tasks_ids=[], attachmentsPresented=None):
    
    if attachmentsPresented in (False, True):
        if tasks_ids:
            tasks = Task.objects.filter(id__in=tasks_ids, attachments__isnull=(not attachmentsPresented)).prefetch_related()
        else:
            tasks = Task.objects.filter(project_id=project_id, cycles__in=[cycle_id], attachments__isnull=(not attachmentsPresented)).prefetch_related()
    elif tasks_ids:
        tasks = Task.objects.filter(id__in=tasks_ids).prefetch_related()
    else:
        tasks = Task.objects.filter(project_id=project_id, cycles__in=[cycle_id]).prefetch_related()

    for task in tasks:
        print('syncing: ', task.phase.order, task.activity.order, task.order)
        # if no_sql_db:
        #     create_task_one_facilitator("process_design", task, no_sql_db)
        # else:
        #     create_task_all_facilitators("process_design", task, develop_mode, training_mode)
        create_task_all_facilitators("process_design", task, develop_mode, training_mode, no_sql_dbs, administrativelevel_ids, project_id=project_id, cycle_id=cycle_id)
    
    print("Sync done!")

    # add_facilitator_design(develop_mode, training_mode, no_sql_dbs=no_sql_dbs, project_id=project_id)
    # print("Done!")


def sync_tasks_attachments(project_id, cycle_id, attachments_names_with_attrs, tasks_ids, develop_mode=False, training_mode=False, no_sql_dbs=False, administrativelevel_ids=[], attachmentsPresented=None):
    """
    attachments_names_with_attrs={'attachment_name': {'attribute_to_add':'value'}}
    """
    if attachmentsPresented in (False, True):
        if tasks_ids:
            tasks = Task.objects.filter(id__in=tasks_ids, attachments__isnull=(not attachmentsPresented)).prefetch_related()
        else:
            tasks = Task.objects.filter(project_id=project_id, cycles__in=[cycle_id], attachments__isnull=(not attachmentsPresented)).prefetch_related()
    elif tasks_ids:
        tasks = Task.objects.filter(id__in=tasks_ids).prefetch_related()
    else:
        tasks = Task.objects.filter(project_id=project_id, cycles__in=[cycle_id]).prefetch_related()

    nsc = NoSQLClient()

    if no_sql_dbs:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, no_sql_db_name__in=no_sql_dbs)
    else:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, projects__in=[project_id])

    for task in tasks:
        print('syncing: ', task.phase.order, task.activity.order, task.order)
        
        if not cycle_id:
            raise Exception("ID Cycle can't be unknow")
        if not task.cycles.all().filter(id=cycle_id).exists():
            raise Exception("Undefined ID Cycle")
        cycle_object = Cycle.objects.get(id=cycle_id)

        for facilitator in facilitators:
            facilitator_database = nsc.get_db(facilitator.no_sql_db_name)
            print(facilitator.no_sql_db_name, facilitator.username)

            # fc_tasks = facilitator_database.all_docs(include_docs=True)['rows']
            # fc_tasks = [doc for doc in fc_tasks if doc.get('doc') and doc.get('doc').get('cycle_id') == cycle.couch_id and doc.get('doc').get('project_id') == project.couch_id]
            if administrativelevel_ids:
                fc_tasks = facilitator_database.get_query_result({
                    "type": "task",
                    "sql_id": task.id,
                    "cycle_id": cycle_object.couch_id,
                    "project_id": cycle_object.project.couch_id,
                    "administrative_level_id": {'$in': [str(_id) for _id in administrativelevel_ids]}
                })[:]
            else:
                fc_tasks = facilitator_database.get_query_result({
                    "type": "task",
                    "sql_id": task.id,
                    "cycle_id": cycle_object.couch_id,
                    "project_id": cycle_object.project.couch_id
                })[:]

            for fc_task in fc_tasks:
                ok_1 = False
                for i in range(len(fc_task['attachments'])):
                    if fc_task['attachments'][i]['name'] in list(attachments_names_with_attrs.keys()):
                        for k, v in attachments_names_with_attrs[fc_task['attachments'][i]['name']].items():
                            fc_task['attachments'][i][k] = v
                        print(fc_task['administrative_level_id'], fc_task['administrative_level_name'], fc_task['attachments'][i])
                        ok_1 = True
                if ok_1:
                    nsc.update_cloudant_document(facilitator_database,  fc_task["_id"], fc_task)  # Update task for the facilitator
                    print(fc_task['administrative_level_id'], fc_task['administrative_level_name'], fc_task['attachments'])
                    print()

                

def sync_tasks_by_putting_unfinished_those_which_do_not_have_the_attachments(develop_mode=False, training_mode=False, no_sql_db=False, project_id=None, cycle_id=None):
    project = Project.objects.get(id=project_id)
    if no_sql_db:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, no_sql_db_name=no_sql_db)
    else:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, projects__in=[project_id])

    if not cycle_id:
        raise Exception("ID Cycle can't be unknow")
    cycle = Cycle.objects.get(id=cycle_id)

    nsc = NoSQLClient()
    for facilitator in facilitators:
        facilitator_database = nsc.get_db(facilitator.no_sql_db_name)
        print(facilitator.no_sql_db_name, facilitator.username)
        # fc_tasks = facilitator_database.get_query_result({"type": "task"})[:]
        fc_tasks = facilitator_database.all_docs(include_docs=True)['rows']
        fc_tasks = [doc for doc in fc_tasks if doc.get('doc') and doc.get('doc').get('cycle_id') == cycle.couch_id and doc.get('doc').get('project_id') == project.couch_id]
        
        for _task in fc_tasks:
            task = _task.get('doc')
            if task.get('cycle_id') == cycle.couch_id and task.get('type') == 'task' and task.get("completed") and task.get("support_attachments"):
                attachments = task["attachments"]
                all_attachs_filled = True

                for att in attachments:
                    if not att.get("attachment") or (att.get("attachment") and "file:///data" in att.get("attachment").get("uri")):
                        all_attachs_filled = False

                if not all_attachs_filled:
                    task["completed"] = False
                    nsc.update_cloudant_document(facilitator_database,  task["_id"], task)  # Update task for the facilitator
                    print(task)



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


def create_training_facilitators(project_name, start=1, amount=1):
    project = Project.objects.get(name=project_name)
    cycle = Cycle.objects.get(order=1, project_id=project.id)
    total_tasks_p_c = Task.objects.filter(project_id=project.id, cycles__in=[cycle.id]).count()
    count = start
    while count <= amount:
        facilitator = Facilitator(
            username="training" + str(count),
            password="123learn",
            active=True,
            training_mode=True,
            name=f"Training{count} Acccount",
            email=f"training{count}@test.com",
            phone=f"123456{count}",
            sex="M.",
        )
        facilitator = facilitator.save(replicate_design=False)
        password = make_password(facilitator.password, salt=None, hasher='default')
        query_facilitator = Facilitator.objects.filter(id=facilitator.id).update(password=password)
        project.facilitators.add(facilitator)
        
        doc = {
            "name": f"Training{count} Acccount",
            "email": f"training{count}@test.com",
            "phone": f"123456{count}",
            "sex": "M.",
            "administrative_levels": [
                {
                "name": "SANFATOUTE CENTRE",
                "id": "3805",
                "is_headquarters_village": True,
                "project_name": project.name,
                "project_id": project.couch_id,
                "cycle_name": cycle.name,
                "cycle_id": cycle.couch_id
                },
                {
                "name": "SANFATOUTE 2",
                "id": "3804",
                "project_name": project.name,
                "project_id": project.couch_id,
                "cycle_name": cycle.name,
                "cycle_id": cycle.couch_id
                }
            ],
            "type": "facilitator",
            "geographical_units": [
                {
                    "sql_id": "133",
                    "name": "SANFATOUTE 2/SANFATOUTE CENTRE",
                    "villages": [
                        "3805",
                        "3804"
                    ],
                    "cvd_groups": [
                        {
                        "sql_id": "141",
                        "name": "CVD SANFATOUTE CENTRE",
                        "village_cvd": 3805,
                        "villages": [
                            "3805",
                            "3804"
                        ]
                        }
                    ]
                }
            ],
            "develop_mode": False,
            "training_mode": True,
            "sql_id": facilitator.id,
            "project_id": project.couch_id,
            "project_name": project.name,
            "projects_ids": [
                project.couch_id
            ],
            "projects_names": [
                project.name
            ],
            "total_number_of_tasks": total_tasks_p_c,
            "total_tasks_by_project_by_cycle": {
                project.couch_id: {
                    cycle.couch_id: total_tasks_p_c
                },
                project.name: {
                    cycle.name: total_tasks_p_c
                }
            }
        }
        nsc = NoSQLClient()
        facilitator_database = nsc.get_db(facilitator.no_sql_db_name)
        nsc.create_document(facilitator_database, doc)
        print(count)
        count = count + 1
    project.save()
    return True

# TODO: Test this well
def delete_training_facilitators(project_name, start, amount):
    project = Project.objects.get(name=project_name)
    training_facilitators = Facilitator.objects.filter(training_mode=True, username__in=["training" + str(count) for count in range(start, amount+1)], projects__in=[project.id])
    nsc = NoSQLClient()
    for facilitator in training_facilitators:
        print(facilitator.name, facilitator.username)
        nsc.delete_db(facilitator.no_sql_db_name)
        nsc.delete_user(facilitator.no_sql_user)
        facilitator.delete()
    return True


def clear_facilitator_database(develop_mode=False, training_mode=False, no_sql_db=False, project_id=None):
    # facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode)
    if no_sql_db:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, no_sql_db_name=no_sql_db)
    else:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, projects__in=[project_id])


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

def clear_facilitator_documents_tasks_by_administrativelevels(no_sql_db, administrativelevels_ids=[], to_delete=True):
    facilitators = Facilitator.objects.filter(no_sql_db_name=no_sql_db) 
    nsc = NoSQLClient()
    for facilitator in facilitators:
        print()
        print(facilitator)
        nsc_database = nsc.get_db(facilitator.no_sql_db_name)
        facilitator_doc = nsc_database[nsc_database.get_query_result({"type": "facilitator"})[:][0]['_id']]
        administrative_levels = facilitator_doc["administrative_levels"]
        _administrative_levels = []
        fc_docs = nsc_database.all_docs(include_docs=True)['rows']
        
        print(administrative_levels)
        for elt in administrative_levels:
            if elt['id'] in administrativelevels_ids:
                adl_id = elt['id']
                # for adl_id in administrativelevels_ids:
        
                for _doc in fc_docs:
                    doc = _doc.get('doc')
                    if doc.get('type') in ('task', 'activity', 'phase') and doc.get('administrative_level_id') == adl_id:
                        nsc.delete_document(nsc_database, doc["_id"])
                # phases = nsc_database.get_query_result({"type": "phase", "administrative_level_id": adl_id})
                # for phase in phases:
                #     nsc.delete_document(nsc_database, phase["_id"])
                # activities = nsc_database.get_query_result({"type": "activity", "administrative_level_id": adl_id})
                # for activity in activities:
                #     nsc.delete_document(nsc_database, activity["_id"])
                # tasks = nsc_database.get_query_result({"type": "task", "administrative_level_id": adl_id})
                # for task in tasks:
                #     nsc.delete_document(nsc_database, task["_id"])

                # for i in range(len(administrative_levels)):
                #     if administrative_levels[i]["id"] == adl_id:
                #         continue
                #     _administrative_levels.append(administrative_levels[i])
            else:
                _administrative_levels.append(elt)
                
        print(_administrative_levels)
        if to_delete:
            doc = {
                "administrative_levels": _administrative_levels
            }
            nsc.update_doc(nsc_database, facilitator_doc['_id'], doc)



def sync_geographicalunits_with_cvd_on_facilittor(project_id, develop_mode=False, training_mode=False, no_sql_db=False):
    
    if no_sql_db:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, no_sql_db_name=no_sql_db)
    else:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, projects__in=[project_id])

    nsc = NoSQLClient()
    for facilitator in facilitators:
        facilitator_database = nsc.get_db(facilitator.no_sql_db_name)
        print(facilitator.no_sql_db_name, facilitator.username)
        doc_facilitator = facilitator_database.get_query_result(
            {"type": "facilitator"}
        )[:][0]

        geographical_units = []
        for i_range in range(len(doc_facilitator['administrative_levels'])):
            administrativelevel = doc_facilitator['administrative_levels'][i_range]
            try:
                administrativelevel_obj = administrativelevels_models.AdministrativeLevel.objects.using('mis').get(id=int(administrativelevel['id']))
                if administrativelevel_obj.geographical_unit:
                    geographical_unit_id_exists = False
                    for i in range(len(geographical_units)):
                        if geographical_units[i] and geographical_units[i].get('sql_id') and str(geographical_units[i].get('sql_id')) == str(administrativelevel_obj.geographical_unit_id):
                            geographical_unit_id_exists = True
                    if not geographical_unit_id_exists:
                        geographical_units.append(
                            {
                                "sql_id": str(administrativelevel_obj.geographical_unit_id),
                                "name": administrativelevel_obj.geographical_unit.get_name(),
                                "villages": [], 
                                "cvd_groups": []
                            }
                        )

                    

                    for i in range(len(geographical_units)):
                        if geographical_units[i] and geographical_units[i].get('sql_id') and str(geographical_units[i].get('sql_id')) == str(administrativelevel_obj.geographical_unit_id):
                            villages = geographical_units[i].get('villages')
                            villages.append(str(administrativelevel_obj.id))
                            geographical_units[i]['villages'] = list(set(villages))



                            #CVD
                            if administrativelevel_obj.cvd:
                                cvd_id_exists = False
                                for a in range(len(geographical_units[i].get('cvd_groups'))):
                                    if str(geographical_units[i].get('cvd_groups')[a].get('sql_id')) == str(administrativelevel_obj.cvd_id):
                                        cvd_id_exists = True
                                if not cvd_id_exists:
                                    geographical_units[i].get('cvd_groups').append(
                                        {
                                            "sql_id": str(administrativelevel_obj.cvd_id),
                                            "name": administrativelevel_obj.cvd.get_name(),
                                            "village_cvd": administrativelevel_obj.cvd.headquarters_village.id if administrativelevel_obj.cvd.headquarters_village else None,
                                            "villages": [str(administrativelevel_obj.id)]
                                        }
                                    )

                                for a in range(len(geographical_units[i].get('cvd_groups'))):
                                    if str(geographical_units[i].get('cvd_groups')[a].get('sql_id')) == str(administrativelevel_obj.cvd_id):
                                        villages = geographical_units[i].get('cvd_groups')[a].get('villages')
                                        villages.append(str(administrativelevel_obj.id))
                                        geographical_units[i].get('cvd_groups')[a]['villages'] = list(set(villages))
                                
                            #End CVD
                    if administrativelevel_obj.cvd and administrativelevel_obj.cvd.headquarters_village and str(administrativelevel_obj.cvd.headquarters_village.id) == doc_facilitator['administrative_levels'][i_range]['id']:
                        doc_facilitator['administrative_levels'][i_range]['is_headquarters_village'] = True
                
                else:
                    print("pass")
            
            except Exception as exc:
                print()
                print(administrativelevel['id'], administrativelevel['name'] , ': ', exc.__str__())
                print()

        doc_facilitator["geographical_units"] = geographical_units
        doc_facilitator['total_number_of_tasks'] = Task.objects.filter(project_id=project_id, cycles__in=[Cycle.objects.get(order=1, project_id=project_id).id]).count()

        doc_facilitator['total_tasks_by_project_by_cycle'] = {}
        for _project in Project.objects.all():
            _cycles = Cycle.objects.filter(project_id=_project.id)
            doc_facilitator['total_tasks_by_project_by_cycle'][_project.couch_id] = {}
            doc_facilitator['total_tasks_by_project_by_cycle'][_project.name] = {}
            for _cycle in _cycles:
                total_tasks_p_c = Task.objects.filter(project_id=_project.id, cycles__in=[_cycle.id]).count()
                doc_facilitator['total_tasks_by_project_by_cycle'][_project.couch_id][_cycle.couch_id] = total_tasks_p_c
                doc_facilitator['total_tasks_by_project_by_cycle'][_project.name][_cycle.name] = total_tasks_p_c
            
        nsc.update_cloudant_document(facilitator_database, doc_facilitator['_id'], doc_facilitator)


        print(geographical_units)
        print(doc_facilitator['administrative_levels'])
        print()
        print()


def copy_village_datas_completed_to_other_villages_belonging_to_same_cvd(develop_mode=False, training_mode=False, no_sql_db=False, project_id=None, cycle_id=None):
    
    if no_sql_db:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, no_sql_db_name=no_sql_db)
    else:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, projects__in=[project_id])

    if not cycle_id:
        raise Exception("ID Cycle can't be unknow")
    cycle = Cycle.objects.get(id=cycle_id)
    project = Project.objects.get(id=project_id)

    nsc = NoSQLClient()
    for facilitator in facilitators:
        facilitator_database = nsc.get_db(facilitator.no_sql_db_name)
        print(facilitator.no_sql_db_name, facilitator.username)
        
        
        fc_tasks = facilitator_database.all_docs(include_docs=True)['rows']
        fc_tasks = [doc for doc in fc_tasks if doc.get('doc') and doc.get('doc').get('cycle_id') == cycle.couch_id and doc.get('doc').get('project_id') == project.couch_id]

        _fc_tasks = fc_tasks.copy()
        for _task in fc_tasks:
            task = _task.get('doc')
            if task.get('cycle_id') == cycle.couch_id and task.get("completed") and task.get('type') == 'task':
                attachments = task.get("attachments")
                form_response = task.get("form_response")
                completed_date = task.get("completed_date")
                last_updated = task.get("last_updated")

                villages = []
                try:
                    administrativelevel_obj = administrativelevels_models.AdministrativeLevel.objects.using('mis').get(id=int(task['administrative_level_id']))
                    if administrativelevel_obj.cvd:
                        villages = administrativelevel_obj.cvd.get_villages()
                except Exception as e:
                    print(task.get('name'), ', ', task.get('administrative_level_name'),":", e)

                for village in villages:
                    if village.id != int(task['administrative_level_id']):
                        for _t in _fc_tasks:
                            t = _t.get('doc')
                            if t.get('cycle_id') == cycle.couch_id and task['name'] == t['name'] and int(t['administrative_level_id']) == village.id and t.get('type') == 'task':
                                if attachments:
                                    for i in range(len(attachments)):
                                        att = attachments[i]
                                        if att.get('attachment') and att.get('attachment').get("uri") and "https://" in att.get('attachment').get("uri") :
                                            t["attachments"][i] = att
                                if form_response:
                                    t["form_response"] = form_response

                                t["completed_date"] = completed_date
                                t["last_updated"] = last_updated
                                t["completed"] = True

                                nsc.update_cloudant_document(facilitator_database,  t["_id"], t)  # Update task for the facilitator
                                print(t)
                                print()
                                print()
    


def copy_village_datas_completed_to_other_villages_belonging_to_same_canton_for_only_canton_tasks(develop_mode=False, training_mode=False, no_sql_db=False, project_id=None, cycle_id=None):
    
    if no_sql_db:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, no_sql_db_name=no_sql_db)
    else:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, projects__in=[project_id])

    if not cycle_id:
        raise Exception("ID Cycle can't be unknow")
    cycle = Cycle.objects.get(id=cycle_id)
    project = Project.objects.get(id=project_id)
    
    nsc = NoSQLClient()
    for facilitator in facilitators:
        facilitator_database = nsc.get_db(facilitator.no_sql_db_name)
        print(facilitator.no_sql_db_name, facilitator.username)
        
        
        fc_tasks = facilitator_database.all_docs(include_docs=True)['rows']
        fc_tasks = [doc for doc in fc_tasks if doc.get('doc') and doc.get('doc').get('cycle_id') == cycle.couch_id and doc.get('doc').get('project_id') == project.couch_id]
        
        _fc_tasks = fc_tasks.copy()
        for _task in fc_tasks:
            task = _task.get('doc')
            if task.get('cycle_id') == cycle.couch_id and task.get("completed") and task.get('type') == 'task' and (str(task.get('sql_id')) in ['13', '14', '15', '16'] or task.get('activity_name') == "Réunion cantonale"):
                attachments = task.get("attachments")
                form_response = task.get("form_response")
                completed_date = task.get("completed_date")
                last_updated = task.get("last_updated")

                for _t in _fc_tasks:
                    t = _t.get('doc')
                    if t.get('cycle_id') == cycle.couch_id and t.get('type') == 'task' and task['sql_id'] == t['sql_id'] and task['canton_sql_id'] == t['canton_sql_id'] and t['administrative_level_id'] != task['administrative_level_id']:
                        if attachments:
                            for i in range(len(attachments)):
                                att = attachments[i]
                                if att.get('attachment') and att.get('attachment').get("uri") and "https://" in att.get('attachment').get("uri") :
                                    t["attachments"][i] = att
                        if form_response:
                            t["form_response"] = form_response

                        t["completed_date"] = completed_date
                        t["last_updated"] = last_updated
                        t["completed"] = True

                        nsc.update_cloudant_document(facilitator_database,  t["_id"], t)  # Update task for the facilitator
                        print(t)
                        print()
                        print()
    


def clear_facilitators_documents_tasks_administrative_level_not_headquarters(develop_mode=False, training_mode=False, no_sql_db=False, project_id=None):
    if no_sql_db:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, no_sql_db_name=no_sql_db)
    else:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, projects__in=[project_id])
    
    nsc = NoSQLClient()
    for facilitator in facilitators:
        facilitator_database = nsc.get_db(facilitator.no_sql_db_name)
        print(facilitator.no_sql_db_name, facilitator.username)
        doc_facilitator = facilitator_database.get_query_result(
            {"type": "facilitator"}
        )[:][0]

        administrative_level_not_headquarters = []
        for administrativelevel in doc_facilitator['administrative_levels']:
            if not administrativelevel.get('is_headquarters_village'):
                administrative_level_not_headquarters.append(administrativelevel['id'])
        print(administrative_level_not_headquarters)
        clear_facilitator_documents_tasks_by_administrativelevels(facilitator.no_sql_db_name, administrative_level_not_headquarters, False)


def clear_facilitator_documents_tasks_not_sql_id(develop_mode=False, training_mode=False, no_sql_db=False, project_id=None, clear_no_form_response=False):
    if no_sql_db:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, no_sql_db_name=no_sql_db)
    else:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, projects__in=[project_id])
    nsc = NoSQLClient()
    count = 0
    for facilitator in facilitators:
        print()
        print(facilitator)
        nsc_database = nsc.get_db(facilitator.no_sql_db_name)
        fc_docs = nsc_database.all_docs(include_docs=True)['rows']
        
        facilitator_doc = None
        cvds = []
        administrative_levels_id = []
        for _doc in fc_docs:
            doc = _doc.get('doc')
            if doc.get('type') == 'facilitator':
                facilitator_doc = doc
                cvds = get_cvds(facilitator_doc)
                for a in facilitator_doc['administrative_levels']:
                    if a.get('is_headquarters_village'):
                        administrative_levels_id.append(a['id'])
                # for ad in doc.get('administrative_levels'):
                #     if ad.get('is_headquarters_village'):
                #         nbr_cvd += 1
                break
        print(administrative_levels_id)
        for _doc in fc_docs:
            doc = _doc.get('doc')
            if doc.get('type') in ('task', 'free_task') and doc.get('administrative_level_id') != None:
                try:
                    # for cvd in cvds:
                    #     docs = nsc_database.get_query_result({"type": "task", "administrative_level_id": cvd["village_id"], "sql_id": doc["sql_id"]})
                    #     print(len(docs[:]))
                    #     if len(docs[:]) > 1:
                    #         try:
                    #             print(doc)
                    #             d = nsc_database[docs[0][1]['_id']]
                    #             d.delete()
                    #             count += 1
                    #         except Exception as exc:
                    #             print(1, exc)
                    
                    
                    if doc.get('administrative_level_id') not in administrative_levels_id:
                        nsc.delete_document(nsc_database, doc["_id"])
                        count += 1
                        print(doc)

                    if clear_no_form_response and not doc.get('form_response'):
                        nsc.delete_document(nsc_database, doc["_id"])
                        count += 1
                        print(doc)


                except Exception as e:
                    print(2, e)
                try:
                    sql_id = doc["sql_id"]
                    task_order = doc["task_order"]
                    last_updated = doc["last_updated"]
                    canton_sql_id = doc["canton_sql_id"]
                    administrative_level_id = doc["administrative_level_id"]
                except Exception as exc:
                    count += 1
                    print(doc)
                    nsc.delete_document(nsc_database, doc["_id"])
    print() 
    print(count)



def check_cvd_and_tasks_number(develop_mode=False, training_mode=False, no_sql_db=False, project_id=None, cycle_id=None):
    if no_sql_db:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, no_sql_db_name=no_sql_db)
    else:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, projects__in=[project_id])
    nsc = NoSQLClient()
    
    if not cycle_id:
        raise Exception("ID Cycle can't be unknow")
    cycle = Cycle.objects.get(id=cycle_id)
    project = Project.objects.get(id=project_id)

    for facilitator in facilitators:
        nsc_database = nsc.get_db(facilitator.no_sql_db_name)
        fc_docs = nsc_database.all_docs(include_docs=True)['rows']
        
        facilitator_doc = None
        nbr_cvd = 0
        for _doc in fc_docs:
            doc = _doc.get('doc')
            if doc.get('type') == 'facilitator':
                facilitator_doc = doc
                for ad in doc.get('administrative_levels'):
                    if ad.get('is_headquarters_village') and ad.get('project_id') == project.couch_id and ad.get('cycle_id') == cycle.couch_id:
                        nbr_cvd += 1
                break

        fc_docs = [doc for doc in fc_docs if doc.get('doc') and doc.get('doc').get('cycle_id') == cycle.couch_id and doc.get('doc').get('project_id') == project.couch_id]

        nbr_tasks = 0
        if facilitator_doc:
            for _doc in fc_docs:
                doc = _doc.get('doc')
                if doc.get('cycle_id') == cycle.couch_id and doc.get('type') == 'task':
                    nbr_tasks += 1
        
        n_task = nbr_tasks/nbr_cvd if nbr_cvd else 0
        if n_task != Task.objects.filter(project_id=project_id).count():
            print()
            print(facilitator.no_sql_db_name, facilitator.username)
            print(f"CVD : {nbr_cvd} ; Tasks : {nbr_tasks} ; {n_task}")


def map_users_to_their_db(develop_mode=False, training_mode=False, no_sql_db=False,project_id=None):
    if no_sql_db:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, no_sql_db_name=no_sql_db)
    else:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, projects__in=[project_id])
    nsc = NoSQLClient()
    nsc_database = nsc.get_db("_users")
    for facilitator in facilitators:
        print()
        print(facilitator.no_sql_db_name, facilitator.username)
        user =  nsc_database.get_query_result({"type": 'user', "name": facilitator.no_sql_user})[:][0]
        user["password"] = facilitator.no_sql_pass
        nsc_database.bulk_docs([user])
        facilitator_db = nsc.get_db(facilitator.no_sql_db_name)
        nsc.add_member_to_database(facilitator_db, facilitator.no_sql_user)
        print("updated")

        #nsc_database.create_document({'_id': f'org.couchdb.user:1670846715',"name": "1670846715","type": "user","roles": [],"password": "HztsITGzOvlhPD6KzQ"})
        print()



def sync_clear_reponse_data_set_task_on_uncomplete(develop_mode, training_mode, administrativelevel_ids, tasks_ids, no_sql_db=False, project_id=None):
    if tasks_ids:
        tasks = Task.objects.filter(id__in=tasks_ids).prefetch_related()
    else:
        tasks = Task.objects.filter(project_id=project_id).prefetch_related()
    for task in tasks:
        print('syncing: ', task.phase.order, task.activity.order, task.order)
        clear_reponse_data_set_task_on_uncomplete(task, develop_mode, training_mode, no_sql_db, administrativelevel_ids, project_id=project_id)

def clear_reponse_data_set_task_on_uncomplete(task_model, develop_mode=False, trainning_mode=False, no_sql_db=False, administrativelevel_ids=[], project_id=None):
    if no_sql_db:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=trainning_mode, no_sql_db_name=no_sql_db)
    else:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=trainning_mode, projects__in=[project_id])

    nsc = NoSQLClient()
    for facilitator in facilitators:
        facilitator_database = nsc.get_db(facilitator.no_sql_db_name)
        print(facilitator.no_sql_db_name, facilitator.username)
        facilitator_administrative_levels = facilitator_database.get_query_result(
            {"type": "facilitator"}
        )[0]

        # Iterate every administrative level assigned to the facilitator
        for administrative_level in facilitator_administrative_levels[0]['administrative_levels']:
            canton_sql_id = None
            try:
                administrativelevel_obj = administrativelevels_models.AdministrativeLevel.objects.using('mis').get(id=int(administrative_level['id']))
                canton_sql_id = str(administrativelevel_obj.parent.id)
            except Exception as e:
                pass

            if(
                (administrative_level.get('is_headquarters_village') and not administrativelevel_ids)
                or
                (administrative_level.get('is_headquarters_village') and administrativelevel_ids and str(administrative_level['id']) in administrativelevel_ids)
                or
                (administrative_level.get('is_headquarters_village') and administrativelevel_ids and canton_sql_id and canton_sql_id in administrativelevel_ids)
               ):
                
                fc_task = facilitator_database.get_query_result({
                    "administrative_level_id": administrative_level['id'],
                    "sql_id": task_model.id
                })[0]
                
                if len(fc_task) > 0:
                    _fc_task = fc_task[0].copy()
                    if (_fc_task['form'][0]['options']['fields']['generalitiesSurVillage']['label'] != "Section 1: caractéristiques générales du quartier/village") or (
                        _fc_task['form_response'] and _fc_task['form_response'][0] and _fc_task['form_response'][0].get('generalitiesSurVillage') and _fc_task['form_response'][0]['generalitiesSurVillage'].get('pisteRurale') != None
                    ):
                        _fc_task['completed'] = False
                        _fc_task["form_response"] = []

                        nsc.update_cloudant_document(facilitator_database,  _fc_task["_id"], _fc_task)
                        print(_fc_task)


                    

def copy_village_pac_completed_to_other_villages_belonging_to_same_canton(develop_mode=False, training_mode=False, no_sql_db=False, project_id=None, cycle_id=None):
    
    if no_sql_db:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, no_sql_db_name=no_sql_db)
    else:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, projects__in=[project_id])

    if not cycle_id:
        raise Exception("ID Cycle can't be unknow")
    cycle = Cycle.objects.get(id=cycle_id)
    project = Project.objects.get(id=project_id)

    nsc = NoSQLClient()
    for facilitator in facilitators:
        facilitator_database = nsc.get_db(facilitator.no_sql_db_name)
        print(facilitator.no_sql_db_name, facilitator.username)
        
        
        
        fc_tasks = facilitator_database.get_query_result({
            'type': 'task',
            'sql_id': 47,
            "cycle_id": cycle.couch_id,
            "project_id": project.couch_id
        })[:]
        
        for task in fc_tasks:
            attachments = task.get("attachments")

            for f_same_canton in facilitators:
                f_same_canton_database = nsc.get_db(f_same_canton.no_sql_db_name)
                fc_tasks_same_canton = f_same_canton_database.get_query_result({
                    'type': 'task',
                    'sql_id': 47,
                    'canton_sql_id': task.get("canton_sql_id"),
                    "cycle_id": cycle.couch_id,
                    "project_id": project.couch_id
                })[:]
                if attachments:
                    att = attachments[5]
                    if (att.get('name') == "Télecharger le document du plan d'actions cantonales finalisé" and att.get('attachment') and att.get('attachment').get("uri") and "https://" in att['attachment']['uri']):
                        for _task in fc_tasks_same_canton:
                            _att = _task['attachments'][5]
                            if _att.get('name') == "Télecharger le document du plan d'actions cantonales finalisé" and (
                                not _att.get('attachment') or (
                                    _att.get('attachment').get("uri") and (
                                        "https://" not in _att['attachment']['uri']
                                    )
                                )
                            ):
                                _task['attachments'][5] = att
                                print("==========> ", f_same_canton.no_sql_db_name, f_same_canton.username)
                                nsc.update_cloudant_document(f_same_canton_database,  _task["_id"], _task)  # Update task for the facilitator
                                print(_task)
                                print()
                                print()



def add_facilitator_design(develop_mode=False, trainning_mode=False, no_sql_dbs=False, project_id=None):
    if no_sql_dbs:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=trainning_mode, no_sql_db_name__in=no_sql_dbs)
    else:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=trainning_mode, projects__in=[project_id])

    nsc = NoSQLClient()
    nsc_database = nsc.get_db("process_design")
    
    doc_designs = [
        # nsc_database.get_design_document('_design/views_docs')[:],
        (nsc_database.get_design_document('_design/tasks_number'), False),
        (nsc_database.get_query_result({"type": "geolocation"})[:], True),
        (nsc_database.get_design_document('_design/task_stats'), False),
    ]

    for doc_design, will_be_delete in doc_designs:
        if doc_design and type(doc_design) is list:
            doc_design = doc_design[0]

        if doc_design:
            if will_be_delete:
                del doc_design['_id']
            del doc_design['_rev']
            
            for facilitator in facilitators:
                try:
                    facilitator_database = nsc.get_db(facilitator.no_sql_db_name)

                    if doc_design.get('type') == "geolocation":
                        _f_design = facilitator_database.get_query_result({"type": "geolocation"})[:]
                    elif '_id' in doc_design and '_design' in doc_design['_id']:
                        _f_design = facilitator_database.get_design_document(doc_design['_id'])

                    if not _f_design or (_f_design and type(_f_design) is not list and not _f_design.get('_rev')):
                        _doc = nsc.create_document(facilitator_database, doc_design)
                        
                    elif '_id' in doc_design and '_design' in doc_design['_id'] and _f_design and _f_design.get('_rev'):
                        #Update phase if it exists
                        _doc_design = doc_design.copy()
                        del _doc_design['_id']

                        nsc.update_doc_uncontrolled(facilitator_database,  _f_design["_id"], _doc_design) # Update phase for the facilitator
                except Exception as exc:
                    print(exc, "Error creating investment", facilitator.no_sql_db_name)
            
        
def format_datestr_to_dateobject(doc, attr):
    _ = datetime_complet_str(doc.get(attr))
    if _ == "0000-00-00 00:00:00":
        _d = None
    else:
        _d = datetime.strptime(_, '%Y-%m-%d %H:%M:%S')
    return _d


def format_date():
    nsc = NoSQLClient()
    for f in Facilitator.objects.all():
        facilitator_db = nsc.get_db(f.no_sql_db_name)
        docs = facilitator_db.all_docs(include_docs=True)['rows']

        for _doc in docs:
            doc = _doc.get('doc')
            if doc.get('type') == "task":
                _task = {}
                    
                _task['last_updated'] = format_datestr_to_dateobject(datetime_complet_str(doc.get('last_updated')))
                _task['last_updated'] = format_datestr_to_dateobject(datetime_complet_str(doc.get('last_updated')))
                    
                nsc.update_cloudant_document(facilitator_db,  doc["_id"], _task)
                
                
                
                
                
def test():
    nsc = NoSQLClient()
    eadls = nsc.get_db('eadls')
    
    liste_A = ["4597"]
    resultats = eadls.get_view_result('administrative_regions', 'elements_in_list', keys=liste_A)
    
    print(len(resultats[:]))


def test1():
    nsc = NoSQLClient()
    eadls = nsc.get_db('eadls')

    village_ids_to_check = [2077]

    results = eadls.get_view_result("_design/adl_village_filter", "by_village_id", keys=village_ids_to_check,include_docs=True)
    
    return results


def default_project_to_assign(name="COSO", develop_mode=False, training_mode=False):
    project = Project.objects.filter(name=name).first()

    nsc = NoSQLClient()
    db = nsc.get_db("backup_db_facilitators_docs")
    fc_docs = db.all_docs(include_docs=True)['rows']
    for _doc in fc_docs:
        doc = _doc.get('doc')
        if not doc.get('project_name') and doc.get('type') in ["phase", "activity", "task", "free_task"]:
            doc["project_name"] = project.name
            doc["project_id"] = project.couch_id
            nsc.update_cloudant_document(db,  doc["_id"], doc)

    facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, projects__in=[project.id])

    if project and facilitators:

        if facilitators:
            nsc = NoSQLClient()
            for f in facilitators:
                print(f.name)
                db = nsc.get_db(f.no_sql_db_name)

    #             docs = db.get_query_result({"type": "facilitator"})[0]

    #             if len(docs) > 0:
    #                 doc = docs[0].copy()
    #                 doc["project_id"] = project.couch_id
    #                 doc["project_name"] = project.name
    #                 doc["projects_ids"] = [project.couch_id]

    #                 nsc.update_cloudant_document(db,  doc["_id"], doc)
    

                fc_docs = db.all_docs(include_docs=True)['rows']
                for _doc in fc_docs:
                    doc = _doc.get('doc')
                    # if not doc.get('project_name') and doc.get('type') in ["phase", "activity", "task", "free_task"]:
                    #     doc["project_name"] = project.name
                    #     doc["project_id"] = project.couch_id
                    #     nsc.update_cloudant_document(db,  doc["_id"], doc)
                    if not doc.get('project_name') and doc.get('type') == "task":
                        doc["project_name"] = project.name
                        doc["project_id"] = project.couch_id
                        nsc.update_cloudant_document(db,  doc["_id"], doc)


    # aggregated_status_null = AggregatedStatus.objects.filter(project__isnull=True)

    # if project and aggregated_status_null:
    #     aggregated_status_null.update(project=project)


    # facilitators = Facilitator.objects.filter(projects__isnull=True)
    # users = User.objects.filter(projects__isnull=True)

    # if project and (facilitators or users):

    #     if facilitators:
    #         project.facilitators.add(*facilitators)
    #     if users:
    #         project.users.add(*users)
    #     project.save()

    #     if facilitators:
    #         nsc = NoSQLClient()
    #         for f in facilitators:
    #             print(f.name)
    #             db = nsc.get_db(f.no_sql_db_name)

    #             docs = db.get_query_result({"type": "facilitator"})[0]

    #             if len(docs) > 0:
    #                 doc = docs[0].copy()
    #                 doc["project_id"] = project.couch_id
    #                 doc["project_name"] = project.name
    #                 doc["projects_ids"] = [project.couch_id]

    #                 nsc.update_cloudant_document(db,  doc["_id"], doc)
    

    #             fc_docs = db.all_docs(include_docs=True)['rows']
    #             for _doc in fc_docs:
    #                 doc = _doc.get('doc')
    #                 if not doc.get('project_name') and doc.get('type') in ["phase", "activity", "task", "free_task"]:
    #                     doc["project_name"] = project.name
    #                     doc["project_id"] = project.couch_id
    #                     nsc.update_cloudant_document(db,  doc["_id"], doc)


#search_facilitators_db_with_villages_stabilized MGP adl
# -
def search_facilitators_db_with_villages_stabilized(project_name, develop_mode=False, trainning_mode=False, active=True, no_sql_db=None, no_sql_dbs=None):
    project = Project.objects.filter(name=project_name).first()
    projects = project.build_the_tree_structure()
    _facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=trainning_mode, projects__in=[project.id])
    if no_sql_db or no_sql_dbs:
        if not no_sql_dbs:
            no_sql_dbs = []
        if no_sql_db:
            no_sql_dbs.append(no_sql_db)

        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=trainning_mode, active=active, no_sql_db_name__in=no_sql_dbs).order_by("name")
    else:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=trainning_mode, active=active, projects__in=[project.id]).order_by("name")
    
    # emails = [f.email for f in facilitators if f.email]

    nsc = NoSQLClient()
    # eadls = nsc.get_db('eadls')
    # docs_eadls = eadls.all_docs(include_docs=True)['rows']
    """
    "3805",
    "3804"
    """
    # for _doc in docs_eadls:
    #     no_sql_dbs_names = []
    #     doc = _doc.get('doc')
    #     if doc.get('type') == "adl" and doc.get('representative') and doc.get('administrative_regions_objects') and doc['representative'].get('email') in emails:
    #         print(doc['representative'].get('name'), doc['representative'].get('email'))
    #         facilitator = facilitators.filter(email=doc['representative'].get('email')).first()
            
    #         # villages = []
    #         # for c in doc['administrative_regions_objects']:
    #         #     villages += c['villages']
            
    #         villages_ids = list(itertools.chain(*[[int(v['id']) for v in ad['villages']] for ad in doc['administrative_regions_objects']]))

    for facilitator in facilitators:
        if facilitator.stabilization_administrative_ids or facilitator.additional_administrative_ids:
            print(facilitator.name, facilitator.email)

            villages_ids = list(set((facilitator.stabilization_administrative_ids or []) + (facilitator.additional_administrative_ids or [])))

            facilitators_ids = list(
                mis_objects_call
                .filter_objects(
                    AssignAdministrativeLevelToFacilitator,
                    administrative_level_id__in=villages_ids, project_id__in=[_p.id for _p in mis_objects_call.filter_objects(ProjectMis, name__in=[p.name for p in projects])], activated=True
                )
                .exclude(facilitator_id=facilitator.id)
                .values_list('facilitator_id', flat=True)
            )
            if facilitators_ids:
                no_sql_dbs_names = list(_facilitators.filter(id__in=facilitators_ids).values_list('no_sql_db_name', flat=True))
            # if villages:
            #     for f in _facilitators:
            #         if f.email != doc['representative'].get('email'):
            #             print(f.name)
            #             db = nsc.get_db(f.no_sql_db_name)
            #             docs = db.get_query_result({"type": "facilitator"})[0]
            #             if len(docs) > 0:
            #                 for adl in docs[0]['administrative_levels']:
            #                     if  len([v for v in villages if str(v.get('id')) == adl.get('id')]) > 0:
            #                         no_sql_dbs_names.append(f.no_sql_db_name)
            #                         break
            

            if facilitator and facilitator.no_sql_dbs_names != no_sql_dbs_names:
                    
                print(f"Old {facilitator.no_sql_dbs_names} ; New : {no_sql_dbs_names}")

                facilitator.no_sql_dbs_names = no_sql_dbs_names
                facilitator = facilitator.save_and_return_object()

                db = nsc.get_db(facilitator.no_sql_db_name)
                docs = db.get_query_result({"type": "facilitator"})[0]
                if len(docs) > 0:
                    __doc = docs[0].copy()
                    __doc["no_sql_dbs_names"] = no_sql_dbs_names
                    nsc.update_cloudant_document(db,  __doc["_id"], __doc)
            else:
                print("No updated")
            print()


# def search_facilitators_db_with_villages_stabilized_using_assign_model(name="COSO", develop_mode=False, trainning_mode=False, no_sql_db=False):

#     project = Project.objects.filter(name=name).first()
#     if no_sql_db:
#         facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=trainning_mode, no_sql_db_name=no_sql_db)
#     else:
#         facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=trainning_mode, projects__in=[project.id])


#     nsc = NoSQLClient()
#     eadls = nsc.get_db('eadls')
#     docs_eadls = eadls.all_docs(include_docs=True)['rows']
#     """
#     "3805",
#     "3804"
#     """
#     for _doc in docs_eadls:
#         no_sql_dbs_names = []
#         doc = _doc.get('doc')
#         if doc.get('type') == "adl" and doc.get('representative') and doc.get('administrative_regions_objects'):
#             print(doc['representative'].get('name'), doc['representative'].get('email'))

#             villages = []
#             for c in doc['administrative_regions_objects']:
#                 villages += c['villages']
            

#             if villages:
#                 for f in facilitators:
#                     if f.email != doc['representative'].get('email'):
#                         print(f.name)
#                         db = nsc.get_db(f.no_sql_db_name)
#                         docs = db.get_query_result({"type": "facilitator"})[0]
#                         if len(docs) > 0:
#                             for adl in docs[0]['administrative_levels']:
#                                 if  len([v for v in villages if str(v.get('id')) == adl.get('id')]) > 0:
#                                     no_sql_dbs_names.append(f.no_sql_db_name)
#                                     break
                
#             print(no_sql_dbs_names)
#             facilitator = Facilitator.objects.filter(email=doc['representative'].get('email'), develop_mode=False, training_mode=False).first()
#             if facilitator:
#                 facilitator.no_sql_dbs_names = no_sql_dbs_names
#                 facilitator = facilitator.save_and_return_object()

#                 db = nsc.get_db(facilitator.no_sql_db_name)
#                 docs = db.get_query_result({"type": "facilitator"})[0]
#                 if len(docs) > 0:
#                     doc = docs[0].copy()
#                     doc["no_sql_dbs_names"] = no_sql_dbs_names
#                     nsc.update_cloudant_document(db,  doc["_id"], doc)



def default_project_to_assign(name="COSO", develop_mode=False, training_mode=False):
    project = Project.objects.filter(name=name).first()

    nsc = NoSQLClient()
    db = nsc.get_db("backup_db_facilitators_docs")
    fc_docs = db.all_docs(include_docs=True)['rows']
    for _doc in fc_docs:
        doc = _doc.get('doc')
        if not doc.get('project_name') and doc.get('type') in ["phase", "activity", "task", "free_task"]:
            doc["project_name"] = project.name
            doc["project_id"] = project.couch_id
            nsc.update_cloudant_document(db,  doc["_id"], doc)

    facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, projects__in=[project.id])

    if project and facilitators:

        if facilitators:
            nsc = NoSQLClient()
            for f in facilitators:
                print(f.name)
                db = nsc.get_db(f.no_sql_db_name)

    #             docs = db.get_query_result({"type": "facilitator"})[0]

    #             if len(docs) > 0:
    #                 doc = docs[0].copy()
    #                 doc["project_id"] = project.couch_id
    #                 doc["project_name"] = project.name
    #                 doc["projects_ids"] = [project.couch_id]

    #                 nsc.update_cloudant_document(db,  doc["_id"], doc)
    

                fc_docs = db.all_docs(include_docs=True)['rows']
                for _doc in fc_docs:
                    doc = _doc.get('doc')
                    if not doc.get('project_name') and doc.get('type') in ["phase", "activity", "task", "free_task"]:
                        doc["project_name"] = project.name
                        doc["project_id"] = project.couch_id
                        nsc.update_cloudant_document(db,  doc["_id"], doc)
                    # if not doc.get('project_name') and doc.get('type') == "task":
                    #     doc["project_name"] = project.name
                    #     doc["project_id"] = project.couch_id
                    #     nsc.update_cloudant_document(db,  doc["_id"], doc)


    # aggregated_status_null = AggregatedStatus.objects.filter(project__isnull=True)

    # if project and aggregated_status_null:
    #     aggregated_status_null.update(project=project)


    # facilitators = Facilitator.objects.filter(projects__isnull=True)
    # users = User.objects.filter(projects__isnull=True)

    # if project and (facilitators or users):

    #     if facilitators:
    #         project.facilitators.add(*facilitators)
    #     if users:
    #         project.users.add(*users)
    #     project.save()

    #     if facilitators:
    #         nsc = NoSQLClient()
    #         for f in facilitators:
    #             print(f.name)
    #             db = nsc.get_db(f.no_sql_db_name)

    #             docs = db.get_query_result({"type": "facilitator"})[0]

    #             if len(docs) > 0:
    #                 doc = docs[0].copy()
    #                 doc["project_id"] = project.couch_id
    #                 doc["project_name"] = project.name
    #                 doc["projects_ids"] = [project.couch_id]

    #                 nsc.update_cloudant_document(db,  doc["_id"], doc)
    

    #             fc_docs = db.all_docs(include_docs=True)['rows']
    #             for _doc in fc_docs:
    #                 doc = _doc.get('doc')
    #                 if not doc.get('project_name') and doc.get('type') in ["phase", "activity", "task", "free_task"]:
    #                     doc["project_name"] = project.name
    #                     doc["project_id"] = project.couch_id
    #                     nsc.update_cloudant_document(db,  doc["_id"], doc)


def add_default_necessary_attrs_couchdb_and_on_objects(project_name="COSO"):
    nsc = NoSQLClient()
    if project_name:
        projects = Project.objects.filter(name=project_name)
    else:
        projects = Project.objects.all()
    print("Start")
    for project in projects:
        print(f"\n\n\t=============={project.name}===========\n")
        cycle = Cycle.objects.get(project_id=project.id, order=1)
        db = nsc.get_db("process_design")
        docs = db.get_query_result({"sql_id": project.id, "_id": project.couch_id, 'type': 'project'})[0]
        if not len(docs):
            data_project = project.serialize_project(project)
            docs = [nsc.create_document(db, {**data_project, "_id": project.couch_id})]

        if len(docs) > 0:
            doc = docs[0].copy()
            project.couch_id = doc['_id']
            project.save()

            phases = Phase.objects.filter(project_id=project.id)

            print("Start with Pahse, Activities and Tasks objects")
            for phase in phases:
                docs = db.get_query_result({'type': 'phase', 'project_id': project.couch_id, 'sql_id': phase.id})[0]
                if len(docs) > 0:
                    doc = docs[0].copy()
                    phase.couch_id = doc['_id']
                    phase.cycles.set([cycle])
                    phase.save()

                    # doc['project_name'] = project.name
                    # doc['project_id'] = project.couch_id
                    # doc['cycles'] = [cycle.couch_id]
                    # nsc.update_cloudant_document(db,  doc["_id"], doc)


            activities = Activity.objects.filter(project_id=project.id)

            for activity in activities:
                docs = db.get_query_result({'type': 'activity', 'project_id': project.couch_id, 'sql_id': activity.id})[0]
                if len(docs) > 0:
                    doc = docs[0].copy()
                    activity.couch_id = doc['_id']
                    activity.cycles.set([cycle])
                    activity.save()

                    # doc['project_name'] = project.name
                    # doc['project_id'] = project.couch_id
                    # doc['phase_id'] = activity.phase.couch_id
                    # doc['cycles'] = [cycle.couch_id]
                    # nsc.update_cloudant_document(db,  doc["_id"], doc)


            tasks = Task.objects.filter(project_id=project.id)

            for task in tasks:
                docs = db.get_query_result({'type': 'task', 'project_id': project.couch_id, 'sql_id': task.id})[0]
                if len(docs) > 0:
                    doc = docs[0].copy()
                    task.couch_id = doc['_id']
                    task.cycles.set([cycle])
                    task.save()

                    # doc['project_name'] = project.name
                    # doc['project_id'] = project.couch_id
                    # doc['phase_id'] = task.phase.couch_id
                    # doc['activity_id'] = task.activity.couch_id
                    # doc['cycles'] = [cycle.couch_id]
                    # nsc.update_cloudant_document(db,  doc["_id"], doc)

            
            print("Start with Pahse, Activities and Tasks docs")
            for phase in phases:
                docs = db.get_query_result({'type': 'phase', 'project_id': project.couch_id, 'sql_id': phase.id})[0]
                if len(docs) > 0:
                    doc = docs[0].copy()
                    doc['project_name'] = project.name
                    doc['project_id'] = project.couch_id
                    doc['cycles'] = [cycle.couch_id]
                    
                    nsc.update_cloudant_document(db,  doc["_id"], doc)

            for activity in activities:
                docs = db.get_query_result({'type': 'activity', 'project_id': project.couch_id, 'sql_id': activity.id})[0]
                if len(docs) > 0:
                    doc = docs[0].copy()
                    doc['project_name'] = project.name
                    doc['project_id'] = project.couch_id
                    doc['phase_id'] = activity.phase.couch_id
                    doc['cycles'] = [cycle.couch_id]
                    
                    nsc.update_cloudant_document(db,  doc["_id"], doc)

            for task in tasks:
                docs = db.get_query_result({'type': 'task', 'project_id': project.couch_id, 'sql_id': task.id})[0]
                if len(docs) > 0:
                    doc = docs[0].copy()
                    doc['project_name'] = project.name
                    doc['project_id'] = project.couch_id
                    doc['phase_id'] = task.phase.couch_id
                    doc['activity_id'] = task.activity.couch_id
                    doc['cycles'] = [cycle.couch_id]
                    
                    nsc.update_cloudant_document(db,  doc["_id"], doc)



            print("Start for backup_db_facilitators_docs DB")
            db = nsc.get_db("backup_db_facilitators_docs")
            fc_docs = db.all_docs(include_docs=True)['rows']
            for _doc in fc_docs:
                doc = _doc.get('doc')
                if doc.get('project_id') == project.couch_id and doc.get('type') in ["phase", "activity", "task", "free_task"]:
                    doc["project_name"] = project.name
                    doc["project_id"] = project.couch_id
                    doc["cycle_id"] = cycle.couch_id
                    doc["cycle_name"] = cycle.name
                    
                    nsc.update_cloudant_document(db,  doc["_id"], doc)


            print("Start for facilitators DB")
            facilitators = Facilitator.objects.filter(projects__in=[project.id]).order_by('name')
            if facilitators:
                # count = 0
                for f in facilitators:
                    print(f.name, f.no_sql_db_name)
                    # try:
                    db = nsc.get_db(f.no_sql_db_name)


                    nsc_database = nsc.get_db("process_design")
                    cycle_docs = nsc_database.get_query_result({"_id": cycle.couch_id})[0]
                    if not len(cycle_docs):
                        data_cycle = cycle.serialize_project(cycle)
                        cycle_docs = [nsc.create_document(db, {**data_cycle, "_id": cycle.couch_id, "capacity_attachments": cycle.capacity_attachments})]
                    
                    fc_cycle = db.get_query_result(
                        {"type": "cycle", "name": cycle.name, "project_id": project.couch_id}
                    )[0]
                    if not len(fc_cycle):
                        nsc.create_document(db, cycle_docs[0])


                    fc_docs = db.all_docs(include_docs=True)['rows']
                    for _doc in fc_docs:
                        doc = _doc.get('doc')
                        if doc.get('project_id') == project.couch_id and doc.get('type') in ["phase", "activity", "task", "free_task"]:
                            doc["project_name"] = project.name
                            doc["project_id"] = project.couch_id
                            doc["cycle_id"] = cycle.couch_id
                            doc["cycle_name"] = cycle.name
                            
                            nsc.update_cloudant_document(db,  doc["_id"], doc)

                        elif doc.get('type') == "facilitator":
                            administrative_levels = doc['administrative_levels']
                            for i_range in range(len(administrative_levels)):
                                if 'project_id' not in administrative_levels[i_range]:
                                    doc['administrative_levels'][i_range]['project_name'] = project.name
                                    doc['administrative_levels'][i_range]['project_id'] = project.couch_id
                                    doc['administrative_levels'][i_range]['cycle_name'] = cycle.name
                                    doc['administrative_levels'][i_range]['cycle_id'] = cycle.couch_id
                            
                            doc["projects_ids"] = [
                                project.couch_id
                            ] if 'projects_ids' not in doc or not doc.get('projects_ids') else list(set(doc["projects_ids"] + [project.couch_id]))
                            doc["projects_names"] = [
                                project.name
                            ] if 'projects_names' not in doc or not doc.get('projects_names') else list(set(doc["projects_names"] + [project.name]))
                            
                            nsc.update_cloudant_document(db,  doc["_id"], doc)
                        
                    
                    # count += 1
                    # if count <= 10:
                    #     print("continue", count)
                    #     continue
                    
                    # except Exception as exc:
                    #     print(f.name, exc)

    print("\nEnd")

def add_attr_total_number_of_tasks_on_facilitators_doc(develop_mode=False, trainning_mode=False):
    for cycle in Cycle.objects.all():

        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=trainning_mode, projects__in=[cycle.project.id])

        if cycle.project and facilitators:
                
            nsc = NoSQLClient()
            for f in facilitators:
                print(f.name)
                db = nsc.get_db(f.no_sql_db_name)

                docs = db.get_query_result({"type": "facilitator"})[0]

                if len(docs) > 0:
                    doc = docs[0].copy()
                    # doc["total_number_of_tasks"] = Task.objects.filter(project_id=cycle.project.id, cycles__in=[Cycle.objects.get(order=1, project_id=cycle.project.id).id]).count()
                    
                    doc['total_tasks_by_project_by_cycle'] = {}
                    for _project in Project.objects.all():
                        _cycles = Cycle.objects.filter(project_id=_project.id)
                        doc['total_tasks_by_project_by_cycle'][_project.couch_id] = {}
                        doc['total_tasks_by_project_by_cycle'][_project.name] = {}
                        for _cycle in _cycles:
                            total_tasks_p_c = Task.objects.filter(project_id=_project.id, cycles__in=[_cycle.id]).count()
                            doc['total_tasks_by_project_by_cycle'][_project.couch_id][_cycle.couch_id] = total_tasks_p_c
                            doc['total_tasks_by_project_by_cycle'][_project.name][_cycle.name] = total_tasks_p_c
                            
                    nsc.update_cloudant_document(db,  doc["_id"], doc)
        
        nsc_database = nsc.get_db("process_design")
        _doc = nsc_database.get_query_result(
            {"_id": cycle.couch_id}
        )[0]
        if _doc:
            _doc["total_number_of_tasks"] = Task.objects.filter(project_id=cycle.project.id, cycles__in=[cycle.id]).count()
            nsc.update_cloudant_document(nsc_database,  _doc["_id"], _doc)


def add_attr_facilitator_type_on_facilitators_doc(name="COSO", facilitator_type='community_facilitator'):
    project = Project.objects.filter(name=name).first()

    facilitators = Facilitator.objects.filter(facilitator_type='community_facilitator', projects__in=[project.id])

    if project and facilitators:
            
        nsc = NoSQLClient()
        for f in facilitators:
            print(f.name)
            db = nsc.get_db(f.no_sql_db_name)

            docs = db.get_query_result({
                "type": "facilitator",
                "$or": [
                    {
                        "facilitator_type": {
                            "$in": [
                                None,
                                ""
                            ]
                        }
                    },
                    {
                        "facilitator_type": {
                            "$exists": False
                        }
                    }
                ]
            })[0]

            if len(docs) > 0:
                doc = docs[0].copy()
                doc["facilitator_type"] = facilitator_type

                nsc.update_cloudant_document(db,  doc["_id"], doc)

                print(f.name, "done!")

    print("")
    print("End")



# from authentication.models import Facilitator
# from process_manager.models import Task, Phase, Activity, Project, Cycle
# from no_sql_client import NoSQLClient
# from django.utils.translation import gettext_lazy
# from cdd.my_librairies.mail.send_mail import send_email
# def put_task_to_pending_invalidated(project_id, cycle_id, task_ids, develop_mode=False, training_mode=False):
#     _fs = []
#     nsc = NoSQLClient()
#     project = Project.objects.get(id=project_id)
#     cycle = Cycle.objects.get(id=cycle_id)
#     facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, projects__in=[project_id])
#     in_validation_comment = """Nous invalidons et metons cette tâche en cours uniquement en raison d'un problème qui avait survenu et qui avait fait perdre les photos de cette tâche. 
#     Nous vous prions de nous aider à retélécharger ces photos sur l'application. Merci pour votre compréhension et désolé pour cet desagrement.
#     """
#     date_validated = "2025-5-1 19:00:27"
#     if facilitators:
#         for f in facilitators:
#             print(f.name)
#             db = nsc.get_db(f.no_sql_db_name)
#             fc_docs = db.all_docs(include_docs=True)['rows']
#             fc_docs = [doc for doc in fc_docs if doc.get('doc') and doc.get('doc').get('type') == 'task' and doc.get('doc').get('completed') == True and doc.get('doc').get('sql_id') in task_ids and doc.get('doc').get('cycle_id') == cycle.couch_id and doc.get('doc').get('project_id') == project.couch_id]
#             for _doc in fc_docs:
#                 doc = _doc.get('doc')
#                 doc["completed"] = False
#                 actions_by = doc.get('actions_by') if doc.get('actions_by') else []
#                 action_by = {
#                     'type': "Invalidated", 
#                     'user_name': 'vincent', 
#                     'user_id': 2,
#                     'user_last_name': 'ADABOUNOU', 
#                     'user_first_name': 'Vincent',
#                     'user_email': 'adaboubvincent@gmail.com', 
#                     'action_date': date_validated,
#                     'comment': in_validation_comment
#                 }
#                 actions_by.insert(0, action_by)
#                 doc["validated"] = False
#                 doc["date_validated"] = None,
#                 doc["action_by"] = action_by,
#                 doc["actions_by"] = actions_by
#                 nsc.update_cloudant_document(db,  doc["_id"], doc)
#                 _fs.append(f)
#     try:
#         _task_name = ", ".join(list(set([doc.get('doc').get('name') for doc in fc_docs])))
#         msg = send_email(
#             f'{gettext_lazy("Task Invalided")} : {_task_name}',
#             "mail/send/comment",
#             {
#                 "datas": {
#                     gettext_lazy("Title"): gettext_lazy("Task Invalided"), 
#                     gettext_lazy("Comment"): in_validation_comment,
#                     gettext_lazy("Phase"): ", ".join(list(set([doc.get('doc').get('phase_name') for doc in fc_docs]))),
#                     gettext_lazy("Activity"): ", ".join(list(set([doc.get('doc').get('activity_name') for doc in fc_docs]))),
#                     gettext_lazy("Task"): _task_name,
#                     gettext_lazy("Location Name"): None,
#                     gettext_lazy("Date"): date_validated
#                 },
#                 "user": {
#                     gettext_lazy("Facilitator Name"): ", ".join(list(set([_f.name for _f in _fs]))),
#                     gettext_lazy("Facilitator Phone"): ", ".join(list(set([_f.phone for _f in _fs]))),
#                     gettext_lazy("Facilitator Sex"): ", ".join(list(set(["F" if _f.sex == "Mme" else "M" for _f in _fs]))),
#                     gettext_lazy("Validator"): f"ADABOUNOU Vincent",
#                     gettext_lazy("Validator Type"): "Administrateur principal",
#                     gettext_lazy("Validator Email"): 'adaboubvincent@gmail.com'
#                 },
#                 "url": None
#             },
#             list(set([_f.email for _f in _fs]))
#         )
#         mail_message = gettext_lazy("Mail sent successfully")
#     except Exception as exc:
#         mail_message = gettext_lazy("An error occurred while sending the email")
#     return _fs, mail_message





def update_facilitators_ads_for_error_adls_deleting(project_name="COSO"):
    _updated_ = []

    nsc = NoSQLClient()
    if project_name:
        projects = Project.objects.filter(name=project_name)
    else:
        projects = Project.objects.all()
    print("Start")
    for project in projects:
        print(f"\n\n\t=============={project.name}===========\n")
        cycle = Cycle.objects.get(project_id=project.id, order=1)


        facilitators = Facilitator.objects.filter(projects__in=[project.id], develop_mode=False, training_mode=False).order_by('name')
        if facilitators:
            
            for f in facilitators:
                print(f.name, f.no_sql_db_name)
                
                db = nsc.get_db(f.no_sql_db_name)

                _docs = db.get_query_result({"type": 'facilitator'})[:]
                fc_doc = db[_docs[0]['_id']]
                administrative_levels = list(fc_doc['administrative_levels']) #[_a for _a in list(fc_doc['administrative_levels']) if _a.get('project_name') != 'COSO']

                fc_docs = db.all_docs(include_docs=True)['rows']

                _adls = []
                for _doc in fc_docs:
                    doc = _doc.get('doc')
                    if doc.get('project_id') == project.couch_id and doc.get('cycle_id') == cycle.couch_id and doc.get('type') == "task" and doc.get('administrative_level_id'):
                        if (not any(_ad for _ad in _adls if _ad['project_id'] == doc['project_id'] and _ad['cycle_id'] == doc['cycle_id'] and _ad['id'] == doc['administrative_level_id'])) and \
                            not any(_ad for _ad in administrative_levels if _ad['project_id'] == doc['project_id'] and _ad['cycle_id'] == doc['cycle_id'] and _ad['id'] == doc['administrative_level_id']):
                            _adls.append({
                                "name": doc['administrative_level_name'],
                                "id": doc['administrative_level_id'],
                                "project_name": project.name,
                                "project_id": project.couch_id,
                                "cycle_name": cycle.name,
                                "cycle_id": cycle.couch_id
                            })
                

                print(_adls)
                if fc_doc:

                    _updated_.append({
                        "fc_name": fc_doc['name'],
                        "sql_id": fc_doc['sql_id'],
                        "adls": _adls,
                    })
                    if project.name == "COSO":
                        for _adl in _adls:
                            administrative_levels.insert(0, _adl)
                    else:
                        for _adl in _adls:
                            administrative_levels.append(_adl)


                    for __adl in administrative_levels:
                        if __adl['project_id'] == project.couch_id and __adl['cycle_id'] == cycle.couch_id:
                            administrativelevel_obj = administrativelevels_models.AdministrativeLevel.objects.using('mis').get(id=int(__adl['id']))
                            villages = administrativelevel_obj.cvd.get_villages()
                            
                            for _village in villages:
                                if not any(_ad for _ad in administrative_levels if _ad['project_id'] == project.couch_id and _ad['cycle_id'] == cycle.couch_id and int(_ad['id']) == int(_village.id)):
                                    _adl = {
                                        "name": _village.name,
                                        "id": str(_village.id),
                                        "project_name": project.name,
                                        "project_id": project.couch_id,
                                        "cycle_name": cycle.name,
                                        "cycle_id": cycle.couch_id
                                    }
                                    if project.name == "COSO":
                                        administrative_levels.insert(0, _adl)
                                    else:
                                        administrative_levels.append(_adl)


                    fc_doc['administrative_levels'] = administrative_levels

                    print("Saving")
                    nsc.update_cloudant_document(db,  fc_doc["_id"], fc_doc)

                    print()
                    print()


    print("Start sync_geographicalunits_with_cvd_on_facilittor")
    sync_geographicalunits_with_cvd_on_facilittor(project.id)

    print("\nEnd")
    return _updated_





def update_facilitator_assignment_in_mis(project_name="COSO"):
    _updated_ = []

    nsc = NoSQLClient()
    if project_name:
        projects = Project.objects.filter(name=project_name)
    else:
        projects = Project.objects.all()
    print("Start")
    for project in projects:
        print(f"\n\n\t=============={project.name}===========\n")
        
        cycle = Cycle.objects.get(project_id=project.id, order=1)
        project_mis = mis_objects_call.get_object(ProjectMis, name=project.name)


        facilitators = Facilitator.objects.filter(projects__in=[project.id], develop_mode=False, training_mode=False).order_by('name')
        if facilitators:
            
            for f in facilitators:
                print(f.name, f.no_sql_db_name)
                
                
                facilitator_db = nsc.get_db(f.no_sql_db_name)
                docs = facilitator_db.get_query_result({"type": 'facilitator'})[:]
                
                if docs:
                    doc = facilitator_db[docs[0]['_id']]
                    _adls = [_ad for _ad in doc.get('administrative_levels') if _ad['project_id'] == project.couch_id and _ad['cycle_id'] == cycle.couch_id]
                    for ad in _adls:
                        id_str = ad.get('id')

                        if  (id_str and str(id_str).isdigit() and \
                            not AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(administrative_level_id=int(id_str), project_id=project_mis.id, activated=True).exists()):
                            
                            try:
                                assign = AssignAdministrativeLevelToFacilitator()
                                assign.administrative_level_id = int(id_str)
                                assign.facilitator_id = str(f.id)
                                assign.project_id = project_mis.id
                                assign.save(using='mis')
                                print(ad['name'])
                            except Exception as exc:
                                print(exc)
                                input()
                                

    print("\nEnd")




def sync_geographicalunits_with_cvd(project_name):

    def mettre_a_jour_element(liste, id_recherche, nouvelles_donnees):
        for i, element in enumerate(liste):
            if str(element.get('sql_id') if element.get('sql_id') else element.get('id')) == str(id_recherche):
                liste[i] = nouvelles_donnees
                return True
        return False
    
    nsc = NoSQLClient()
    db = nsc.get_db("backup_administrativelevels")
    
    if project_name:
        projects = Project.objects.filter(name=project_name)
    else:
        projects = Project.objects.all()
    print("Start")
    for project in projects:
        already_exists = True
        print(f"\n\n\t=============={project.name}===========\n")
        
        cycle = Cycle.objects.get(project_id=project.id, order=1)
        project_mis = mis_objects_call.get_object(ProjectMis, name=project.name)

        select_data_geographical_unit = {"type": 'geographical_unit', 'project_id': project.couch_id, 'cycle_id': cycle.couch_id}
        _docs = db.get_query_result(select_data_geographical_unit)[:]
        if not _docs:
            already_exists = False
            nsc.create_document(db, {**select_data_geographical_unit, 'project_name': project.name, 'cycle_name': cycle.name, 'created_date': datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%fZ')})
            _docs = db.get_query_result(select_data_geographical_unit)[:]
        geographical_unit_doc = db[_docs[0]['_id']]

        select_data_village = {"type": 'village', 'project_id': project.couch_id, 'cycle_id': cycle.couch_id}
        v_docs = db.get_query_result(select_data_village)[:]
        if not v_docs:
            nsc.create_document(db, {**select_data_village, 'project_name': project.name, 'cycle_name': cycle.name, 'created_date': datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%fZ')})
            v_docs = db.get_query_result(select_data_village)[:]
        village_doc = db[v_docs[0]['_id']]


        if already_exists:
            reponse = input("Ce document existe déjà dans la base. Souhaitez vous mettre à jour les données ? (y: pour poursuivre l'exécution) ").lower()
            if reponse not in ('y', 'yes'):
                return
            print("NB: La mise à jour se fera selon la configuration actuelle des CVD et unités géographiques d'interventions")
            reponse = input("Souhaitez vous vraiment poursuivre ? (y: pour poursuivre l'exécution) ").lower()
            if reponse not in ('y', 'yes'):
                return

        adls = mis_objects_call.filter_objects(administrativelevels_models.AdministrativeLevel, type="Village", administrative_levels_projects__in=[project_mis.id])
        

        geographical_units = []
        all_villages = []

        for administrativelevel_obj in adls:
            all_villages.append({
                "id": administrativelevel_obj.id,
                "name": administrativelevel_obj.name,
                "parent_id": administrativelevel_obj.parent.id,
                "parent_name": administrativelevel_obj.parent.name,
                "is_headquarters_village": True if administrativelevel_obj.cvd and administrativelevel_obj.cvd.headquarters_village.id == administrativelevel_obj.id else False
            })
            if administrativelevel_obj.geographical_unit:
                geographical_unit = next((el for el in geographical_units if str(el.get('sql_id')) == str(administrativelevel_obj.geographical_unit_id)), None)

                if not geographical_unit:
                    geographical_units.append(
                        {
                            "sql_id": str(administrativelevel_obj.geographical_unit_id),
                            "name": administrativelevel_obj.geographical_unit.get_name(),
                            "villages": [], 
                            "cvd_groups": []
                        }
                    )
                
                geographical_unit = next((el for el in geographical_units if str(el.get('sql_id')) == str(administrativelevel_obj.geographical_unit_id)), None)

                villages = geographical_unit['villages']
                villages.append(str(administrativelevel_obj.id))
                geographical_unit['villages'] = list(set(villages))



                #CVD
                if administrativelevel_obj.cvd:
                    cvd = next((el for el in geographical_unit['cvd_groups'] if str(el['sql_id']) == str(administrativelevel_obj.cvd_id)), None)
                    
                    if not cvd:
                        geographical_unit['cvd_groups'].append(
                            {
                                "sql_id": str(administrativelevel_obj.cvd_id),
                                "name": administrativelevel_obj.cvd.get_name(),
                                "village_cvd": administrativelevel_obj.cvd.headquarters_village.id if administrativelevel_obj.cvd.headquarters_village else None,
                                "villages": [str(administrativelevel_obj.id)]
                            }
                        )

                    cvd = next((el for el in geographical_unit['cvd_groups'] if str(el['sql_id']) == str(administrativelevel_obj.cvd_id)), None)
                    
                    villages = cvd['villages']
                    villages.append(str(administrativelevel_obj.id))
                    cvd['villages'] = list(set(villages))

                    mettre_a_jour_element(geographical_unit['cvd_groups'], administrativelevel_obj.cvd_id, cvd)
                    #End CVD

                mettre_a_jour_element(geographical_units, administrativelevel_obj.geographical_unit_id, geographical_unit)


        geographical_unit_doc["geographical_units"] = geographical_units
        geographical_unit_doc['updated_date'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        village_doc["villages"] = all_villages
        village_doc['updated_date'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        nsc.update_cloudant_document(db,  geographical_unit_doc["_id"], geographical_unit_doc)
        nsc.update_cloudant_document(db,  village_doc["_id"], village_doc)

    print()
    print("End")



# -
def copy_facilitators_doc_task_on_other(
        project_name_to_copy="COSO", project_name_to_save="FA-COSO",
        administrativelevel_ids=["3144", "3216", "1960", "1973", "2042", "2068", "1998", "2084", "2373", "2347", "3779", "3690"],
        facilitators_params=[]
    ):
    
    def get_all_keys(_list: list, form):
        if isinstance(form, list):
            for i in range(len(form)):
                get_all_keys(_list, form[i])
        elif isinstance(form, dict):
            for k in list(form.keys()):
                _list.append(k)
                v = form[k]
                if isinstance(v, (list, dict)):
                    get_all_keys(_list, v)
        return _list
    
    def recursive_on_data(_data, _list):
        if isinstance(_data, list):
            for i in range(len(_data)):
                _data[i] = recursive_on_data(_data[i], _list)
        elif isinstance(_data, dict):
            for k in list(_data.keys()):
                v = _data[k]
                if isinstance(v, (list, dict)):
                    _data[k] = recursive_on_data(v, _list)
                if k.lower() not in _list:
                    del _data[k]
                elif k.lower() in [elt.lower() for elt in [
                    "totalHommesPlus35Refugie", "totalFemmesPlus35Refugie", "totalHommesMoins35Refugie", "totalFemmesMoins35Refugie",
                    "totalHommesPlus35DeplaceInterne", "totalFemmesPlus35DeplaceInterne", "totalHommesMoins35DeplaceInterne",
                    "totalFemmesMoins35DeplaceInterne", "totalHommesPlus35CommunauteAcceuil", "totalFemmesPlus35CommunauteAcceuil",
                    "totalHommesMoins35CommunauteAcceuil", "totalFemmesMoins35CommunauteAcceuil", "totalMenages", "nombreEthniques"
                ]]:
                    _data[k] = None
                # ['totalHommes', 'totalFemmes', 'totalPlus35', 'totalHommesMoins35', 'totalFemmesMoins35', 'totalMoins35', 'totalParticipants']
                elif 'date' in str(k).lower() and not isinstance(v, (list, dict)):
                    _data[k] = None
                    
        return _data

    nsc = NoSQLClient()

    project_to_copy = Project.objects.get(name=project_name_to_copy)
    cycle_to_copy = Cycle.objects.get(project_id=project_to_copy.id, order=1)
    project_mis_to_copy = mis_objects_call.get_object(ProjectMis, name=project_to_copy.name)


    project_to_save = Project.objects.get(name=project_name_to_save)
    cycle_to_save = Cycle.objects.get(project_id=project_to_save.id, order=1)

    _facilitators = {
        str(_f.id): dict([
            ('id', _f.id), ('name', _f.name), ('email', _f.email),
            ('no_sql_db_name', _f.no_sql_db_name),
            ('projects_id', [_p.id for _p in _f.projects.all()]),
            ('projects_couch_id', [_p.couch_id for _p in _f.projects.all()]), 
            ('projects_name', [_p.name for _p in _f.projects.all()])
        ])
        for _f in Facilitator.objects.filter(develop_mode=False, training_mode=False).order_by('name')
    }



    print("Start")
    print(f"\n\n\t=============={project_to_save.name}===========\n")


    facilitators = [_f for _id, _f in _facilitators.items() if project_to_save.id in _f['projects_id'] if not facilitators_params or (facilitators_params and _f['no_sql_db_name'] in facilitators_params)]

    assign_adl_to_facilitators = {
        str(_assgn.administrative_level_id): _facilitators.get(str(_assgn.facilitator_id))
        for _assgn in AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(project_id=project_mis_to_copy.id, activated=True)
    }

    if facilitators:
        
        for f in facilitators:
            print(f['name'], f['no_sql_db_name'])
            
            db = nsc.get_db(f['no_sql_db_name'])

            _docs = db.get_query_result({"type": 'facilitator'})[:]
            fc_doc = db[_docs[0]['_id']]
            administrative_levels = [_a for _a in list(fc_doc['administrative_levels']) if _a.get('project_name') == project_to_save.name]

            for administrative_level in administrative_levels:
                canton_sql_id = None
                try:
                    administrativelevel_obj = administrativelevels_models.AdministrativeLevel.objects.using('mis').get(id=int(administrative_level['id']))
                    canton_sql_id = str(administrativelevel_obj.parent.id)
                except Exception as e:
                    pass


                if(administrative_level.get('project_name') == project_to_save.name and administrative_level.get('cycle_name') == cycle_to_save.name and (
                    (administrative_level.get('is_headquarters_village') and not administrativelevel_ids)
                    or
                    (administrative_level.get('is_headquarters_village') and administrativelevel_ids and str(administrative_level['id']) in administrativelevel_ids)
                    or
                    (administrative_level.get('is_headquarters_village') and administrativelevel_ids and canton_sql_id and canton_sql_id in administrativelevel_ids)
                )):

                    fc_docs = db.get_query_result({
                        "type": "task",
                        'project_id': project_to_save.couch_id,
                        'cycle_id': cycle_to_save.couch_id,
                        "administrative_level_id": administrative_level['id'],
                        "phase_name": {
                            "$in": ["VISITES PREALABLES", "MOBILISATION COMMUNAUTAIRE", "PLANIFICATION"]
                        }
                    }, limit=1000000)[:]

                    fc_copy = {str(_elt['task_order']): _elt for _elt in nsc.get_db(
                        assign_adl_to_facilitators.get(str(administrative_level['id'])).get('no_sql_db_name')
                    ).get_query_result({
                        "type": "task",
                        'project_id': project_to_copy.couch_id,
                        'cycle_id': cycle_to_copy.couch_id,
                        "administrative_level_id": administrative_level['id'],
                        "phase_name": {
                            "$in": ["VISITES PREALABLES", "MOBILISATION COMMUNAUTAIRE", "PLANIFICATION"]
                        }
                    }, limit=1000000)[:]}

                    for doc in fc_docs:
                        if not doc.get('form_response') and doc.get('project_id') == project_to_save.couch_id and doc.get('cycle_id') == cycle_to_save.couch_id and doc.get('type') == "task" and doc.get('administrative_level_id'):
                            
                            doc_copy = fc_copy.get(str(doc['task_order']))
                            if doc_copy:
                                print(doc_copy['administrative_level_name'])

                                if normaliser_chaine(doc['name']) == normaliser_chaine("Etablissement du profil du village") and (not get_datas_dict(doc_copy['form_response'], "generalitiesSurVillage", 1) or not get_datas_dict(doc_copy['form_response'], "principaleLanguesParlees", 1)):
                                    continue
                                if doc_copy.get('form_response') and doc_copy.get('administrative_level_id') == doc.get('administrative_level_id'):
                                    
                                    doc['form_response'] = recursive_on_data(doc_copy['form_response'], [elt.lower() for elt in get_all_keys([], doc['form'])])

                                    if normaliser_chaine(doc['name']) in [
                                        normaliser_chaine("Animer la session de formation sur le Module 1 : rôles et responsabilités des membres des organes de CVD"),
                                        normaliser_chaine("Animer la session de formation sur le Module 2 : mécanisme de gestion des plaintes"),
                                        normaliser_chaine("Animer la session de formation sur le Module 3 : rôles et responsabilités des APDC"),
                                        normaliser_chaine("Animer la session de formation sur le Module 4 : techniques de facilitation des focus groups et d’utilisation des outils MARP"),

                                        # normaliser_chaine("Mise en place et/ou restructuration du comité cantonal de développement (CCD)  et du comité cantonal de gestion des plaintes (CCGP)"),
                                        # normaliser_chaine("Appui au CCD dans  l'analyse des PAV des villages, l'arbitrage, la sélection des sous - projets à financer et l'affectation des ressources par sous - projet")
                                    ]:
                                        doc["attachments"] = doc_copy["attachments"]
                                    elif normaliser_chaine(doc['name']) in [
                                        normaliser_chaine("Utilisation  des outils et défintion du travail à faire par chaque groupe")
                                    ]:
                                        for i_att in range(4):
                                            if 'type' in doc_copy["attachments"][i_att]:
                                                doc["attachments"][i_att]['type'] = doc_copy["attachments"][i_att]['type']
                                            doc["attachments"][i_att]['attachment'] = doc_copy["attachments"][i_att]['attachment']
                                    elif normaliser_chaine(doc['name']) in [
                                        normaliser_chaine("Présenter les activités de la journée")
                                    ]:
                                        doc["attachments"][1] = doc_copy["attachments"][1]
                                    elif normaliser_chaine(doc['name']) in [
                                        normaliser_chaine("Organiser la communauté en groupes de travail")
                                    ]:
                                        for i_attachment in range(len(doc["attachments"])):
                                            _elts = [_elt for _elt in doc_copy["attachments"] if normaliser_chaine(_elt['name']) == normaliser_chaine(doc["attachments"][i_attachment]['name'])]
                                            if _elts:
                                                if 'type' in _elts[0]:
                                                    doc["attachments"][i_attachment]['type'] = _elts[0]['type']
                                                doc["attachments"][i_attachment]['attachment'] = _elts[0]['attachment']
                                    
                                    
                                    nsc.update_cloudant_document(db,  doc["_id"], doc)


def copy_facilitators_doc_task_on_other(
        project_name_to_copy="FA-COSO", project_name_to_save="COSO",
        administrativelevel_ids=["4594", "4608"],
        facilitators_params=[]
    ):
    
    def get_all_keys(_list: list, form):
        if isinstance(form, list):
            for i in range(len(form)):
                get_all_keys(_list, form[i])
        elif isinstance(form, dict):
            for k in list(form.keys()):
                _list.append(k)
                v = form[k]
                if isinstance(v, (list, dict)):
                    get_all_keys(_list, v)
        return _list
    
    def recursive_on_data(_data, _list):
        if isinstance(_data, list):
            for i in range(len(_data)):
                _data[i] = recursive_on_data(_data[i], _list)
        elif isinstance(_data, dict):
            for k in list(_data.keys()):
                v = _data[k]
                if isinstance(v, (list, dict)):
                    _data[k] = recursive_on_data(v, _list)
                elif k.lower() in [elt.lower() for elt in [
                    "totalHommesPlus35CommunauteAcceuil", "totalFemmesPlus35CommunauteAcceuil",
                    "totalHommesMoins35CommunauteAcceuil", "totalFemmesMoins35CommunauteAcceuil"
                ]] and any(_o for _o in ['totalhommes', 'totalfemmes', 'totalhommesmoins35', 'totalfemmesmoins35'] if _o in _list):
                    _data[{
                        'totalHommesPlus35CommunauteAcceuil': 'totalHommes' if 'totalhommes' in _list else 'totalHommesPlus35',
                        'totalFemmesPlus35CommunauteAcceuil': 'totalFemmes' if 'totalfemmes' in _list else 'totalFemmesPlus35',
                        'totalHommesMoins35CommunauteAcceuil': 'totalHommesMoins35',
                        'totalFemmesMoins35CommunauteAcceuil': 'totalFemmesMoins35'
                    }[k]] = v

                    if _data.get('totalHommes') != None and _data.get('totalFemmes') != None and \
                    _data.get('totalHommesMoins35') != None and _data.get('totalFemmesMoins35') != None:
                        _data['totalMoins35'] = _data['totalHommesMoins35'] + _data['totalFemmesMoins35'] 
                        _data['totalPlus35'] = _data['totalHommes'] + _data['totalFemmes']
                        _data['totalParticipants'] = _data['totalMoins35'] + _data['totalPlus35']

                elif 'date' in str(k).lower() and not isinstance(v, (list, dict)):
                    _data[k] = None
                    
        return _data
    
    def recursive_delete_attributes_on_data(_data, _list):
        if isinstance(_data, list):
            for i in range(len(_data)):
                _data[i] = recursive_delete_attributes_on_data(_data[i], _list)
        elif isinstance(_data, dict):
            for k in list(_data.keys()):
                v = _data[k]
                if isinstance(v, (list, dict)):
                    _data[k] = recursive_delete_attributes_on_data(v, _list)
                if k.lower() not in _list:
                    del _data[k]

        return _data

    nsc = NoSQLClient()

    project_to_copy = Project.objects.get(name=project_name_to_copy)
    cycle_to_copy = Cycle.objects.get(project_id=project_to_copy.id, order=1)
    project_mis_to_copy = mis_objects_call.get_object(ProjectMis, name=project_to_copy.name)


    project_to_save = Project.objects.get(name=project_name_to_save)
    cycle_to_save = Cycle.objects.get(project_id=project_to_save.id, order=1)

    _facilitators = {
        str(_f.id): dict([
            ('id', _f.id), ('name', _f.name), ('email', _f.email),
            ('no_sql_db_name', _f.no_sql_db_name),
            ('projects_id', [_p.id for _p in _f.projects.all()]),
            ('projects_couch_id', [_p.couch_id for _p in _f.projects.all()]), 
            ('projects_name', [_p.name for _p in _f.projects.all()])
        ])
        for _f in Facilitator.objects.filter(develop_mode=False, training_mode=False).order_by('name')
    }



    print("Start")
    print(f"\n\n\t=============={project_to_save.name}===========\n")

    history_tasks_no_updated = {}

    facilitators = [_f for _id, _f in _facilitators.items() if project_to_save.id in _f['projects_id'] if not facilitators_params or (facilitators_params and _f['no_sql_db_name'] in facilitators_params)]

    assign_adl_to_facilitators = {
        str(_assgn.administrative_level_id): _facilitators.get(str(_assgn.facilitator_id))
        for _assgn in AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(project_id=project_mis_to_copy.id, activated=True)
    }

    if facilitators:
        
        for f in facilitators:
            print(f['name'], f['no_sql_db_name'])
            
            db = nsc.get_db(f['no_sql_db_name'])

            _docs = db.get_query_result({"type": 'facilitator'})[:]
            fc_doc = db[_docs[0]['_id']]
            administrative_levels = [_a for _a in list(fc_doc['administrative_levels']) if _a.get('project_name') == project_to_save.name]

            for administrative_level in administrative_levels:
                canton_sql_id = None
                try:
                    administrativelevel_obj = administrativelevels_models.AdministrativeLevel.objects.using('mis').get(id=int(administrative_level['id']))
                    canton_sql_id = str(administrativelevel_obj.parent.id)
                except Exception as e:
                    pass


                if(administrative_level.get('project_name') == project_to_save.name and administrative_level.get('cycle_name') == cycle_to_save.name and (
                    (administrative_level.get('is_headquarters_village') and not administrativelevel_ids)
                    or
                    (administrative_level.get('is_headquarters_village') and administrativelevel_ids and str(administrative_level['id']) in administrativelevel_ids)
                    or
                    (administrative_level.get('is_headquarters_village') and administrativelevel_ids and canton_sql_id and canton_sql_id in administrativelevel_ids)
                )):

                    fc_docs = db.get_query_result({
                        "type": "task",
                        'project_id': project_to_save.couch_id,
                        'cycle_id': cycle_to_save.couch_id,
                        "administrative_level_id": administrative_level['id'],
                        "phase_name": {
                            "$in": ["VISITES PREALABLES", "MOBILISATION COMMUNAUTAIRE", "PLANIFICATION"]
                        }
                    }, limit=1000000)[:]

                    fc_copy = {str(_elt['task_order']): _elt for _elt in nsc.get_db(
                        assign_adl_to_facilitators.get(str(administrative_level['id'])).get('no_sql_db_name')
                    ).get_query_result({
                        "type": "task",
                        'project_id': project_to_copy.couch_id,
                        'cycle_id': cycle_to_copy.couch_id,
                        "administrative_level_id": administrative_level['id'],
                        "phase_name": {
                            "$in": ["VISITES PREALABLES", "MOBILISATION COMMUNAUTAIRE", "PLANIFICATION"]
                        }
                    }, limit=1000000)[:]}

                    for doc in fc_docs:
                        if doc.get('project_id') == project_to_save.couch_id and doc.get('cycle_id') == cycle_to_save.couch_id and doc.get('type') == "task" and doc.get('administrative_level_id'):
                            doc_copy = fc_copy.get(str(doc['task_order']))
                            if (
                                not doc.get('form_response') or doc.get('validated') == False or (
                                    doc.get('form_response') and not doc['form_response'][0]
                                )
                            ):
                                if doc_copy:
                                    print(doc_copy['administrative_level_name'])
                                    

                                    if normaliser_chaine(doc['name']) == normaliser_chaine("Etablissement du profil du village") and (not get_datas_dict(doc_copy['form_response'], "generalitiesSurVillage", 1) or not get_datas_dict(doc_copy['form_response'], "principaleLanguesParlees", 1)):
                                        continue
                                    if doc_copy.get('form_response') and doc_copy.get('administrative_level_id') == doc.get('administrative_level_id'):
                                        
                                        doc['form_response'] = recursive_on_data(doc_copy['form_response'], [elt.lower() for elt in get_all_keys([], doc['form'])])
                                        doc['form_response'] = recursive_delete_attributes_on_data(doc_copy['form_response'], [elt.lower() for elt in get_all_keys([], doc['form'])])
                                        
                                        for i_attachment in range(len(doc["attachments"])):
                                            _elts = [_elt for _elt in doc_copy["attachments"] if normaliser_chaine(_elt['name']) == normaliser_chaine(doc["attachments"][i_attachment]['name'])]
                                            if _elts:
                                                if 'type' in _elts[0] and (
                                                    not doc["attachments"][i_attachment]['attachment'] or 
                                                    'http' not in doc["attachments"][i_attachment]['attachment']['uri']
                                                ):
                                                    doc["attachments"][i_attachment]['type'] = _elts[0]['type']
                                                doc["attachments"][i_attachment]['attachment'] = _elts[0]['attachment']
                                        
                                        
                                        nsc.update_cloudant_document(db,  doc["_id"], doc)
                            else:
                                if doc_copy['administrative_level_name'] in history_tasks_no_updated:
                                    history_tasks_no_updated[doc_copy['administrative_level_name']].append(doc_copy['name'])
                                else:
                                    history_tasks_no_updated[doc_copy['administrative_level_name']] = [doc_copy['name']]
    print(history_tasks_no_updated)


def copy_facilitators_doc_task_attachment_ok_on_other(
        project_name_to_copy="COSO", project_name_to_save="FA-COSO",
        administrativelevel_ids=["3216"],
        tasks_ids_to_copy=[46], tasks_ids_to_save=[131],
        facilitators_params=['facilitator_1670848212', 'facilitator_1673012693', 'facilitator_1673013470', 'facilitator_1673013736', 'facilitator_1676590614', 'facilitator_1676844142', 'facilitator_1715073327', 'facilitator_1744193609']
    ):
    
    def get_all_keys(_list: list, form):
        if isinstance(form, list):
            for i in range(len(form)):
                get_all_keys(_list, form[i])
        elif isinstance(form, dict):
            for k in list(form.keys()):
                _list.append(k)
                v = form[k]
                if isinstance(v, (list, dict)):
                    get_all_keys(_list, v)
        return _list
    
    def recursive_on_data(_data, _list):
        if isinstance(_data, list):
            for i in range(len(_data)):
                _data[i] = recursive_on_data(_data[i], _list)
        elif isinstance(_data, dict):
            for k in list(_data.keys()):
                v = _data[k]
                if isinstance(v, (list, dict)):
                    _data[k] = recursive_on_data(v, _list)
                if k.lower() not in _list:
                    del _data[k]
                elif k.lower() in [elt.lower() for elt in [
                    "totalHommesPlus35Refugie", "totalFemmesPlus35Refugie", "totalHommesMoins35Refugie", "totalFemmesMoins35Refugie",
                    "totalHommesPlus35DeplaceInterne", "totalFemmesPlus35DeplaceInterne", "totalHommesMoins35DeplaceInterne",
                    "totalFemmesMoins35DeplaceInterne", "totalHommesPlus35CommunauteAcceuil", "totalFemmesPlus35CommunauteAcceuil",
                    "totalHommesMoins35CommunauteAcceuil", "totalFemmesMoins35CommunauteAcceuil", "totalMenages", "nombreEthniques"
                ]]:
                    _data[k] = None
                elif 'date' in str(k).lower() and not isinstance(v, (list, dict)):
                    _data[k] = None
                    
        return _data

    nsc = NoSQLClient()

    project_to_copy = Project.objects.get(name=project_name_to_copy)
    cycle_to_copy = Cycle.objects.get(project_id=project_to_copy.id, order=1)
    project_mis_to_copy = mis_objects_call.get_object(ProjectMis, name=project_to_copy.name)


    project_to_save = Project.objects.get(name=project_name_to_save)
    cycle_to_save = Cycle.objects.get(project_id=project_to_save.id, order=1)

    _facilitators = {
        str(_f.id): dict([
            ('id', _f.id), ('name', _f.name), ('email', _f.email),
            ('no_sql_db_name', _f.no_sql_db_name),
            ('projects_id', [_p.id for _p in _f.projects.all()]),
            ('projects_couch_id', [_p.couch_id for _p in _f.projects.all()]), 
            ('projects_name', [_p.name for _p in _f.projects.all()])
        ])
        for _f in Facilitator.objects.filter(develop_mode=False, training_mode=False).order_by('name')
    }



    print("Start")
    print(f"\n\n\t=============={project_to_save.name}===========\n")


    facilitators = [_f for _id, _f in _facilitators.items() if project_to_save.id in _f['projects_id'] if not facilitators_params or (facilitators_params and _f['no_sql_db_name'] in facilitators_params)]

    assign_adl_to_facilitators = {
        str(_assgn.administrative_level_id): _facilitators.get(str(_assgn.facilitator_id))
        for _assgn in AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(project_id=project_mis_to_copy.id, activated=True)
    }

    docs_copy_ok = {}
    for k, v in assign_adl_to_facilitators.items():
        fc_copy = nsc.get_db(
            v.get('no_sql_db_name')
        ).get_query_result({
            'sql_id': {'$in': tasks_ids_to_copy},
            'canton_sql_id': {'$in': administrativelevel_ids},
            "type": "task",
            "completed": True,
            "validated": True,
            'project_id': project_to_copy.couch_id,
            'cycle_id': cycle_to_copy.couch_id,
            "administrative_level_id": k,
            "phase_name": {
                "$in": ["VISITES PREALABLES", "MOBILISATION COMMUNAUTAIRE", "PLANIFICATION"]
            }
        }, limit=1000000)[:]
        
        for elt_fc_copy in fc_copy:
            ok = True
            if not elt_fc_copy["attachments"] or bool([att for att in elt_fc_copy["attachments"] if not att['attachment']]):
                ok = False
                break
        
            if ok:
                docs_copy_ok[str(elt_fc_copy['task_order'])] = elt_fc_copy
                break
        if docs_copy_ok:
            print(list(docs_copy_ok.values())[0].get('administrative_level_name'))
            break # To edit after

    if facilitators:
        
        for f in facilitators:
            print(f['name'], f['no_sql_db_name'])
            
            db = nsc.get_db(f['no_sql_db_name'])

            _docs = db.get_query_result({"type": 'facilitator'})[:]
            fc_doc = db[_docs[0]['_id']]
            administrative_levels = [_a for _a in list(fc_doc['administrative_levels']) if _a.get('project_name') == project_to_save.name]

            for administrative_level in administrative_levels:
                canton_sql_id = None
                try:
                    administrativelevel_obj = administrativelevels_models.AdministrativeLevel.objects.using('mis').get(id=int(administrative_level['id']))
                    canton_sql_id = str(administrativelevel_obj.parent.id)
                except Exception as e:
                    pass


                if(administrative_level.get('project_name') == project_to_save.name and administrative_level.get('cycle_name') == cycle_to_save.name and (
                    (administrative_level.get('is_headquarters_village') and not administrativelevel_ids)
                    or
                    (administrative_level.get('is_headquarters_village') and administrativelevel_ids and str(administrative_level['id']) in administrativelevel_ids)
                    or
                    (administrative_level.get('is_headquarters_village') and administrativelevel_ids and canton_sql_id and canton_sql_id in administrativelevel_ids)
                )):

                    fc_docs = db.get_query_result({
                        "type": "task",
                        'sql_id': {'$in': tasks_ids_to_save},
                        'canton_sql_id': {'$in': administrativelevel_ids},
                        'project_id': project_to_save.couch_id,
                        'cycle_id': cycle_to_save.couch_id,
                        "administrative_level_id": administrative_level['id'],
                        "phase_name": {
                            "$in": ["VISITES PREALABLES", "MOBILISATION COMMUNAUTAIRE", "PLANIFICATION"]
                        }
                    }, limit=1000000)[:]

                    

                    for doc in fc_docs:
                        doc_copy_ok = docs_copy_ok.get(str(doc['task_order']))
                        if doc_copy_ok:
                            if doc_copy_ok.get('canton_sql_id') == doc.get('canton_sql_id'):
                                
                                if normaliser_chaine(doc['name']) in [
                                    normaliser_chaine("Mise en place et/ou restructuration du comité cantonal de développement (CCD)  et du comité cantonal de gestion des plaintes (CCGP)"),
                                ]:
                                    print(doc_copy_ok['administrative_level_name'])
                                    for i_attachment in range(len(doc["attachments"])):
                                        _elts = [
                                            _elt for _elt in doc_copy_ok["attachments"] 
                                            if (not doc["attachments"][i_attachment]['attachment'] or (doc["attachments"][i_attachment]['attachment'] and 'https://' not in doc["attachments"][i_attachment]['attachment']['uri'])) and 
                                            (
                                                normaliser_chaine(_elt['name']) == normaliser_chaine(doc["attachments"][i_attachment]['name']) or 
                                                (
                                                    normaliser_chaine('Liste des membres du CCD et les postes occupé') in normaliser_chaine(_elt['name']) and 
                                                    normaliser_chaine('Liste des membres du CCD et les postes occupé') in normaliser_chaine(doc["attachments"][i_attachment]['name'])
                                                ) or 
                                                (
                                                    normaliser_chaine('Télecharger la liste des membres du CCD') == normaliser_chaine(doc["attachments"][i_attachment]['name']) and 
                                                    normaliser_chaine('Liste des membres du CCD et les postes occupé sous projets') == normaliser_chaine(_elt['name'])
                                                )
                                            )
                                        ]
                                        if _elts:
                                            if 'type' in _elts[0]:
                                                doc["attachments"][i_attachment]['type'] = _elts[0]['type']
                                            doc["attachments"][i_attachment]['attachment'] = _elts[0]['attachment']
                                
                                
                                    nsc.update_cloudant_document(db,  doc["_id"], doc)
                                
                        


def delete_facilitators_task_form_reponse(project_id, cycle_id, administrativelevel_ids, develop_mode=False, trainning_mode=False, no_sql_dbs=False, tasks_ids=[]):
    if no_sql_dbs:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=trainning_mode, no_sql_db_name__in=no_sql_dbs)
    else:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=trainning_mode, projects__in=[project_id])

    if not tasks_ids:
        tasks_ids = [t.id for t in Task.objects.filter(project_id=project_id, cycles__in=[cycle_id]).prefetch_related()]
    
    nsc = NoSQLClient()
    nsc_database = nsc.get_db("process_design")

    process_design = {str(_elt['sql_id']): _elt for _elt in  nsc_database.get_query_result({
            "sql_id": {
                "$in": tasks_ids
            }
        })
    }


    project = Project.objects.get(id=project_id)
    cycle = Cycle.objects.get(project_id=project.id, order=1)

    print("Start")


    if facilitators:
        
        for f in facilitators:
            print(f.name, f.no_sql_db_name)
            
            db = nsc.get_db(f.no_sql_db_name)

            _docs = db.get_query_result({"type": 'facilitator'})[:]
            fc_doc = db[_docs[0]['_id']]
            administrative_levels = [_a for _a in list(fc_doc['administrative_levels']) if _a.get('project_name') == project.name]

            for administrative_level in administrative_levels:
                canton_sql_id = None
                try:
                    administrativelevel_obj = administrativelevels_models.AdministrativeLevel.objects.using('mis').get(id=int(administrative_level['id']))
                    canton_sql_id = str(administrativelevel_obj.parent.id)
                except Exception as e:
                    pass


                if(administrative_level.get('project_name') == project.name and administrative_level.get('cycle_name') == cycle.name and (
                    (administrative_level.get('is_headquarters_village') and not administrativelevel_ids)
                    or
                    (administrative_level.get('is_headquarters_village') and administrativelevel_ids and str(administrative_level['id']) in administrativelevel_ids)
                    or
                    (administrative_level.get('is_headquarters_village') and administrativelevel_ids and canton_sql_id and canton_sql_id in administrativelevel_ids)
                )):

                    fc_docs = db.get_query_result({
                        "type": "task",
                        'project_id': project.couch_id,
                        'cycle_id': cycle.couch_id,
                        "administrative_level_id": administrative_level['id'],
                        "phase_name": {
                            "$in": ["VISITES PREALABLES", "MOBILISATION COMMUNAUTAIRE", "PLANIFICATION"]
                        },
                        "sql_id": {
                            "$in": tasks_ids
                        }
                    }, limit=1000000)[:]

                    for doc in fc_docs:
                        if doc.get('form_response') and doc.get('project_id') == project.couch_id and doc.get('cycle_id') == cycle.couch_id and doc.get('type') == "task" and doc.get('administrative_level_id'):
                            doc['form_response'] = []
                            doc["attachments"] = process_design.get(str(doc['sql_id']))["attachments"]
                                
                            nsc.update_cloudant_document(db,  doc["_id"], doc)

                                

def set_facilitators_task_attibute_value_to_null(
        project_name="FA-COSO",
        administrativelevel_ids=["3144", "3216", "1960", "1973", "2042", "2068", "1998", "2084", "2373", "2347", "3779", "3690"],
        facilitators_params=[], tasks_id=[104]
    ):
    nsc = NoSQLClient()
    project = Project.objects.get(name=project_name)
    cycle = Cycle.objects.get(project_id=project.id, order=1)
    _facilitators = {
        str(_f.id): dict([
            ('id', _f.id), ('name', _f.name), ('email', _f.email),
            ('no_sql_db_name', _f.no_sql_db_name),
            ('projects_id', [_p.id for _p in _f.projects.all()]),
            ('projects_couch_id', [_p.couch_id for _p in _f.projects.all()]), 
            ('projects_name', [_p.name for _p in _f.projects.all()])
        ])
        for _f in Facilitator.objects.filter(develop_mode=False, training_mode=False).order_by('name')
    }
    count = 0
    print("Start")
    print(f"\n\n\t=============={project.name}===========\n")
    facilitators = [_f for _id, _f in _facilitators.items() if project.id in _f['projects_id'] if not facilitators_params or (facilitators_params and _f['no_sql_db_name'] in facilitators_params)]
    if facilitators:
        for f in facilitators:
            print(f['name'], f['no_sql_db_name'])
            print()
            db = nsc.get_db(f['no_sql_db_name'])
            _docs = db.get_query_result({"type": 'facilitator'})[:]
            fc_doc = db[_docs[0]['_id']]
            administrative_levels = [_a for _a in list(fc_doc['administrative_levels']) if _a.get('project_name') == project.name]
            for administrative_level in administrative_levels:
                canton_sql_id = None
                try:
                    administrativelevel_obj = administrativelevels_models.AdministrativeLevel.objects.using('mis').get(id=int(administrative_level['id']))
                    canton_sql_id = str(administrativelevel_obj.parent.id)
                except Exception as e:
                    pass
                if(administrative_level.get('project_name') == project.name and administrative_level.get('cycle_name') == cycle.name and (
                    (administrative_level.get('is_headquarters_village') and not administrativelevel_ids)
                    or
                    (administrative_level.get('is_headquarters_village') and administrativelevel_ids and str(administrative_level['id']) in administrativelevel_ids)
                    or
                    (administrative_level.get('is_headquarters_village') and administrativelevel_ids and canton_sql_id and canton_sql_id in administrativelevel_ids)
                )):
                    fc_docs = db.get_query_result({
                        "type": "task",
                        'project_id': project.couch_id,
                        'cycle_id': cycle.couch_id,
                        "administrative_level_id": administrative_level['id'],
                        "phase_name": {
                            "$in": ["VISITES PREALABLES", "MOBILISATION COMMUNAUTAIRE", "PLANIFICATION"]
                        },
                        "sql_id": {
                            "$in": tasks_id
                        },
                    }, limit=1000000)[:]
                    for doc in fc_docs:
                        if doc.get('form_response') and doc.get('project_id') == project.couch_id and doc.get('cycle_id') == cycle.couch_id and doc.get('type') == "task" and doc.get('administrative_level_id'):
                            if normaliser_chaine(doc['name']) in [
                                normaliser_chaine("Vérification de l'existence du CVD et de ses organes")
                            ]:
                                _value = get_datas_dict(doc["form_response"], "fonctionnement", 1)
                                _value = _value.get('dateDesDeuxReunions', {}) if _value else None
                                value = _value.get('reunion1') if _value else None
                                if value and (
                                    'T' not in value and 'Z' not in value
                                ):
                                    print(value)
                                    doc["form_response"][1]["fonctionnement"]["dateDesDeuxReunions"] = None
                                    nsc.update_cloudant_document(db,  doc["_id"], doc)
                                    count += 1
                                    print(doc)
                                    print()
                                    print()
    print(count)



"""
updated_history
updated_after_invalidation_history
{
            facilitator: {
              name: facilitator?.name,
              email: facilitator?.email,
              phone: facilitator?.phone,
              sex: facilitator?.sex,
              sql_id: facilitator?.sql_id,
              type: facilitator?.type,
              fields_updated_response: fields_updated_response,
              fields_updated: fields_updated,
              attachments_updated: attachments_updated,
              page: currentPage
            },
            date: date_moment
          }


completed_history
{
                      facilitator: {
                        name: facilitator?.name,
                        email: facilitator?.email,
                        phone: facilitator?.phone,
                        sex: facilitator?.sex,
                        sql_id: facilitator?.sql_id,
                        type: facilitator?.type,
                        form_response: task.form_response,
                        attachments: task.attachments,
                      },
                      date: moment()
                    }
"""
def review_task_history(): 
    nsc = NoSQLClient()

    for cycle in Cycle.objects.all():

        facilitators = Facilitator.objects.filter(projects__in=[cycle.project.id])

        if cycle.project and facilitators:
               
            for f in facilitators:
                print(f.name)
                db = nsc.get_db(f.no_sql_db_name)

                query_result_docs = db.get_query_result({
                    "type": "task",
                    'project_id': cycle.project.couch_id,
                    'cycle_id': cycle.couch_id
                }, limit=1000000)[:]

                for doc in query_result_docs:
                    _updated_history = []
                    if 'updated_history' in doc:
                        updated_history = doc['updated_history']
                        for u_h in updated_history:
                            _updated_history.append({
                                'facilitator': {
                                    'name': u_h.get('facilitator', {}).get('name'),
                                    'email': u_h.get('facilitator', {}).get('email'),
                                    'phone': u_h.get('facilitator', {}).get('phone'),
                                    'sex': u_h.get('facilitator', {}).get('sex'),
                                    'sql_id': u_h.get('facilitator', {}).get('sql_id'),
                                    'type': u_h.get('facilitator', {}).get('type'),
                                    'fields_updated_response': u_h.get('facilitator', {}).get('fields_updated_response'),
                                    'fields_updated': u_h.get('facilitator', {}).get('fields_updated'),
                                    'attachments_updated': u_h.get('facilitator', {}).get('attachments_updated'),
                                    'page': u_h.get('facilitator', {}).get('page'),
                                },
                                'date': u_h.get('date')
                            })
                        doc['updated_history'] = _updated_history
                    
                    _updated_after_invalidation_history = []
                    if 'updated_after_invalidation_history' in doc:
                        updated_after_invalidation_history = doc['updated_after_invalidation_history']
                        for u_a_i_h in updated_after_invalidation_history:
                            _updated_after_invalidation_history.append({
                                'facilitator': {
                                    'name': u_a_i_h.get('facilitator', {}).get('name'),
                                    'email': u_a_i_h.get('facilitator', {}).get('email'),
                                    'phone': u_a_i_h.get('facilitator', {}).get('phone'),
                                    'sex': u_a_i_h.get('facilitator', {}).get('sex'),
                                    'sql_id': u_a_i_h.get('facilitator', {}).get('sql_id'),
                                    'type': u_a_i_h.get('facilitator', {}).get('type'),
                                    'fields_updated_response': u_a_i_h.get('facilitator', {}).get('fields_updated_response'),
                                    'fields_updated': u_a_i_h.get('facilitator', {}).get('fields_updated'),
                                    'attachments_updated': u_a_i_h.get('facilitator', {}).get('attachments_updated'),
                                    'page': u_a_i_h.get('facilitator', {}).get('page'),
                                },
                                'date': u_a_i_h.get('date')
                            })
                        doc['updated_after_invalidation_history'] = _updated_after_invalidation_history
                    
                    _completed_history = []
                    if 'completed_history' in doc:
                        completed_history = doc['completed_history']
                        for c_h in completed_history:
                            _completed_history.append({
                                'facilitator': {
                                    'name': c_h.get('facilitator', {}).get('name'),
                                    'email': c_h.get('facilitator', {}).get('email'),
                                    'phone': c_h.get('facilitator', {}).get('phone'),
                                    'sex': c_h.get('facilitator', {}).get('sex'),
                                    'sql_id': c_h.get('facilitator', {}).get('sql_id'),
                                    'type': c_h.get('facilitator', {}).get('type'),
                                    'form_response': c_h.get('facilitator', {}).get('form_response'),
                                    'attachments': c_h.get('facilitator', {}).get('attachments'),
                                },
                                'date': c_h.get('date')
                            })
                        doc['completed_history'] = _completed_history
                       
                    if 'completed_history' in doc and 'updated_after_invalidation_history' in doc and 'updated_history' in doc:
                        nsc.update_cloudant_document(db,  doc["_id"], doc)
        

    print("backup_db_facilitators_docs")
    backup_db = nsc.get_db("backup_db_facilitators_docs")
    query_result_docs = backup_db.get_query_result({
        "type": "task"
    }, limit=10000000)[:]

    for doc in query_result_docs:
        _updated_history = []
        if 'updated_history' in doc:
            updated_history = doc['updated_history']
            for u_h in updated_history:
                _updated_history.append({
                    'facilitator': {
                        'name': u_h.get('facilitator', {}).get('name'),
                        'email': u_h.get('facilitator', {}).get('email'),
                        'phone': u_h.get('facilitator', {}).get('phone'),
                        'sex': u_h.get('facilitator', {}).get('sex'),
                        'sql_id': u_h.get('facilitator', {}).get('sql_id'),
                        'type': u_h.get('facilitator', {}).get('type'),
                        'fields_updated_response': u_h.get('facilitator', {}).get('fields_updated_response'),
                        'fields_updated': u_h.get('facilitator', {}).get('fields_updated'),
                        'attachments_updated': u_h.get('facilitator', {}).get('attachments_updated'),
                        'page': u_h.get('facilitator', {}).get('page'),
                    },
                    'date': u_h.get('date')
                })
            doc['updated_history'] = _updated_history
        
        _updated_after_invalidation_history = []
        if 'updated_after_invalidation_history' in doc:
            updated_after_invalidation_history = doc['updated_after_invalidation_history']
            for u_a_i_h in updated_after_invalidation_history:
                _updated_after_invalidation_history.append({
                    'facilitator': {
                        'name': u_a_i_h.get('facilitator', {}).get('name'),
                        'email': u_a_i_h.get('facilitator', {}).get('email'),
                        'phone': u_a_i_h.get('facilitator', {}).get('phone'),
                        'sex': u_a_i_h.get('facilitator', {}).get('sex'),
                        'sql_id': u_a_i_h.get('facilitator', {}).get('sql_id'),
                        'type': u_a_i_h.get('facilitator', {}).get('type'),
                        'fields_updated_response': u_a_i_h.get('facilitator', {}).get('fields_updated_response'),
                        'fields_updated': u_a_i_h.get('facilitator', {}).get('fields_updated'),
                        'attachments_updated': u_a_i_h.get('facilitator', {}).get('attachments_updated'),
                        'page': u_a_i_h.get('facilitator', {}).get('page'),
                    },
                    'date': u_a_i_h.get('date')
                })
            doc['updated_after_invalidation_history'] = _updated_after_invalidation_history
        
        _completed_history = []
        if 'completed_history' in doc:
            completed_history = doc['completed_history']
            for c_h in completed_history:
                _completed_history.append({
                    'facilitator': {
                        'name': c_h.get('facilitator', {}).get('name'),
                        'email': c_h.get('facilitator', {}).get('email'),
                        'phone': c_h.get('facilitator', {}).get('phone'),
                        'sex': c_h.get('facilitator', {}).get('sex'),
                        'sql_id': c_h.get('facilitator', {}).get('sql_id'),
                        'type': c_h.get('facilitator', {}).get('type'),
                        'form_response': c_h.get('facilitator', {}).get('form_response'),
                        'attachments': c_h.get('facilitator', {}).get('attachments'),
                    },
                    'date': c_h.get('date')
                })
            doc['completed_history'] = _completed_history
        
        if 'completed_history' in doc and 'updated_after_invalidation_history' in doc and 'updated_history' in doc:
            nsc.update_cloudant_document(backup_db,  doc["_id"], doc)



def update_geolocation_docs(projects_names=["COSO", "FA-COSO"]):
    nsc = NoSQLClient()
    facilitators = Facilitator.objects.filter(projects__in=Project.objects.filter(name__in=projects_names), develop_mode=False, training_mode=False)

    _facilitators = {
        str(_f.id): dict([
            ('id', _f.id), ('name', _f.name), ('email', _f.email),
            ('no_sql_db_name', _f.no_sql_db_name),
            ('projects_id', [_p.id for _p in _f.projects.all()]),
            ('projects_couch_id', [_p.couch_id for _p in _f.projects.all()]), 
            ('projects_name', [_p.name for _p in _f.projects.all()])
        ])
        for _f in Facilitator.objects.filter(develop_mode=False, training_mode=False).order_by('name')
    }

    assign_adl_to_facilitators = {}
    for p_name in projects_names:

        assign_adl_to_facilitators[p_name] = {}

        project_mis_to_copy = mis_objects_call.get_object(ProjectMis, name=p_name)

        assign_adl_to_facilitators[p_name] = {
            str(_assgn.administrative_level_id): _facilitators.get(str(_assgn.facilitator_id))
            for _assgn in AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(project_id=project_mis_to_copy.id, activated=True)
        }

    count = 0
    adls_no_found = []

    for f in facilitators:
        print(f.name, f.no_sql_db_name)
        db = nsc.get_db(f.no_sql_db_name)

        geolocations = db.get_query_result({
            "type": "geolocation",
        }, limit=1)[:]

        if geolocations:

            geolocation = geolocations[0]
            
            administrativelevels = geolocation['administrativelevels'] if 'administrativelevels' in geolocation else []
            
            for adm in administrativelevels:
                for k, v in assign_adl_to_facilitators.items():
                    facilitator_find = v.get(str(adm['id']))

                    if facilitator_find:
                        db_facilitator_find = nsc.get_db(facilitator_find['no_sql_db_name'])
                        
                        geolocations_facilitator_find = db_facilitator_find.get_query_result({"type": "geolocation"}, limit=1)[:]
                        if geolocations_facilitator_find:
                            geolocation_facilitator_find = geolocations_facilitator_find[0]
                            administrativelevels_facilitator_find = geolocation_facilitator_find["administrativelevels"] if 'administrativelevels' in geolocation_facilitator_find else []
                            
                            if adm['id'] not in [_adm['id'] for _adm in administrativelevels_facilitator_find]:
                                administrativelevels_facilitator_find.append(adm)
                                geolocation_facilitator_find["administrativelevels"] = administrativelevels_facilitator_find

                                geolocation_facilitator_find["synced"] = True

                                nsc.update_cloudant_document(db_facilitator_find,  geolocation_facilitator_find["_id"], geolocation_facilitator_find)
                                
                                count += 1

                                print("Save", count, f.no_sql_db_name, "to", facilitator_find['no_sql_db_name'])


                    else:
                        adls_no_found.append(str(adm['id']))


    return adls_no_found, count



def get_facilitator_db_which_have_cvd_id(project_id, cycle_id, cvd_ids, develop_mode=False, training_mode=False):
    project = Project.objects.get(id=project_id)
    cycle = Cycle.objects.get(id=cycle_id)
    project_mis = mis_objects_call.filter_objects(MisProject, name=project.name)
    project_mis_id = project_mis.first().id if project_mis.exists() else None
    cycle_mis = mis_objects_call.filter_objects(MisCycle, order=cycle.order, project_id=project_mis_id)
    cycle_mis_id = cycle_mis.first().id if cycle_mis.exists() else None
    
    nsc = NoSQLClient()
    count_facilitator = 0
    print("Start")

    facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, projects__in=[project_id])

    administrativelevels_dict = {str(ad.id): str(ad.cvd.id) for ad in mis_objects_call.filter_objects(AdministrativeLevel, type="Village", administrative_levels_projects__in=[project_mis_id], administrative_levels_cycles__in=[cycle_mis_id])}
    
    for f in facilitators.order_by('id'):
        count_facilitator += 1
        facilitator_db = nsc.get_db(f.no_sql_db_name)
        docs = facilitator_db.all_docs(include_docs=True)['rows']

        facilitator_doc = None
        for _doc in docs:
            doc = _doc.get('doc')
            if doc.get('type') == 'facilitator' and not doc.get('develop_mode') and not doc.get('training_mode'):
                facilitator_doc = doc
                break

        docs = sorted([doc for doc in docs if doc.get('doc') and doc.get('doc').get('cycle_id') == cycle.couch_id and doc.get('doc').get('project_id') == project.couch_id and doc.get('doc').get('type') == 'task' and doc.get('doc').get('sql_id')], key=lambda obj: obj["doc"]["completed"])
        
        if facilitator_doc:
            doc = facilitator_doc
            for _task in docs:
                _task = _task.get('doc')
                _administrative_level_id = administrativelevels_dict.get(str(_task.get('administrative_level_id')))

                if _administrative_level_id and _administrative_level_id in cvd_ids:
                    print("Find cvd id", _administrative_level_id, "village id", _task.get('administrative_level_id'),  "in facilitator db", f.no_sql_db_name)
                    break
    print()
    print("End", count_facilitator)