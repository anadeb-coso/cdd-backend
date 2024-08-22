from administrativelevels import models as administrativelevels_models

def get_cascade_administrative_levels_by_administrative_level_id(_id):
    
    if _id and _id not in (1, "1"): #1 == Country
        ad_obj = administrativelevels_models.AdministrativeLevel.objects.using('mis').get(id=int(_id))

        ads = ad_obj.administrativelevel_set.get_queryset()
        _type = ad_obj.type

        if _type == "Region":
            regions = [ad_obj]
            prefectures = ads
            communes = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(parent_id__in=[o.id for o in prefectures])
            cantons = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(parent_id__in=[o.id for o in communes])
            villages = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(parent_id__in=[o.id for o in cantons])
        elif _type == "Prefecture":
            communes = ads
            cantons = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(parent_id__in=[o.id for o in communes])
            villages = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(parent_id__in=[o.id for o in cantons])
        elif _type == "Commune":
            cantons = ads
            villages = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(parent_id__in=[o.id for o in cantons])
        elif _type == "Canton":
            cantons = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(id=ad_obj.id)
            villages = ads
        elif _type == "Village":
            cantons = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(id=(ad_obj.parent.id if ad_obj.parent else 0))
            villages = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(id=ad_obj.id)
        else:
            cantons = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Canton")
            villages = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Village")
    elif _id and _id in (1, "1"):
        cantons = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Canton")
        villages = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Village")
    else:
        cantons = []
        villages = []
        
    return list(cantons.order_by("name")) , list(villages.order_by("name"))



def get_object_by_type_and_object(_type, obj):
    if obj:
        if obj.type == _type:
            return obj
        return get_object_by_type_and_object(_type, obj.parent)
    return None
