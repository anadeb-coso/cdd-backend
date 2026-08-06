from django.db.models import Q
import pandas as pd
import os
from sys import platform
from datetime import datetime

from authentication.models import Facilitator
from no_sql_client import NoSQLClient
import grm_client
from cdd.call_objects_from_other_db import mis_objects_call
from administrativelevels.models import AdministrativeLevel
from assignments.models import AssignAdministrativeLevelToFacilitator
from process_manager.models import Cycle, Project


def get_last_task_completed(last_task_completed, _task):
    if ((not last_task_completed and _task.get('completed')) or (
            last_task_completed and _task.get('completed') and _task.get('task_order') > last_task_completed.get('task_order') 
        )):
        return _task
    return last_task_completed

def get_cvd_index(datas_dict_havent_priorities_pav: dict, cvd_id: str):
    g_index = -1
    for k, v in datas_dict_havent_priorities_pav.items():
        if k == "ID CVD":
            for _k, _v in v.items():
                if _v == cvd_id:
                    return (_k, True)
                else:
                    g_index = _k if _k > g_index else g_index
    return (g_index + 1, False)

def villages_level(project_id, cycle_id, develop_mode=False, training_mode=False, no_sql_db=False):
    
    cycle = Cycle.objects.get(id=cycle_id)
    project = Project.objects.get(id=project_id)

    if no_sql_db:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, no_sql_db_name=no_sql_db).order_by('name')
    else:
        facilitators = Facilitator.objects.filter(develop_mode=develop_mode, training_mode=training_mode, projects__in=[project_id]).order_by('name')

    datas = {
        "ID CVD": {},
        "REGION": {},
        "PREFECTURE": {},
        "COMMUNE": {},
        "CANTON": {},
        "CVD": {},
        "VILLAGES": {},
        "PHASE": {},
        "ACTIVITE": {},
        "TACHE": {},
        "AC": {},
        "PHONE": {},
    }
    datas_dict_cvd_with_last_task = {
        "ID CVD": {},
        "task": {}
    }
    
    nsc = NoSQLClient()

    all_villages_ids_with_facilitators = grm_client.get_villages_with_facilitators(list(set(sum([
        list(set((facilitator.administrative_levels_ids or []) + (facilitator.stabilization_administrative_ids or []))) 
        for facilitator in facilitators
    ], []))))

    for facilitator in facilitators:
        facilitator_database = nsc.get_db(facilitator.no_sql_db_name)
        fc_tasks = facilitator_database.all_docs(include_docs=True)['rows']
        fc_tasks = [doc for doc in fc_tasks if doc.get('doc') and doc.get('doc').get('cycle_id') == cycle.couch_id and doc.get('doc').get('project_id') == project.couch_id]

        for _task in fc_tasks:
            task = _task.get('doc')
            if task and task.get('cycle_id') == cycle.couch_id and task.get('type') == "task":

                _village = mis_objects_call.get_object(AdministrativeLevel, id=int(task.get("administrative_level_id")))
                cvd = _village.cvd
                count, exists = get_cvd_index(datas, cvd.id if cvd else 0)

                if not exists:
                    assign_facilitators = mis_objects_call.filter_objects(
                        AssignAdministrativeLevelToFacilitator, 
                        project_id=project_id,
                        administrative_level_id=int(task.get("administrative_level_id"))
                    )
                    # facilitators_stabilized = eadls.get_view_result('administrative_regions', 'elements_in_list', keys=[task.get("administrative_level_id")])
                    # _f_s = []
                    # if facilitators_stabilized:
                    #     for elt in facilitators_stabilized[:]:
                    #         if elt.get('value') and elt.get('value') not in _f_s:
                    #             _f_s.append(elt['value'])

                    facilitators_stabilized = all_villages_ids_with_facilitators.get(str(task.get("administrative_level_id")), [])
                    # [
                    #     {'doc': doc}
                    #     for doc in grm_client.get_facilitator_by_village(int(task.get("administrative_level_id")))
                    # ]
                    _f_s = []
                    if facilitators_stabilized:
                        for elt in facilitators_stabilized:
                        # for row in facilitators_stabilized[:]:
                        #     elt = row['doc']
                            if elt not in _f_s:
                                _f_s.append(elt)

                    _facilitators = Facilitator.objects.filter(
                        Q(id__in=([facilitator.id]+[a_f.facilitator_id for a_f in assign_facilitators])) |
                        Q(email__in=[doc.get('representative').get('email') for doc in _f_s if doc.get('representative')]),
                        active=True
                    )

                last_task_completed = get_last_task_completed(
                    datas_dict_cvd_with_last_task["task"][count] if (
                        datas_dict_cvd_with_last_task["task"].get(count)
                    ) else None, 
                    task
                )
                datas_dict_cvd_with_last_task["ID CVD"][count] = cvd.id if cvd else 0
                datas_dict_cvd_with_last_task["task"][count] = last_task_completed

                datas["ID CVD"][count] = cvd.id if cvd else 0
                datas["REGION"][count] = _village.parent.parent.parent.parent.name
                datas["PREFECTURE"][count] = _village.parent.parent.parent.name
                datas["COMMUNE"][count] = _village.parent.parent.name
                datas["CANTON"][count] = _village.parent.name
                datas["CVD"][count] = cvd.name if cvd and cvd.name else task.get("administrative_level_name")
                datas["VILLAGES"][count] = " ; ".join([v.name for v in cvd.get_villages()]) if cvd else _village.name
                datas["PHASE"][count] = last_task_completed.get("phase_name") if last_task_completed else ""
                datas["ACTIVITE"][count] = last_task_completed.get("activity_name") if last_task_completed else ""
                datas["TACHE"][count] = last_task_completed.get("name") if last_task_completed else ""
                if not exists:
                    datas["AC"][count] = " ; ".join([f.name for f in _facilitators if f.name])
                    datas["PHONE"][count] = " ; ".join([f.phone for f in _facilitators if f.phone])
                
        

    bk_database = nsc.get_db("backup_db_facilitators_docs")
    bk_tasks = bk_database.all_docs(include_docs=True)['rows']
    bk_tasks = [doc for doc in bk_tasks if doc.get('doc') and doc.get('doc').get('cycle_id') == cycle.couch_id and doc.get('doc').get('project_id') == project.couch_id]
    
    for _doc in bk_tasks:
        task = _doc.get('doc')
        if task and task.get('cycle_id') == cycle.couch_id and task.get('type') == "task":
        
            _village = mis_objects_call.filter_objects(AdministrativeLevel, id=int(task.get("administrative_level_id"))).first()
            if _village:
                cvd = _village.cvd
                count, exists = get_cvd_index(datas, cvd.id if cvd else 0)

                if not exists:
                    assign_facilitators = mis_objects_call.filter_objects(
                        AssignAdministrativeLevelToFacilitator, 
                        project_id=project_id,
                        administrative_level_id=int(task.get("administrative_level_id"))
                    )
                    # facilitators_stabilized = eadls.get_view_result('administrative_regions', 'elements_in_list', keys=[task.get("administrative_level_id")])
                    # _f_s = []
                    # if facilitators_stabilized:
                    #     for elt in facilitators_stabilized[:]:
                    #         if elt.get('value') and elt.get('value') not in _f_s:
                    #             _f_s.append(elt['value'])

                    facilitators_stabilized = all_villages_ids_with_facilitators.get(str(task.get("administrative_level_id")), [])
                    
                    _f_s = []
                    if facilitators_stabilized:
                        for elt in facilitators_stabilized:
                            if elt not in _f_s:
                                _f_s.append(elt)


                    _facilitators = Facilitator.objects.filter(
                        Q(id__in=([a_f.facilitator_id for a_f in assign_facilitators])) |
                        Q(email__in=[doc.get('representative').get('email') for doc in _f_s if doc.get('representative')]),
                        active=True
                    )

                last_task_completed = get_last_task_completed(
                    datas_dict_cvd_with_last_task["task"][count] if (
                        datas_dict_cvd_with_last_task["task"].get(count)
                    ) else None, 
                    task
                )
                datas_dict_cvd_with_last_task["ID CVD"][count] = cvd.id if cvd else 0
                datas_dict_cvd_with_last_task["task"][count] = last_task_completed

                datas["ID CVD"][count] = cvd.id if cvd else 0
                datas["REGION"][count] = _village.parent.parent.parent.parent.name
                datas["PREFECTURE"][count] = _village.parent.parent.parent.name
                datas["COMMUNE"][count] = _village.parent.parent.name
                datas["CANTON"][count] = _village.parent.name
                datas["CVD"][count] = cvd.name if cvd and cvd.name else task.get("administrative_level_name")
                datas["VILLAGES"][count] = " ; ".join([v.name for v in cvd.get_villages()]) if cvd else _village.name
                datas["PHASE"][count] = last_task_completed.get("phase_name") if last_task_completed else ""
                datas["ACTIVITE"][count] = last_task_completed.get("activity_name") if last_task_completed else ""
                datas["TACHE"][count] = last_task_completed.get("name") if last_task_completed else ""
                if not exists:
                    datas["AC"][count] = " ; ".join([f.name for f in _facilitators if f.name])
                    datas["PHONE"][count] = " ; ".join([f.phone for f in _facilitators if f.phone])
                

    if not os.path.exists("media/utils/exports"):
            os.makedirs("media/utils/exports")
    file_path = f'utils/exports/villages_level_{str(datetime.today().replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_")}.xlsx'

    df = pd.DataFrame(datas)

    with pd.ExcelWriter("media/"+file_path) as writer:
        df.to_excel(writer, sheet_name='Niveaux avancement', index=False)

        
    if platform == "win32":
        # windows
        return file_path.replace("/", "\\\\")
    else:
        return file_path