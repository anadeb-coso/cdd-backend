from administrativelevels import models as administrativelevels_models
from assignments.models import AssignAdministrativeLevelToFacilitator
from dashboard.facilitators.repository.db_facilitator_repository import FacilitatorRepository
from dashboard.facilitators.repository.facilitator_criteria import FacilitatorCriteria
from subprojects.models import Project as MisProject
from cdd.call_objects_from_other_db import mis_objects_call


def get_administrative_level_under_json(administrative_level):
    if administrative_level:
        return {
            "administrative_id": str(administrative_level.id),
            "name": str(administrative_level.name),
            "id": administrative_level.id, 
            "parent": administrative_level.parent.id if administrative_level.parent else None, 
            "type": administrative_level.type 
        }
        
    return None

def get_administrative_levels_under_json(administrative_levels):
    datas = []
    for adm_obj in administrative_levels:
        datas.append(get_administrative_level_under_json(adm_obj))
        
    return datas



def get_cascade_villages_by_administrative_level_id(_ids):
    
    if type(_ids) is not list:
        _ids = [_ids]

    if '' in _ids:
        del _ids[_ids.index('')]
    if None in _ids:
        del _ids[_ids.index(None)]
        
    if _ids:
        ad_objects = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(id__in=[int(_id) for _id in _ids if _id])
        
        villages = []
        for ad_obj in ad_objects:
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
                villages += datas["villages"]

        return get_administrative_levels_under_json(list(set(villages)))
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




def get_cascade_administrative_levels_by_administrative_level_ids(_ids, request=None):
    datas = {}
    if type(_ids) is not list:
        _ids = [_ids]
    
    if '' in _ids:
        del _ids[_ids.index('')]
    if None in _ids:
        del _ids[_ids.index(None)]

    _ids = [int(_id) for _id in _ids if _id if str(_id).isdigit()]

    if _ids:
        ad_objects = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(id__in=_ids)

        ads = []
        for ad_obj in ad_objects:
            ads += list(ad_obj.administrativelevel_set.get_queryset())
        _type = ad_objects[0].type

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
            villages = ad_objects
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

        
    datas["prefectures"] = get_administrative_levels_under_json(prefectures)
    datas["communes"] = get_administrative_levels_under_json(communes)
    datas["cantons"] = get_administrative_levels_under_json(cantons)
    datas["villages"] = get_administrative_levels_under_json(villages)

    if request:
        project_mis = mis_objects_call.filter_objects(MisProject, name=request.session.get('project_name'))
        project_mis_id = project_mis.first().id if project_mis.count() >= 1 else 1
        
        if datas["villages"]:
            assign_facilitators = AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(
                administrative_level_id__in=[str(v['administrative_id']) for v in datas["villages"]],
                project_id=project_mis_id,
                activated=True
            )
            criteria = FacilitatorCriteria(
                id__in=list(set([int(f.facilitator_id) for f in assign_facilitators])),
                develop_mode=False,
                training_mode=False,
                projects__id=[request.session.get('project_id')]
            )

        else:
            criteria = FacilitatorCriteria(
                develop_mode=False,
                training_mode=False,
                projects__id=[request.session.get('project_id')]
            )
        fs = FacilitatorRepository().find_by_criteria(criteria=criteria)
        
        _facilitators = [('', '')]
        datas["facilitators"] = [{'id': o.no_sql_db_name, 'name': o.name if o.name else o.username} for o in fs.order_by("name", "username")]
        
    return datas