from administrativelevels import models as administrativelevels_models


def get_administrative_level_under_json(administrative_level):
    if administrative_level:
        return {
            "administrative_id": str(administrative_level.id),
            "name": str(administrative_level.name)
        }
        
    return None

def get_administrative_levels_under_json(administrative_levels):
    datas = []
    for adm_obj in administrative_levels:
        datas.append(get_administrative_level_under_json(adm_obj))
        
    return datas



def get_cascade_villages_by_administrative_level_id(_id):
    if _id:
        ad_obj = administrativelevels_models.AdministrativeLevel.objects.using('mis').get(id=int(_id))
        
        if ad_obj:
            ads = []
            _type = ad_obj.type
            if _type == "Village":
                ads.append(ad_obj)
            else:
                ads = ad_obj.administrativelevel_set.get_queryset()
                
            datas = {
                "prefectures": ads if _type == "Region" else [], 
                "communes": ads if _type == "Prefecture" else [], 
                "cantons": ads if _type == "Commune" else [], 
                "villages": ads if _type in ("Canton", "Village") else []
            }
            for p in datas["prefectures"]:
                [datas["communes"].append(o) for o in p.administrativelevel_set.get_queryset()]

            for c in datas["communes"]:
                [datas["cantons"].append(o) for o in c.administrativelevel_set.get_queryset()]
            
            for c in datas["cantons"]:
                [datas["villages"].append(o) for o in c.administrativelevel_set.get_queryset()]
            
            if _type == "village":
                datas["villages"].append(ad_obj)

            return get_administrative_levels_under_json(datas["villages"])
    return []