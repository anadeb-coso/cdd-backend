from __future__ import absolute_import, unicode_literals
from cdd.celery import app
from celery import shared_task
from datetime import datetime
import pytz

from authentication.models import Facilitator
from dashboard.facilitators.functions import get_cvds
from no_sql_client import NoSQLClient
from process_manager.models import AggregatedStatus
from administrativelevels.models import AdministrativeLevel
from cdd.functions import datetime_complet_str


def recursive_to_save_administrativelevel_tasks_completed(count_facilitator, count_facilitator_cvd, ad: AdministrativeLevel, _task: dict):
    if ad.parent:
        parent = ad.parent
        _ok = True
        try:
            a = AggregatedStatus.objects.get(administrative_level_id=parent.id, task_id=int(_task["sql_id"]))
            if count_facilitator == 1 and count_facilitator_cvd == 1:
                a.total_tasks_completed = 0
                a.total_tasks = 0
        except AggregatedStatus.DoesNotExist as exc:
            a = AggregatedStatus()
            a.administrative_level_id = parent.id
            a.task_id = int(_task["sql_id"])
        except Exception as exc:
            print(exc)
            _ok = False
        if _ok:
            a.total_tasks_completed = ((a.total_tasks_completed+1) if _task['completed'] else a.total_tasks_completed)
            a.total_tasks += 1
            a.save()
        
        return recursive_to_save_administrativelevel_tasks_completed(count_facilitator, count_facilitator_cvd, parent, _task) #call recursive function
    
    return None


@app.task
def sync_celery_tasks():
    nsc = NoSQLClient()
    count_facilitator = 0
    print("Start")
    for f in Facilitator.objects.filter(develop_mode=False, training_mode=False).order_by('id'):
        print()
        print()
        print()
        print(count_facilitator, f.no_sql_db_name, f.username)
        count_facilitator += 1
        nbr_tasks_completed = 0
        nbr_tasks = 0
        last_activity_date = "0000-00-00 00:00:00"
        facilitator_db = nsc.get_db(f.no_sql_db_name)
        docs = facilitator_db.all_docs(include_docs=True)['rows']
        facilitator_doc = None
        for _doc in docs:
            doc = _doc.get('doc')
            if doc.get('type') == 'facilitator' and not doc.get('develop_mode') and not doc.get('training_mode'):
                facilitator_doc = doc
                break
            
        if facilitator_doc:
            doc = facilitator_doc
            cvds = get_cvds(doc)
            count_facilitator_cvd = 0
            for cvd in cvds:
                count_facilitator_cvd += 1
                _village = cvd['village']
                
                for _task in docs:
                    _task = _task.get('doc')
                    if _task.get('type') == 'task' and _task.get('sql_id') and str(_task.get('administrative_level_id')) == str(_village['id']):
                        if _task['completed']:
                            nbr_tasks_completed += 1
                        nbr_tasks += 1

                        last_updated = datetime_complet_str(_task.get('last_updated'))
                        if last_updated and last_activity_date < last_updated:
                            last_activity_date = last_updated

                        #By village
                        print(_task.get('administrative_level_id'), _task.get('name'), _task.get('sql_id'))
                        for ad_id in cvd['villages']:
                            a = None
                            _ok = True
                            try:
                                a = AggregatedStatus.objects.get(administrative_level_id=int(ad_id['id']), task_id=int(_task["sql_id"]))
                            except AggregatedStatus.DoesNotExist as exc:
                                a = AggregatedStatus()
                                a.administrative_level_id = int(ad_id['id'])
                                a.task_id = int(_task["sql_id"])
                            # except Exception as exc:
                            #     print(exc)
                            #     _ok = False
                            if _ok:
                                a.total_tasks_completed = 1 if _task['completed'] else 0
                                a.total_tasks = 1
                                a.save()
                        
                        #By Canton but counting on CVD not villages
                        try:
                            _village_cvd = AdministrativeLevel.objects.using('mis').get(id=int(_village['id']))
                            if _village_cvd.type == "Village":
                                recursive_to_save_administrativelevel_tasks_completed(count_facilitator, count_facilitator_cvd, _village_cvd, _task)
                        except:
                            pass
                        # _ok = True
                        # canton = AdministrativeLevel.objects.get(id=int(_village['id'])).parent
                        # try:
                        #     a_canton = AggregatedStatus.objects.get(administrative_level_id=canton.id, task_id=int(_task["sql_id"]))
                        #     if count_facilitator == 1:
                        #         a_canton.total_tasks_completed = 0
                        #         a_canton.total_tasks = 0
                        # except AggregatedStatus.DoesNotExist as exc:
                        #     a_canton = AggregatedStatus()
                        #     a_canton.administrative_level_id = canton.id
                        #     a_canton.task_id = int(_task["sql_id"])
                        # except Exception as exc:
                        #     print(exc)
                        #     _ok = False
                        # if _ok:
                        #     a_canton.total_tasks_completed = a_canton.total_tasks_completed+1 if _task['completed'] else a_canton.total_tasks_completed
                        #     a_canton.total_tasks =  a_canton.total_tasks + 1
                        #     a_canton.save()
                        
            print(count_facilitator_cvd)

            f.name = facilitator_doc.get('name')
            f.email = facilitator_doc.get('email')
            f.phone = facilitator_doc.get('phone')
            f.sex = facilitator_doc.get('sex')
            f.total_tasks_completed = nbr_tasks_completed
            f.total_tasks = nbr_tasks

            if last_activity_date == "0000-00-00 00:00:00":
                last_activity_date = None
            else:
                last_activity_date = datetime.strptime(last_activity_date, '%Y-%m-%d %H:%M:%S')
                # _date = last_activity_date.split()[0]
                # _hours = last_activity_date.split()[1]
                # last_activity_date = datetime(
                #     int(_date.split("-")[0]), int(_date.split("-")[1]), int(_date.split("-")[2]), 
                #     int(_hours.split(":")[0]), int(_hours.split(":")[1]), int(_hours.split(":")[2]),
                #     tzinfo=pytz.UTC
                # )
            f.last_activity = last_activity_date

            f.save()
        
    print("End")


# @app.on_after_configure.connect
# def setup_periodic_tasks(sender, **kwargs):
#     # Calls test every 10 seconds.
#     sender.add_periodic_task(10.0, test.s(4, 8), name='add every 10')