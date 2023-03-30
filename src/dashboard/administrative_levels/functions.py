

def get_administrative_level_under_json(administrative_levels):
    datas = []
    for adm_obj in administrative_levels:
        datas.append({
            "administrative_id": str(adm_obj.id),
            "name": str(adm_obj.name)
        })
        
    return datas