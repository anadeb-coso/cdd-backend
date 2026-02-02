import os
import sys
from datetime import datetime
import json
import requests
from requests.auth import HTTPBasicAuth
import pandas as pd
from sys import platform

from authentication.models import Facilitator
from cdd.call_objects_from_other_db import mis_objects_call
from administrativelevels.models import AdministrativeLevel
from assignments.models import AssignAdministrativeLevelToFacilitator
from dashboard.facilitators.repository.db_facilitator_repository import FacilitatorRepository
from dashboard.facilitators.repository.facilitator_criteria import FacilitatorCriteria
from subprojects.models import Project as MisProject
from cdd.call_objects_from_other_db import mis_objects_call
from dashboard.administrative_levels.functions import get_cascade_villages_by_administrative_level_id
from process_manager.models import Project
from dashboard.statistics.utils import comparer_chaines, normaliser_chaine

from no_sql_client import NoSQLClient


def get_task_by_administrativelevel_id_and_task_id(list, ad_id, task_id):
    for doc in list:
        if doc and doc.get('type') == "task" and doc.get('administrative_level_id') == ad_id and doc.get('sql_id') == task_id:
            return doc
    return None

def get_task_by_task_id(list, task_id, task_name=None):
    docs = []
    for o in list:
        doc = o.get("doc")
        if doc.get('type') == "task" and (doc.get('sql_id') == task_id or normaliser_chaine(doc.get('name')) == task_name):
            docs.append(doc)
    return docs

def get_task_by_task_ids(list, tasks_ids, tasks_names=[]):
    docs = []
    for o in list:
        doc = o.get("doc")
        if doc.get('type') == "task" and (doc.get('sql_id') in tasks_ids or normaliser_chaine(doc.get('name')) in tasks_names):
            docs.append(doc)
    return docs

def append_elt(_list, elt):
    if elt not in _list:
        _list.append(elt)
    return _list

def get_cvd_index(datas_dict_havent_priorities_pav: dict, cvd_id: str):
    g_index = -1
    for k, v in datas_dict_havent_priorities_pav.items():
        if k == "ID CVD":
            for _k, _v in v.items():
                if _v == cvd_id:
                    return _k
                else:
                    g_index = _k if _k > g_index else g_index
    return g_index + 1


def priorities_situation(facilitator_dbs_name, params={"type":"All", "ids_administrativelevel":""}):
    facilitators_havent_priorities = []
    facilitators_uncompleted = []
    villages_havent_priorities = []
    villages_havent_three_priorities = []
    villages_uncompleted = []
    datas_dict_havent_priorities = {
        "AC": {},
        "Phone": {},
        "CVD": {},
        "Villages": {}
    }
    datas_dict_uncompleted = {
        "AC": {},
        "Phone": {},
        "CVD": {},
        "Villages": {}
    }

    datas_dict_havent_three_priorities = {
        "AC": {},
        "Phone": {},
        "CVD": {},
        "Villages": {}
    }
    project_name = params.get('session_project_name')
    cycle_id = params.get('session_cycle_couch_id')
    project = Project.objects.get(id=params.get('session_project_id'))

    nsc = NoSQLClient()

    count_unc = 0
    count_havent = 0
    count_havent_three = 0

    
    _type = params.get("type")
    liste_villages = get_cascade_villages_by_administrative_level_id(params.get("ids_administrativelevel"))
    
    project_mis = mis_objects_call.filter_objects(MisProject, name=project_name)
    project_mis_id = project_mis.first().id if project_mis.count() >= 1 else 1
    if facilitator_dbs_name:
        fs = Facilitator.objects.filter(develop_mode=False, training_mode=False, no_sql_db_name__in=facilitator_dbs_name)
    else:
        if params.get("ids_administrativelevel"):
            assign_facilitators = AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(
                administrative_level_id__in=[int(v['administrative_id']) for v in liste_villages],
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


    # fs = Facilitator.objects.filter(develop_mode=False, training_mode=False, projects__in=[params.get('session_project_id')])

    for facilitator in fs:
        villages_havent_priorities = []
        villages_havent_three_priorities = []
        villages_uncompleted = []
        
        facilitator_database = nsc.get_db(facilitator.no_sql_db_name)
        fc_tasks = facilitator_database.all_docs(include_docs=True)['rows']

        facilitator_doc = None
        facilitator_adl_ids = []
        for elt in fc_tasks:
            d = elt.get('doc')
            if d.get('type') == 'facilitator':
                facilitator_doc = d
                facilitator_adl_ids = [_['id'] for _ in d['administrative_levels']]
                break

        fc_tasks = [doc for doc in fc_tasks if doc.get('doc') and doc.get('doc').get('cycle_id') == cycle_id and doc.get('doc').get('project_id') == project.couch_id]
                            
        # docs = get_task_by_task_id(fc_tasks, 59, normaliser_chaine("Soutenir la communauté dans la sélection des priorités par sous-composante (1.1, 1.2 et 1.3) à soumettre à la discussion du CCD lors de la réunion cantonale d'arbitrage"))
        docs = get_task_by_task_ids(
            fc_tasks, 
            [59, 128, 92], # COSO, FA-COSO, PURS
            [
                normaliser_chaine("Soutenir la communauté dans la sélection des priorités par composante (1, 2 et 3) à soumettre à la discussion du CCD."),
                normaliser_chaine("Soutenir la communauté dans la sélection des priorités par sous-composante (1.1, 1.2 et 1.3) à soumettre à la discussion du CCD lors de la réunion cantonale d'arbitrage")
            ]
        )
        ok_unc = False
        ok_havent_p = False
        ok_havent_three_p = False
        for _doc in docs:
            if _doc and _doc.get('project_name') == project_name and str(_doc.get("administrative_level_id")) in facilitator_adl_ids:
                # if not _doc.get('form_response') or (_doc.get('form_response') and (
                #     not _doc['form_response'][0].get('sousComposante11') or (
                #         _doc['form_response'][0].get('sousComposante11') and (
                #             not _doc['form_response'][0].get('sousComposante11').get('prioritesDuVillage') or len(_doc['form_response'][0].get('sousComposante11').get('prioritesDuVillage'))<3
                #         )
                #     )
                # )):
                #     villages_havent_three_priorities = append_elt(villages_havent_three_priorities, _doc.get("administrative_level_name"))
                #     ok_havent_three_p = True
                if not _doc.get('form_response') or (
                    _doc.get('form_response') and len(_doc['form_response'][0].get('sousComposante11').get('prioritesDuVillage'))<3
                    ):
                    if _doc.get('form_response'):
                        n = len(_doc['form_response'][0].get('sousComposante11').get('prioritesDuVillage'))
                    else:
                        n = 0
                    villages_havent_three_priorities = append_elt(villages_havent_three_priorities, f"{_doc.get('administrative_level_name')} ({n})")
                    ok_havent_three_p = True

                if _doc and (not _doc["completed"] or not _doc['form_response']):
                    if _doc and not _doc["completed"]:
                        villages_uncompleted = append_elt(villages_uncompleted, _doc.get("administrative_level_name"))
                        ok_unc = True
                        
                    if _doc and not _doc['form_response']:
                        villages_havent_priorities = append_elt(villages_havent_priorities, _doc.get("administrative_level_name"))
                        ok_havent_p = True
                    
        if ok_unc:
            datas_dict_uncompleted["AC"][count_unc] = facilitator_doc.get("name")
            datas_dict_uncompleted["Phone"][count_unc] = facilitator_doc.get("phone")
            datas_dict_uncompleted["CVD"][count_unc] = len(villages_uncompleted)
            datas_dict_uncompleted["Villages"][count_unc] = " ; ".join(villages_uncompleted)
            count_unc += 1
        if ok_havent_p:
            datas_dict_havent_priorities["AC"][count_havent] = facilitator_doc.get("name")
            datas_dict_havent_priorities["Phone"][count_havent] = facilitator_doc.get("phone")
            datas_dict_havent_priorities["CVD"][count_havent] = len(villages_havent_priorities)
            datas_dict_havent_priorities["Villages"][count_havent] = " ; ".join(villages_havent_priorities)
            count_havent += 1
        if ok_havent_three_p:
            datas_dict_havent_three_priorities["AC"][count_havent_three] = facilitator_doc.get("name")
            datas_dict_havent_three_priorities["Phone"][count_havent_three] = facilitator_doc.get("phone")
            datas_dict_havent_three_priorities["CVD"][count_havent_three] = len(villages_havent_three_priorities)
            datas_dict_havent_three_priorities["Villages"][count_havent_three] = " ; ".join(villages_havent_three_priorities)
            count_havent_three += 1

        

    bk_database = nsc.get_db("backup_db_facilitators_docs")
    bk_tasks = bk_database.all_docs(include_docs=True)['rows']
    bk_tasks = [doc for doc in bk_tasks if doc.get('doc') and doc.get('doc').get('cycle_id') == cycle_id and doc.get('doc').get('project_id') == project.couch_id]            
    # docs = get_task_by_task_id(bk_tasks, 59, normaliser_chaine("Soutenir la communauté dans la sélection des priorités par sous-composante (1.1, 1.2 et 1.3) à soumettre à la discussion du CCD lors de la réunion cantonale d'arbitrage"))
    docs = get_task_by_task_ids(
        bk_tasks, 
        [59, 128, 92], # COSO, FA-COSO, PURS
        [
            normaliser_chaine("Soutenir la communauté dans la sélection des priorités par composante (1, 2 et 3) à soumettre à la discussion du CCD."),
            normaliser_chaine("Soutenir la communauté dans la sélection des priorités par sous-composante (1.1, 1.2 et 1.3) à soumettre à la discussion du CCD lors de la réunion cantonale d'arbitrage")
        ]
    )
    
    administrative_level_cvd_villages = []
    for _doc in docs:
        if _doc and _doc["administrative_level_id"] not in administrative_level_cvd_villages:
            adl = mis_objects_call.filter_objects(AdministrativeLevel,id=int(_doc["administrative_level_id"])).first()
            if adl:
                administrative_level_cvd_villages.append(_doc["administrative_level_id"])
                villages_havent_priorities = []
                villages_uncompleted = []
                villages_havent_three_priorities = []
                ok_unc = False
                ok_havent_p = False
                ok_havent_three_p = False
                if _doc:
                    # if not _doc.get('form_response') or (_doc.get('form_response') and (
                    #     not _doc['form_response'][0].get('sousComposante11') or (
                    #         _doc['form_response'][0].get('sousComposante11') and (
                    #             not _doc['form_response'][0].get('sousComposante11').get('prioritesDuVillage') or len(_doc['form_response'][0].get('sousComposante11').get('prioritesDuVillage'))<3
                    #         )
                    #     )
                    # )):
                    #     villages_havent_three_priorities = append_elt(villages_havent_three_priorities, _doc.get("administrative_level_name"))
                    #     ok_havent_three_p = True
                    if not _doc.get('form_response') or (
                        _doc.get('form_response') and len(_doc['form_response'][0].get('sousComposante11').get('prioritesDuVillage'))<3
                        ):
                        if _doc.get('form_response'):
                            n = len(_doc['form_response'][0].get('sousComposante11').get('prioritesDuVillage'))
                        else:
                            n = 0
                        villages_havent_three_priorities = append_elt(villages_havent_three_priorities, f"{_doc.get('administrative_level_name')} ({n})")
                        ok_havent_three_p = True

                    if _doc and (not _doc["completed"] or not _doc['form_response']):
                        if _doc and not _doc["completed"]:
                            villages_uncompleted = append_elt(villages_uncompleted, _doc.get("administrative_level_name"))
                            ok_unc = True
                            
                        if _doc and not _doc['form_response']:
                            villages_havent_priorities = append_elt(villages_havent_priorities, _doc.get("administrative_level_name"))
                            ok_havent_p = True
                        
                if ok_unc:
                    datas_dict_uncompleted["AC"][count_unc] = ""
                    datas_dict_uncompleted["Phone"][count_unc] = ""
                    datas_dict_uncompleted["CVD"][count_unc] = len(villages_uncompleted)
                    datas_dict_uncompleted["Villages"][count_unc] = " ; ".join(villages_uncompleted)
                    count_unc += 1
                if ok_havent_p:
                    datas_dict_havent_priorities["AC"][count_havent] = ""
                    datas_dict_havent_priorities["Phone"][count_havent] = ""
                    datas_dict_havent_priorities["CVD"][count_havent] = len(villages_havent_priorities)
                    datas_dict_havent_priorities["Villages"][count_havent] = " ; ".join(villages_havent_priorities)
                    count_havent += 11
                if ok_havent_three_p:
                    datas_dict_havent_three_priorities["AC"][count_havent_three] = ""
                    datas_dict_havent_three_priorities["Phone"][count_havent_three] = ""
                    datas_dict_havent_three_priorities["CVD"][count_havent_three] = len(villages_havent_three_priorities)
                    datas_dict_havent_three_priorities["Villages"][count_havent_three] = " ; ".join(villages_havent_three_priorities)
                    count_havent_three += 1
                            
            
    # print()
    # print("Done!")


    if not os.path.exists("media/statistics"):
            os.makedirs("media/statistics")
    file_path = f'statistics/unpriorities_{str(datetime.today().replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_")}.xlsx'

    df = pd.DataFrame(datas_dict_havent_priorities)

    with pd.ExcelWriter("media/"+file_path) as writer:
        df.to_excel(writer, sheet_name='Pas de priorités renseignées', index=False)
        
        pd.DataFrame(
            datas_dict_uncompleted
        ).to_excel(writer, sheet_name='Tâches de priorités non achevées', index=False)

        pd.DataFrame(
            datas_dict_havent_three_priorities
        ).to_excel(writer, sheet_name='Pas de 3 priorités renseignées', index=False)

    if platform == "win32":
        # windows
        return file_path.replace("/", "\\\\")
    else:
        return file_path



def priorities_pav_pac_situation(facilitator_dbs_name, params={"type":"All", "ids_administrativelevel":""}):
    facilitators_havent_priorities = []
    facilitators_uncompleted = []
    villages_havent_priorities = [] 
    villages_uncompleted = []
    datas_dict_havent_priorities_pav = {
        "ID CVD": {},
        "ID Village": {},
        "REGION": {},
        "PREFECTURE": {},
        "COMMUNE": {},
        "CANTON": {},
        "CVD": {},
        "VILLAGES": {},
        "Priorite 1": {},
        "Priorite 2": {},
        "Priorite 3": {},
        "Priorite 4": {},
        "Priorite 5": {},
        "Priorite 6": {},
        "Priorite 7": {},
        "Priorite 8": {},
        "Priorite 9": {},
        "Priorite 10": {},
        "Priorite 11": {},
        "Priorite 12": {},
        "Priorite sous-composante 1.2a": {},
        "Priorite sous-composante 1.2b Groupes Socio-economiques": {},
        "Priorite sous-composante 1.2b Besoins Socio-Economiques": {},
        "Priorite sous-composante 1.2b Besoins en renforcement de capacites": {},
        "Priorite sous-composante 1.3 1": {},
        "Priorite sous-composante 1.3 2": {},
        "Priorite sous-composante 1.3 3": {},
        "Priorite sous-composante 1.3 4": {},
        "Priorite sous-composante 1.3 5": {},
        "PAV": {},
        "PAV correct": {},
        "PAC": {},
        "PAC correct": {},
        "AC": {},
        "Phone": {}
    }
    project_name = params.get('session_project_name')
    cycle_id = params.get('session_cycle_couch_id')
    project = Project.objects.get(id=params.get('session_project_id'))

    _type = params.get("type")
    liste_villages = get_cascade_villages_by_administrative_level_id(params.get("ids_administrativelevel"))
    
    project_mis = mis_objects_call.filter_objects(MisProject, name=project_name)
    project_mis_id = project_mis.first().id if project_mis.count() >= 1 else 1
    if facilitator_dbs_name:
        fs = Facilitator.objects.filter(develop_mode=False, training_mode=False, no_sql_db_name__in=facilitator_dbs_name)
    else:
        if params.get("ids_administrativelevel"):
            assign_facilitators = AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(
                administrative_level_id__in=[int(v['administrative_id']) for v in liste_villages],
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

    nsc = NoSQLClient()

    count = 0
    
    # fs = Facilitator.objects.filter(develop_mode=False, training_mode=False, projects__in=[params.get('session_project_id')])
    # print(fs.count())
    for facilitator in fs:
        # print()
        villages_havent_priorities = []
        villages_uncompleted = []
        # print(facilitator.name)
        facilitator_database = nsc.get_db(facilitator.no_sql_db_name)
        fc_tasks = facilitator_database.all_docs(include_docs=True)['rows']
        
        facilitator_doc = None
        facilitator_adl_ids = []
        for elt in fc_tasks:            
            d = elt.get('doc')
            if d.get('type') == 'facilitator':
                facilitator_doc = d
                facilitator_adl_ids = [_['id'] for _ in d['administrative_levels']]
                break
            
        fc_tasks = [doc for doc in fc_tasks if doc.get('doc') and doc.get('doc').get('cycle_id') == cycle_id and doc.get('doc').get('project_id') == project.couch_id]
                
        docs = get_task_by_task_ids(
            fc_tasks, 
            [45, 47, 59, 130, 132, 128, 94, 96, 92], # COSO, FA-COSO, PURS
            [
                normaliser_chaine("Soutenir la communauté dans la sélection des priorités par composante (1, 2 et 3) à soumettre à la discussion du CCD."),
                normaliser_chaine("Soutenir la communauté dans la sélection des priorités par sous-composante (1.1, 1.2 et 1.3) à soumettre à la discussion du CCD lors de la réunion cantonale d'arbitrage"),
                normaliser_chaine("Elaboration du plan d'action villageois (PAV)"),
                normaliser_chaine("Appui au CCD dans l'analyse des PAV des villages, l'arbitrage, la sélection des sous - projets à financer et l'affection des ressources par sous - projet")
            ]
        )
        ok_unc = False
        ok_havent_p = False
        ok_havent_three_p = False
        # print(facilitator_doc)
        if facilitator_doc:
            for _doc in docs:
                if _doc.get('type') == 'task': # and _doc.get('project_name') == project_name
                    try:
                        adl = mis_objects_call.get_object(AdministrativeLevel, id=int(_doc.get("administrative_level_id")))
                        cvd = adl.cvd
                        count = get_cvd_index(datas_dict_havent_priorities_pav, cvd.id if cvd else 0)
                        datas_dict_havent_priorities_pav["AC"][count] = facilitator_doc.get("name")
                        datas_dict_havent_priorities_pav["Phone"][count] = facilitator_doc.get("phone")
                        datas_dict_havent_priorities_pav["CVD"][count] = _doc.get("administrative_level_name")
                        datas_dict_havent_priorities_pav["ID CVD"][count] = cvd.id if cvd else 0
                        datas_dict_havent_priorities_pav["ID Village"][count] = int(_doc.get("administrative_level_id"))

                        datas_dict_havent_priorities_pav["VILLAGES"][count] = ";".join([o.name for o in cvd.get_villages()])
                        datas_dict_havent_priorities_pav["CANTON"][count] = adl.parent.name
                        datas_dict_havent_priorities_pav["COMMUNE"][count] = adl.parent.parent.name
                        datas_dict_havent_priorities_pav["PREFECTURE"][count] = adl.parent.parent.parent.name
                        datas_dict_havent_priorities_pav["REGION"][count] = adl.parent.parent.parent.parent.name
                        
                        prioritesDuVillage = []
                        classementSousComposante13 = []
                        
                        if _doc['form_response']:
                            form_response = list(_doc['form_response'])
                            if _doc['sql_id'] in [59, 128, 92]:
                                sousComposante11 = dict(form_response[0]).get('sousComposante11')
                                if sousComposante11:
                                    prioritesDuVillage = sousComposante11.get('prioritesDuVillage')
                                    
                                    if prioritesDuVillage:
                                        for i in range(1, 13):
                                            try:
                                                priorite = ""
                                                if prioritesDuVillage[i-1].get('priorite') == 'Autre' and prioritesDuVillage[i-1].get('siAutreVeuillezDecrire') not in ('', None):
                                                    priorite = f"{prioritesDuVillage[i-1].get('siAutreVeuillezDecrire')} ({prioritesDuVillage[i-1].get('coutEstime')})"
                                                else:
                                                    priorite = f"{prioritesDuVillage[i-1].get('priorite')} ({prioritesDuVillage[i-1].get('coutEstime')})"

                                                
                                                datas_dict_havent_priorities_pav[f"Priorite {i}"][count] = priorite
                                                #datas_dict_havent_priorities_pav[f"Priorite {i}"][count] = f"{(prioritesDuVillage[i-1].get('') if prioritesDuVillage[i-1].get('priorite') not in ('', None) else prioritesDuVillage[i-1].get('priorite')) if prioritesDuVillage[i-1].get('priorite') == 'Autre' else prioritesDuVillage[i-1].get('priorite')} ({prioritesDuVillage[i-1].get('coutEstime')})"
                                                # print(priorite)
                                            except:
                                                datas_dict_havent_priorities_pav[f"Priorite {i}"][count] = ""
                                            # print(datas_dict_havent_priorities_pav[f"Priorite {i}"][count])

                                # print("datas_dict_havent_priorities_pav 1")
                                # print(datas_dict_havent_priorities_pav)
                                try:
                                    sousComposante12a = dict(form_response[1]).get('sousComposante12a')
                                except Exception as exc:
                                    print(exc)
                                    sousComposante12a = dict()
                                if sousComposante12a:
                                    datas_dict_havent_priorities_pav["Priorite sous-composante 1.2a"][count] = f"{sousComposante12a['nomDuMarcheLePlusImportant']} ({' ; '.join([t.get('typeDeDeveloppement') for t in sousComposante12a['typesInfrastructuresEtEquipements'] if t and t.get('typeDeDeveloppement')])})"
                                else:
                                    datas_dict_havent_priorities_pav["Priorite sous-composante 1.2a"][count] = ""
                                
                                try:
                                    sousComposante12b = dict(form_response[2]).get('sousComposante12b')
                                except:
                                    sousComposante12b = dict()
                                    
                                if sousComposante12b:
                                    datas_dict_havent_priorities_pav["Priorite sous-composante 1.2b Groupes Socio-economiques"][count] = f"{' ; '.join([p.get('principalGroupeSocioeconomique') for p in sousComposante12b.get('principauxGroupesSocioeconomiques') if p and p.get('principalGroupeSocioeconomique')])}"
                                    datas_dict_havent_priorities_pav["Priorite sous-composante 1.2b Besoins Socio-Economiques"][count] = f"{' ; '.join([b.get('besoin') for b in sousComposante12b.get('principauxbesoinsSociauxEconomiques') if b and b.get('besoin')])}"
                                    datas_dict_havent_priorities_pav["Priorite sous-composante 1.2b Besoins en renforcement de capacites"][count] = f"{' ; '.join([b.get('besoin') for b in sousComposante12b.get('principauxBesoinsEnRenforcementDeCapacites') if b and b.get('besoin')])}"
                                else:
                                    datas_dict_havent_priorities_pav["Priorite sous-composante 1.2b Groupes Socio-economiques"][count] = ""
                                    datas_dict_havent_priorities_pav["Priorite sous-composante 1.2b Besoins Socio-Economiques"][count] = ""
                                    datas_dict_havent_priorities_pav["Priorite sous-composante 1.2b Besoins en renforcement de capacites"][count] = ""
                        
                                try:
                                    sousComposante13 = dict(form_response[3]).get('sousComposante13')
                                except:
                                    sousComposante13 = dict()
                                if sousComposante13:
                                    classementSousComposante13 = sousComposante13.get('classement')
                                    if classementSousComposante13:
                                        for i in range(1, 6):
                                            try:
                                                priorite = ""
                                                if classementSousComposante13[i-1].get('priorite') == 'Autre' and classementSousComposante13[i-1].get('siAutreVeuillezDecrire') not in ('', None):
                                                    priorite = f"{classementSousComposante13[i-1].get('siAutreVeuillezDecrire')} ({classementSousComposante13[i-1].get('coutEstime')})"
                                                else:
                                                    priorite = f"{classementSousComposante13[i-1].get('priorite')} ({classementSousComposante13[i-1].get('coutEstime')})"
                                                datas_dict_havent_priorities_pav[f"Priorite sous-composante 1.3 {i}"][count] = priorite
                                            except:
                                                datas_dict_havent_priorities_pav[f"Priorite sous-composante 1.3 {i}"][count] = ""

                                        
                                if not prioritesDuVillage:
                                    for i in range(1, 13):
                                        datas_dict_havent_priorities_pav[f"Priorite {i}"][count] = ""
                                if not classementSousComposante13:
                                    for i in range(1, 6):
                                        datas_dict_havent_priorities_pav[f"Priorite sous-composante 1.3 {i}"][count] = ""

                            elif _doc['sql_id'] in [45, 130, 94]:
                                if _doc['attachments'][0]['attachment'] and _doc['attachments'][0]['attachment'].get('uri'):
                                    datas_dict_havent_priorities_pav["PAV"][count] = _doc['attachments'][0]['attachment']['uri'].split('?')[0]
                                    datas_dict_havent_priorities_pav["PAV correct"][count] = "Non" if _doc['attachments'][0]['attachment'] and _doc['attachments'][0].get('type') and 'image' in _doc['attachments'][0]['type'] else ("Oui" if _doc['attachments'][0].get('type') else "N/A")

                                if not datas_dict_havent_priorities_pav["PAV"].get(count):
                                    datas_dict_havent_priorities_pav["PAV"][count] = ""
                                    datas_dict_havent_priorities_pav["PAV correct"][count] = ""
                                    
                            elif _doc['sql_id'] in [47, 132, 96]:
                                try:
                                    if _doc['attachments'][5]['attachment'] and _doc['attachments'][5]['attachment'].get('uri'):
                                        datas_dict_havent_priorities_pav["PAC"][count] = _doc['attachments'][5]['attachment']['uri'].split('?')[0]
                                        datas_dict_havent_priorities_pav["PAC correct"][count] = "Non" if _doc['attachments'][5]['attachment'] and _doc['attachments'][5].get('type') and 'image' in _doc['attachments'][5]['type'] else ("Oui" if _doc['attachments'][0].get('type') else "N/A")
                                except Exception as exc:
                                    print(exc)
                                        
                                if not datas_dict_havent_priorities_pav["PAC"].get(count):
                                    datas_dict_havent_priorities_pav["PAC"][count] = ""
                                    datas_dict_havent_priorities_pav["PAC correct"][count] = ""
                                    
                    except Exception as exc:
                        print(exc, _doc['administrative_level_id'])
                    
    # print(datas_dict_havent_priorities_pav)
    bk_database = nsc.get_db("backup_db_facilitators_docs")
    bk_tasks = bk_database.all_docs(include_docs=True)['rows']
    bk_tasks = [doc for doc in bk_tasks if doc.get('doc') and doc.get('doc').get('cycle_id') == cycle_id and doc.get('doc').get('project_id') == project.couch_id]              
    docs = get_task_by_task_ids(
        bk_tasks, 
        [45, 47, 59, 130, 132, 128, 94, 96, 92], # COSO, FA-COSO, PURS
        [
            normaliser_chaine("Soutenir la communauté dans la sélection des priorités par composante (1, 2 et 3) à soumettre à la discussion du CCD."),
            normaliser_chaine("Soutenir la communauté dans la sélection des priorités par sous-composante (1.1, 1.2 et 1.3) à soumettre à la discussion du CCD lors de la réunion cantonale d'arbitrage"),
            normaliser_chaine("Elaboration du plan d'action villageois (PAV)"),
            normaliser_chaine("Appui au CCD dans l'analyse des PAV des villages, l'arbitrage, la sélection des sous - projets à financer et l'affection des ressources par sous - projet")
        ]
    )
    
    for _doc in docs:
            
        if _doc.get('type') == 'task':
            adl = mis_objects_call.filter_objects(AdministrativeLevel, id=int(_doc.get("administrative_level_id"))).first()
            if adl:
                cvd = adl.cvd
                count = get_cvd_index(datas_dict_havent_priorities_pav, cvd.id if cvd else 0)
                datas_dict_havent_priorities_pav["AC"][count] = ""
                datas_dict_havent_priorities_pav["Phone"][count] = ""
                datas_dict_havent_priorities_pav["CVD"][count] = _doc.get("administrative_level_name")
                datas_dict_havent_priorities_pav["ID CVD"][count] = cvd.id if cvd else 0
                datas_dict_havent_priorities_pav["ID Village"][count] = int(_doc.get("administrative_level_id"))

                datas_dict_havent_priorities_pav["VILLAGES"][count] = ";".join([o.name for o in cvd.get_villages()])
                datas_dict_havent_priorities_pav["CANTON"][count] = adl.parent.name
                datas_dict_havent_priorities_pav["COMMUNE"][count] = adl.parent.parent.name
                datas_dict_havent_priorities_pav["PREFECTURE"][count] = adl.parent.parent.parent.name
                datas_dict_havent_priorities_pav["REGION"][count] = adl.parent.parent.parent.parent.name
                
                prioritesDuVillage = []
                classementSousComposante13 = []
                
                if _doc['form_response']:
                    form_response = list(_doc['form_response'])
                    if _doc['sql_id'] in [59, 128, 92]:
                        sousComposante11 = dict(form_response[0]).get('sousComposante11')
                        if sousComposante11:
                            prioritesDuVillage = sousComposante11.get('prioritesDuVillage')
                            if prioritesDuVillage:
                                for i in range(1, 13):
                                    # try:
                                    #     datas_dict_havent_priorities_pav[f"Priorite {i}"][count] = f"{prioritesDuVillage[i-1].get('priorite')} ({prioritesDuVillage[i-1].get('coutEstime')})"
                                    # except:
                                    #     datas_dict_havent_priorities_pav[f"Priorite {i}"][count] = ""
                                    try:
                                        priorite = ""
                                        if prioritesDuVillage[i-1].get('priorite') == 'Autre' and prioritesDuVillage[i-1].get('siAutreVeuillezDecrire') not in ('', None):
                                            priorite = f"{prioritesDuVillage[i-1].get('siAutreVeuillezDecrire')} ({prioritesDuVillage[i-1].get('coutEstime')})"
                                        else:
                                            priorite = f"{prioritesDuVillage[i-1].get('priorite')} ({prioritesDuVillage[i-1].get('coutEstime')})"


                                        datas_dict_havent_priorities_pav[f"Priorite {i}"][count] = priorite
                                        #datas_dict_havent_priorities_pav[f"Priorite {i}"][count] = f"{(prioritesDuVillage[i-1].get('') if prioritesDuVillage[i-1].get('priorite') not in ('', None) else prioritesDuVillage[i-1].get('priorite')) if prioritesDuVillage[i-1].get('priorite') == 'Autre' else prioritesDuVillage[i-1].get('priorite')} ({prioritesDuVillage[i-1].get('coutEstime')})"

                                    except:
                                        datas_dict_havent_priorities_pav[f"Priorite {i}"][count] = ""

                        try:
                            sousComposante12a = dict(form_response[1]).get('sousComposante12a')
                        except:
                            sousComposante12a = dict()
                        if sousComposante12a:
                                datas_dict_havent_priorities_pav["Priorite sous-composante 1.2a"][count] = f"{sousComposante12a.get('nomDuMarcheLePlusImportant')} ({' ; '.join([t.get('typeDeDeveloppement') for t in sousComposante12a.get('typesInfrastructuresEtEquipements') if t and t.get('typeDeDeveloppement')])})"
                        else:
                            datas_dict_havent_priorities_pav["Priorite sous-composante 1.2a"][count] = ""
                        
                        try:
                            sousComposante12b = dict(form_response[2]).get('sousComposante12b')
                        except:
                            sousComposante12b = dict()
                        if sousComposante12b:
                            datas_dict_havent_priorities_pav["Priorite sous-composante 1.2b Groupes Socio-economiques"][count] = f"{' ; '.join([p.get('principalGroupeSocioeconomique') for p in sousComposante12b.get('principauxGroupesSocioeconomiques') if p and p.get('principalGroupeSocioeconomique')])}"
                            datas_dict_havent_priorities_pav["Priorite sous-composante 1.2b Besoins Socio-Economiques"][count] = f"{' ; '.join([b.get('besoin') for b in sousComposante12b.get('principauxbesoinsSociauxEconomiques') if b and b.get('besoin')])}"
                            datas_dict_havent_priorities_pav["Priorite sous-composante 1.2b Besoins en renforcement de capacites"][count] = f"{' ; '.join([b.get('besoin') for b in sousComposante12b.get('principauxBesoinsEnRenforcementDeCapacites') if b and b.get('besoin')])}"
                        else:
                            datas_dict_havent_priorities_pav["Priorite sous-composante 1.2b Groupes Socio-economiques"][count] = ""
                            datas_dict_havent_priorities_pav["Priorite sous-composante 1.2b Besoins Socio-Economiques"][count] = ""
                            datas_dict_havent_priorities_pav["Priorite sous-composante 1.2b Besoins en renforcement de capacites"][count] = ""
                
                            
                        try:
                            sousComposante13 = dict(form_response[3]).get('sousComposante13')
                        except:
                            sousComposante13 = dict()
                        if sousComposante13:
                            classementSousComposante13 = sousComposante13.get('classement')
                            if classementSousComposante13:
                                for i in range(1, 6):
                                    # try:
                                    #     datas_dict_havent_priorities_pav[f"Priorite sous-composante 1.3 {i}"][count] = f"{classementSousComposante13[i-1].get('priorite')} ({classementSousComposante13[i-1].get('coutEstime')})"
                                    # except:
                                    #     datas_dict_havent_priorities_pav[f"Priorite sous-composante 1.3 {i}"][count] = ""
                                    try:
                                        priorite = ""
                                        if classementSousComposante13[i-1].get('priorite') == 'Autre' and classementSousComposante13[i-1].get('siAutreVeuillezDecrire') not in ('', None):
                                            priorite = f"{classementSousComposante13[i-1].get('siAutreVeuillezDecrire')} ({classementSousComposante13[i-1].get('coutEstime')})"
                                        else:
                                            priorite = f"{classementSousComposante13[i-1].get('priorite')} ({classementSousComposante13[i-1].get('coutEstime')})"
                                        datas_dict_havent_priorities_pav[f"Priorite sous-composante 1.3 {i}"][count] = priorite
                                    except:
                                        datas_dict_havent_priorities_pav[f"Priorite sous-composante 1.3 {i}"][count] = ""

                        if not prioritesDuVillage:
                            for i in range(1, 13):
                                datas_dict_havent_priorities_pav[f"Priorite {i}"][count] = ""
                        if not classementSousComposante13:
                            for i in range(1, 6):
                                datas_dict_havent_priorities_pav[f"Priorite sous-composante 1.3 {i}"][count] = ""
                        
                    elif _doc['sql_id'] in [45, 130, 94]:
                        if _doc['attachments'][0]['attachment'] and _doc['attachments'][0]['attachment'].get('uri'):
                            datas_dict_havent_priorities_pav["PAV"][count] = _doc['attachments'][0]['attachment']['uri'].split('?')[0]
                            datas_dict_havent_priorities_pav["PAV correct"][count] = "Non" if _doc['attachments'][0]['attachment'] and _doc['attachments'][0].get('type') and 'image' in _doc['attachments'][0]['type'] else ("Oui" if _doc['attachments'][0].get('type') else "N/A")
                                
                        if not datas_dict_havent_priorities_pav["PAV"].get(count):
                            datas_dict_havent_priorities_pav["PAV"][count] = ""
                            datas_dict_havent_priorities_pav["PAV correct"][count] = ""

                    elif _doc['sql_id'] in [47, 132, 96]:
                        try:
                            if _doc['attachments'][5]['attachment'] and _doc['attachments'][5]['attachment'].get('uri'):
                                datas_dict_havent_priorities_pav["PAC"][count] = _doc['attachments'][5]['attachment']['uri'].split('?')[0]
                                datas_dict_havent_priorities_pav["PAC correct"][count] = "Non" if _doc['attachments'][5]['attachment'] and _doc['attachments'][5].get('type') and 'image' in _doc['attachments'][5]['type'] else ("Oui" if _doc['attachments'][0].get('type') else "N/A")
                        except Exception as exc:
                            print(exc)

                        if not datas_dict_havent_priorities_pav["PAC"].get(count):
                            datas_dict_havent_priorities_pav["PAC"][count] = ""
                            datas_dict_havent_priorities_pav["PAC correct"][count] = ""

    # print()
    # print("Done!")
    

    if not os.path.exists("media/statistics"):
            os.makedirs("media/statistics")
    file_path = f'statistics/unpriorities_pav_pac_situation_{str(datetime.today().replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_")}.xlsx'

    df = pd.DataFrame(datas_dict_havent_priorities_pav)

    with pd.ExcelWriter("media/"+file_path) as writer:
        df.to_excel(writer, sheet_name='Situation priorités & PAV & PAC', index=False)
        
        # pd.DataFrame(
        #     datas_dict_uncompleted
        # ).to_excel(writer, sheet_name='Tâches de priorités non achevées', index=False)

    
    if platform == "win32":
        # windows
        return file_path.replace("/", "\\\\")
    else:
        return file_path