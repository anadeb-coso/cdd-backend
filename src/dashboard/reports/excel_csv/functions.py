from django.utils.translation import gettext_lazy
import os
from sys import platform
from datetime import datetime
import pandas as pd

from no_sql_client import NoSQLClient
from dashboard.administrative_levels.functions import get_cascade_villages_by_administrative_level_id
from authentication.models import Facilitator
from dashboard.facilitators.functions import get_cvds
from cdd.functions import datetime_complet_str
from administrativelevels import models as administrativelevels_models
from dashboard.reports.constants import IGNORES
from cdd.my_librairies.functions import strip_accents


def get_datas_dict(reponses_datas, key, level: int = 1):
    for i in range(len(reponses_datas)):
        elt = reponses_datas[i]
        if level == 1:
            for k,v in elt.items():
                if k == key:
                    return v

def get_facilitator_excel_csv_under_file_excel_or_csv(request, facilitator_db_name=None):
    nsc = NoSQLClient()

    id_region = request.GET.get('id_region')
    id_prefecture = request.GET.get('id_prefecture')
    id_commune = request.GET.get('id_commune')
    id_canton = request.GET.get('id_canton')
    id_village = request.GET.get('id_village')
    type_field = request.GET.get('type_field', 'all')
    val_date_start = request.GET.get('val_date_start')
    val_date_end = request.GET.get('val_date_end')
    file_type = request.GET.get('file_type', 'excel')
    id_in_details = request.GET.get("id_in_details")
    _id = 0
    facilitators = []
    if (id_region or id_prefecture or id_commune or id_canton or id_village) and type_field:
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
            
        

        liste_villages = []

        liste_villages = get_cascade_villages_by_administrative_level_id(_id)
        if facilitator_db_name:
            fs = Facilitator.objects.filter(develop_mode=False, training_mode=False, no_sql_db_name=facilitator_db_name)
        else:
            fs = Facilitator.objects.filter(develop_mode=False, training_mode=False)
        for f in fs.order_by("name", "username"):
            dict_administrative_levels_with_infos = {}
            already_count_facilitator = False
            facilitator_db = nsc.get_db(f.no_sql_db_name)
            query_result_docs = facilitator_db.all_docs(include_docs=True)['rows']
            f_doc = None
            cvds = []
            name_with_sex = None
            name = None
            sex = None
            phone = None
            for doc in query_result_docs:
                doc = doc.get('doc')
                if doc.get('type') == "facilitator":
                    f_doc = doc
                    cvds = get_cvds(f_doc)
                    name_with_sex = f"{f_doc['sex']} {f_doc['name']}" if f_doc.get('sex') else f_doc['name']
                    name = f_doc['name']
                    sex =  'I' if not f_doc.get('sex') else "F" if f_doc.get('sex') == "Mme" else "M"
                    phone = f_doc["phone"]
                    break
            
            if f_doc:
                for _village in f_doc['administrative_levels']:
                    
                    if str(_village['id']).isdigit(): #Verify if id contain only digit
                            
                        for village in liste_villages:
                            if str(_village['id']) == str(village['administrative_id']):
                                if not already_count_facilitator:

                                    total_tasks_completed = 0
                                    total_tasks_uncompleted = 0
                                    total_tasks = 0
                                    total_tasks_completed_inter_date = 0
                                    total_tasks_uncompleted_inter_date = 0
                                    total_tasks_inter_date = 0
                                    last_activity_date = "0000-00-00 00:00:00"

                                    for doc in query_result_docs:
                                        _ = doc.get('doc')
                                        if _.get('type') == "task":
                                            last_updated = datetime_complet_str(_.get('last_updated'))
                                            if last_updated and last_activity_date < last_updated:
                                                last_activity_date = last_updated

                                            for administrative_level_cvd in cvds:
                                                village = administrative_level_cvd['village']
                                                if village and str(village.get("id")) == str(_["administrative_level_id"]):
                                                    if _.get("completed"):
                                                        if last_updated and val_date_start <= last_updated.split(' ')[0] <= val_date_end:
                                                            total_tasks_completed_inter_date += 1
                                                        total_tasks_completed += 1
                                                    else:
                                                        if last_updated and val_date_start <= last_updated.split(' ')[0] <= val_date_end:
                                                            total_tasks_uncompleted_inter_date += 1
                                                        total_tasks_uncompleted += 1
                                                    if last_updated and val_date_start <= last_updated.split(' ')[0] <= val_date_end:
                                                            total_tasks_inter_date += 1
                                                    total_tasks += 1


                                                    if dict_administrative_levels_with_infos.get(administrative_level_cvd.get("name")):
                                                        if _.get("completed"):
                                                            if last_updated and val_date_start <= last_updated.split(' ')[0] <= val_date_end:
                                                                dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks_completed_inter_date'] += 1
                                                            dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks_completed'] += 1
                                                        else:
                                                            if last_updated and val_date_start <= last_updated.split(' ')[0] <= val_date_end:
                                                                dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks_uncompleted_inter_date'] += 1
                                                            dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks_uncompleted'] += 1
                                                        if last_updated and val_date_start <= last_updated.split(' ')[0] <= val_date_end:
                                                            dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks_inter_date'] += 1
                                                        dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks'] += 1
                                                    else:
                                                        if _.get("completed"):
                                                            dict_administrative_levels_with_infos[administrative_level_cvd.get("name")] = {
                                                                'total_tasks_completed': 1,
                                                                'total_tasks_uncompleted': 0,
                                                                'total_tasks_completed_inter_date': 1 if last_updated and val_date_start <= last_updated.split(' ')[0] <= val_date_end else 0,
                                                                'total_tasks_uncompleted_inter_date': 0
                                                            }
                                                        else:
                                                            dict_administrative_levels_with_infos[administrative_level_cvd.get("name")] = {
                                                                'total_tasks_completed': 0,
                                                                'total_tasks_uncompleted': 1,
                                                                'total_tasks_completed_inter_date': 0,
                                                                'total_tasks_uncompleted_inter_date': 1 if last_updated and val_date_start <= last_updated.split(' ')[0] <= val_date_end else 0
                                                            }
                                                        
                                                        dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks_inter_date'] = 1 if last_updated and val_date_start <= last_updated.split(' ')[0] <= val_date_end else 0
                                                        dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks'] = 1
                                                    dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['cvd'] = administrative_level_cvd

                                    nbr_villages = 0
                                    for key, value in dict_administrative_levels_with_infos.items():
                                        dict_administrative_levels_with_infos[key]["percentage_tasks_completed"] = ((value["total_tasks_completed"]/value["total_tasks"])*100) if value["total_tasks"] else 0
                                        dict_administrative_levels_with_infos[key]["percentage_tasks_completed_inter_date"] = ((value["total_tasks_completed_inter_date"]/value["total_tasks"])*100) if value["total_tasks"] else 0
                                        del dict_administrative_levels_with_infos[key]["total_tasks"]

                                        nbr_villages += len(dict_administrative_levels_with_infos[key]['cvd']['villages'])

                                    percent = float("%.2f" % (((total_tasks_completed/total_tasks)*100) if total_tasks else 0))
                                    percent_inter_date = float("%.2f" % (((total_tasks_completed_inter_date/total_tasks)*100) if total_tasks else 0))
                                    if last_activity_date == "0000-00-00 00:00:00":
                                        last_activity_date = None
                                    else:
                                        last_activity_date = datetime.strptime(last_activity_date, '%Y-%m-%d %H:%M:%S')

                                    facilitators.append({
                                        'facilitator': f_doc, "name_with_sex": name_with_sex, "name": name, "sex": sex,
                                        "username": f.username, "phone": phone, 
                                        "total_tasks_completed": total_tasks_completed,
                                        "total_tasks_uncompleted": total_tasks_uncompleted,
                                        "total_tasks": total_tasks,
                                        "total_tasks_completed_inter_date": total_tasks_completed_inter_date,
                                        "total_tasks_uncompleted_inter_date": total_tasks_uncompleted_inter_date,
                                        "total_tasks_inter_date": total_tasks_inter_date,
                                        'last_activity_date': last_activity_date, "percent": percent, 
                                        "percent_inter_date": percent_inter_date, 
                                        "dict_administrative_levels_with_infos": dict_administrative_levels_with_infos,
                                        "nbr_villages": nbr_villages
                                    })
                                    already_count_facilitator = True
    else:
        is_training = bool(request.GET.get('is_training', "False") == "True")
        is_develop = bool(request.GET.get('is_develop', "False") == "True")
        if facilitator_db_name:
            fs = Facilitator.objects.filter(develop_mode=is_develop, training_mode=is_training, no_sql_db_name=facilitator_db_name)
        else:
            fs = Facilitator.objects.filter(develop_mode=is_develop, training_mode=is_training)
        for f in fs.order_by("name", "username"):
            dict_administrative_levels_with_infos = {}
            already_count_facilitator = False
            facilitator_db = nsc.get_db(f.no_sql_db_name)
            query_result_docs = facilitator_db.all_docs(include_docs=True)['rows']
            f_doc = None
            cvds = []
            name_with_sex = None
            name = None
            sex = None
            phone = None
            for doc in query_result_docs:
                doc = doc.get('doc')
                if doc.get('type') == "facilitator":
                    f_doc = doc
                    cvds = get_cvds(f_doc)
                    name_with_sex = f"{f_doc['sex']} {f_doc['name']}" if f_doc.get('sex') else f_doc['name']
                    name = f_doc['name']
                    sex =  'I' if not f_doc.get('sex') else "F" if f_doc.get('sex') == "Mme" else "M"
                    phone = f_doc["phone"]
                    break
            
            if f_doc:        
                total_tasks_completed = 0
                total_tasks_uncompleted = 0
                total_tasks = 0
                total_tasks_completed_inter_date = 0
                total_tasks_uncompleted_inter_date = 0
                total_tasks_inter_date = 0
                last_activity_date = "0000-00-00 00:00:00"

                for doc in query_result_docs:
                    _ = doc.get('doc')
                    if _.get('type') == "task":
                        last_updated = datetime_complet_str(_.get('last_updated'))
                        if last_updated and last_activity_date < last_updated:
                            last_activity_date = last_updated
                        for administrative_level_cvd in cvds:
                            village = administrative_level_cvd['village']
                            if village and str(village.get("id")) == str(_["administrative_level_id"]):
                                if _.get("completed"):
                                    if last_updated and val_date_start <= last_updated.split(' ')[0] <= val_date_end:
                                        total_tasks_completed_inter_date += 1
                                    total_tasks_completed += 1
                                else:
                                    if last_updated and val_date_start <= last_updated.split(' ')[0] <= val_date_end:
                                        total_tasks_uncompleted_inter_date += 1
                                    total_tasks_uncompleted += 1
                                if last_updated and val_date_start <= last_updated.split(' ')[0] <= val_date_end:
                                    total_tasks_inter_date += 1
                                total_tasks += 1


                                if dict_administrative_levels_with_infos.get(administrative_level_cvd.get("name")):
                                    if _.get("completed"):
                                        if last_updated and val_date_start <= last_updated.split(' ')[0] <= val_date_end:
                                            dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks_completed_inter_date'] += 1
                                        dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks_completed'] += 1
                                    else:
                                        if last_updated and val_date_start <= last_updated.split(' ')[0] <= val_date_end:
                                            dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks_uncompleted_inter_date'] += 1
                                        dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks_uncompleted'] += 1
                                    if last_updated and val_date_start <= last_updated.split(' ')[0] <= val_date_end:
                                        dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks_inter_date'] += 1
                                    dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks'] += 1
                                else:
                                    if _.get("completed"):
                                        dict_administrative_levels_with_infos[administrative_level_cvd.get("name")] = {
                                            'total_tasks_completed': 1,
                                            'total_tasks_uncompleted': 0,
                                            'total_tasks_completed_inter_date': 1 if last_updated and val_date_start <= last_updated.split(' ')[0] <= val_date_end else 0,
                                            'total_tasks_uncompleted_inter_date': 0
                                        }
                                    else:
                                        dict_administrative_levels_with_infos[administrative_level_cvd.get("name")] = {
                                            'total_tasks_completed': 0,
                                            'total_tasks_uncompleted': 1,
                                            'total_tasks_completed_inter_date': 0,
                                            'total_tasks_uncompleted_inter_date': 1 if last_updated and val_date_start <= last_updated.split(' ')[0] <= val_date_end else 0
                                        }
                                    
                                    dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks_inter_date'] = 1 if last_updated and val_date_start <= last_updated.split(' ')[0] <= val_date_end else 0
                                    dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['total_tasks'] = 1
                                dict_administrative_levels_with_infos[administrative_level_cvd.get("name")]['cvd'] = administrative_level_cvd

                nbr_villages = 0
                for key, value in dict_administrative_levels_with_infos.items():
                    dict_administrative_levels_with_infos[key]["percentage_tasks_completed"] = ((value["total_tasks_completed"]/value["total_tasks"])*100) if value["total_tasks"] else 0
                    dict_administrative_levels_with_infos[key]["percentage_tasks_completed_inter_date"] = ((value["total_tasks_completed_inter_date"]/value["total_tasks"])*100) if value["total_tasks"] else 0
                    dict_administrative_levels_with_infos[key]["total_tasks"]

                    nbr_villages += len(dict_administrative_levels_with_infos[key]['cvd']['villages'])

                percent = float("%.2f" % (((total_tasks_completed/total_tasks)*100) if total_tasks else 0))
                percent_inter_date = float("%.2f" % (((total_tasks_completed_inter_date/total_tasks)*100) if total_tasks else 0))
                if last_activity_date == "0000-00-00 00:00:00":
                    last_activity_date = None
                else:
                    last_activity_date = datetime.strptime(last_activity_date, '%Y-%m-%d %H:%M:%S')

                facilitators.append({
                    'facilitator': f_doc, "name_with_sex": name_with_sex, "name": name, "sex": sex,
                    "username": f.username, "phone": phone, 
                    "total_tasks_completed": total_tasks_completed,
                    "total_tasks_uncompleted": total_tasks_uncompleted,
                    "total_tasks": total_tasks,
                    "total_tasks_completed_inter_date": total_tasks_completed_inter_date,
                    "total_tasks_uncompleted_inter_date": total_tasks_uncompleted_inter_date,
                    "total_tasks_inter_date": total_tasks_inter_date,
                    'last_activity_date': last_activity_date, "percent": percent, 
                    "percent_inter_date": percent_inter_date, 
                    "dict_administrative_levels_with_infos": dict_administrative_levels_with_infos,
                    "nbr_villages": nbr_villages
                })
    _date = " " + datetime.strptime(val_date_start, '%Y-%m-%d').date().__str__() + " " + gettext_lazy('to').__str__() + " " + datetime.strptime(val_date_end, '%Y-%m-%d').date().__str__()
    d_cols = [
        (gettext_lazy('N°').__str__(), gettext_lazy('N°').__str__()),
        (gettext_lazy('Name').__str__(), gettext_lazy('Name').__str__()),
        (gettext_lazy('Sex').__str__(), gettext_lazy('Sex').__str__()),
        (gettext_lazy('Phone').__str__(), gettext_lazy('Phone').__str__()),
        (gettext_lazy('CVD').__str__(), gettext_lazy('Nbr').__str__()),
        (gettext_lazy('CVD').__str__(), gettext_lazy('CVD').__str__()),
        (gettext_lazy('Village(s)').__str__(), gettext_lazy('Nbr').__str__()),
        (gettext_lazy('Village(s)').__str__(), gettext_lazy('Village(s)').__str__()),
        (gettext_lazy('Period').__str__()+_date, gettext_lazy('Completed').__str__()),
        (gettext_lazy('Period').__str__()+_date, gettext_lazy('Uncompleted').__str__()),
        (gettext_lazy('Period').__str__()+_date, gettext_lazy('Total').__str__()),
        (gettext_lazy('Period').__str__()+_date, gettext_lazy('Percentage').__str__()),
        (gettext_lazy('All').__str__(), gettext_lazy('Completed').__str__()),
        (gettext_lazy('All').__str__(), gettext_lazy('Uncompleted').__str__()),
        (gettext_lazy('All').__str__(), gettext_lazy('Total').__str__()),
        (gettext_lazy('All').__str__(), gettext_lazy('Percentage').__str__())
    ]
    
    cols = pd.MultiIndex.from_tuples(d_cols)
    datas = {}
    for col in d_cols:
        datas[col] = {}
    index_f = 0
    for facilitator in facilitators:
        
        _cvds = ""
        _villages = ""
        count_c = 1
        for k_c, v_c in facilitator['dict_administrative_levels_with_infos'].items():
            count_v = 1
            try:
                cvd_obj = administrativelevels_models.CVD.objects.using('mis').get(id=int(v_c['cvd']['sql_id']))
                _cvds += f'{count_c}-/ {cvd_obj.get_name()}\n'
                for _v in cvd_obj.get_villages():
                    _villages += f'{count_c}.{count_v}-/ {_v.name}\n'
                    count_v += 1
                
                if id_in_details == "0":
                    pass
                else:
                    datas[(gettext_lazy('N°').__str__(), gettext_lazy('N°').__str__())][index_f] = index_f + 1
                    datas[(gettext_lazy('Name').__str__(), gettext_lazy('Name').__str__())][index_f] = facilitator['name']
                    datas[(gettext_lazy('Sex').__str__(), gettext_lazy('Sex').__str__())][index_f] = facilitator['sex']
                    datas[(gettext_lazy('Phone').__str__(), gettext_lazy('Phone').__str__())][index_f] = facilitator['phone']
                    datas[(gettext_lazy('CVD').__str__(), gettext_lazy('Nbr').__str__())][index_f] = len(facilitator['dict_administrative_levels_with_infos'])

                    datas[(gettext_lazy('CVD').__str__(), gettext_lazy('CVD').__str__())][index_f] = _cvds
                    datas[(gettext_lazy('Village(s)').__str__(), gettext_lazy('Nbr').__str__())][index_f] = count_v - 1
                    datas[(gettext_lazy('Village(s)').__str__(), gettext_lazy('Village(s)').__str__())][index_f] = _villages
                    
                    
                    datas[(gettext_lazy('Period').__str__()+_date, gettext_lazy('Completed').__str__())][index_f] = v_c['total_tasks_completed_inter_date']
                    datas[(gettext_lazy('Period').__str__()+_date, gettext_lazy('Uncompleted').__str__())][index_f] = v_c['total_tasks_uncompleted_inter_date']
                    datas[(gettext_lazy('Period').__str__()+_date, gettext_lazy('Total').__str__())][index_f] = v_c['total_tasks_inter_date']
                    datas[(gettext_lazy('Period').__str__()+_date, gettext_lazy('Percentage').__str__())][index_f] = v_c['percentage_tasks_completed_inter_date']
                    datas[(gettext_lazy('All').__str__(), gettext_lazy('Completed').__str__())][index_f] = v_c['total_tasks_completed']
                    datas[(gettext_lazy('All').__str__(), gettext_lazy('Uncompleted').__str__())][index_f] = v_c['total_tasks_uncompleted']
                    datas[(gettext_lazy('All').__str__(), gettext_lazy('Total').__str__())][index_f] = v_c['total_tasks']
                    datas[(gettext_lazy('All').__str__(), gettext_lazy('Percentage').__str__())][index_f] = v_c['percentage_tasks_completed']

                    _cvds = ''
                    _villages = ''
                    index_f += 1
                


            except Exception as exc:
                pass
            count_c += 1
        
        if id_in_details == "0":
            datas[(gettext_lazy('N°').__str__(), gettext_lazy('N°').__str__())][index_f] = index_f + 1
            datas[(gettext_lazy('Name').__str__(), gettext_lazy('Name').__str__())][index_f] = facilitator['name']
            datas[(gettext_lazy('Sex').__str__(), gettext_lazy('Sex').__str__())][index_f] = facilitator['sex']
            datas[(gettext_lazy('Phone').__str__(), gettext_lazy('Phone').__str__())][index_f] = facilitator['phone']

            datas[(gettext_lazy('CVD').__str__(), gettext_lazy('Nbr').__str__())][index_f] = len(facilitator['dict_administrative_levels_with_infos'])

            datas[(gettext_lazy('CVD').__str__(), gettext_lazy('CVD').__str__())][index_f] = _cvds

            datas[(gettext_lazy('Village(s)').__str__(), gettext_lazy('Nbr').__str__())][index_f] = facilitator['nbr_villages']
            datas[(gettext_lazy('Village(s)').__str__(), gettext_lazy('Village(s)').__str__())][index_f] = _villages
            
            datas[(gettext_lazy('Period').__str__()+_date, gettext_lazy('Completed').__str__())][index_f] = facilitator['total_tasks_completed_inter_date']
            datas[(gettext_lazy('Period').__str__()+_date, gettext_lazy('Uncompleted').__str__())][index_f] = facilitator['total_tasks_uncompleted_inter_date']
            datas[(gettext_lazy('Period').__str__()+_date, gettext_lazy('Total').__str__())][index_f] = facilitator['total_tasks_inter_date']
            datas[(gettext_lazy('Period').__str__()+_date, gettext_lazy('Percentage').__str__())][index_f] = facilitator['percent_inter_date']
            datas[(gettext_lazy('All').__str__(), gettext_lazy('Completed').__str__())][index_f] = facilitator['total_tasks_completed']
            datas[(gettext_lazy('All').__str__(), gettext_lazy('Uncompleted').__str__())][index_f] = facilitator['total_tasks_uncompleted']
            datas[(gettext_lazy('All').__str__(), gettext_lazy('Total').__str__())][index_f] = facilitator['total_tasks']
            datas[(gettext_lazy('All').__str__(), gettext_lazy('Percentage').__str__())][index_f] = facilitator['percent']
            index_f += 1


    if not os.path.exists("media/"+file_type+"/reports/excel_csv"):
        os.makedirs("media/"+file_type+"/reports/excel_csv")

    file_name = "reports_excel_csv_" + type_field.lower() + "_" + (("reports_excel_csv_".lower() + "_") if "reports_excel_csv_" else "")

    if file_type == "csv":
        file_path = file_type+"/reports/excel_csv/" + file_name + str(datetime.today().replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_") +".csv"
        pd.DataFrame(datas, columns=cols).to_csv("media/"+file_path)
    else:
        file_path = file_type+"/reports/excel_csv/" + file_name + str(datetime.today().replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_") +".xlsx"
        pd.DataFrame(datas, columns=cols).to_excel("media/"+file_path)

    if platform == "win32":
        # windows
        return file_path.replace("/", "\\\\")
    else:
        return file_path
    








def get_villages_monograph_under_file_excel_or_csv(facilitator_db_name, file_type="excel", params={"type":"All", "id_administrativelevel":""}):
    nsc = NoSQLClient()

    _type = params.get("type")
    liste_villages = get_cascade_villages_by_administrative_level_id(params.get("id_administrativelevel"))
    if facilitator_db_name:
        fs = Facilitator.objects.filter(develop_mode=False, training_mode=False, no_sql_db_name=facilitator_db_name)
    else:
        fs = Facilitator.objects.filter(develop_mode=False, training_mode=False)

    d_cols = [ 
        ("MONOGRAPHIE", "N°", "N°", "N°", "ind_0"),
        ("MONOGRAPHIE", "LOCALITE", "Région", "Région", "ind_1"),
        ("MONOGRAPHIE", "LOCALITE", "Préfecture", "Préfecture", "ind_2"),
        ("MONOGRAPHIE", "LOCALITE", "Commune", "Commune", "ind_3"),
        ("MONOGRAPHIE", "LOCALITE", "Canton", "Canton", "ind_4"),
        ("MONOGRAPHIE", "LOCALITE", "CVD", "CVD", "ind_5"),
        ("MONOGRAPHIE", "LOCALITE", "Villages", "Villages", "ind_6"),
        ("MONOGRAPHIE", "LOCALITE", "Unité géographique", "Unité géographique", "ind_7"),
        ("MONOGRAPHIE", "LOCALITE", "Nom de l'AC", "Nom de l'AC", "ind_8"),
        ("MONOGRAPHIE", "LOCALITE", "Eff. Population", "Eff. Population", "ind_9"),
        ("MONOGRAPHIE", "LOCALITE", "Nbre total ménages dans le village", "Nbre total ménages dans le village", "ind_10"),

        ("MONOGRAPHIE", "Équipement et infrastructures", "Écoles", "Lycée", "ind_11"),
        ("MONOGRAPHIE", "Équipement et infrastructures", "Écoles", "Collége", "ind_12"),
        ("MONOGRAPHIE", "Équipement et infrastructures", "Écoles", "École primaire", "ind_13"),
        ("MONOGRAPHIE", "Équipement et infrastructures", "Écoles", "Préscolaire", "ind_14"),
        ("MONOGRAPHIE", "Équipement et infrastructures", "Écoles", "Autre", "ind_15"),
        
        ("MONOGRAPHIE", "Équipement et infrastructures", "Santé", "Dispensaire", "ind_16"),
        ("MONOGRAPHIE", "Équipement et infrastructures", "Santé", "USP", "ind_17"),
        ("MONOGRAPHIE", "Équipement et infrastructures", "Santé", "CMS", "ind_18"),
        ("MONOGRAPHIE", "Équipement et infrastructures", "Santé", "Clinique", "ind_19"),
        ("MONOGRAPHIE", "Équipement et infrastructures", "Santé", "Autre", "ind_20"),
        
        ("MONOGRAPHIE", "Équipement et infrastructures", "Religieu", "Eglise", "ind_21"),
        ("MONOGRAPHIE", "Équipement et infrastructures", "Religieu", "Mosquée", "ind_22"),
        ("MONOGRAPHIE", "Équipement et infrastructures", "Religieu", "Autres", "ind_23"),
        
        ("MONOGRAPHIE", "Équipement et infrastructures", "infrastructures de marchés", "Hangar", "ind_24"),
        
        ("MONOGRAPHIE", "Équipement et infrastructures", "Infrast routiéres/type", "Piste", "ind_25"),
        
        ("MONOGRAPHIE", "Équipement et infrastructures", "Équipement et infrastructures", "Toutes", "ind_26"),

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
                            datas[("MONOGRAPHIE", "N°", "N°", "N°", "ind_0")][count] = count + 1
                            datas[("MONOGRAPHIE", "LOCALITE", "Région", "Région", "ind_1")][count] = administrativelevel_obj.parent.parent.parent.parent.name
                            datas[("MONOGRAPHIE", "LOCALITE", "Préfecture", "Préfecture", "ind_2")][count] = administrativelevel_obj.parent.parent.parent.name
                            datas[("MONOGRAPHIE", "LOCALITE", "Commune", "Commune", "ind_3")][count] = administrativelevel_obj.parent.parent.name
                            datas[("MONOGRAPHIE", "LOCALITE", "Canton", "Canton", "ind_4")][count] = administrativelevel_obj.parent.name
                            datas[("MONOGRAPHIE", "LOCALITE", "CVD", "CVD", "ind_5")][count] = administrativelevel_obj.cvd.name
                            datas[("MONOGRAPHIE", "LOCALITE", "Villages", "Villages", "ind_6")][count] = ";".join([o.name for o in administrativelevel_obj.cvd.get_villages()])
                            datas[("MONOGRAPHIE", "LOCALITE", "Unité géographique", "Unité géographique", "ind_7")][count] = administrativelevel_obj.geographical_unit.attributed_number_in_canton
                            datas[("MONOGRAPHIE", "LOCALITE", "Nom de l'AC", "Nom de l'AC", "ind_8")][count] = f.name
                            
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
                                            datas[("MONOGRAPHIE", "LOCALITE", "Eff. Population", "Eff. Population", "ind_9")][count] = value
                                            
                                            try:
                                                value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalHouseHolds"]
                                            except Exception as exc:
                                                value = None
                                            datas[("MONOGRAPHIE", "LOCALITE", "Nbre total ménages dans le village", "Nbre total ménages dans le village", "ind_10")][count] = value

                                            try:
                                                value = dict(get_datas_dict(form_response, "equipementEtInfrastructures", 1))

                                                datas[("MONOGRAPHIE", "Équipement et infrastructures", "Équipement et infrastructures", "Toutes", "ind_26")][count] = ""
                                                if value.get('ecoles'):
                                                    ecoles = value.get('ecoles')
                                                    if ecoles.get('ecoleLycee'):
                                                        datas[("MONOGRAPHIE", "Équipement et infrastructures", "Écoles", "Lycée", "ind_11")][count] = ecoles.get('ecoleLycee')
                                                        datas[("MONOGRAPHIE", "Équipement et infrastructures", "Équipement et infrastructures", "Toutes", "ind_26")][count] += "Lycée ; " if ecoles.get('ecoleLycee') == "Oui" else ""
                                                    if ecoles.get('ecoleCollege'):
                                                        datas[("MONOGRAPHIE", "Équipement et infrastructures", "Écoles", "Collége", "ind_12")][count] = ecoles.get('ecoleCollege')
                                                        datas[("MONOGRAPHIE", "Équipement et infrastructures", "Équipement et infrastructures", "Toutes", "ind_26")][count] += "Collége ; " if ecoles.get('ecoleCollege') == "Oui" else ""
                                                    if ecoles.get('ecolePrimaire'):
                                                        datas[("MONOGRAPHIE", "Équipement et infrastructures", "Écoles", "École primaire", "ind_13")][count] = ecoles.get('ecolePrimaire')
                                                        datas[("MONOGRAPHIE", "Équipement et infrastructures", "Équipement et infrastructures", "Toutes", "ind_26")][count] += "École primaire ; " if ecoles.get('ecolePrimaire') == "Oui" else ""
                                                    if ecoles.get('ecoleprescolaire'):
                                                        datas[("MONOGRAPHIE", "Équipement et infrastructures", "Écoles", "Préscolaire", "ind_14")][count] = ecoles.get('ecoleprescolaire')
                                                        datas[("MONOGRAPHIE", "Équipement et infrastructures", "Équipement et infrastructures", "Toutes", "ind_26")][count] += "École primaire ; " if ecoles.get('ecoleprescolaire') == "Oui" else ""
                                                    if ecoles.get('ecoleAutre') and (strip_accents(ecoles.get('ecoleAutre')).strip()).title().replace('-', ' ') not in IGNORES:
                                                        datas[("MONOGRAPHIE", "Équipement et infrastructures", "Écoles", "Autre", "ind_15")][count] = ecoles.get('ecoleAutre')
                                                        datas[("MONOGRAPHIE", "Équipement et infrastructures", "Équipement et infrastructures", "Toutes", "ind_26")][count] += f'{ecoles.get("ecoleAutre")} ; '
                                                
                                                if value.get('sante'):
                                                    santes = value.get('sante')
                                                    if santes.get('santeDispensaire'):
                                                        datas[("MONOGRAPHIE", "Équipement et infrastructures", "Santé", "Dispensaire", "ind_16")][count] = santes.get('santeDispensaire')
                                                        datas[("MONOGRAPHIE", "Équipement et infrastructures", "Équipement et infrastructures", "Toutes", "ind_26")][count] += "Dispensaire ; " if santes.get('santeDispensaire') == "Oui" else ""
                                                    if santes.get('santeUSP'):
                                                        datas[("MONOGRAPHIE", "Équipement et infrastructures", "Santé", "USP", "ind_17")][count] = santes.get('santeUSP')
                                                        datas[("MONOGRAPHIE", "Équipement et infrastructures", "Équipement et infrastructures", "Toutes", "ind_26")][count] += "USP ; " if santes.get('santeUSP') == "Oui" else ""
                                                    if santes.get('santeCMS'):
                                                        datas[("MONOGRAPHIE", "Équipement et infrastructures", "Santé", "CMS", "ind_18")][count] = santes.get('santeCMS')
                                                        datas[("MONOGRAPHIE", "Équipement et infrastructures", "Équipement et infrastructures", "Toutes", "ind_26")][count] += "CMS ; " if santes.get('santeCMS') == "Oui" else ""
                                                    if santes.get('santeClinique'):
                                                        datas[("MONOGRAPHIE", "Équipement et infrastructures", "Santé", "Clinique", "ind_19")][count] = santes.get('santeClinique')
                                                        datas[("MONOGRAPHIE", "Équipement et infrastructures", "Équipement et infrastructures", "Toutes", "ind_26")][count] += "Clinique ; " if santes.get('santeClinique') == "Oui" else ""
                                                    if santes.get('santeAutre') and (strip_accents(santes.get('santeAutre')).strip()).title().replace('-', ' ') not in IGNORES:
                                                        datas[("MONOGRAPHIE", "Équipement et infrastructures", "Santé", "Autre", "ind_20")][count] = santes.get('santeAutre')
                                                        datas[("MONOGRAPHIE", "Équipement et infrastructures", "Équipement et infrastructures", "Toutes", "ind_26")][count] += f'{santes.get("santeAutre")} ; '
                                                
                                                if value.get('religieu'):
                                                    religieux = value.get('religieu')
                                                    if religieux.get('religieuEglise'):
                                                        datas[("MONOGRAPHIE", "Équipement et infrastructures", "Religieu", "Eglise", "ind_21")][count] = religieux.get('religieuEglise')
                                                        datas[("MONOGRAPHIE", "Équipement et infrastructures", "Équipement et infrastructures", "Toutes", "ind_26")][count] += "Eglise ; " if religieux.get('religieuEglise') == "Oui" else ""
                                                    if religieux.get('religieuMosquee'):
                                                        datas[("MONOGRAPHIE", "Équipement et infrastructures",  "Religieu", "Mosquée", "ind_22")][count] = religieux.get('religieuMosquee')
                                                        datas[("MONOGRAPHIE", "Équipement et infrastructures", "Équipement et infrastructures", "Toutes", "ind_26")][count] += "Mosquée ; " if religieux.get('religieuMosquee') == "Oui" else ""
                                                    if religieux.get('religeuAutres') and (strip_accents(religieux.get('religeuAutres')).strip()).title().replace('-', ' ') not in IGNORES:
                                                        datas[("MONOGRAPHIE", "Équipement et infrastructures", "Religieu", "Autres", "ind_23")][count] = religieux.get('religeuAutres')
                                                        datas[("MONOGRAPHIE", "Équipement et infrastructures", "Équipement et infrastructures", "Toutes", "ind_26")][count] += f'{religieux.get("religeuAutres")} ; '
                                                
                                                if value.get('infrastDeMarches'):
                                                    infrastDeMarches = value.get('infrastDeMarches')
                                                    if infrastDeMarches.get('hangar'):
                                                        datas[("MONOGRAPHIE", "Équipement et infrastructures", "infrastructures de marchés", "Hangar", "ind_24")][count] = infrastDeMarches.get('hangar')
                                                        datas[("MONOGRAPHIE", "Équipement et infrastructures", "Équipement et infrastructures", "Toutes", "ind_26")][count] += "Hangar ; " if infrastDeMarches.get('hangar') == "Oui" else ""
                                                
                                                if value.get('infrastRoutieres'):
                                                    infrastRoutieres = value.get('infrastRoutieres')
                                                    if infrastRoutieres.get('piste'):
                                                        datas[("MONOGRAPHIE", "Équipement et infrastructures", "Infrast routiéres/type", "Piste", "ind_25")][count] = infrastRoutieres.get('piste')
                                                        datas[("MONOGRAPHIE", "Équipement et infrastructures", "Équipement et infrastructures", "Toutes", "ind_26")][count] += "Piste ; " if infrastRoutieres.get('piste') == "Oui" else ""

                                            except:
                                                pass

                            count += 1


    if not os.path.exists("media/"+file_type+"/reports/excel_csv"):
        os.makedirs("media/"+file_type+"/reports/excel_csv")

    file_name = "reports_monographie_" + _type.lower() + "_" + (("reports_monographie".lower() + "_") if "reports_monographie" else "")

    if file_type == "csv":
        file_path = file_type+"/reports/excel_csv/" + file_name + str(datetime.today().replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_") +".csv"
        pd.DataFrame(datas, columns=cols).to_csv("media/"+file_path)
    else:
        file_path = file_type+"/reports/excel_csv/" + file_name + str(datetime.today().replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_") +".xlsx"
        pd.DataFrame(datas, columns=cols).to_excel("media/"+file_path)

    if platform == "win32":
        # windows
        return file_path.replace("/", "\\\\")
    else:
        return file_path
    
    



def get_existences_cvd_under_file_excel_or_csv(facilitator_db_name, file_type="excel", params={"type":"All", "id_administrativelevel":""}):
    nsc = NoSQLClient()

    _type = params.get("type")
    liste_villages = get_cascade_villages_by_administrative_level_id(params.get("id_administrativelevel"))
    if facilitator_db_name:
        fs = Facilitator.objects.filter(develop_mode=False, training_mode=False, no_sql_db_name=facilitator_db_name)
    else:
        fs = Facilitator.objects.filter(develop_mode=False, training_mode=False)

    d_cols = [ 
        ("MONOGRAPHIE", "N°", "N°", "N°", "ind_0"),
        ("MONOGRAPHIE", "LOCALITE", "Région", "Région", "ind_1"),
        ("MONOGRAPHIE", "LOCALITE", "Préfecture", "Préfecture", "ind_2"),
        ("MONOGRAPHIE", "LOCALITE", "Commune", "Commune", "ind_3"),
        ("MONOGRAPHIE", "LOCALITE", "Canton", "Canton", "ind_4"),
        ("MONOGRAPHIE", "LOCALITE", "CVD", "CVD", "ind_5"),
        ("MONOGRAPHIE", "LOCALITE", "Villages", "Villages", "ind_6"),
        ("MONOGRAPHIE", "LOCALITE", "Unité géographique", "Unité géographique", "ind_7"),
        ("MONOGRAPHIE", "LOCALITE", "Nom de l'AC", "Nom de l'AC", "ind_8"),
        ("MONOGRAPHIE", "LOCALITE", "Eff. Population", "Eff. Population", "ind_9"),
        ("MONOGRAPHIE", "LOCALITE", "Nbre total ménages dans le village", "Nbre total ménages dans le village", "ind_10"),

        ("MONOGRAPHIE", "Existence CVD", "Existence CVD", "Existence CVD", "ind_11"),

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
                            datas[("MONOGRAPHIE", "N°", "N°", "N°", "ind_0")][count] = count + 1
                            datas[("MONOGRAPHIE", "LOCALITE", "Région", "Région", "ind_1")][count] = administrativelevel_obj.parent.parent.parent.parent.name
                            datas[("MONOGRAPHIE", "LOCALITE", "Préfecture", "Préfecture", "ind_2")][count] = administrativelevel_obj.parent.parent.parent.name
                            datas[("MONOGRAPHIE", "LOCALITE", "Commune", "Commune", "ind_3")][count] = administrativelevel_obj.parent.parent.name
                            datas[("MONOGRAPHIE", "LOCALITE", "Canton", "Canton", "ind_4")][count] = administrativelevel_obj.parent.name
                            datas[("MONOGRAPHIE", "LOCALITE", "CVD", "CVD", "ind_5")][count] = administrativelevel_obj.cvd.name
                            datas[("MONOGRAPHIE", "LOCALITE", "Villages", "Villages", "ind_6")][count] = ";".join([o.name for o in administrativelevel_obj.cvd.get_villages()])
                            datas[("MONOGRAPHIE", "LOCALITE", "Unité géographique", "Unité géographique", "ind_7")][count] = administrativelevel_obj.geographical_unit.attributed_number_in_canton
                            datas[("MONOGRAPHIE", "LOCALITE", "Nom de l'AC", "Nom de l'AC", "ind_8")][count] = f.name
                            
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
                                            datas[("MONOGRAPHIE", "LOCALITE", "Eff. Population", "Eff. Population", "ind_9")][count] = value
                                            
                                            try:
                                                value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalHouseHolds"]
                                            except Exception as exc:
                                                value = None
                                            datas[("MONOGRAPHIE", "LOCALITE", "Nbre total ménages dans le village", "Nbre total ménages dans le village", "ind_10")][count] = value

                                        
                                        if _.get('sql_id') == 19: #Vérification de l'existence du CVD et de ses organes
                                            value = "N/A"
                                            try:
                                                value = get_datas_dict(form_response, "structuration", 1)["existenCVD"]
                                                value = value if value in ("Non", "Oui") else "N/A"
                                            except Exception as exc:
                                                pass
                                            
                                            datas[("MONOGRAPHIE", "Existence CVD", "Existence CVD", "Existence CVD", "ind_11")][count] = value

                            count += 1


    if not os.path.exists("media/"+file_type+"/reports/excel_csv"):
        os.makedirs("media/"+file_type+"/reports/excel_csv")

    file_name = "reports_existence_cvd_" + _type.lower() + "_" + (("reports_existence_cvd".lower() + "_") if "reports_existence_cvd" else "")

    if file_type == "csv":
        file_path = file_type+"/reports/excel_csv/" + file_name + str(datetime.today().replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_") +".csv"
        pd.DataFrame(datas, columns=cols).to_csv("media/"+file_path)
    else:
        file_path = file_type+"/reports/excel_csv/" + file_name + str(datetime.today().replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_") +".xlsx"
        pd.DataFrame(datas, columns=cols).to_excel("media/"+file_path)

    if platform == "win32":
        # windows
        return file_path.replace("/", "\\\\")
    else:
        return file_path
    
    
    


def get_village_priorities_under_file_excel_or_csv(facilitator_db_name, file_type="excel", params={"type":"All", "id_administrativelevel":""}):
    nsc = NoSQLClient()
    priorities_1_1, priorities_1_2_a, priorities_1_2_b, priorities_1_3 = [], {}, {}, []
    p_g_farmers_breeders_1_1, p_g_women_1_1, p_g_young_1_1, p_g_ethnic_minorities_1_1 = [], [], [], []
    p_g_farmers_breeders_vision_obstacles, p_g_women_vision_obstacles, p_g_young_vision_obstacles, p_g_ethnic_minorities_vision_obstacles = {}, {}, {}, {}
    priorites_village = []
    p_g_farmers_breeders_1_2_a, p_g_women_1_2_a, p_g_young_1_2_a, p_g_ethnic_minorities_1_2_a = {}, {}, {}, {}
    p_g_farmers_breeders_1_2_b, p_g_women_1_2_b, p_g_young_1_2_b, p_g_ethnic_minorities_1_2_b = {}, {}, {}, {}
    

    _type = params.get("type")
    liste_villages = get_cascade_villages_by_administrative_level_id(params.get("id_administrativelevel"))
    if facilitator_db_name:
        fs = Facilitator.objects.filter(develop_mode=False, training_mode=False, no_sql_db_name=facilitator_db_name)
    else:
        fs = Facilitator.objects.filter(develop_mode=False, training_mode=False)

    d_cols = [ 
        ("MONOGRAPHIE", "N°", "N°", "N°", "N°"),
        ("MONOGRAPHIE", "LOCALITE", "Région", "Région", "Région"),
        ("MONOGRAPHIE", "LOCALITE", "Préfecture", "Préfecture", "Préfecture"),
        ("MONOGRAPHIE", "LOCALITE", "Commune", "Commune", "Commune"),
        ("MONOGRAPHIE", "LOCALITE", "Canton", "Canton", "Canton"),
        ("MONOGRAPHIE", "LOCALITE", "CVD", "CVD", "CVD"),
        ("MONOGRAPHIE", "LOCALITE", "Villages", "Villages", "Villages"),
        ("MONOGRAPHIE", "LOCALITE", "Unité géographique", "Unité géographique", "Unité géographique"),
        ("MONOGRAPHIE", "LOCALITE", "Nom de l'AC", "Nom de l'AC", "Nom de l'AC"),
        ("MONOGRAPHIE", "LOCALITE", "Eff. Population", "Eff. Population", "Eff. Population"),
        ("MONOGRAPHIE", "LOCALITE", "Nbre total ménages dans le village", "Nbre total ménages dans le village", "Nbre total ménages dans le village"),

        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.1", "Les priorités du village", "Priorité 1", "Priorité"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.1", "Les priorités du village", "Priorité 1", "Cout estimé"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.1", "Les priorités du village", "Priorité 1", "Proposé par"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.1", "Les priorités du village", "Priorité 2", "Priorité"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.1", "Les priorités du village", "Priorité 2", "Cout estimé"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.1", "Les priorités du village", "Priorité 2", "Proposé par"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.1", "Les priorités du village", "Priorité 3", "Priorité"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.1", "Les priorités du village", "Priorité 3", "Cout estimé"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.1", "Les priorités du village", "Priorité 3", "Proposé par"),
        
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.1", "Les priorités du village", "Groupes", "Groupe des agriculteurs et eleveurs"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.1", "Les priorités du village", "Groupes", "Groupe des femmes"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.1", "Les priorités du village", "Groupes", "Groupe des jeunes"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.1", "Les priorités du village", "Groupes", "Groupe ethnique minoritaires"),
        
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2a", "SOUS-COMPOSANTE 1.2a", "SOUS-COMPOSANTE 1.2a", "Nom du marché le plus important du canton pour le village"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2a", "SOUS-COMPOSANTE 1.2a", "SOUS-COMPOSANTE 1.2a", "Lieu du marché le plus important du canton pour le village"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2a", "SOUS-COMPOSANTE 1.2a", "SOUS-COMPOSANTE 1.2a", "Quels types d'infrastructure/équipement la communauté souhaiterait-elle voir dans ce marché ?"),
        
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2a", "SOUS-COMPOSANTE 1.2a", "Groupes", "Groupe des agriculteurs et eleveurs (Nom et lieu du marché et types d'infrastructures)"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2a", "SOUS-COMPOSANTE 1.2a", "Groupes", "Groupe des femmes (Nom et lieu du marché et types d'infrastructures)"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2a", "SOUS-COMPOSANTE 1.2a", "Groupes", "Groupe des jeunes (Nom et lieu du marché et types d'infrastructures)"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2a", "SOUS-COMPOSANTE 1.2a", "Groupes", "Groupe ethnique minoritaires (Nom et lieu du marché et types d'infrastructures)"),
        
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "Les principaux groupements /coopératives du village qui sont liées au marche identifié en 1.2a"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "Quels sont les principaux besoins de ces groupes sociaux économiques (SE) du village ?"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "Quels sont leurs principaux besoins en renforcement de capacités et appuis à le restructuration (RCAR) ?"),
        
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "Groupes", "Groupe des agriculteurs et eleveurs (Les principaux groupes socioéconomiques du village qui sont liées au marche identifiée en 1.2a ?)"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "Groupes", "Groupe des agriculteurs et eleveurs (Quels sont les principaux besoins de ces groupes sociaux économiques (SE) du village ?)"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "Groupes", "Groupe des agriculteurs et eleveurs (Quels sont leurs principaux besoins en renforcement de capacités et appuis à le restructuration (RCAR) ?)"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "Groupes", "Groupe des femmes (Les principaux groupes socioéconomiques du village qui sont liées au marche identifiée en 1.2a ?)"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "Groupes", "Groupe des femmes (Quels sont les principaux besoins de ces groupes sociaux économiques (SE) du village ?)"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "Groupes", "Groupe des femmes (Quels sont leurs principaux besoins en renforcement de capacités et appuis à le restructuration (RCAR) ?)"),        
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "Groupes", "Groupe des jeunes (Les principaux groupes socioéconomiques du village qui sont liées au marche identifiée en 1.2a ?)"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "Groupes", "Groupe des jeunes (Quels sont les principaux besoins de ces groupes sociaux économiques (SE) du village ?)"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "Groupes", "Groupe des jeunes (Quels sont leurs principaux besoins en renforcement de capacités et appuis à le restructuration (RCAR) ?)"),      
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "Groupes", "Groupe ethnique minoritaires (Les principaux groupes socioéconomiques du village qui sont liées au marche identifiée en 1.2a ?)"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "Groupes", "Groupe ethnique minoritaires (Quels sont les principaux besoins de ces groupes sociaux économiques (SE) du village ?)"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "Groupes", "Groupe ethnique minoritaires (Quels sont leurs principaux besoins en renforcement de capacités et appuis à le restructuration (RCAR) ?)"),

        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.3", "Les priorités des jeunes du village", "Priorité 1", "Priorité"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.3", "Les priorités des jeunes du village", "Priorité 1", "Cout estimé"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.3", "Les priorités des jeunes du village", "Priorité 1", "Proposé par"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.3", "Les priorités des jeunes du village", "Priorité 2", "Priorité"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.3", "Les priorités des jeunes du village", "Priorité 2", "Cout estimé"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.3", "Les priorités des jeunes du village", "Priorité 2", "Proposé par"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.3", "Les priorités des jeunes du village", "Priorité 3", "Priorité"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.3", "Les priorités des jeunes du village", "Priorité 3", "Cout estimé"),
        ("MONOGRAPHIE", "SOUS-COMPOSANTE 1.3", "Les priorités des jeunes du village", "Priorité 3", "Proposé par"),
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
                            datas[("MONOGRAPHIE", "N°", "N°", "N°", "N°")][count] = count + 1
                            datas[("MONOGRAPHIE", "LOCALITE", "Région", "Région", "Région")][count] = administrativelevel_obj.parent.parent.parent.parent.name
                            datas[("MONOGRAPHIE", "LOCALITE", "Préfecture", "Préfecture", "Préfecture")][count] = administrativelevel_obj.parent.parent.parent.name
                            datas[("MONOGRAPHIE", "LOCALITE", "Commune", "Commune", "Commune")][count] = administrativelevel_obj.parent.parent.name
                            datas[("MONOGRAPHIE", "LOCALITE", "Canton", "Canton", "Canton")][count] = administrativelevel_obj.parent.name
                            datas[("MONOGRAPHIE", "LOCALITE", "CVD", "CVD", "CVD")][count] = administrativelevel_obj.cvd.name
                            datas[("MONOGRAPHIE", "LOCALITE", "Villages", "Villages", "Villages")][count] = ";".join([o.name for o in administrativelevel_obj.cvd.get_villages()])
                            datas[("MONOGRAPHIE", "LOCALITE", "Unité géographique", "Unité géographique", "Unité géographique")][count] = administrativelevel_obj.geographical_unit.attributed_number_in_canton
                            datas[("MONOGRAPHIE", "LOCALITE", "Nom de l'AC", "Nom de l'AC", "Nom de l'AC")][count] = f.name
                            
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
                                            datas[("MONOGRAPHIE", "LOCALITE", "Eff. Population", "Eff. Population", "Eff. Population")][count] = value
                                            
                                            try:
                                                value = get_datas_dict(form_response, "generalitiesSurVillage", 1)["totalHouseHolds"]
                                            except Exception as exc:
                                                value = None
                                            datas[("MONOGRAPHIE", "LOCALITE", "Nbre total ménages dans le village", "Nbre total ménages dans le village", "Nbre total ménages dans le village")][count] = value

                                        if _.get('sql_id') == 60: #Aidez les groupes du village à identifier la liste des obstacles et leur vision du développement pour leur village
                                            try:
                                                p_g_farmers_breeders_vision_obstacles = dict(get_datas_dict(form_response, "agriculteursEtEleveurs", 1))
                                            except:
                                                pass
                                            try:
                                                p_g_women_vision_obstacles = dict(get_datas_dict(form_response, "groupeDesFemmes", 1))
                                            except:
                                                pass
                                            try:
                                                p_g_young_vision_obstacles = dict(get_datas_dict(form_response, "groupeDesJeunes", 1))
                                            except:
                                                pass
                                            try:
                                                p_g_ethnic_minorities_vision_obstacles = dict(get_datas_dict(form_response, "groupeEthniqueMinoritaires", 1))
                                            except:
                                                pass

                                        if _.get('sql_id') == 44: #Identification et établissement de la liste des besoins prioritaires pour la composante 1.1  par groupe
                                            try:
                                                p_g_farmers_breeders_1_1 = list(get_datas_dict(form_response, "agriculteursEtEleveurs", 1)["besoinsPrioritairesDuGroupe"])
                                            except:
                                                p_g_farmers_breeders_1_1 = []
                                            try:
                                                p_g_women_1_1 = list(get_datas_dict(form_response, "groupeDesFemmes", 1)["besoinsPrioritairesDuGroupe"])
                                            except:
                                                p_g_women_1_1 = []
                                            try:
                                                p_g_young_1_1 = list(get_datas_dict(form_response, "groupeDesJeunes", 1)["besoinsPrioritairesDuGroupe"])
                                            except:
                                                p_g_young_1_1 = []
                                            try:
                                                p_g_ethnic_minorities_1_1 = list(get_datas_dict(form_response, "groupeEthniqueMinoritaires", 1)["besoinsPrioritairesDuGroupe"])
                                            except:
                                                p_g_ethnic_minorities_1_1 = []
                                            
                                            datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.1", "Les priorités du village", "Groupes", "Groupe des agriculteurs et eleveurs")][count] = ";".join([elt.get("besoinSelectionne") if elt.get("besoinSelectionne") != "Autre" else f'{elt.get("besoinSelectionne")} ({elt.get("siAutreVeuillezDecrire")})' for elt in p_g_farmers_breeders_1_1])
                                            datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.1", "Les priorités du village", "Groupes", "Groupe des femmes")][count] =  ";".join([elt.get("besoinSelectionne") if elt.get("besoinSelectionne") != "Autre" else f'{elt.get("besoinSelectionne")} ({elt.get("siAutreVeuillezDecrire")})' for elt in p_g_women_1_1])
                                            datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.1", "Les priorités du village", "Groupes", "Groupe des jeunes")][count] =  ";".join([elt.get("besoinSelectionne") if elt.get("besoinSelectionne") != "Autre" else f'{elt.get("besoinSelectionne")} ({elt.get("siAutreVeuillezDecrire")})' for elt in p_g_young_1_1])
                                            datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.1", "Les priorités du village", "Groupes", "Groupe ethnique minoritaires")][count] =  ";".join([elt.get("besoinSelectionne") if elt.get("besoinSelectionne") != "Autre" else f'{elt.get("besoinSelectionne")} ({elt.get("siAutreVeuillezDecrire")})' for elt in p_g_ethnic_minorities_1_1])
        
                                        if _.get('sql_id') == 57: #Identification et établissement de la liste des besoins prioritaires pour la sous - composante 1.2a  par groupe
                                            try:
                                                p_g_farmers_breeders_1_2_a = dict(get_datas_dict(form_response, "agriculteursEtEleveurs", 1))
                                            except:
                                                p_g_farmers_breeders_1_2_a = {}
                                            try:
                                                p_g_women_1_2_a = dict(get_datas_dict(form_response, "groupeDesFemmes", 1))
                                            except:
                                                p_g_women_1_2_a = {}
                                            try:
                                                p_g_young_1_2_a = dict(get_datas_dict(form_response, "groupeDesJeunes", 1))
                                            except:
                                                p_g_young_1_2_a = {}
                                            try:
                                                p_g_ethnic_minorities_1_2_a = dict(get_datas_dict(form_response, "groupeEthniqueMinoritaires", 1))
                                            except:
                                                p_g_ethnic_minorities_1_2_a = {}
                                            
                                            datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2a", "SOUS-COMPOSANTE 1.2a", "Groupes", "Groupe des agriculteurs et eleveurs (Nom et lieu du marché et types d'infrastructures)")][count] = f"{p_g_farmers_breeders_1_2_a.get('nomDuMarcheLePlusImportant')};{p_g_farmers_breeders_1_2_a.get('lieuDuMarcheLePlusImportant')};{';'.join([elt.get('typeDeDeveloppement') for elt in p_g_farmers_breeders_1_2_a.get('typesDeDeveloppementsInfrastructuresEtEquipements')]) if p_g_farmers_breeders_1_2_a.get('typesDeDeveloppementsInfrastructuresEtEquipements') else ''}"
                                            datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2a", "SOUS-COMPOSANTE 1.2a", "Groupes", "Groupe des femmes (Nom et lieu du marché et types d'infrastructures)")][count] = f"{p_g_women_1_2_a.get('nomDuMarcheLePlusImportant')};{p_g_women_1_2_a.get('lieuDuMarcheLePlusImportant')};{';'.join([elt.get('typeDeDeveloppement') for elt in p_g_women_1_2_a.get('typesDeDeveloppementsInfrastructuresEtEquipements')]) if p_g_women_1_2_a.get('typesDeDeveloppementsInfrastructuresEtEquipements') else ''}"
                                            datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2a", "SOUS-COMPOSANTE 1.2a", "Groupes", "Groupe des jeunes (Nom et lieu du marché et types d'infrastructures)")][count] = f"{p_g_young_1_2_a.get('nomDuMarcheLePlusImportant')};{p_g_young_1_2_a.get('lieuDuMarcheLePlusImportant')};{';'.join([elt.get('typeDeDeveloppement') for elt in p_g_young_1_2_a.get('typesDeDeveloppementsInfrastructuresEtEquipements')]) if p_g_young_1_2_a.get('typesDeDeveloppementsInfrastructuresEtEquipements') else ''}"
                                            datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2a", "SOUS-COMPOSANTE 1.2a", "Groupes", "Groupe ethnique minoritaires (Nom et lieu du marché et types d'infrastructures)")][count] = f"{p_g_ethnic_minorities_1_2_a.get('nomDuMarcheLePlusImportant')};{p_g_ethnic_minorities_1_2_a.get('lieuDuMarcheLePlusImportant')};{';'.join([elt.get('typeDeDeveloppement') for elt in p_g_ethnic_minorities_1_2_a.get('typesDeDeveloppementsInfrastructuresEtEquipements')]) if p_g_ethnic_minorities_1_2_a.get('typesDeDeveloppementsInfrastructuresEtEquipements') else ''}"
        
                                        if _.get('sql_id') == 58: #Identification et établissement de la liste des besoins prioritaires pour la composante 1.2b  par groupe
                                            try:
                                                p_g_farmers_breeders_1_2_b = dict(get_datas_dict(form_response, "agriculteursEtEleveurs", 1))
                                            except:
                                                p_g_farmers_breeders_1_2_b = {}
                                            try:
                                                p_g_women_1_2_b = dict(get_datas_dict(form_response, "groupeDesFemmes", 1))
                                            except:
                                                p_g_women_1_2_b = {}
                                            try:
                                                p_g_young_1_2_b = dict(get_datas_dict(form_response, "groupeDesJeunes", 1))
                                            except:
                                                p_g_young_1_2_b = {}
                                            try:
                                                p_g_ethnic_minorities_1_2_b = dict(get_datas_dict(form_response, "groupeEthniqueMinoritaires", 1))
                                            except:
                                                p_g_ethnic_minorities_1_2_b = {}
                                            
                                            datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "Groupes", "Groupe des agriculteurs et eleveurs (Les principaux groupes socioéconomiques du village qui sont liées au marche identifiée en 1.2a ?)")][count] = ';'.join([elt.get('principalGroupeSocioeconomique') for elt in p_g_farmers_breeders_1_2_b.get('principauxGroupesSocioeconomiques')]) if p_g_farmers_breeders_1_2_b.get('principauxGroupesSocioeconomiques') else ''
                                            datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "Groupes", "Groupe des agriculteurs et eleveurs (Quels sont les principaux besoins de ces groupes sociaux économiques (SE) du village ?)")][count] = ';'.join([elt.get('besoin') for elt in p_g_farmers_breeders_1_2_b.get('principauxbesoinsSociauxEconomiques')]) if p_g_farmers_breeders_1_2_b.get('principauxbesoinsSociauxEconomiques') else ''
                                            datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "Groupes", "Groupe des agriculteurs et eleveurs (Quels sont leurs principaux besoins en renforcement de capacités et appuis à le restructuration (RCAR) ?)")][count] = ';'.join([elt.get('besoin') for elt in p_g_farmers_breeders_1_2_b.get('principauxBesoinsEnRenforcementDeCapacites')]) if p_g_farmers_breeders_1_2_b.get('principauxBesoinsEnRenforcementDeCapacites') else ''
                                            datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "Groupes", "Groupe des femmes (Les principaux groupes socioéconomiques du village qui sont liées au marche identifiée en 1.2a ?)")][count] = ';'.join([elt.get('principalGroupeSocioeconomique') for elt in p_g_women_1_2_b.get('principauxGroupesSocioeconomiques')]) if p_g_women_1_2_b.get('principauxGroupesSocioeconomiques') else ''
                                            datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "Groupes", "Groupe des femmes (Quels sont les principaux besoins de ces groupes sociaux économiques (SE) du village ?)")][count] = ';'.join([elt.get('besoin') for elt in p_g_women_1_2_b.get('principauxbesoinsSociauxEconomiques')]) if p_g_women_1_2_b.get('principauxbesoinsSociauxEconomiques') else ''
                                            datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "Groupes", "Groupe des femmes (Quels sont leurs principaux besoins en renforcement de capacités et appuis à le restructuration (RCAR) ?)")][count] = ';'.join([elt.get('besoin') for elt in p_g_women_1_2_b.get('principauxBesoinsEnRenforcementDeCapacites')]) if p_g_women_1_2_b.get('principauxBesoinsEnRenforcementDeCapacites') else ''
                                            datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "Groupes", "Groupe des jeunes (Les principaux groupes socioéconomiques du village qui sont liées au marche identifiée en 1.2a ?)")][count] = ';'.join([elt.get('principalGroupeSocioeconomique') for elt in p_g_young_1_2_b.get('principauxGroupesSocioeconomiques')]) if p_g_young_1_2_b.get('principauxGroupesSocioeconomiques') else ''
                                            datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "Groupes", "Groupe des jeunes (Quels sont les principaux besoins de ces groupes sociaux économiques (SE) du village ?)")][count] = ';'.join([elt.get('besoin') for elt in p_g_young_1_2_b.get('principauxbesoinsSociauxEconomiques')]) if p_g_young_1_2_b.get('principauxbesoinsSociauxEconomiques') else ''
                                            datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "Groupes", "Groupe des jeunes (Quels sont leurs principaux besoins en renforcement de capacités et appuis à le restructuration (RCAR) ?)")][count] = ';'.join([elt.get('besoin') for elt in p_g_young_1_2_b.get('principauxBesoinsEnRenforcementDeCapacites')]) if p_g_young_1_2_b.get('principauxBesoinsEnRenforcementDeCapacites') else ''
                                            datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "Groupes", "Groupe ethnique minoritaires (Les principaux groupes socioéconomiques du village qui sont liées au marche identifiée en 1.2a ?)")][count] = ';'.join([elt.get('principalGroupeSocioeconomique') for elt in p_g_ethnic_minorities_1_2_b.get('principauxGroupesSocioeconomiques')]) if p_g_ethnic_minorities_1_2_b.get('principauxGroupesSocioeconomiques') else ''
                                            datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "Groupes", "Groupe ethnique minoritaires (Quels sont les principaux besoins de ces groupes sociaux économiques (SE) du village ?)")][count] = ';'.join([elt.get('besoin') for elt in p_g_ethnic_minorities_1_2_b.get('principauxbesoinsSociauxEconomiques')]) if p_g_ethnic_minorities_1_2_b.get('principauxbesoinsSociauxEconomiques') else ''
                                            datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "Groupes", "Groupe ethnique minoritaires (Quels sont leurs principaux besoins en renforcement de capacités et appuis à le restructuration (RCAR) ?)")][count] = ';'.join([elt.get('besoin') for elt in p_g_ethnic_minorities_1_2_b.get('principauxBesoinsEnRenforcementDeCapacites')]) if p_g_ethnic_minorities_1_2_b.get('principauxBesoinsEnRenforcementDeCapacites') else ''
                                            
                                        if _.get('sql_id') == 59: #Soutenir la communauté dans la sélection des priorités par sous-composante (1.1, 1.2 et 1.3) à soumettre à la discussion du CCD lors de la réunion cantonale d'arbitrage
                                            try:
                                                priorites_village = list(get_datas_dict(form_response, "sousComposante11", 1)["prioritesDuVillage"])
                                            except:
                                                priorites_village = []
                                            _i = 1
                                            for p in priorites_village:
                                                datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.1", "Les priorités du village", f"Priorité {_i}", "Priorité")][count] = p.get("priorite") if p.get("priorite") != "Autre" else f'{p.get("priorite")} ({p.get("siAutreVeuillezDecrire")})'
                                                datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.1", "Les priorités du village", f"Priorité {_i}", "Cout estimé")][count] = p.get("coutEstime")
                                                datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.1", "Les priorités du village", f"Priorité {_i}", "Proposé par")][count] = p.get("proposePar")
                                                _i += 1
                                                if _i >= 4:
                                                    break
                                                                         
                                            try:
                                                priorities_1_2_a = dict(get_datas_dict(form_response, "sousComposante12a", 1))
                                            except:
                                                priorities_1_2_a = {}
                                            datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2a", "SOUS-COMPOSANTE 1.2a", "SOUS-COMPOSANTE 1.2a", "Nom du marché le plus important du canton pour le village")][count] = priorities_1_2_a.get("nomDuMarcheLePlusImportant")
                                            datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2a", "SOUS-COMPOSANTE 1.2a", "SOUS-COMPOSANTE 1.2a", "Lieu du marché le plus important du canton pour le village")][count] = priorities_1_2_a.get("lieuDuMarcheLePlusImportant")
                                            datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2a", "SOUS-COMPOSANTE 1.2a", "SOUS-COMPOSANTE 1.2a", "Quels types d'infrastructure/équipement la communauté souhaiterait-elle voir dans ce marché ?")][count] = ";".join([elt.get("typeDeDeveloppement") for elt in priorities_1_2_a.get("typesInfrastructuresEtEquipements")]) if priorities_1_2_a.get("typesInfrastructuresEtEquipements") else ''
        
                                            try:
                                                priorities_1_2_b = dict(get_datas_dict(form_response, "sousComposante12b", 1))
                                            except:
                                                priorities_1_2_b = {}
                                            
                                            datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "Les principaux groupements /coopératives du village qui sont liées au marche identifié en 1.2a")][count] = ";".join([elt.get("principalGroupeSocioeconomique") for elt in priorities_1_2_b.get("principauxGroupesSocioeconomiques")]) if priorities_1_2_b.get("principauxGroupesSocioeconomiques") else ''
                                            datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "Quels sont les principaux besoins de ces groupes sociaux économiques (SE) du village ?")][count] = ";".join([elt.get("besoin") for elt in priorities_1_2_b.get("principauxbesoinsSociauxEconomiques")]) if priorities_1_2_b.get("principauxbesoinsSociauxEconomiques") else ''
                                            datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "SOUS-COMPOSANTE 1.2b", "Quels sont leurs principaux besoins en renforcement de capacités et appuis à le restructuration (RCAR) ?")][count] = ";".join([elt.get("besoin") for elt in priorities_1_2_b.get("principauxBesoinsEnRenforcementDeCapacites")]) if priorities_1_2_b.get("principauxBesoinsEnRenforcementDeCapacites") else ''
                                            
                                            try:
                                                priorities_1_3 = list(get_datas_dict(form_response, "sousComposante13", 1)["classement"])
                                            except:
                                                priorities_1_3 = []
                                            _i = 1
                                            for p in priorities_1_3:
                                                datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.3", "Les priorités des jeunes du village", f"Priorité {_i}", "Priorité")][count] =  p.get("priorite") if p.get("priorite") != "Autre" else f'{p.get("priorite")} ({p.get("siAutreVeuillezDecrire")})'
                                                datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.3", "Les priorités des jeunes du village", f"Priorité {_i}", "Cout estimé")][count] = p.get("coutEstime")
                                                datas[("MONOGRAPHIE", "SOUS-COMPOSANTE 1.3", "Les priorités des jeunes du village", f"Priorité {_i}", "Proposé par")][count] = p.get("proposePar")
                                                _i += 1
                                                if _i >= 4:
                                                    break
                            count += 1


    if not os.path.exists("media/"+file_type+"/reports/excel_csv"):
        os.makedirs("media/"+file_type+"/reports/excel_csv")

    file_name = "reports_villages_priorities_" + _type.lower() + "_" + (("reports_villages_priorities".lower() + "_") if "reports_villages_priorities" else "")

    if file_type == "csv":
        file_path = file_type+"/reports/excel_csv/" + file_name + str(datetime.today().replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_") +".csv"
        pd.DataFrame(datas, columns=cols).to_csv("media/"+file_path)
    else:
        file_path = file_type+"/reports/excel_csv/" + file_name + str(datetime.today().replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_") +".xlsx"
        pd.DataFrame(datas, columns=cols).to_excel("media/"+file_path)

    if platform == "win32":
        # windows
        return file_path.replace("/", "\\\\")
    else:
        return file_path