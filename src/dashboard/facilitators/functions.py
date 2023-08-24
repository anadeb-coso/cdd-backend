from no_sql_client import NoSQLClient
from administrativelevels import models as administrativelevels_models

def get_cvds(facilitator):
    administrative_levels = facilitator['administrative_levels']
    geographical_units = facilitator.get('geographical_units')

    CVDs = []
    if geographical_units:
        for index in range(len(geographical_units)) :
            element = geographical_units[index]
            for i in range(len(element["cvd_groups"])):
                elt = element["cvd_groups"][i]
                
                cvd_obj = administrativelevels_models.CVD.objects.using('mis').filter(id=int(elt['sql_id'])).first()
                if cvd_obj and not '(' in cvd_obj.name:
                    elt['cvd_name'] = f'{cvd_obj.name} ({cvd_obj.get_canton()})'
                else:
                    elt['cvd_name'] = cvd_obj.name
                
                villages = []
                for _index in range(len(administrative_levels)):
                    adl = administrative_levels[_index]
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
                print(doc)
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
                
        
            