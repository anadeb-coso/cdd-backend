import os
import sys
from datetime import datetime
import json
import requests
from requests.auth import HTTPBasicAuth
import pandas as pd
from sys import platform
import re

from authentication.models import Facilitator
from cdd.call_objects_from_other_db import mis_objects_call
from administrativelevels.models import AdministrativeLevel
from assignments.models import AssignAdministrativeLevelToFacilitator
from dashboard.facilitators.repository.db_facilitator_repository import FacilitatorRepository
from dashboard.facilitators.repository.facilitator_criteria import FacilitatorCriteria
from subprojects.models import Project as MisProject
from cdd.call_objects_from_other_db import mis_objects_call
from dashboard.administrative_levels.functions import get_cascade_villages_by_administrative_level_id

from no_sql_client import NoSQLClient
from cdd.constants import INVALID_CHARS, HEADERS_FORM_FIELDS, HEADERS_HISTORY



def all_cdd_datas(facilitator_dbs_name, params={"type":"All", "ids_administrativelevel":""}):
    
    project_name = params.get('session_project_name')
    include_form_fields = params.get('include_form_fields')
    include_history = params.get('include_history')

    headers_to_skip = []
    if not include_form_fields and not include_history:
        headers_to_skip = HEADERS_FORM_FIELDS + HEADERS_HISTORY
    elif not include_form_fields:
        headers_to_skip = HEADERS_FORM_FIELDS
    elif not include_history:
        headers_to_skip = HEADERS_HISTORY

    nsc = NoSQLClient()
    
    _type = params.get("type")
    liste_villages = get_cascade_villages_by_administrative_level_id(params.get("ids_administrativelevel"))
    village_ids = [v['administrative_id'] for v in liste_villages]
    
    project_mis = mis_objects_call.filter_objects(MisProject, name=project_name)
    project_mis_id = project_mis.first().id if project_mis.count() >= 1 else 1
    if facilitator_dbs_name:
        fs = Facilitator.objects.filter(develop_mode=False, training_mode=False, no_sql_db_name__in=facilitator_dbs_name)
    else:
        if params.get("ids_administrativelevel"):
            assign_facilitators = AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(
                administrative_level_id__in=[int(v_id) for v_id in village_ids],
                project_id=project_mis_id,
                activated=True
            )
            criteria = FacilitatorCriteria(
                id__in=list(set([int(f.facilitator_id) for f in assign_facilitators])),
                develop_mode=False,
                training_mode=False,
                projects__id=[params.get('session_project_id')]
            )

        else:
            criteria = FacilitatorCriteria(
                develop_mode=False,
                training_mode=False,
                projects__id=[params.get('session_project_id')]
            )
        fs = FacilitatorRepository().find_by_criteria(criteria=criteria)

    
    def append_data_to_dict(flat_doc: dict, dict_item: tuple):
        if dict_item[0] not in headers_to_skip:
            if type(dict_item[1]) in (dict, list):
                if type(dict_item[1]) == dict:
                    for k, v in [(k, v) for k, v in dict_item[1].items() if k not in headers_to_skip]:
                        append_data_to_dict(flat_doc, (f"{dict_item[0]}_{k}", v))
                else:
                    for i in range(len(dict_item[1])):
                        append_data_to_dict(flat_doc, (f"{dict_item[0]}_{str(i).zfill(2)}", dict_item[1][i]))
            else:
                flat_doc[dict_item[0]] = int(dict_item[1]) if type(dict_item[1]) is bool else dict_item[1]

    selector = {
        "type": "task"
    }
    
    if village_ids:
        selector["administrative_level_id"] = {"$in": village_ids}

    all_datas = {}
    
    for facilitator in fs:
        facilitator_database = nsc.get_db(facilitator.no_sql_db_name)
        
        fc_tasks = facilitator_database.get_query_result(
            selector
            # , 
            # sort=[{'task_order': 'desc'}]
        )

        for row in fc_tasks:
            flat_doc = {}
            for k, v in row.items():
                if k not in headers_to_skip:
                    append_data_to_dict(flat_doc, (k, v))
            flat_doc = dict(sorted(flat_doc.items()))
            if flat_doc.get("name"):
                sheet_name = re.sub(INVALID_CHARS, ' ', flat_doc["name"])
                if flat_doc.get("task_order"):
                    sheet_name = f'{str(flat_doc.get("task_order")).zfill(3)} {sheet_name}'
                if not all_datas.get(sheet_name):
                    all_datas[sheet_name] = [flat_doc]
                else:
                    all_datas[sheet_name].append(flat_doc)


    if not os.path.exists("media/utils/exports"):
            os.makedirs("media/utils/exports")
    file_path = f'utils/exports/cdd_datas_{str(datetime.today().replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_")}.xlsx'
    
    all_datas_order = dict(sorted(all_datas.items()))

    if all_datas_order:
        first_sheet = list(all_datas_order.keys())[0]
        df = pd.DataFrame(all_datas_order[first_sheet])
        
        with pd.ExcelWriter("media/"+file_path) as writer:
            df.to_excel(writer, sheet_name=first_sheet, index=False)
            
            for k, v in all_datas_order.items():
                if k != first_sheet:
                    pd.DataFrame(
                        v
                    ).to_excel(writer, sheet_name=k, index=False)

        
    if platform == "win32":
        # windows
        return file_path.replace("/", "\\\\")
    else:
        return file_path