

def get_cvds(facilitator):
    administrative_levels = facilitator['administrative_levels']
    geographical_units = facilitator.get('geographical_units')

    CVDs = []
    if geographical_units:
        for index in range(len(geographical_units)) :
            element = geographical_units[index]
            for i in range(len(element["cvd_groups"])):
                elt = element["cvd_groups"][i]
                villages = []
                for _index in range(len(administrative_levels)):
                    if elt.get('villages') and administrative_levels[_index]['id'] in elt['villages']:
                        
                        _in_list = False
                        for v in villages:
                            if administrative_levels[_index]['id'] == v['id']:
                                _in_list = True
                        if not _in_list:
                            villages.append(administrative_levels[_index])

                            if administrative_levels[_index].get('is_headquarters_village'):
                                elt['village'] = administrative_levels[_index]
                                elt['village_id'] = administrative_levels[_index]['id']
                
                # elt['village'] = villages[0] if len(villages) != 0 else None
                # elt['village_id'] = villages[0]['id'] if len(villages) != 0 else None
                
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