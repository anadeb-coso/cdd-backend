from django.utils.translation import gettext_lazy
import os
from sys import platform
from datetime import datetime
import pandas as pd
import itertools
import json
from django.conf import settings

from no_sql_client import NoSQLClient
from dashboard.administrative_levels.functions import get_cascade_villages_by_administrative_level_id
from authentication.models import Facilitator
from dashboard.facilitators.functions import get_cvds
from cdd.functions import datetime_complet_str
from administrativelevels import models as administrativelevels_models
from dashboard.reports.constants import IGNORES
from cdd.my_librairies.functions import strip_accents
from dashboard.utils_functions import get_facilitators_on_adlor_dbs_name
from process_manager.models import Project, AggregatedStatus, AggregatedStatusFacilitator
from subprojects.models import Project as MisProject
from cdd.call_objects_from_other_db import mis_objects_call
from assignments.models import AssignAdministrativeLevelToFacilitator
from dashboard.facilitators.repository.facilitator_criteria import FacilitatorCriteria
from dashboard.facilitators.repository.db_facilitator_repository import FacilitatorRepository


def get_datas_dict(reponses_datas, key, level: int = 1):
    for i in range(len(reponses_datas)):
        elt = reponses_datas[i]
        if level == 1:
            for k,v in elt.items():
                if k == key:
                    return v


def _get_ids_list(elt: str):
    if type(elt) is str:
        return [_elt for _elt in elt.split(',') if _elt and _elt not in (None, 'None', 'null', 'undefined')]
    return []

def get_value(dictionnay: dict, keys: list):
    for key in keys:
        if key in dictionnay:
            return dictionnay[key]


def get_facilitator_status_excel_csv_under_file_excel_or_csv(request=None, facilitator_db_name=None):
    if not request:
        from django import http
        request = http.HttpRequest()
        request.session = http.QueryDict(mutable=True)

    # nsc = NoSQLClient()

    # ids_region = _get_ids_list(request.GET.get('id_region'))
    # ids_prefecture = _get_ids_list(request.GET.get('id_prefecture'))
    # ids_commune = _get_ids_list(request.GET.get('id_commune'))
    # ids_canton = _get_ids_list(request.GET.get('id_canton'))
    # ids_village = _get_ids_list(request.GET.get('id_village'))
    # type_field = request.GET.get('type_field', 'all')
    # val_date_start = request.GET.get('val_date_start')
    # val_date_end = request.GET.get('val_date_end')
    # file_type = request.GET.get('file_type', 'excel')
    # id_in_details = request.GET.get("id_in_details")
    # ids_administrative_level = _get_ids_list(request.GET.get('administrative_level_id'))
    # ids_administrative_level = list(set(ids_administrative_level+ids_region+ids_prefecture+ids_commune+ids_canton+ids_village))

    # facilitators = []
    # liste_villages = None

    # if ids_administrative_level:
    #     fs, liste_villages = get_facilitators_on_adlor_dbs_name(
    #         request.session.get('project_name') or "COSO",
    #         request.session.get('project_id') or 4,
    #         ids_administrative_level,
    #         [facilitator_db_name] if facilitator_db_name else []
    #     )
    # else:
    #     is_training = bool(request.GET.get('is_training', "False") == "True")
    #     is_develop = bool(request.GET.get('is_develop', "False") == "True")
    #     if facilitator_db_name:
    #         fs = Facilitator.objects.filter(develop_mode=is_develop, training_mode=is_training, no_sql_db_name=facilitator_db_name)
    #     else:
    #         fs = Facilitator.objects.filter(develop_mode=is_develop, training_mode=is_training, projects__in=[request.session.get('project_id') or 4])
    
    # eadls = nsc.get_db('eadls')
    # docs_eadls = eadls.all_docs(include_docs=True)['rows']
    # docs_eadls_dict = {doc.get('doc').get('representative').get('email'): list(itertools.chain(*[[str(v['id']) for v in ad['villages']] for ad in doc.get('doc')['administrative_regions_objects']])) for doc in docs_eadls if doc.get('doc') and doc.get('doc').get('type') == 'adl' and doc.get('doc').get('representative') and doc.get('doc').get('administrative_regions_objects')}

    # liste_villages = [int(v["administrative_id"]) for v in liste_villages] if liste_villages else []
    
    # projects_cdd = Project.objects.get(id=request.session.get('project_id') or 4).build_the_tree_structure()
    # dict_projets_cdd = {}
    # for p_cdd in projects_cdd:
    #     p = mis_objects_call.get_object(MisProject, name=p_cdd.name)
    #     adls = p.administrative_levels.filter(id__in=liste_villages) if liste_villages else p.administrative_levels.all()
    #     adl_headquarters_villages = set(adl.cvd.headquarters_village.id for adl in adls if adl.cvd and adl.cvd.headquarters_village)
    #     adl_villages_ids = set(adl.id for adl in adls if adl.cvd)
    #     cvds_query_results = administrativelevels_models.CVD.objects.using('mis').filter(headquarters_village_id__in=adl_headquarters_villages)

    #     cvds_dict_results = {}
    #     for cvd_obj in cvds_query_results:
    #         dict_villages = {str(v_c.id): v_c.name for v_c in cvd_obj.get_villages()}
    #         no_sql_db_name = Facilitator.objects.get(id=mis_objects_call.filter_objects(
    #             AssignAdministrativeLevelToFacilitator, 
    #             project_id=p.id,
    #             administrative_level_id=cvd_obj.headquarters_village_id
    #         ).last().facilitator_id).no_sql_db_name
    #         cvds_dict_results[str(cvd_obj.headquarters_village_id)] = {
    #             'cvd_id': str(cvd_obj.id),
    #             'villages_ids': list(dict_villages.keys()),
    #             'villages_names': list(dict_villages.values()),
    #             'headquarters_village_id': cvd_obj.headquarters_village_id,
    #             'headquarters_village_name': cvd_obj.headquarters_village.name,
    #             'no_sql_db_name': no_sql_db_name
    #         }

    #     dict_projets_cdd[p_cdd.couch_id] = {
    #         'project_mis_id': p.id,
    #         'project_mis_name': p.name,
    #         'project_cdd_id': p_cdd.id,
    #         'project_cdd_name': p_cdd.name,
    #         'adls': adls,
    #         'adl_headquarters_villages': adl_headquarters_villages,
    #         'adl_villages_ids': adl_villages_ids,
    #         'cvds_query_results': cvds_query_results,
    #         'cvds_dict_results': cvds_dict_results
    #     }

    
    # all_data = {}
    # for f in fs.order_by("name", "username"):
    #     dict_administrative_levels_with_infos = {}
    #     already_count_facilitator = False
    #     facilitator_db = nsc.get_db(f.no_sql_db_name)
        
    #     query_result_docs = facilitator_db.get_query_result({
    #         "type": {"$in": ["facilitator", "task"]},
    #         # "cycle_id": cycle_id,
    #         # "project_id": request.session.get('project_couch_id')
    #     }, limit=10000000)[:]
        
    #     f_doc = None
    #     cvds = []
    #     tasks_by_villages_id = {}

    #     for doc in query_result_docs:
    #         if doc.get('type') == "task":
    #             if doc['administrative_level_id'] in tasks_by_villages_id:
    #                 tasks_by_villages_id[doc['administrative_level_id']].append(doc)
    #             else:
    #                 tasks_by_villages_id[doc['administrative_level_id']] = [doc]
    #         else:
    #             f_doc = doc
    #             cvds = get_cvds(None, None, f_doc)
    #             f_doc['name_with_sex'] = f"{f_doc['sex']} {f_doc['name']}" if f_doc.get('sex') else f_doc['name']
    #             f_doc['sex'] =  'I' if not f_doc.get('sex') else "F" if f_doc.get('sex') == "Mme" else "M"

    #     all_data[f.no_sql_db_name] = {'tasks': tasks_by_villages_id, 'facilitator': f_doc, 'cvds': cvds}
    
    # errors_adm = []
    
    # for f in fs.order_by("name", "username"):
    #     data = all_data[f.no_sql_db_name]
    #     tasks_by_villages_id = data['tasks']
    #     f_doc = data['facilitator']
    #     cvds = data['cvds']

    #     if f_doc:
    #         dict_administrative_levels_with_infos = {
    #             "total_tasks_completed": 0,
    #             "total_tasks_uncompleted": 0,
    #             "total_tasks": 0,
    #             "total_tasks_validated": 0,
    #             "total_tasks_invalidated": 0,
    #             "total_tasks_invalidated_review": 0,
    #             "total_tasks_invalidated_unreview": 0,
    #             "total_tasks_waiting_validation": 0,
    #             "last_activity_date" : "0000-00-00 00:00:00",
    #             "percent": "",
    #             "facilitator": {'name': f_doc['name'], 'phone': f_doc['phone'], 'sex': f_doc['sex'], 'email': f_doc['email']}
    #         }
    #         for projet_couch_id, project_details in dict_projets_cdd.items():
    #             adl_headquarters_villages = project_details['adl_headquarters_villages']
    #             cvds_dict_results = project_details['cvds_dict_results']

    #             dict_administrative_levels_with_infos[projet_couch_id] = {
    #                 "total_tasks_completed": 0,
    #                 "total_tasks_uncompleted": 0,
    #                 "total_tasks": 0,
    #                 "total_tasks_validated": 0,
    #                 "total_tasks_invalidated": 0,
    #                 "total_tasks_invalidated_review": 0,
    #                 "total_tasks_invalidated_unreview": 0,
    #                 "total_tasks_waiting_validation": 0,
    #                 "last_activity_date" : "0000-00-00 00:00:00",
    #                 "project_name": project_details["project_mis_name"],
    #                 "facilitator": {'name': f_doc['name'], 'phone': f_doc['phone'], 'sex': f_doc['sex'], 'email': f_doc['email']},
    #                 "percent": ""
    #             }

    #             administrative_levels_ids = [str(adl['id']) for adl in f.administrative_levels if adl['project_id'] == projet_couch_id and adl.get('is_headquarters_village')] if f.administrative_levels else []
    #             administrative_levels_ids_stabilize = docs_eadls_dict.get(f.email)
    #             administrative_levels_ids_stabilize = [ad_id for ad_id in administrative_levels_ids_stabilize if int(ad_id) in adl_headquarters_villages] if administrative_levels_ids_stabilize else []
    #             # _administrative_levels_ids = list(set(administrative_levels_ids + administrative_levels_ids_stabilize))
    #             print("administrative_levels_ids")
    #             print(administrative_levels_ids)
    #             print("administrative_levels_ids_stabilize")
    #             print(administrative_levels_ids_stabilize)

    #             for _type_adm_, _adm_ids in {'affected' : administrative_levels_ids, 'stabilized': administrative_levels_ids_stabilize}.items():
    #                 dict_administrative_levels_with_infos[projet_couch_id][_type_adm_] = {
    #                     "total_tasks_completed": 0,
    #                     "total_tasks_uncompleted": 0,
    #                     "total_tasks": 0,
    #                     "total_tasks_validated": 0,
    #                     "total_tasks_invalidated": 0,
    #                     "total_tasks_invalidated_review": 0,
    #                     "total_tasks_invalidated_unreview": 0,
    #                     "total_tasks_waiting_validation": 0,
    #                     "last_activity_date" : "0000-00-00 00:00:00",
    #                     "project_name": project_details["project_mis_name"],
    #                     "facilitator": {'name': f_doc['name'], 'phone': f_doc['phone'], 'sex': f_doc['sex'], 'email': f_doc['email']},
    #                     "type": _type_adm_,
    #                     "percent": ""
    #                 }
    #                 for _adm_id in _adm_ids:
    #                     headquarters_village_detail = cvds_dict_results[str(_adm_id)]
    #                     if headquarters_village_detail:
    #                         headquarters_village_name = headquarters_village_detail["headquarters_village_name"]
    #                         headquarters_village_tasks = all_data[headquarters_village_detail['no_sql_db_name']]['tasks'][str(_adm_id)]

    #                         dict_administrative_levels_with_infos[projet_couch_id][_type_adm_][headquarters_village_name] = {
    #                             "total_tasks_completed": 0,
    #                             "total_tasks_uncompleted": 0,
    #                             "total_tasks": 0,
    #                             "total_tasks_validated": 0,
    #                             "total_tasks_invalidated": 0,
    #                             "total_tasks_invalidated_review": 0,
    #                             "total_tasks_invalidated_unreview": 0,
    #                             "total_tasks_waiting_validation": 0,
    #                             "last_activity_date" : "0000-00-00 00:00:00",
    #                             "headquarters_village_name": headquarters_village_name,
    #                             "project_name": project_details["project_mis_name"],
    #                             "facilitator": {'name': f_doc['name'], 'phone': f_doc['phone'], 'sex': f_doc['sex'], 'email': f_doc['email']},
    #                             "type": _type_adm_,
    #                             "percent": ""
    #                         }
                            
    #                         for _task in headquarters_village_tasks:
    #                             last_updated = datetime_complet_str(_task.get('last_updated'))
    #                             if last_updated and dict_administrative_levels_with_infos[projet_couch_id][_type_adm_][headquarters_village_name]["last_activity_date"] < last_updated:
    #                                 dict_administrative_levels_with_infos[projet_couch_id][_type_adm_][headquarters_village_name]["last_activity_date"] = last_updated
    #                             if last_updated and dict_administrative_levels_with_infos[projet_couch_id][_type_adm_]["last_activity_date"] < last_updated:
    #                                 dict_administrative_levels_with_infos[projet_couch_id][_type_adm_]["last_activity_date"] = last_updated
    #                             if last_updated and dict_administrative_levels_with_infos[projet_couch_id]["last_activity_date"] < last_updated:
    #                                 dict_administrative_levels_with_infos[projet_couch_id]["last_activity_date"] = last_updated
    #                             if last_updated and dict_administrative_levels_with_infos["last_activity_date"] < last_updated:
    #                                 dict_administrative_levels_with_infos["last_activity_date"] = last_updated

    #                             if _task.get("completed"):
    #                                 dict_administrative_levels_with_infos[projet_couch_id][_type_adm_][headquarters_village_name]["total_tasks_completed"] += 1
    #                                 dict_administrative_levels_with_infos[projet_couch_id][_type_adm_]["total_tasks_completed"] += 1
    #                                 dict_administrative_levels_with_infos[projet_couch_id]["total_tasks_completed"] += 1
    #                                 dict_administrative_levels_with_infos["total_tasks_completed"] += 1
    #                             else:
    #                                 dict_administrative_levels_with_infos[projet_couch_id][_type_adm_][headquarters_village_name]["total_tasks_uncompleted"] += 1
    #                                 dict_administrative_levels_with_infos[projet_couch_id][_type_adm_]["total_tasks_uncompleted"] += 1
    #                                 dict_administrative_levels_with_infos[projet_couch_id]["total_tasks_uncompleted"] += 1
    #                                 dict_administrative_levels_with_infos["total_tasks_uncompleted"] += 1
                                
    #                             if _task.get("validated"):
    #                                 dict_administrative_levels_with_infos[projet_couch_id][_type_adm_][headquarters_village_name]["total_tasks_validated"] += 1
    #                                 dict_administrative_levels_with_infos[projet_couch_id][_type_adm_]["total_tasks_validated"] += 1
    #                                 dict_administrative_levels_with_infos[projet_couch_id]["total_tasks_validated"] += 1
    #                                 dict_administrative_levels_with_infos["total_tasks_validated"] += 1
    #                             elif _task.get("validated") == False:
    #                                 dict_administrative_levels_with_infos[projet_couch_id][_type_adm_][headquarters_village_name]["total_tasks_invalidated"] += 1
    #                                 dict_administrative_levels_with_infos[projet_couch_id][_type_adm_]["total_tasks_invalidated"] += 1
    #                                 dict_administrative_levels_with_infos[projet_couch_id]["total_tasks_invalidated"] += 1
    #                                 dict_administrative_levels_with_infos["total_tasks_invalidated"] += 1

    #                                 updated_after_invalidation = _task.get("updated_after_invalidation")
    #                                 if not updated_after_invalidation:
    #                                     action_by = _task.get("action_by", {})
    #                                     if type(action_by) is list:
    #                                         if action_by:
    #                                             action_by = action_by[0] or {}
    #                                         else:
    #                                             action_by = {}
    #                                     action_by_action_date = action_by.get('action_date') if action_by.get("type") == "Invalidated" else None
    #                                     if action_by_action_date and _task.get("last_updated"):
    #                                         action_by_action_date = datetime_complet_str(action_by_action_date)
    #                                         action_last_updated = datetime_complet_str(_task.get("last_updated"))
    #                                         if action_last_updated and action_by_action_date < action_last_updated:
    #                                             updated_after_invalidation = True
    #                                 if updated_after_invalidation:
    #                                     dict_administrative_levels_with_infos[projet_couch_id][_type_adm_][headquarters_village_name]["total_tasks_invalidated_review"] += 1
    #                                     dict_administrative_levels_with_infos[projet_couch_id][_type_adm_]["total_tasks_invalidated_review"] += 1
    #                                     dict_administrative_levels_with_infos[projet_couch_id]["total_tasks_invalidated_review"] += 1
    #                                     dict_administrative_levels_with_infos["total_tasks_invalidated_review"] += 1
    #                                 else:
    #                                     dict_administrative_levels_with_infos[projet_couch_id][_type_adm_][headquarters_village_name]["total_tasks_invalidated_unreview"] += 1
    #                                     dict_administrative_levels_with_infos[projet_couch_id][_type_adm_]["total_tasks_invalidated_unreview"] += 1
    #                                     dict_administrative_levels_with_infos[projet_couch_id]["total_tasks_invalidated_unreview"] += 1
    #                                     dict_administrative_levels_with_infos["total_tasks_invalidated_unreview"] += 1
                                    
    #                             elif _task.get("completed") and _task.get("validated") == None:
    #                                 dict_administrative_levels_with_infos[projet_couch_id][_type_adm_][headquarters_village_name]["total_tasks_waiting_validation"] += 1
    #                                 dict_administrative_levels_with_infos[projet_couch_id][_type_adm_]["total_tasks_waiting_validation"] += 1
    #                                 dict_administrative_levels_with_infos[projet_couch_id]["total_tasks_waiting_validation"] += 1
    #                                 dict_administrative_levels_with_infos["total_tasks_waiting_validation"] += 1
                                
                                    
                                
    #                             dict_administrative_levels_with_infos[projet_couch_id][_type_adm_][headquarters_village_name]["total_tasks"] += 1
    #                             dict_administrative_levels_with_infos[projet_couch_id][_type_adm_]["total_tasks"] += 1
    #                             dict_administrative_levels_with_infos[projet_couch_id]["total_tasks"] += 1
    #                             dict_administrative_levels_with_infos["total_tasks"] += 1

    #                         dict_administrative_levels_with_infos[projet_couch_id][_type_adm_][headquarters_village_name]["percent"] = float("%.2f" % (((dict_administrative_levels_with_infos[projet_couch_id][_type_adm_][headquarters_village_name]["total_tasks_completed"]/dict_administrative_levels_with_infos[projet_couch_id][_type_adm_][headquarters_village_name]["total_tasks"])*100) if dict_administrative_levels_with_infos[projet_couch_id][_type_adm_][headquarters_village_name]["total_tasks"] else 0))
    #                     else:
    #                         errors_adm.append((_adm_id, {'name': f_doc['name'], 'phone': f_doc['phone'], 'sex': f_doc['sex'], 'email': f_doc['email']}))
    #                 dict_administrative_levels_with_infos[projet_couch_id][_type_adm_]["percent"] = float("%.2f" % (((dict_administrative_levels_with_infos[projet_couch_id][_type_adm_]["total_tasks_completed"]/dict_administrative_levels_with_infos[projet_couch_id][_type_adm_]["total_tasks"])*100) if dict_administrative_levels_with_infos[projet_couch_id][_type_adm_]["total_tasks"] else 0))
    #             dict_administrative_levels_with_infos[projet_couch_id]["percent"] = float("%.2f" % (((dict_administrative_levels_with_infos[projet_couch_id]["total_tasks_completed"]/dict_administrative_levels_with_infos[projet_couch_id]["total_tasks"])*100) if dict_administrative_levels_with_infos[projet_couch_id]["total_tasks"] else 0))
    #         dict_administrative_levels_with_infos["percent"] = float("%.2f" % (((dict_administrative_levels_with_infos["total_tasks_completed"]/dict_administrative_levels_with_infos["total_tasks"])*100) if dict_administrative_levels_with_infos["total_tasks"] else 0))
    # #         for cvd in cvds:
    # #             administrative_level_cvd = cvd
    # #             administrative_level_cvd_village = cvd.get('village')
    # #             if administrative_level_cvd_village:
    # #                 dict_cvd = cvds_dict_results.get(administrative_level_cvd_village["id"])

    # #                 if dict_cvd and not already_count_facilitator and (
    # #                     not ids_administrative_level or (ids_administrative_level and any([v_id for v_id in liste_villages for v_c_id in dict_cvd['villages_ids'] if v_id == v_c_id]))
    # #                 ):

    # #                     total_tasks_completed = 0
    # #                     total_tasks_uncompleted = 0
    # #                     total_tasks = 0
    # #                     total_tasks_completed_inter_date = 0
    # #                     total_tasks_uncompleted_inter_date = 0
    # #                     total_tasks_inter_date = 0
    # #                     last_activity_date = "0000-00-00 00:00:00"

    # #                     cvd_tasks = get_value(tasks_by_villages_id, [str(administrative_level_cvd_village["id"])] + dict_cvd['villages_ids'])
    # #                     for _ in cvd_tasks:
    # #                         last_updated = datetime_complet_str(_.get('last_updated'))
    # #                         if last_updated and last_activity_date < last_updated:
    # #                             last_activity_date = last_updated


    # #                         if _.get("completed"):
    # #                             if last_updated and val_date_start <= last_updated.split(' ')[0] <= val_date_end:
    # #                                 total_tasks_completed_inter_date += 1
    # #                             total_tasks_completed += 1
    # #                         else:
    # #                             if last_updated and val_date_start <= last_updated.split(' ')[0] <= val_date_end:
    # #                                 total_tasks_uncompleted_inter_date += 1
    # #                             total_tasks_uncompleted += 1
    # #                         if last_updated and val_date_start <= last_updated.split(' ')[0] <= val_date_end:
    # #                                 total_tasks_inter_date += 1
    # #                         total_tasks += 1


    # #                         if dict_administrative_levels_with_infos.get(administrative_level_cvd.get("name")):
    # #                             if _.get("completed"):
    # #                                 if last_updated and val_date_start <= last_updated.split(' ')[0] <= val_date_end:
    # #                                     dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks_completed_inter_date'] += 1
    # #                                 dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks_completed'] += 1
    # #                             else:
    # #                                 if last_updated and val_date_start <= last_updated.split(' ')[0] <= val_date_end:
    # #                                     dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks_uncompleted_inter_date'] += 1
    # #                                 dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks_uncompleted'] += 1
    # #                             if last_updated and val_date_start <= last_updated.split(' ')[0] <= val_date_end:
    # #                                 dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks_inter_date'] += 1
    # #                             dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks'] += 1
    # #                         else:
    # #                             if _.get("completed"):
    # #                                 dict_administrative_levels_with_infos[administrative_level_cvd.get("name")] = {
    # #                                     'total_tasks_completed': 1,
    # #                                     'total_tasks_uncompleted': 0,
    # #                                     'total_tasks_completed_inter_date': 1 if last_updated and val_date_start <= last_updated.split(' ')[0] <= val_date_end else 0,
    # #                                     'total_tasks_uncompleted_inter_date': 0
    # #                                 }
    # #                             else:
    # #                                 dict_administrative_levels_with_infos[administrative_level_cvd.get("name")] = {
    # #                                     'total_tasks_completed': 0,
    # #                                     'total_tasks_uncompleted': 1,
    # #                                     'total_tasks_completed_inter_date': 0,
    # #                                     'total_tasks_uncompleted_inter_date': 1 if last_updated and val_date_start <= last_updated.split(' ')[0] <= val_date_end else 0
    # #                                 }
                                
    # #                             dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks_inter_date'] = 1 if last_updated and val_date_start <= last_updated.split(' ')[0] <= val_date_end else 0
    # #                             dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks'] = 1
    # #                         dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['cvd'] = administrative_level_cvd

    # #                     nbr_villages = 0
    # #                     for key, value in dict_administrative_levels_with_infos.items():
    # #                         dict_administrative_levels_with_infos[key]["percentage_tasks_completed"] = ((value["total_tasks_completed"]/value["total_tasks"])*100) if value["total_tasks"] else 0
    # #                         dict_administrative_levels_with_infos[key]["percentage_tasks_completed_inter_date"] = ((value["total_tasks_completed_inter_date"]/value["total_tasks"])*100) if value["total_tasks"] else 0
    # #                         del dict_administrative_levels_with_infos[key]["total_tasks"]

    # #                         nbr_villages += len(dict_administrative_levels_with_infos[key]['cvd']['villages'])

    # #                     percent = float("%.2f" % (((total_tasks_completed/total_tasks)*100) if total_tasks else 0))
    # #                     percent_inter_date = float("%.2f" % (((total_tasks_completed_inter_date/total_tasks)*100) if total_tasks else 0))
    # #                     if last_activity_date == "0000-00-00 00:00:00":
    # #                         last_activity_date = None
    # #                     else:
    # #                         last_activity_date = datetime.strptime(last_activity_date, '%Y-%m-%d %H:%M:%S')

    # #                     facilitators.append({
    # #                         'facilitator': f_doc, "name_with_sex": name_with_sex, "name": name, "sex": sex,
    # #                         "username": f.username, "phone": phone, 
    # #                         "total_tasks_completed": total_tasks_completed,
    # #                         "total_tasks_uncompleted": total_tasks_uncompleted,
    # #                         "total_tasks": total_tasks,
    # #                         "total_tasks_completed_inter_date": total_tasks_completed_inter_date,
    # #                         "total_tasks_uncompleted_inter_date": total_tasks_uncompleted_inter_date,
    # #                         "total_tasks_inter_date": total_tasks_inter_date,
    # #                         'last_activity_date': last_activity_date, "percent": percent, 
    # #                         "percent_inter_date": percent_inter_date, 
    # #                         "dict_administrative_levels_with_infos": dict_administrative_levels_with_infos,
    # #                         "nbr_villages": nbr_villages
    # #                     })
    # #                     already_count_facilitator = True


    # # _date = " " + datetime.strptime(val_date_start, '%Y-%m-%d').date().__str__() + " " + gettext_lazy('to').__str__() + " " + datetime.strptime(val_date_end, '%Y-%m-%d').date().__str__()
    # # d_cols = [
    # #     (gettext_lazy('N°').__str__(), gettext_lazy('N°').__str__()),
    # #     (gettext_lazy('Name').__str__(), gettext_lazy('Name').__str__()),
    # #     (gettext_lazy('Sex').__str__(), gettext_lazy('Sex').__str__()),
    # #     (gettext_lazy('Phone').__str__(), gettext_lazy('Phone').__str__()),
    # #     (gettext_lazy('CVD').__str__(), gettext_lazy('Nbr').__str__()),
    # #     (gettext_lazy('CVD').__str__(), gettext_lazy('ID CVD').__str__()),
    # #     (gettext_lazy('CVD').__str__(), gettext_lazy('CVD').__str__()),
    # #     (gettext_lazy('Village(s)').__str__(), gettext_lazy('Nbr').__str__()),
    # #     (gettext_lazy('Village(s)').__str__(), gettext_lazy('Village(s)').__str__()),
    # #     (gettext_lazy('Period').__str__()+_date, gettext_lazy('Completed').__str__()),
    # #     (gettext_lazy('Period').__str__()+_date, gettext_lazy('Uncompleted').__str__()),
    # #     (gettext_lazy('Period').__str__()+_date, gettext_lazy('Total').__str__()),
    # #     (gettext_lazy('Period').__str__()+_date, gettext_lazy('Percentage').__str__()),
    # #     (gettext_lazy('All').__str__(), gettext_lazy('Completed').__str__()),
    # #     (gettext_lazy('All').__str__(), gettext_lazy('Uncompleted').__str__()),
    # #     (gettext_lazy('All').__str__(), gettext_lazy('Total').__str__()),
    # #     (gettext_lazy('All').__str__(), gettext_lazy('Percentage').__str__())
    # # ]
    
    # # cols = pd.MultiIndex.from_tuples(d_cols)
    # # datas = {}
    # # for col in d_cols:
    # #     datas[col] = {}
    # # index_f = 0
    # # for facilitator in facilitators:
        
    # #     _cvds = ""
    # #     _villages = ""
    # #     count_c = 1
    # #     for k_c, v_c in facilitator['dict_administrative_levels_with_infos'].items():
    # #         count_v = 1
    # #         try:
    # #             cvd_obj = administrativelevels_models.CVD.objects.using('mis').get(id=int(v_c['cvd']['sql_id']))
    # #             _cvds += f'{count_c}-/ {cvd_obj.get_name()}\n'
    # #             for _v in cvd_obj.get_villages():
    # #                 _villages += f'{count_c}.{count_v}-/ {_v.name}\n'
    # #                 count_v += 1
                
    # #             if id_in_details == "0":
    # #                 pass
    # #             else:
    # #                 datas[(gettext_lazy('N°').__str__(), gettext_lazy('N°').__str__())][index_f] = index_f + 1
    # #                 datas[(gettext_lazy('Name').__str__(), gettext_lazy('Name').__str__())][index_f] = facilitator['name']
    # #                 datas[(gettext_lazy('Sex').__str__(), gettext_lazy('Sex').__str__())][index_f] = facilitator['sex']
    # #                 datas[(gettext_lazy('Phone').__str__(), gettext_lazy('Phone').__str__())][index_f] = facilitator['phone']
    # #                 datas[(gettext_lazy('CVD').__str__(), gettext_lazy('Nbr').__str__())][index_f] = len(facilitator['dict_administrative_levels_with_infos'])

    # #                 datas[(gettext_lazy('CVD').__str__(), gettext_lazy('ID CVD').__str__())][index_f] = int(v_c['cvd']['sql_id'])
    # #                 datas[(gettext_lazy('CVD').__str__(), gettext_lazy('CVD').__str__())][index_f] = _cvds
    # #                 datas[(gettext_lazy('Village(s)').__str__(), gettext_lazy('Nbr').__str__())][index_f] = count_v - 1
    # #                 datas[(gettext_lazy('Village(s)').__str__(), gettext_lazy('Village(s)').__str__())][index_f] = _villages
                    
                    
    # #                 datas[(gettext_lazy('Period').__str__()+_date, gettext_lazy('Completed').__str__())][index_f] = v_c['total_tasks_completed_inter_date']
    # #                 datas[(gettext_lazy('Period').__str__()+_date, gettext_lazy('Uncompleted').__str__())][index_f] = v_c['total_tasks_uncompleted_inter_date']
    # #                 datas[(gettext_lazy('Period').__str__()+_date, gettext_lazy('Total').__str__())][index_f] = v_c['total_tasks_inter_date']
    # #                 datas[(gettext_lazy('Period').__str__()+_date, gettext_lazy('Percentage').__str__())][index_f] = v_c['percentage_tasks_completed_inter_date']
    # #                 datas[(gettext_lazy('All').__str__(), gettext_lazy('Completed').__str__())][index_f] = v_c['total_tasks_completed']
    # #                 datas[(gettext_lazy('All').__str__(), gettext_lazy('Uncompleted').__str__())][index_f] = v_c['total_tasks_uncompleted']
    # #                 datas[(gettext_lazy('All').__str__(), gettext_lazy('Total').__str__())][index_f] = v_c['total_tasks']
    # #                 datas[(gettext_lazy('All').__str__(), gettext_lazy('Percentage').__str__())][index_f] = v_c['percentage_tasks_completed']

    # #                 _cvds = ''
    # #                 _villages = ''
    # #                 index_f += 1
                


    # #         except Exception as exc:
    # #             pass
    # #         count_c += 1
        
    # #     if id_in_details == "0":
    # #         datas[(gettext_lazy('N°').__str__(), gettext_lazy('N°').__str__())][index_f] = index_f + 1
    # #         datas[(gettext_lazy('Name').__str__(), gettext_lazy('Name').__str__())][index_f] = facilitator['name']
    # #         datas[(gettext_lazy('Sex').__str__(), gettext_lazy('Sex').__str__())][index_f] = facilitator['sex']
    # #         datas[(gettext_lazy('Phone').__str__(), gettext_lazy('Phone').__str__())][index_f] = facilitator['phone']

    # #         datas[(gettext_lazy('CVD').__str__(), gettext_lazy('Nbr').__str__())][index_f] = len(facilitator['dict_administrative_levels_with_infos'])

    # #         datas[(gettext_lazy('CVD').__str__(), gettext_lazy('CVD').__str__())][index_f] = _cvds

    # #         datas[(gettext_lazy('Village(s)').__str__(), gettext_lazy('Nbr').__str__())][index_f] = facilitator['nbr_villages']
    # #         datas[(gettext_lazy('Village(s)').__str__(), gettext_lazy('Village(s)').__str__())][index_f] = _villages
            
    # #         datas[(gettext_lazy('Period').__str__()+_date, gettext_lazy('Completed').__str__())][index_f] = facilitator['total_tasks_completed_inter_date']
    # #         datas[(gettext_lazy('Period').__str__()+_date, gettext_lazy('Uncompleted').__str__())][index_f] = facilitator['total_tasks_uncompleted_inter_date']
    # #         datas[(gettext_lazy('Period').__str__()+_date, gettext_lazy('Total').__str__())][index_f] = facilitator['total_tasks_inter_date']
    # #         datas[(gettext_lazy('Period').__str__()+_date, gettext_lazy('Percentage').__str__())][index_f] = facilitator['percent_inter_date']
    # #         datas[(gettext_lazy('All').__str__(), gettext_lazy('Completed').__str__())][index_f] = facilitator['total_tasks_completed']
    # #         datas[(gettext_lazy('All').__str__(), gettext_lazy('Uncompleted').__str__())][index_f] = facilitator['total_tasks_uncompleted']
    # #         datas[(gettext_lazy('All').__str__(), gettext_lazy('Total').__str__())][index_f] = facilitator['total_tasks']
    # #         datas[(gettext_lazy('All').__str__(), gettext_lazy('Percentage').__str__())][index_f] = facilitator['percent']
    # #         index_f += 1


    # # if not os.path.exists("media/"+file_type+"/reports/excel_csv"):
    # #     os.makedirs("media/"+file_type+"/reports/excel_csv")

    # # file_name = "reports_excel_csv_" + type_field.lower() + "_" + (("reports_excel_csv_".lower() + "_") if "reports_excel_csv_" else "")

    # # if file_type == "csv":
    # #     file_path = file_type+"/reports/excel_csv/" + file_name + str(datetime.today().replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_") +".csv"
    # #     pd.DataFrame(datas, columns=cols).to_csv("media/"+file_path)
    # # else:
    # #     file_path = file_type+"/reports/excel_csv/" + file_name + str(datetime.today().replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_") +".xlsx"
    # #     pd.DataFrame(datas, columns=cols).to_excel("media/"+file_path)

    # # if platform == "win32":
    # #     # windows
    # #     return file_path.replace("/", "\\\\")
    # # else:
    # #     return file_path
    # print("\n\n==========End")

    # file_path = os.path.join(settings.MEDIA_ROOT, f'dict_administrative_levels_with_infos_{datetime.today().strftime().replace("-", "").replace(":", "").replace(" ", "_")}.json')
    # with open(file_path, 'w', encoding='utf-8') as f:
    #     json.dump(dict_administrative_levels_with_infos, f, ensure_ascii=False, indent=4)
    # return None











    id_region = request.GET.get('id_region')
    id_prefecture = request.GET.get('id_prefecture')
    id_commune = request.GET.get('id_commune')
    id_canton = request.GET.get('id_canton')
    id_village = request.GET.get('id_village')
    type_field = request.GET.get('type_field')
    type_facilitator = request.GET.get('type_facilitator')
    type_of_facilitator_list = request.GET.get('type_of_facilitator_list', 'community_facilitator')
    _id = 0
    facilitators = []

    project_mis = mis_objects_call.filter_objects(MisProject, name=(request.session.get('project_name') or "COSO")).first()
    project_mis_id = project_mis.id if project_mis else 1
    liste_villages = []

    if (id_region or id_prefecture or id_commune or id_canton or id_village) and type_field:
        criteria = FacilitatorCriteria()

        _type = None
        if id_region and type_field == "region":
            _type = "region"
            _id = id_region
        elif id_prefecture and type_field == "prefecture":
            _type = "prefecture"
            _id = id_prefecture
        elif id_commune and type_field == "commune":
            _type = "commune"
            _id = id_commune
        elif id_canton and type_field == "canton":
            _type = "canton"
            _id = id_canton
        elif id_village and type_field == "village":
            _type = "village"
            _id = id_village

        liste_villages = get_cascade_villages_by_administrative_level_id(_id)
        liste_villages = [int(v['administrative_id']) for v in liste_villages]

        if type(_id) is not list:
            assign_facilitators_id_list = AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(
                administrative_level_id__in=liste_villages,
                project_id=project_mis_id,
                activated=True
            ).values_list('facilitator_id', flat=True)
            criteria = FacilitatorCriteria(
                id__in=list(set([int(facilitator_id) for facilitator_id in assign_facilitators_id_list])),
                develop_mode=False,
                training_mode=False,
                active=(False if type_facilitator=='inactive' else True),
                projects__id=[request.session.get('project_id') or 4],
                facilitator_type=type_of_facilitator_list
            )

        else:
            assign_facilitators_id_list = AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(
                project_id=project_mis_id,
                activated=True
            ).values_list('facilitator_id', flat=True)
            criteria = FacilitatorCriteria(
                id__in=list(set([int(facilitator_id) for facilitator_id in assign_facilitators_id_list])),
                develop_mode=False,
                training_mode=False,
                active=(False if type_facilitator=='inactive' else True),
                projects__id=[(request.session.get('project_id') or 4)],
                facilitator_type=type_of_facilitator_list
            )

    else:
        assign_facilitators_id_list = AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(
            project_id=project_mis_id,
            activated=True
        ).values_list('facilitator_id', flat=True)
        is_training = bool(request.GET.get('is_training', "False") == "True")
        is_develop = bool(request.GET.get('is_develop', "False") == "True")
        criteria = FacilitatorCriteria(
            id__in=list(set([int(facilitator_id) for facilitator_id in assign_facilitators_id_list])),
            develop_mode=is_develop,
            training_mode=is_training,
            active=(False if type_facilitator=='inactive' else True),
            projects__id=[request.session.get('project_id') or 4],
            facilitator_type=type_of_facilitator_list
        )


    # Liste des facilitateurs à retourner
    _facilitators = []

    # Récupérer tous les facilitateurs en une seule requête
    facilitators = FacilitatorRepository().find_by_criteria(criteria=criteria)
    agg_s_fs = AggregatedStatusFacilitator.objects.filter(facilitator__in=facilitators, project_id=request.session.get('project_id') or 4, cycle_id=request.session.get('cycle_id') or 1)
    dict_agg_s_fs = {str(ag.facilitator.id): ag for ag in agg_s_fs}
    havent_update = len([ag for ag in agg_s_fs[:3] if not ag.new_update_exists]) == 3
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
                f.total_tasks_invalidated_unreview_current_project = _f.total_tasks_invalidated_unreview_current_project
                f.total_tasks_waiting_validation_current_project = _f.total_tasks_waiting_validation_current_project

                f.total_tasks_validated_stabilized = _f.total_tasks_validated_stabilized
                f.total_tasks_invalidated_stabilized = _f.total_tasks_invalidated_stabilized
                f.total_tasks_invalidated_review_stabilized = _f.total_tasks_invalidated_review_stabilized
                f.total_tasks_invalidated_unreview_stabilized = _f.total_tasks_invalidated_unreview_stabilized
                f.total_tasks_waiting_validation_stabilized = _f.total_tasks_waiting_validation_stabilized
                
                f.total_tasks_validated = _f.total_tasks_validated
                f.total_tasks_invalidated = _f.total_tasks_invalidated
                f.total_tasks_invalidated_review = _f.total_tasks_invalidated_review
                f.total_tasks_invalidated_unreview = _f.total_tasks_invalidated_unreview
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
        nsc = NoSQLClient()
        eadls = nsc.get_db('eadls')
        docs_eadls = eadls.all_docs(include_docs=True)['rows']
        docs_eadls_dict = {doc.get('doc').get('representative').get('email'): list(itertools.chain(*[[str(v['id']) for v in ad['villages']] for ad in doc.get('doc')['administrative_regions_objects']])) for doc in docs_eadls if doc.get('doc') and doc.get('doc').get('type') == 'adl' and doc.get('doc').get('representative') and doc.get('doc').get('administrative_regions_objects')}

        # adls = project_mis.administrative_levels.filter(id__in=[ad.id for ad in mis_objects_call.filter_objects(administrativelevels_models.AdministrativeLevel, id__in=liste_villages)]) if liste_villages else project_mis.administrative_levels.all()
        adls = project_mis.administrative_levels.filter(id__in=liste_villages) if liste_villages else project_mis.administrative_levels.all()

        adls_with_names = {str(adl.id): adl.name for adl in adls}

        adl_headquarters_villages = set(adl.cvd.headquarters_village.id for adl in adls if adl.cvd and adl.cvd.headquarters_village)
        adl_villages_ids = set(adl.id for adl in adls if adl.cvd)


        aggregs = AggregatedStatus.objects.filter(administrative_level_id__in=adl_headquarters_villages, project_id=request.session.get('project_id') or 4, cycle_id=request.session.get('cycle_id') or 1, facilitator=None, task__isnull=False)
        
        # Parcours des facilitateurs
        for f in facilitators:

            ag_f = dict_agg_s_fs.get(str(f.id))
            if not ag_f:
                ag_f = AggregatedStatusFacilitator()
                ag_f.project_id = request.session.get('project_id') or 4
                ag_f.cycle_id = request.session.get('cycle_id') or 1
                ag_f.facilitator_id = f.id

            administrative_levels_ids = [str(adl['id']) for adl in f.administrative_levels if adl['project_id'] == request.session.get('project_couch_id') or "1057e0a41198a35ac379602ff7135282"] if f.administrative_levels else []
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
            f.total_tasks_invalidated_unreview_current_project = sum(agg.total_tasks_invalidated_unreview for agg in children_agg_current_project)
            f.total_tasks_waiting_validation_current_project = sum(agg.total_tasks_waiting_validation for agg in children_agg_current_project)
            ag_f.last_activity_current_project = f.last_activity_current_project
            ag_f.total_tasks_completed_current_project = f.total_tasks_completed_current_project
            ag_f.total_tasks_current_project = f.total_tasks_current_project
            ag_f.total_tasks_validated_current_project = f.total_tasks_validated_current_project
            ag_f.total_tasks_invalidated_current_project = f.total_tasks_invalidated_current_project
            ag_f.total_tasks_invalidated_review_current_project = f.total_tasks_invalidated_review_current_project
            ag_f.total_tasks_invalidated_unreview_current_project = f.total_tasks_invalidated_unreview_current_project
            ag_f.total_tasks_waiting_validation_current_project = f.total_tasks_waiting_validation_current_project
            
            f.last_activity_stabilized = aggreg_last_activity_stabilized.last_activity if aggreg_last_activity_stabilized else None
            f.total_tasks_completed_stabilized = sum(agg.total_tasks_completed for agg in children_agg_stabilized)
            f.total_tasks_stabilized = sum(agg.total_tasks for agg in children_agg_stabilized)
            f.total_tasks_validated_stabilized = sum(agg.total_tasks_validated for agg in children_agg_stabilized)
            f.total_tasks_invalidated_stabilized = sum(agg.total_tasks_invalidated for agg in children_agg_stabilized)
            f.total_tasks_invalidated_review_stabilized = sum(agg.total_tasks_invalidated_review for agg in children_agg_stabilized)
            f.total_tasks_invalidated_unreview_stabilized = sum(agg.total_tasks_invalidated_unreview for agg in children_agg_stabilized)
            f.total_tasks_waiting_validation_stabilized = sum(agg.total_tasks_waiting_validation for agg in children_agg_stabilized)
            ag_f.last_activity_stabilized = f.last_activity_stabilized
            ag_f.total_tasks_completed_stabilized = f.total_tasks_completed_stabilized
            ag_f.total_tasks_stabilized = f.total_tasks_stabilized
            ag_f.total_tasks_validated_stabilized = f.total_tasks_validated_stabilized
            ag_f.total_tasks_invalidated_stabilized = f.total_tasks_invalidated_stabilized
            ag_f.total_tasks_invalidated_review_stabilized = f.total_tasks_invalidated_review_stabilized
            ag_f.total_tasks_invalidated_unreview_stabilized = f.total_tasks_invalidated_unreview_stabilized
            ag_f.total_tasks_waiting_validation_stabilized = f.total_tasks_waiting_validation_stabilized

            f.last_activity = aggreg_last_activity.last_activity if aggreg_last_activity else None
            f.total_tasks_completed = sum(agg.total_tasks_completed for agg in children_agg)
            f.total_tasks = sum(agg.total_tasks for agg in children_agg)
            f.total_tasks_validated = sum(agg.total_tasks_validated for agg in children_agg)
            f.total_tasks_invalidated = sum(agg.total_tasks_invalidated for agg in children_agg)
            f.total_tasks_invalidated_review = sum(agg.total_tasks_invalidated_review for agg in children_agg)
            f.total_tasks_invalidated_unreview = sum(agg.total_tasks_invalidated_unreview for agg in children_agg)
            f.total_tasks_waiting_validation = sum(agg.total_tasks_waiting_validation for agg in children_agg)
            ag_f.last_activity = f.last_activity
            ag_f.total_tasks_completed = f.total_tasks_completed
            ag_f.total_tasks = f.total_tasks
            ag_f.total_tasks_validated = f.total_tasks_validated
            ag_f.total_tasks_invalidated = f.total_tasks_invalidated
            ag_f.total_tasks_invalidated_review = f.total_tasks_invalidated_review
            ag_f.total_tasks_invalidated_unreview = f.total_tasks_invalidated_unreview
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
                    _total_tasks_invalidated_unreview = sum(agg.total_tasks_invalidated_unreview for agg in _children_aggs)
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
                        'total_tasks_invalidated_unreview': _total_tasks_invalidated_unreview,
                        'total_tasks_waiting_validation': _total_tasks_waiting_validation,
                        'last_task_done': _last_task_done,
                        'type': _type,
                        'in_the_both': adl_h_id in adl_headquarters_villages_uniques_current_project and adl_h_id in adl_headquarters_villages_uniques_stabilized
                    })

            ag_f.administrative_level_headquarters_villages_infos = adl_headquarters_villages_infos
            ag_f.new_update_exists = False
            ag_f.save()
            
            _facilitators.append(f)





    file_path = os.path.join(settings.MEDIA_ROOT, f'dict_facilitators_evolution_{datetime.today().strftime().replace("-", "").replace(":", "").replace(" ", "_")}.json')
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(_facilitators, f, ensure_ascii=False, indent=4)
    
    return _facilitators