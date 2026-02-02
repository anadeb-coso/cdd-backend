from dashboard.administrative_levels.functions import get_cascade_villages_by_administrative_level_id
from no_sql_client import NoSQLClient
from authentication.models import Facilitator
import os
from sys import platform
from datetime import datetime, date as type_date
import pandas as pd
from dashboard.facilitators.functions import get_cvds
from administrativelevels import models as administrativelevels_models
from assignments.models import AssignAdministrativeLevelToFacilitator
from dashboard.facilitators.repository.db_facilitator_repository import FacilitatorRepository
from dashboard.facilitators.repository.facilitator_criteria import FacilitatorCriteria
from subprojects.models import Project as MisProject
from cdd.call_objects_from_other_db import mis_objects_call
from process_manager.models import Project
from .utils import safe_get, comparer_chaines


def get_datas_dict(reponses_datas, key, level: int = 1, default={}):
    for i in range(len(reponses_datas)):
        elt = reponses_datas[i]
        if level == 1:
            for k,v in elt.items():
                if k == key:
                    return v if v else default
    return default

def get_index_with_datas_dict_by_one_key_name(reponses_datas, key):
    for i in range(len(reponses_datas)):
        elt = reponses_datas[i]
        for k,v in elt.items():
            if k == key:
                return i, elt
    return 0, {}

def sum_dict_value(d: dict):
    _sum = 0
    for k, v in d.items():
        if v and str(v).replace('.','',1).replace(',','',1).isdigit():
            _sum += float(v)
    return _sum


def get_global_statistic_under_file_excel_or_csv(facilitator_dbs_name, file_type="excel", params={"type":"All", "ids_administrativelevel":""}):
    nsc = NoSQLClient()

    _type = params.get("type")
    liste_villages = get_cascade_villages_by_administrative_level_id(params.get("ids_administrativelevel"))
    
    cycle_id = params.get('session_cycle_couch_id')
    project = Project.objects.get(id=params.get('session_project_id'))
    
    project_mis = mis_objects_call.filter_objects(MisProject, name=params.get('session_project_name')).first()
    project_mis_id = project_mis.id if project_mis else 1
    print(project_mis)
    if facilitator_dbs_name:
        fs = Facilitator.objects.filter(develop_mode=False, training_mode=False, no_sql_db_name__in=facilitator_dbs_name)
    else:
        if params.get("ids_administrativelevel"):
            assign_facilitators = AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(
                administrative_level_id__in=[int(v['administrative_id']) for v in liste_villages],
                project_id=project_mis_id,
                # activated=True
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


    # if facilitator_dbs_name:
    #     fs = Facilitator.objects.filter(develop_mode=False, training_mode=False, no_sql_db_name__in=facilitator_dbs_name)
    # else:
    #     fs = Facilitator.objects.filter(develop_mode=False, training_mode=False, projects__in=[params.get('session_project_id')])

    d_cols = [ 
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "ID CVD", "ID CVD", "ID CVD", "ID CVD", "ID CVD", "ind_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Région", "Région", "Région", "Région", "ind_1"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Préfecture", "Préfecture", "Préfecture","Préfecture", "ind_2"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Commune", "Commune", "Commune", "Commune", "ind_3"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Canton", "Canton", "Canton", "Canton", "ind_4"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "CVD", "CVD", "CVD", "CVD", "ind_5"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Villages", "Villages", "Villages", "Villages", "ind_6"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Unité géographique", "Unité géographique", "Unité géographique", "Unité géographique", "ind_7"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Nom de l'AC", "Nom de l'AC", "Nom de l'AC", "Nom de l'AC", "ind_8"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Eff. Population", "Eff. Population", "Eff. Population", "ind_9"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Eff. Population", "Eff. Population", "Eff. Hommes", "ind_9_1"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Eff. Population", "Eff. Population", "Eff. Femmes", "ind_9_2"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Eff. Population", "Eff. Population", "Eff. Jeunes", "ind_9_3"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Eff. Population", "Eff. (<=35)", "H", "ind_9_4"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Eff. Population", "Eff. (<=35)", "F", "ind_9_5"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Eff. Population", "Eff. (<=35)", "T", "ind_9_6"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Eff. Population", "Eff. (>35)", "H", "ind_9_7"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Eff. Population", "Eff. (>35)", "F", "ind_9_8"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Eff. Population", "Eff. (>35)", "T", "ind_9_9"),
        
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Réfugiés", "Eff. (<=35)", "H", "ind_9_10"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Réfugiés", "Eff. (<=35)", "F", "ind_9_11"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Réfugiés", "Eff. (<=35)", "T", "ind_9_12"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Réfugiés", "Eff. (>35)", "H", "ind_9_13"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Réfugiés", "Eff. (>35)", "F", "ind_9_14"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Réfugiés", "Eff. (>35)", "T", "ind_9_15"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Réfugiés", "Total", "T", "ind_9_16"),
        
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Déplacés internes", "Eff. (<=35)", "H", "ind_9_17"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Déplacés internes", "Eff. (<=35)", "F", "ind_9_18"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Déplacés internes", "Eff. (<=35)", "T", "ind_9_19"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Déplacés internes", "Eff. (>35)", "H", "ind_9_20"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Déplacés internes", "Eff. (>35)", "F", "ind_9_21"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Déplacés internes", "Eff. (>35)", "T", "ind_9_22"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Déplacés internes", "Total", "T", "ind_9_23"),
        
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Communautés d'accueil", "Eff. (<=35)", "H", "ind_9_24"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Communautés d'accueil", "Eff. (<=35)", "F", "ind_9_25"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Communautés d'accueil", "Eff. (<=35)", "T", "ind_9_26"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Communautés d'accueil", "Eff. (>35)", "H", "ind_9_27"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Communautés d'accueil", "Eff. (>35)", "F", "ind_9_28"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Communautés d'accueil", "Eff. (>35)", "T", "ind_9_29"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Communautés d'accueil", "Total", "T", "ind_9_30"),

        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Nbre total ménages dans le village", "Nbre total ménages dans le village", "Nbre total ménages dans le village", "Nbre total ménages dans le village", "ind_10"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Nbre total groupes ethniques dans le village", "Nbre total groupes ethniques dans le village", "Nbre total groupes ethniques dans le village", "Nbre total groupes ethniques dans le village", "ind_10_1"),

        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "Date de la séance", "Date de la séance", "ind_11"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES (<=35)", "H", "ind_12"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES (<=35)", "F", "ind_13"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES (<=35)", "T", "ind_14"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES", "H", "ind_15"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES", "F", "ind_16"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES", "T", "ind_17"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "TOTAL PARTICIPANTS", "T", "ind_17_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES - REFUGIES (<=35)", "H", "ind_17_1"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES - REFUGIES (<=35)", "F", "ind_17_2"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES - REFUGIES (<=35)", "T", "ind_17_3"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES - REFUGIES", "H", "ind_17_4"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES - REFUGIES", "F", "ind_17_5"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES - REFUGIES", "T", "ind_17_6"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_17_6_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_17_7"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_17_8"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_17_9"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES - DEPLACES INTERNES", "H", "ind_17_10"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES - DEPLACES INTERNES", "F", "ind_17_11"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES - DEPLACES INTERNES", "T", "ind_17_12"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_17_12_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_17_13"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_17_14"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_17_15"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_17_16"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_17_17"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_17_18"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_17_19_0"),

        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "Date de la séance", "Date de la séance", "ind_18"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES (<=35)", "H", "ind_19"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES (<=35)", "F", "ind_20"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES (<=35)", "T", "ind_21"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES", "H", "ind_22"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES", "F", "ind_23"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES", "T", "ind_24"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "TOTAL PARTICIPANTS", "T", "ind_24_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES - REFUGIES (<=35)", "H", "ind_24_1"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES - REFUGIES (<=35)", "F", "ind_24_2"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES - REFUGIES (<=35)", "T", "ind_24_3"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES - REFUGIES", "H", "ind_24_4"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES - REFUGIES", "F", "ind_24_5"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES - REFUGIES", "T", "ind_24_6"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_24_6_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_24_7"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_24_8"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_24_9"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES - DEPLACES INTERNES", "H", "ind_24_10"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES - DEPLACES INTERNES", "F", "ind_24_11"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES - DEPLACES INTERNES", "T", "ind_24_12"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_24_12_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_24_13"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_24_14"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_24_15"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_24_16"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_24_17"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_24_18"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_24_18_0"),

        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "Date de la séance", "Date de la séance", "ind_25"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES (<=35)", "H", "ind_26"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES (<=35)", "F", "ind_27"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES (<=35)", "T", "ind_28"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES", "H", "ind_29"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES", "F", "ind_30"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES", "T", "ind_31"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "TOTAL PARTICIPANTS", "T", "ind_31_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES - REFUGIES (<=35)", "H", "ind_31_1"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES - REFUGIES (<=35)", "F", "ind_31_2"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES - REFUGIES (<=35)", "T", "ind_31_3"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES - REFUGIES", "H", "ind_31_4"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES - REFUGIES", "F", "ind_31_5"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES - REFUGIES", "T", "ind_31_6"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_31_6_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_31_7"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_31_8"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_31_9"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES - DEPLACES INTERNES", "H", "ind_31_10"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES - DEPLACES INTERNES", "F", "ind_31_11"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES - DEPLACES INTERNES", "T", "ind_31_12"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_31_12_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_31_13"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_31_14"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_31_15"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_31_16"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_31_17"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_31_18"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_31_18_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "Nombre total de ménage", "Nombre total de ménage", "ind_32"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "Ethnies minoritaires", "Ethnies minoritaires", "ind_33"),

        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "Date de la séance", "Date de la séance", "ind_34"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES (<=35)", "H", "ind_35"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES (<=35)", "F", "ind_36"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES (<=35)", "T", "ind_37"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES", "H", "ind_38"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES", "F", "ind_39"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES", "T", "ind_40"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "TOTAL PARTICIPANTS", "T", "ind_40_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES - REFUGIES (<=35)", "H", "ind_40_1"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES - REFUGIES (<=35)", "F", "ind_40_2"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES - REFUGIES (<=35)", "T", "ind_40_3"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES - REFUGIES", "H", "ind_40_4"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES - REFUGIES", "F", "ind_40_5"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES - REFUGIES", "T", "ind_40_6"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_40_6_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_40_7"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_40_8"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_40_9"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "H", "ind_40_10"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "F", "ind_40_11"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "T", "ind_40_12"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_40_12_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_40_13"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_40_14"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_40_15"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_40_16"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_40_17"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_40_18"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_40_18_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "Nombre total de ménage", "Nombre total de ménage", "ind_41"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "Ethnies minoritaires", "Ethnies minoritaires", "ind_42"),

        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "Date de la séance", "Date de la séance", "ind_43"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES (<=35)", "H", "ind_44"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES (<=35)", "F", "ind_45"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES (<=35)", "T", "ind_46"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES", "H", "ind_47"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES", "F", "ind_48"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES", "T", "ind_49"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "TOTAL PARTICIPANTS", "T", "ind_49_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES - REFUGIES (<=35)", "H", "ind_49_1"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES - REFUGIES (<=35)", "F", "ind_49_2"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES - REFUGIES (<=35)", "T", "ind_49_3"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES - REFUGIES", "H", "ind_49_4"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES - REFUGIES", "F", "ind_49_5"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES - REFUGIES", "T", "ind_49_6"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_49_6_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_49_7"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_49_8"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_49_9"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES - DEPLACES INTERNES", "H", "ind_49_10"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES - DEPLACES INTERNES", "F", "ind_49_11"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES - DEPLACES INTERNES", "T", "ind_49_12"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_49_12_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_49_13"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_49_14"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_49_15"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_49_16"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_49_17"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_49_18"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_49_18_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "Nombre total de ménage", "Nombre total de ménage", "ind_50"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "Ethnies minoritaires", "Ethnies minoritaires", "ind_51"),

        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "Date de la séance", "Date de la séance", "ind_52"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES (<=35)", "H", "ind_53"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES (<=35)", "F", "ind_54"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES (<=35)", "T", "ind_55"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES", "H", "ind_56"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES", "F", "ind_57"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES", "T", "ind_58"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "TOTAL PARTICIPANTS", "T", "ind_58_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES - REFUGIES (<=35)", "H", "ind_58_1"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES - REFUGIES (<=35)", "F", "ind_58_2"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES - REFUGIES (<=35)", "T", "ind_58_3"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES - REFUGIES", "H", "ind_58_4"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES - REFUGIES", "F", "ind_58_5"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES - REFUGIES", "T", "ind_58_6"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_58_6_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_58_7"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_58_8"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_58_9"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "H", "ind_58_10"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "F", "ind_58_11"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "T", "ind_58_12"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_58_12_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_58_13"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_58_14"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_58_15"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_58_16"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_58_17"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_58_18"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_58_18_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "Nombre total de ménage", "Nombre total de ménage", "ind_59"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "Ethnies minoritaires", "Ethnies minoritaires", "ind_60"),

        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "Date de la séance", "Date de la séance", "ind_61"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES (<=35)", "H", "ind_62"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES (<=35)", "F", "ind_63"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES (<=35)", "T", "ind_64"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES", "H", "ind_65"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES", "F", "ind_66"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES", "T", "ind_67"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "TOTAL PARTICIPANTS", "T", "ind_67_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES - REFUGIES (<=35)", "H", "ind_67_1"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES - REFUGIES (<=35)", "F", "ind_67_2"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES - REFUGIES (<=35)", "T", "ind_67_3"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES - REFUGIES", "H", "ind_67_4"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES - REFUGIES", "F", "ind_67_5"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES - REFUGIES", "T", "ind_67_6"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_67_6_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_67_7"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_67_8"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_67_9"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "H", "ind_67_10"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "F", "ind_67_11"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "T", "ind_67_12"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_67_12_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_67_13"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_67_14"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_67_15"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_67_16"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_67_17"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_67_18"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_67_18_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "Nombre total de ménage", "Nombre total de ménage", "ind_68"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "Ethnies minoritaires", "Ethnies minoritaires", "ind_69"),

        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "Date de la séance", "Date de la séance", "ind_70"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES (<=35)", "H", "ind_71"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES (<=35)", "F", "ind_72"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES (<=35)", "T", "ind_73"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES", "H", "ind_74"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES", "F", "ind_75"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES", "T", "ind_76"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "TOTAL PARTICIPANTS", "T", "ind_76_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES - REFUGIES (<=35)", "H", "ind_76_1"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES - REFUGIES (<=35)", "F", "ind_76_2"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES - REFUGIES (<=35)", "T", "ind_76_3"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES - REFUGIES", "H", "ind_76_4"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES - REFUGIES", "F", "ind_76_5"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES - REFUGIES", "T", "ind_76_6"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_76_6_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_76_7"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_76_8"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_76_9"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES - DEPLACES INTERNES", "H", "ind_76_10"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES - DEPLACES INTERNES", "F", "ind_76_11"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES - DEPLACES INTERNES", "T", "ind_76_12"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_76_12_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_76_13"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_76_14"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_76_15"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_76_16"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_76_17"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_76_18"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_76_18_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "Nombre total de ménage", "Nombre total de ménage", "ind_77"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "Ethnies minoritaires", "Ethnies minoritaires", "ind_78"),

        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "Date de la séance", "Date de la séance", "ind_79"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES (<=35)", "H", "ind_80"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES (<=35)", "F", "ind_81"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES (<=35)", "T", "ind_82"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES", "H", "ind_83"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES", "F", "ind_84"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES", "T", "ind_85"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "TOTAL PARTICIPANTS", "T", "ind_85_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES - REFUGIES (<=35)", "H", "ind_85_1"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES - REFUGIES (<=35)", "F", "ind_85_2"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES - REFUGIES (<=35)", "T", "ind_85_3"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES - REFUGIES", "H", "ind_85_4"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES - REFUGIES", "F", "ind_85_5"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES - REFUGIES", "T", "ind_85_6"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_85_6_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_85_7"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_85_8"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_85_9"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES - DEPLACES INTERNES", "H", "ind_85_10"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES - DEPLACES INTERNES", "F", "ind_85_11"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES - DEPLACES INTERNES", "T", "ind_85_12"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_85_12_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_85_13"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_85_14"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_85_15"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_85_16"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_85_17"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_85_18"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_85_18_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "Nombre total de ménage", "Nombre total de ménage", "ind_86"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "Ethnies minoritaires", "Ethnies minoritaires", "ind_87"),

        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "Date de la séance", "Date de la séance", "ind_88"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES (<=35)", "H", "ind_89"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES (<=35)", "F", "ind_90"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES (<=35)", "T", "ind_91"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES", "H", "ind_92"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES", "F", "ind_93"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES", "T", "ind_94"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "TOTAL PARTICIPANTS", "T", "ind_94_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES - REFUGIES (<=35)", "H", "ind_94_1"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES - REFUGIES (<=35)", "F", "ind_94_2"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES - REFUGIES (<=35)", "T", "ind_94_3"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES - REFUGIES", "H", "ind_94_4"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES - REFUGIES", "F", "ind_94_5"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES - REFUGIES", "T", "ind_94_6"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_94_6_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_94_7"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_94_8"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_94_9"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "H", "ind_94_10"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "F", "ind_94_11"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "T", "ind_94_12"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_94_12_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_94_13"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_94_14"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_94_15"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_94_16"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_94_17"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_94_18"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_94_18_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "Nombre total de ménage", "Nombre total de ménage", "ind_95"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "Ethnies minoritaires", "Ethnies minoritaires", "ind_96"),

        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "Date de la séance", "Date de la séance", "ind_97"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES (<=35)", "H", "ind_98"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES (<=35)", "F", "ind_99"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES (<=35)", "T", "ind_100"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES", "H", "ind_101"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES", "F", "ind_102"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES", "T", "ind_103"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "TOTAL PARTICIPANTS", "T", "ind_103_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES - REFUGIES (<=35)", "H", "ind_103_1"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES - REFUGIES (<=35)", "F", "ind_103_2"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES - REFUGIES (<=35)", "T", "ind_103_3"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES - REFUGIES", "H", "ind_103_4"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES - REFUGIES", "F", "ind_103_5"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES - REFUGIES", "T", "ind_103_6"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_103_6_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_103_7"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_103_8"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_103_9"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES - DEPLACES INTERNES", "H", "ind_103_10"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES - DEPLACES INTERNES", "F", "ind_103_11"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES - DEPLACES INTERNES", "T", "ind_103_12"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_103_12_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_103_13"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_103_14"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_103_15"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_103_16"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_103_17"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_103_18"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_103_18_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "Nombre total de ménage", "Nombre total de ménage", "ind_104"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "Ethnies minoritaires", "Ethnies minoritaires", "ind_105"),

        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "Date de la séance", "Date de la séance", "ind_106"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES (<=35)", "H", "ind_107"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES (<=35)", "F", "ind_108"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES (<=35)", "T", "ind_109"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES", "H", "ind_110"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES", "F", "ind_111"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES", "T", "ind_112"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "TOTAL PARTICIPANTS", "T", "ind_112_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES - REFUGIES (<=35)", "H", "ind_112_1"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES - REFUGIES (<=35)", "F", "ind_112_2"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES - REFUGIES (<=35)", "T", "ind_112_3"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES - REFUGIES", "H", "ind_112_4"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES - REFUGIES", "F", "ind_112_5"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES - REFUGIES", "T", "ind_112_6"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_112_6_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_112_7"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_112_8"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_112_9"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "H", "ind_112_10"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "F", "ind_112_11"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "T", "ind_112_12"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_112_12_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_112_13"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_112_14"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_112_15"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_112_16"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_112_17"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_112_18"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_112_18_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "Nombre total de ménage", "Nombre total de ménage", "ind_113"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "Ethnies minoritaires", "Ethnies minoritaires", "ind_114"),

        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "Date de la séance", "Date de la séance", "ind_115"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES (<=35)", "H", "ind_116"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES (<=35)", "F", "ind_117"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES (<=35)", "T", "ind_118"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES", "H", "ind_119"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES", "F", "ind_120"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES", "T", "ind_121"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "TOTAL PARTICIPANTS", "T", "ind_121_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES - REFUGIES (<=35)", "H", "ind_121_1"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES - REFUGIES (<=35)", "F", "ind_121_2"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES - REFUGIES (<=35)", "T", "ind_121_3"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES - REFUGIES", "H", "ind_121_4"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES - REFUGIES", "F", "ind_121_5"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES - REFUGIES", "T", "ind_121_6"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_121_6_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_121_7"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_121_8"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_121_9"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES - DEPLACES INTERNES", "H", "ind_121_10"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES - DEPLACES INTERNES", "F", "ind_121_11"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES - DEPLACES INTERNES", "T", "ind_121_12"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_121_12_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_121_13"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_121_14"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_121_15"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_121_16"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_121_17"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_121_18"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_121_18_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "Nombre total de ménage", "Nombre total de ménage", "ind_122"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "Ethnies minoritaires", "Ethnies minoritaires", "ind_123"),

        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "Date de la séance", "Date de la séance", "ind_124"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES (<=35)", "H", "ind_125"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES (<=35)", "F", "ind_126"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES (<=35)", "T", "ind_127"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES", "H", "ind_128"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES", "F", "ind_129"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES", "T", "ind_130"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "TOTAL PARTICIPANTS", "T", "ind_130_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES - REFUGIES (<=35)", "H", "ind_130_1"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES - REFUGIES (<=35)", "F", "ind_130_2"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES - REFUGIES (<=35)", "T", "ind_130_3"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES - REFUGIES", "H", "ind_130_4"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES - REFUGIES", "F", "ind_130_5"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES - REFUGIES", "T", "ind_130_6"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_130_6_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_130_7"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_130_8"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_130_9"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES - DEPLACES INTERNES", "H", "ind_130_10"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES - DEPLACES INTERNES", "F", "ind_130_11"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES - DEPLACES INTERNES", "T", "ind_130_12"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_130_12_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_130_13"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_130_14"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_130_15"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_130_16"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_130_17"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_130_18"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_130_18_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "Nombre total de ménage", "Nombre total de ménage", "ind_131"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "Ethnies minoritaires", "Ethnies minoritaires", "ind_132"),

        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "Date de la séance", "Date de la séance", "ind_133"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES (<=35)", "H", "ind_134"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES (<=35)", "F", "ind_135"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES (<=35)", "T", "ind_136"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES", "H", "ind_137"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES", "F", "ind_138"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES", "T", "ind_139"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "TOTAL PARTICIPANTS", "T", "ind_139_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES - REFUGIES (<=35)", "H", "ind_139_1"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES - REFUGIES (<=35)", "F", "ind_139_2"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES - REFUGIES (<=35)", "T", "ind_139_3"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES - REFUGIES", "H", "ind_139_4"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES - REFUGIES", "F", "ind_139_5"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES - REFUGIES", "T", "ind_139_6"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_139_6_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_139_7"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_139_8"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_139_9"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES - DEPLACES INTERNES", "H", "ind_139_10"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES - DEPLACES INTERNES", "F", "ind_139_11"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES - DEPLACES INTERNES", "T", "ind_139_12"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_139_12_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_139_13"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_139_14"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_139_15"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_139_16"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_139_17"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_139_18"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_139_18_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "Nombre total de ménage", "Nombre total de ménage", "ind_140"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "Ethnies minoritaires", "Ethnies minoritaires", "ind_141"),

        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "Date de la séance", "Date de la séance", "ind_142"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES (<=35)", "H", "ind_143"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES (<=35)", "F", "ind_144"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES (<=35)", "T", "ind_145"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES", "H", "ind_146"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES", "F", "ind_147"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES", "T", "ind_148"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "TOTAL PARTICIPANTS", "T", "ind_148_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES - REFUGIES (<=35)", "H", "ind_148_1"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES - REFUGIES (<=35)", "F", "ind_148_2"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES - REFUGIES (<=35)", "T", "ind_148_3"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES - REFUGIES", "H", "ind_148_4"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES - REFUGIES", "F", "ind_148_5"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES - REFUGIES", "T", "ind_148_6"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_148_6_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_148_7"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_148_8"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_148_9"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES - DEPLACES INTERNES", "H", "ind_148_10"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES - DEPLACES INTERNES", "F", "ind_148_11"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES - DEPLACES INTERNES", "T", "ind_148_12"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_148_12_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_148_13"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_148_14"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_148_15"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_148_16"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_148_17"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_148_18"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_148_18_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "Nombre total de ménage", "Nombre total de ménage", "ind_149"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "Ethnies minoritaires", "Ethnies minoritaires", "ind_150"),

        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "Date de la séance", "Date de la séance", "ind_151"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES (<=35)", "H", "ind_152"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES (<=35)", "F", "ind_153"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES (<=35)", "T", "ind_154"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES", "H", "ind_155"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES", "F", "ind_156"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES", "T", "ind_157"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "TOTAL PARTICIPANTS", "T", "ind_157_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES - REFUGIES (<=35)", "H", "ind_157_1"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES - REFUGIES (<=35)", "F", "ind_157_2"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES - REFUGIES (<=35)", "T", "ind_157_3"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES - REFUGIES", "H", "ind_157_4"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES - REFUGIES", "F", "ind_157_5"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES - REFUGIES", "T", "ind_157_6"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_157_6_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_157_7"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_157_8"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_157_9"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES - DEPLACES INTERNES", "H", "ind_157_10"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES - DEPLACES INTERNES", "F", "ind_157_11"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES - DEPLACES INTERNES", "T", "ind_157_12"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_157_12_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_157_13"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_157_14"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_157_15"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_157_16"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_157_17"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_157_18"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_157_18_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "Nombre total de ménage", "Nombre total de ménage", "ind_158"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "Ethnies minoritaires", "Ethnies minoritaires", "ind_159"),

        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "Date de la sensibilisation", "Date de la sensibilisation", "ind_160"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES (<=35)", "H", "ind_161"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES (<=35)", "F", "ind_162"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES (<=35)", "T", "ind_163"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES", "H", "ind_164"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES", "F", "ind_165"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES", "T", "ind_166"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "TOTAL PARTICIPANTS", "T", "ind_166_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES - REFUGIES (<=35)", "H", "ind_166_1"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES - REFUGIES (<=35)", "F", "ind_166_2"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES - REFUGIES (<=35)", "T", "ind_166_3"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES - REFUGIES", "H", "ind_166_4"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES - REFUGIES", "F", "ind_166_5"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES - REFUGIES", "T", "ind_166_6"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_166_6_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_166_7"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_166_8"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_166_9"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES - DEPLACES INTERNES", "H", "ind_166_10"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES - DEPLACES INTERNES", "F", "ind_166_11"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES - DEPLACES INTERNES", "T", "ind_166_12"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_166_12_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_166_13"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_166_14"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_166_15"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_166_16"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_166_17"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_166_18"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_166_18_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "Nombre total de ménage", "Nombre total de ménage", "ind_167"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "Ethnies minoritaires", "Ethnies minoritaires", "ind_168"),

        
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES (<=35)", "H", "ind_169"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES (<=35)", "F", "ind_170"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES (<=35)", "T", "ind_171"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES", "H", "ind_172"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES", "F", "ind_173"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES", "T", "ind_174"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "TOTAL PARTICIPANTS", "T", "ind_174_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES - REFUGIES (<=35)", "H", "ind_174_1"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES - REFUGIES (<=35)", "F", "ind_174_2"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES - REFUGIES (<=35)", "T", "ind_174_3"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES - REFUGIES", "H", "ind_174_4"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES - REFUGIES", "F", "ind_174_5"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES - REFUGIES", "T", "ind_174_6"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_174_6_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_174_7"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_174_8"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_174_9"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES - DEPLACES INTERNES", "H", "ind_174_10"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES - DEPLACES INTERNES", "F", "ind_174_11"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES - DEPLACES INTERNES", "T", "ind_174_12"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_174_12_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_174_13"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_174_14"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_174_15"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_174_16"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_174_17"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_174_18"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_174_18_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "Nombre total de ménage", "Nombre total de ménage", "ind_175"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "Ethnies minoritaires", "Ethnies minoritaires", "ind_176"),


        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "Observations", "Observations", "Observations", "Observations", "Observations", "ind_177"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "DB_NAME", "DB_NAME", "DB_NAME", "DB_NAME", "DB_NAME", "ind_178")
    ]
    cols = pd.MultiIndex.from_tuples(d_cols)
    datas = {}
    for col in d_cols:
        datas[col] = {}
    count = 0
    for f in fs.order_by("name", "username"):
        dict_administrative_levels_with_infos = {}
        already_count_facilitator = False
        facilitator_db = nsc.get_db(f.no_sql_db_name)
        query_result_docs = facilitator_db.all_docs(include_docs=True)['rows']
        f_doc = None
        cvds = []
        for doc in query_result_docs:
            doc = doc.get('doc')
            if doc.get('type') == "facilitator":
                f_doc = doc
                cvds = get_cvds(project.couch_id, cycle_id, f_doc)
                break
        query_result_docs = [doc for doc in query_result_docs if doc.get('doc') and doc.get('doc').get('cycle_id') == cycle_id and doc.get('doc').get('project_id') == project.couch_id]
        
        if f_doc:
            for cvd in cvds:
                administrative_level_cvd_village = cvd.get('village')
                if administrative_level_cvd_village:
                    # administrativelevel_obj = administrativelevels_models.AdministrativeLevel.objects.using('mis').get(id=int(administrative_level_cvd_village['id']))
                    administrativelevel_obj = project_mis.administrative_levels.filter(id=int(administrative_level_cvd_village['id'])).first()
                    
                    if administrativelevel_obj and administrativelevel_obj.cvd:
                        # _ok = True
                        # if liste_villages:
                        #     _ok = False
                        #     for village in liste_villages:
                        #         if str(administrative_level_cvd_village['id']) == str(village["administrative_id"]):
                        #             _ok = True
                        #             break
                        # if _ok:
                        if (facilitator_dbs_name and (
                            not params.get("ids_administrativelevel") or (params.get("ids_administrativelevel") and [v for v in liste_villages for v_c in administrativelevel_obj.cvd.get_villages() if str(v["administrative_id"]) == str(v_c.id)])
                        )) or (
                            not params.get("ids_administrativelevel") or (params.get("ids_administrativelevel") and [v for v in liste_villages for v_c in administrativelevel_obj.cvd.get_villages() if str(v["administrative_id"]) == str(v_c.id)])
                        ):
                            pass
                        else:
                            continue

                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "ID CVD", "ID CVD", "ID CVD", "ID CVD", "ID CVD", "ind_0")][count] = administrativelevel_obj.cvd.id #count + 1
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Région", "Région", "Région", "Région", "ind_1")][count] = administrativelevel_obj.parent.parent.parent.parent.name
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Préfecture", "Préfecture", "Préfecture", "Préfecture", "ind_2")][count] = administrativelevel_obj.parent.parent.parent.name
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Commune", "Commune", "Commune", "Commune", "ind_3")][count] = administrativelevel_obj.parent.parent.name
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Canton", "Canton", "Canton", "Canton", "ind_4")][count] = administrativelevel_obj.parent.name
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "CVD", "CVD", "CVD", "CVD", "ind_5")][count] = administrativelevel_obj.cvd.name
                        # villages = ""
                        # for o in administrativelevel_obj.cvd.get_villages():
                        #     villages += f'{o.name} ; '
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Villages", "Villages", "Villages", "Villages", "ind_6")][count] = ";".join([o.name for o in administrativelevel_obj.cvd.get_villages()])
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Unité géographique", "Unité géographique", "Unité géographique", "Unité géographique", "ind_7")][count] = administrativelevel_obj.geographical_unit.attributed_number_in_canton
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Nom de l'AC", "Nom de l'AC", "Nom de l'AC", "Nom de l'AC", "ind_8")][count] = f.name
                        
                        total_H, total_F, total_JEUNES_H, total_JEUNES_F, total_JEUNES, total_MENAGES, total_ETHNIES = 0, 0, 0, 0, 0, 0, 0
                        total_JEUNES_H_REFUGIES, total_JEUNES_F_REFUGIES, total_H_REFUGIES, total_F_REFUGIES = 0, 0, 0, 0
                        total_JEUNES_H_DEPLACES_INTERNES, total_JEUNES_F_DEPLACES_INTERNES, total_H_DEPLACES_INTERNES, total_F_DEPLACES_INTERNES = 0, 0, 0, 0
                        total_JEUNES_H_COMMUNAUTES_ACCUEIL, total_JEUNES_F_COMMUNAUTES_ACCUEIL, total_H_COMMUNAUTES_ACCUEIL, total_F_COMMUNAUTES_ACCUEIL = 0, 0, 0, 0
                        
                        for doc in query_result_docs:
                            _ = doc.get('doc')
                            if _.get('type') == "task" and str(administrative_level_cvd_village["id"]) == str(_["administrative_level_id"]):
                                form_response = _.get("form_response")
                                if form_response:
                                    value = None

                                    if _.get('sql_id') in [20] or comparer_chaines(_.get('name'), "Etablissement du profil du village"): #Etablissement du profil du village

                                        old_forms = _.get('old_forms')
                                        old_form_response = old_forms[-1].get("form_response") if old_forms else []

                                        # Eff. Population
                                        try:
                                            value = get_datas_dict(form_response, "population", 1)["populationTotaleDuVillage"]
                                        except Exception as exc:
                                            if not value:
                                                try:
                                                    value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["populationVillage"]
                                                except:
                                                    try:
                                                        value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["populationVillage"]
                                                    except:
                                                        value = None
                                        population = value
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Eff. Population", "Eff. Population", "Eff. Population", "ind_9")][count] = value
                                        # End Eff. Population


                                        """Réfugiés"""
                                        # "Eff. Population", "Réfugiés", "Eff. (<=35)", "H"
                                        population_refugees_young_h = None
                                        value = None
                                        try:
                                            try:
                                                value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalHommesMoins35Refugie"]
                                            except:
                                                value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalHommesMoins35Refugie"]
                                        except Exception as exc:
                                            value = None
                                        population_refugees_young_h = value
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Réfugiés", "Eff. (<=35)", "H", "ind_9_10")][count] = value
                                        # End "Eff. Population", "Réfugiés", "Eff. (<=35)", "H"

                                        # "Eff. Population", "Réfugiés", "Eff. (<=35)", "F"
                                        population_refugees_young_f = None
                                        value = None
                                        try:
                                            try:
                                                value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalFemmesMoins35Refugie"]
                                            except:
                                                value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalFemmesMoins35Refugie"]
                                        except Exception as exc:
                                            value = None
                                        population_refugees_young_f = value
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Réfugiés", "Eff. (<=35)", "F", "ind_9_11")][count] = value
                                        # End "Eff. Population", "Réfugiés", "Eff. (<=35)", "F"

                                        population_refugees_young = (population_refugees_young_f if population_refugees_young_f else 0) + (population_refugees_young_h if population_refugees_young_h else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Réfugiés", "Eff. (<=35)", "T", "ind_9_12")][count] = population_refugees_young


                                        # "Eff. Population", "Réfugiés", "Eff. (>35)", "H"
                                        population_refugees_old_h = None
                                        value = None
                                        try:
                                            try:
                                                value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalHommesPlus35Refugie"]
                                            except:
                                                value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalHommesPlus35Refugie"]
                                        except Exception as exc:
                                            value = None
                                        population_refugees_old_h = value
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Réfugiés", "Eff. (>35)", "H", "ind_9_13")][count] = value
                                        # End "Eff. Population", "Réfugiés", "Eff. (>35)", "H"

                                        # "Eff. Population", "Réfugiés", "Eff. (>35)", "F"
                                        population_refugees_old_f = None
                                        value = None
                                        try:
                                            try:
                                                value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalFemmesPlus35Refugie"]
                                            except:
                                                value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalFemmesPlus35Refugie"]
                                        except Exception as exc:
                                            value = None
                                        population_refugees_old_f = value
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Réfugiés", "Eff. (>35)", "F", "ind_9_14")][count] = value
                                        # End "Eff. Population", "Réfugiés", "Eff. (>35)", "F"
                                        
                                        population_refugees_old = (population_refugees_old_f if population_refugees_old_f else 0) + (population_refugees_old_h if population_refugees_old_h else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Réfugiés", "Eff. (>35)", "T", "ind_9_15")][count] = population_refugees_old

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Réfugiés", "Total", "T", "ind_9_16")][count] = population_refugees_young + population_refugees_old

                                        """End Réfugiés"""


                                        """Déplacés internes"""
                                        # "Eff. Population", "Déplacés internes", "Eff. (<=35)", "H"
                                        population_internally_displaced_persons_young_h = None
                                        value = None
                                        try:
                                            try:
                                                value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalHommesMoins35DeplaceInterne"]
                                            except:
                                                value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalHommesMoins35DeplaceInterne"]
                                        except Exception as exc:
                                            value = None
                                        population_internally_displaced_persons_young_h = value
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Déplacés internes", "Eff. (<=35)", "H", "ind_9_17")][count] = value
                                        # End "Eff. Population", "Déplacés internes", "Eff. (<=35)", "H"

                                        # "Eff. Population", "Déplacés internes", "Eff. (<=35)", "F"
                                        population_internally_displaced_persons_young_f = None
                                        value = None
                                        try:
                                            try:
                                                value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalFemmesMoins35DeplaceInterne"]
                                            except:
                                                value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalFemmesMoins35DeplaceInterne"]
                                        except Exception as exc:
                                            value = None
                                        population_internally_displaced_persons_young_f = value
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Déplacés internes", "Eff. (<=35)", "F", "ind_9_18")][count] = value
                                        # End "Eff. Population", "Déplacés internes", "Eff. (<=35)", "F"

                                        population_internally_displaced_persons_young = (population_internally_displaced_persons_young_f if population_internally_displaced_persons_young_f else 0) + (population_internally_displaced_persons_young_h if population_internally_displaced_persons_young_h else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Déplacés internes", "Eff. (<=35)", "T", "ind_9_19")][count] = population_internally_displaced_persons_young


                                        # "Eff. Population", "Déplacés internes", "Eff. (>35)", "H"
                                        population_internally_displaced_persons_old_h = None
                                        value = None
                                        try:
                                            try:
                                                value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalHommesPlus35DeplaceInterne"]
                                            except:
                                                value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalHommesPlus35DeplaceInterne"]
                                        except Exception as exc:
                                            value = None
                                        population_internally_displaced_persons_old_h = value
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Déplacés internes", "Eff. (>35)", "H", "ind_9_20")][count] = value
                                        # End "Eff. Population", "Déplacés internes", "Eff. (>35)", "H"

                                        # "Eff. Population", "Déplacés internes", "Eff. (>35)", "F"
                                        population_internally_displaced_persons_old_f = None
                                        value = None
                                        try:
                                            try:
                                                value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalFemmesPlus35DeplaceInterne"]
                                            except:
                                                value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalFemmesPlus35DeplaceInterne"]
                                        except Exception as exc:
                                            value = None
                                        population_internally_displaced_persons_old_f = value
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Déplacés internes", "Eff. (>35)", "F", "ind_9_21")][count] = value
                                        # End "Eff. Population", "Déplacés internes", "Eff. (>35)", "F"
                                        
                                        population_internally_displaced_persons_old = (population_internally_displaced_persons_old_f if population_internally_displaced_persons_old_f else 0) + (population_internally_displaced_persons_old_h if population_internally_displaced_persons_old_h else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Déplacés internes", "Eff. (>35)", "T", "ind_9_22")][count] = population_internally_displaced_persons_old

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Déplacés internes", "Total", "T", "ind_9_23")][count] = population_internally_displaced_persons_young + population_internally_displaced_persons_old

                                        """End Déplacés internes"""


                                        """Communautés d'accueil"""
                                        # "Eff. Population", "Communautés d'accueil", "Eff. (<=35)", "H"
                                        population_host_communities_young_h = None
                                        value = None
                                        try:
                                            try:
                                                value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalHommesMoins35Refugie"]
                                            except:
                                                value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalHommesMoins35Refugie"]
                                        except Exception as exc:
                                            value = None
                                        population_host_communities_young_h = value
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Communautés d'accueil", "Eff. (<=35)", "H", "ind_9_24")][count] = value
                                        # End "Eff. Population", "Communautés d'accueil", "Eff. (<=35)", "H"

                                        # "Eff. Population", "Communautés d'accueil", "Eff. (<=35)", "F"
                                        population_host_communities_young_f = None
                                        value = None
                                        try:
                                            try:
                                                value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalFemmesMoins35Refugie"]
                                            except:
                                                value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalFemmesMoins35Refugie"]
                                        except Exception as exc:
                                            value = None
                                        population_host_communities_young_f = value
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Communautés d'accueil", "Eff. (<=35)", "F", "ind_9_25")][count] = value
                                        # End "Eff. Population", "Communautés d'accueil", "Eff. (<=35)", "F"

                                        population_host_communities_young = (population_host_communities_young_f if population_host_communities_young_f else 0) + (population_host_communities_young_h if population_host_communities_young_h else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Communautés d'accueil", "Eff. (<=35)", "T", "ind_9_26")][count] = population_host_communities_young


                                        # "Eff. Population", "Communautés d'accueil", "Eff. (>35)", "H"
                                        population_host_communities_old_h = None
                                        value = None
                                        try:
                                            try:
                                                value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalHommesPlus35Refugie"]
                                            except:
                                                value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalHommesPlus35Refugie"]
                                        except Exception as exc:
                                            value = None
                                        population_host_communities_old_h = value
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Communautés d'accueil", "Eff. (>35)", "H", "ind_9_27")][count] = value
                                        # End "Eff. Population", "Communautés d'accueil", "Eff. (>35)", "H"

                                        # "Eff. Population", "Communautés d'accueil", "Eff. (>35)", "F"
                                        population_host_communities_old_f = None
                                        value = None
                                        try:
                                            try:
                                                value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalFemmesPlus35Refugie"]
                                            except:
                                                value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalFemmesPlus35Refugie"]
                                        except Exception as exc:
                                            value = None
                                        population_host_communities_old_f = value
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Communautés d'accueil", "Eff. (>35)", "F", "ind_9_28")][count] = value
                                        # End "Eff. Population", "Communautés d'accueil", "Eff. (>35)", "F"
                                        
                                        population_host_communities_old = (population_host_communities_old_f if population_host_communities_old_f else 0) + (population_host_communities_old_h if population_host_communities_old_h else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Communautés d'accueil", "Eff. (>35)", "T", "ind_9_29")][count] = population_host_communities_old

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Communautés d'accueil", "Total", "T", "ind_9_30")][count] = population_host_communities_young + population_host_communities_old

                                        """End Communautés d'accueil"""



                                        # "Eff. Population", "Eff. (<=35)", "H"
                                        population_young_h = None
                                        value = None
                                        percent_young_h = None
                                        try:
                                            try:
                                                value = get_datas_dict(form_response, "donnees", 1)["populationPersonnesJeunes"]["populationPersonnesJeunesTotal"]
                                                percent_young_h = get_datas_dict(form_response, "donnees", 1)["populationPersonnesJeunes"]["populationPersonnesJeunesProportionHomme"]
                                                percent_young_f = get_datas_dict(form_response, "donnees", 1)["populationPersonnesJeunes"]["populationPersonnesJeunesProportionFemmes"]
                                            except:
                                                value = get_datas_dict(old_form_response, "donnees", 1)["populationPersonnesJeunes"]["populationPersonnesJeunesTotal"]
                                                percent_young_h = get_datas_dict(old_form_response, "donnees", 1)["populationPersonnesJeunes"]["populationPersonnesJeunesProportionHomme"]
                                                percent_young_f = get_datas_dict(old_form_response, "donnees", 1)["populationPersonnesJeunes"]["populationPersonnesJeunesProportionFemmes"]

                                            if percent_young_f and percent_young_h:
                                                t = percent_young_f+percent_young_f
                                                if t == 100:
                                                    value = ((value*percent_young_h)/100) if value and percent_young_h else None
                                                else:
                                                    value = percent_young_h
                                        except Exception as exc:
                                            if not value:
                                                try:
                                                    value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalHommesMoins35"]
                                                except:
                                                    try:
                                                        value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalHommesMoins35"]
                                                    except:
                                                        value = None
                                        population_young_h = value if value else (population_refugees_young_h + population_internally_displaced_persons_young_h + population_host_communities_young_h if population_refugees_young_h != None and population_internally_displaced_persons_young_h != None and population_host_communities_young_h != None else None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Eff. Population", "Eff. (<=35)", "H", "ind_9_4")][count] = population_young_h
                                        # End "Eff. Population", "Eff. (<=35)", "H"

                                        # "Eff. Population", "Eff. (<=35)", "F"
                                        value = None
                                        percent_young_f = None
                                        population_young_f = None
                                        try:
                                            try:
                                                value = get_datas_dict(form_response, "donnees", 1)["populationPersonnesJeunes"]["populationPersonnesJeunesTotal"]
                                                percent_young_f = get_datas_dict(form_response, "donnees", 1)["populationPersonnesJeunes"]["populationPersonnesJeunesProportionFemmes"]
                                                percent_young_h = get_datas_dict(form_response, "donnees", 1)["populationPersonnesJeunes"]["populationPersonnesJeunesProportionHomme"]
                                            except:
                                                value = get_datas_dict(old_form_response, "donnees", 1)["populationPersonnesJeunes"]["populationPersonnesJeunesTotal"]
                                                percent_young_f = get_datas_dict(old_form_response, "donnees", 1)["populationPersonnesJeunes"]["populationPersonnesJeunesProportionFemmes"]
                                                percent_young_h = get_datas_dict(old_form_response, "donnees", 1)["populationPersonnesJeunes"]["populationPersonnesJeunesProportionHomme"]
                                                
                                            if percent_young_f and percent_young_h:
                                                t = percent_young_f+percent_young_f
                                                if t == 100:
                                                    value = ((value*percent_young_f)/100) if value and percent_young_f else None
                                                else:
                                                    value = percent_young_f
                                        except Exception as exc:
                                            if not value:
                                                try:
                                                    value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalFemmesMoins35"]
                                                except:
                                                    try:
                                                        value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalFemmesMoins35"]
                                                    except:
                                                        value = None
                                        population_young_f = value if value else (population_refugees_young_f + population_internally_displaced_persons_young_f + population_host_communities_young_f if population_refugees_young_f != None and population_internally_displaced_persons_young_f != None and population_host_communities_young_f != None else None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Eff. Population", "Eff. (<=35)", "F", "ind_9_5")][count] = population_young_f
                                        # End "Eff. Population", "Eff. (<=35)", "F"
                                        
                                        # "Eff. Population", "Eff. Jeunes"
                                        young = None
                                        value = None
                                        try:
                                            value = get_datas_dict(form_response, "donnees", 1)["populationPersonnesJeunes"]["populationPersonnesJeunesTotal"]
                                        except Exception as exc:
                                            try:
                                                value = get_datas_dict(old_form_response, "donnees", 1)["populationPersonnesJeunes"]["populationPersonnesJeunesTotal"]
                                            except Exception as exc:
                                                value = None
                                        young = value if value else ((population_young_f if population_young_f else 0) + (population_young_h if population_young_h else 0))
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Eff. Population", "Eff. Population", "Eff. Jeunes", "ind_9_3")][count] = young
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Eff. Population", "Eff. (<=35)", "T", "ind_9_6")][count] = young
                                        # End "Eff. Population", "Eff. Jeunes"

                                        # "Eff. Population", "Eff. (>35)", "H"
                                        population_old_h = None
                                        try:
                                            value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalHommesPlus35"]
                                        except:
                                            try:
                                                value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalHommesPlus35"]
                                            except:
                                                value = None
                                        population_old_h = value if value else (population_refugees_old_h + population_internally_displaced_persons_old_h + population_host_communities_old_h if population_refugees_old_h != None and population_internally_displaced_persons_old_h != None and population_host_communities_old_h != None else None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Eff. Population", "Eff. (>35)", "H", "ind_9_7")][count] = population_old_h
                                        # End "Eff. Population", "Eff. (>35)", "H"

                                        # "Eff. Population", "Eff. (>35)", "F"
                                        population_old_f = None
                                        try:
                                            value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalFemmesPlus35"]
                                        except:
                                            try:
                                                value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalFemmesPlus35"]
                                            except:
                                                value = None
                                        population_old_f = value if value else (population_refugees_old_f + population_internally_displaced_persons_old_f + population_host_communities_old_f if population_refugees_old_f != None and population_internally_displaced_persons_old_f != None and population_host_communities_old_f != None else None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Eff. Population", "Eff. (>35)", "F", "ind_9_8")][count] = population_old_f
                                        # End "Eff. Population", "Eff. (>35)", "F"

                                        old = ((population_old_f if population_old_f else 0)+(population_old_h if population_old_h else 0)) if population_old_f or population_old_h else (population - young if population and young else None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Eff. Population", "Eff. (>35)", "T", "ind_9_9")][count] = old

                                        
                                        value = None
                                        try:
                                            value = get_datas_dict(form_response, "population", 1)["populationNombreDeHommes"]
                                        except Exception as exc:
                                            try:
                                                value = get_datas_dict(old_form_response, "population", 1)["populationNombreDeHommes"]
                                            except Exception as exc:
                                                value = None
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Eff. Population", "Eff. Population", "Eff. Hommes", "ind_9_1")][count] = value if value else ((population_old_h if population_old_h else 0) + (population_young_h if population_young_h else 0) if population_old_h or population_young_h else None)

                                        value = None
                                        try:
                                            value = get_datas_dict(form_response, "population", 1)["populationNombreDeFemmes"]
                                        except Exception as exc:
                                            try:
                                                value = get_datas_dict(old_form_response, "population", 1)["populationNombreDeFemmes"]
                                            except Exception as exc:
                                                value = None
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Eff. Population", "Eff. Population", "Eff. Femmes", "ind_9_2")][count] = value if value else ((population_old_f if population_old_f else 0) + (population_young_f if population_young_f else 0) if population_old_f or population_young_f else None)



                                        try:
                                            value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalHouseHolds"]
                                        except Exception as exc:
                                            try:
                                                value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalHouseHolds"]
                                            except Exception as exc:
                                                value = None
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Nbre total ménages dans le village", "Nbre total ménages dans le village", "Nbre total ménages dans le village", "Nbre total ménages dans le village", "ind_10")][count] = value

                                        try:
                                            value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["nombreEthniques"]
                                        except Exception as exc:
                                            try:
                                                value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["nombreEthniques"]
                                            except Exception as exc:
                                                value = None
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Nbre total groupes ethniques dans le village", "Nbre total groupes ethniques dans le village", "Nbre total groupes ethniques dans le village", "Nbre total groupes ethniques dans le village", "ind_10_1")][count] = value


                                       
                                    elif _.get('sql_id') in [13] or comparer_chaines(_.get('name'), "Introduction et présentation de l'AC par l'AADB lors de la première réunion cantonale"): #Introduction et présentation de l'AC par l'AADB lors de la première réunion cantonale
                            
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "Date de la séance", "Date de la séance", "ind_11")][count] = safe_get(form_response, 0).get("dateDeLaReunion", None)
                                        

                                        totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES - REFUGIES (<=35)", "H", "ind_17_1")][count] = totalHommesMoins35Refugie
                                        
                                        totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES - REFUGIES (<=35)", "F", "ind_17_2")][count] = totalFemmesMoins35Refugie

                                        totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES - REFUGIES (<=35)", "T", "ind_17_3")][count] = totalMoins35Refugie

                                        totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES - REFUGIES", "H", "ind_17_4")][count] = totalHommesPlus35Refugie

                                        totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES - REFUGIES", "F", "ind_17_5")][count] = totalFemmesPlus35Refugie

                                        totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES - REFUGIES", "T", "ind_17_6")][count] = totalPlus35Refugie

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_17_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                                        


                                        totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_17_7")][count] = totalHommesMoins35DeplaceInterne
                                        
                                        totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_17_8")][count] = totalFemmesMoins35DeplaceInterne

                                        totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_17_9")][count] = totalMoins35DeplaceInterne

                                        totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES - DEPLACES INTERNES", "H", "ind_17_10")][count] = totalHommesPlus35DeplaceInterne

                                        totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES - DEPLACES INTERNES", "F", "ind_17_11")][count] = totalFemmesPlus35DeplaceInterne

                                        totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES - DEPLACES INTERNES", "T", "ind_17_12")][count] = totalPlus35DeplaceInterne

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_17_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                                        


                                        totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_17_13")][count] = totalHommesMoins35CommunauteAcceuil
                                        
                                        totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_17_14")][count] = totalFemmesMoins35CommunauteAcceuil

                                        totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_17_15")][count] = totalMoins35CommunauteAcceuil

                                        totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_17_16")][count] = totalHommesPlus35CommunauteAcceuil

                                        totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_17_17")][count] = totalFemmesPlus35CommunauteAcceuil

                                        totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_17_18")][count] = totalPlus35CommunauteAcceuil

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_17_19_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                                        
                                        
                                        if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                            totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                                        else:
                                            totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES (<=35)", "H", "ind_12")][count] = totalHommesMoins35
                                        
                                        if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                            totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                                        else:
                                            totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES (<=35)", "F", "ind_13")][count] = totalFemmesMoins35

                                        if totalHommesMoins35 or totalFemmesMoins35:
                                            totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                                        else:
                                            totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES (<=35)", "T", "ind_14")][count] = totalMoins35

                                        if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                            totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                                        else:
                                            totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES", "H", "ind_15")][count] = totalHommes

                                        if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                            totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                                        else:
                                            totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES", "F", "ind_16")][count] = totalFemmes

                                        if totalHommes or totalFemmes:
                                            totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                                        else:
                                            totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES", "T", "ind_17")][count] = totalPlus35

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "TOTAL PARTICIPANTS", "T", "ind_17_0")][count] = totalPlus35 + totalMoins35


                                    elif _.get('sql_id') in [17] or comparer_chaines(_.get('name'), "Présentation et clarification de votre mission"): #Présentation et clarification de votre mission
                                        
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "Date de la séance", "Date de la séance", "ind_18")][count] = get_datas_dict(form_response, "dateDeLaReunion", 1, None)


                                        totalHommesMoins35Refugie = get_datas_dict(form_response, "totalPersonnes", 1).get("totalHommesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES - REFUGIES (<=35)", "H", "ind_24_1")][count] = totalHommesMoins35Refugie
                                        
                                        totalFemmesMoins35Refugie = get_datas_dict(form_response, "totalPersonnes", 1).get("totalFemmesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES - REFUGIES (<=35)", "F", "ind_24_2")][count] = totalFemmesMoins35Refugie

                                        totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES - REFUGIES (<=35)", "T", "ind_24_3")][count] = totalMoins35Refugie

                                        totalHommesPlus35Refugie = get_datas_dict(form_response, "totalPersonnes", 1).get("totalHommesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES - REFUGIES", "H", "ind_24_4")][count] = totalHommesPlus35Refugie

                                        totalFemmesPlus35Refugie = get_datas_dict(form_response, "totalPersonnes", 1).get("totalFemmesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES - REFUGIES", "F", "ind_24_5")][count] = totalFemmesPlus35Refugie

                                        totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES - REFUGIES", "T", "ind_24_6")][count] = totalPlus35Refugie

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_24_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                                        


                                        totalHommesMoins35DeplaceInterne = get_datas_dict(form_response, "totalPersonnes", 1).get("totalHommesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_24_7")][count] = totalHommesMoins35DeplaceInterne
                                        
                                        totalFemmesMoins35DeplaceInterne = get_datas_dict(form_response, "totalPersonnes", 1).get("totalFemmesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_24_8")][count] = totalFemmesMoins35DeplaceInterne

                                        totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_24_9")][count] = totalMoins35DeplaceInterne

                                        totalHommesPlus35DeplaceInterne = get_datas_dict(form_response, "totalPersonnes", 1).get("totalHommesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES - DEPLACES INTERNES", "H", "ind_24_10")][count] = totalHommesPlus35DeplaceInterne

                                        totalFemmesPlus35DeplaceInterne = get_datas_dict(form_response, "totalPersonnes", 1).get("totalFemmesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES - DEPLACES INTERNES", "F", "ind_24_11")][count] = totalFemmesPlus35DeplaceInterne

                                        totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES - DEPLACES INTERNES", "T", "ind_24_12")][count] = totalPlus35DeplaceInterne

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_24_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                                        


                                        totalHommesMoins35CommunauteAcceuil = get_datas_dict(form_response, "totalPersonnes", 1).get("totalHommesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_24_13")][count] = totalHommesMoins35CommunauteAcceuil
                                        
                                        totalFemmesMoins35CommunauteAcceuil = get_datas_dict(form_response, "totalPersonnes", 1).get("totalFemmesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_24_14")][count] = totalFemmesMoins35CommunauteAcceuil

                                        totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_24_15")][count] = totalMoins35CommunauteAcceuil

                                        totalHommesPlus35CommunauteAcceuil = get_datas_dict(form_response, "totalPersonnes", 1).get("totalHommesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_24_16")][count] = totalHommesPlus35CommunauteAcceuil

                                        totalFemmesPlus35CommunauteAcceuil = get_datas_dict(form_response, "totalPersonnes", 1).get("totalFemmesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_24_17")][count] = totalFemmesPlus35CommunauteAcceuil

                                        totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_24_18")][count] = totalPlus35CommunauteAcceuil

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_24_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                                        


                                        if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                            totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                                        else:
                                            totalHommesMoins35 = get_datas_dict(form_response, "totalPersonnes", 1).get('totalHommesMoins35', None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES (<=35)", "H", "ind_19")][count] = totalHommesMoins35

                                        if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                            totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                                        else:
                                            totalFemmesMoins35 = get_datas_dict(form_response, "totalPersonnes", 1).get('totalFemmesMoins35', None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES (<=35)", "F", "ind_20")][count] = totalFemmesMoins35

                                        if totalHommesMoins35 or totalFemmesMoins35:
                                            totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                                        else:
                                            totalMoins35 = get_datas_dict(form_response, "totalPersonnes", 1).get('totalMoins35', 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES (<=35)", "T", "ind_21")][count] = totalMoins35

                                        if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                            totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                                        else:
                                            totalHommes = get_datas_dict(form_response, "totalPersonnes", 1).get('totalHommes', None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES", "H", "ind_22")][count] = totalHommes

                                        if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                            totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                                        else:
                                            totalFemmes = get_datas_dict(form_response, "totalPersonnes", 1).get('totalFemmes', None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES", "F", "ind_23")][count] = totalFemmes

                                        if totalHommes or totalFemmes:
                                            totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                                        else:
                                            totalPlus35 = get_datas_dict(form_response, "totalPersonnes", 1).get('totalPlus35', 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES", "T", "ind_24")][count] = totalPlus35

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "TOTAL PARTICIPANTS", "T", "ind_24_0")][count] = totalPlus35 + totalMoins35
                                        

                                    elif _.get('sql_id') in [22] or comparer_chaines(_.get('name'), "Brève introduction de la réunion et de l'ANADEB"): #Brève introduction de la réunion et de l'ANADEB
                                        
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "Date de la séance", "Date de la séance", "ind_25")][count] = safe_get(form_response, 0).get("dateDeLaReunion", None)


                                        totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES - REFUGIES (<=35)", "H", "ind_31_1")][count] = totalHommesMoins35Refugie
                                        
                                        totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES - REFUGIES (<=35)", "F", "ind_31_2")][count] = totalFemmesMoins35Refugie

                                        totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES - REFUGIES (<=35)", "T", "ind_31_3")][count] = totalMoins35Refugie

                                        totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES - REFUGIES", "H", "ind_31_4")][count] = totalHommesPlus35Refugie

                                        totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES - REFUGIES", "F", "ind_31_5")][count] = totalFemmesPlus35Refugie

                                        totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES - REFUGIES", "T", "ind_31_6")][count] = totalPlus35Refugie

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_31_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                                        


                                        totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_31_7")][count] = totalHommesMoins35DeplaceInterne
                                        
                                        totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_31_8")][count] = totalFemmesMoins35DeplaceInterne

                                        totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_31_9")][count] = totalMoins35DeplaceInterne

                                        totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES - DEPLACES INTERNES", "H", "ind_31_10")][count] = totalHommesPlus35DeplaceInterne

                                        totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES - DEPLACES INTERNES", "F", "ind_31_11")][count] = totalFemmesPlus35DeplaceInterne

                                        totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES - DEPLACES INTERNES", "T", "ind_31_12")][count] = totalPlus35DeplaceInterne

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_31_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                                        

                                        totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_31_13")][count] = totalHommesMoins35CommunauteAcceuil
                                        
                                        totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_31_14")][count] = totalFemmesMoins35CommunauteAcceuil

                                        totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_31_15")][count] = totalMoins35CommunauteAcceuil

                                        totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_31_16")][count] = totalHommesPlus35CommunauteAcceuil

                                        totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_31_17")][count] = totalFemmesPlus35CommunauteAcceuil

                                        totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_31_18")][count] = totalPlus35CommunauteAcceuil

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_31_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                                        

                                        
                                        if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                            totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                                        else:
                                            totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES (<=35)", "H", "ind_26")][count] = totalHommesMoins35
                                        
                                        if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                            totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                                        else:
                                            totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES (<=35)", "F", "ind_27")][count] = totalFemmesMoins35

                                        if totalHommesMoins35 or totalFemmesMoins35:
                                            totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                                        else:
                                            totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES (<=35)", "T", "ind_28")][count] = totalMoins35

                                        if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                            totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                                        else:
                                            totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES", "H", "ind_29")][count] = totalHommes

                                        if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                            totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                                        else:
                                            totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES", "F", "ind_30")][count] = totalFemmes

                                        if totalHommes or totalFemmes:
                                            totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                                        else:
                                            totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES", "T", "ind_31")][count] = totalPlus35

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "TOTAL PARTICIPANTS", "T", "ind_31_0")][count] = totalPlus35 + totalMoins35

                                        
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "Nombre total de ménage", "Nombre total de ménage", "ind_32")][count] = safe_get(form_response, 0).get("totalMenages", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "Ethnies minoritaires", "Ethnies minoritaires", "ind_33")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                                    elif _.get('sql_id') in [27] or comparer_chaines(_.get('name'), "Ouverture de la deuxième réunion et vérification du quorum des participants"): #Ouverture de la deuxième réunion et vérification du quorum des participants
                                        
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "Date de la séance", "Date de la séance", "ind_34")][count] = safe_get(form_response, 0).get("dateDeLaReunion", None)
                                                                

                                        totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES - REFUGIES (<=35)", "H", "ind_40_1")][count] = totalHommesMoins35Refugie
                                        
                                        totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES - REFUGIES (<=35)", "F", "ind_40_2")][count] = totalFemmesMoins35Refugie

                                        totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES - REFUGIES (<=35)", "T", "ind_40_3")][count] = totalMoins35Refugie

                                        totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES - REFUGIES", "H", "ind_40_4")][count] = totalHommesPlus35Refugie

                                        totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES - REFUGIES", "F", "ind_40_5")][count] = totalFemmesPlus35Refugie

                                        totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES - REFUGIES", "T", "ind_40_6")][count] = totalPlus35Refugie

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_40_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                                        


                                        totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_40_7")][count] = totalHommesMoins35DeplaceInterne
                                        
                                        totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_40_8")][count] = totalFemmesMoins35DeplaceInterne

                                        totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_40_9")][count] = totalMoins35DeplaceInterne

                                        totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "H", "ind_40_10")][count] = totalHommesPlus35DeplaceInterne

                                        totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "F", "ind_40_11")][count] = totalFemmesPlus35DeplaceInterne

                                        totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "T", "ind_40_12")][count] = totalPlus35DeplaceInterne

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_40_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                                        

                                        totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_40_13")][count] = totalHommesMoins35CommunauteAcceuil
                                        
                                        totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_40_14")][count] = totalFemmesMoins35CommunauteAcceuil

                                        totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_40_15")][count] = totalMoins35CommunauteAcceuil

                                        totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_40_16")][count] = totalHommesPlus35CommunauteAcceuil

                                        totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_40_17")][count] = totalFemmesPlus35CommunauteAcceuil

                                        totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_40_18")][count] = totalPlus35CommunauteAcceuil

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_40_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                                        
                                        
                                        
                                        if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                            totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                                        else:
                                            totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES (<=35)", "H", "ind_35")][count] = totalHommesMoins35
                                        
                                        if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                            totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                                        else:
                                            totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES (<=35)", "F", "ind_36")][count] = totalFemmesMoins35

                                        if totalHommesMoins35 or totalFemmesMoins35:
                                            totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                                        else:
                                            totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES (<=35)", "T", "ind_37")][count] = totalMoins35

                                        if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                            totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                                        else:
                                            totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES", "H", "ind_38")][count] = totalHommes

                                        if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                            totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                                        else:
                                            totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES", "F", "ind_39")][count] = totalFemmes

                                        if totalHommes or totalFemmes:
                                            totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                                        else:
                                            totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES", "T", "ind_40")][count] = totalPlus35

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "TOTAL PARTICIPANTS", "T", "ind_40_0")][count] = totalPlus35 + totalMoins35


                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "Nombre total de ménage", "Nombre total de ménage", "ind_41")][count] = safe_get(form_response, 0).get("totalMenages", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "Ethnies minoritaires", "Ethnies minoritaires", "ind_42")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                                    elif _.get('sql_id') in [37] or comparer_chaines(_.get('name'), "Animer la session de formation sur le Module 1 : rôles et responsabilités des membres des organes de CVD"): #Animer la session de formation sur le Module 1 : rôles et responsabilités des membres des organes de CVD
                                        
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "Date de la séance", "Date de la séance", "ind_43")][count] = safe_get(form_response, 0).get("DateDeLaFormation", None)


                                        totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES - REFUGIES (<=35)", "H", "ind_49_1")][count] = totalHommesMoins35Refugie
                                        
                                        totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES - REFUGIES (<=35)", "F", "ind_49_2")][count] = totalFemmesMoins35Refugie

                                        totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES - REFUGIES (<=35)", "T", "ind_49_3")][count] = totalMoins35Refugie

                                        totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES - REFUGIES", "H", "ind_49_4")][count] = totalHommesPlus35Refugie

                                        totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES - REFUGIES", "F", "ind_49_5")][count] = totalFemmesPlus35Refugie

                                        totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES - REFUGIES", "T", "ind_49_6")][count] = totalPlus35Refugie

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_49_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                                        


                                        totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_49_7")][count] = totalHommesMoins35DeplaceInterne
                                        
                                        totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_49_8")][count] = totalFemmesMoins35DeplaceInterne

                                        totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_49_9")][count] = totalMoins35DeplaceInterne

                                        totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES - DEPLACES INTERNES", "H", "ind_49_10")][count] = totalHommesPlus35DeplaceInterne

                                        totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES - DEPLACES INTERNES", "F", "ind_49_11")][count] = totalFemmesPlus35DeplaceInterne

                                        totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES - DEPLACES INTERNES", "T", "ind_49_12")][count] = totalPlus35DeplaceInterne

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_49_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                                        
                                        

                                        totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_49_13")][count] = totalHommesMoins35CommunauteAcceuil
                                        
                                        totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_49_14")][count] = totalFemmesMoins35CommunauteAcceuil

                                        totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_49_15")][count] = totalMoins35CommunauteAcceuil

                                        totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_49_16")][count] = totalHommesPlus35CommunauteAcceuil

                                        totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_49_17")][count] = totalFemmesPlus35CommunauteAcceuil

                                        totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_49_18")][count] = totalPlus35CommunauteAcceuil

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_49_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                                        
                                        
                                        
                                        if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                            totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                                        else:
                                            totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES (<=35)", "H", "ind_44")][count] = totalHommesMoins35
                                        
                                        if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                            totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                                        else:
                                            totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES (<=35)", "F", "ind_45")][count] = totalFemmesMoins35

                                        if totalHommesMoins35 or totalFemmesMoins35:
                                            totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                                        else:
                                            totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES (<=35)", "T", "ind_46")][count] = totalMoins35

                                        if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                            totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                                        else:
                                            totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES", "H", "ind_47")][count] = totalHommes

                                        if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                            totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                                        else:
                                            totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES", "F", "ind_48")][count] = totalFemmes

                                        if totalHommes or totalFemmes:
                                            totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                                        else:
                                            totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES", "T", "ind_49")][count] = totalPlus35

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "TOTAL PARTICIPANTS", "T", "ind_49_0")][count] = totalPlus35 + totalMoins35


                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "Nombre total de ménage", "Nombre total de ménage", "ind_50")][count] = safe_get(form_response, 0).get("totalMenages", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "Ethnies minoritaires", "Ethnies minoritaires", "ind_51")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                                    elif _.get('sql_id') in [41] or comparer_chaines(_.get('name'), "Présenter les activités de la journée"): #Présenter les activités de la journée

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "Date de la séance", "Date de la séance", "ind_52")][count] = safe_get(form_response, 0).get("dateDeLaReunion", None)


                                        totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES - REFUGIES (<=35)", "H", "ind_58_1")][count] = totalHommesMoins35Refugie
                                        
                                        totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES - REFUGIES (<=35)", "F", "ind_58_2")][count] = totalFemmesMoins35Refugie

                                        totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES - REFUGIES (<=35)", "T", "ind_58_3")][count] = totalMoins35Refugie

                                        totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES - REFUGIES", "H", "ind_58_4")][count] = totalHommesPlus35Refugie

                                        totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES - REFUGIES", "F", "ind_58_5")][count] = totalFemmesPlus35Refugie

                                        totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES - REFUGIES", "T", "ind_58_6")][count] = totalPlus35Refugie

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_58_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                                        


                                        totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_58_7")][count] = totalHommesMoins35DeplaceInterne
                                        
                                        totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_58_8")][count] = totalFemmesMoins35DeplaceInterne

                                        totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_58_9")][count] = totalMoins35DeplaceInterne

                                        totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "H", "ind_58_10")][count] = totalHommesPlus35DeplaceInterne

                                        totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "F", "ind_58_11")][count] = totalFemmesPlus35DeplaceInterne

                                        totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "T", "ind_58_12")][count] = totalPlus35DeplaceInterne

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_58_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                                        
                                        

                                        totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_58_13")][count] = totalHommesMoins35CommunauteAcceuil
                                        
                                        totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_58_14")][count] = totalFemmesMoins35CommunauteAcceuil

                                        totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_58_15")][count] = totalMoins35CommunauteAcceuil

                                        totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_58_16")][count] = totalHommesPlus35CommunauteAcceuil

                                        totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_58_17")][count] = totalFemmesPlus35CommunauteAcceuil

                                        totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_58_18")][count] = totalPlus35CommunauteAcceuil

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_58_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil


                                        
                                        if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                            totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                                        else:
                                            totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES (<=35)", "H", "ind_53")][count] = totalHommesMoins35
                                        
                                        if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                            totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                                        else:
                                            totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES (<=35)", "F", "ind_54")][count] = totalFemmesMoins35

                                        if totalHommesMoins35 or totalFemmesMoins35:
                                            totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                                        else:
                                            totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES (<=35)", "T", "ind_55")][count] = totalMoins35

                                        if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                            totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                                        else:
                                            totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES", "H", "ind_56")][count] = totalHommes

                                        if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                            totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                                        else:
                                            totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES", "F", "ind_57")][count] = totalFemmes

                                        if totalHommes or totalFemmes:
                                            totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                                        else:
                                            totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES", "T", "ind_58")][count] = totalPlus35

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "TOTAL PARTICIPANTS", "T", "ind_58_0")][count] = totalPlus35 + totalMoins35


                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "Nombre total de ménage", "Nombre total de ménage", "ind_59")][count] = safe_get(form_response, 0).get("totalMenages", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "Ethnies minoritaires", "Ethnies minoritaires", "ind_60")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                                    elif _.get('sql_id') in [45] or comparer_chaines(_.get('name'), "Elaboration du plan d'action villageois (PAV)"): #Elaboration du plan d'action villageois (PAV)
                                        
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "Date de la séance", "Date de la séance", "ind_61")][count] = safe_get(form_response, 0).get("dateDeLaReunion", None)


                                        totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES - REFUGIES (<=35)", "H", "ind_67_1")][count] = totalHommesMoins35Refugie
                                        
                                        totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES - REFUGIES (<=35)", "F", "ind_67_2")][count] = totalFemmesMoins35Refugie

                                        totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES - REFUGIES (<=35)", "T", "ind_67_3")][count] = totalMoins35Refugie

                                        totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES - REFUGIES", "H", "ind_67_4")][count] = totalHommesPlus35Refugie

                                        totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES - REFUGIES", "F", "ind_67_5")][count] = totalFemmesPlus35Refugie

                                        totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES - REFUGIES", "T", "ind_67_6")][count] = totalPlus35Refugie

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_67_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                                        


                                        totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_67_7")][count] = totalHommesMoins35DeplaceInterne
                                        
                                        totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_67_8")][count] = totalFemmesMoins35DeplaceInterne

                                        totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_67_9")][count] = totalMoins35DeplaceInterne

                                        totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "H", "ind_67_10")][count] = totalHommesPlus35DeplaceInterne

                                        totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "F", "ind_67_11")][count] = totalFemmesPlus35DeplaceInterne

                                        totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "T", "ind_67_12")][count] = totalPlus35DeplaceInterne

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_67_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                                        
                                        

                                        totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_67_13")][count] = totalHommesMoins35CommunauteAcceuil
                                        
                                        totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_67_14")][count] = totalFemmesMoins35CommunauteAcceuil

                                        totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_67_15")][count] = totalMoins35CommunauteAcceuil

                                        totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_67_16")][count] = totalHommesPlus35CommunauteAcceuil

                                        totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_67_17")][count] = totalFemmesPlus35CommunauteAcceuil

                                        totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_67_18")][count] = totalPlus35CommunauteAcceuil

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_67_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                                        

                                        
                                        if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                            totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                                        else:
                                            totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES (<=35)", "H", "ind_62")][count] = totalHommesMoins35
                                        
                                        if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                            totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                                        else:
                                            totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES (<=35)", "F", "ind_63")][count] = totalFemmesMoins35

                                        if totalHommesMoins35 or totalFemmesMoins35:
                                            totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                                        else:
                                            totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES (<=35)", "T", "ind_64")][count] = totalMoins35

                                        if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                            totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                                        else:
                                            totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES", "H", "ind_65")][count] = totalHommes

                                        if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                            totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                                        else:
                                            totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES", "F", "ind_66")][count] = totalFemmes

                                        if totalHommes or totalFemmes:
                                            totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                                        else:
                                            totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES", "T", "ind_67")][count] = totalPlus35

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "TOTAL PARTICIPANTS", "T", "ind_67_0")][count] = totalPlus35 + totalMoins35


                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "Nombre total de ménage", "Nombre total de ménage", "ind_68")][count] = safe_get(form_response, 0).get("totalMenages", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "Ethnies minoritaires", "Ethnies minoritaires", "ind_69")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                                    elif _.get('sql_id') in [46] or comparer_chaines(_.get('name'), "Mise en place et/ou restructuration du comité cantonal de développement (CCD)  et du comité cantonal de gestion des plaintes (CCGP)"): #Mise en place et/ou restructuration du comité cantonal de développement (CCD)  et du comité cantonal de gestion des plaintes (CCGP)
                                        
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "Date de la séance", "Date de la séance", "ind_70")][count] = safe_get(form_response, 0).get("dateDeLaReunion", None)


                                        totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES - REFUGIES (<=35)", "H", "ind_76_1")][count] = totalHommesMoins35Refugie
                                        
                                        totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES - REFUGIES (<=35)", "F", "ind_76_2")][count] = totalFemmesMoins35Refugie

                                        totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES - REFUGIES (<=35)", "T", "ind_76_3")][count] = totalMoins35Refugie

                                        totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES - REFUGIES", "H", "ind_76_4")][count] = totalHommesPlus35Refugie

                                        totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES - REFUGIES", "F", "ind_76_5")][count] = totalFemmesPlus35Refugie

                                        totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES - REFUGIES", "T", "ind_76_6")][count] = totalPlus35Refugie

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_76_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                                        


                                        totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_76_7")][count] = totalHommesMoins35DeplaceInterne
                                        
                                        totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_76_8")][count] = totalFemmesMoins35DeplaceInterne

                                        totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_76_9")][count] = totalMoins35DeplaceInterne

                                        totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES - DEPLACES INTERNES", "H", "ind_76_10")][count] = totalHommesPlus35DeplaceInterne

                                        totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES - DEPLACES INTERNES", "F", "ind_76_11")][count] = totalFemmesPlus35DeplaceInterne

                                        totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES - DEPLACES INTERNES", "T", "ind_76_12")][count] = totalPlus35DeplaceInterne

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_76_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                                        
                                        

                                        totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_76_13")][count] = totalHommesMoins35CommunauteAcceuil
                                        
                                        totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_76_14")][count] = totalFemmesMoins35CommunauteAcceuil

                                        totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_76_15")][count] = totalMoins35CommunauteAcceuil

                                        totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_76_16")][count] = totalHommesPlus35CommunauteAcceuil

                                        totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_76_17")][count] = totalFemmesPlus35CommunauteAcceuil

                                        totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_76_18")][count] = totalPlus35CommunauteAcceuil

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_76_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                                        

                                        
                                        if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                            totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                                        else:
                                            totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES (<=35)", "H", "ind_71")][count] = totalHommesMoins35
                                        
                                        if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                            totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                                        else:
                                            totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES (<=35)", "F", "ind_72")][count] = totalFemmesMoins35

                                        if totalHommesMoins35 or totalFemmesMoins35:
                                            totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                                        else:
                                            totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES (<=35)", "T", "ind_73")][count] = totalMoins35

                                        if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                            totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                                        else:
                                            totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES", "H", "ind_74")][count] = totalHommes

                                        if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                            totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                                        else:
                                            totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES", "F", "ind_75")][count] = totalFemmes

                                        if totalHommes or totalFemmes:
                                            totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                                        else:
                                            totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES", "T", "ind_76")][count] = totalPlus35

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "TOTAL PARTICIPANTS", "T", "ind_76_0")][count] = totalPlus35 + totalMoins35


                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "Nombre total de ménage", "Nombre total de ménage", "ind_77")][count] = safe_get(form_response, 0).get("totalMenages", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "Ethnies minoritaires", "Ethnies minoritaires", "ind_78")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                                    elif _.get('sql_id') in [47] or comparer_chaines(_.get('name'), "Appui au CCD dans  l'analyse des PAV des villages, l'arbitrage, la sélection des sous - projets à financer et l'affection des ressources par sous - projet"): #Appui au CCD dans  l'analyse des PAV des villages, l'arbitrage, la sélection des sous - projets à financer et l'affection des ressources par sous - projet
                                        
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "Date de la séance", "Date de la séance", "ind_79")][count] = safe_get(form_response, 0).get("dateDeLaReunion", None)

                                        
                                        totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES - REFUGIES (<=35)", "H", "ind_85_1")][count] = totalHommesMoins35Refugie
                                        
                                        totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES - REFUGIES (<=35)", "F", "ind_85_2")][count] = totalFemmesMoins35Refugie

                                        totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES - REFUGIES (<=35)", "T", "ind_85_3")][count] = totalMoins35Refugie

                                        totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES - REFUGIES", "H", "ind_85_4")][count] = totalHommesPlus35Refugie

                                        totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES - REFUGIES", "F", "ind_85_5")][count] = totalFemmesPlus35Refugie

                                        totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES - REFUGIES", "T", "ind_85_6")][count] = totalPlus35Refugie

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_85_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                                        


                                        totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_85_7")][count] = totalHommesMoins35DeplaceInterne
                                        
                                        totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_85_8")][count] = totalFemmesMoins35DeplaceInterne

                                        totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_85_9")][count] = totalMoins35DeplaceInterne

                                        totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES - DEPLACES INTERNES", "H", "ind_85_10")][count] = totalHommesPlus35DeplaceInterne

                                        totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES - DEPLACES INTERNES", "F", "ind_85_11")][count] = totalFemmesPlus35DeplaceInterne

                                        totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES - DEPLACES INTERNES", "T", "ind_85_12")][count] = totalPlus35DeplaceInterne

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_85_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                                        
                                        

                                        totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_85_13")][count] = totalHommesMoins35CommunauteAcceuil
                                        
                                        totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_85_14")][count] = totalFemmesMoins35CommunauteAcceuil

                                        totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_85_15")][count] = totalMoins35CommunauteAcceuil

                                        totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_85_16")][count] = totalHommesPlus35CommunauteAcceuil

                                        totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_85_17")][count] = totalFemmesPlus35CommunauteAcceuil

                                        totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_85_18")][count] = totalPlus35CommunauteAcceuil

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_85_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                                        

                                        
                                        if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                            totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                                        else:
                                            totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES (<=35)", "H", "ind_80")][count] = totalHommesMoins35
                                        
                                        if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                            totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                                        else:
                                            totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES (<=35)", "F", "ind_81")][count] = totalFemmesMoins35

                                        if totalHommesMoins35 or totalFemmesMoins35:
                                            totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                                        else:
                                            totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES (<=35)", "T", "ind_82")][count] = totalMoins35

                                        if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                            totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                                        else:
                                            totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES", "H", "ind_83")][count] = totalHommes

                                        if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                            totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                                        else:
                                            totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES", "F", "ind_84")][count] = totalFemmes

                                        if totalHommes or totalFemmes:
                                            totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                                        else:
                                            totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES", "T", "ind_85")][count] = totalPlus35

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "TOTAL PARTICIPANTS", "T", "ind_85_0")][count] = totalPlus35 + totalMoins35


                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "Nombre total de ménage", "Nombre total de ménage", "ind_86")][count] = safe_get(form_response, 0).get("totalMenages", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "Ethnies minoritaires", "Ethnies minoritaires", "ind_87")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                                    elif _.get('sql_id') in [48] or comparer_chaines(_.get('name'), "Appui à l'organisation et à la facilitation de rencontre  communautaire de restitution des résultats de la reunion cantonale d'arbitrage"): #Appui à l'organisation et à la facilitation de rencontre  communautaire de restitution des résultats de la reunion cantonale d'arbitrage
                                        
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "Date de la séance", "Date de la séance", "ind_88")][count] = safe_get(form_response, 0).get("dateDeLaReunion", None)

                                        
                                        totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES - REFUGIES (<=35)", "H", "ind_94_1")][count] = totalHommesMoins35Refugie
                                        
                                        totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES - REFUGIES (<=35)", "F", "ind_94_2")][count] = totalFemmesMoins35Refugie

                                        totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES - REFUGIES (<=35)", "T", "ind_94_3")][count] = totalMoins35Refugie

                                        totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES - REFUGIES", "H", "ind_94_4")][count] = totalHommesPlus35Refugie

                                        totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES - REFUGIES", "F", "ind_94_5")][count] = totalFemmesPlus35Refugie

                                        totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES - REFUGIES", "T", "ind_94_6")][count] = totalPlus35Refugie

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_94_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                                        


                                        totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_94_7")][count] = totalHommesMoins35DeplaceInterne
                                        
                                        totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_94_8")][count] = totalFemmesMoins35DeplaceInterne

                                        totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_94_9")][count] = totalMoins35DeplaceInterne

                                        totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "H", "ind_94_10")][count] = totalHommesPlus35DeplaceInterne

                                        totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "F", "ind_94_11")][count] = totalFemmesPlus35DeplaceInterne

                                        totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "T", "ind_94_12")][count] = totalPlus35DeplaceInterne

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_94_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                                        
                                        

                                        totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_94_13")][count] = totalHommesMoins35CommunauteAcceuil
                                        
                                        totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_94_14")][count] = totalFemmesMoins35CommunauteAcceuil

                                        totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_94_15")][count] = totalMoins35CommunauteAcceuil

                                        totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_94_16")][count] = totalHommesPlus35CommunauteAcceuil

                                        totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_94_17")][count] = totalFemmesPlus35CommunauteAcceuil

                                        totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_94_18")][count] = totalPlus35CommunauteAcceuil

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_94_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                                        

                                        
                                        if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                            totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                                        else:
                                            totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES (<=35)", "H", "ind_89")][count] = totalHommesMoins35
                                        
                                        if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                            totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                                        else:
                                            totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES (<=35)", "F", "ind_90")][count] = totalFemmesMoins35

                                        if totalHommesMoins35 or totalFemmesMoins35:
                                            totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                                        else:
                                            totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES (<=35)", "T", "ind_91")][count] = totalMoins35

                                        if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                            totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                                        else:
                                            totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES", "H", "ind_92")][count] = totalHommes

                                        if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                            totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                                        else:
                                            totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES", "F", "ind_93")][count] = totalFemmes

                                        if totalHommes or totalFemmes:
                                            totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                                        else:
                                            totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES", "T", "ind_94")][count] = totalPlus35

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "TOTAL PARTICIPANTS", "T", "ind_94_0")][count] = totalPlus35 + totalMoins35

            
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "Nombre total de ménage", "Nombre total de ménage", "ind_95")][count] = safe_get(form_response, 0).get("totalMenages", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "Ethnies minoritaires", "Ethnies minoritaires", "ind_96")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                                    elif _.get('sql_id') in [49] or comparer_chaines(_.get('name'), "Appuie au bureau du CVD  dans la rédaction du document du sous projet et la demande de financement"): #Appuie au bureau du CVD  dans la rédaction du document du sous projet et la demande de financement
                                        
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "Date de la séance", "Date de la séance", "ind_97")][count] = safe_get(form_response, 0).get("dateDeSeance", None)

                                        
                                        totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES - REFUGIES (<=35)", "H", "ind_103_1")][count] = totalHommesMoins35Refugie
                                        
                                        totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES - REFUGIES (<=35)", "F", "ind_103_2")][count] = totalFemmesMoins35Refugie

                                        totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES - REFUGIES (<=35)", "T", "ind_103_3")][count] = totalMoins35Refugie

                                        totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES - REFUGIES", "H", "ind_103_4")][count] = totalHommesPlus35Refugie

                                        totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES - REFUGIES", "F", "ind_103_5")][count] = totalFemmesPlus35Refugie

                                        totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES - REFUGIES", "T", "ind_103_6")][count] = totalPlus35Refugie

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_103_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                                        


                                        totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_103_7")][count] = totalHommesMoins35DeplaceInterne
                                        
                                        totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_103_8")][count] = totalFemmesMoins35DeplaceInterne

                                        totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_103_9")][count] = totalMoins35DeplaceInterne

                                        totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES - DEPLACES INTERNES", "H", "ind_103_10")][count] = totalHommesPlus35DeplaceInterne

                                        totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES - DEPLACES INTERNES", "F", "ind_103_11")][count] = totalFemmesPlus35DeplaceInterne

                                        totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES - DEPLACES INTERNES", "T", "ind_103_12")][count] = totalPlus35DeplaceInterne

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_103_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                                        
                                        

                                        totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_103_13")][count] = totalHommesMoins35CommunauteAcceuil
                                        
                                        totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_103_14")][count] = totalFemmesMoins35CommunauteAcceuil

                                        totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_103_15")][count] = totalMoins35CommunauteAcceuil

                                        totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_103_16")][count] = totalHommesPlus35CommunauteAcceuil

                                        totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_103_17")][count] = totalFemmesPlus35CommunauteAcceuil

                                        totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_103_18")][count] = totalPlus35CommunauteAcceuil

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_103_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                                        

                                        
                                        if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                            totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                                        else:
                                            totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES (<=35)", "H", "ind_98")][count] = totalHommesMoins35
                                        
                                        if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                            totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                                        else:
                                            totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES (<=35)", "F", "ind_99")][count] = totalFemmesMoins35

                                        if totalHommesMoins35 or totalFemmesMoins35:
                                            totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                                        else:
                                            totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES (<=35)", "T", "ind_100")][count] = totalMoins35

                                        if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                            totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                                        else:
                                            totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES", "H", "ind_101")][count] = totalHommes

                                        if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                            totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                                        else:
                                            totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES", "F", "ind_102")][count] = totalFemmes

                                        if totalHommes or totalFemmes:
                                            totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                                        else:
                                            totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES", "T", "ind_103")][count] = totalPlus35

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "TOTAL PARTICIPANTS", "T", "ind_103_0")][count] = totalPlus35 + totalMoins35


                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "Nombre total de ménage", "Nombre total de ménage", "ind_104")][count] = safe_get(form_response, 0).get("totalMenages", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "Ethnies minoritaires", "Ethnies minoritaires", "ind_105")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                                    elif _.get('sql_id') in [50] or comparer_chaines(_.get('name'), "Réunion d'information de la communauté sur le sous projet: activités, coût estimatif et prochainbes étapes"): #Réunion d'information de la communauté sur le sous projet: activités, coût estimatif et prochainbes étapes
                                        
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "Date de la séance", "Date de la séance", "ind_106")][count] = safe_get(form_response, 0).get("dateDeLaReunion", None)


                                        totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES - REFUGIES (<=35)", "H", "ind_112_1")][count] = totalHommesMoins35Refugie
                                        
                                        totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES - REFUGIES (<=35)", "F", "ind_112_2")][count] = totalFemmesMoins35Refugie

                                        totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES - REFUGIES (<=35)", "T", "ind_112_3")][count] = totalMoins35Refugie

                                        totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES - REFUGIES", "H", "ind_112_4")][count] = totalHommesPlus35Refugie

                                        totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES - REFUGIES", "F", "ind_112_5")][count] = totalFemmesPlus35Refugie

                                        totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES - REFUGIES", "T", "ind_112_6")][count] = totalPlus35Refugie

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_112_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                                        


                                        totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_112_7")][count] = totalHommesMoins35DeplaceInterne
                                        
                                        totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_112_8")][count] = totalFemmesMoins35DeplaceInterne

                                        totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_112_9")][count] = totalMoins35DeplaceInterne

                                        totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "H", "ind_112_10")][count] = totalHommesPlus35DeplaceInterne

                                        totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "F", "ind_112_11")][count] = totalFemmesPlus35DeplaceInterne

                                        totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "T", "ind_112_12")][count] = totalPlus35DeplaceInterne

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_112_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                                        
                                        

                                        totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_112_13")][count] = totalHommesMoins35CommunauteAcceuil
                                        
                                        totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_112_14")][count] = totalFemmesMoins35CommunauteAcceuil

                                        totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_112_15")][count] = totalMoins35CommunauteAcceuil

                                        totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_112_16")][count] = totalHommesPlus35CommunauteAcceuil

                                        totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_112_17")][count] = totalFemmesPlus35CommunauteAcceuil

                                        totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_112_18")][count] = totalPlus35CommunauteAcceuil

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_112_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                                        

                                        
                                        if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                            totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                                        else:
                                            totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES (<=35)", "H", "ind_107")][count] = totalHommesMoins35
                                        
                                        if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                            totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                                        else:
                                            totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES (<=35)", "F", "ind_108")][count] = totalFemmesMoins35

                                        if totalHommesMoins35 or totalFemmesMoins35:
                                            totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                                        else:
                                            totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES (<=35)", "T", "ind_109")][count] = totalMoins35

                                        if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                            totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                                        else:
                                            totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES", "H", "ind_110")][count] = totalHommes

                                        if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                            totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                                        else:
                                            totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES", "F", "ind_111")][count] = totalFemmes

                                        if totalHommes or totalFemmes:
                                            totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                                        else:
                                            totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES", "T", "ind_112")][count] = totalPlus35

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "TOTAL PARTICIPANTS", "T", "ind_112_0")][count] = totalPlus35 + totalMoins35


                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "Nombre total de ménage", "Nombre total de ménage", "ind_113")][count] = safe_get(form_response, 0).get("totalMenages", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "Ethnies minoritaires", "Ethnies minoritaires", "ind_114")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                                    elif _.get('sql_id') in [51] or comparer_chaines(_.get('name'), "Soumission de la demande de financement du sous-projet à l’ANADEB pour approbation par le CORA"): #Soumission de la demande de financement du sous-projet à l’ANADEB pour approbation par le CORA
                                        
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "Date de la séance", "Date de la séance", "ind_115")][count] = safe_get(form_response, 0).get("dateDeSoumission", None)


                                        totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES - REFUGIES (<=35)", "H", "ind_121_1")][count] = totalHommesMoins35Refugie
                                        
                                        totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES - REFUGIES (<=35)", "F", "ind_121_2")][count] = totalFemmesMoins35Refugie

                                        totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES - REFUGIES (<=35)", "T", "ind_121_3")][count] = totalMoins35Refugie

                                        totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES - REFUGIES", "H", "ind_121_4")][count] = totalHommesPlus35Refugie

                                        totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES - REFUGIES", "F", "ind_121_5")][count] = totalFemmesPlus35Refugie

                                        totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES - REFUGIES", "T", "ind_121_6")][count] = totalPlus35Refugie

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_121_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                                        


                                        totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_121_7")][count] = totalHommesMoins35DeplaceInterne
                                        
                                        totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_121_8")][count] = totalFemmesMoins35DeplaceInterne

                                        totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_121_9")][count] = totalMoins35DeplaceInterne

                                        totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES - DEPLACES INTERNES", "H", "ind_121_10")][count] = totalHommesPlus35DeplaceInterne

                                        totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES - DEPLACES INTERNES", "F", "ind_121_11")][count] = totalFemmesPlus35DeplaceInterne

                                        totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES - DEPLACES INTERNES", "T", "ind_121_12")][count] = totalPlus35DeplaceInterne

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_121_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                                        
                                        

                                        totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_121_13")][count] = totalHommesMoins35CommunauteAcceuil
                                        
                                        totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_121_14")][count] = totalFemmesMoins35CommunauteAcceuil

                                        totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_121_15")][count] = totalMoins35CommunauteAcceuil

                                        totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_121_16")][count] = totalHommesPlus35CommunauteAcceuil

                                        totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_121_17")][count] = totalFemmesPlus35CommunauteAcceuil

                                        totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_121_18")][count] = totalPlus35CommunauteAcceuil

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_121_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                                        

                                        
                                        if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                            totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                                        else:
                                            totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES (<=35)", "H", "ind_116")][count] = totalHommesMoins35
                                        
                                        if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                            totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                                        else:
                                            totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES (<=35)", "F", "ind_117")][count] = totalFemmesMoins35

                                        if totalHommesMoins35 or totalFemmesMoins35:
                                            totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                                        else:
                                            totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES (<=35)", "T", "ind_118")][count] = totalMoins35

                                        if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                            totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                                        else:
                                            totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES", "H", "ind_119")][count] = totalHommes

                                        if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                            totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                                        else:
                                            totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES", "F", "ind_120")][count] = totalFemmes

                                        if totalHommes or totalFemmes:
                                            totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                                        else:
                                            totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES", "T", "ind_121")][count] = totalPlus35

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "TOTAL PARTICIPANTS", "T", "ind_121_0")][count] = totalPlus35 + totalMoins35


                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "Nombre total de ménage", "Nombre total de ménage", "ind_122")][count] = safe_get(form_response, 0).get("totalMenages", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "Ethnies minoritaires", "Ethnies minoritaires", "ind_123")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                                    elif _.get('sql_id') in [52] or comparer_chaines(_.get('name'), "Séance communautaire d'information sur les grandes lignes  du sous projet, sa durée d'exécution et les mesures de sauvegardes à observer"): #Séance communautaire d'information sur les grandes lignes  du sous projet, sa durée d'exécution et les mesures de sauvegardes à observer
                                        
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "Date de la séance", "Date de la séance", "ind_124")][count] = safe_get(form_response, 0).get("dateDeSeance", None)


                                        totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES - REFUGIES (<=35)", "H", "ind_130_1")][count] = totalHommesMoins35Refugie
                                        
                                        totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES - REFUGIES (<=35)", "F", "ind_130_2")][count] = totalFemmesMoins35Refugie

                                        totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES - REFUGIES (<=35)", "T", "ind_130_3")][count] = totalMoins35Refugie

                                        totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES - REFUGIES", "H", "ind_130_4")][count] = totalHommesPlus35Refugie

                                        totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES - REFUGIES", "F", "ind_130_5")][count] = totalFemmesPlus35Refugie

                                        totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES - REFUGIES", "T", "ind_130_6")][count] = totalPlus35Refugie

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_130_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                                        


                                        totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_130_7")][count] = totalHommesMoins35DeplaceInterne
                                        
                                        totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_130_8")][count] = totalFemmesMoins35DeplaceInterne

                                        totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_130_9")][count] = totalMoins35DeplaceInterne

                                        totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES - DEPLACES INTERNES", "H", "ind_130_10")][count] = totalHommesPlus35DeplaceInterne

                                        totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES - DEPLACES INTERNES", "F", "ind_130_11")][count] = totalFemmesPlus35DeplaceInterne

                                        totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES - DEPLACES INTERNES", "T", "ind_130_12")][count] = totalPlus35DeplaceInterne

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_130_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                                        
                                        

                                        totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_130_13")][count] = totalHommesMoins35CommunauteAcceuil
                                        
                                        totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_130_14")][count] = totalFemmesMoins35CommunauteAcceuil

                                        totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_130_15")][count] = totalMoins35CommunauteAcceuil

                                        totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_130_16")][count] = totalHommesPlus35CommunauteAcceuil

                                        totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_130_17")][count] = totalFemmesPlus35CommunauteAcceuil

                                        totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_130_18")][count] = totalPlus35CommunauteAcceuil

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_130_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                                        

                                        
                                        if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                            totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                                        else:
                                            totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES (<=35)", "H", "ind_125")][count] = totalHommesMoins35
                                        
                                        if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                            totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                                        else:
                                            totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES (<=35)", "F", "ind_126")][count] = totalFemmesMoins35

                                        if totalHommesMoins35 or totalFemmesMoins35:
                                            totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                                        else:
                                            totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES (<=35)", "T", "ind_127")][count] = totalMoins35

                                        if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                            totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                                        else:
                                            totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES", "H", "ind_128")][count] = totalHommes

                                        if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                            totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                                        else:
                                            totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES", "F", "ind_129")][count] = totalFemmes

                                        if totalHommes or totalFemmes:
                                            totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                                        else:
                                            totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES", "T", "ind_130")][count] = totalPlus35

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "TOTAL PARTICIPANTS", "T", "ind_130_0")][count] = totalPlus35 + totalMoins35


                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "Nombre total de ménage", "Nombre total de ménage", "ind_131")][count] = safe_get(form_response, 0).get("totalMenages", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "Ethnies minoritaires", "Ethnies minoritaires", "ind_132")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                                    elif _.get('sql_id') in [53] or comparer_chaines(_.get('name'), "Appuie au CVD dans la production des rapports périodiques et l'organisation des réunions d'échanges sur l'état d'avancement des travaux"): #Appuie au CVD dans la production des rapports périodiques et l'organisation des réunions d'échanges sur l'état d'avancement des travaux
                                        
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "Date de la séance", "Date de la séance", "ind_133")][count] = safe_get(form_response, 0).get("dateDeLaReunion", None)


                                        totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES - REFUGIES (<=35)", "H", "ind_139_1")][count] = totalHommesMoins35Refugie
                                        
                                        totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES - REFUGIES (<=35)", "F", "ind_139_2")][count] = totalFemmesMoins35Refugie

                                        totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES - REFUGIES (<=35)", "T", "ind_139_3")][count] = totalMoins35Refugie

                                        totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES - REFUGIES", "H", "ind_139_4")][count] = totalHommesPlus35Refugie

                                        totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES - REFUGIES", "F", "ind_139_5")][count] = totalFemmesPlus35Refugie

                                        totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES - REFUGIES", "T", "ind_139_6")][count] = totalPlus35Refugie

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_139_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                                        


                                        totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_139_7")][count] = totalHommesMoins35DeplaceInterne
                                        
                                        totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_139_8")][count] = totalFemmesMoins35DeplaceInterne

                                        totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_139_9")][count] = totalMoins35DeplaceInterne

                                        totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES - DEPLACES INTERNES", "H", "ind_139_10")][count] = totalHommesPlus35DeplaceInterne

                                        totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES - DEPLACES INTERNES", "F", "ind_139_11")][count] = totalFemmesPlus35DeplaceInterne

                                        totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES - DEPLACES INTERNES", "T", "ind_139_12")][count] = totalPlus35DeplaceInterne

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_139_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                                                                                

                                        totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_139_13")][count] = totalHommesMoins35CommunauteAcceuil
                                        
                                        totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_139_14")][count] = totalFemmesMoins35CommunauteAcceuil

                                        totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_139_15")][count] = totalMoins35CommunauteAcceuil

                                        totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_139_16")][count] = totalHommesPlus35CommunauteAcceuil

                                        totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_139_17")][count] = totalFemmesPlus35CommunauteAcceuil

                                        totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_139_18")][count] = totalPlus35CommunauteAcceuil

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_139_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                                        
                                        
                                        if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                            totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                                        else:
                                            totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES (<=35)", "H", "ind_134")][count] = totalHommesMoins35
                                        
                                        if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                            totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                                        else:
                                            totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES (<=35)", "F", "ind_135")][count] = totalFemmesMoins35

                                        if totalHommesMoins35 or totalFemmesMoins35:
                                            totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                                        else:
                                            totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES (<=35)", "T", "ind_136")][count] = totalMoins35

                                        if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                            totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                                        else:
                                            totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES", "H", "ind_137")][count] = totalHommes

                                        if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                            totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                                        else:
                                            totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES", "F", "ind_138")][count] = totalFemmes

                                        if totalHommes or totalFemmes:
                                            totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                                        else:
                                            totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES", "T", "ind_139")][count] = totalPlus35

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "TOTAL PARTICIPANTS", "T", "ind_139_0")][count] = totalPlus35 + totalMoins35


                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "Nombre total de ménage", "Nombre total de ménage", "ind_140")][count] = safe_get(form_response, 0).get("totalMenages", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "Ethnies minoritaires", "Ethnies minoritaires", "ind_141")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                                    elif _.get('sql_id') in [54] or comparer_chaines(_.get('name'), "Classement et archivage de tous les documents relatifs à la mise en œuvre du sous projet"): #Classement et archivage de tous les documents relatifs à la mise en œuvre du sous projet
                                        
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "Date de la séance", "Date de la séance", "ind_142")][count] = safe_get(form_response, 0).get("dateDeLaReunion", None)


                                        totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES - REFUGIES (<=35)", "H", "ind_148_1")][count] = totalHommesMoins35Refugie
                                        
                                        totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES - REFUGIES (<=35)", "F", "ind_148_2")][count] = totalFemmesMoins35Refugie

                                        totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES - REFUGIES (<=35)", "T", "ind_148_3")][count] = totalMoins35Refugie

                                        totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES - REFUGIES", "H", "ind_148_4")][count] = totalHommesPlus35Refugie

                                        totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES - REFUGIES", "F", "ind_148_5")][count] = totalFemmesPlus35Refugie

                                        totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES - REFUGIES", "T", "ind_148_6")][count] = totalPlus35Refugie

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_148_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                                        


                                        totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_148_7")][count] = totalHommesMoins35DeplaceInterne
                                        
                                        totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_148_8")][count] = totalFemmesMoins35DeplaceInterne

                                        totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_148_9")][count] = totalMoins35DeplaceInterne

                                        totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES - DEPLACES INTERNES", "H", "ind_148_10")][count] = totalHommesPlus35DeplaceInterne

                                        totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES - DEPLACES INTERNES", "F", "ind_148_11")][count] = totalFemmesPlus35DeplaceInterne

                                        totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES - DEPLACES INTERNES", "T", "ind_148_12")][count] = totalPlus35DeplaceInterne

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_148_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                                                                                

                                        totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_148_13")][count] = totalHommesMoins35CommunauteAcceuil
                                        
                                        totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_148_14")][count] = totalFemmesMoins35CommunauteAcceuil

                                        totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_148_15")][count] = totalMoins35CommunauteAcceuil

                                        totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_148_16")][count] = totalHommesPlus35CommunauteAcceuil

                                        totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_148_17")][count] = totalFemmesPlus35CommunauteAcceuil

                                        totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_148_18")][count] = totalPlus35CommunauteAcceuil

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_148_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                                        
                                        
                                        if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                            totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                                        else:
                                            totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES (<=35)", "H", "ind_143")][count] = totalHommesMoins35
                                        
                                        if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                            totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                                        else:
                                            totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES (<=35)", "F", "ind_144")][count] = totalFemmesMoins35

                                        if totalHommesMoins35 or totalFemmesMoins35:
                                            totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                                        else:
                                            totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES (<=35)", "T", "ind_145")][count] = totalMoins35

                                        if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                            totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                                        else:
                                            totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES", "H", "ind_146")][count] = totalHommes

                                        if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                            totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                                        else:
                                            totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES", "F", "ind_147")][count] = totalFemmes

                                        if totalHommes or totalFemmes:
                                            totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                                        else:
                                            totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES", "T", "ind_148")][count] = totalPlus35

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "TOTAL PARTICIPANTS", "T", "ind_148_0")][count] = totalPlus35 + totalMoins35
            
            
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "Nombre total de ménage", "Nombre total de ménage", "ind_149")][count] = safe_get(form_response, 0).get("totalMenages", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "Ethnies minoritaires", "Ethnies minoritaires", "ind_150")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                                    elif _.get('sql_id') in [55] or comparer_chaines(_.get('name'), "Réalisation de l'auto évaluation participative de la mise en œuvre du sous projet"): #Réalisation de l'auto évaluation participative de la mise en œuvre du sous projet
                                        
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "Date de la séance", "Date de la séance", "ind_151")][count] = safe_get(form_response, 0).get("dateDeSeance", None)


                                        totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES - REFUGIES (<=35)", "H", "ind_157_1")][count] = totalHommesMoins35Refugie
                                        
                                        totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES - REFUGIES (<=35)", "F", "ind_157_2")][count] = totalFemmesMoins35Refugie

                                        totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES - REFUGIES (<=35)", "T", "ind_157_3")][count] = totalMoins35Refugie

                                        totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES - REFUGIES", "H", "ind_157_4")][count] = totalHommesPlus35Refugie

                                        totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES - REFUGIES", "F", "ind_157_5")][count] = totalFemmesPlus35Refugie

                                        totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES - REFUGIES", "T", "ind_157_6")][count] = totalPlus35Refugie

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_157_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                                        

                                        totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_157_7")][count] = totalHommesMoins35DeplaceInterne
                                        
                                        totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_157_8")][count] = totalFemmesMoins35DeplaceInterne

                                        totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_157_9")][count] = totalMoins35DeplaceInterne

                                        totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES - DEPLACES INTERNES", "H", "ind_157_10")][count] = totalHommesPlus35DeplaceInterne

                                        totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES - DEPLACES INTERNES", "F", "ind_157_11")][count] = totalFemmesPlus35DeplaceInterne

                                        totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES - DEPLACES INTERNES", "T", "ind_157_12")][count] = totalPlus35DeplaceInterne

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_157_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                                                                                

                                        totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_157_13")][count] = totalHommesMoins35CommunauteAcceuil
                                        
                                        totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_157_14")][count] = totalFemmesMoins35CommunauteAcceuil

                                        totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_157_15")][count] = totalMoins35CommunauteAcceuil

                                        totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_157_16")][count] = totalHommesPlus35CommunauteAcceuil

                                        totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_157_17")][count] = totalFemmesPlus35CommunauteAcceuil

                                        totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_157_18")][count] = totalPlus35CommunauteAcceuil

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_157_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                                        
                                        
                                        if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                            totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                                        else:
                                            totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES (<=35)", "H", "ind_152")][count] = totalHommesMoins35
                                        
                                        if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                            totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                                        else:
                                            totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES (<=35)", "F", "ind_153")][count] = totalFemmesMoins35

                                        if totalHommesMoins35 or totalFemmesMoins35:
                                            totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                                        else:
                                            totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES (<=35)", "T", "ind_154")][count] = totalMoins35

                                        if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                            totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                                        else:
                                            totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES", "H", "ind_155")][count] = totalHommes

                                        if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                            totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                                        else:
                                            totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES", "F", "ind_156")][count] = totalFemmes

                                        if totalHommes or totalFemmes:
                                            totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                                        else:
                                            totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES", "T", "ind_157")][count] = totalPlus35

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "TOTAL PARTICIPANTS", "T", "ind_157_0")][count] = totalPlus35 + totalMoins35
            
            
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "Nombre total de ménage", "Nombre total de ménage", "ind_158")][count] = safe_get(form_response, 0).get("totalMenages", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "Ethnies minoritaires", "Ethnies minoritaires", "ind_159")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                                    elif _.get('sql_id') in [56] or comparer_chaines(_.get('name'), "Elaboration et mise en oeuvre du plan d'entretien et de maintenance de l'ouvrage"): #Elaboration et mise en oeuvre du plan d'entretien et de maintenance de l'ouvrage
                                        
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "Date de la sensibilisation", "Date de la sensibilisation", "ind_160")][count] = safe_get(form_response, 0).get("dateDeSensibilisation", None)


                                        totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES - REFUGIES (<=35)", "H", "ind_166_1")][count] = totalHommesMoins35Refugie
                                        
                                        totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES - REFUGIES (<=35)", "F", "ind_166_2")][count] = totalFemmesMoins35Refugie

                                        totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES - REFUGIES (<=35)", "T", "ind_166_3")][count] = totalMoins35Refugie

                                        totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES - REFUGIES", "H", "ind_166_4")][count] = totalHommesPlus35Refugie

                                        totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES - REFUGIES", "F", "ind_166_5")][count] = totalFemmesPlus35Refugie

                                        totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES - REFUGIES", "T", "ind_166_6")][count] = totalPlus35Refugie

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_166_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                                        

                                        totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_166_7")][count] = totalHommesMoins35DeplaceInterne
                                        
                                        totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_166_8")][count] = totalFemmesMoins35DeplaceInterne

                                        totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_166_9")][count] = totalMoins35DeplaceInterne

                                        totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES - DEPLACES INTERNES", "H", "ind_166_10")][count] = totalHommesPlus35DeplaceInterne

                                        totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES - DEPLACES INTERNES", "F", "ind_166_11")][count] = totalFemmesPlus35DeplaceInterne

                                        totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES - DEPLACES INTERNES", "T", "ind_166_12")][count] = totalPlus35DeplaceInterne

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_166_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                                                                                

                                        totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_166_13")][count] = totalHommesMoins35CommunauteAcceuil
                                        
                                        totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_166_14")][count] = totalFemmesMoins35CommunauteAcceuil

                                        totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_166_15")][count] = totalMoins35CommunauteAcceuil

                                        totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_166_16")][count] = totalHommesPlus35CommunauteAcceuil

                                        totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_166_17")][count] = totalFemmesPlus35CommunauteAcceuil

                                        totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_166_18")][count] = totalPlus35CommunauteAcceuil

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_166_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                                        
                                        
                                        if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                            totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                                        else:
                                            totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES (<=35)", "H", "ind_161")][count] = totalHommesMoins35
                                        
                                        if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                            totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                                        else:
                                            totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES (<=35)", "F", "ind_162")][count] = totalFemmesMoins35

                                        if totalHommesMoins35 or totalFemmesMoins35:
                                            totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                                        else:
                                            totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES (<=35)", "T", "ind_163")][count] = totalMoins35

                                        if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                            totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                                        else:
                                            totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES", "H", "ind_164")][count] = totalHommes

                                        if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                            totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                                        else:
                                            totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES", "F", "ind_165")][count] = totalFemmes

                                        if totalHommes or totalFemmes:
                                            totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                                        else:
                                            totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES", "T", "ind_166")][count] = totalPlus35

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "TOTAL PARTICIPANTS", "T", "ind_166_0")][count] = totalPlus35 + totalMoins35
                    

                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "Nombre total de ménage", "Nombre total de ménage", "ind_167")][count] = safe_get(form_response, 0).get("totalMenages", None)
                                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "Ethnies minoritaires", "Ethnies minoritaires", "ind_168")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                        #
                        for d_k, d_v in datas.items():
                            # REFUGIES
                            if d_k[4] == "JEUNES - REFUGIES (<=35)" and d_k[5] == "H" and d_v.get(count):
                                if d_v[count] > total_JEUNES_H_REFUGIES:
                                    total_JEUNES_H_REFUGIES = d_v[count]
                            elif d_k[4] == "JEUNES - REFUGIES (<=35)" and d_k[5] == "F" and d_v.get(count):
                                if d_v[count] > total_JEUNES_F_REFUGIES:
                                    total_JEUNES_F_REFUGIES = d_v[count]
                            elif d_k[4] == "NON JEUNES - REFUGIES" and d_k[5] == "H" and d_v.get(count):
                                if d_v[count] > total_H_REFUGIES:
                                    total_H_REFUGIES = d_v[count]
                            elif d_k[4] == "NON JEUNES - REFUGIES" and d_k[5] == "F" and d_v.get(count):
                                if d_v[count] > total_F_REFUGIES:
                                    total_F_REFUGIES = d_v[count]
                            # End REFUGIES
                            
                            # DEPLACES INTERNES
                            elif d_k[4] == "JEUNES - DEPLACES INTERNES (<=35)" and d_k[5] == "H" and d_v.get(count):
                                if d_v[count] > total_JEUNES_H_DEPLACES_INTERNES:
                                    total_JEUNES_H_DEPLACES_INTERNES = d_v[count]
                            elif d_k[4] == "JEUNES - DEPLACES INTERNES (<=35)" and d_k[5] == "F" and d_v.get(count):
                                if d_v[count] > total_JEUNES_F_DEPLACES_INTERNES:
                                    total_JEUNES_F_DEPLACES_INTERNES = d_v[count]
                            elif d_k[4] == "NON JEUNES - DEPLACES INTERNES" and d_k[5] == "H" and d_v.get(count):
                                if d_v[count] > total_H_DEPLACES_INTERNES:
                                    total_H_DEPLACES_INTERNES = d_v[count]
                            elif d_k[4] == "NON JEUNES - DEPLACES INTERNES" and d_k[5] == "F" and d_v.get(count):
                                if d_v[count] > total_F_DEPLACES_INTERNES:
                                    total_F_DEPLACES_INTERNES = d_v[count]
                            # End DEPLACES INTERNES
                            
                            # COMMUNAUTES ACCUEIL
                            elif d_k[4] == "JEUNES - COMMUNAUTES ACCUEIL (<=35)" and d_k[5] == "H" and d_v.get(count):
                                if d_v[count] > total_JEUNES_H_COMMUNAUTES_ACCUEIL:
                                    total_JEUNES_H_COMMUNAUTES_ACCUEIL = d_v[count]
                            elif d_k[4] == "JEUNES - COMMUNAUTES ACCUEIL (<=35)" and d_k[5] == "F" and d_v.get(count):
                                if d_v[count] > total_JEUNES_F_COMMUNAUTES_ACCUEIL:
                                    total_JEUNES_F_COMMUNAUTES_ACCUEIL = d_v[count]
                            elif d_k[4] == "NON JEUNES - COMMUNAUTES ACCUEIL" and d_k[5] == "H" and d_v.get(count):
                                if d_v[count] > total_H_COMMUNAUTES_ACCUEIL:
                                    total_H_COMMUNAUTES_ACCUEIL = d_v[count]
                            elif d_k[4] == "NON JEUNES - COMMUNAUTES ACCUEIL" and d_k[5] == "F" and d_v.get(count):
                                if d_v[count] > total_F_COMMUNAUTES_ACCUEIL:
                                    total_F_COMMUNAUTES_ACCUEIL = d_v[count]
                            # End COMMUNAUTES ACCUEIL

                            elif d_k[4] == "NON JEUNES" and d_k[5] == "H" and d_v.get(count):
                                if d_v[count] > total_H:
                                    total_H = d_v[count]
                            elif d_k[4] == "NON JEUNES" and d_k[5] == "F" and d_v.get(count):
                                if d_v[count] > total_F:
                                    total_F = d_v[count]
                            elif d_k[4] == "JEUNES (<=35)" and d_k[5] == "H" and d_v.get(count):
                                if d_v[count] > total_JEUNES_H:
                                    total_JEUNES_H = d_v[count]
                            elif d_k[4] == "JEUNES (<=35)" and d_k[5] == "F" and d_v.get(count):
                                if d_v[count] > total_JEUNES_F:
                                    total_JEUNES_F = d_v[count]
                            elif d_k[4] == "JEUNES (<=35)" and d_k[5] == "T" and d_v.get(count):
                                if d_v[count] > total_JEUNES:
                                    total_JEUNES = d_v[count]
                            elif d_k[4] == "Nombre total de ménage" and d_k[5] == "Nombre total de ménage" and d_v.get(count):
                                if d_v[count] > total_MENAGES:
                                    total_MENAGES = d_v[count]
                            elif d_k[4] == "Ethnies minoritaires" and  d_k[5] == "Ethnies minoritaires" and d_v.get(count):
                                if d_v[count] > total_ETHNIES:
                                    total_ETHNIES = d_v[count]


                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES - REFUGIES (<=35)", "H", "ind_174_1")][count] = total_JEUNES_H_REFUGIES
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES - REFUGIES (<=35)", "F", "ind_174_2")][count] = total_JEUNES_F_REFUGIES
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES - REFUGIES (<=35)", "T", "ind_174_3")][count] = total_JEUNES_H_REFUGIES + total_JEUNES_F_REFUGIES
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES - REFUGIES", "H", "ind_174_4")][count] = total_H_REFUGIES
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES - REFUGIES", "F", "ind_174_5")][count] = total_F_REFUGIES
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES - REFUGIES", "T", "ind_174_6")][count] = total_H_REFUGIES + total_F_REFUGIES
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_174_6_0")][count] = (
                            total_JEUNES_H_REFUGIES + total_JEUNES_F_REFUGIES + total_H_REFUGIES + total_F_REFUGIES
                        )

                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_174_7")][count] = total_JEUNES_H_DEPLACES_INTERNES
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_174_8")][count] = total_JEUNES_F_DEPLACES_INTERNES
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_174_9")][count] = total_JEUNES_H_DEPLACES_INTERNES + total_JEUNES_F_DEPLACES_INTERNES
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES - DEPLACES INTERNES", "H", "ind_174_10")][count] = total_H_DEPLACES_INTERNES
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES - DEPLACES INTERNES", "F", "ind_174_11")][count] = total_F_DEPLACES_INTERNES
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES - DEPLACES INTERNES", "T", "ind_174_12")][count] = total_H_DEPLACES_INTERNES + total_F_DEPLACES_INTERNES
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_174_12_0")][count] = (
                            total_JEUNES_H_DEPLACES_INTERNES + total_JEUNES_F_DEPLACES_INTERNES + total_H_DEPLACES_INTERNES + total_F_DEPLACES_INTERNES
                        )

                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_174_13")][count] = total_JEUNES_H_COMMUNAUTES_ACCUEIL
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_174_14")][count] = total_JEUNES_F_COMMUNAUTES_ACCUEIL
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_174_15")][count] = total_JEUNES_H_COMMUNAUTES_ACCUEIL + total_JEUNES_F_COMMUNAUTES_ACCUEIL
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_174_16")][count] = total_H_COMMUNAUTES_ACCUEIL
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_174_17")][count] = total_F_COMMUNAUTES_ACCUEIL
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_174_18")][count] = total_H_COMMUNAUTES_ACCUEIL + total_F_COMMUNAUTES_ACCUEIL
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_174_18_0")][count] = (
                            total_JEUNES_H_COMMUNAUTES_ACCUEIL + total_JEUNES_F_COMMUNAUTES_ACCUEIL + total_H_COMMUNAUTES_ACCUEIL + total_F_COMMUNAUTES_ACCUEIL
                        )



                        if total_JEUNES_H_REFUGIES or total_JEUNES_H_DEPLACES_INTERNES or total_JEUNES_H_COMMUNAUTES_ACCUEIL:
                            total_JEUNES_H = total_JEUNES_H_REFUGIES + total_JEUNES_H_DEPLACES_INTERNES + total_JEUNES_H_COMMUNAUTES_ACCUEIL
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES (<=35)", "H", "ind_169")][count] = total_JEUNES_H
                        
                        if total_JEUNES_F_REFUGIES or total_JEUNES_F_DEPLACES_INTERNES or total_JEUNES_F_COMMUNAUTES_ACCUEIL:
                            total_JEUNES_F = total_JEUNES_F_REFUGIES + total_JEUNES_F_DEPLACES_INTERNES + total_JEUNES_F_COMMUNAUTES_ACCUEIL
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES (<=35)", "F", "ind_170")][count] = total_JEUNES_F
                        
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES (<=35)", "T", "ind_171")][count] = (total_JEUNES_H + total_JEUNES_F) if (total_JEUNES_H + total_JEUNES_F) else total_JEUNES
                        
                        if total_H_REFUGIES or total_H_DEPLACES_INTERNES or total_H_COMMUNAUTES_ACCUEIL:
                            total_H = total_H_REFUGIES + total_H_DEPLACES_INTERNES + total_H_COMMUNAUTES_ACCUEIL
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES", "H", "ind_172")][count] = total_H
                        
                        if total_F_REFUGIES or total_F_DEPLACES_INTERNES or total_F_COMMUNAUTES_ACCUEIL:
                            total_F = total_F_REFUGIES + total_F_DEPLACES_INTERNES + total_F_COMMUNAUTES_ACCUEIL
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES", "F", "ind_173")][count] = total_F
                        
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES", "T", "ind_174")][count] = total_H + total_F
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "TOTAL PARTICIPANTS", "T", "ind_174_0")][count] = (
                            total_H + total_F + (total_JEUNES_H + total_JEUNES_F) if (total_JEUNES_H + total_JEUNES_F) else total_JEUNES
                        )

                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "Nombre total de ménage", "Nombre total de ménage", "ind_175")][count] = total_MENAGES
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "Ethnies minoritaires", "Ethnies minoritaires", "ind_176")][count] = total_ETHNIES

                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "Observations", "Observations", "Observations", "Observations", "Observations", "ind_177")][count] = ""
                        datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "DB_NAME", "DB_NAME", "DB_NAME", "DB_NAME", "DB_NAME", "ind_178")][count] = f.no_sql_db_name



                        count += 1


    backup_db = nsc.get_db("backup_db_facilitators_docs")
    query_result_docs = [_ for _ in backup_db.all_docs(include_docs=True)['rows'] if type(_) is dict and _.get('doc') and _.get('doc').get('type') == 'task' and _.get('doc').get('cycle_id') == cycle_id and _.get('doc').get('project_id') == project.couch_id]
    administrative_level_cvd_villages = []
    for _ in query_result_docs:
        doc = _.get('doc')
        if doc and doc["administrative_level_id"] not in administrative_level_cvd_villages:
            administrative_level_cvd_villages.append(doc["administrative_level_id"])
            
    for administrative_level_cvd_village in administrative_level_cvd_villages:
        administrativelevel_obj = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(id=int(administrative_level_cvd_village)).first()
        if administrativelevel_obj and administrativelevel_obj.cvd:
            # _ok = True
            # if liste_villages:
            #     _ok = False
            #     for village in liste_villages:
            #         if str(administrative_level_cvd_village) == str(village["administrative_id"]):
            #             _ok = True
            #             break
            # if _ok:
            if (facilitator_dbs_name and (
                not params.get("ids_administrativelevel") or (params.get("ids_administrativelevel") and [v for v in liste_villages for v_c in administrativelevel_obj.cvd.get_villages() if str(v["administrative_id"]) == str(v_c.id)])
            )) or (
                not params.get("ids_administrativelevel") or (params.get("ids_administrativelevel") and [v for v in liste_villages for v_c in administrativelevel_obj.cvd.get_villages() if str(v["administrative_id"]) == str(v_c.id)])
            ):
                pass
            else:
                continue

            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "ID CVD", "ID CVD", "ID CVD", "ID CVD", "ID CVD", "ind_0")][count] = administrativelevel_obj.cvd.id #count + 1
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Région", "Région", "Région", "Région", "ind_1")][count] = administrativelevel_obj.parent.parent.parent.parent.name
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Préfecture", "Préfecture", "Préfecture", "Préfecture", "ind_2")][count] = administrativelevel_obj.parent.parent.parent.name
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Commune", "Commune", "Commune", "Commune", "ind_3")][count] = administrativelevel_obj.parent.parent.name
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Canton", "Canton", "Canton", "Canton", "ind_4")][count] = administrativelevel_obj.parent.name
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "CVD", "CVD", "CVD", "CVD", "ind_5")][count] = administrativelevel_obj.cvd.name
            # villages = ""
            # for o in administrativelevel_obj.cvd.get_villages():
            #     villages += f'{o.name} ; '
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Villages", "Villages", "Villages", "Villages", "ind_6")][count] = ";".join([o.name for o in administrativelevel_obj.cvd.get_villages()])
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Unité géographique", "Unité géographique", "Unité géographique", "Unité géographique", "ind_7")][count] = administrativelevel_obj.geographical_unit.attributed_number_in_canton
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Nom de l'AC", "Nom de l'AC", "Nom de l'AC", "Nom de l'AC", "ind_8")][count] = ''
            
            total_H, total_F, total_JEUNES_H, total_JEUNES_F, total_JEUNES, total_MENAGES, total_ETHNIES = 0, 0, 0, 0, 0, 0, 0
            
            for doc in query_result_docs:
                _ = doc.get('doc')
                if _.get('type') == "task" and str(administrative_level_cvd_village) == str(_["administrative_level_id"]):
                    form_response = _.get("form_response")
                    if form_response:
                        value = None

                        if _.get('sql_id') in [20] or comparer_chaines(_.get('name'), "Etablissement du profil du village"): #Etablissement du profil du village

                            old_forms = _.get('old_forms')
                            old_form_response = old_forms[-1].get("form_response") if old_forms else []

                            # Eff. Population
                            try:
                                value = get_datas_dict(form_response, "population", 1)["populationTotaleDuVillage"]
                            except Exception as exc:
                                if not value:
                                    try:
                                        value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["populationVillage"]
                                    except:
                                        try:
                                            value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["populationVillage"]
                                        except:
                                            value = None
                            population = value
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Eff. Population", "Eff. Population", "Eff. Population", "ind_9")][count] = value
                            # End Eff. Population


                            """Réfugiés"""
                            # "Eff. Population", "Réfugiés", "Eff. (<=35)", "H"
                            population_refugees_young_h = None
                            value = None
                            try:
                                try:
                                    value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalHommesMoins35Refugie"]
                                except:
                                    value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalHommesMoins35Refugie"]
                            except Exception as exc:
                                value = None
                            population_refugees_young_h = value
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Réfugiés", "Eff. (<=35)", "H", "ind_9_10")][count] = value
                            # End "Eff. Population", "Réfugiés", "Eff. (<=35)", "H"

                            # "Eff. Population", "Réfugiés", "Eff. (<=35)", "F"
                            population_refugees_young_f = None
                            value = None
                            try:
                                try:
                                    value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalFemmesMoins35Refugie"]
                                except:
                                    value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalFemmesMoins35Refugie"]
                            except Exception as exc:
                                value = None
                            population_refugees_young_f = value
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Réfugiés", "Eff. (<=35)", "F", "ind_9_11")][count] = value
                            # End "Eff. Population", "Réfugiés", "Eff. (<=35)", "F"

                            population_refugees_young = (population_refugees_young_f if population_refugees_young_f else 0) + (population_refugees_young_h if population_refugees_young_h else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Réfugiés", "Eff. (<=35)", "T", "ind_9_12")][count] = population_refugees_young


                            # "Eff. Population", "Réfugiés", "Eff. (>35)", "H"
                            population_refugees_old_h = None
                            value = None
                            try:
                                try:
                                    value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalHommesPlus35Refugie"]
                                except:
                                    value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalHommesPlus35Refugie"]
                            except Exception as exc:
                                value = None
                            population_refugees_old_h = value
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Réfugiés", "Eff. (>35)", "H", "ind_9_13")][count] = value
                            # End "Eff. Population", "Réfugiés", "Eff. (>35)", "H"

                            # "Eff. Population", "Réfugiés", "Eff. (>35)", "F"
                            population_refugees_old_f = None
                            value = None
                            try:
                                try:
                                    value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalFemmesPlus35Refugie"]
                                except:
                                    value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalFemmesPlus35Refugie"]
                            except Exception as exc:
                                value = None
                            population_refugees_old_f = value
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Réfugiés", "Eff. (>35)", "F", "ind_9_14")][count] = value
                            # End "Eff. Population", "Réfugiés", "Eff. (>35)", "F"
                            
                            population_refugees_old = (population_refugees_old_f if population_refugees_old_f else 0) + (population_refugees_old_h if population_refugees_old_h else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Réfugiés", "Eff. (>35)", "T", "ind_9_15")][count] = population_refugees_old

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Réfugiés", "Total", "T", "ind_9_16")][count] = population_refugees_young + population_refugees_old

                            """End Réfugiés"""


                            """Déplacés internes"""
                            # "Eff. Population", "Déplacés internes", "Eff. (<=35)", "H"
                            population_internally_displaced_persons_young_h = None
                            value = None
                            try:
                                try:
                                    value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalHommesMoins35DeplaceInterne"]
                                except:
                                    value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalHommesMoins35DeplaceInterne"]
                            except Exception as exc:
                                value = None
                            population_internally_displaced_persons_young_h = value
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Déplacés internes", "Eff. (<=35)", "H", "ind_9_17")][count] = value
                            # End "Eff. Population", "Déplacés internes", "Eff. (<=35)", "H"

                            # "Eff. Population", "Déplacés internes", "Eff. (<=35)", "F"
                            population_internally_displaced_persons_young_f = None
                            value = None
                            try:
                                try:
                                    value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalFemmesMoins35DeplaceInterne"]
                                except:
                                    value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalFemmesMoins35DeplaceInterne"]
                            except Exception as exc:
                                value = None
                            population_internally_displaced_persons_young_f = value
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Déplacés internes", "Eff. (<=35)", "F", "ind_9_18")][count] = value
                            # End "Eff. Population", "Déplacés internes", "Eff. (<=35)", "F"

                            population_internally_displaced_persons_young = (population_internally_displaced_persons_young_f if population_internally_displaced_persons_young_f else 0) + (population_internally_displaced_persons_young_h if population_internally_displaced_persons_young_h else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Déplacés internes", "Eff. (<=35)", "T", "ind_9_19")][count] = population_internally_displaced_persons_young


                            # "Eff. Population", "Déplacés internes", "Eff. (>35)", "H"
                            population_internally_displaced_persons_old_h = None
                            value = None
                            try:
                                try:
                                    value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalHommesPlus35DeplaceInterne"]
                                except:
                                    value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalHommesPlus35DeplaceInterne"]
                            except Exception as exc:
                                value = None
                            population_internally_displaced_persons_old_h = value
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Déplacés internes", "Eff. (>35)", "H", "ind_9_20")][count] = value
                            # End "Eff. Population", "Déplacés internes", "Eff. (>35)", "H"

                            # "Eff. Population", "Déplacés internes", "Eff. (>35)", "F"
                            population_internally_displaced_persons_old_f = None
                            value = None
                            try:
                                try:
                                    value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalFemmesPlus35DeplaceInterne"]
                                except:
                                    value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalFemmesPlus35DeplaceInterne"]
                            except Exception as exc:
                                value = None
                            population_internally_displaced_persons_old_f = value
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Déplacés internes", "Eff. (>35)", "F", "ind_9_21")][count] = value
                            # End "Eff. Population", "Déplacés internes", "Eff. (>35)", "F"
                            
                            population_internally_displaced_persons_old = (population_internally_displaced_persons_old_f if population_internally_displaced_persons_old_f else 0) + (population_internally_displaced_persons_old_h if population_internally_displaced_persons_old_h else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Déplacés internes", "Eff. (>35)", "T", "ind_9_22")][count] = population_internally_displaced_persons_old

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Déplacés internes", "Total", "T", "ind_9_23")][count] = population_internally_displaced_persons_young + population_internally_displaced_persons_old

                            """End Déplacés internes"""


                            """Communautés d'accueil"""
                            # "Eff. Population", "Communautés d'accueil", "Eff. (<=35)", "H"
                            population_host_communities_young_h = None
                            value = None
                            try:
                                try:
                                    value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalHommesMoins35Refugie"]
                                except:
                                    value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalHommesMoins35Refugie"]
                            except Exception as exc:
                                value = None
                            population_host_communities_young_h = value
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Communautés d'accueil", "Eff. (<=35)", "H", "ind_9_24")][count] = value
                            # End "Eff. Population", "Communautés d'accueil", "Eff. (<=35)", "H"

                            # "Eff. Population", "Communautés d'accueil", "Eff. (<=35)", "F"
                            population_host_communities_young_f = None
                            value = None
                            try:
                                try:
                                    value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalFemmesMoins35Refugie"]
                                except:
                                    value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalFemmesMoins35Refugie"]
                            except Exception as exc:
                                value = None
                            population_host_communities_young_f = value
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Communautés d'accueil", "Eff. (<=35)", "F", "ind_9_25")][count] = value
                            # End "Eff. Population", "Communautés d'accueil", "Eff. (<=35)", "F"

                            population_host_communities_young = (population_host_communities_young_f if population_host_communities_young_f else 0) + (population_host_communities_young_h if population_host_communities_young_h else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Communautés d'accueil", "Eff. (<=35)", "T", "ind_9_26")][count] = population_host_communities_young


                            # "Eff. Population", "Communautés d'accueil", "Eff. (>35)", "H"
                            population_host_communities_old_h = None
                            value = None
                            try:
                                try:
                                    value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalHommesPlus35Refugie"]
                                except:
                                    value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalHommesPlus35Refugie"]
                            except Exception as exc:
                                value = None
                            population_host_communities_old_h = value
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Communautés d'accueil", "Eff. (>35)", "H", "ind_9_27")][count] = value
                            # End "Eff. Population", "Communautés d'accueil", "Eff. (>35)", "H"

                            # "Eff. Population", "Communautés d'accueil", "Eff. (>35)", "F"
                            population_host_communities_old_f = None
                            value = None
                            try:
                                try:
                                    value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalFemmesPlus35Refugie"]
                                except:
                                    value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalFemmesPlus35Refugie"]
                            except Exception as exc:
                                value = None
                            population_host_communities_old_f = value
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Communautés d'accueil", "Eff. (>35)", "F", "ind_9_28")][count] = value
                            # End "Eff. Population", "Communautés d'accueil", "Eff. (>35)", "F"
                            
                            population_host_communities_old = (population_host_communities_old_f if population_host_communities_old_f else 0) + (population_host_communities_old_h if population_host_communities_old_h else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Communautés d'accueil", "Eff. (>35)", "T", "ind_9_29")][count] = population_host_communities_old

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Communautés d'accueil", "Total", "T", "ind_9_30")][count] = population_host_communities_young + population_host_communities_old

                            """End Communautés d'accueil"""



                            # "Eff. Population", "Eff. (<=35)", "H"
                            population_young_h = None
                            value = None
                            percent_young_h = None
                            try:
                                try:
                                    value = get_datas_dict(form_response, "donnees", 1)["populationPersonnesJeunes"]["populationPersonnesJeunesTotal"]
                                    percent_young_h = get_datas_dict(form_response, "donnees", 1)["populationPersonnesJeunes"]["populationPersonnesJeunesProportionHomme"]
                                    percent_young_f = get_datas_dict(form_response, "donnees", 1)["populationPersonnesJeunes"]["populationPersonnesJeunesProportionFemmes"]
                                except:
                                    value = get_datas_dict(old_form_response, "donnees", 1)["populationPersonnesJeunes"]["populationPersonnesJeunesTotal"]
                                    percent_young_h = get_datas_dict(old_form_response, "donnees", 1)["populationPersonnesJeunes"]["populationPersonnesJeunesProportionHomme"]
                                    percent_young_f = get_datas_dict(old_form_response, "donnees", 1)["populationPersonnesJeunes"]["populationPersonnesJeunesProportionFemmes"]

                                if percent_young_f and percent_young_h:
                                    t = percent_young_f+percent_young_f
                                    if t == 100:
                                        value = ((value*percent_young_h)/100) if value and percent_young_h else None
                                    else:
                                        value = percent_young_h
                            except Exception as exc:
                                if not value:
                                    try:
                                        value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalHommesMoins35"]
                                    except:
                                        try:
                                            value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalHommesMoins35"]
                                        except:
                                            value = None
                            population_young_h = value if value else (population_refugees_young_h + population_internally_displaced_persons_young_h + population_host_communities_young_h)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Eff. Population", "Eff. (<=35)", "H", "ind_9_4")][count] = population_young_h
                            # End "Eff. Population", "Eff. (<=35)", "H"

                            # "Eff. Population", "Eff. (<=35)", "F"
                            value = None
                            percent_young_f = None
                            population_young_f = None
                            try:
                                try:
                                    value = get_datas_dict(form_response, "donnees", 1)["populationPersonnesJeunes"]["populationPersonnesJeunesTotal"]
                                    percent_young_f = get_datas_dict(form_response, "donnees", 1)["populationPersonnesJeunes"]["populationPersonnesJeunesProportionFemmes"]
                                    percent_young_h = get_datas_dict(form_response, "donnees", 1)["populationPersonnesJeunes"]["populationPersonnesJeunesProportionHomme"]
                                except:
                                    value = get_datas_dict(old_form_response, "donnees", 1)["populationPersonnesJeunes"]["populationPersonnesJeunesTotal"]
                                    percent_young_f = get_datas_dict(old_form_response, "donnees", 1)["populationPersonnesJeunes"]["populationPersonnesJeunesProportionFemmes"]
                                    percent_young_h = get_datas_dict(old_form_response, "donnees", 1)["populationPersonnesJeunes"]["populationPersonnesJeunesProportionHomme"]
                                    
                                if percent_young_f and percent_young_h:
                                    t = percent_young_f+percent_young_f
                                    if t == 100:
                                        value = ((value*percent_young_f)/100) if value and percent_young_f else None
                                    else:
                                        value = percent_young_f
                            except Exception as exc:
                                if not value:
                                    try:
                                        value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalFemmesMoins35"]
                                    except:
                                        try:
                                            value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalFemmesMoins35"]
                                        except:
                                            value = None
                            population_young_f = value if value else (population_refugees_young_f + population_internally_displaced_persons_young_f + population_host_communities_young_f)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Eff. Population", "Eff. (<=35)", "F", "ind_9_5")][count] = population_young_f
                            # End "Eff. Population", "Eff. (<=35)", "F"
                            
                            # "Eff. Population", "Eff. Jeunes"
                            young = None
                            value = None
                            try:
                                value = get_datas_dict(form_response, "donnees", 1)["populationPersonnesJeunes"]["populationPersonnesJeunesTotal"]
                            except Exception as exc:
                                try:
                                    value = get_datas_dict(old_form_response, "donnees", 1)["populationPersonnesJeunes"]["populationPersonnesJeunesTotal"]
                                except Exception as exc:
                                    value = None
                            young = value if value else (population_young_f + population_young_h)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Eff. Population", "Eff. Population", "Eff. Jeunes", "ind_9_3")][count] = young
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Eff. Population", "Eff. (<=35)", "T", "ind_9_6")][count] = young
                            # End "Eff. Population", "Eff. Jeunes"

                            # "Eff. Population", "Eff. (>35)", "H"
                            population_old_h = None
                            try:
                                value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalHommesPlus35"]
                            except:
                                try:
                                    value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalHommesPlus35"]
                                except:
                                    value = None
                            population_old_h = value if value else (population_refugees_old_h + population_internally_displaced_persons_old_h + population_host_communities_old_h)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Eff. Population", "Eff. (>35)", "H", "ind_9_7")][count] = population_old_h
                            # End "Eff. Population", "Eff. (>35)", "H"

                            # "Eff. Population", "Eff. (>35)", "F"
                            population_old_f = None
                            try:
                                value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalFemmesPlus35"]
                            except:
                                try:
                                    value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalFemmesPlus35"]
                                except:
                                    value = None
                            population_old_f = value if value else (population_refugees_old_f + population_internally_displaced_persons_old_f + population_host_communities_old_f)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Eff. Population", "Eff. (>35)", "F", "ind_9_8")][count] = population_old_f
                            # End "Eff. Population", "Eff. (>35)", "F"

                            old = (population_old_f+population_old_h) if population_old_f and population_old_h else (population - young if population and young else None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Eff. Population", "Eff. (>35)", "T", "ind_9_9")][count] = old

                            
                            value = None
                            try:
                                value = get_datas_dict(form_response, "population", 1)["populationNombreDeHommes"]
                            except Exception as exc:
                                try:
                                    value = get_datas_dict(old_form_response, "population", 1)["populationNombreDeHommes"]
                                except Exception as exc:
                                    value = None
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Eff. Population", "Eff. Population", "Eff. Hommes", "ind_9_1")][count] = value if value else (population_old_h + population_young_h if population_old_h and population_young_h else None)

                            value = None
                            try:
                                value = get_datas_dict(form_response, "population", 1)["populationNombreDeFemmes"]
                            except Exception as exc:
                                try:
                                    value = get_datas_dict(old_form_response, "population", 1)["populationNombreDeFemmes"]
                                except Exception as exc:
                                    value = None
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Eff. Population", "Eff. Population", "Eff. Population", "Eff. Femmes", "ind_9_2")][count] = value if value else (population_old_f + population_young_f if population_old_f and population_young_f else None)



                            try:
                                value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalHouseHolds"]
                            except Exception as exc:
                                try:
                                    value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["totalHouseHolds"]
                                except Exception as exc:
                                    value = None
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Nbre total ménages dans le village", "Nbre total ménages dans le village", "Nbre total ménages dans le village", "Nbre total ménages dans le village", "ind_10")][count] = value

                            try:
                                value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["nombreEthniques"]
                            except Exception as exc:
                                try:
                                    value = get_datas_dict(old_form_response, "generalitiesSurVillage", 1)["nombreEthniques"]
                                except Exception as exc:
                                    value = None
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "POPULATION", "Nbre total groupes ethniques dans le village", "Nbre total groupes ethniques dans le village", "Nbre total groupes ethniques dans le village", "Nbre total groupes ethniques dans le village", "ind_10_1")][count] = value


                            
                        elif _.get('sql_id') in [13] or comparer_chaines(_.get('name'), "Introduction et présentation de l'AC par l'AADB lors de la première réunion cantonale"): #Introduction et présentation de l'AC par l'AADB lors de la première réunion cantonale
                
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "Date de la séance", "Date de la séance", "ind_11")][count] = safe_get(form_response, 0).get("dateDeLaReunion", None)
                            

                            totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES - REFUGIES (<=35)", "H", "ind_17_1")][count] = totalHommesMoins35Refugie
                            
                            totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES - REFUGIES (<=35)", "F", "ind_17_2")][count] = totalFemmesMoins35Refugie

                            totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES - REFUGIES (<=35)", "T", "ind_17_3")][count] = totalMoins35Refugie

                            totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES - REFUGIES", "H", "ind_17_4")][count] = totalHommesPlus35Refugie

                            totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES - REFUGIES", "F", "ind_17_5")][count] = totalFemmesPlus35Refugie

                            totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES - REFUGIES", "T", "ind_17_6")][count] = totalPlus35Refugie

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_17_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                            


                            totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_17_7")][count] = totalHommesMoins35DeplaceInterne
                            
                            totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_17_8")][count] = totalFemmesMoins35DeplaceInterne

                            totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_17_9")][count] = totalMoins35DeplaceInterne

                            totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES - DEPLACES INTERNES", "H", "ind_17_10")][count] = totalHommesPlus35DeplaceInterne

                            totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES - DEPLACES INTERNES", "F", "ind_17_11")][count] = totalFemmesPlus35DeplaceInterne

                            totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES - DEPLACES INTERNES", "T", "ind_17_12")][count] = totalPlus35DeplaceInterne

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_17_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                            


                            totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_17_13")][count] = totalHommesMoins35CommunauteAcceuil
                            
                            totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_17_14")][count] = totalFemmesMoins35CommunauteAcceuil

                            totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_17_15")][count] = totalMoins35CommunauteAcceuil

                            totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_17_16")][count] = totalHommesPlus35CommunauteAcceuil

                            totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_17_17")][count] = totalFemmesPlus35CommunauteAcceuil

                            totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_17_18")][count] = totalPlus35CommunauteAcceuil

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_17_19_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                            
                            
                            if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                            else:
                                totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES (<=35)", "H", "ind_12")][count] = totalHommesMoins35
                            
                            if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                            else:
                                totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES (<=35)", "F", "ind_13")][count] = totalFemmesMoins35

                            if totalHommesMoins35 or totalFemmesMoins35:
                                totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                            else:
                                totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES (<=35)", "T", "ind_14")][count] = totalMoins35

                            if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                            else:
                                totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES", "H", "ind_15")][count] = totalHommes

                            if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                            else:
                                totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES", "F", "ind_16")][count] = totalFemmes

                            if totalHommes or totalFemmes:
                                totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                            else:
                                totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "NON JEUNES", "T", "ind_17")][count] = totalPlus35

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "TOTAL PARTICIPANTS", "T", "ind_17_0")][count] = totalPlus35 + totalMoins35


                        elif _.get('sql_id') in [17] or comparer_chaines(_.get('name'), "Présentation et clarification de votre mission"): #Présentation et clarification de votre mission
                            
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "Date de la séance", "Date de la séance", "ind_18")][count] = get_datas_dict(form_response, "dateDeLaReunion", 1, None)


                            totalHommesMoins35Refugie = get_datas_dict(form_response, "totalPersonnes", 1).get("totalHommesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES - REFUGIES (<=35)", "H", "ind_24_1")][count] = totalHommesMoins35Refugie
                            
                            totalFemmesMoins35Refugie = get_datas_dict(form_response, "totalPersonnes", 1).get("totalFemmesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES - REFUGIES (<=35)", "F", "ind_24_2")][count] = totalFemmesMoins35Refugie

                            totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES - REFUGIES (<=35)", "T", "ind_24_3")][count] = totalMoins35Refugie

                            totalHommesPlus35Refugie = get_datas_dict(form_response, "totalPersonnes", 1).get("totalHommesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES - REFUGIES", "H", "ind_24_4")][count] = totalHommesPlus35Refugie

                            totalFemmesPlus35Refugie = get_datas_dict(form_response, "totalPersonnes", 1).get("totalFemmesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES - REFUGIES", "F", "ind_24_5")][count] = totalFemmesPlus35Refugie

                            totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES - REFUGIES", "T", "ind_24_6")][count] = totalPlus35Refugie

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_24_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                            


                            totalHommesMoins35DeplaceInterne = get_datas_dict(form_response, "totalPersonnes", 1).get("totalHommesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_24_7")][count] = totalHommesMoins35DeplaceInterne
                            
                            totalFemmesMoins35DeplaceInterne = get_datas_dict(form_response, "totalPersonnes", 1).get("totalFemmesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_24_8")][count] = totalFemmesMoins35DeplaceInterne

                            totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_24_9")][count] = totalMoins35DeplaceInterne

                            totalHommesPlus35DeplaceInterne = get_datas_dict(form_response, "totalPersonnes", 1).get("totalHommesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES - DEPLACES INTERNES", "H", "ind_24_10")][count] = totalHommesPlus35DeplaceInterne

                            totalFemmesPlus35DeplaceInterne = get_datas_dict(form_response, "totalPersonnes", 1).get("totalFemmesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES - DEPLACES INTERNES", "F", "ind_24_11")][count] = totalFemmesPlus35DeplaceInterne

                            totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES - DEPLACES INTERNES", "T", "ind_24_12")][count] = totalPlus35DeplaceInterne

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_24_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                            


                            totalHommesMoins35CommunauteAcceuil = get_datas_dict(form_response, "totalPersonnes", 1).get("totalHommesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_24_13")][count] = totalHommesMoins35CommunauteAcceuil
                            
                            totalFemmesMoins35CommunauteAcceuil = get_datas_dict(form_response, "totalPersonnes", 1).get("totalFemmesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_24_14")][count] = totalFemmesMoins35CommunauteAcceuil

                            totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_24_15")][count] = totalMoins35CommunauteAcceuil

                            totalHommesPlus35CommunauteAcceuil = get_datas_dict(form_response, "totalPersonnes", 1).get("totalHommesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_24_16")][count] = totalHommesPlus35CommunauteAcceuil

                            totalFemmesPlus35CommunauteAcceuil = get_datas_dict(form_response, "totalPersonnes", 1).get("totalFemmesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_24_17")][count] = totalFemmesPlus35CommunauteAcceuil

                            totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_24_18")][count] = totalPlus35CommunauteAcceuil

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_24_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                            


                            if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                            else:
                                totalHommesMoins35 = get_datas_dict(form_response, "totalPersonnes", 1).get('totalHommesMoins35', None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES (<=35)", "H", "ind_19")][count] = totalHommesMoins35

                            if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                            else:
                                totalFemmesMoins35 = get_datas_dict(form_response, "totalPersonnes", 1).get('totalFemmesMoins35', None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES (<=35)", "F", "ind_20")][count] = totalFemmesMoins35

                            if totalHommesMoins35 or totalFemmesMoins35:
                                totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                            else:
                                totalMoins35 = get_datas_dict(form_response, "totalPersonnes", 1).get('totalMoins35', 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES (<=35)", "T", "ind_21")][count] = totalMoins35

                            if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                            else:
                                totalHommes = get_datas_dict(form_response, "totalPersonnes", 1).get('totalHommes', None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES", "H", "ind_22")][count] = totalHommes

                            if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                            else:
                                totalFemmes = get_datas_dict(form_response, "totalPersonnes", 1).get('totalFemmes', None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES", "F", "ind_23")][count] = totalFemmes

                            if totalHommes or totalFemmes:
                                totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                            else:
                                totalPlus35 = get_datas_dict(form_response, "totalPersonnes", 1).get('totalPlus35', 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "NON JEUNES", "T", "ind_24")][count] = totalPlus35

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "TOTAL PARTICIPANTS", "T", "ind_24_0")][count] = totalPlus35 + totalMoins35
                            

                        elif _.get('sql_id') in [22] or comparer_chaines(_.get('name'), "Brève introduction de la réunion et de l'ANADEB"): #Brève introduction de la réunion et de l'ANADEB
                            
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "Date de la séance", "Date de la séance", "ind_25")][count] = safe_get(form_response, 0).get("dateDeLaReunion", None)


                            totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES - REFUGIES (<=35)", "H", "ind_31_1")][count] = totalHommesMoins35Refugie
                            
                            totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES - REFUGIES (<=35)", "F", "ind_31_2")][count] = totalFemmesMoins35Refugie

                            totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES - REFUGIES (<=35)", "T", "ind_31_3")][count] = totalMoins35Refugie

                            totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES - REFUGIES", "H", "ind_31_4")][count] = totalHommesPlus35Refugie

                            totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES - REFUGIES", "F", "ind_31_5")][count] = totalFemmesPlus35Refugie

                            totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES - REFUGIES", "T", "ind_31_6")][count] = totalPlus35Refugie

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_31_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                            


                            totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_31_7")][count] = totalHommesMoins35DeplaceInterne
                            
                            totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_31_8")][count] = totalFemmesMoins35DeplaceInterne

                            totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_31_9")][count] = totalMoins35DeplaceInterne

                            totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES - DEPLACES INTERNES", "H", "ind_31_10")][count] = totalHommesPlus35DeplaceInterne

                            totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES - DEPLACES INTERNES", "F", "ind_31_11")][count] = totalFemmesPlus35DeplaceInterne

                            totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES - DEPLACES INTERNES", "T", "ind_31_12")][count] = totalPlus35DeplaceInterne

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_31_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                            

                            totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_31_13")][count] = totalHommesMoins35CommunauteAcceuil
                            
                            totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_31_14")][count] = totalFemmesMoins35CommunauteAcceuil

                            totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_31_15")][count] = totalMoins35CommunauteAcceuil

                            totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_31_16")][count] = totalHommesPlus35CommunauteAcceuil

                            totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_31_17")][count] = totalFemmesPlus35CommunauteAcceuil

                            totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_31_18")][count] = totalPlus35CommunauteAcceuil

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_31_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                            

                            
                            if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                            else:
                                totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES (<=35)", "H", "ind_26")][count] = totalHommesMoins35
                            
                            if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                            else:
                                totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES (<=35)", "F", "ind_27")][count] = totalFemmesMoins35

                            if totalHommesMoins35 or totalFemmesMoins35:
                                totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                            else:
                                totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES (<=35)", "T", "ind_28")][count] = totalMoins35

                            if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                            else:
                                totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES", "H", "ind_29")][count] = totalHommes

                            if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                            else:
                                totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES", "F", "ind_30")][count] = totalFemmes

                            if totalHommes or totalFemmes:
                                totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                            else:
                                totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "NON JEUNES", "T", "ind_31")][count] = totalPlus35

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "TOTAL PARTICIPANTS", "T", "ind_31_0")][count] = totalPlus35 + totalMoins35

                            
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "Nombre total de ménage", "Nombre total de ménage", "ind_32")][count] = safe_get(form_response, 0).get("totalMenages", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "Ethnies minoritaires", "Ethnies minoritaires", "ind_33")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                        elif _.get('sql_id') in [27] or comparer_chaines(_.get('name'), "Ouverture de la deuxième réunion et vérification du quorum des participants"): #Ouverture de la deuxième réunion et vérification du quorum des participants
                            
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "Date de la séance", "Date de la séance", "ind_34")][count] = safe_get(form_response, 0).get("dateDeLaReunion", None)
                                                    

                            totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES - REFUGIES (<=35)", "H", "ind_40_1")][count] = totalHommesMoins35Refugie
                            
                            totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES - REFUGIES (<=35)", "F", "ind_40_2")][count] = totalFemmesMoins35Refugie

                            totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES - REFUGIES (<=35)", "T", "ind_40_3")][count] = totalMoins35Refugie

                            totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES - REFUGIES", "H", "ind_40_4")][count] = totalHommesPlus35Refugie

                            totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES - REFUGIES", "F", "ind_40_5")][count] = totalFemmesPlus35Refugie

                            totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES - REFUGIES", "T", "ind_40_6")][count] = totalPlus35Refugie

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_40_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                            


                            totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_40_7")][count] = totalHommesMoins35DeplaceInterne
                            
                            totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_40_8")][count] = totalFemmesMoins35DeplaceInterne

                            totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_40_9")][count] = totalMoins35DeplaceInterne

                            totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "H", "ind_40_10")][count] = totalHommesPlus35DeplaceInterne

                            totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "F", "ind_40_11")][count] = totalFemmesPlus35DeplaceInterne

                            totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "T", "ind_40_12")][count] = totalPlus35DeplaceInterne

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_40_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                            

                            totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_40_13")][count] = totalHommesMoins35CommunauteAcceuil
                            
                            totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_40_14")][count] = totalFemmesMoins35CommunauteAcceuil

                            totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_40_15")][count] = totalMoins35CommunauteAcceuil

                            totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_40_16")][count] = totalHommesPlus35CommunauteAcceuil

                            totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_40_17")][count] = totalFemmesPlus35CommunauteAcceuil

                            totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_40_18")][count] = totalPlus35CommunauteAcceuil

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_40_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                            
                            
                            
                            if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                            else:
                                totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES (<=35)", "H", "ind_35")][count] = totalHommesMoins35
                            
                            if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                            else:
                                totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES (<=35)", "F", "ind_36")][count] = totalFemmesMoins35

                            if totalHommesMoins35 or totalFemmesMoins35:
                                totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                            else:
                                totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES (<=35)", "T", "ind_37")][count] = totalMoins35

                            if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                            else:
                                totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES", "H", "ind_38")][count] = totalHommes

                            if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                            else:
                                totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES", "F", "ind_39")][count] = totalFemmes

                            if totalHommes or totalFemmes:
                                totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                            else:
                                totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "NON JEUNES", "T", "ind_40")][count] = totalPlus35

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "TOTAL PARTICIPANTS", "T", "ind_40_0")][count] = totalPlus35 + totalMoins35


                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "Nombre total de ménage", "Nombre total de ménage", "ind_41")][count] = safe_get(form_response, 0).get("totalMenages", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "Ethnies minoritaires", "Ethnies minoritaires", "ind_42")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                        elif _.get('sql_id') in [37] or comparer_chaines(_.get('name'), "Animer la session de formation sur le Module 1 : rôles et responsabilités des membres des organes de CVD"): #Animer la session de formation sur le Module 1 : rôles et responsabilités des membres des organes de CVD
                            
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "Date de la séance", "Date de la séance", "ind_43")][count] = safe_get(form_response, 0).get("DateDeLaFormation", None)


                            totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES - REFUGIES (<=35)", "H", "ind_49_1")][count] = totalHommesMoins35Refugie
                            
                            totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES - REFUGIES (<=35)", "F", "ind_49_2")][count] = totalFemmesMoins35Refugie

                            totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES - REFUGIES (<=35)", "T", "ind_49_3")][count] = totalMoins35Refugie

                            totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES - REFUGIES", "H", "ind_49_4")][count] = totalHommesPlus35Refugie

                            totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES - REFUGIES", "F", "ind_49_5")][count] = totalFemmesPlus35Refugie

                            totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES - REFUGIES", "T", "ind_49_6")][count] = totalPlus35Refugie

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_49_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                            


                            totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_49_7")][count] = totalHommesMoins35DeplaceInterne
                            
                            totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_49_8")][count] = totalFemmesMoins35DeplaceInterne

                            totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_49_9")][count] = totalMoins35DeplaceInterne

                            totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES - DEPLACES INTERNES", "H", "ind_49_10")][count] = totalHommesPlus35DeplaceInterne

                            totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES - DEPLACES INTERNES", "F", "ind_49_11")][count] = totalFemmesPlus35DeplaceInterne

                            totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES - DEPLACES INTERNES", "T", "ind_49_12")][count] = totalPlus35DeplaceInterne

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_49_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                            
                            

                            totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_49_13")][count] = totalHommesMoins35CommunauteAcceuil
                            
                            totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_49_14")][count] = totalFemmesMoins35CommunauteAcceuil

                            totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_49_15")][count] = totalMoins35CommunauteAcceuil

                            totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_49_16")][count] = totalHommesPlus35CommunauteAcceuil

                            totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_49_17")][count] = totalFemmesPlus35CommunauteAcceuil

                            totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_49_18")][count] = totalPlus35CommunauteAcceuil

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_49_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                            
                            
                            
                            if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                            else:
                                totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES (<=35)", "H", "ind_44")][count] = totalHommesMoins35
                            
                            if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                            else:
                                totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES (<=35)", "F", "ind_45")][count] = totalFemmesMoins35

                            if totalHommesMoins35 or totalFemmesMoins35:
                                totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                            else:
                                totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES (<=35)", "T", "ind_46")][count] = totalMoins35

                            if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                            else:
                                totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES", "H", "ind_47")][count] = totalHommes

                            if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                            else:
                                totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES", "F", "ind_48")][count] = totalFemmes

                            if totalHommes or totalFemmes:
                                totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                            else:
                                totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "NON JEUNES", "T", "ind_49")][count] = totalPlus35

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "TOTAL PARTICIPANTS", "T", "ind_49_0")][count] = totalPlus35 + totalMoins35


                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "Nombre total de ménage", "Nombre total de ménage", "ind_50")][count] = safe_get(form_response, 0).get("totalMenages", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "Ethnies minoritaires", "Ethnies minoritaires", "ind_51")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                        elif _.get('sql_id') in [41] or comparer_chaines(_.get('name'), "Présenter les activités de la journée"): #Présenter les activités de la journée

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "Date de la séance", "Date de la séance", "ind_52")][count] = safe_get(form_response, 0).get("dateDeLaReunion", None)


                            totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES - REFUGIES (<=35)", "H", "ind_58_1")][count] = totalHommesMoins35Refugie
                            
                            totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES - REFUGIES (<=35)", "F", "ind_58_2")][count] = totalFemmesMoins35Refugie

                            totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES - REFUGIES (<=35)", "T", "ind_58_3")][count] = totalMoins35Refugie

                            totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES - REFUGIES", "H", "ind_58_4")][count] = totalHommesPlus35Refugie

                            totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES - REFUGIES", "F", "ind_58_5")][count] = totalFemmesPlus35Refugie

                            totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES - REFUGIES", "T", "ind_58_6")][count] = totalPlus35Refugie

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_58_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                            


                            totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_58_7")][count] = totalHommesMoins35DeplaceInterne
                            
                            totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_58_8")][count] = totalFemmesMoins35DeplaceInterne

                            totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_58_9")][count] = totalMoins35DeplaceInterne

                            totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "H", "ind_58_10")][count] = totalHommesPlus35DeplaceInterne

                            totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "F", "ind_58_11")][count] = totalFemmesPlus35DeplaceInterne

                            totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "T", "ind_58_12")][count] = totalPlus35DeplaceInterne

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_58_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                            
                            

                            totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_58_13")][count] = totalHommesMoins35CommunauteAcceuil
                            
                            totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_58_14")][count] = totalFemmesMoins35CommunauteAcceuil

                            totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_58_15")][count] = totalMoins35CommunauteAcceuil

                            totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_58_16")][count] = totalHommesPlus35CommunauteAcceuil

                            totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_58_17")][count] = totalFemmesPlus35CommunauteAcceuil

                            totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_58_18")][count] = totalPlus35CommunauteAcceuil

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_58_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil


                            
                            if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                            else:
                                totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES (<=35)", "H", "ind_53")][count] = totalHommesMoins35
                            
                            if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                            else:
                                totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES (<=35)", "F", "ind_54")][count] = totalFemmesMoins35

                            if totalHommesMoins35 or totalFemmesMoins35:
                                totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                            else:
                                totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES (<=35)", "T", "ind_55")][count] = totalMoins35

                            if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                            else:
                                totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES", "H", "ind_56")][count] = totalHommes

                            if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                            else:
                                totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES", "F", "ind_57")][count] = totalFemmes

                            if totalHommes or totalFemmes:
                                totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                            else:
                                totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "NON JEUNES", "T", "ind_58")][count] = totalPlus35

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "TOTAL PARTICIPANTS", "T", "ind_58_0")][count] = totalPlus35 + totalMoins35


                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "Nombre total de ménage", "Nombre total de ménage", "ind_59")][count] = safe_get(form_response, 0).get("totalMenages", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "Ethnies minoritaires", "Ethnies minoritaires", "ind_60")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                        elif _.get('sql_id') in [45] or comparer_chaines(_.get('name'), "Elaboration du plan d'action villageois (PAV)"): #Elaboration du plan d'action villageois (PAV)
                            
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "Date de la séance", "Date de la séance", "ind_61")][count] = safe_get(form_response, 0).get("dateDeLaReunion", None)


                            totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES - REFUGIES (<=35)", "H", "ind_67_1")][count] = totalHommesMoins35Refugie
                            
                            totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES - REFUGIES (<=35)", "F", "ind_67_2")][count] = totalFemmesMoins35Refugie

                            totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES - REFUGIES (<=35)", "T", "ind_67_3")][count] = totalMoins35Refugie

                            totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES - REFUGIES", "H", "ind_67_4")][count] = totalHommesPlus35Refugie

                            totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES - REFUGIES", "F", "ind_67_5")][count] = totalFemmesPlus35Refugie

                            totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES - REFUGIES", "T", "ind_67_6")][count] = totalPlus35Refugie

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_67_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                            


                            totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_67_7")][count] = totalHommesMoins35DeplaceInterne
                            
                            totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_67_8")][count] = totalFemmesMoins35DeplaceInterne

                            totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_67_9")][count] = totalMoins35DeplaceInterne

                            totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "H", "ind_67_10")][count] = totalHommesPlus35DeplaceInterne

                            totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "F", "ind_67_11")][count] = totalFemmesPlus35DeplaceInterne

                            totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "T", "ind_67_12")][count] = totalPlus35DeplaceInterne

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_67_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                            
                            

                            totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_67_13")][count] = totalHommesMoins35CommunauteAcceuil
                            
                            totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_67_14")][count] = totalFemmesMoins35CommunauteAcceuil

                            totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_67_15")][count] = totalMoins35CommunauteAcceuil

                            totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_67_16")][count] = totalHommesPlus35CommunauteAcceuil

                            totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_67_17")][count] = totalFemmesPlus35CommunauteAcceuil

                            totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_67_18")][count] = totalPlus35CommunauteAcceuil

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_67_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                            

                            
                            if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                            else:
                                totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES (<=35)", "H", "ind_62")][count] = totalHommesMoins35
                            
                            if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                            else:
                                totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES (<=35)", "F", "ind_63")][count] = totalFemmesMoins35

                            if totalHommesMoins35 or totalFemmesMoins35:
                                totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                            else:
                                totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES (<=35)", "T", "ind_64")][count] = totalMoins35

                            if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                            else:
                                totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES", "H", "ind_65")][count] = totalHommes

                            if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                            else:
                                totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES", "F", "ind_66")][count] = totalFemmes

                            if totalHommes or totalFemmes:
                                totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                            else:
                                totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "NON JEUNES", "T", "ind_67")][count] = totalPlus35

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "TOTAL PARTICIPANTS", "T", "ind_67_0")][count] = totalPlus35 + totalMoins35


                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "Nombre total de ménage", "Nombre total de ménage", "ind_68")][count] = safe_get(form_response, 0).get("totalMenages", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "Ethnies minoritaires", "Ethnies minoritaires", "ind_69")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                        elif _.get('sql_id') in [46] or comparer_chaines(_.get('name'), "Mise en place et/ou restructuration du comité cantonal de développement (CCD)  et du comité cantonal de gestion des plaintes (CCGP)"): #Mise en place et/ou restructuration du comité cantonal de développement (CCD)  et du comité cantonal de gestion des plaintes (CCGP)
                            
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "Date de la séance", "Date de la séance", "ind_70")][count] = safe_get(form_response, 0).get("dateDeLaReunion", None)


                            totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES - REFUGIES (<=35)", "H", "ind_76_1")][count] = totalHommesMoins35Refugie
                            
                            totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES - REFUGIES (<=35)", "F", "ind_76_2")][count] = totalFemmesMoins35Refugie

                            totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES - REFUGIES (<=35)", "T", "ind_76_3")][count] = totalMoins35Refugie

                            totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES - REFUGIES", "H", "ind_76_4")][count] = totalHommesPlus35Refugie

                            totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES - REFUGIES", "F", "ind_76_5")][count] = totalFemmesPlus35Refugie

                            totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES - REFUGIES", "T", "ind_76_6")][count] = totalPlus35Refugie

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_76_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                            


                            totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_76_7")][count] = totalHommesMoins35DeplaceInterne
                            
                            totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_76_8")][count] = totalFemmesMoins35DeplaceInterne

                            totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_76_9")][count] = totalMoins35DeplaceInterne

                            totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES - DEPLACES INTERNES", "H", "ind_76_10")][count] = totalHommesPlus35DeplaceInterne

                            totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES - DEPLACES INTERNES", "F", "ind_76_11")][count] = totalFemmesPlus35DeplaceInterne

                            totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES - DEPLACES INTERNES", "T", "ind_76_12")][count] = totalPlus35DeplaceInterne

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_76_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                            
                            

                            totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_76_13")][count] = totalHommesMoins35CommunauteAcceuil
                            
                            totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_76_14")][count] = totalFemmesMoins35CommunauteAcceuil

                            totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_76_15")][count] = totalMoins35CommunauteAcceuil

                            totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_76_16")][count] = totalHommesPlus35CommunauteAcceuil

                            totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_76_17")][count] = totalFemmesPlus35CommunauteAcceuil

                            totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_76_18")][count] = totalPlus35CommunauteAcceuil

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_76_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                            

                            
                            if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                            else:
                                totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES (<=35)", "H", "ind_71")][count] = totalHommesMoins35
                            
                            if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                            else:
                                totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES (<=35)", "F", "ind_72")][count] = totalFemmesMoins35

                            if totalHommesMoins35 or totalFemmesMoins35:
                                totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                            else:
                                totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES (<=35)", "T", "ind_73")][count] = totalMoins35

                            if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                            else:
                                totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES", "H", "ind_74")][count] = totalHommes

                            if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                            else:
                                totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES", "F", "ind_75")][count] = totalFemmes

                            if totalHommes or totalFemmes:
                                totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                            else:
                                totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "NON JEUNES", "T", "ind_76")][count] = totalPlus35

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "TOTAL PARTICIPANTS", "T", "ind_76_0")][count] = totalPlus35 + totalMoins35


                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "Nombre total de ménage", "Nombre total de ménage", "ind_77")][count] = safe_get(form_response, 0).get("totalMenages", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "Ethnies minoritaires", "Ethnies minoritaires", "ind_78")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                        elif _.get('sql_id') in [47] or comparer_chaines(_.get('name'), "Appui au CCD dans  l'analyse des PAV des villages, l'arbitrage, la sélection des sous - projets à financer et l'affection des ressources par sous - projet"): #Appui au CCD dans  l'analyse des PAV des villages, l'arbitrage, la sélection des sous - projets à financer et l'affection des ressources par sous - projet
                            
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "Date de la séance", "Date de la séance", "ind_79")][count] = safe_get(form_response, 0).get("dateDeLaReunion", None)

                            
                            totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES - REFUGIES (<=35)", "H", "ind_85_1")][count] = totalHommesMoins35Refugie
                            
                            totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES - REFUGIES (<=35)", "F", "ind_85_2")][count] = totalFemmesMoins35Refugie

                            totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES - REFUGIES (<=35)", "T", "ind_85_3")][count] = totalMoins35Refugie

                            totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES - REFUGIES", "H", "ind_85_4")][count] = totalHommesPlus35Refugie

                            totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES - REFUGIES", "F", "ind_85_5")][count] = totalFemmesPlus35Refugie

                            totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES - REFUGIES", "T", "ind_85_6")][count] = totalPlus35Refugie

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_85_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                            


                            totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_85_7")][count] = totalHommesMoins35DeplaceInterne
                            
                            totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_85_8")][count] = totalFemmesMoins35DeplaceInterne

                            totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_85_9")][count] = totalMoins35DeplaceInterne

                            totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES - DEPLACES INTERNES", "H", "ind_85_10")][count] = totalHommesPlus35DeplaceInterne

                            totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES - DEPLACES INTERNES", "F", "ind_85_11")][count] = totalFemmesPlus35DeplaceInterne

                            totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES - DEPLACES INTERNES", "T", "ind_85_12")][count] = totalPlus35DeplaceInterne

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_85_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                            
                            

                            totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_85_13")][count] = totalHommesMoins35CommunauteAcceuil
                            
                            totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_85_14")][count] = totalFemmesMoins35CommunauteAcceuil

                            totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_85_15")][count] = totalMoins35CommunauteAcceuil

                            totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_85_16")][count] = totalHommesPlus35CommunauteAcceuil

                            totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_85_17")][count] = totalFemmesPlus35CommunauteAcceuil

                            totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_85_18")][count] = totalPlus35CommunauteAcceuil

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_85_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                            

                            
                            if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                            else:
                                totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES (<=35)", "H", "ind_80")][count] = totalHommesMoins35
                            
                            if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                            else:
                                totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES (<=35)", "F", "ind_81")][count] = totalFemmesMoins35

                            if totalHommesMoins35 or totalFemmesMoins35:
                                totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                            else:
                                totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES (<=35)", "T", "ind_82")][count] = totalMoins35

                            if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                            else:
                                totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES", "H", "ind_83")][count] = totalHommes

                            if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                            else:
                                totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES", "F", "ind_84")][count] = totalFemmes

                            if totalHommes or totalFemmes:
                                totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                            else:
                                totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "NON JEUNES", "T", "ind_85")][count] = totalPlus35

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "TOTAL PARTICIPANTS", "T", "ind_85_0")][count] = totalPlus35 + totalMoins35


                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "Nombre total de ménage", "Nombre total de ménage", "ind_86")][count] = safe_get(form_response, 0).get("totalMenages", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "Ethnies minoritaires", "Ethnies minoritaires", "ind_87")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                        elif _.get('sql_id') in [48] or comparer_chaines(_.get('name'), "Appui à l'organisation et à la facilitation de rencontre  communautaire de restitution des résultats de la reunion cantonale d'arbitrage"): #Appui à l'organisation et à la facilitation de rencontre  communautaire de restitution des résultats de la reunion cantonale d'arbitrage
                            
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "Date de la séance", "Date de la séance", "ind_88")][count] = safe_get(form_response, 0).get("dateDeLaReunion", None)

                            
                            totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES - REFUGIES (<=35)", "H", "ind_94_1")][count] = totalHommesMoins35Refugie
                            
                            totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES - REFUGIES (<=35)", "F", "ind_94_2")][count] = totalFemmesMoins35Refugie

                            totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES - REFUGIES (<=35)", "T", "ind_94_3")][count] = totalMoins35Refugie

                            totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES - REFUGIES", "H", "ind_94_4")][count] = totalHommesPlus35Refugie

                            totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES - REFUGIES", "F", "ind_94_5")][count] = totalFemmesPlus35Refugie

                            totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES - REFUGIES", "T", "ind_94_6")][count] = totalPlus35Refugie

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_94_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                            


                            totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_94_7")][count] = totalHommesMoins35DeplaceInterne
                            
                            totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_94_8")][count] = totalFemmesMoins35DeplaceInterne

                            totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_94_9")][count] = totalMoins35DeplaceInterne

                            totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "H", "ind_94_10")][count] = totalHommesPlus35DeplaceInterne

                            totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "F", "ind_94_11")][count] = totalFemmesPlus35DeplaceInterne

                            totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "T", "ind_94_12")][count] = totalPlus35DeplaceInterne

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_94_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                            
                            

                            totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_94_13")][count] = totalHommesMoins35CommunauteAcceuil
                            
                            totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_94_14")][count] = totalFemmesMoins35CommunauteAcceuil

                            totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_94_15")][count] = totalMoins35CommunauteAcceuil

                            totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_94_16")][count] = totalHommesPlus35CommunauteAcceuil

                            totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_94_17")][count] = totalFemmesPlus35CommunauteAcceuil

                            totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_94_18")][count] = totalPlus35CommunauteAcceuil

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_94_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                            

                            
                            if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                            else:
                                totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES (<=35)", "H", "ind_89")][count] = totalHommesMoins35
                            
                            if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                            else:
                                totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES (<=35)", "F", "ind_90")][count] = totalFemmesMoins35

                            if totalHommesMoins35 or totalFemmesMoins35:
                                totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                            else:
                                totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES (<=35)", "T", "ind_91")][count] = totalMoins35

                            if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                            else:
                                totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES", "H", "ind_92")][count] = totalHommes

                            if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                            else:
                                totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES", "F", "ind_93")][count] = totalFemmes

                            if totalHommes or totalFemmes:
                                totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                            else:
                                totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "NON JEUNES", "T", "ind_94")][count] = totalPlus35

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "TOTAL PARTICIPANTS", "T", "ind_94_0")][count] = totalPlus35 + totalMoins35


                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "Nombre total de ménage", "Nombre total de ménage", "ind_95")][count] = safe_get(form_response, 0).get("totalMenages", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "Ethnies minoritaires", "Ethnies minoritaires", "ind_96")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                        elif _.get('sql_id') in [49] or comparer_chaines(_.get('name'), "Appuie au bureau du CVD  dans la rédaction du document du sous projet et la demande de financement"): #Appuie au bureau du CVD  dans la rédaction du document du sous projet et la demande de financement
                            
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "Date de la séance", "Date de la séance", "ind_97")][count] = safe_get(form_response, 0).get("dateDeSeance", None)

                            
                            totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES - REFUGIES (<=35)", "H", "ind_103_1")][count] = totalHommesMoins35Refugie
                            
                            totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES - REFUGIES (<=35)", "F", "ind_103_2")][count] = totalFemmesMoins35Refugie

                            totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES - REFUGIES (<=35)", "T", "ind_103_3")][count] = totalMoins35Refugie

                            totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES - REFUGIES", "H", "ind_103_4")][count] = totalHommesPlus35Refugie

                            totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES - REFUGIES", "F", "ind_103_5")][count] = totalFemmesPlus35Refugie

                            totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES - REFUGIES", "T", "ind_103_6")][count] = totalPlus35Refugie

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_103_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                            


                            totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_103_7")][count] = totalHommesMoins35DeplaceInterne
                            
                            totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_103_8")][count] = totalFemmesMoins35DeplaceInterne

                            totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_103_9")][count] = totalMoins35DeplaceInterne

                            totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES - DEPLACES INTERNES", "H", "ind_103_10")][count] = totalHommesPlus35DeplaceInterne

                            totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES - DEPLACES INTERNES", "F", "ind_103_11")][count] = totalFemmesPlus35DeplaceInterne

                            totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES - DEPLACES INTERNES", "T", "ind_103_12")][count] = totalPlus35DeplaceInterne

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_103_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                            
                            

                            totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_103_13")][count] = totalHommesMoins35CommunauteAcceuil
                            
                            totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_103_14")][count] = totalFemmesMoins35CommunauteAcceuil

                            totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_103_15")][count] = totalMoins35CommunauteAcceuil

                            totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_103_16")][count] = totalHommesPlus35CommunauteAcceuil

                            totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_103_17")][count] = totalFemmesPlus35CommunauteAcceuil

                            totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_103_18")][count] = totalPlus35CommunauteAcceuil

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_103_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                            

                            
                            if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                            else:
                                totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES (<=35)", "H", "ind_98")][count] = totalHommesMoins35
                            
                            if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                            else:
                                totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES (<=35)", "F", "ind_99")][count] = totalFemmesMoins35

                            if totalHommesMoins35 or totalFemmesMoins35:
                                totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                            else:
                                totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES (<=35)", "T", "ind_100")][count] = totalMoins35

                            if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                            else:
                                totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES", "H", "ind_101")][count] = totalHommes

                            if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                            else:
                                totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES", "F", "ind_102")][count] = totalFemmes

                            if totalHommes or totalFemmes:
                                totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                            else:
                                totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "NON JEUNES", "T", "ind_103")][count] = totalPlus35

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "TOTAL PARTICIPANTS", "T", "ind_103_0")][count] = totalPlus35 + totalMoins35


                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "Nombre total de ménage", "Nombre total de ménage", "ind_104")][count] = safe_get(form_response, 0).get("totalMenages", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "Ethnies minoritaires", "Ethnies minoritaires", "ind_105")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                        elif _.get('sql_id') in [50] or comparer_chaines(_.get('name'), "Réunion d'information de la communauté sur le sous projet: activités, coût estimatif et prochainbes étapes"): #Réunion d'information de la communauté sur le sous projet: activités, coût estimatif et prochainbes étapes
                            
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "Date de la séance", "Date de la séance", "ind_106")][count] = safe_get(form_response, 0).get("dateDeLaReunion", None)


                            totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES - REFUGIES (<=35)", "H", "ind_112_1")][count] = totalHommesMoins35Refugie
                            
                            totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES - REFUGIES (<=35)", "F", "ind_112_2")][count] = totalFemmesMoins35Refugie

                            totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES - REFUGIES (<=35)", "T", "ind_112_3")][count] = totalMoins35Refugie

                            totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES - REFUGIES", "H", "ind_112_4")][count] = totalHommesPlus35Refugie

                            totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES - REFUGIES", "F", "ind_112_5")][count] = totalFemmesPlus35Refugie

                            totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES - REFUGIES", "T", "ind_112_6")][count] = totalPlus35Refugie

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_112_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                            


                            totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_112_7")][count] = totalHommesMoins35DeplaceInterne
                            
                            totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_112_8")][count] = totalFemmesMoins35DeplaceInterne

                            totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_112_9")][count] = totalMoins35DeplaceInterne

                            totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "H", "ind_112_10")][count] = totalHommesPlus35DeplaceInterne

                            totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "F", "ind_112_11")][count] = totalFemmesPlus35DeplaceInterne

                            totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES - DEPLACES INTERNES", "T", "ind_112_12")][count] = totalPlus35DeplaceInterne

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_112_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                            
                            

                            totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_112_13")][count] = totalHommesMoins35CommunauteAcceuil
                            
                            totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_112_14")][count] = totalFemmesMoins35CommunauteAcceuil

                            totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_112_15")][count] = totalMoins35CommunauteAcceuil

                            totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_112_16")][count] = totalHommesPlus35CommunauteAcceuil

                            totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_112_17")][count] = totalFemmesPlus35CommunauteAcceuil

                            totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_112_18")][count] = totalPlus35CommunauteAcceuil

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_112_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                            

                            
                            if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                            else:
                                totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES (<=35)", "H", "ind_107")][count] = totalHommesMoins35
                            
                            if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                            else:
                                totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES (<=35)", "F", "ind_108")][count] = totalFemmesMoins35

                            if totalHommesMoins35 or totalFemmesMoins35:
                                totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                            else:
                                totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES (<=35)", "T", "ind_109")][count] = totalMoins35

                            if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                            else:
                                totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES", "H", "ind_110")][count] = totalHommes

                            if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                            else:
                                totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES", "F", "ind_111")][count] = totalFemmes

                            if totalHommes or totalFemmes:
                                totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                            else:
                                totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "NON JEUNES", "T", "ind_112")][count] = totalPlus35

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "TOTAL PARTICIPANTS", "T", "ind_112_0")][count] = totalPlus35 + totalMoins35


                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "Nombre total de ménage", "Nombre total de ménage", "ind_113")][count] = safe_get(form_response, 0).get("totalMenages", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "Ethnies minoritaires", "Ethnies minoritaires", "ind_114")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                        elif _.get('sql_id') in [51] or comparer_chaines(_.get('name'), "Soumission de la demande de financement du sous-projet à l’ANADEB pour approbation par le CORA"): #Soumission de la demande de financement du sous-projet à l’ANADEB pour approbation par le CORA
                            
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "Date de la séance", "Date de la séance", "ind_115")][count] = safe_get(form_response, 0).get("dateDeSoumission", None)


                            totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES - REFUGIES (<=35)", "H", "ind_121_1")][count] = totalHommesMoins35Refugie
                            
                            totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES - REFUGIES (<=35)", "F", "ind_121_2")][count] = totalFemmesMoins35Refugie

                            totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES - REFUGIES (<=35)", "T", "ind_121_3")][count] = totalMoins35Refugie

                            totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES - REFUGIES", "H", "ind_121_4")][count] = totalHommesPlus35Refugie

                            totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES - REFUGIES", "F", "ind_121_5")][count] = totalFemmesPlus35Refugie

                            totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES - REFUGIES", "T", "ind_121_6")][count] = totalPlus35Refugie

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_121_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                            


                            totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_121_7")][count] = totalHommesMoins35DeplaceInterne
                            
                            totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_121_8")][count] = totalFemmesMoins35DeplaceInterne

                            totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_121_9")][count] = totalMoins35DeplaceInterne

                            totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES - DEPLACES INTERNES", "H", "ind_121_10")][count] = totalHommesPlus35DeplaceInterne

                            totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES - DEPLACES INTERNES", "F", "ind_121_11")][count] = totalFemmesPlus35DeplaceInterne

                            totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES - DEPLACES INTERNES", "T", "ind_121_12")][count] = totalPlus35DeplaceInterne

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_121_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                            
                            

                            totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_121_13")][count] = totalHommesMoins35CommunauteAcceuil
                            
                            totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_121_14")][count] = totalFemmesMoins35CommunauteAcceuil

                            totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_121_15")][count] = totalMoins35CommunauteAcceuil

                            totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_121_16")][count] = totalHommesPlus35CommunauteAcceuil

                            totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_121_17")][count] = totalFemmesPlus35CommunauteAcceuil

                            totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_121_18")][count] = totalPlus35CommunauteAcceuil

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_121_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                            

                            
                            if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                            else:
                                totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES (<=35)", "H", "ind_116")][count] = totalHommesMoins35
                            
                            if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                            else:
                                totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES (<=35)", "F", "ind_117")][count] = totalFemmesMoins35

                            if totalHommesMoins35 or totalFemmesMoins35:
                                totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                            else:
                                totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES (<=35)", "T", "ind_118")][count] = totalMoins35

                            if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                            else:
                                totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES", "H", "ind_119")][count] = totalHommes

                            if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                            else:
                                totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES", "F", "ind_120")][count] = totalFemmes

                            if totalHommes or totalFemmes:
                                totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                            else:
                                totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "NON JEUNES", "T", "ind_121")][count] = totalPlus35

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "TOTAL PARTICIPANTS", "T", "ind_121_0")][count] = totalPlus35 + totalMoins35


                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "Nombre total de ménage", "Nombre total de ménage", "ind_122")][count] = safe_get(form_response, 0).get("totalMenages", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "Ethnies minoritaires", "Ethnies minoritaires", "ind_123")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                        elif _.get('sql_id') in [52] or comparer_chaines(_.get('name'), "Séance communautaire d'information sur les grandes lignes  du sous projet, sa durée d'exécution et les mesures de sauvegardes à observer"): #Séance communautaire d'information sur les grandes lignes  du sous projet, sa durée d'exécution et les mesures de sauvegardes à observer
                            
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "Date de la séance", "Date de la séance", "ind_124")][count] = safe_get(form_response, 0).get("dateDeSeance", None)


                            totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES - REFUGIES (<=35)", "H", "ind_130_1")][count] = totalHommesMoins35Refugie
                            
                            totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES - REFUGIES (<=35)", "F", "ind_130_2")][count] = totalFemmesMoins35Refugie

                            totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES - REFUGIES (<=35)", "T", "ind_130_3")][count] = totalMoins35Refugie

                            totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES - REFUGIES", "H", "ind_130_4")][count] = totalHommesPlus35Refugie

                            totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES - REFUGIES", "F", "ind_130_5")][count] = totalFemmesPlus35Refugie

                            totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES - REFUGIES", "T", "ind_130_6")][count] = totalPlus35Refugie

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_130_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                            


                            totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_130_7")][count] = totalHommesMoins35DeplaceInterne
                            
                            totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_130_8")][count] = totalFemmesMoins35DeplaceInterne

                            totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_130_9")][count] = totalMoins35DeplaceInterne

                            totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES - DEPLACES INTERNES", "H", "ind_130_10")][count] = totalHommesPlus35DeplaceInterne

                            totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES - DEPLACES INTERNES", "F", "ind_130_11")][count] = totalFemmesPlus35DeplaceInterne

                            totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES - DEPLACES INTERNES", "T", "ind_130_12")][count] = totalPlus35DeplaceInterne

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_130_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                            
                            

                            totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_130_13")][count] = totalHommesMoins35CommunauteAcceuil
                            
                            totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_130_14")][count] = totalFemmesMoins35CommunauteAcceuil

                            totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_130_15")][count] = totalMoins35CommunauteAcceuil

                            totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_130_16")][count] = totalHommesPlus35CommunauteAcceuil

                            totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_130_17")][count] = totalFemmesPlus35CommunauteAcceuil

                            totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_130_18")][count] = totalPlus35CommunauteAcceuil

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_130_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                            

                            
                            if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                            else:
                                totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES (<=35)", "H", "ind_125")][count] = totalHommesMoins35
                            
                            if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                            else:
                                totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES (<=35)", "F", "ind_126")][count] = totalFemmesMoins35

                            if totalHommesMoins35 or totalFemmesMoins35:
                                totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                            else:
                                totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES (<=35)", "T", "ind_127")][count] = totalMoins35

                            if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                            else:
                                totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES", "H", "ind_128")][count] = totalHommes

                            if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                            else:
                                totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES", "F", "ind_129")][count] = totalFemmes

                            if totalHommes or totalFemmes:
                                totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                            else:
                                totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "NON JEUNES", "T", "ind_130")][count] = totalPlus35

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "TOTAL PARTICIPANTS", "T", "ind_130_0")][count] = totalPlus35 + totalMoins35


                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "Nombre total de ménage", "Nombre total de ménage", "ind_131")][count] = safe_get(form_response, 0).get("totalMenages", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "Ethnies minoritaires", "Ethnies minoritaires", "ind_132")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                        elif _.get('sql_id') in [53] or comparer_chaines(_.get('name'), "Appuie au CVD dans la production des rapports périodiques et l'organisation des réunions d'échanges sur l'état d'avancement des travaux"): #Appuie au CVD dans la production des rapports périodiques et l'organisation des réunions d'échanges sur l'état d'avancement des travaux
                            
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "Date de la séance", "Date de la séance", "ind_133")][count] = safe_get(form_response, 0).get("dateDeLaReunion", None)


                            totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES - REFUGIES (<=35)", "H", "ind_139_1")][count] = totalHommesMoins35Refugie
                            
                            totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES - REFUGIES (<=35)", "F", "ind_139_2")][count] = totalFemmesMoins35Refugie

                            totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES - REFUGIES (<=35)", "T", "ind_139_3")][count] = totalMoins35Refugie

                            totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES - REFUGIES", "H", "ind_139_4")][count] = totalHommesPlus35Refugie

                            totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES - REFUGIES", "F", "ind_139_5")][count] = totalFemmesPlus35Refugie

                            totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES - REFUGIES", "T", "ind_139_6")][count] = totalPlus35Refugie

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_139_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                            


                            totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_139_7")][count] = totalHommesMoins35DeplaceInterne
                            
                            totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_139_8")][count] = totalFemmesMoins35DeplaceInterne

                            totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_139_9")][count] = totalMoins35DeplaceInterne

                            totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES - DEPLACES INTERNES", "H", "ind_139_10")][count] = totalHommesPlus35DeplaceInterne

                            totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES - DEPLACES INTERNES", "F", "ind_139_11")][count] = totalFemmesPlus35DeplaceInterne

                            totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES - DEPLACES INTERNES", "T", "ind_139_12")][count] = totalPlus35DeplaceInterne

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_139_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                                                                    

                            totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_139_13")][count] = totalHommesMoins35CommunauteAcceuil
                            
                            totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_139_14")][count] = totalFemmesMoins35CommunauteAcceuil

                            totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_139_15")][count] = totalMoins35CommunauteAcceuil

                            totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_139_16")][count] = totalHommesPlus35CommunauteAcceuil

                            totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_139_17")][count] = totalFemmesPlus35CommunauteAcceuil

                            totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_139_18")][count] = totalPlus35CommunauteAcceuil

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_139_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                            
                            
                            if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                            else:
                                totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES (<=35)", "H", "ind_134")][count] = totalHommesMoins35
                            
                            if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                            else:
                                totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES (<=35)", "F", "ind_135")][count] = totalFemmesMoins35

                            if totalHommesMoins35 or totalFemmesMoins35:
                                totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                            else:
                                totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES (<=35)", "T", "ind_136")][count] = totalMoins35

                            if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                            else:
                                totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES", "H", "ind_137")][count] = totalHommes

                            if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                            else:
                                totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES", "F", "ind_138")][count] = totalFemmes

                            if totalHommes or totalFemmes:
                                totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                            else:
                                totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "NON JEUNES", "T", "ind_139")][count] = totalPlus35

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "TOTAL PARTICIPANTS", "T", "ind_139_0")][count] = totalPlus35 + totalMoins35


                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "Nombre total de ménage", "Nombre total de ménage", "ind_140")][count] = safe_get(form_response, 0).get("totalMenages", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "Ethnies minoritaires", "Ethnies minoritaires", "ind_141")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                        elif _.get('sql_id') in [54] or comparer_chaines(_.get('name'), "Classement et archivage de tous les documents relatifs à la mise en œuvre du sous projet"): #Classement et archivage de tous les documents relatifs à la mise en œuvre du sous projet
                            
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "Date de la séance", "Date de la séance", "ind_142")][count] = safe_get(form_response, 0).get("dateDeLaReunion", None)


                            totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES - REFUGIES (<=35)", "H", "ind_148_1")][count] = totalHommesMoins35Refugie
                            
                            totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES - REFUGIES (<=35)", "F", "ind_148_2")][count] = totalFemmesMoins35Refugie

                            totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES - REFUGIES (<=35)", "T", "ind_148_3")][count] = totalMoins35Refugie

                            totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES - REFUGIES", "H", "ind_148_4")][count] = totalHommesPlus35Refugie

                            totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES - REFUGIES", "F", "ind_148_5")][count] = totalFemmesPlus35Refugie

                            totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES - REFUGIES", "T", "ind_148_6")][count] = totalPlus35Refugie

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_148_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                            


                            totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_148_7")][count] = totalHommesMoins35DeplaceInterne
                            
                            totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_148_8")][count] = totalFemmesMoins35DeplaceInterne

                            totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_148_9")][count] = totalMoins35DeplaceInterne

                            totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES - DEPLACES INTERNES", "H", "ind_148_10")][count] = totalHommesPlus35DeplaceInterne

                            totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES - DEPLACES INTERNES", "F", "ind_148_11")][count] = totalFemmesPlus35DeplaceInterne

                            totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES - DEPLACES INTERNES", "T", "ind_148_12")][count] = totalPlus35DeplaceInterne

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_148_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                                                                    

                            totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_148_13")][count] = totalHommesMoins35CommunauteAcceuil
                            
                            totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_148_14")][count] = totalFemmesMoins35CommunauteAcceuil

                            totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_148_15")][count] = totalMoins35CommunauteAcceuil

                            totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_148_16")][count] = totalHommesPlus35CommunauteAcceuil

                            totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_148_17")][count] = totalFemmesPlus35CommunauteAcceuil

                            totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_148_18")][count] = totalPlus35CommunauteAcceuil

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_148_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                            
                            
                            if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                            else:
                                totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES (<=35)", "H", "ind_143")][count] = totalHommesMoins35
                            
                            if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                            else:
                                totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES (<=35)", "F", "ind_144")][count] = totalFemmesMoins35

                            if totalHommesMoins35 or totalFemmesMoins35:
                                totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                            else:
                                totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES (<=35)", "T", "ind_145")][count] = totalMoins35

                            if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                            else:
                                totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES", "H", "ind_146")][count] = totalHommes

                            if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                            else:
                                totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES", "F", "ind_147")][count] = totalFemmes

                            if totalHommes or totalFemmes:
                                totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                            else:
                                totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "NON JEUNES", "T", "ind_148")][count] = totalPlus35

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "TOTAL PARTICIPANTS", "T", "ind_148_0")][count] = totalPlus35 + totalMoins35


                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "Nombre total de ménage", "Nombre total de ménage", "ind_149")][count] = safe_get(form_response, 0).get("totalMenages", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "Ethnies minoritaires", "Ethnies minoritaires", "ind_150")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                        elif _.get('sql_id') in [55] or comparer_chaines(_.get('name'), "Réalisation de l'auto évaluation participative de la mise en œuvre du sous projet"): #Réalisation de l'auto évaluation participative de la mise en œuvre du sous projet
                            
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "Date de la séance", "Date de la séance", "ind_151")][count] = safe_get(form_response, 0).get("dateDeSeance", None)


                            totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES - REFUGIES (<=35)", "H", "ind_157_1")][count] = totalHommesMoins35Refugie
                            
                            totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES - REFUGIES (<=35)", "F", "ind_157_2")][count] = totalFemmesMoins35Refugie

                            totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES - REFUGIES (<=35)", "T", "ind_157_3")][count] = totalMoins35Refugie

                            totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES - REFUGIES", "H", "ind_157_4")][count] = totalHommesPlus35Refugie

                            totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES - REFUGIES", "F", "ind_157_5")][count] = totalFemmesPlus35Refugie

                            totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES - REFUGIES", "T", "ind_157_6")][count] = totalPlus35Refugie

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_157_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                            

                            totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_157_7")][count] = totalHommesMoins35DeplaceInterne
                            
                            totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_157_8")][count] = totalFemmesMoins35DeplaceInterne

                            totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_157_9")][count] = totalMoins35DeplaceInterne

                            totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES - DEPLACES INTERNES", "H", "ind_157_10")][count] = totalHommesPlus35DeplaceInterne

                            totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES - DEPLACES INTERNES", "F", "ind_157_11")][count] = totalFemmesPlus35DeplaceInterne

                            totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES - DEPLACES INTERNES", "T", "ind_157_12")][count] = totalPlus35DeplaceInterne

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_157_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                                                                    

                            totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_157_13")][count] = totalHommesMoins35CommunauteAcceuil
                            
                            totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_157_14")][count] = totalFemmesMoins35CommunauteAcceuil

                            totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_157_15")][count] = totalMoins35CommunauteAcceuil

                            totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_157_16")][count] = totalHommesPlus35CommunauteAcceuil

                            totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_157_17")][count] = totalFemmesPlus35CommunauteAcceuil

                            totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_157_18")][count] = totalPlus35CommunauteAcceuil

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_157_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                            
                            
                            if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                            else:
                                totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES (<=35)", "H", "ind_152")][count] = totalHommesMoins35
                            
                            if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                            else:
                                totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES (<=35)", "F", "ind_153")][count] = totalFemmesMoins35

                            if totalHommesMoins35 or totalFemmesMoins35:
                                totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                            else:
                                totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES (<=35)", "T", "ind_154")][count] = totalMoins35

                            if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                            else:
                                totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES", "H", "ind_155")][count] = totalHommes

                            if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                            else:
                                totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES", "F", "ind_156")][count] = totalFemmes

                            if totalHommes or totalFemmes:
                                totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                            else:
                                totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "NON JEUNES", "T", "ind_157")][count] = totalPlus35

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "TOTAL PARTICIPANTS", "T", "ind_157_0")][count] = totalPlus35 + totalMoins35


                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "Nombre total de ménage", "Nombre total de ménage", "ind_158")][count] = safe_get(form_response, 0).get("totalMenages", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "Ethnies minoritaires", "Ethnies minoritaires", "ind_159")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


                        elif _.get('sql_id') in [56] or comparer_chaines(_.get('name'), "Elaboration et mise en oeuvre du plan d'entretien et de maintenance de l'ouvrage"): #Elaboration et mise en oeuvre du plan d'entretien et de maintenance de l'ouvrage
                            
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "Date de la sensibilisation", "Date de la sensibilisation", "ind_160")][count] = safe_get(form_response, 0).get("dateDeSensibilisation", None)


                            totalHommesMoins35Refugie = safe_get(form_response, 0).get("totalHommesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES - REFUGIES (<=35)", "H", "ind_166_1")][count] = totalHommesMoins35Refugie
                            
                            totalFemmesMoins35Refugie = safe_get(form_response, 0).get("totalFemmesMoins35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES - REFUGIES (<=35)", "F", "ind_166_2")][count] = totalFemmesMoins35Refugie

                            totalMoins35Refugie = (totalHommesMoins35Refugie if totalHommesMoins35Refugie else 0) + (totalFemmesMoins35Refugie if totalFemmesMoins35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES - REFUGIES (<=35)", "T", "ind_166_3")][count] = totalMoins35Refugie

                            totalHommesPlus35Refugie = safe_get(form_response, 0).get("totalHommesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES - REFUGIES", "H", "ind_166_4")][count] = totalHommesPlus35Refugie

                            totalFemmesPlus35Refugie = safe_get(form_response, 0).get("totalFemmesPlus35Refugie", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES - REFUGIES", "F", "ind_166_5")][count] = totalFemmesPlus35Refugie

                            totalPlus35Refugie = (totalHommesPlus35Refugie if totalHommesPlus35Refugie else 0) + (totalFemmesPlus35Refugie if totalFemmesPlus35Refugie else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES - REFUGIES", "T", "ind_166_6")][count] = totalPlus35Refugie

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_166_6_0")][count] = totalPlus35Refugie + totalMoins35Refugie
                            

                            totalHommesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalHommesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_166_7")][count] = totalHommesMoins35DeplaceInterne
                            
                            totalFemmesMoins35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesMoins35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_166_8")][count] = totalFemmesMoins35DeplaceInterne

                            totalMoins35DeplaceInterne = (totalHommesMoins35DeplaceInterne if totalHommesMoins35DeplaceInterne else 0) + (totalFemmesMoins35DeplaceInterne if totalFemmesMoins35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_166_9")][count] = totalMoins35DeplaceInterne

                            totalHommesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalHommesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES - DEPLACES INTERNES", "H", "ind_166_10")][count] = totalHommesPlus35DeplaceInterne

                            totalFemmesPlus35DeplaceInterne = safe_get(form_response, 0).get("totalFemmesPlus35DeplaceInterne", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES - DEPLACES INTERNES", "F", "ind_166_11")][count] = totalFemmesPlus35DeplaceInterne

                            totalPlus35DeplaceInterne = (totalHommesPlus35DeplaceInterne if totalHommesPlus35DeplaceInterne else 0) + (totalFemmesPlus35DeplaceInterne if totalFemmesPlus35DeplaceInterne else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES - DEPLACES INTERNES", "T", "ind_166_12")][count] = totalPlus35DeplaceInterne

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_166_12_0")][count] = totalMoins35DeplaceInterne + totalPlus35DeplaceInterne
                                                                    

                            totalHommesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_166_13")][count] = totalHommesMoins35CommunauteAcceuil
                            
                            totalFemmesMoins35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesMoins35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_166_14")][count] = totalFemmesMoins35CommunauteAcceuil

                            totalMoins35CommunauteAcceuil = (totalHommesMoins35CommunauteAcceuil if totalHommesMoins35CommunauteAcceuil else 0) + (totalFemmesMoins35CommunauteAcceuil if totalFemmesMoins35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_166_15")][count] = totalMoins35CommunauteAcceuil

                            totalHommesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalHommesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_166_16")][count] = totalHommesPlus35CommunauteAcceuil

                            totalFemmesPlus35CommunauteAcceuil = safe_get(form_response, 0).get("totalFemmesPlus35CommunauteAcceuil", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_166_17")][count] = totalFemmesPlus35CommunauteAcceuil

                            totalPlus35CommunauteAcceuil = (totalHommesPlus35CommunauteAcceuil if totalHommesPlus35CommunauteAcceuil else 0) + (totalFemmesPlus35CommunauteAcceuil if totalFemmesPlus35CommunauteAcceuil else 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_166_18")][count] = totalPlus35CommunauteAcceuil

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_166_18_0")][count] = totalMoins35CommunauteAcceuil + totalPlus35CommunauteAcceuil
                            
                            
                            if totalHommesMoins35Refugie or totalHommesMoins35DeplaceInterne or totalHommesMoins35CommunauteAcceuil:
                                totalHommesMoins35 = totalHommesMoins35Refugie + totalHommesMoins35DeplaceInterne + totalHommesMoins35CommunauteAcceuil
                            else:
                                totalHommesMoins35 = safe_get(form_response, 0).get("totalHommesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES (<=35)", "H", "ind_161")][count] = totalHommesMoins35
                            
                            if totalFemmesMoins35Refugie or totalFemmesMoins35DeplaceInterne or totalFemmesMoins35CommunauteAcceuil:
                                totalFemmesMoins35 = totalFemmesMoins35Refugie + totalFemmesMoins35DeplaceInterne + totalFemmesMoins35CommunauteAcceuil
                            else:
                                totalFemmesMoins35 = safe_get(form_response, 0).get("totalFemmesMoins35", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES (<=35)", "F", "ind_162")][count] = totalFemmesMoins35

                            if totalHommesMoins35 or totalFemmesMoins35:
                                totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                            else:
                                totalMoins35 = safe_get(form_response, 0).get("totalMoins35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES (<=35)", "T", "ind_163")][count] = totalMoins35

                            if totalHommesPlus35Refugie or totalHommesPlus35DeplaceInterne or totalHommesPlus35CommunauteAcceuil:
                                totalHommes = totalHommesPlus35Refugie + totalHommesPlus35DeplaceInterne + totalHommesPlus35CommunauteAcceuil
                            else:
                                totalHommes = safe_get(form_response, 0).get("totalHommes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES", "H", "ind_164")][count] = totalHommes

                            if totalFemmesPlus35Refugie or totalFemmesPlus35DeplaceInterne or totalFemmesPlus35CommunauteAcceuil:
                                totalFemmes = totalFemmesPlus35Refugie + totalFemmesPlus35DeplaceInterne + totalFemmesPlus35CommunauteAcceuil
                            else:
                                totalFemmes = safe_get(form_response, 0).get("totalFemmes", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES", "F", "ind_165")][count] = totalFemmes

                            if totalHommes or totalFemmes:
                                totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                            else:
                                totalPlus35 = safe_get(form_response, 0).get("totalPlus35", 0)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "NON JEUNES", "T", "ind_166")][count] = totalPlus35

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "TOTAL PARTICIPANTS", "T", "ind_166_0")][count] = totalPlus35 + totalMoins35
        

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "Nombre total de ménage", "Nombre total de ménage", "ind_167")][count] = safe_get(form_response, 0).get("totalMenages", None)
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "Ethnies minoritaires", "Ethnies minoritaires", "ind_168")][count] = safe_get(form_response, 0).get("nombreEthniques", None)


            #
            for d_k, d_v in datas.items():
                # REFUGIES
                if d_k[4] == "JEUNES - REFUGIES (<=35)" and d_k[5] == "H" and d_v.get(count):
                    if d_v[count] > total_JEUNES_H_REFUGIES:
                        total_JEUNES_H_REFUGIES = d_v[count]
                elif d_k[4] == "JEUNES - REFUGIES (<=35)" and d_k[5] == "F" and d_v.get(count):
                    if d_v[count] > total_JEUNES_F_REFUGIES:
                        total_JEUNES_F_REFUGIES = d_v[count]
                elif d_k[4] == "NON JEUNES - REFUGIES" and d_k[5] == "H" and d_v.get(count):
                    if d_v[count] > total_H_REFUGIES:
                        total_H_REFUGIES = d_v[count]
                elif d_k[4] == "NON JEUNES - REFUGIES" and d_k[5] == "F" and d_v.get(count):
                    if d_v[count] > total_F_REFUGIES:
                        total_F_REFUGIES = d_v[count]
                # End REFUGIES
                
                # DEPLACES INTERNES
                elif d_k[4] == "JEUNES - DEPLACES INTERNES (<=35)" and d_k[5] == "H" and d_v.get(count):
                    if d_v[count] > total_JEUNES_H_DEPLACES_INTERNES:
                        total_JEUNES_H_DEPLACES_INTERNES = d_v[count]
                elif d_k[4] == "JEUNES - DEPLACES INTERNES (<=35)" and d_k[5] == "F" and d_v.get(count):
                    if d_v[count] > total_JEUNES_F_DEPLACES_INTERNES:
                        total_JEUNES_F_DEPLACES_INTERNES = d_v[count]
                elif d_k[4] == "NON JEUNES - DEPLACES INTERNES" and d_k[5] == "H" and d_v.get(count):
                    if d_v[count] > total_H_DEPLACES_INTERNES:
                        total_H_DEPLACES_INTERNES = d_v[count]
                elif d_k[4] == "NON JEUNES - DEPLACES INTERNES" and d_k[5] == "F" and d_v.get(count):
                    if d_v[count] > total_F_DEPLACES_INTERNES:
                        total_F_DEPLACES_INTERNES = d_v[count]
                # End DEPLACES INTERNES
                
                # COMMUNAUTES ACCUEIL
                elif d_k[4] == "JEUNES - COMMUNAUTES ACCUEIL (<=35)" and d_k[5] == "H" and d_v.get(count):
                    if d_v[count] > total_JEUNES_H_COMMUNAUTES_ACCUEIL:
                        total_JEUNES_H_COMMUNAUTES_ACCUEIL = d_v[count]
                elif d_k[4] == "JEUNES - COMMUNAUTES ACCUEIL (<=35)" and d_k[5] == "F" and d_v.get(count):
                    if d_v[count] > total_JEUNES_F_COMMUNAUTES_ACCUEIL:
                        total_JEUNES_F_COMMUNAUTES_ACCUEIL = d_v[count]
                elif d_k[4] == "NON JEUNES - COMMUNAUTES ACCUEIL" and d_k[5] == "H" and d_v.get(count):
                    if d_v[count] > total_H_COMMUNAUTES_ACCUEIL:
                        total_H_COMMUNAUTES_ACCUEIL = d_v[count]
                elif d_k[4] == "NON JEUNES - COMMUNAUTES ACCUEIL" and d_k[5] == "F" and d_v.get(count):
                    if d_v[count] > total_F_COMMUNAUTES_ACCUEIL:
                        total_F_COMMUNAUTES_ACCUEIL = d_v[count]
                # End COMMUNAUTES ACCUEIL

                elif d_k[4] == "NON JEUNES" and d_k[5] == "H" and d_v.get(count):
                    if d_v[count] > total_H:
                        total_H = d_v[count]
                elif d_k[4] == "NON JEUNES" and d_k[5] == "F" and d_v.get(count):
                    if d_v[count] > total_F:
                        total_F = d_v[count]
                elif d_k[4] == "JEUNES (<=35)" and d_k[5] == "H" and d_v.get(count):
                    if d_v[count] > total_JEUNES_H:
                        total_JEUNES_H = d_v[count]
                elif d_k[4] == "JEUNES (<=35)" and d_k[5] == "F" and d_v.get(count):
                    if d_v[count] > total_JEUNES_F:
                        total_JEUNES_F = d_v[count]
                elif d_k[4] == "JEUNES (<=35)" and d_k[5] == "T" and d_v.get(count):
                    if d_v[count] > total_JEUNES:
                        total_JEUNES = d_v[count]
                elif d_k[4] == "Nombre total de ménage" and d_k[5] == "Nombre total de ménage" and d_v.get(count):
                    if d_v[count] > total_MENAGES:
                        total_MENAGES = d_v[count]
                elif d_k[4] == "Ethnies minoritaires" and  d_k[5] == "Ethnies minoritaires" and d_v.get(count):
                    if d_v[count] > total_ETHNIES:
                        total_ETHNIES = d_v[count]


            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES - REFUGIES (<=35)", "H", "ind_174_1")][count] = total_JEUNES_H_REFUGIES
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES - REFUGIES (<=35)", "F", "ind_174_2")][count] = total_JEUNES_F_REFUGIES
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES - REFUGIES (<=35)", "T", "ind_174_3")][count] = total_JEUNES_H_REFUGIES + total_JEUNES_F_REFUGIES
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES - REFUGIES", "H", "ind_174_4")][count] = total_H_REFUGIES
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES - REFUGIES", "F", "ind_174_5")][count] = total_F_REFUGIES
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES - REFUGIES", "T", "ind_174_6")][count] = total_H_REFUGIES + total_F_REFUGIES
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "TOTAL PARTICIPANTS - REFUGIES", "T", "ind_174_6_0")][count] = (
                total_JEUNES_H_REFUGIES + total_JEUNES_F_REFUGIES + total_H_REFUGIES + total_F_REFUGIES
            )

            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES - DEPLACES INTERNES (<=35)", "H", "ind_174_7")][count] = total_JEUNES_H_DEPLACES_INTERNES
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES - DEPLACES INTERNES (<=35)", "F", "ind_174_8")][count] = total_JEUNES_F_DEPLACES_INTERNES
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES - DEPLACES INTERNES (<=35)", "T", "ind_174_9")][count] = total_JEUNES_H_DEPLACES_INTERNES + total_JEUNES_F_DEPLACES_INTERNES
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES - DEPLACES INTERNES", "H", "ind_174_10")][count] = total_H_DEPLACES_INTERNES
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES - DEPLACES INTERNES", "F", "ind_174_11")][count] = total_F_DEPLACES_INTERNES
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES - DEPLACES INTERNES", "T", "ind_174_12")][count] = total_H_DEPLACES_INTERNES + total_F_DEPLACES_INTERNES
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "TOTAL PARTICIPANTS - DEPLACES INTERNES", "T", "ind_174_12_0")][count] = (
                total_JEUNES_H_DEPLACES_INTERNES + total_JEUNES_F_DEPLACES_INTERNES + total_H_DEPLACES_INTERNES + total_F_DEPLACES_INTERNES
            )

            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "H", "ind_174_13")][count] = total_JEUNES_H_COMMUNAUTES_ACCUEIL
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "F", "ind_174_14")][count] = total_JEUNES_F_COMMUNAUTES_ACCUEIL
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES - COMMUNAUTES ACCUEIL (<=35)", "T", "ind_174_15")][count] = total_JEUNES_H_COMMUNAUTES_ACCUEIL + total_JEUNES_F_COMMUNAUTES_ACCUEIL
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES - COMMUNAUTES ACCUEIL", "H", "ind_174_16")][count] = total_H_COMMUNAUTES_ACCUEIL
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES - COMMUNAUTES ACCUEIL", "F", "ind_174_17")][count] = total_F_COMMUNAUTES_ACCUEIL
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES - COMMUNAUTES ACCUEIL", "T", "ind_174_18")][count] = total_H_COMMUNAUTES_ACCUEIL + total_F_COMMUNAUTES_ACCUEIL
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "TOTAL PARTICIPANTS - COMMUNAUTES ACCUEIL", "T", "ind_174_18_0")][count] = (
                total_JEUNES_H_COMMUNAUTES_ACCUEIL + total_JEUNES_F_COMMUNAUTES_ACCUEIL + total_H_COMMUNAUTES_ACCUEIL + total_F_COMMUNAUTES_ACCUEIL
            )



            if total_JEUNES_H_REFUGIES or total_JEUNES_H_DEPLACES_INTERNES or total_JEUNES_H_COMMUNAUTES_ACCUEIL:
                total_JEUNES_H = total_JEUNES_H_REFUGIES + total_JEUNES_H_DEPLACES_INTERNES + total_JEUNES_H_COMMUNAUTES_ACCUEIL
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES (<=35)", "H", "ind_169")][count] = total_JEUNES_H
            
            if total_JEUNES_F_REFUGIES or total_JEUNES_F_DEPLACES_INTERNES or total_JEUNES_F_COMMUNAUTES_ACCUEIL:
                total_JEUNES_F = total_JEUNES_F_REFUGIES + total_JEUNES_F_DEPLACES_INTERNES + total_JEUNES_F_COMMUNAUTES_ACCUEIL
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES (<=35)", "F", "ind_170")][count] = total_JEUNES_F
            
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES (<=35)", "T", "ind_171")][count] = (total_JEUNES_H + total_JEUNES_F) if (total_JEUNES_H + total_JEUNES_F) else total_JEUNES
            
            if total_H_REFUGIES or total_H_DEPLACES_INTERNES or total_H_COMMUNAUTES_ACCUEIL:
                total_H = total_H_REFUGIES + total_H_DEPLACES_INTERNES + total_H_COMMUNAUTES_ACCUEIL
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES", "H", "ind_172")][count] = total_H
            
            if total_F_REFUGIES or total_F_DEPLACES_INTERNES or total_F_COMMUNAUTES_ACCUEIL:
                total_F = total_F_REFUGIES + total_F_DEPLACES_INTERNES + total_F_COMMUNAUTES_ACCUEIL
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES", "F", "ind_173")][count] = total_F
            
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "NON JEUNES", "T", "ind_174")][count] = total_H + total_F
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "TOTAL PARTICIPANTS", "T", "ind_174_0")][count] = (
                total_H + total_F + (total_JEUNES_H + total_JEUNES_F) if (total_JEUNES_H + total_JEUNES_F) else total_JEUNES
            )

            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "Nombre total de ménage", "Nombre total de ménage", "ind_175")][count] = total_MENAGES
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "Ethnies minoritaires", "Ethnies minoritaires", "ind_176")][count] = total_ETHNIES

            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "Observations", "Observations", "Observations", "Observations", "Observations", "ind_177")][count] = ""
            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "DB_NAME", "DB_NAME", "DB_NAME", "DB_NAME", "DB_NAME", "ind_178")][count] = f.no_sql_db_name



            count += 1

                
                
                
                



                
    # All sum
    datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "ID CVD", "ID CVD", "ID CVD", "ID CVD", "ID CVD", "ind_0")][count] = "Total"
    columns_skip = [
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "ID CVD", "ID CVD", "ID CVD", "ID CVD", "ID CVD", "ind_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Unité géographique", "Unité géographique", "Unité géographique", "Unité géographique", "ind_7")
    ]
    for k_data in datas.keys():
        _sum = 0
        if k_data not in columns_skip:
            _sum = sum_dict_value(datas[k_data])
        if _sum:
            datas[k_data][count] = _sum
    # End All sum

    if not os.path.exists("media/"+file_type+"/statistics"):
        os.makedirs("media/"+file_type+"/statistics")

    file_name = "statistics_" + _type.lower() + "_" + (("statistics".lower() + "_") if "statistics" else "")
    df = pd.DataFrame(datas, columns=cols)
    
    #Sort Datas
    # df.sort_values([
    #     ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Région", "Région", "Région", "Région", "ind_1"),
    #     ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Préfecture", "Préfecture", "Préfecture","Préfecture", "ind_2"),
    #     ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Commune", "Commune", "Commune", "Commune", "ind_3"),
    #     ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Canton", "Canton", "Canton", "Canton", "ind_4"),
    #     ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "CVD", "CVD", "CVD", "CVD", "ind_5"),
    #     ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Villages", "Villages", "Villages", "Villages", "ind_6")
    # ])
    #End Sort Datas


    if file_type == "csv":
        file_path = file_type+"/statistics/" + file_name + str(datetime.today().replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_") +".csv"
        df.to_csv("media/"+file_path)
    else:
        file_path = file_type+"/statistics/" + file_name + str(datetime.today().replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_") +".xlsx"
        df.to_excel("media/"+file_path)

    if platform == "win32":
        # windows
        return file_path.replace("/", "\\\\")
    else:
        return file_path
    




def get_value(elt):
    _elt  = elt if not pd.isna(elt) else None
    if type(_elt) in (type_date, datetime, pd.Timestamp):
        return _elt.strftime('%d/%m/%Y')
    elif type(_elt) == float:
        return int(_elt)
    return _elt


def save_csv_datas_in_db(project_couch_id, cycle_couch_id, datas_file: dict) -> str:
    """Function to save the CSV datas in database"""
    nsc = NoSQLClient()
    list_error_found = []
    
    
    if datas_file:
        count = 0
        long = len(list(datas_file.values())[0])
        while count < long:
            


                
            try:
                canton = datas_file["ind_4"][count]
                ad_canton = administrativelevels_models.AdministrativeLevel.objects.using('mis').get(name=canton, type="Canton")
                cvds = administrativelevels_models.CVD.objects.using('mis').filter(name=datas_file["ind_5"][count])
                cvd = None
                for _cvd in cvds:
                    if _cvd.geographical_unit.canton.id == ad_canton.id:
                        cvd = _cvd

                facilitator_db = nsc.get_db(get_value(datas_file["ind_178"][count]))
                if cvd:
                    headquarters_village = cvd.headquarters_village
                    # 20 Etablissement du profil du village
                    try:
                        populationTotaleDuVillage = get_value(datas_file["ind_9"][count])
                    except Exception as exc:
                        populationTotaleDuVillage = None
                    
                    try:
                        totalHouseHolds = get_value(datas_file["ind_10"][count])
                    except Exception as exc:
                        totalHouseHolds = None
                    
                    try:
                        task = facilitator_db.get_query_result(
                            {"type": "task", "administrative_level_id": str(headquarters_village.id), "sql_id": 20, "project_id": project_couch_id, "cycle_id": cycle_couch_id}
                        )[0][0]
                        form_response = task.get("form_response")
                        index, d = get_index_with_datas_dict_by_one_key_name(form_response, "population")
                        if not d.get("population"):
                            d["population"] = {}
                        if populationTotaleDuVillage:
                            d["population"]["populationTotaleDuVillage"] = populationTotaleDuVillage
                        if totalHouseHolds:
                            d["population"]["totalHouseHolds"] = totalHouseHolds
                        form_response[index] = d
                        task["form_response"] = form_response
                        nsc.update_cloudant_document(facilitator_db,  task["_id"], task)
                    except Exception as exc:
                        pass
                    # End 20


                    # 13 Introduction et présentation de l'AC par l'AADB lors de la première réunion cantonale
                    try:
                        dateDeLaReunion = get_value(datas_file["ind_11"][count])
                    except Exception as exc:
                        dateDeLaReunion = None
                    
                    try:
                        totalHommesMoins35 = get_value(datas_file["ind_12"][count])
                    except Exception as exc:
                        totalHommesMoins35 = None
                    
                    try:
                        totalFemmesMoins35 = get_value(datas_file["ind_13"][count])
                    except Exception as exc:
                        totalFemmesMoins35 = None
                    
                    try:
                        totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                        if not totalMoins35:
                            totalMoins35 = get_value(datas_file["ind_14"][count])
                    except Exception as exc:
                        totalMoins35 = None
                    
                    try:
                        totalHommes = get_value(datas_file["ind_15"][count])
                    except Exception as exc:
                        totalHommes = None
                    
                    try:
                        totalFemmes = get_value(datas_file["ind_16"][count])
                    except Exception as exc:
                        totalFemmes = None
                    
                    try:
                        totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                        if not totalPlus35:
                            totalPlus35 = get_value(datas_file["ind_17"][count])
                    except Exception as exc:
                        totalPlus35 = None

                    try:
                        task = facilitator_db.get_query_result(
                            {"type": "task", "administrative_level_id": str(headquarters_village.id), "sql_id": 13, "project_id": project_couch_id, "cycle_id": cycle_couch_id}
                        )[0][0]
                        form_response = task.get("form_response")
                        if not form_response:
                            form_response.append({})
                        if dateDeLaReunion:
                            form_response[0]["dateDeLaReunion"] = dateDeLaReunion
                        if totalHommesMoins35:
                            form_response[0]["totalHommesMoins35"] = totalHommesMoins35
                        if totalFemmesMoins35:
                            form_response[0]["totalFemmesMoins35"] = totalFemmesMoins35
                        if totalMoins35:
                            form_response[0]["totalMoins35"] = totalMoins35
                        if totalHommes:
                            form_response[0]["totalHommes"] = totalHommes
                        if totalFemmes:
                            form_response[0]["totalFemmes"] = totalFemmes
                        if totalPlus35:
                            form_response[0]["totalPlus35"] = totalPlus35

                        task["form_response"] = form_response
                        nsc.update_cloudant_document(facilitator_db,  task["_id"], task)
                    except Exception as exc:
                        pass
                    # End 13


                    # 17 Présentation et clarification de votre mission
                    try:
                        dateDeLaReunion = get_value(datas_file["ind_18"][count])
                    except Exception as exc:
                        dateDeLaReunion = None
                    
                    try:
                        totalHommesMoins35 = get_value(datas_file["ind_19"][count])
                    except Exception as exc:
                        totalHommesMoins35 = None
                    
                    try:
                        totalFemmesMoins35 = get_value(datas_file["ind_20"][count])
                    except Exception as exc:
                        totalFemmesMoins35 = None
                    
                    try:
                        totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                        if not totalMoins35:
                            totalMoins35 = get_value(datas_file["ind_21"][count])
                    except Exception as exc:
                        totalMoins35 = None
                    
                    try:
                        totalHommes = get_value(datas_file["ind_22"][count])
                    except Exception as exc:
                        totalHommes = None
                    
                    try:
                        totalFemmes = get_value(datas_file["ind_23"][count])
                    except Exception as exc:
                        totalFemmes = None
                    
                    try:
                        totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                        if not totalPlus35:
                            totalPlus35 = get_value(datas_file["ind_24"][count])
                    except Exception as exc:
                        totalPlus35 = None

                    try:
                        task = facilitator_db.get_query_result(
                            {"type": "task", "administrative_level_id": str(headquarters_village.id), "sql_id": 17, "project_id": project_couch_id, "cycle_id": cycle_couch_id}
                        )[0][0]
                        form_response = task.get("form_response")
                        
                        index_date, d_date = get_index_with_datas_dict_by_one_key_name(form_response, "dateDeLaReunion")
                        index, d = get_index_with_datas_dict_by_one_key_name(form_response, "totalPersonnes")
                        if not d.get("totalPersonnes"):
                            d["totalPersonnes"] = {}
                        if dateDeLaReunion:
                            form_response[index_date]["dateDeLaReunion"] = dateDeLaReunion
                        if totalHommesMoins35:
                            d["totalPersonnes"]["totalHommesMoins35"] = totalHommesMoins35
                        if totalFemmesMoins35:
                            d["totalPersonnes"]["totalFemmesMoins35"] = totalFemmesMoins35
                        if totalMoins35:
                            d["totalPersonnes"]["totalMoins35"] = totalMoins35
                        if totalHommes:
                            d["totalPersonnes"]["totalHommes"] = totalHommes
                        if totalFemmes:
                            d["totalPersonnes"]["totalFemmes"] = totalFemmes
                        if totalPlus35:
                            d["totalPersonnes"]["totalPlus35"] = totalPlus35

                        form_response[index] = d
                        task["form_response"] = form_response
                        nsc.update_cloudant_document(facilitator_db,  task["_id"], task)
                    except Exception as exc:
                        pass
                    # End 17


                    # 22 Brève introduction de la réunion et de l'ANADEB
                    try:
                        dateDeLaReunion = get_value(datas_file["ind_25"][count])
                    except Exception as exc:
                        dateDeLaReunion = None
                    
                    try:
                        totalHommesMoins35 = get_value(datas_file["ind_26"][count])
                    except Exception as exc:
                        totalHommesMoins35 = None
                    
                    try:
                        totalFemmesMoins35 = get_value(datas_file["ind_27"][count])
                    except Exception as exc:
                        totalFemmesMoins35 = None
                    
                    try:
                        totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                        if not totalMoins35:
                            totalMoins35 = get_value(datas_file["ind_28"][count])
                    except Exception as exc:
                        totalMoins35 = None
                    
                    try:
                        totalHommes = get_value(datas_file["ind_29"][count])
                    except Exception as exc:
                        totalHommes = None
                    
                    try:
                        totalFemmes = get_value(datas_file["ind_30"][count])
                    except Exception as exc:
                        totalFemmes = None
                    
                    try:
                        totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                        if not totalPlus35:
                            totalPlus35 = get_value(datas_file["ind_31"][count])
                    except Exception as exc:
                        totalPlus35 = None

                    try:
                        totalMenages = get_value(datas_file["ind_32"][count])
                    except Exception as exc:
                        totalMenages = None
                    
                    try:
                        nombreEthniques = get_value(datas_file["ind_33"][count])
                    except Exception as exc:
                        nombreEthniques = None

                    try:
                        task = facilitator_db.get_query_result(
                            {"type": "task", "administrative_level_id": str(headquarters_village.id), "sql_id": 22, "project_id": project_couch_id, "cycle_id": cycle_couch_id}
                        )[0][0]
                        form_response = task.get("form_response")
                        if not form_response:
                            form_response.append({})
                        if dateDeLaReunion:
                            form_response[0]["dateDeLaReunion"] = dateDeLaReunion
                        if totalHommesMoins35:
                            form_response[0]["totalHommesMoins35"] = totalHommesMoins35
                        if totalFemmesMoins35:
                            form_response[0]["totalFemmesMoins35"] = totalFemmesMoins35
                        if totalMoins35:
                            form_response[0]["totalMoins35"] = totalMoins35
                        if totalHommes:
                            form_response[0]["totalHommes"] = totalHommes
                        if totalFemmes:
                            form_response[0]["totalFemmes"] = totalFemmes
                        if totalPlus35:
                            form_response[0]["totalPlus35"] = totalPlus35
                        if totalMenages:
                            form_response[0]["totalMenages"] = totalMenages
                        if nombreEthniques:
                            form_response[0]["nombreEthniques"] = nombreEthniques
                        task["form_response"] = form_response
                        nsc.update_cloudant_document(facilitator_db,  task["_id"], task)
                    except Exception as exc:
                        pass
                    # End 22


                    # 27 Ouverture de la deuxième réunion et vérification du quorum des participants
                    try:
                        dateDeLaReunion = get_value(datas_file["ind_34"][count])
                    except Exception as exc:
                        dateDeLaReunion = None
                    
                    try:
                        totalHommesMoins35 = get_value(datas_file["ind_35"][count])
                    except Exception as exc:
                        totalHommesMoins35 = None
                    
                    try:
                        totalFemmesMoins35 = get_value(datas_file["ind_36"][count])
                    except Exception as exc:
                        totalFemmesMoins35 = None
                    
                    try:
                        totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                        if not totalMoins35:
                            totalMoins35 = get_value(datas_file["ind_37"][count])
                    except Exception as exc:
                        totalMoins35 = None
                    
                    try:
                        totalHommes = get_value(datas_file["ind_38"][count])
                    except Exception as exc:
                        totalHommes = None
                    
                    try:
                        totalFemmes = get_value(datas_file["ind_39"][count])
                    except Exception as exc:
                        totalFemmes = None
                    
                    try:
                        totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                        if not totalPlus35:
                            totalPlus35 = get_value(datas_file["ind_40"][count])
                    except Exception as exc:
                        totalPlus35 = None

                    try:
                        totalMenages = get_value(datas_file["ind_41"][count])
                    except Exception as exc:
                        totalMenages = None
                    
                    try:
                        nombreEthniques = get_value(datas_file["ind_42"][count])
                    except Exception as exc:
                        nombreEthniques = None

                    try:
                        task = facilitator_db.get_query_result(
                            {"type": "task", "administrative_level_id": str(headquarters_village.id), "sql_id": 27, "project_id": project_couch_id, "cycle_id": cycle_couch_id}
                        )[0][0]
                        form_response = task.get("form_response")
                        if not form_response:
                            form_response.append({})
                        if dateDeLaReunion:
                            form_response[0]["dateDeLaReunion"] = dateDeLaReunion
                        if totalHommesMoins35:
                            form_response[0]["totalHommesMoins35"] = totalHommesMoins35
                        if totalFemmesMoins35:
                            form_response[0]["totalFemmesMoins35"] = totalFemmesMoins35
                        if totalMoins35:
                            form_response[0]["totalMoins35"] = totalMoins35
                        if totalHommes:
                            form_response[0]["totalHommes"] = totalHommes
                        if totalFemmes:
                            form_response[0]["totalFemmes"] = totalFemmes
                        if totalPlus35:
                            form_response[0]["totalPlus35"] = totalPlus35
                        if totalMenages:
                            form_response[0]["totalMenages"] = totalMenages
                        if nombreEthniques:
                            form_response[0]["nombreEthniques"] = nombreEthniques

                        task["form_response"] = form_response
                        nsc.update_cloudant_document(facilitator_db,  task["_id"], task)
                    except Exception as exc:
                        pass
                    # End 27







                    # 37 Animer la session de formation sur le Module 1 : rôles et responsabilités des membres des organes de CVD
                    try:
                        DateDeLaFormation = get_value(datas_file["ind_43"][count])
                    except Exception as exc:
                        DateDeLaFormation = None
                    
                    try:
                        totalHommesMoins35 = get_value(datas_file["ind_44"][count])
                    except Exception as exc:
                        totalHommesMoins35 = None
                    
                    try:
                        totalFemmesMoins35 = get_value(datas_file["ind_45"][count])
                    except Exception as exc:
                        totalFemmesMoins35 = None
                    
                    try:
                        totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                        if not totalMoins35:
                            totalMoins35 = get_value(datas_file["ind_46"][count])
                    except Exception as exc:
                        totalMoins35 = None
                    
                    try:
                        totalHommes = get_value(datas_file["ind_47"][count])
                    except Exception as exc:
                        totalHommes = None
                    
                    try:
                        totalFemmes = get_value(datas_file["ind_48"][count])
                    except Exception as exc:
                        totalFemmes = None
                    
                    try:
                        totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                        if not totalPlus35:
                            totalPlus35 = get_value(datas_file["ind_49"][count])
                    except Exception as exc:
                        totalPlus35 = None

                    try:
                        totalMenages = get_value(datas_file["ind_50"][count])
                    except Exception as exc:
                        totalMenages = None
                    
                    try:
                        nombreEthniques = get_value(datas_file["ind_51"][count])
                    except Exception as exc:
                        nombreEthniques = None

                    try:
                        task = facilitator_db.get_query_result(
                            {"type": "task", "administrative_level_id": str(headquarters_village.id), "sql_id": 37, "project_id": project_couch_id, "cycle_id": cycle_couch_id}
                        )[0][0]
                        form_response = task.get("form_response")
                        if not form_response:
                            form_response.append({})
                        if DateDeLaFormation:
                            form_response[0]["DateDeLaFormation"] = DateDeLaFormation
                        if totalHommesMoins35:
                            form_response[0]["totalHommesMoins35"] = totalHommesMoins35
                        if totalFemmesMoins35:
                            form_response[0]["totalFemmesMoins35"] = totalFemmesMoins35
                        if totalMoins35:
                            form_response[0]["totalMoins35"] = totalMoins35
                        if totalHommes:
                            form_response[0]["totalHommes"] = totalHommes
                        if totalFemmes:
                            form_response[0]["totalFemmes"] = totalFemmes
                        if totalPlus35:
                            form_response[0]["totalPlus35"] = totalPlus35
                        if totalMenages:
                            form_response[0]["totalMenages"] = totalMenages
                        if nombreEthniques:
                            form_response[0]["nombreEthniques"] = nombreEthniques

                        task["form_response"] = form_response
                        nsc.update_cloudant_document(facilitator_db,  task["_id"], task)
                    except Exception as exc:
                        pass
                    # End 37









                    # 41 Présenter les activités de la journée
                    try:
                        dateDeLaReunion = get_value(datas_file["ind_52"][count])
                    except Exception as exc:
                        dateDeLaReunion = None
                    
                    try:
                        totalHommesMoins35 = get_value(datas_file["ind_53"][count])
                    except Exception as exc:
                        totalHommesMoins35 = None
                    
                    try:
                        totalFemmesMoins35 = get_value(datas_file["ind_54"][count])
                    except Exception as exc:
                        totalFemmesMoins35 = None
                    
                    try:
                        totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                        if not totalMoins35:
                            totalMoins35 = get_value(datas_file["ind_55"][count])
                    except Exception as exc:
                        totalMoins35 = None
                    
                    try:
                        totalHommes = get_value(datas_file["ind_56"][count])
                    except Exception as exc:
                        totalHommes = None
                    
                    try:
                        totalFemmes = get_value(datas_file["ind_57"][count])
                    except Exception as exc:
                        totalFemmes = None
                    
                    try:
                        totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                        if not totalPlus35:
                            totalPlus35 = get_value(datas_file["ind_58"][count])
                    except Exception as exc:
                        totalPlus35 = None

                    try:
                        totalMenages = get_value(datas_file["ind_59"][count])
                    except Exception as exc:
                        totalMenages = None
                    
                    try:
                        nombreEthniques = get_value(datas_file["ind_60"][count])
                    except Exception as exc:
                        nombreEthniques = None

                    try:
                        task = facilitator_db.get_query_result(
                            {"type": "task", "administrative_level_id": str(headquarters_village.id), "sql_id": 41, "project_id": project_couch_id, "cycle_id": cycle_couch_id}
                        )[0][0]
                        form_response = task.get("form_response")
                        if not form_response:
                            form_response.append({})
                        if dateDeLaReunion:
                            form_response[0]["dateDeLaReunion"] = dateDeLaReunion
                        if totalHommesMoins35:
                            form_response[0]["totalHommesMoins35"] = totalHommesMoins35
                        if totalFemmesMoins35:
                            form_response[0]["totalFemmesMoins35"] = totalFemmesMoins35
                        if totalMoins35:
                            form_response[0]["totalMoins35"] = totalMoins35
                        if totalHommes:
                            form_response[0]["totalHommes"] = totalHommes
                        if totalFemmes:
                            form_response[0]["totalFemmes"] = totalFemmes
                        if totalPlus35:
                            form_response[0]["totalPlus35"] = totalPlus35
                        if totalMenages:
                            form_response[0]["totalMenages"] = totalMenages
                        if nombreEthniques:
                            form_response[0]["nombreEthniques"] = nombreEthniques

                        task["form_response"] = form_response
                        nsc.update_cloudant_document(facilitator_db,  task["_id"], task)
                    except Exception as exc:
                        pass
                    # End 41


                    # 45 Elaboration du plan d'action villageois (PAV)
                    try:
                        dateDeLaReunion = get_value(datas_file["ind_61"][count])
                    except Exception as exc:
                        dateDeLaReunion = None
                    
                    try:
                        totalHommesMoins35 = get_value(datas_file["ind_62"][count])
                    except Exception as exc:
                        totalHommesMoins35 = None
                    
                    try:
                        totalFemmesMoins35 = get_value(datas_file["ind_63"][count])
                    except Exception as exc:
                        totalFemmesMoins35 = None
                    
                    try:
                        totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                        if not totalMoins35:
                            totalMoins35 = get_value(datas_file["ind_64"][count])
                    except Exception as exc:
                        totalMoins35 = None
                    
                    try:
                        totalHommes = get_value(datas_file["ind_65"][count])
                    except Exception as exc:
                        totalHommes = None
                    
                    try:
                        totalFemmes = get_value(datas_file["ind_66"][count])
                    except Exception as exc:
                        totalFemmes = None
                    
                    try:
                        totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                        if not totalPlus35:
                            totalPlus35 = get_value(datas_file["ind_67"][count])
                    except Exception as exc:
                        totalPlus35 = None

                    try:
                        totalMenages = get_value(datas_file["ind_68"][count])
                    except Exception as exc:
                        totalMenages = None
                    
                    try:
                        nombreEthniques = get_value(datas_file["ind_69"][count])
                    except Exception as exc:
                        nombreEthniques = None

                    try:
                        task = facilitator_db.get_query_result(
                            {"type": "task", "administrative_level_id": str(headquarters_village.id), "sql_id": 45, "project_id": project_couch_id, "cycle_id": cycle_couch_id}
                        )[0][0]
                        form_response = task.get("form_response")
                        if not form_response:
                            form_response.append({})
                        if dateDeLaReunion:
                            form_response[0]["dateDeLaReunion"] = dateDeLaReunion
                        if totalHommesMoins35:
                            form_response[0]["totalHommesMoins35"] = totalHommesMoins35
                        if totalFemmesMoins35:
                            form_response[0]["totalFemmesMoins35"] = totalFemmesMoins35
                        if totalMoins35:
                            form_response[0]["totalMoins35"] = totalMoins35
                        if totalHommes:
                            form_response[0]["totalHommes"] = totalHommes
                        if totalFemmes:
                            form_response[0]["totalFemmes"] = totalFemmes
                        if totalPlus35:
                            form_response[0]["totalPlus35"] = totalPlus35
                        if totalMenages:
                            form_response[0]["totalMenages"] = totalMenages
                        if nombreEthniques:
                            form_response[0]["nombreEthniques"] = nombreEthniques

                        task["form_response"] = form_response
                        nsc.update_cloudant_document(facilitator_db,  task["_id"], task)
                    except Exception as exc:
                        pass
                    # End 45


                    # 46 Mise en place et/ou restructuration du comité cantonal de développement (CCD)  et du comité cantonal de gestion des plaintes (CCGP)
                    try:
                        dateDeLaReunion = get_value(datas_file["ind_70"][count])
                    except Exception as exc:
                        dateDeLaReunion = None
                    
                    try:
                        totalHommesMoins35 = get_value(datas_file["ind_71"][count])
                    except Exception as exc:
                        totalHommesMoins35 = None
                    
                    try:
                        totalFemmesMoins35 = get_value(datas_file["ind_72"][count])
                    except Exception as exc:
                        totalFemmesMoins35 = None
                    
                    try:
                        totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                        if not totalMoins35:
                            totalMoins35 = get_value(datas_file["ind_73"][count])
                    except Exception as exc:
                        totalMoins35 = None
                    
                    try:
                        totalHommes = get_value(datas_file["ind_74"][count])
                    except Exception as exc:
                        totalHommes = None
                    
                    try:
                        totalFemmes = get_value(datas_file["ind_75"][count])
                    except Exception as exc:
                        totalFemmes = None
                    
                    try:
                        totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                        if not totalPlus35:
                            totalPlus35 = get_value(datas_file["ind_76"][count])
                    except Exception as exc:
                        totalPlus35 = None

                    try:
                        totalMenages = get_value(datas_file["ind_77"][count])
                    except Exception as exc:
                        totalMenages = None
                    
                    try:
                        nombreEthniques = get_value(datas_file["ind_78"][count])
                    except Exception as exc:
                        nombreEthniques = None

                    try:
                        task = facilitator_db.get_query_result(
                            {"type": "task", "administrative_level_id": str(headquarters_village.id), "sql_id": 46, "project_id": project_couch_id, "cycle_id": cycle_couch_id}
                        )[0][0]
                        form_response = task.get("form_response")
                        if not form_response:
                            form_response.append({})
                        if dateDeLaReunion:
                            form_response[0]["dateDeLaReunion"] = dateDeLaReunion
                        if totalHommesMoins35:
                            form_response[0]["totalHommesMoins35"] = totalHommesMoins35
                        if totalFemmesMoins35:
                            form_response[0]["totalFemmesMoins35"] = totalFemmesMoins35
                        if totalMoins35:
                            form_response[0]["totalMoins35"] = totalMoins35
                        if totalHommes:
                            form_response[0]["totalHommes"] = totalHommes
                        if totalFemmes:
                            form_response[0]["totalFemmes"] = totalFemmes
                        if totalPlus35:
                            form_response[0]["totalPlus35"] = totalPlus35
                        if totalMenages:
                            form_response[0]["totalMenages"] = totalMenages
                        if nombreEthniques:
                            form_response[0]["nombreEthniques"] = nombreEthniques

                        task["form_response"] = form_response
                        nsc.update_cloudant_document(facilitator_db,  task["_id"], task)
                    except Exception as exc:
                        pass
                    # End 46













                    # 47 Appui au CCD dans  l'analyse des PAV des villages, l'arbitrage, la sélection des sous - projets à financer et l'affection des ressources par sous - projet
                    try:
                        dateDeLaReunion = get_value(datas_file["ind_79"][count])
                    except Exception as exc:
                        dateDeLaReunion = None
                    
                    try:
                        totalHommesMoins35 = get_value(datas_file["ind_80"][count])
                    except Exception as exc:
                        totalHommesMoins35 = None
                    
                    try:
                        totalFemmesMoins35 = get_value(datas_file["ind_81"][count])
                    except Exception as exc:
                        totalFemmesMoins35 = None
                    
                    try:
                        totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                        if not totalMoins35:
                            totalMoins35 = get_value(datas_file["ind_82"][count])
                    except Exception as exc:
                        totalMoins35 = None
                    
                    try:
                        totalHommes = get_value(datas_file["ind_83"][count])
                    except Exception as exc:
                        totalHommes = None
                    
                    try:
                        totalFemmes = get_value(datas_file["ind_84"][count])
                    except Exception as exc:
                        totalFemmes = None
                    
                    try:
                        totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                        if not totalPlus35:
                            totalPlus35 = get_value(datas_file["ind_85"][count])
                    except Exception as exc:
                        totalPlus35 = None

                    try:
                        totalMenages = get_value(datas_file["ind_86"][count])
                    except Exception as exc:
                        totalMenages = None
                    
                    try:
                        nombreEthniques = get_value(datas_file["ind_87"][count])
                    except Exception as exc:
                        nombreEthniques = None

                    try:
                        task = facilitator_db.get_query_result(
                            {"type": "task", "administrative_level_id": str(headquarters_village.id), "sql_id": 47, "project_id": project_couch_id, "cycle_id": cycle_couch_id}
                        )[0][0]
                        form_response = task.get("form_response")
                        if not form_response:
                            form_response.append({})
                        if dateDeLaReunion:
                            form_response[0]["dateDeLaReunion"] = dateDeLaReunion
                        if totalHommesMoins35:
                            form_response[0]["totalHommesMoins35"] = totalHommesMoins35
                        if totalFemmesMoins35:
                            form_response[0]["totalFemmesMoins35"] = totalFemmesMoins35
                        if totalMoins35:
                            form_response[0]["totalMoins35"] = totalMoins35
                        if totalHommes:
                            form_response[0]["totalHommes"] = totalHommes
                        if totalFemmes:
                            form_response[0]["totalFemmes"] = totalFemmes
                        if totalPlus35:
                            form_response[0]["totalPlus35"] = totalPlus35
                        if totalMenages:
                            form_response[0]["totalMenages"] = totalMenages
                        if nombreEthniques:
                            form_response[0]["nombreEthniques"] = nombreEthniques

                        task["form_response"] = form_response
                        nsc.update_cloudant_document(facilitator_db,  task["_id"], task)
                    except Exception as exc:
                        pass
                    # End 47


                    # 48 Appui à l'organisation et à la facilitation de rencontre  communautaire de restitution des résultats de la reunion cantonale d'arbitrage
                    try:
                        dateDeLaReunion = get_value(datas_file["ind_88"][count])
                    except Exception as exc:
                        dateDeLaReunion = None
                    
                    try:
                        totalHommesMoins35 = get_value(datas_file["ind_89"][count])
                    except Exception as exc:
                        totalHommesMoins35 = None
                    
                    try:
                        totalFemmesMoins35 = get_value(datas_file["ind_90"][count])
                    except Exception as exc:
                        totalFemmesMoins35 = None
                    
                    try:
                        totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                        if not totalMoins35:
                            totalMoins35 = get_value(datas_file["ind_91"][count])
                    except Exception as exc:
                        totalMoins35 = None
                    
                    try:
                        totalHommes = get_value(datas_file["ind_92"][count])
                    except Exception as exc:
                        totalHommes = None
                    
                    try:
                        totalFemmes = get_value(datas_file["ind_93"][count])
                    except Exception as exc:
                        totalFemmes = None
                    
                    try:
                        totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                        if not totalPlus35:
                            totalPlus35 = get_value(datas_file["ind_94"][count])
                    except Exception as exc:
                        totalPlus35 = None

                    try:
                        totalMenages = get_value(datas_file["ind_95"][count])
                    except Exception as exc:
                        totalMenages = None
                    
                    try:
                        nombreEthniques = get_value(datas_file["ind_96"][count])
                    except Exception as exc:
                        nombreEthniques = None

                    try:
                        task = facilitator_db.get_query_result(
                            {"type": "task", "administrative_level_id": str(headquarters_village.id), "sql_id": 48, "project_id": project_couch_id, "cycle_id": cycle_couch_id}
                        )[0][0]
                        form_response = task.get("form_response")
                        if not form_response:
                            form_response.append({})
                        if dateDeLaReunion:
                            form_response[0]["dateDeLaReunion"] = dateDeLaReunion
                        if totalHommesMoins35:
                            form_response[0]["totalHommesMoins35"] = totalHommesMoins35
                        if totalFemmesMoins35:
                            form_response[0]["totalFemmesMoins35"] = totalFemmesMoins35
                        if totalMoins35:
                            form_response[0]["totalMoins35"] = totalMoins35
                        if totalHommes:
                            form_response[0]["totalHommes"] = totalHommes
                        if totalFemmes:
                            form_response[0]["totalFemmes"] = totalFemmes
                        if totalPlus35:
                            form_response[0]["totalPlus35"] = totalPlus35
                        if totalMenages:
                            form_response[0]["totalMenages"] = totalMenages
                        if nombreEthniques:
                            form_response[0]["nombreEthniques"] = nombreEthniques

                        task["form_response"] = form_response
                        nsc.update_cloudant_document(facilitator_db,  task["_id"], task)
                    except Exception as exc:
                        pass
                    # End 48



                    # 49 Appuie au bureau du CVD  dans la rédaction du document du sous projet et la demande de financement
                    try:
                        dateDeSeance = get_value(datas_file["ind_97"][count])
                    except Exception as exc:
                        dateDeSeance = None
                    
                    try:
                        totalHommesMoins35 = get_value(datas_file["ind_98"][count])
                    except Exception as exc:
                        totalHommesMoins35 = None
                    
                    try:
                        totalFemmesMoins35 = get_value(datas_file["ind_99"][count])
                    except Exception as exc:
                        totalFemmesMoins35 = None
                    
                    try:
                        totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                        if not totalMoins35:
                            totalMoins35 = get_value(datas_file["ind_100"][count])
                    except Exception as exc:
                        totalMoins35 = None
                    
                    try:
                        totalHommes = get_value(datas_file["ind_101"][count])
                    except Exception as exc:
                        totalHommes = None
                    
                    try:
                        totalFemmes = get_value(datas_file["ind_102"][count])
                    except Exception as exc:
                        totalFemmes = None
                    
                    try:
                        totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                        if not totalPlus35:
                            totalPlus35 = get_value(datas_file["ind_103"][count])
                    except Exception as exc:
                        totalPlus35 = None

                    try:
                        totalMenages = get_value(datas_file["ind_104"][count])
                    except Exception as exc:
                        totalMenages = None
                    
                    try:
                        nombreEthniques = get_value(datas_file["ind_105"][count])
                    except Exception as exc:
                        nombreEthniques = None

                    try:
                        task = facilitator_db.get_query_result(
                            {"type": "task", "administrative_level_id": str(headquarters_village.id), "sql_id": 49, "project_id": project_couch_id, "cycle_id": cycle_couch_id}
                        )[0][0]
                        form_response = task.get("form_response")
                        if not form_response:
                            form_response.append({})
                        if dateDeSeance:
                            form_response[0]["dateDeSeance"] = dateDeSeance
                        if totalHommesMoins35:
                            form_response[0]["totalHommesMoins35"] = totalHommesMoins35
                        if totalFemmesMoins35:
                            form_response[0]["totalFemmesMoins35"] = totalFemmesMoins35
                        if totalMoins35:
                            form_response[0]["totalMoins35"] = totalMoins35
                        if totalHommes:
                            form_response[0]["totalHommes"] = totalHommes
                        if totalFemmes:
                            form_response[0]["totalFemmes"] = totalFemmes
                        if totalPlus35:
                            form_response[0]["totalPlus35"] = totalPlus35
                        if totalMenages:
                            form_response[0]["totalMenages"] = totalMenages
                        if nombreEthniques:
                            form_response[0]["nombreEthniques"] = nombreEthniques

                        task["form_response"] = form_response
                        nsc.update_cloudant_document(facilitator_db,  task["_id"], task)
                    except Exception as exc:
                        pass
                    # End 49


                    # 50 Réunion d'information de la communauté sur le sous projet: activités, coût estimatif et prochainbes étapes
                    try:
                        dateDeLaReunion = get_value(datas_file["ind_106"][count])
                    except Exception as exc:
                        dateDeLaReunion = None
                    
                    try:
                        totalHommesMoins35 = get_value(datas_file["ind_107"][count])
                    except Exception as exc:
                        totalHommesMoins35 = None
                    
                    try:
                        totalFemmesMoins35 = get_value(datas_file["ind_108"][count])
                    except Exception as exc:
                        totalFemmesMoins35 = None
                    
                    try:
                        totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                        if not totalMoins35:
                            totalMoins35 = get_value(datas_file["ind_109"][count])
                    except Exception as exc:
                        totalMoins35 = None
                    
                    try:
                        totalHommes = get_value(datas_file["ind_110"][count])
                    except Exception as exc:
                        totalHommes = None
                    
                    try:
                        totalFemmes = get_value(datas_file["ind_111"][count])
                    except Exception as exc:
                        totalFemmes = None
                    
                    try:
                        totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                        if not totalPlus35:
                            totalPlus35 = get_value(datas_file["ind_112"][count])
                    except Exception as exc:
                        totalPlus35 = None

                    try:
                        totalMenages = get_value(datas_file["ind_113"][count])
                    except Exception as exc:
                        totalMenages = None
                    
                    try:
                        nombreEthniques = get_value(datas_file["ind_114"][count])
                    except Exception as exc:
                        nombreEthniques = None

                    try:
                        task = facilitator_db.get_query_result(
                            {"type": "task", "administrative_level_id": str(headquarters_village.id), "sql_id": 50, "project_id": project_couch_id, "cycle_id": cycle_couch_id}
                        )[0][0]
                        form_response = task.get("form_response")
                        if not form_response:
                            form_response.append({})
                        if dateDeLaReunion:
                            form_response[0]["dateDeLaReunion"] = dateDeLaReunion
                        if totalHommesMoins35:
                            form_response[0]["totalHommesMoins35"] = totalHommesMoins35
                        if totalFemmesMoins35:
                            form_response[0]["totalFemmesMoins35"] = totalFemmesMoins35
                        if totalMoins35:
                            form_response[0]["totalMoins35"] = totalMoins35
                        if totalHommes:
                            form_response[0]["totalHommes"] = totalHommes
                        if totalFemmes:
                            form_response[0]["totalFemmes"] = totalFemmes
                        if totalPlus35:
                            form_response[0]["totalPlus35"] = totalPlus35
                        if totalMenages:
                            form_response[0]["totalMenages"] = totalMenages
                        if nombreEthniques:
                            form_response[0]["nombreEthniques"] = nombreEthniques

                        task["form_response"] = form_response
                        nsc.update_cloudant_document(facilitator_db,  task["_id"], task)
                    except Exception as exc:
                        pass
                    # End 50




                    # 51 Soumission de la demande de financement du sous-projet à l’ANADEB pour approbation par le CORA
                    try:
                        dateDeSoumission = get_value(datas_file["ind_115"][count])
                    except Exception as exc:
                        dateDeSoumission = None
                    
                    try:
                        totalHommesMoins35 = get_value(datas_file["ind_116"][count])
                    except Exception as exc:
                        totalHommesMoins35 = None
                    
                    try:
                        totalFemmesMoins35 = get_value(datas_file["ind_117"][count])
                    except Exception as exc:
                        totalFemmesMoins35 = None
                    
                    try:
                        totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                        if not totalMoins35:
                            totalMoins35 = get_value(datas_file["ind_118"][count])
                    except Exception as exc:
                        totalMoins35 = None
                    
                    try:
                        totalHommes = get_value(datas_file["ind_119"][count])
                    except Exception as exc:
                        totalHommes = None
                    
                    try:
                        totalFemmes = get_value(datas_file["ind_120"][count])
                    except Exception as exc:
                        totalFemmes = None
                    
                    try:
                        totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                        if not totalPlus35:
                            totalPlus35 = get_value(datas_file["ind_121"][count])
                    except Exception as exc:
                        totalPlus35 = None

                    try:
                        totalMenages = get_value(datas_file["ind_122"][count])
                    except Exception as exc:
                        totalMenages = None
                    
                    try:
                        nombreEthniques = get_value(datas_file["ind_123"][count])
                    except Exception as exc:
                        nombreEthniques = None

                    try:
                        task = facilitator_db.get_query_result(
                            {"type": "task", "administrative_level_id": str(headquarters_village.id), "sql_id": 51, "project_id": project_couch_id, "cycle_id": cycle_couch_id}
                        )[0][0]
                        form_response = task.get("form_response")
                        if not form_response:
                            form_response.append({})
                        if dateDeSoumission:
                            form_response[0]["dateDeSoumission"] = dateDeSoumission
                        if totalHommesMoins35:
                            form_response[0]["totalHommesMoins35"] = totalHommesMoins35
                        if totalFemmesMoins35:
                            form_response[0]["totalFemmesMoins35"] = totalFemmesMoins35
                        if totalMoins35:
                            form_response[0]["totalMoins35"] = totalMoins35
                        if totalHommes:
                            form_response[0]["totalHommes"] = totalHommes
                        if totalFemmes:
                            form_response[0]["totalFemmes"] = totalFemmes
                        if totalPlus35:
                            form_response[0]["totalPlus35"] = totalPlus35
                        if totalMenages:
                            form_response[0]["totalMenages"] = totalMenages
                        if nombreEthniques:
                            form_response[0]["nombreEthniques"] = nombreEthniques

                        task["form_response"] = form_response
                        nsc.update_cloudant_document(facilitator_db,  task["_id"], task)
                    except Exception as exc:
                        pass
                    # End 51


                    # 52 Séance communautaire d'information sur les grandes lignes  du sous projet, sa durée d'exécution et les mesures de sauvegardes à observer
                    try:
                        dateDeSeance = get_value(datas_file["ind_124"][count])
                    except Exception as exc:
                        dateDeSeance = None
                    
                    try:
                        totalHommesMoins35 = get_value(datas_file["ind_125"][count])
                    except Exception as exc:
                        totalHommesMoins35 = None
                    
                    try:
                        totalFemmesMoins35 = get_value(datas_file["ind_126"][count])
                    except Exception as exc:
                        totalFemmesMoins35 = None
                    
                    try:
                        totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                        if not totalMoins35:
                            totalMoins35 = get_value(datas_file["ind_127"][count])
                    except Exception as exc:
                        totalMoins35 = None
                    
                    try:
                        totalHommes = get_value(datas_file["ind_128"][count])
                    except Exception as exc:
                        totalHommes = None
                    
                    try:
                        totalFemmes = get_value(datas_file["ind_129"][count])
                    except Exception as exc:
                        totalFemmes = None
                    
                    try:
                        totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                        if not totalPlus35:
                            totalPlus35 = get_value(datas_file["ind_130"][count])
                    except Exception as exc:
                        totalPlus35 = None

                    try:
                        totalMenages = get_value(datas_file["ind_131"][count])
                    except Exception as exc:
                        totalMenages = None
                    
                    try:
                        nombreEthniques = get_value(datas_file["ind_132"][count])
                    except Exception as exc:
                        nombreEthniques = None

                    try:
                        task = facilitator_db.get_query_result(
                            {"type": "task", "administrative_level_id": str(headquarters_village.id), "sql_id": 52, "project_id": project_couch_id, "cycle_id": cycle_couch_id}
                        )[0][0]
                        form_response = task.get("form_response")
                        if not form_response:
                            form_response.append({})
                        if dateDeSeance:
                            form_response[0]["dateDeSeance"] = dateDeSeance
                        if totalHommesMoins35:
                            form_response[0]["totalHommesMoins35"] = totalHommesMoins35
                        if totalFemmesMoins35:
                            form_response[0]["totalFemmesMoins35"] = totalFemmesMoins35
                        if totalMoins35:
                            form_response[0]["totalMoins35"] = totalMoins35
                        if totalHommes:
                            form_response[0]["totalHommes"] = totalHommes
                        if totalFemmes:
                            form_response[0]["totalFemmes"] = totalFemmes
                        if totalPlus35:
                            form_response[0]["totalPlus35"] = totalPlus35
                        if totalMenages:
                            form_response[0]["totalMenages"] = totalMenages
                        if nombreEthniques:
                            form_response[0]["nombreEthniques"] = nombreEthniques

                        task["form_response"] = form_response
                        nsc.update_cloudant_document(facilitator_db,  task["_id"], task)
                    except Exception as exc:
                        pass
                    # End 52


                    # 53 Appuie au CVD dans la production des rapports périodiques et l'organisation des réunions d'échanges sur l'état d'avancement des travaux
                    try:
                        dateDeLaReunion = get_value(datas_file["ind_133"][count])
                    except Exception as exc:
                        dateDeLaReunion = None
                    
                    try:
                        totalHommesMoins35 = get_value(datas_file["ind_134"][count])
                    except Exception as exc:
                        totalHommesMoins35 = None
                    
                    try:
                        totalFemmesMoins35 = get_value(datas_file["ind_135"][count])
                    except Exception as exc:
                        totalFemmesMoins35 = None
                    
                    try:
                        totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                        if not totalMoins35:
                            totalMoins35 = get_value(datas_file["ind_136"][count])
                    except Exception as exc:
                        totalMoins35 = None
                    
                    try:
                        totalHommes = get_value(datas_file["ind_137"][count])
                    except Exception as exc:
                        totalHommes = None
                    
                    try:
                        totalFemmes = get_value(datas_file["ind_138"][count])
                    except Exception as exc:
                        totalFemmes = None
                    
                    try:
                        totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                        if not totalPlus35:
                            totalPlus35 = get_value(datas_file["ind_139"][count])
                    except Exception as exc:
                        totalPlus35 = None

                    try:
                        totalMenages = get_value(datas_file["ind_140"][count])
                    except Exception as exc:
                        totalMenages = None
                    
                    try:
                        nombreEthniques = get_value(datas_file["ind_141"][count])
                    except Exception as exc:
                        nombreEthniques = None

                    try:
                        task = facilitator_db.get_query_result(
                            {"type": "task", "administrative_level_id": str(headquarters_village.id), "sql_id": 53, "project_id": project_couch_id, "cycle_id": cycle_couch_id}
                        )[0][0]
                        form_response = task.get("form_response")
                        if not form_response:
                            form_response.append({})
                        if dateDeLaReunion:
                            form_response[0]["dateDeLaReunion"] = dateDeLaReunion
                        if totalHommesMoins35:
                            form_response[0]["totalHommesMoins35"] = totalHommesMoins35
                        if totalFemmesMoins35:
                            form_response[0]["totalFemmesMoins35"] = totalFemmesMoins35
                        if totalMoins35:
                            form_response[0]["totalMoins35"] = totalMoins35
                        if totalHommes:
                            form_response[0]["totalHommes"] = totalHommes
                        if totalFemmes:
                            form_response[0]["totalFemmes"] = totalFemmes
                        if totalPlus35:
                            form_response[0]["totalPlus35"] = totalPlus35
                        if totalMenages:
                            form_response[0]["totalMenages"] = totalMenages
                        if nombreEthniques:
                            form_response[0]["nombreEthniques"] = nombreEthniques

                        task["form_response"] = form_response
                        nsc.update_cloudant_document(facilitator_db,  task["_id"], task)
                    except Exception as exc:
                        pass
                    # End 53


                    # 54 Classement et archivage de tous les documents relatifs à la mise en œuvre du sous projet
                    try:
                        dateDeSeance = get_value(datas_file["ind_142"][count])
                    except Exception as exc:
                        dateDeSeance = None
                    
                    try:
                        totalHommesMoins35 = get_value(datas_file["ind_143"][count])
                    except Exception as exc:
                        totalHommesMoins35 = None
                    
                    try:
                        totalFemmesMoins35 = get_value(datas_file["ind_144"][count])
                    except Exception as exc:
                        totalFemmesMoins35 = None
                    
                    try:
                        totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                        if not totalMoins35:
                            totalMoins35 = get_value(datas_file["ind_145"][count])
                    except Exception as exc:
                        totalMoins35 = None
                    
                    try:
                        totalHommes = get_value(datas_file["ind_146"][count])
                    except Exception as exc:
                        totalHommes = None
                    
                    try:
                        totalFemmes = get_value(datas_file["ind_147"][count])
                    except Exception as exc:
                        totalFemmes = None
                    
                    try:
                        totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                        if not totalPlus35:
                            totalPlus35 = get_value(datas_file["ind_148"][count])
                    except Exception as exc:
                        totalPlus35 = None

                    try:
                        totalMenages = get_value(datas_file["ind_149"][count])
                    except Exception as exc:
                        totalMenages = None
                    
                    try:
                        nombreEthniques = get_value(datas_file["ind_150"][count])
                    except Exception as exc:
                        nombreEthniques = None

                    try:
                        task = facilitator_db.get_query_result(
                            {"type": "task", "administrative_level_id": str(headquarters_village.id), "sql_id": 54, "project_id": project_couch_id, "cycle_id": cycle_couch_id}
                        )[0][0]
                        form_response = task.get("form_response")
                        if not form_response:
                            form_response.append({})
                        if dateDeSeance:
                            form_response[0]["dateDeSeance"] = dateDeSeance
                        if totalHommesMoins35:
                            form_response[0]["totalHommesMoins35"] = totalHommesMoins35
                        if totalFemmesMoins35:
                            form_response[0]["totalFemmesMoins35"] = totalFemmesMoins35
                        if totalMoins35:
                            form_response[0]["totalMoins35"] = totalMoins35
                        if totalHommes:
                            form_response[0]["totalHommes"] = totalHommes
                        if totalFemmes:
                            form_response[0]["totalFemmes"] = totalFemmes
                        if totalPlus35:
                            form_response[0]["totalPlus35"] = totalPlus35
                        if totalMenages:
                            form_response[0]["totalMenages"] = totalMenages
                        if nombreEthniques:
                            form_response[0]["nombreEthniques"] = nombreEthniques

                        task["form_response"] = form_response
                        nsc.update_cloudant_document(facilitator_db,  task["_id"], task)
                    except Exception as exc:
                        pass
                    # End 54


                    # 55 Réalisation de l'auto évaluation participative de la mise en œuvre du sous projet
                    try:
                        dateDeSeance = get_value(datas_file["ind_151"][count])
                    except Exception as exc:
                        dateDeSeance = None
                    
                    try:
                        totalHommesMoins35 = get_value(datas_file["ind_152"][count])
                    except Exception as exc:
                        totalHommesMoins35 = None
                    
                    try:
                        totalFemmesMoins35 = get_value(datas_file["ind_153"][count])
                    except Exception as exc:
                        totalFemmesMoins35 = None
                    
                    try:
                        totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                        if not totalMoins35:
                            totalMoins35 = get_value(datas_file["ind_154"][count])
                    except Exception as exc:
                        totalMoins35 = None
                    
                    try:
                        totalHommes = get_value(datas_file["ind_155"][count])
                    except Exception as exc:
                        totalHommes = None
                    
                    try:
                        totalFemmes = get_value(datas_file["ind_156"][count])
                    except Exception as exc:
                        totalFemmes = None
                    
                    try:
                        totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                        if not totalPlus35:
                            totalPlus35 = get_value(datas_file["ind_157"][count])
                    except Exception as exc:
                        totalPlus35 = None

                    try:
                        totalMenages = get_value(datas_file["ind_158"][count])
                    except Exception as exc:
                        totalMenages = None
                    
                    try:
                        nombreEthniques = get_value(datas_file["ind_159"][count])
                    except Exception as exc:
                        nombreEthniques = None

                    try:
                        task = facilitator_db.get_query_result(
                            {"type": "task", "administrative_level_id": str(headquarters_village.id), "sql_id": 55, "project_id": project_couch_id, "cycle_id": cycle_couch_id}
                        )[0][0]
                        form_response = task.get("form_response")
                        if not form_response:
                            form_response.append({})
                        if dateDeSeance:
                            form_response[0]["dateDeSeance"] = dateDeSeance
                        if totalHommesMoins35:
                            form_response[0]["totalHommesMoins35"] = totalHommesMoins35
                        if totalFemmesMoins35:
                            form_response[0]["totalFemmesMoins35"] = totalFemmesMoins35
                        if totalMoins35:
                            form_response[0]["totalMoins35"] = totalMoins35
                        if totalHommes:
                            form_response[0]["totalHommes"] = totalHommes
                        if totalFemmes:
                            form_response[0]["totalFemmes"] = totalFemmes
                        if totalPlus35:
                            form_response[0]["totalPlus35"] = totalPlus35
                        if totalMenages:
                            form_response[0]["totalMenages"] = totalMenages
                        if nombreEthniques:
                            form_response[0]["nombreEthniques"] = nombreEthniques

                        task["form_response"] = form_response
                        nsc.update_cloudant_document(facilitator_db,  task["_id"], task)
                    except Exception as exc:
                        pass
                    # End 55


                    # 56 Elaboration et mise en oeuvre du plan d'entretien et de maintenance de l'ouvrage
                    try:
                        dateDeSensibilisation = get_value(datas_file["ind_160"][count])
                    except Exception as exc:
                        dateDeSensibilisation = None
                    
                    try:
                        totalHommesMoins35 = get_value(datas_file["ind_161"][count])
                    except Exception as exc:
                        totalHommesMoins35 = None
                    
                    try:
                        totalFemmesMoins35 = get_value(datas_file["ind_162"][count])
                    except Exception as exc:
                        totalFemmesMoins35 = None
                    
                    try:
                        totalMoins35 = (totalHommesMoins35 if totalHommesMoins35 else 0) + (totalFemmesMoins35 if totalFemmesMoins35 else 0)
                        if not totalMoins35:
                            totalMoins35 = get_value(datas_file["ind_163"][count])
                    except Exception as exc:
                        totalMoins35 = None
                    
                    try:
                        totalHommes = get_value(datas_file["ind_164"][count])
                    except Exception as exc:
                        totalHommes = None
                    
                    try:
                        totalFemmes = get_value(datas_file["ind_165"][count])
                    except Exception as exc:
                        totalFemmes = None
                    
                    try:
                        totalPlus35 = (totalHommes if totalHommes else 0) + (totalFemmes if totalFemmes else 0)
                        if not totalPlus35:
                            totalPlus35 = get_value(datas_file["ind_166"][count])
                    except Exception as exc:
                        totalPlus35 = None

                    try:
                        totalMenages = get_value(datas_file["ind_167"][count])
                    except Exception as exc:
                        totalMenages = None
                    
                    try:
                        nombreEthniques = get_value(datas_file["ind_168"][count])
                    except Exception as exc:
                        nombreEthniques = None

                    try:
                        task = facilitator_db.get_query_result(
                            {"type": "task", "administrative_level_id": str(headquarters_village.id), "sql_id": 56, "project_id": project_couch_id, "cycle_id": cycle_couch_id}
                        )[0][0]
                        form_response = task.get("form_response")
                        if not form_response:
                            form_response.append({})
                        if dateDeSensibilisation:
                            form_response[0]["dateDeSensibilisation"] = dateDeSensibilisation
                        if totalHommesMoins35:
                            form_response[0]["totalHommesMoins35"] = totalHommesMoins35
                        if totalFemmesMoins35:
                            form_response[0]["totalFemmesMoins35"] = totalFemmesMoins35
                        if totalMoins35:
                            form_response[0]["totalMoins35"] = totalMoins35
                        if totalHommes:
                            form_response[0]["totalHommes"] = totalHommes
                        if totalFemmes:
                            form_response[0]["totalFemmes"] = totalFemmes
                        if totalPlus35:
                            form_response[0]["totalPlus35"] = totalPlus35
                        if totalMenages:
                            form_response[0]["totalMenages"] = totalMenages
                        if nombreEthniques:
                            form_response[0]["nombreEthniques"] = nombreEthniques

                        task["form_response"] = form_response
                        nsc.update_cloudant_document(facilitator_db,  task["_id"], task)
                    except Exception as exc:
                        pass
                    # End 56

            except Exception as exc:
                list_error_found.append(f'\nLine N°{count} [{datas_file["ind_4"][count]}-{datas_file["ind_5"][count]}]: {exc.__str__()}')

            count += 1
            
    

    summary_errors = "##########################################################Summary###################################################################\n"
    summary_errors += f'\nNumber errors found: {len(list_error_found)}'
    for err in list_error_found:
        summary_errors += err

    if not os.path.exists("media/logs/errors"):
        os.makedirs("media/logs/errors")
    file_path = "logs/errors/ac_statistics_datas_logs_errors_" + str(datetime.today().replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_") + ".txt"
    
    f = open("media/"+file_path, "a")
    f.write(summary_errors)
    f.close()
    


    return ("ok", file_path.replace("/", "\\\\") if platform == "win32" else file_path)

