from dashboard.administrative_levels.functions import get_cascade_villages_by_administrative_level_id
from no_sql_client import NoSQLClient
from authentication.models import Facilitator
import os
from sys import platform
from datetime import datetime
import pandas as pd
from dashboard.facilitators.functions import get_cvds
from administrativelevels import models as administrativelevels_models

def get_datas_dict(reponses_datas, key, level: int = 1):
    for i in range(len(reponses_datas)):
        elt = reponses_datas[i]
        if level == 1:
            for k,v in elt.items():
                if k == key:
                    return v

def get_global_statistic_under_file_excel_or_csv(facilitator_db_name, file_type="excel", params={"type":"All", "id_administrativelevel":""}):
    nsc = NoSQLClient()

    _type = params.get("type")
    liste_villages = get_cascade_villages_by_administrative_level_id(params.get("id_administrativelevel"))
    if facilitator_db_name:
        fs = Facilitator.objects.filter(develop_mode=False, training_mode=False, no_sql_db_name=facilitator_db_name)
    else:
        fs = Facilitator.objects.filter(develop_mode=False, training_mode=False)

    d_cols = [ 
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "N°", "N°", "N°", "N°", "ind_0"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Région", "Région", "Région", "ind_1"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Préfecture", "Préfecture", "Préfecture", "ind_2"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Commune", "Commune", "Commune", "ind_3"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Canton", "Canton", "Canton", "ind_4"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "CVD", "CVD", "CVD", "ind_5"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Villages", "Villages", "Villages", "ind_6"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Unité géographique", "Unité géographique", "Unité géographique", "ind_7"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Nom de l'AC", "Nom de l'AC", "Nom de l'AC", "ind_8"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "Eff. Population", "Eff. Population", "Eff. Population", "ind_9"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "Nbre total ménages dans le village", "Nbre total ménages dans le village", "Nbre total ménages dans le village", "ind_10"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "Date de la séance", "ind_d"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "H", "ind_11"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "F", "ind_12"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "T", "ind_13"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES", "ind_14"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "Date de la séance", "ind_d"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "H", "ind_15"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "F", "ind_16"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "T", "ind_17"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES", "ind_18"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "Date de la séance", "ind_d"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "H", "ind_19"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "F", "ind_20"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "T", "ind_21"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES", "ind_22"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "Nombre total de ménage", "ind_23"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "Ethnies minoritaires", "ind_24"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "Date de la séance", "ind_d"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "H", "ind_25"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "F", "ind_26"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "T", "ind_27"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES", "ind_28"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "Nombre total de ménage", "ind_29"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "Ethnies minoritaires", "ind_30"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "Date de la séance", "ind_d"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "H", "ind_31"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "F", "ind_32"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "T", "ind_33"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES", "ind_34"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "Nombre total de ménage", "ind_35"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "Ethnies minoritaires", "ind_36"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "Date de la séance", "ind_d"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "H", "ind_37"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "F", "ind_38"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "T", "ind_39"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES", "ind_40"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "Nombre total de ménage", "ind_41"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "Ethnies minoritaires", "ind_42"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "Date de la séance", "ind_d"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "H", "ind_43"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "F", "ind_44"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "T", "ind_45"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES", "ind_46"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "Nombre total de ménage", "ind_47"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "Ethnies minoritaires", "ind_48"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "Date de la séance", "ind_d"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "H", "ind_49"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "F", "ind_50"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "T", "ind_51"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES", "ind_52"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "Nombre total de ménage", "ind_53"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "Ethnies minoritaires", "ind_54"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "Date de la séance", "ind_d"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "H", "ind_55"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "F", "ind_56"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "T", "ind_57"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES", "ind_58"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "Nombre total de ménage", "ind_59"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "Ethnies minoritaires", "ind_60"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "Date de la séance", "ind_d"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "H", "ind_61"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "F", "ind_62"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "T", "ind_63"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES", "ind_64"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "Nombre total de ménage", "ind_65"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "Ethnies minoritaires", "ind_66"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "Date de la séance", "ind_d"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "H", "ind_67"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "F", "ind_68"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "T", "ind_69"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES", "ind_70"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "Nombre total de ménage", "ind_71"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "Ethnies minoritaires", "ind_72"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "Date de la séance", "ind_d"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "H", "ind_73"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "F", "ind_74"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "T", "ind_75"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES", "ind_76"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "Nombre total de ménage", "ind_77"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "Ethnies minoritaires", "ind_78"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "Date de la séance", "ind_d"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "H", "ind_79"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "F", "ind_80"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "T", "ind_81"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES", "ind_82"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "Nombre total de ménage", "ind_83"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "Ethnies minoritaires", "ind_84"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "Date de la séance", "ind_d"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "H", "ind_85"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "F", "ind_86"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "T", "ind_87"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES", "ind_88"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "Nombre total de ménage", "ind_89"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "Ethnies minoritaires", "ind_90"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "Date de la séance", "ind_d"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "H", "ind_91"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "F", "ind_92"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "T", "ind_93"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES", "ind_94"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "Nombre total de ménage", "ind_95"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "Ethnies minoritaires", "ind_96"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "Date de la séance", "ind_d"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "H", "ind_97"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "F", "ind_98"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "T", "ind_99"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES", "ind_100"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "Nombre total de ménage", "ind_101"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "Ethnies minoritaires", "ind_102"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "Date de la séance", "ind_d"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "H", "ind_103"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "F", "ind_104"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "T", "ind_105"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES", "ind_106"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "Nombre total de ménage", "ind_107"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "Ethnies minoritaires", "ind_108"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "Date de la sensibilisation", "ind_d"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "H", "ind_109"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "F", "ind_110"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "T", "ind_111"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES", "ind_112"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "Nombre total de ménage", "ind_113"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "Ethnies minoritaires", "ind_114"),

        
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "H", "ind_115"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "F", "ind_116"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "T", "ind_117"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES", "ind_118"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "Nombre total de ménage", "ind_119"),
        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "Ethnies minoritaires", "ind_120"),


        ("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "Observations", "Observations", "Observations", "Observations", "ind_121")
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
                cvds = get_cvds(f_doc)
                break
        
        if f_doc:
            for cvd in cvds:
                administrative_level_cvd_village = cvd.get('village')
                if administrative_level_cvd_village:
                    administrativelevel_obj = administrativelevels_models.AdministrativeLevel.objects.using('mis').get(id=int(administrative_level_cvd_village['id']))
                    if administrativelevel_obj.cvd:
                        _ok = True
                        if liste_villages:
                            _ok = False
                            for village in liste_villages:
                                if str(administrative_level_cvd_village['id']) == str(village["administrative_id"]):
                                    _ok = True
                                    break
                        if _ok:
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "N°", "N°", "N°", "N°", "ind_0")][count] = count + 1
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Région", "Région", "Région", "ind_1")][count] = administrativelevel_obj.parent.parent.parent.parent.name
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Préfecture", "Préfecture", "Préfecture", "ind_2")][count] = administrativelevel_obj.parent.parent.parent.name
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Commune", "Commune", "Commune", "ind_3")][count] = administrativelevel_obj.parent.parent.name
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Canton", "Canton", "Canton", "ind_4")][count] = administrativelevel_obj.parent.name
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "CVD", "CVD", "CVD", "ind_5")][count] = administrativelevel_obj.cvd.name
                            villages = ""
                            for o in administrativelevel_obj.cvd.get_villages():
                                villages += f'{o.name} ; '
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Villages", "Villages", "Villages", "ind_6")][count] = villages
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Unité géographique", "Unité géographique", "Unité géographique", "ind_7")][count] = administrativelevel_obj.geographical_unit.attributed_number_in_canton
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "LOCALITE", "Nom de l'AC", "Nom de l'AC", "Nom de l'AC", "ind_8")][count] = f.name
                            
                            total_H, total_F, total_JEUNES, total_MENAGES, total_ETHNIES = 0, 0, 0, 0, 0
                            
                            for doc in query_result_docs:
                                _ = doc.get('doc')
                                if _.get('type') == "task" and str(administrative_level_cvd_village["id"]) == str(_["administrative_level_id"]):
                                    form_response = _.get("form_response")
                                    if form_response:
                                        value = None

                                        if _.get('sql_id') == 20: #Etablissement du profil du village
                                            try:
                                                value = get_datas_dict(form_response, "population", 1)["populationTotaleDuVillage"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "Eff. Population", "Eff. Population", "Eff. Population", "ind_9")][count] = value
                                            
                                            try:
                                                value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalHouseHolds"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "Nbre total ménages dans le village", "Nbre total ménages dans le village", "Nbre total ménages dans le village", "ind_10")][count] = value

                                        elif _.get('sql_id') == 13: #Introduction et présentation de l'AC par l'AADB lors de la première réunion cantonale
                                            try:
                                                value = form_response[0]["dateDeLaReunion"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "Date de la séance", "ind_d")][count] = value
                                            
                                            try:
                                                value = form_response[0]["totalHommes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "H", "ind_11")][count] = value

                                            try:
                                                value = form_response[0]["totalFemmes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "F", "ind_12")][count] = value

                                            try:
                                                value = (form_response[0].get("totalHommes") if form_response[0].get("totalHommes") else 0) + (form_response[0].get("totalFemmes") if form_response[0].get("totalFemmes") else 0)
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "T", "ind_13")][count] = value

                                            try:
                                                value = form_response[0]["totalMoins35"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "1- Visite préalable au niveau canton", "JEUNES", "ind_14")][count] = value


                                        elif _.get('sql_id') == 17: #Présentation et clarification de votre mission
                                            try:
                                                value = get_datas_dict(form_response, "dateDeLaReunion", 1)
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "Date de la séance", "ind_d")][count] = value

                                            try:
                                                value = get_datas_dict(form_response, "totalPersonnes", 1)["totalHommes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "H", "ind_15")][count] = value

                                            try:
                                                value = get_datas_dict(form_response, "totalPersonnes", 1)["totalFemmes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "F", "ind_16")][count] = value

                                            try:
                                                value = (get_datas_dict(form_response, "totalPersonnes", 1)["totalHommes"] if get_datas_dict(form_response, "totalPersonnes", 1)["totalHommes"] else 0) + (get_datas_dict(form_response, "totalPersonnes", 1)["totalFemmes"] if get_datas_dict(form_response, "totalPersonnes", 1)["totalFemmes"] else 0)
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "T", "ind_17")][count] = value

                                            try:
                                                value = get_datas_dict(form_response, "totalPersonnes", 1)["totalMoins35"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "1–Visites Prealables", "2- Visite préalable au niveau village", "JEUNES", "ind_18")][count] = value


                                        elif _.get('sql_id') == 22: #Brève introduction de la réunion et de l'ANADEB
                                            try:
                                                value = form_response[0]["dateDeLaReunion"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "Date de la séance", "ind_d")][count] = value

                                            try:
                                                value = form_response[0]["totalHommes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "H", "ind_19")][count] = value

                                            try:
                                                value = form_response[0]["totalFemmes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "F", "ind_20")][count] = value

                                            try:
                                                value = (form_response[0]["totalHommes"] if form_response[0]["totalHommes"] else 0) + (form_response[0]["totalFemmes"] if form_response[0]["totalFemmes"] else 0)
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "T", "ind_21")][count] = value
              
                                            try:
                                                value = form_response[0]["totalMoins35"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "JEUNES", "ind_22")][count] = value

                                            try:
                                                value = form_response[0]["totalMenages"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "Nombre total de ménage", "ind_23")][count] = value

                                            try:
                                                value = form_response[0]["nombreEthniques"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "3- 1ère réunion de village", "Ethnies minoritaires", "ind_24")][count] = value


                                        elif _.get('sql_id') == 27: #Ouverture de la deuxième réunion et vérification du quorum des participants
                                            try:
                                                value = form_response[0]["dateDeLaReunion"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "Date de la séance", "ind_d")][count] = value

                                            try:
                                                value = form_response[0]["totalHommes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "H", "ind_25")][count] = value

                                            try:
                                                value = form_response[0]["totalFemmes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "F", "ind_26")][count] = value

                                            try:
                                                value = (form_response[0]["totalHommes"] if form_response[0]["totalHommes"] else 0) + (form_response[0]["totalFemmes"] if form_response[0]["totalFemmes"] else 0)
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "T", "ind_27")][count] = value
              
                                            try:
                                                value = form_response[0]["totalMoins35"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "JEUNES", "ind_28")][count] = value

                                            try:
                                                value = form_response[0]["totalMenages"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "Nombre total de ménage", "ind_29")][count] = value

                                            try:
                                                value = form_response[0]["nombreEthniques"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "4- 2ème réunion de village", "Ethnies minoritaires", "ind_30")][count] = value


                                        elif _.get('sql_id') == 37: #Animer la session de formation sur le Module 1 : rôles et responsabilités des membres des organes de CVD
                                            try:
                                                value = form_response[0]["DateDeLaFormation"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "Date de la séance", "ind_d")][count] = value

                                            try:
                                                value = form_response[0]["totalHommes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "H", "ind_31")][count] = value

                                            try:
                                                value = form_response[0]["totalFemmes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "F", "ind_32")][count] = value

                                            try:
                                                value = (form_response[0]["totalHommes"] if form_response[0]["totalHommes"] else 0) + (form_response[0]["totalFemmes"] if form_response[0]["totalFemmes"] else 0)
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "T", "ind_33")][count] = value
              
                                            try:
                                                value = form_response[0]["totalMoins35"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "JEUNES", "ind_34")][count] = value

                                            try:
                                                value = form_response[0]["totalMenages"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "Nombre total de ménage", "ind_35")][count] = value

                                            try:
                                                value = form_response[0]["nombreEthniques"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "5- Formation ECG au niveau village", "Ethnies minoritaires", "ind_36")][count] = value


                                        elif _.get('sql_id') == 41: #Présenter les activités de la journée
                                            try:
                                                value = form_response[0]["dateDeLaReunion"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "Date de la séance", "ind_d")][count] = value

                                            try:
                                                value = form_response[0]["totalHommes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "H", "ind_37")][count] = value

                                            try:
                                                value = form_response[0]["totalFemmes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "F", "ind_38")][count] = value

                                            try:
                                                value = (form_response[0]["totalHommes"] if form_response[0]["totalHommes"] else 0) + (form_response[0]["totalFemmes"] if form_response[0]["totalFemmes"] else 0)
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "T", "ind_39")][count] = value
              
                                            try:
                                                value = form_response[0]["totalMoins35"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "JEUNES", "ind_40")][count] = value

                                            try:
                                                value = form_response[0]["totalMenages"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "Nombre total de ménage", "ind_41")][count] = value

                                            try:
                                                value = form_response[0]["nombreEthniques"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "2–Mobilisation Communautaire", "6- 3ème réunion de village", "Ethnies minoritaires", "ind_42")][count] = value


                                        elif _.get('sql_id') == 45: #Elaboration du plan d'action villageois (PAV)
                                            try:
                                                value = form_response[0]["dateDeLaReunion"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "Date de la séance", "ind_d")][count] = value

                                            try:
                                                value = form_response[0]["totalHommes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "H", "ind_43")][count] = value

                                            try:
                                                value = form_response[0]["totalFemmes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "F", "ind_44")][count] = value

                                            try:
                                                value = (form_response[0]["totalHommes"] if form_response[0]["totalHommes"] else 0) + (form_response[0]["totalFemmes"] if form_response[0]["totalFemmes"] else 0)
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "T", "ind_45")][count] = value
              
                                            try:
                                                value = form_response[0]["totalMoins35"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "JEUNES", "ind_46")][count] = value

                                            try:
                                                value = form_response[0]["totalMenages"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "Nombre total de ménage", "ind_47")][count] = value

                                            try:
                                                value = form_response[0]["nombreEthniques"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "7- 4ème réunion de village", "Ethnies minoritaires", "ind_48")][count] = value


                                        elif _.get('sql_id') == 46: #Mise en place et/ou restructuration du comité cantonal de développement (CCD)  et du comité cantonal de gestion des plaintes (CCGP)
                                            try:
                                                value = form_response[0]["dateDeLaReunion"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "Date de la séance", "ind_d")][count] = value

                                            try:
                                                value = form_response[0]["totalHommes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "H", "ind_49")][count] = value

                                            try:
                                                value = form_response[0]["totalFemmes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "F", "ind_50")][count] = value

                                            try:
                                                value = (form_response[0]["totalHommes"] if form_response[0]["totalHommes"] else 0) + (form_response[0]["totalFemmes"] if form_response[0]["totalFemmes"] else 0)
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "T", "ind_51")][count] = value
              
                                            try:
                                                value = form_response[0]["totalMoins35"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "JEUNES", "ind_52")][count] = value

                                            try:
                                                value = form_response[0]["totalMenages"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "Nombre total de ménage", "ind_53")][count] = value

                                            try:
                                                value = form_response[0]["nombreEthniques"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "8- Réunion cantonale J1", "Ethnies minoritaires", "ind_54")][count] = value


                                        elif _.get('sql_id') == 47: #Appui au CCD dans  l'analyse des PAV des villages, l'arbitrage, la sélection des sous - projets à financer et l'affection des ressources par sous - projet
                                            try:
                                                value = form_response[0]["dateDeLaReunion"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "Date de la séance", "ind_d")][count] = value

                                            try:
                                                value = form_response[0]["totalHommes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "H", "ind_55")][count] = value

                                            try:
                                                value = form_response[0]["totalFemmes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "F", "ind_56")][count] = value

                                            try:
                                                value = (form_response[0]["totalHommes"] if form_response[0]["totalHommes"] else 0) + (form_response[0]["totalFemmes"] if form_response[0]["totalFemmes"] else 0)
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "T", "ind_57")][count] = value
              
                                            try:
                                                value = form_response[0]["totalMoins35"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "JEUNES", "ind_58")][count] = value

                                            try:
                                                value = form_response[0]["totalMenages"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "Nombre total de ménage", "ind_59")][count] = value

                                            try:
                                                value = form_response[0]["nombreEthniques"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "9- Réunion cantonale J2", "Ethnies minoritaires", "ind_60")][count] = value


                                        elif _.get('sql_id') == 48: #Appui à l'organisation et à la facilitation de rencontre  communautaire de restitution des résultats de la reunion cantonale d'arbitrage
                                            try:
                                                value = form_response[0]["dateDeLaReunion"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "Date de la séance", "ind_d")][count] = value

                                            try:
                                                value = form_response[0]["totalHommes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "H", "ind_61")][count] = value

                                            try:
                                                value = form_response[0]["totalFemmes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "F", "ind_62")][count] = value

                                            try:
                                                value = (form_response[0]["totalHommes"] if form_response[0]["totalHommes"] else 0) + (form_response[0]["totalFemmes"] if form_response[0]["totalFemmes"] else 0)
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "T", "ind_63")][count] = value
              
                                            try:
                                                value = form_response[0]["totalMoins35"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "JEUNES", "ind_64")][count] = value

                                            try:
                                                value = form_response[0]["totalMenages"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "Nombre total de ménage", "ind_65")][count] = value

                                            try:
                                                value = form_response[0]["nombreEthniques"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "3–Planification", "10- 5ème réunion de village", "Ethnies minoritaires", "ind_66")][count] = value


                                        elif _.get('sql_id') == 49: #Appuie au bureau du CVD  dans la rédaction du document du sous projet et la demande de financement
                                            try:
                                                value = form_response[0]["dateDeSeance"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "Date de la séance", "ind_d")][count] = value

                                            try:
                                                value = form_response[0]["totalHommes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "H", "ind_67")][count] = value

                                            try:
                                                value = form_response[0]["totalFemmes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "F", "ind_68")][count] = value

                                            try:
                                                value = (form_response[0]["totalHommes"] if form_response[0]["totalHommes"] else 0) + (form_response[0]["totalFemmes"] if form_response[0]["totalFemmes"] else 0)
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "T", "ind_69")][count] = value
              
                                            try:
                                                value = form_response[0]["totalMoins35"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "JEUNES", "ind_70")][count] = value

                                            try:
                                                value = form_response[0]["totalMenages"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "Nombre total de ménage", "ind_71")][count] = value

                                            try:
                                                value = form_response[0]["nombreEthniques"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "4–Préparation Sous–Projet", "11- Réunion technique du CVD", "Ethnies minoritaires", "ind_72")][count] = value


                                        elif _.get('sql_id') == 50: #Réunion d'information de la communauté sur le sous projet: activités, coût estimatif et prochainbes étapes
                                            try:
                                                value = form_response[0]["dateDeLaReunion"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "Date de la séance", "ind_d")][count] = value

                                            try:
                                                value = form_response[0]["totalHommes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "H", "ind_73")][count] = value

                                            try:
                                                value = form_response[0]["totalFemmes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "F", "ind_74")][count] = value

                                            try:
                                                value = (form_response[0]["totalHommes"] if form_response[0]["totalHommes"] else 0) + (form_response[0]["totalFemmes"] if form_response[0]["totalFemmes"] else 0)
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "T", "ind_75")][count] = value
              
                                            try:
                                                value = form_response[0]["totalMoins35"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "JEUNES", "ind_76")][count] = value

                                            try:
                                                value = form_response[0]["totalMenages"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "Nombre total de ménage", "ind_77")][count] = value

                                            try:
                                                value = form_response[0]["nombreEthniques"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "12- 6ème réunion de village", "Ethnies minoritaires", "ind_78")][count] = value


                                        elif _.get('sql_id') == 51: #Soumission de la demande de financement du sous-projet à l’ANADEB pour approbation par le CORA
                                            try:
                                                value = form_response[0]["dateDeSoumission"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "Date de la séance", "ind_d")][count] = value

                                            try:
                                                value = form_response[0]["totalHommes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "H", "ind_79")][count] = value

                                            try:
                                                value = form_response[0]["totalFemmes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "F", "ind_80")][count] = value

                                            try:
                                                value = (form_response[0]["totalHommes"] if form_response[0]["totalHommes"] else 0) + (form_response[0]["totalFemmes"] if form_response[0]["totalFemmes"] else 0)
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "T", "ind_81")][count] = value
              
                                            try:
                                                value = form_response[0]["totalMoins35"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "JEUNES", "ind_82")][count] = value

                                            try:
                                                value = form_response[0]["totalMenages"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "Nombre total de ménage", "ind_83")][count] = value

                                            try:
                                                value = form_response[0]["nombreEthniques"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "5–Consultation Et Examen  Sous–Projet", "13- Soumission du sous projet", "Ethnies minoritaires", "ind_84")][count] = value


                                        elif _.get('sql_id') == 52: #Séance communautaire d'information sur les grandes lignes  du sous projet, sa durée d'exécution et les mesures de sauvegardes à observer
                                            try:
                                                value = form_response[0]["dateDeSeance"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "Date de la séance", "ind_d")][count] = value

                                            try:
                                                value = form_response[0]["totalHommes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "H", "ind_85")][count] = value

                                            try:
                                                value = form_response[0]["totalFemmes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "F", "ind_86")][count] = value

                                            try:
                                                value = (form_response[0]["totalHommes"] if form_response[0]["totalHommes"] else 0) + (form_response[0]["totalFemmes"] if form_response[0]["totalFemmes"] else 0)
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "T", "ind_87")][count] = value
              
                                            try:
                                                value = form_response[0]["totalMoins35"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "JEUNES", "ind_88")][count] = value

                                            try:
                                                value = form_response[0]["totalMenages"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "Nombre total de ménage", "ind_89")][count] = value

                                            try:
                                                value = form_response[0]["nombreEthniques"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "14- Mise en œuvre", "Ethnies minoritaires", "ind_90")][count] = value


                                        elif _.get('sql_id') == 53: #Appuie au CVD dans la production des rapports périodiques et l'organisation des réunions d'échanges sur l'état d'avancement des travaux
                                            try:
                                                value = form_response[0]["dateDeLaReunion"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "Date de la séance", "ind_d")][count] = value

                                            try:
                                                value = form_response[0]["totalHommes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "H", "ind_91")][count] = value

                                            try:
                                                value = form_response[0]["totalFemmes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "F", "ind_92")][count] = value

                                            try:
                                                value = (form_response[0]["totalHommes"] if form_response[0]["totalHommes"] else 0) + (form_response[0]["totalFemmes"] if form_response[0]["totalFemmes"] else 0)
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "T", "ind_93")][count] = value
              
                                            try:
                                                value = form_response[0]["totalMoins35"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "JEUNES", "ind_94")][count] = value

                                            try:
                                                value = form_response[0]["totalMenages"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "Nombre total de ménage", "ind_95")][count] = value

                                            try:
                                                value = form_response[0]["nombreEthniques"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "6–Mise En Œuvre Du Sous–Projet", "15- Réunions périodiques", "Ethnies minoritaires", "ind_96")][count] = value


                                        elif _.get('sql_id') == 54: #Classement et archivage de tous les documents relatifs à la mise en œuvre du sous projet
                                            try:
                                                value = form_response[0]["dateDeLaReunion"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "Date de la séance", "ind_d")][count] = value

                                            try:
                                                value = form_response[0]["totalHommes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "H", "ind_97")][count] = value

                                            try:
                                                value = form_response[0]["totalFemmes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "F", "ind_98")][count] = value

                                            try:
                                                value = (form_response[0]["totalHommes"] if form_response[0]["totalHommes"] else 0) + (form_response[0]["totalFemmes"] if form_response[0]["totalFemmes"] else 0)
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "T", "ind_99")][count] = value
              
                                            try:
                                                value = form_response[0]["totalMoins35"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "JEUNES", "ind_100")][count] = value

                                            try:
                                                value = form_response[0]["totalMenages"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "Nombre total de ménage", "ind_101")][count] = value

                                            try:
                                                value = form_response[0]["nombreEthniques"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "16- Clôture du sous-projet", "Ethnies minoritaires", "ind_102")][count] = value


                                        elif _.get('sql_id') == 55: #Réalisation de l'auto évaluation participative de la mise en œuvre du sous projet
                                            try:
                                                value = form_response[0]["dateDeSeance"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "Date de la séance", "ind_d")][count] = value

                                            try:
                                                value = form_response[0]["totalHommes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "H", "ind_103")][count] = value

                                            try:
                                                value = form_response[0]["totalFemmes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "F", "ind_104")][count] = value

                                            try:
                                                value = (form_response[0]["totalHommes"] if form_response[0]["totalHommes"] else 0) + (form_response[0]["totalFemmes"] if form_response[0]["totalFemmes"] else 0)
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "T", "ind_105")][count] = value
              
                                            try:
                                                value = form_response[0]["totalMoins35"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "JEUNES", "ind_106")][count] = value

                                            try:
                                                value = form_response[0]["totalMenages"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "Nombre total de ménage", "ind_107")][count] = value

                                            try:
                                                value = form_response[0]["nombreEthniques"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "17- Audit social", "Ethnies minoritaires", "ind_108")][count] = value


                                        elif _.get('sql_id') == 56: #Elaboration et mise en oeuvre du plan d'entretien et de maintenance de l'ouvrage
                                            try:
                                                value = form_response[0]["dateDeSensibilisation"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "Date de la sensibilisation", "ind_d")][count] = value

                                            try:
                                                value = form_response[0]["totalHommes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "H", "ind_109")][count] = value

                                            try:
                                                value = form_response[0]["totalFemmes"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "F", "ind_110")][count] = value

                                            try:
                                                value = (form_response[0]["totalHommes"] if form_response[0]["totalHommes"] else 0) + (form_response[0]["totalFemmes"] if form_response[0]["totalFemmes"] else 0)
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "T", "ind_111")][count] = value
              
                                            try:
                                                value = form_response[0]["totalMoins35"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "JEUNES", "ind_112")][count] = value

                                            try:
                                                value = form_response[0]["totalMenages"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "Nombre total de ménage", "ind_113")][count] = value

                                            try:
                                                value = form_response[0]["nombreEthniques"]
                                            except Exception as exc:
                                                value = None
                                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "7–Cloture Et Replanification Du Sous–Projet", "18- Exploitation et maintenance", "Ethnies minoritaires", "ind_114")][count] = value


                            #
                            for d_k, d_v in datas.items():
                                if d_k[4] == "H" and d_v.get(count):
                                    if d_v[count] > total_H:
                                        total_H = d_v[count]
                                elif d_k[4] == "F" and d_v.get(count):
                                    if d_v[count] > total_F:
                                        total_F = d_v[count]
                                elif d_k[4] == "JEUNES" and d_v.get(count):
                                    if d_v[count] > total_JEUNES:
                                        total_JEUNES = d_v[count]
                                elif d_k[4] == "Nombre total de ménage" and d_v.get(count):
                                    if d_v[count] > total_MENAGES:
                                        total_MENAGES = d_v[count]
                                elif d_k[4] == "Ethnies minoritaires" and d_v.get(count):
                                    if d_v[count] > total_ETHNIES:
                                        total_ETHNIES = d_v[count]

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "H", "ind_115")][count] = total_H
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "F", "ind_116")][count] = total_F
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "T", "ind_117")][count] = total_H + total_F
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "JEUNES", "ind_118")][count] = total_JEUNES
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "Nombre total de ménage", "ind_119")][count] = total_MENAGES
                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "PARTICIPATIONS", "TOTAL", "TOTAL", "Ethnies minoritaires", "ind_120")][count] = total_ETHNIES

                            datas[("FICHE DE SUIVI MENSUEL DES INDICATGEURS DES RÉUNIONS CANTONNALES/VILLAGEOISES", "Observations", "Observations", "Observations", "Observations", "ind_121")][count] = ""



                            count += 1



    if not os.path.exists("media/"+file_type+"/statistics"):
        os.makedirs("media/"+file_type+"/statistics")

    file_name = "statistics_" + _type.lower() + "_" + (("statistics".lower() + "_") if "statistics" else "")

    if file_type == "csv":
        file_path = file_type+"/statistics/" + file_name + str(datetime.today().replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_") +".csv"
        pd.DataFrame(datas, columns=cols).to_csv("media/"+file_path)
    else:
        file_path = file_type+"/statistics/" + file_name + str(datetime.today().replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_") +".xlsx"
        pd.DataFrame(datas, columns=cols).to_excel("media/"+file_path)

    if platform == "win32":
        # windows
        return file_path.replace("/", "\\\\")
    else:
        return file_path