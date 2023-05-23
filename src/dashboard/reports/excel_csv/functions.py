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
    
