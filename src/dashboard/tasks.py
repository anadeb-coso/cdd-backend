from __future__ import absolute_import, unicode_literals
from cdd.celery import app
from celery import shared_task
from datetime import datetime
import pytz
from django.db.models import Sum
from django.utils.dateparse import parse_datetime
from django.db import transaction
from django.utils import timezone

from authentication.models import Facilitator
from dashboard.facilitators.functions import get_cvds
from no_sql_client import NoSQLClient
from process_manager.models import AggregatedStatus, Task, Cycle, Project, AggregatedStatusFacilitator
from administrativelevels.models import AdministrativeLevel, CVD
from cdd.functions import datetime_complet_str
from cdd.call_objects_from_other_db import mis_objects_call
from subprojects.models import Project as MisProject, Cycle as MisCycle
from cdd.constants import PHASES_BEFORE_BEGINING_SUBPROJECT_EXECUTION

BATCH_SIZE = 500
def bulk_objects_create_or_update(model, objects, type_bulk="update", fields=[], batch_size=BATCH_SIZE):
    for i in range(0, len(objects), batch_size):
        batch = objects[i:i + batch_size]
        with transaction.atomic():
            if type_bulk == "create":
                model.objects.bulk_create(batch)
            else:
                model.objects.bulk_update(
                    batch,
                    fields
                )

# def recursive_to_save_administrativelevel_tasks_completed(count_facilitator, count_facilitator_cvd, ad: AdministrativeLevel, _task: dict, project_id: int, cycle_id):
#     if ad.parent:
#         parent = ad.parent
#         _ok = True
#         try:
#             a = AggregatedStatus.objects.get(administrative_level_id=parent.id, task_id=int(_task["sql_id"]), project_id=project_id, cycle_id=cycle_id)
#             if count_facilitator == 1 and count_facilitator_cvd == 1:
#                 a.total_tasks_completed = 0
#                 a.total_tasks = 0
#         except AggregatedStatus.DoesNotExist as exc:
#             a = AggregatedStatus()
#             a.administrative_level_id = parent.id
#             a.project_id = project_id
#             a.cycle_id = cycle_id
#             a.task_id = int(_task["sql_id"])
#         except Exception as exc:
#             # print(exc)
#             _ok = False
#         if _ok:
#             a.total_tasks_completed = ((a.total_tasks_completed+1) if _task['completed'] else a.total_tasks_completed)
#             a.total_tasks += 1
#             a.save()
        
#         return recursive_to_save_administrativelevel_tasks_completed(count_facilitator, count_facilitator_cvd, parent, _task, project_id, cycle_id) #call recursive function
    
#     return None


# # @app.task
# def sync_celery_tasks(project_id, cycle_id, develop_mode=False, training_mode=False):
#     project = Project.objects.get(id=project_id)
#     cycle = Cycle.objects.get(id=cycle_id)
#     nsc = NoSQLClient()
#     count_facilitator = 0
#     print("Start")
#     for f in Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, projects__in=[project_id]).order_by('id'):
#         print()
#         # print()
#         # print()
#         print(count_facilitator, f.no_sql_db_name, f.username)
#         count_facilitator += 1
#         nbr_tasks_completed = 0
#         nbr_tasks = 0
#         last_activity_date = "0000-00-00 00:00:00"
#         facilitator_db = nsc.get_db(f.no_sql_db_name)
#         docs = facilitator_db.all_docs(include_docs=True)['rows']

#         facilitator_doc = None
#         for _doc in docs:
#             doc = _doc.get('doc')
#             if doc.get('type') == 'facilitator' and not doc.get('develop_mode') and not doc.get('training_mode'):
#                 facilitator_doc = doc
#                 break
            
#         docs = [doc for doc in docs if doc.get('doc') and doc.get('doc').get('cycle_id') == cycle.couch_id and doc.get('doc').get('project_id') == project.couch_id]
        
#         if facilitator_doc:
#             doc = facilitator_doc
#             cvds = get_cvds(project.couch_id, cycle.couch_id, doc)
#             count_facilitator_cvd = 0
#             for cvd in cvds:
#                 count_facilitator_cvd += 1
#                 _village = cvd['village']
                
#                 for _task in docs:
#                     _task = _task.get('doc')
#                     if _task.get('type') == 'task' and _task.get('sql_id') and str(_task.get('administrative_level_id')) == str(_village['id']):
#                         if _task['completed']:
#                             nbr_tasks_completed += 1
#                         nbr_tasks += 1

#                         last_updated = datetime_complet_str(_task.get('last_updated'))
#                         if last_updated and last_activity_date < last_updated:
#                             last_activity_date = last_updated

#                         #By village
#                         # print(_task.get('administrative_level_id'), _task.get('name'), _task.get('sql_id'))
#                         for ad_id in cvd['villages']:
#                             a = None
#                             _ok = True
#                             try:
#                                 a = AggregatedStatus.objects.get(administrative_level_id=int(ad_id['id']), task_id=int(_task["sql_id"]), project_id=project_id, cycle_id=cycle_id)
#                             except AggregatedStatus.DoesNotExist as exc:
#                                 a = AggregatedStatus()
#                                 a.administrative_level_id = int(ad_id['id'])
#                                 a.project_id = project_id
#                                 a.cycle_id = cycle_id
#                                 a.task_id = int(_task["sql_id"])
#                             # except Exception as exc:
#                             #     print(exc)
#                             #     _ok = False
#                             if _ok:
#                                 a.total_tasks_completed = 1 if _task['completed'] else 0
#                                 a.total_tasks = 1
#                                 a.save()
                        
#                         #By Canton but counting on CVD not villages
#                         try:
#                             _village_cvd = AdministrativeLevel.objects.using('mis').get(id=int(_village['id']))
#                             if _village_cvd.type == "Village":
#                                 recursive_to_save_administrativelevel_tasks_completed(count_facilitator, count_facilitator_cvd, _village_cvd, _task, project_id, cycle_id)
#                         except:
#                             pass
#                         # _ok = True
#                         # canton = AdministrativeLevel.objects.get(id=int(_village['id'])).parent
#                         # try:
#                         #     a_canton = AggregatedStatus.objects.get(administrative_level_id=canton.id, task_id=int(_task["sql_id"]))
#                         #     if count_facilitator == 1:
#                         #         a_canton.total_tasks_completed = 0
#                         #         a_canton.total_tasks = 0
#                         # except AggregatedStatus.DoesNotExist as exc:
#                         #     a_canton = AggregatedStatus()
#                         #     a_canton.administrative_level_id = canton.id
#                         #     a_canton.task_id = int(_task["sql_id"])
#                         # except Exception as exc:
#                         #     print(exc)
#                         #     _ok = False
#                         # if _ok:
#                         #     a_canton.total_tasks_completed = a_canton.total_tasks_completed+1 if _task['completed'] else a_canton.total_tasks_completed
#                         #     a_canton.total_tasks =  a_canton.total_tasks + 1
#                         #     a_canton.save()
                        
#             # print(count_facilitator_cvd)

#             f.name = facilitator_doc.get('name')
#             f.email = facilitator_doc.get('email')
#             f.phone = facilitator_doc.get('phone')
#             f.sex = facilitator_doc.get('sex')
#             f.total_tasks_completed = nbr_tasks_completed
#             f.total_tasks = nbr_tasks

#             if last_activity_date == "0000-00-00 00:00:00":
#                 last_activity_date = None
#             else:
#                 last_activity_date = parse_datetime(last_activity_date) #datetime.strptime(last_activity_date, '%Y-%m-%d %H:%M:%S')
#                 if last_activity_date is not None:
#                     last_activity_date = last_activity_date.replace(tzinfo=pytz.UTC)
#                 # _date = last_activity_date.split()[0]
#                 # _hours = last_activity_date.split()[1]
#                 # last_activity_date = datetime(
#                 #     int(_date.split("-")[0]), int(_date.split("-")[1]), int(_date.split("-")[2]), 
#                 #     int(_hours.split(":")[0]), int(_hours.split(":")[1]), int(_hours.split(":")[2]),
#                 #     tzinfo=pytz.UTC
#                 # )
#             f.last_activity = last_activity_date

#             f.save()
        
#     print("End")


@app.task
def test_one():

    data = {
        "type": "test",
        "date": datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    }
    nsc = NoSQLClient()
    nsc_database = nsc.get_db("process_design")
    
    new_document = nsc.create_document(nsc_database, data)

    print(new_document)


# @app.task(bind=True)
# def debug_task(self):
#     print('Request: {0!r}'.format(self.request))


# @app.on_after_configure.connect
# def setup_periodic_tasks(sender, **kwargs):
#     # Calls test every 10 seconds.
#     sender.add_periodic_task(10.0, test.s(4, 8), name='add every 10')


def sync_aggregated_status_on_adl(project_id: int, cycle_id: int, execute_adl_village=True, execute_adl_bigger_than_village=False, villages_ids_have_subproject=[]):
    project = Project.objects.get(id=project_id)
    cycle = Cycle.objects.get(id=cycle_id)
    project_mis = mis_objects_call.filter_objects(MisProject, name=project.name)
    project_mis_id = project_mis.first().id if project_mis.exists() else None
    cycle_mis = mis_objects_call.filter_objects(MisCycle, order=cycle.order, project_id=project_mis_id)
    cycle_mis_id = cycle_mis.first().id if cycle_mis.exists() else None
    now = timezone.now()

    if execute_adl_village:
        tasks_bucket_create = []
        tasks_bucket_update = []
        print("Start sync_aggregated_status_on_adl for Village")
        for adl in mis_objects_call.filter_objects(AdministrativeLevel, type="Village", administrative_levels_projects__in=[project_mis_id], administrative_levels_cycles__in=[cycle_mis_id]):
            aggregs = AggregatedStatus.objects.filter(administrative_level_id=adl.id, project_id=project_id, cycle_id=cycle_id, facilitator=None, task__isnull=False)
            
            if aggregs.exists():
                aggreg_last_activity = aggregs.latest('last_activity') #.order_by('last_activity').last()
                # if aggreg_last_activity:
                #     adl.last_activity = aggreg_last_activity.last_activity
                

                task_action = "update"
                adl_a = AggregatedStatus.objects.filter(administrative_level_id=adl.id, task_id=None, project_id=project_id, cycle_id=cycle_id, facilitator=None).first()
                if not adl_a:
                    adl_a = AggregatedStatus()
                    adl_a.administrative_level_id = adl.id
                    adl_a.project_id = project_id
                    adl_a.cycle_id = cycle_id
                    adl_a.task = None
                    adl_a.facilitator = None
                    task_action = "create"
                        
                adl_a.last_activity = aggreg_last_activity.last_activity
                
                sums = aggregs.aggregate(
                    total_tasks_completed=Sum('total_tasks_completed'),
                    total_tasks=Sum('total_tasks'),
                    total_tasks_validated=Sum('total_tasks_validated'),
                    total_tasks_waiting_validation=Sum('total_tasks_waiting_validation'),
                    total_tasks_invalidated=Sum('total_tasks_invalidated'),
                    total_tasks_invalidated_review=Sum('total_tasks_invalidated_review'),
                    total_tasks_invalidated_review_completed=Sum('total_tasks_invalidated_review_completed'),
                    total_tasks_invalidated_review_in_pending=Sum('total_tasks_invalidated_review_in_pending'),
                    total_tasks_invalidated_unreview=Sum('total_tasks_invalidated_unreview'),
                    total_tasks_invalidated_unreview_completed=Sum('total_tasks_invalidated_unreview_completed'),
                    total_tasks_invalidated_unreview_in_pending=Sum('total_tasks_invalidated_unreview_in_pending'),
                )
                adl_a.total_tasks_completed = sums['total_tasks_completed'] or 0
                adl_a.total_tasks = sums['total_tasks'] or 0
                adl_a.total_tasks_validated = sums['total_tasks_validated'] or 0
                adl_a.total_tasks_waiting_validation = sums['total_tasks_waiting_validation'] or 0
                adl_a.total_tasks_invalidated = sums['total_tasks_invalidated'] or 0
                adl_a.total_tasks_invalidated_review = sums['total_tasks_invalidated_review'] or 0
                adl_a.total_tasks_invalidated_review_completed = sums['total_tasks_invalidated_review_completed'] or 0
                adl_a.total_tasks_invalidated_review_in_pending = sums['total_tasks_invalidated_review_in_pending'] or 0
                adl_a.total_tasks_invalidated_unreview = sums['total_tasks_invalidated_unreview'] or 0
                adl_a.total_tasks_invalidated_unreview_completed = sums['total_tasks_invalidated_unreview_completed'] or 0
                adl_a.total_tasks_invalidated_unreview_in_pending = sums['total_tasks_invalidated_unreview_in_pending'] or 0
                adl_a.updated_date = now
                
                if task_action == "create":
                    tasks_bucket_create.append(adl_a)
                else:
                    tasks_bucket_update.append(adl_a)

        if tasks_bucket_create:
            bulk_objects_create_or_update(AggregatedStatus, tasks_bucket_create, type_bulk="create")
        if tasks_bucket_update:
            bulk_objects_create_or_update(AggregatedStatus, tasks_bucket_update, type_bulk="update", fields=['total_tasks_completed', 'total_tasks', 'total_tasks_validated', 'total_tasks_waiting_validation', 'total_tasks_invalidated', 'total_tasks_invalidated_review', 'total_tasks_invalidated_review_completed', 'total_tasks_invalidated_review_in_pending', 'total_tasks_invalidated_unreview', 'total_tasks_invalidated_unreview_completed', 'total_tasks_invalidated_unreview_in_pending', 'last_activity', 'updated_date'])
        
        print("End sync_aggregated_status_on_adl for Village")

    if execute_adl_bigger_than_village:
        #Canton|Commune|Prefecture|Region
        adls_dict = {_type_adl: mis_objects_call.filter_objects(AdministrativeLevel, type=_type_adl, administrative_levels_projects__in=[project_mis_id], administrative_levels_cycles__in=[cycle_mis_id]) for _type_adl in ['Canton', 'Commune', 'Prefecture', 'Region']}
        _adls_ids_dict = {
            str(_adl.id): (
                list(set([v.cvd.headquarters_village.id for v in _adl.children if v and v.cvd and v.cvd.headquarters_village])) if _type_adl == 'Canton' else list(set([adm.id for adm in _adl.children]))
            ) for _type_adl, _adls in adls_dict.items() for _adl in _adls
        }
        for type_adl in ['Canton', 'Commune', 'Prefecture', 'Region']:
            print("Start sync_aggregated_status_on_adl for", type_adl, "for tasks")
            adls = adls_dict.get(type_adl)
            tasks_bucket_create = []
            tasks_bucket_update = []
            for adl in adls:
                _adls_ids = _adls_ids_dict.get(str(adl.id))
                
                for task in Task.objects.filter(project_id=project_id, cycles__in=[cycle_id]).order_by('id'):
                    children_agg = AggregatedStatus.all_objects.filter(task_id=task.id, administrative_level_id__in=_adls_ids, project_id=project_id, cycle_id=cycle_id, facilitator=None)
                    
                    aggreg_last_activity = None
                    if children_agg:
                        aggreg_last_activity = children_agg.latest('last_activity')

                    task_action = "update"
                    a = AggregatedStatus.all_objects.filter(administrative_level_id=adl.id, task_id=task.id, project_id=project_id, cycle_id=cycle_id, facilitator=None).first()
                    if not a:
                        a = AggregatedStatus()
                        a.administrative_level_id = adl.id
                        a.project_id = project_id
                        a.cycle_id = cycle_id
                        a.task_id = task.id
                        a.facilitator = None
                        if task.phase.name in PHASES_BEFORE_BEGINING_SUBPROJECT_EXECUTION:
                            a.task_needs_subproject = False
                        else:
                            a.task_needs_subproject = True
                        task_action = "create"

                    if villages_ids_have_subproject:
                        if adl.id in villages_ids_have_subproject:
                            a.its_adl_has_sub_project = True
                        else:
                            a.its_adl_has_sub_project = False
                    else:
                        a.its_adl_has_sub_project = None
                    
                    a.last_activity = aggreg_last_activity.last_activity if aggreg_last_activity else None

                    sums = children_agg.aggregate(
                        total_tasks_completed=Sum('total_tasks_completed'),
                        total_tasks=Sum('total_tasks'),
                        total_tasks_validated=Sum('total_tasks_validated'),
                        total_tasks_waiting_validation=Sum('total_tasks_waiting_validation'),
                        total_tasks_invalidated=Sum('total_tasks_invalidated'),
                        total_tasks_invalidated_review=Sum('total_tasks_invalidated_review'),
                        total_tasks_invalidated_review_completed=Sum('total_tasks_invalidated_review_completed'),
                        total_tasks_invalidated_review_in_pending=Sum('total_tasks_invalidated_review_in_pending'),
                        total_tasks_invalidated_unreview=Sum('total_tasks_invalidated_unreview'),
                        total_tasks_invalidated_unreview_completed=Sum('total_tasks_invalidated_unreview_completed'),
                        total_tasks_invalidated_unreview_in_pending=Sum('total_tasks_invalidated_unreview_in_pending'),
                    )
                    a.total_tasks_completed = sums['total_tasks_completed'] or 0
                    a.total_tasks = sums['total_tasks'] or 0
                    a.total_tasks_validated = sums['total_tasks_validated'] or 0
                    a.total_tasks_waiting_validation = sums['total_tasks_waiting_validation'] or 0
                    a.total_tasks_invalidated = sums['total_tasks_invalidated'] or 0
                    a.total_tasks_invalidated_review = sums['total_tasks_invalidated_review'] or 0
                    a.total_tasks_invalidated_review_completed = sums['total_tasks_invalidated_review_completed'] or 0
                    a.total_tasks_invalidated_review_in_pending = sums['total_tasks_invalidated_review_in_pending'] or 0
                    a.total_tasks_invalidated_unreview = sums['total_tasks_invalidated_unreview'] or 0
                    a.total_tasks_invalidated_unreview_completed = sums['total_tasks_invalidated_unreview_completed'] or 0
                    a.total_tasks_invalidated_unreview_in_pending = sums['total_tasks_invalidated_unreview_in_pending'] or 0
                    a.updated_date = now

                        # a.save()
                    if task_action == "create":
                        tasks_bucket_create.append(a)
                    else:
                        tasks_bucket_update.append(a)
                
            if tasks_bucket_create:
                bulk_objects_create_or_update(AggregatedStatus, tasks_bucket_create, type_bulk="create")
            if tasks_bucket_update:
                bulk_objects_create_or_update(AggregatedStatus, tasks_bucket_update, type_bulk="update", fields=['total_tasks_completed', 'total_tasks', 'total_tasks_validated', 'total_tasks_waiting_validation', 'total_tasks_invalidated', 'total_tasks_invalidated_review', 'total_tasks_invalidated_review_completed', 'total_tasks_invalidated_review_in_pending', 'total_tasks_invalidated_unreview', 'total_tasks_invalidated_unreview_completed', 'total_tasks_invalidated_unreview_in_pending', 'last_activity', 'its_adl_has_sub_project', 'updated_date'])
            
            print("End sync_aggregated_status_on_adl for", type_adl, "for tasks")


        for type_adl in ['Canton', 'Commune', 'Prefecture', 'Region']:
            print("Start sync_aggregated_status_on_adl for", type_adl, "for adl")
            adls = adls_dict.get(type_adl)
            tasks_bucket_create = []
            tasks_bucket_update = []
            for adl in adls:
                _adls_ids = _adls_ids_dict.get(str(adl.id))
                
                aggregs = AggregatedStatus.objects.filter(administrative_level_id=adl.id, project_id=project_id, cycle_id=cycle_id, facilitator=None, task__isnull=False)
                
                if aggregs.exists():

                    aggreg_last_activity = aggregs.latest('last_activity') #.order_by('last_activity').last()
                
                    task_action = "update"
                    adl_a = AggregatedStatus.objects.filter(administrative_level_id=adl.id, task=None, project_id=project_id, cycle_id=cycle_id, facilitator=None).first()
                    if not adl_a:
                        adl_a = AggregatedStatus()
                        adl_a.administrative_level_id = adl.id
                        adl_a.project_id = project_id
                        adl_a.cycle_id = cycle_id
                        adl_a.task = None
                        adl_a.facilitator = None
                        task_action = "create"
                    
                    adl_a.last_activity = aggreg_last_activity.last_activity

                    sums = aggregs.aggregate(
                        total_tasks_completed=Sum('total_tasks_completed'),
                        total_tasks=Sum('total_tasks'),
                        total_tasks_validated=Sum('total_tasks_validated'),
                        total_tasks_waiting_validation=Sum('total_tasks_waiting_validation'),
                        total_tasks_invalidated=Sum('total_tasks_invalidated'),
                        total_tasks_invalidated_review=Sum('total_tasks_invalidated_review'),
                        total_tasks_invalidated_review_completed=Sum('total_tasks_invalidated_review_completed'),
                        total_tasks_invalidated_review_in_pending=Sum('total_tasks_invalidated_review_in_pending'),
                        total_tasks_invalidated_unreview=Sum('total_tasks_invalidated_unreview'),
                        total_tasks_invalidated_unreview_completed=Sum('total_tasks_invalidated_unreview_completed'),
                        total_tasks_invalidated_unreview_in_pending=Sum('total_tasks_invalidated_unreview_in_pending'),
                    )
                    adl_a.total_tasks_completed = sums['total_tasks_completed'] or 0
                    adl_a.total_tasks = sums['total_tasks'] or 0
                    adl_a.total_tasks_validated = sums['total_tasks_validated'] or 0
                    adl_a.total_tasks_waiting_validation = sums['total_tasks_waiting_validation'] or 0
                    adl_a.total_tasks_invalidated = sums['total_tasks_invalidated'] or 0
                    adl_a.total_tasks_invalidated_review = sums['total_tasks_invalidated_review'] or 0
                    adl_a.total_tasks_invalidated_review_completed = sums['total_tasks_invalidated_review_completed'] or 0
                    adl_a.total_tasks_invalidated_review_in_pending = sums['total_tasks_invalidated_review_in_pending'] or 0
                    adl_a.total_tasks_invalidated_unreview = sums['total_tasks_invalidated_unreview'] or 0
                    adl_a.total_tasks_invalidated_unreview_completed = sums['total_tasks_invalidated_unreview_completed'] or 0
                    adl_a.total_tasks_invalidated_unreview_in_pending = sums['total_tasks_invalidated_unreview_in_pending'] or 0
                    adl_a.updated_date = now

                    if task_action == "create":
                        tasks_bucket_create.append(adl_a)
                    else:
                        tasks_bucket_update.append(adl_a)
                
            if tasks_bucket_create:
                bulk_objects_create_or_update(AggregatedStatus, tasks_bucket_create, type_bulk="create")
            if tasks_bucket_update:
                bulk_objects_create_or_update(AggregatedStatus, tasks_bucket_update, type_bulk="update", fields=['total_tasks_completed', 'total_tasks', 'total_tasks_validated', 'total_tasks_waiting_validation', 'total_tasks_invalidated', 'total_tasks_invalidated_review', 'total_tasks_invalidated_review_completed', 'total_tasks_invalidated_review_in_pending', 'total_tasks_invalidated_unreview', 'total_tasks_invalidated_unreview_completed', 'total_tasks_invalidated_unreview_in_pending', 'last_activity', 'updated_date'])
            
            print("End sync_aggregated_status_on_adl for", type_adl, "for adl")


        #End Canton|Commune|Prefecture|Region
    print("End sync_aggregated_status_on_adl")


"""
from process_manager.models import AggregatedStatus, AggregatedStatusFacilitator
from dashboard.tasks import sync_celery_tasks_re, sync_aggregated_status_on_adl
for projet in [(4,1,'COSO'), (6,3,'FA-COSO'), (5,2,'PURS')]: #COSO, FA-COSO, PURS
    print(projet)
    AggregatedStatus.objects.filter(project_id=projet[0]).delete()
    sync_celery_tasks_re(projet[0], projet[1])
    sync_aggregated_status_on_adl(projet[0], projet[1])
    AggregatedStatusFacilitator.objects.filter(project_id=projet[0], cycle_id=projet[1]).update(new_update_exists=True)


from process_manager.models import AggregatedStatus, AggregatedStatusFacilitator
from dashboard.tasks import sync_celery_tasks_re, sync_aggregated_status_on_adl
from dashboard.utils import search_facilitators_db_with_villages_stabilized
for projet in [(6,3,'FA-COSO')]: #COSO, FA-COSO, PURS (4,1,'COSO'), (6,3,'FA-COSO'), (5,2,'PURS')
    print(projet)
    #AggregatedStatus.objects.filter(project_id=projet[0]).delete()
    sync_celery_tasks_re(projet[0], projet[1])
    sync_aggregated_status_on_adl(projet[0], projet[1])
    AggregatedStatusFacilitator.objects.filter(project_id=projet[0], cycle_id=projet[1]).update(new_update_exists=True)


search_facilitators_db_with_villages_stabilized("COSO")


"""

def sync_celery_tasks_re(project_id, cycle_id, develop_mode=False, training_mode=False, no_sql_db=None, villages_ids_have_subproject=[]):
    project = Project.objects.get(id=project_id)
    cycle = Cycle.objects.get(id=cycle_id)
    project_mis = mis_objects_call.filter_objects(MisProject, name=project.name)
    project_mis_id = project_mis.first().id if project_mis.exists() else None
    cycle_mis = mis_objects_call.filter_objects(MisCycle, order=cycle.order, project_id=project_mis_id)
    cycle_mis_id = cycle_mis.first().id if cycle_mis.exists() else None
    now = timezone.now()
    
    nsc = NoSQLClient()
    count_facilitator = 0
    print("Start")

    if no_sql_db:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, no_sql_db_name=no_sql_db)
    else:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, projects__in=[project_id])

    tasks_bucket_create = []
    tasks_bucket_update = []

    administrativelevels_dict = {str(ad.id): str(ad.cvd.id) for ad in mis_objects_call.filter_objects(AdministrativeLevel, type="Village", administrative_levels_projects__in=[project_mis_id], administrative_levels_cycles__in=[cycle_mis_id])}
    cvds_dict_with_villages = {str(_cvd.id): [str(v.id) for v in _cvd.get_villages()] for _cvd in mis_objects_call.filter_objects(CVD)}

    for f in facilitators.order_by('id'):
        print()
        # print()
        # print()
        print(count_facilitator, f.no_sql_db_name, f.username)
        count_facilitator += 1
        # nbr_tasks_completed = 0
        # nbr_tasks = 0
        last_activity_date = "0000-00-00 00:00:00"
        facilitator_db = nsc.get_db(f.no_sql_db_name)
        docs = facilitator_db.all_docs(include_docs=True)['rows']

        facilitator_doc = None
        for _doc in docs:
            doc = _doc.get('doc')
            if doc.get('type') == 'facilitator' and not doc.get('develop_mode') and not doc.get('training_mode'):
                facilitator_doc = doc
                break

        docs = sorted([doc for doc in docs if doc.get('doc') and doc.get('doc').get('cycle_id') == cycle.couch_id and doc.get('doc').get('project_id') == project.couch_id and doc.get('doc').get('type') == 'task' and doc.get('doc').get('sql_id')], key=lambda obj: obj["doc"]["completed"])
        print(len(docs))

        if facilitator_doc:
            doc = facilitator_doc
            # cvds = get_cvds(project.couch_id, cycle.couch_id, doc)
            for _task in docs:
                _task = _task.get('doc')
                _administrative_level_id = administrativelevels_dict.get(str(_task.get('administrative_level_id')))
                _villages_ids = cvds_dict_with_villages.get(_administrative_level_id, []) if _administrative_level_id else []
                
                # for cvd in cvds:
                for ad_id in _villages_ids:
                    # _village = cvd['village']
                    # if _task.get('type') == 'task' and _task.get('sql_id') and str(_task.get('administrative_level_id')) == str(_village['id']):
                        
                        last_updated = datetime_complet_str(_task.get('last_updated'))
                        if last_updated and last_activity_date < last_updated:
                            last_activity_date = last_updated

                        #By village
                        # for ad_id in cvd['villages']:
                        # ad_id['id']
                           
                        task_action = "update"
                        a = AggregatedStatus.all_objects.filter(administrative_level_id=int(ad_id), task_id=int(_task["sql_id"]), project_id=project_id, cycle_id=cycle_id, facilitator=None).first()
                        if not a:
                            a = AggregatedStatus()
                            a.administrative_level_id = int(ad_id)
                            a.project_id = project_id
                            a.cycle_id = cycle_id
                            a.task_id = int(_task["sql_id"])
                            if _task["phase_name"] in PHASES_BEFORE_BEGINING_SUBPROJECT_EXECUTION:
                                a.task_needs_subproject = False
                            else:
                                a.task_needs_subproject = True
                            task_action = "create"
                                
                        a.total_tasks_completed = 1 if _task['completed'] else 0
                        a.total_tasks = 1

                        # Validation status
                        a.total_tasks_validated = 1 if _task.get("validated") else 0
                        a.total_tasks_waiting_validation = 1 if _task.get("completed") and _task.get("validated") == None else 0
                        
                        a.total_tasks_invalidated_review_completed = 0
                        a.total_tasks_invalidated_review_in_pending = 0
                        a.total_tasks_invalidated_unreview_completed = 0
                        a.total_tasks_invalidated_unreview_in_pending = 0

                        if villages_ids_have_subproject:
                            if int(ad_id) in villages_ids_have_subproject:
                                a.its_adl_has_sub_project = True
                            else:
                                a.its_adl_has_sub_project = False
                        else:
                            a.its_adl_has_sub_project = None
                                        
                        if _task.get("validated") == False:
                            a.total_tasks_invalidated = 1

                            updated_after_invalidation = _task.get("updated_after_invalidation")
                            # if not updated_after_invalidation:
                            #     action_by = _task.get("action_by", {})
                            #     if type(action_by) is list:
                            #         if action_by:
                            #             action_by = action_by[0] or {}
                            #         else:
                            #             action_by = {}
                            #     action_by_action_date = action_by.get('action_date') if action_by.get("type") == "Invalidated" else None
                            #     if action_by_action_date and _task.get("last_updated"):
                            #         action_by_action_date = datetime_complet_str(action_by_action_date)
                            #         action_last_updated = datetime_complet_str(_task.get("last_updated"))
                            #         if action_last_updated and action_by_action_date < action_last_updated:
                            #             updated_after_invalidation = True
                            if updated_after_invalidation:
                                a.total_tasks_invalidated_review = 1
                                a.total_tasks_invalidated_unreview = 0
                                if _task['completed']:
                                    a.total_tasks_invalidated_review_completed = 1
                                else:
                                    a.total_tasks_invalidated_review_in_pending = 1
                            else:
                                a.total_tasks_invalidated_unreview = 1
                                a.total_tasks_invalidated_review = 0
                                if _task['completed']:
                                    a.total_tasks_invalidated_unreview_completed = 1
                                else:
                                    a.total_tasks_invalidated_unreview_in_pending = 1

                        else:
                            a.total_tasks_invalidated = 0
                        # End - Validation status

                        _l_act = datetime_complet_str(_task.get('last_updated'))
                        a_last_activity = None if _l_act in (None, "0000-00-00 00:00:00") else parse_datetime(_l_act) #datetime.strptime(_l_act, '%Y-%m-%d %H:%M:%S')
                        if a_last_activity is not None:
                            a_last_activity = a_last_activity.replace(tzinfo=pytz.UTC)
                        a.last_activity = a_last_activity
                        a.updated_date = now

                        # a.save()
                        if task_action == "create":
                            tasks_bucket_create.append(a)
                        else:
                            tasks_bucket_update.append(a)

    
    #Backup
    backup_db = nsc.get_db("backup_db_facilitators_docs")
    backup_db_docs = backup_db.all_docs(include_docs=True)['rows']
    backup_db_docs = [doc for doc in backup_db_docs if doc.get('doc') and doc.get('doc').get('cycle_id') == cycle.couch_id and doc.get('doc').get('project_id') == project.couch_id and doc.get('doc').get('type') == 'task']
    for _task in backup_db_docs:
        _task = _task.get('doc')
        if _task.get('type') == 'task' and _task.get('sql_id') and _task.get('administrative_level_id'):

            _administrative_level_id = administrativelevels_dict.get(str(_task.get('administrative_level_id')))
            _villages_ids = cvds_dict_with_villages.get(_administrative_level_id, []) if _administrative_level_id else []
            
            # _adl = None
            # _adls = mis_objects_call.filter_objects(AdministrativeLevel, id=int(_task['administrative_level_id']))
            # if _adls:
            #     _adl = _adls.first()
            # else:
            #     print("ADL doesn't exists : ", _task['administrative_level_id'], _task['administrative_level_name'], "Canton ID : ", _task['canton_sql_id'])

            # if _adl and _adl.cvd:
                # for adl_o in _adl.cvd.get_villages():
                # adl_o.id
            for ad_id in _villages_ids:
                    task_action = "update"
                    a = AggregatedStatus.all_objects.filter(administrative_level_id=int(ad_id), task_id=int(_task["sql_id"]), project_id=project_id, cycle_id=cycle_id, facilitator=None).first()
                    if not a:
                        a = AggregatedStatus()
                        a.administrative_level_id = int(ad_id)
                        a.project_id = project_id
                        a.cycle_id = cycle_id
                        a.task_id = int(_task["sql_id"])
                        if _task["phase_name"] in PHASES_BEFORE_BEGINING_SUBPROJECT_EXECUTION:
                            a.task_needs_subproject = False
                        else:
                            a.task_needs_subproject = True
                        task_action = "create"
                            
                    a.total_tasks_completed = 1 if _task['completed'] else 0
                    a.total_tasks = 1

                    # Validation status
                    a.total_tasks_validated = 1 if _task.get("validated") else 0
                    a.total_tasks_waiting_validation = 1 if _task.get("completed") and _task.get("validated") == None else 0

                    a.total_tasks_invalidated_review_completed = 0
                    a.total_tasks_invalidated_review_in_pending = 0
                    a.total_tasks_invalidated_unreview_completed = 0
                    a.total_tasks_invalidated_unreview_in_pending = 0

                    if villages_ids_have_subproject:
                        if int(ad_id) in villages_ids_have_subproject:
                            a.its_adl_has_sub_project = True
                        else:
                            a.its_adl_has_sub_project = False
                    else:
                        a.its_adl_has_sub_project = None
                    
                    if _task.get("validated") == False:
                        a.total_tasks_invalidated = 1

                        updated_after_invalidation = _task.get("updated_after_invalidation")
                        # if not updated_after_invalidation:
                        #     action_by = _task.get("action_by", {})
                        #     if type(action_by) is list:
                        #         if action_by:
                        #             action_by = action_by[0] or {}
                        #         else:
                        #             action_by = {}
                        #     action_by_action_date = action_by.get('action_date') if action_by.get("type") == "Invalidated" else None
                        #     if action_by_action_date and _task.get("last_updated"):
                        #         action_by_action_date = datetime_complet_str(action_by_action_date)
                        #         action_last_updated = datetime_complet_str(_task.get("last_updated"))
                        #         if action_last_updated and action_by_action_date < action_last_updated:
                        #             updated_after_invalidation = True
                        if updated_after_invalidation:
                            a.total_tasks_invalidated_review = 1
                            a.total_tasks_invalidated_unreview = 0
                            if _task['completed']:
                                a.total_tasks_invalidated_review_completed = 1
                            else:
                                a.total_tasks_invalidated_review_in_pending = 1
                        else:
                            a.total_tasks_invalidated_unreview = 1
                            a.total_tasks_invalidated_review = 0
                            if _task['completed']:
                                a.total_tasks_invalidated_unreview_completed = 1
                            else:
                                a.total_tasks_invalidated_unreview_in_pending = 1

                    else:
                        a.total_tasks_invalidated = 0
                    # End - Validation status

                    _l_act = datetime_complet_str(_task.get('last_updated'))
                    a_last_activity = None if _l_act in (None, "0000-00-00 00:00:00") else parse_datetime(_l_act) #datetime.strptime(_l_act, '%Y-%m-%d %H:%M:%S')
                    if a_last_activity is not None:
                        a_last_activity = a_last_activity.replace(tzinfo=pytz.UTC)
                    a.last_activity = a_last_activity
                    a.updated_date = now

                    # a.save()
                    if task_action == "create":
                        tasks_bucket_create.append(a)
                    else:
                        tasks_bucket_update.append(a)
    
    # sync_aggregated_status_on_adl(project_id)
    
    # AggregatedStatusFacilitator.objects.filter(project_id=project_id, cycle_id=cycle_id).update(new_update_exists=True)

    if tasks_bucket_create:
        bulk_objects_create_or_update(AggregatedStatus, tasks_bucket_create, type_bulk="create")
    if tasks_bucket_update:
        bulk_objects_create_or_update(AggregatedStatus, tasks_bucket_update, type_bulk="update", fields=['total_tasks_completed', 'total_tasks', 'total_tasks_validated', 'total_tasks_waiting_validation', 'total_tasks_invalidated', 'total_tasks_invalidated_review', 'total_tasks_invalidated_unreview', 'last_activity', 'its_adl_has_sub_project', 'updated_date'])



    print("End")