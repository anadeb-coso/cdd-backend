import itertools
from django.db import transaction
from django.utils import timezone

from no_sql_client import NoSQLClient
import grm_client
from administrativelevels import models as administrativelevels_models
from cdd.call_objects_from_other_db import mis_objects_call
from authentication.models import Facilitator
from assignments.models import AssignAdministrativeLevelToFacilitator
from process_manager.models import Project, AggregatedStatusFacilitator, AggregatedStatus
from subprojects.models import Project as ProjectMis


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

def get_cvds(project_couch_id, cycle_couch_id, facilitator, ald_ids: list = [], administratives_stabilized: list = []):
    administrative_levels_project = [_ for _ in facilitator['administrative_levels'] if (not cycle_couch_id or _.get('cycle_id') == cycle_couch_id) and (not project_couch_id or _.get('project_id') == project_couch_id)]
    administrative_levels_project_ids = [_.get('id') for _ in administrative_levels_project]
    geographical_units = [_ for _ in facilitator.get('geographical_units') if any(elem in administrative_levels_project_ids for elem in _['villages'])]
    CVDs = []
    if geographical_units:
        for index in range(len(geographical_units)) :
            element = geographical_units[index]
            if not ald_ids or (ald_ids and any(elt in ald_ids for elt in element['villages'])):
                for i in range(len(element["cvd_groups"])):
                    elt = element["cvd_groups"][i]

                    if any(elem in administrative_levels_project_ids for elem in elt['villages']):

                        if (administratives_stabilized and any(_elt in administratives_stabilized for _elt in elt['villages'])):
                            elt['stabilized'] = True
                        if (ald_ids and any(_elt in ald_ids for _elt in elt['villages'])):
                            elt['stabilized'] = True
                            elt['for_another_facilitator'] = True
                        
                        cvd_obj = administrativelevels_models.CVD.objects.using('mis').filter(id=int(elt['sql_id'])).first()
                        if cvd_obj:
                            if cvd_obj and not '(' in cvd_obj.name:
                                elt['cvd_name'] = f'{cvd_obj.name} ({cvd_obj.get_canton()})'
                            else:
                                elt['cvd_name'] = cvd_obj.name
                            
                            villages = []
                            for _index in range(len(administrative_levels_project)):
                                adl = administrative_levels_project[_index]
                                if elt.get('villages') and adl['id'] in elt['villages']:
                                    
                                    _in_list = False
                                    for v in villages:
                                        if adl['id'] == v['id']:
                                            _in_list = True
                                    if not _in_list:
                                        villages.append(adl)

                                        if adl.get('is_headquarters_village'):
                                            elt['village'] = adl
                                            elt['village_id'] = adl['id']
                            
                        # elt['village'] = villages[0] if len(villages) != 0 else None
                        # elt['village_id'] = villages[0]['id'] if len(villages) != 0 else None
                        if elt.get('village_id'):
                            elt['villages'] = villages
                            elt['unit'] = element['name']
                            CVDs.append(elt)
    
    return CVDs

def get_cvd_name_by_village_id(cvds, village_id):
    for cvd in cvds:
        for village in cvd['villages']:
            if village['id'] == village_id:
                return cvd['name']
    return None

def get_headquarters_village_id(cvds, village_id):
    for cvd in cvds:
        for village in cvd['villages']:
            if village['id'] == village_id:
                # print(cvd)
                return cvd['village']['id']
    return None

def is_village_principal(cvds, village_id):
    for cvd in cvds:
        if cvd['village_id'] == village_id:
            return True
    return False


def single_task_by_cvd(tasks, cvds):
    _tasks = []
    a = -1
    for _ in tasks:
        a += 1
        if not is_village_principal(cvds, _['administrative_level_id']):
            continue
        _['administrative_level_name'] = get_cvd_name_by_village_id(cvds, _['administrative_level_id'])
        _tasks.append(_)

    return _tasks


def clear_facilitator_docs_by_administrativelevels_and_save_to_backup_db(no_sql_db_name, backup_db_name, administrativelevels_ids):

    nsc = NoSQLClient()
    backup_db = nsc.get_db(backup_db_name)
    
    nsc_database = nsc.get_db(no_sql_db_name)
    fc_docs = nsc_database.all_docs(include_docs=True)['rows']
    
    for adl_id in administrativelevels_ids:
        for _doc in fc_docs:
            doc = _doc.get('doc')
            if doc.get('type') in ('task', 'activity', 'phase') and doc.get('administrative_level_id') == adl_id:
                # print(doc)
                try:
                    nsc.delete_document(backup_db, doc["_id"])
                except:
                    pass
                
                nsc.create_document(backup_db, doc)

                try:
                    fc_task = backup_db.get_query_result({
                        "_id": doc["_id"],
                        "administrative_level_id": doc["administrative_level_id"]
                    })[0]
                    if len(fc_task) != 0:
                        try:
                            nsc.delete_document(nsc_database, doc["_id"])
                        except Exception as exc:
                            print(exc)
                except:
                    pass
                
        


def get_search_for_stabilized_facilitator_dbs(project_mis_id, facilitator):
    nsc = NoSQLClient()
    no_sql_dbs_names_with_village_ids = {}
    cvds = []
    administratives_stabilized = []
    try:
        facilitator_grm = grm_client.get_facilitator_by_email(facilitator.get('email'))
        grm_client.attach_administrative_regions_objects(facilitator_grm)
        administratives_stabilized = facilitator_grm['administrative_regions']
        administrative_regions_objects = facilitator_grm.get('administrative_regions_objects')
        administratives_stabilized = list(set(
            (administratives_stabilized if administratives_stabilized else []) + list(itertools.chain(*[[str(v['id']) for v in ad['villages']] for ad in (administrative_regions_objects if administrative_regions_objects else [])]))
        ))

        for adl_id in administratives_stabilized:
            if adl_id not in [elt['id'] for elt in facilitator['administrative_levels']]:
                assing_facilitator_object = mis_objects_call.filter_objects(
                    AssignAdministrativeLevelToFacilitator, 
                    project_id=project_mis_id,
                    administrative_level_id=int(adl_id)
                ).last()
                if assing_facilitator_object:
                    _facilitator = Facilitator.objects.get(id=assing_facilitator_object.facilitator_id)
                    _ids = no_sql_dbs_names_with_village_ids[_facilitator.no_sql_db_name]['ids'] if _facilitator.no_sql_db_name in no_sql_dbs_names_with_village_ids else []
                    _ids.append(adl_id)
                    _ids = list(set(_ids))
                    no_sql_dbs_names_with_village_ids[_facilitator.no_sql_db_name] = {}
                    no_sql_dbs_names_with_village_ids[_facilitator.no_sql_db_name]['ids'] = list(set(_ids))
                    no_sql_dbs_names_with_village_ids[_facilitator.no_sql_db_name]['facilitator'] = _facilitator

        project_cdd = Project.objects.get(name=mis_objects_call.get_object(ProjectMis, id=project_mis_id).name)
        for k, v in no_sql_dbs_names_with_village_ids.items():
            cvds += get_cvds(project_cdd.couch_id, project_cdd.get_cycles().last().couch_id, nsc.get_db(k).get_query_result({"type": 'facilitator'})[:][0], v['ids'])
    
    except Exception as exc:
        print(exc)     

    return no_sql_dbs_names_with_village_ids, cvds, administratives_stabilized


def get_db_task(no_sql_dbs_names_with_village_ids: dict, task__id: str):
    nsc = NoSQLClient()

    for k, v in no_sql_dbs_names_with_village_ids.items():
        _db = nsc.get_db(k)
        query_result = _db.get_query_result({
                "type": 'task',
                "_id": task__id
        })[:]
        if query_result:
            return k, query_result
        
    return None, []



def update_facilitators_stats(facilitators, liste_villages, cdd_project_id, cdd_cycle_id, cdd_project_couch_id, project_mis):
    now = timezone.now()
    _facilitators = []
    agg_s_fs = AggregatedStatusFacilitator.objects.filter(facilitator__in=facilitators, project_id=cdd_project_id, cycle_id=cdd_cycle_id)
    dict_agg_s_fs = {str(ag.facilitator.id): ag for ag in agg_s_fs}
    havent_update = False if (facilitators and (not agg_s_fs.exists() or (agg_s_fs.exists() and agg_s_fs.filter(new_update_exists=True).exists()))) else True
    if havent_update:
        for f in facilitators:
            _f = dict_agg_s_fs.get(str(f.id))
            if _f:
                f.total_tasks_current_project = _f.total_tasks_current_project
                f.total_tasks_completed_current_project = _f.total_tasks_completed_current_project
                f.last_activity_current_project = _f.last_activity_current_project
                f.total_tasks_stabilized = _f.total_tasks_stabilized
                f.total_tasks_completed_stabilized = _f.total_tasks_completed_stabilized
                f.last_activity_stabilized = _f.last_activity_stabilized
                f.total_tasks = _f.total_tasks
                f.total_tasks_completed = _f.total_tasks_completed
                f.last_activity = _f.last_activity

                f.total_tasks_validated_current_project = _f.total_tasks_validated_current_project
                f.total_tasks_invalidated_current_project = _f.total_tasks_invalidated_current_project
                f.total_tasks_invalidated_review_current_project = _f.total_tasks_invalidated_review_current_project
                f.total_tasks_invalidated_review_completed_current_project = _f.total_tasks_invalidated_review_completed_current_project
                f.total_tasks_invalidated_review_in_pending_current_project = _f.total_tasks_invalidated_review_in_pending_current_project
                f.total_tasks_invalidated_unreview_current_project = _f.total_tasks_invalidated_unreview_current_project
                f.total_tasks_invalidated_unreview_completed_current_project = _f.total_tasks_invalidated_unreview_completed_current_project
                f.total_tasks_invalidated_unreview_in_pending_current_project = _f.total_tasks_invalidated_unreview_in_pending_current_project
                f.total_tasks_waiting_validation_current_project = _f.total_tasks_waiting_validation_current_project

                f.total_tasks_validated_stabilized = _f.total_tasks_validated_stabilized
                f.total_tasks_invalidated_stabilized = _f.total_tasks_invalidated_stabilized
                f.total_tasks_invalidated_review_stabilized = _f.total_tasks_invalidated_review_stabilized
                f.total_tasks_invalidated_review_completed_stabilized = _f.total_tasks_invalidated_review_completed_stabilized
                f.total_tasks_invalidated_review_in_pending_stabilized = _f.total_tasks_invalidated_review_in_pending_stabilized
                f.total_tasks_invalidated_unreview_stabilized = _f.total_tasks_invalidated_unreview_stabilized
                f.total_tasks_invalidated_unreview_completed_stabilized = _f.total_tasks_invalidated_unreview_completed_stabilized
                f.total_tasks_invalidated_unreview_in_pending_stabilized = _f.total_tasks_invalidated_unreview_in_pending_stabilized
                f.total_tasks_waiting_validation_stabilized = _f.total_tasks_waiting_validation_stabilized
                
                f.total_tasks_validated = _f.total_tasks_validated
                f.total_tasks_invalidated = _f.total_tasks_invalidated
                f.total_tasks_invalidated_review = _f.total_tasks_invalidated_review
                f.total_tasks_invalidated_review_completed = _f.total_tasks_invalidated_review_completed
                f.total_tasks_invalidated_review_in_pending = _f.total_tasks_invalidated_review_in_pending
                f.total_tasks_invalidated_unreview = _f.total_tasks_invalidated_unreview
                f.total_tasks_invalidated_unreview_completed = _f.total_tasks_invalidated_unreview_completed
                f.total_tasks_invalidated_unreview_in_pending = _f.total_tasks_invalidated_unreview_in_pending
                f.total_tasks_waiting_validation = _f.total_tasks_waiting_validation
                
                f.cvds_number_current_project = _f.cvds_number_current_project
                f.villages_number_current_project = _f.villages_number_current_project
                f.cvds_number_stabilized = _f.cvds_number_stabilized
                f.villages_number_stabilized = _f.villages_number_stabilized
                f.cvds_number = _f.cvds_number
                f.villages_number = _f.villages_number

                f.last_task_done_current_project = _f.last_task_done_current_project
                f.last_task_done_stabilized = _f.last_task_done_stabilized
                f.last_task_done = _f.last_task_done

            _facilitators.append(f)
    else:
        ag_f_bucket_create = []
        ag_f_bucket_update = []

        docs_eadls = [grm_client.attach_administrative_regions_objects(doc) for doc in grm_client.get_all_facilitators()]
        docs_eadls_dict = {doc.get('representative').get('email'): list(itertools.chain(*[[str(v['id']) for v in ad['villages']] for ad in doc['administrative_regions_objects']])) for doc in docs_eadls if doc.get('type') == 'adl' and doc.get('representative') and doc.get('administrative_regions_objects')}

        adls = project_mis.administrative_levels.filter(id__in=liste_villages) if liste_villages else project_mis.administrative_levels.all()

        adls_with_names = {str(adl.id): adl.name for adl in adls}

        adl_headquarters_villages = set(adl.cvd.headquarters_village.id for adl in adls if adl.cvd and adl.cvd.headquarters_village)
        adl_villages_ids = set(adl.id for adl in adls if adl.cvd)


        aggregs = AggregatedStatus.objects.filter(administrative_level_id__in=adl_headquarters_villages, project_id=cdd_project_id, cycle_id=cdd_cycle_id, facilitator=None, task__isnull=False)
        
        # Parcours des facilitateurs
        for f in facilitators:
            ag_f_action = "update"
            ag_f = dict_agg_s_fs.get(str(f.id))
            if not ag_f:
                ag_f = AggregatedStatusFacilitator()
                ag_f.project_id = cdd_project_id
                ag_f.cycle_id = cdd_cycle_id
                ag_f.facilitator_id = f.id
                ag_f_action = "create"

            administrative_levels_ids = [str(adl['id']) for adl in f.administrative_levels if adl['project_id'] == cdd_project_couch_id] if f.administrative_levels else []
            administrative_levels_ids_stabilize = docs_eadls_dict.get(f.email)
            administrative_levels_ids_stabilize = [ad_id for ad_id in administrative_levels_ids_stabilize if int(ad_id) in adl_villages_ids] if administrative_levels_ids_stabilize else []

            adl_headquarters_villages_uniques_current_project = set(str(elt) for elt in adl_headquarters_villages) & set(administrative_levels_ids)
            children_agg_current_project = [agg for agg in aggregs if str(agg.administrative_level_id) in administrative_levels_ids]
            f.villages_number_current_project = len(administrative_levels_ids)
            f.cvds_number_current_project = len(adl_headquarters_villages_uniques_current_project)
            ag_f.villages_number_current_project = f.villages_number_current_project
            ag_f.cvds_number_current_project = f.cvds_number_current_project

            adl_headquarters_villages_uniques_stabilized = set(str(elt) for elt in adl_headquarters_villages) & set(administrative_levels_ids_stabilize)
            children_agg_stabilized = [agg for agg in aggregs if str(agg.administrative_level_id) in administrative_levels_ids_stabilize]
            f.villages_number_stabilized = len(administrative_levels_ids_stabilize)
            f.cvds_number_stabilized = len(adl_headquarters_villages_uniques_stabilized)
            ag_f.villages_number_stabilized = f.villages_number_stabilized
            ag_f.cvds_number_stabilized = f.cvds_number_stabilized


            _administrative_levels_ids = list(set(administrative_levels_ids + administrative_levels_ids_stabilize))
            adl_headquarters_villages_uniques = set(str(elt) for elt in adl_headquarters_villages) & set(_administrative_levels_ids)
            children_agg = [agg for agg in aggregs if str(agg.administrative_level_id) in _administrative_levels_ids]
            f.villages_number = len(_administrative_levels_ids)
            f.cvds_number = len(adl_headquarters_villages_uniques)
            ag_f.villages_number = f.villages_number
            ag_f.cvds_number = f.cvds_number

            # Filtrer les éléments qui ont un last_activity valide (non-None)
            valid_aggregs_current_project = [agg for agg in children_agg_current_project if agg.last_activity is not None]
            valid_aggregs_stabilized = [agg for agg in children_agg_stabilized if agg.last_activity is not None]
            valid_aggregs = [agg for agg in children_agg if agg.last_activity is not None]

            # Calculer la dernière activité si possible
            aggreg_last_activity_current_project = max(valid_aggregs_current_project, key=lambda x: x.last_activity, default=None) if valid_aggregs_current_project else None
            aggreg_last_activity_stabilized = max(valid_aggregs_stabilized, key=lambda x: x.last_activity, default=None) if valid_aggregs_stabilized else None
            aggreg_last_activity = max(valid_aggregs, key=lambda x: x.last_activity, default=None) if valid_aggregs else None

            aggreg_last_task_done_current_project = max([ag for ag in valid_aggregs_current_project if ag.total_tasks_completed], key=lambda x: x.task.task_order, default=None) if valid_aggregs_current_project else None
            aggreg_last_task_done_stabilized = max([ag for ag in valid_aggregs_stabilized if ag.total_tasks_completed], key=lambda x: x.task.task_order, default=None) if valid_aggregs_stabilized else None
            aggreg_last_task_done = max([ag for ag in valid_aggregs if ag.total_tasks_completed], key=lambda x: x.task.task_order, default=None) if valid_aggregs else None


            # Assigner la dernière activité et les totaux des tâches
            f.last_activity_current_project = aggreg_last_activity_current_project.last_activity if aggreg_last_activity_current_project else None
            f.total_tasks_completed_current_project = sum(agg.total_tasks_completed for agg in children_agg_current_project)
            f.total_tasks_current_project = sum(agg.total_tasks for agg in children_agg_current_project)
            f.total_tasks_validated_current_project = sum(agg.total_tasks_validated for agg in children_agg_current_project)
            f.total_tasks_invalidated_current_project = sum(agg.total_tasks_invalidated for agg in children_agg_current_project)
            f.total_tasks_invalidated_review_current_project = sum(agg.total_tasks_invalidated_review for agg in children_agg_current_project)
            f.total_tasks_invalidated_review_completed_current_project = sum(agg.total_tasks_invalidated_review_completed for agg in children_agg_current_project)
            f.total_tasks_invalidated_review_in_pending_current_project = sum(agg.total_tasks_invalidated_review_in_pending for agg in children_agg_current_project)
            f.total_tasks_invalidated_unreview_current_project = sum(agg.total_tasks_invalidated_unreview for agg in children_agg_current_project)
            f.total_tasks_invalidated_unreview_completed_current_project = sum(agg.total_tasks_invalidated_unreview_completed for agg in children_agg_current_project)
            f.total_tasks_invalidated_unreview_in_pending_current_project = sum(agg.total_tasks_invalidated_unreview_in_pending for agg in children_agg_current_project)
            f.total_tasks_waiting_validation_current_project = sum(agg.total_tasks_waiting_validation for agg in children_agg_current_project)
            ag_f.last_activity_current_project = f.last_activity_current_project
            ag_f.total_tasks_completed_current_project = f.total_tasks_completed_current_project
            ag_f.total_tasks_current_project = f.total_tasks_current_project
            ag_f.total_tasks_validated_current_project = f.total_tasks_validated_current_project
            ag_f.total_tasks_invalidated_current_project = f.total_tasks_invalidated_current_project
            ag_f.total_tasks_invalidated_review_current_project = f.total_tasks_invalidated_review_current_project
            ag_f.total_tasks_invalidated_review_completed_current_project = f.total_tasks_invalidated_review_completed_current_project
            ag_f.total_tasks_invalidated_review_in_pending_current_project = f.total_tasks_invalidated_review_in_pending_current_project
            ag_f.total_tasks_invalidated_unreview_current_project = f.total_tasks_invalidated_unreview_current_project
            ag_f.total_tasks_invalidated_unreview_completed_current_project = f.total_tasks_invalidated_unreview_completed_current_project
            ag_f.total_tasks_invalidated_unreview_in_pending_current_project = f.total_tasks_invalidated_unreview_in_pending_current_project
            ag_f.total_tasks_waiting_validation_current_project = f.total_tasks_waiting_validation_current_project
            
            f.last_activity_stabilized = aggreg_last_activity_stabilized.last_activity if aggreg_last_activity_stabilized else None
            f.total_tasks_completed_stabilized = sum(agg.total_tasks_completed for agg in children_agg_stabilized)
            f.total_tasks_stabilized = sum(agg.total_tasks for agg in children_agg_stabilized)
            f.total_tasks_validated_stabilized = sum(agg.total_tasks_validated for agg in children_agg_stabilized)
            f.total_tasks_invalidated_stabilized = sum(agg.total_tasks_invalidated for agg in children_agg_stabilized)
            f.total_tasks_invalidated_review_stabilized = sum(agg.total_tasks_invalidated_review for agg in children_agg_stabilized)
            f.total_tasks_invalidated_review_completed_stabilized = sum(agg.total_tasks_invalidated_review_completed for agg in children_agg_stabilized)
            f.total_tasks_invalidated_review_in_pending_stabilized = sum(agg.total_tasks_invalidated_review_in_pending for agg in children_agg_stabilized)
            f.total_tasks_invalidated_unreview_stabilized = sum(agg.total_tasks_invalidated_unreview for agg in children_agg_stabilized)
            f.total_tasks_invalidated_unreview_completed_stabilized = sum(agg.total_tasks_invalidated_unreview_completed for agg in children_agg_stabilized)
            f.total_tasks_invalidated_unreview_in_pending_stabilized = sum(agg.total_tasks_invalidated_unreview_in_pending for agg in children_agg_stabilized)
            f.total_tasks_waiting_validation_stabilized = sum(agg.total_tasks_waiting_validation for agg in children_agg_stabilized)
            ag_f.last_activity_stabilized = f.last_activity_stabilized
            ag_f.total_tasks_completed_stabilized = f.total_tasks_completed_stabilized
            ag_f.total_tasks_stabilized = f.total_tasks_stabilized
            ag_f.total_tasks_validated_stabilized = f.total_tasks_validated_stabilized
            ag_f.total_tasks_invalidated_stabilized = f.total_tasks_invalidated_stabilized
            ag_f.total_tasks_invalidated_review_stabilized = f.total_tasks_invalidated_review_stabilized
            ag_f.total_tasks_invalidated_review_completed_stabilized = f.total_tasks_invalidated_review_completed_stabilized
            ag_f.total_tasks_invalidated_review_in_pending_stabilized = f.total_tasks_invalidated_review_in_pending_stabilized
            ag_f.total_tasks_invalidated_unreview_stabilized = f.total_tasks_invalidated_unreview_stabilized
            ag_f.total_tasks_invalidated_unreview_completed_stabilized = f.total_tasks_invalidated_unreview_completed_stabilized
            ag_f.total_tasks_invalidated_unreview_in_pending_stabilized = f.total_tasks_invalidated_unreview_in_pending_stabilized
            ag_f.total_tasks_waiting_validation_stabilized = f.total_tasks_waiting_validation_stabilized

            f.last_activity = aggreg_last_activity.last_activity if aggreg_last_activity else None
            f.total_tasks_completed = sum(agg.total_tasks_completed for agg in children_agg)
            f.total_tasks = sum(agg.total_tasks for agg in children_agg)
            f.total_tasks_validated = sum(agg.total_tasks_validated for agg in children_agg)
            f.total_tasks_invalidated = sum(agg.total_tasks_invalidated for agg in children_agg)
            f.total_tasks_invalidated_review = sum(agg.total_tasks_invalidated_review for agg in children_agg)
            f.total_tasks_invalidated_review_completed = sum(agg.total_tasks_invalidated_review_completed for agg in children_agg)
            f.total_tasks_invalidated_review_in_pending = sum(agg.total_tasks_invalidated_review_in_pending for agg in children_agg)
            f.total_tasks_invalidated_unreview = sum(agg.total_tasks_invalidated_unreview for agg in children_agg)
            f.total_tasks_invalidated_unreview_completed = sum(agg.total_tasks_invalidated_unreview_completed for agg in children_agg)
            f.total_tasks_invalidated_unreview_in_pending = sum(agg.total_tasks_invalidated_unreview_in_pending for agg in children_agg)
            f.total_tasks_waiting_validation = sum(agg.total_tasks_waiting_validation for agg in children_agg)
            ag_f.last_activity = f.last_activity
            ag_f.total_tasks_completed = f.total_tasks_completed
            ag_f.total_tasks = f.total_tasks
            ag_f.total_tasks_validated = f.total_tasks_validated
            ag_f.total_tasks_invalidated = f.total_tasks_invalidated
            ag_f.total_tasks_invalidated_review = f.total_tasks_invalidated_review
            ag_f.total_tasks_invalidated_review_completed = f.total_tasks_invalidated_review_completed
            ag_f.total_tasks_invalidated_review_in_pending = f.total_tasks_invalidated_review_in_pending
            ag_f.total_tasks_invalidated_unreview = f.total_tasks_invalidated_unreview
            ag_f.total_tasks_invalidated_unreview_completed = f.total_tasks_invalidated_unreview_completed
            ag_f.total_tasks_invalidated_unreview_in_pending = f.total_tasks_invalidated_unreview_in_pending
            ag_f.total_tasks_waiting_validation = f.total_tasks_waiting_validation

            f.last_task_done_current_project = aggreg_last_task_done_current_project.task if aggreg_last_task_done_current_project else None
            f.last_task_done_stabilized = aggreg_last_task_done_stabilized.task if aggreg_last_task_done_stabilized else None
            f.last_task_done = aggreg_last_task_done.task if aggreg_last_task_done else None
            ag_f.last_task_done_current_project = f.last_task_done_current_project
            ag_f.last_task_done_stabilized = f.last_task_done_stabilized
            ag_f.last_task_done = f.last_task_done

            adl_headquarters_villages_infos = []
            for k, v in {'current_project': adl_headquarters_villages_uniques_current_project, 'stabilized': adl_headquarters_villages_uniques_stabilized}.items():
                for adl_h_id in v:
                    if k == 'stabilized' and adl_h_id in adl_headquarters_villages_uniques_current_project:
                        continue

                    _children_aggs = [agg for agg in aggregs if str(agg.administrative_level_id) == adl_h_id]
                    
                    # Filtrer les éléments qui ont un last_activity valide (non-None)
                    _valid_aggregs = [agg for agg in _children_aggs if agg.last_activity is not None]

                    # Calculer la dernière activité si possible
                    _aggreg_last_activity = max(_valid_aggregs, key=lambda x: x.last_activity, default=None) if _valid_aggregs else None
                    _aggreg_last_task_done = max([ag for ag in _valid_aggregs if ag.total_tasks_completed], key=lambda x: x.task.task_order, default=None) if _valid_aggregs else None
                    
                    # Assigner la dernière activité et les totaux des tâches
                    _last_activity = _aggreg_last_activity.last_activity if _aggreg_last_activity else None
                    _total_tasks_completed = sum(agg.total_tasks_completed for agg in _children_aggs)
                    _total_tasks = sum(agg.total_tasks for agg in _children_aggs)
                    _total_tasks_validated = sum(agg.total_tasks_validated for agg in _children_aggs)
                    _total_tasks_invalidated = sum(agg.total_tasks_invalidated for agg in _children_aggs)
                    _total_tasks_invalidated_review = sum(agg.total_tasks_invalidated_review for agg in _children_aggs)
                    _total_tasks_invalidated_review_completed = sum(agg.total_tasks_invalidated_review_completed for agg in _children_aggs)
                    _total_tasks_invalidated_review_in_pending = sum(agg.total_tasks_invalidated_review_in_pending for agg in _children_aggs)
                    _total_tasks_invalidated_unreview = sum(agg.total_tasks_invalidated_unreview for agg in _children_aggs)
                    _total_tasks_invalidated_unreview_completed = sum(agg.total_tasks_invalidated_unreview_completed for agg in _children_aggs)
                    _total_tasks_invalidated_unreview_in_pending = sum(agg.total_tasks_invalidated_unreview_in_pending for agg in _children_aggs)
                    _total_tasks_waiting_validation = sum(agg.total_tasks_waiting_validation for agg in _children_aggs)
                    _last_task_done = {
                        'id': _aggreg_last_task_done.task.id,
                        'name': _aggreg_last_task_done.task.name,
                        'phase_name': _aggreg_last_task_done.task.phase.name,
                        'activity_name': _aggreg_last_task_done.task.activity.name,
                        'order': _aggreg_last_task_done.task.order,
                        'task_order': _aggreg_last_task_done.task.task_order,
                    } if _aggreg_last_task_done and _aggreg_last_task_done.task else None
                    _type = k
                    
                    adl_headquarters_villages_infos.append({
                        'village_name': adls_with_names.get(adl_h_id),
                        'last_activity': _last_activity.strftime('%Y-%m-%dT%H:%M:%S.%fZ') if _last_activity else None,
                        'total_tasks_completed': _total_tasks_completed,
                        'total_tasks': _total_tasks,
                        'percent': float("%.2f" % (((_total_tasks_completed/_total_tasks)*100) if _total_tasks else 0)),
                        'total_tasks_validated': _total_tasks_validated,
                        'total_tasks_invalidated': _total_tasks_invalidated,
                        'total_tasks_invalidated_review': _total_tasks_invalidated_review,
                        'total_tasks_invalidated_review_completed': _total_tasks_invalidated_review_completed,
                        'total_tasks_invalidated_review_in_pending': _total_tasks_invalidated_review_in_pending,
                        'total_tasks_invalidated_unreview': _total_tasks_invalidated_unreview,
                        'total_tasks_invalidated_unreview_completed': _total_tasks_invalidated_unreview_completed,
                        'total_tasks_invalidated_unreview_in_pending': _total_tasks_invalidated_unreview_in_pending,
                        'total_tasks_waiting_validation': _total_tasks_waiting_validation,
                        'last_task_done': _last_task_done,
                        'type': _type,
                        'in_the_both': adl_h_id in adl_headquarters_villages_uniques_current_project and adl_h_id in adl_headquarters_villages_uniques_stabilized
                    })

            ag_f.administrative_level_headquarters_villages_infos = adl_headquarters_villages_infos
            ag_f.new_update_exists = False
            ag_f.updated_date = now
            # ag_f.save()
            if ag_f_action == "create":
                ag_f_bucket_create.append(ag_f)
            else:
                ag_f_bucket_update.append(ag_f)
            
            _facilitators.append(f)

        if ag_f_bucket_create:
            bulk_objects_create_or_update(AggregatedStatusFacilitator, ag_f_bucket_create, type_bulk="create", batch_size=10)
        if ag_f_bucket_update:
            bulk_objects_create_or_update(
                AggregatedStatusFacilitator, 
                ag_f_bucket_update, type_bulk="update", 
                fields=[
                    'villages_number_current_project', 'cvds_number_current_project', 'villages_number_stabilized', 'cvds_number_stabilized',
                    'villages_number', 'cvds_number', 'last_activity_current_project', 'total_tasks_completed_current_project',
                    'total_tasks_current_project', 'total_tasks_validated_current_project', 'total_tasks_invalidated_current_project',
                    'total_tasks_invalidated_review_current_project', 'total_tasks_invalidated_review_completed_current_project', 'total_tasks_invalidated_review_in_pending_current_project', 
                    'total_tasks_invalidated_unreview_current_project', 'total_tasks_invalidated_unreview_completed_current_project', 'total_tasks_invalidated_unreview_in_pending_current_project', 
                    'total_tasks_waiting_validation_current_project', 'last_activity_stabilized', 'total_tasks_completed_stabilized',
                    'total_tasks_stabilized', 'total_tasks_validated_stabilized', 'total_tasks_invalidated_stabilized',
                    'total_tasks_invalidated_review_stabilized', 'total_tasks_invalidated_review_completed_stabilized', 'total_tasks_invalidated_review_in_pending_stabilized', 
                    'total_tasks_invalidated_unreview_stabilized', 'total_tasks_invalidated_unreview_completed_stabilized', 'total_tasks_invalidated_unreview_in_pending_stabilized',
                    'total_tasks_waiting_validation_stabilized', 'last_activity', 'total_tasks_completed', 'total_tasks', 'total_tasks_validated',
                    'total_tasks_invalidated', 
                    'total_tasks_invalidated_review', 'total_tasks_invalidated_review_completed', 'total_tasks_invalidated_review_in_pending', 
                    'total_tasks_invalidated_unreview', 'total_tasks_invalidated_unreview_completed', 'total_tasks_invalidated_unreview_in_pending', 
                    'total_tasks_waiting_validation', 'last_task_done_current_project', 'last_task_done_stabilized', 'last_task_done', 
                    'administrative_level_headquarters_villages_infos', 'new_update_exists', 'updated_date'
                ], 
                batch_size=10
            )

    return _facilitators