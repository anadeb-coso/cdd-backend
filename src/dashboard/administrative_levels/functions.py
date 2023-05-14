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

def get_cascade_administrative_levels_by_administrative_level_id(_id):
    datas = {}
    
    if _id:
        ad_obj = administrativelevels_models.AdministrativeLevel.objects.using('mis').get(id=int(_id))

        ads = ad_obj.administrativelevel_set.get_queryset()
        _type = ad_obj.type

        if _type == "Region":
            # regions = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Region")
            prefectures = ads
            communes = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(parent_id__in=[o.id for o in prefectures])
            cantons = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(parent_id__in=[o.id for o in communes])
            villages = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(parent_id__in=[o.id for o in cantons])
        elif _type == "Prefecture":
            # regions = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Region")
            prefectures = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Prefecture")
            communes = ads
            cantons = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(parent_id__in=[o.id for o in communes])
            villages = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(parent_id__in=[o.id for o in cantons])
        elif _type == "Commune":
            # regions = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Region")
            prefectures = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Prefecture")
            communes = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Commune")
            cantons = ads
            villages = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(parent_id__in=[o.id for o in cantons])
        elif _type == "Canton":
            # regions = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Region")
            prefectures = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Prefecture")
            communes = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Commune")
            cantons = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Canton")
            villages = ads
        elif _type == "Village":
            # regions = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Region")
            prefectures = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Prefecture")
            communes = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Commune")
            cantons = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Canton")
            villages = ad_obj.parent.administrativelevel_set.get_queryset()
        else:
            prefectures = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Prefecture")
            communes = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Commune")
            cantons = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Canton")
            villages = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Village")
    else:
        prefectures = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Prefecture")
        communes = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Commune")
        cantons = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Canton")
        villages = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Village")


        # datas = {
        #     "prefectures": ads if _type == "Region" else [], 
        #     "communes": ads if _type == "Prefecture" else [], 
        #     "cantons": ads if _type == "Commune" else [], 
        #     "villages": ads if _type == "Canton" else []
        # }
        # for p in datas["prefectures"]:
        #     [datas["communes"].append(o) for o in p.administrativelevel_set.get_queryset()]

        # for c in datas["communes"]:
        #     [datas["cantons"].append(o) for o in c.administrativelevel_set.get_queryset()]
        
        # for c in datas["cantons"]:
        #     [datas["villages"].append(o) for o in c.administrativelevel_set.get_queryset()]
        # datas["prefectures"] = get_administrative_levels_under_json(datas["prefectures"])
        # datas["communes"] = get_administrative_levels_under_json(datas["communes"])
        # datas["cantons"] = get_administrative_levels_under_json(datas["cantons"])
        # datas["villages"] = get_administrative_levels_under_json(datas["villages"])
        
        
    datas["prefectures"] = get_administrative_levels_under_json(prefectures)
    datas["communes"] = get_administrative_levels_under_json(communes)
    datas["cantons"] = get_administrative_levels_under_json(cantons)
    datas["villages"] = get_administrative_levels_under_json(villages)


    return datas