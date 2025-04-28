import logging
from django.db.models import Q

from administrativelevels import models as administrativelevels_models
from assignments.models import AssignAdministrativeLevelToFacilitator
from dashboard.facilitators.repository.db_facilitator_repository import FacilitatorRepository
from dashboard.facilitators.repository.facilitator_criteria import FacilitatorCriteria
from subprojects.models import Project as MisProject
from cdd.call_objects_from_other_db import mis_objects_call


# Créer un logger pour le débogage
logger = logging.getLogger(__name__)


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
    # Nettoyage et filtrage des IDs
    if not isinstance(_ids, list):
        _ids = [_ids]

    _ids = list(filter(None, _ids))  # Supprime les '' et None

    if _ids:
        # Récupération des objets administratifs en une seule requête
        ad_objects = administrativelevels_models.AdministrativeLevel.objects.using('mis')\
            .filter(id__in=_ids)\
            .prefetch_related('administrativelevel_set')

        villages = set()

        for ad_obj in ad_objects:
            _type = ad_obj.type
            ads = set()

            if _type == "Village":
                ads.add(ad_obj)
            else:
                ads.update(ad_obj.administrativelevel_set.all())

            # Dictionnaire des niveaux administratifs
            datas = {
                "prefectures": ads if _type == "Region" else set(), 
                "communes": ads if _type == "Prefecture" else set(), 
                "cantons": ads if _type == "Commune" else set(), 
                "villages": ads if _type in ("Canton", "Village") else set()
            }

            # Construction de la hiérarchie avec une boucle optimisée
            for p in datas["prefectures"]:
                datas["communes"].update(p.administrativelevel_set.all())

            for c in datas["communes"]:
                datas["cantons"].update(c.administrativelevel_set.all())

            for c in datas["cantons"]:
                datas["villages"].update(c.administrativelevel_set.all())

            if _type == "Village":
                datas["villages"].add(ad_obj)

            villages.update(datas["villages"])

        return get_administrative_levels_under_json(list(villages))

    return []
# def get_cascade_villages_by_administrative_level_id(_ids):
    
#     if type(_ids) is not list:
#         _ids = [_ids]

#     if '' in _ids:
#         del _ids[_ids.index('')]
#     if None in _ids:
#         del _ids[_ids.index(None)]
        
#     if _ids:
#         ad_objects = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(id__in=[int(_id) for _id in _ids if _id])
        
#         villages = []
#         for ad_obj in ad_objects:
#             if ad_obj:
#                 ads = []
#                 _type = ad_obj.type
#                 if _type == "Village":
#                     ads.append(ad_obj)
#                 else:
#                     ads = ad_obj.administrativelevel_set.get_queryset()
                    
#                 datas = {
#                     "prefectures": ads if _type == "Region" else [], 
#                     "communes": ads if _type == "Prefecture" else [], 
#                     "cantons": ads if _type == "Commune" else [], 
#                     "villages": ads if _type in ("Canton", "Village") else []
#                 }
#                 for p in datas["prefectures"]:
#                     [datas["communes"].append(o) for o in p.administrativelevel_set.get_queryset()]

#                 for c in datas["communes"]:
#                     [datas["cantons"].append(o) for o in c.administrativelevel_set.get_queryset()]
                
#                 for c in datas["cantons"]:
#                     [datas["villages"].append(o) for o in c.administrativelevel_set.get_queryset()]
                
#                 if _type == "village":
#                     datas["villages"].append(ad_obj)
#                 villages += datas["villages"]

#         return get_administrative_levels_under_json(list(set(villages)))
#     return []


def get_cascade_administrative_levels_by_administrative_level_id(_id):
    datas = {}

    # Préchargement des objets pour limiter le nombre de requêtes SQL
    admin_levels = administrativelevels_models.AdministrativeLevel.objects.using('mis')\
        .select_related('parent')\
        .prefetch_related('administrativelevel_set')

    # Si un ID est fourni, on récupère l'objet correspondant
    ad_obj = None
    if _id:
        try:
            ad_obj = admin_levels.get(id=int(_id))
        except administrativelevels_models.AdministrativeLevel.DoesNotExist:
            return {"error": "ID non trouvé"}  # Optionnel : Gérer le cas d'un ID inexistant

    # Dictionnaire des types d'entités
    level_types = ["Prefecture", "Commune", "Canton", "Village"]

    # Initialisation des ensembles pour stocker les objets filtrés
    levels = {level: set() for level in level_types}

    if ad_obj:
        _type = ad_obj.type
        children = set(ad_obj.administrativelevel_set.all())

        # Construction des niveaux administratifs selon le type
        if _type == "Region":
            levels["Prefecture"] = children
            levels["Commune"] = {o for p in children for o in p.administrativelevel_set.all()}
            levels["Canton"] = {o for c in levels["Commune"] for o in c.administrativelevel_set.all()}
            levels["Village"] = {o for v in levels["Canton"] for o in v.administrativelevel_set.all()}

        elif _type == "Prefecture":
            levels["Prefecture"] = admin_levels.filter(type="Prefecture")
            levels["Commune"] = children
            levels["Canton"] = {o for c in children for o in c.administrativelevel_set.all()}
            levels["Village"] = {o for v in levels["Canton"] for o in v.administrativelevel_set.all()}

        elif _type == "Commune":
            levels["Prefecture"] = admin_levels.filter(type="Prefecture")
            levels["Commune"] = admin_levels.filter(type="Commune")
            levels["Canton"] = children
            levels["Village"] = {o for v in children for o in v.administrativelevel_set.all()}

        elif _type == "Canton":
            levels["Prefecture"] = admin_levels.filter(type="Prefecture")
            levels["Commune"] = admin_levels.filter(type="Commune")
            levels["Canton"] = admin_levels.filter(type="Canton")
            levels["Village"] = children

        elif _type == "Village":
            levels["Prefecture"] = admin_levels.filter(type="Prefecture")
            levels["Commune"] = admin_levels.filter(type="Commune")
            levels["Canton"] = admin_levels.filter(type="Canton")
            levels["Village"] = {ad_obj.parent} if ad_obj.parent else set()
    else:
        # Cas où aucun ID n'est fourni
        for level in level_types:
            levels[level] = admin_levels.filter(type=level)

    # Conversion en JSON
    for key, value in levels.items():
        datas[key.lower() + "s"] = get_administrative_levels_under_json(value)

    return datas
# def get_cascade_administrative_levels_by_administrative_level_id(_id):
#     datas = {}
    
#     if _id:
#         ad_obj = administrativelevels_models.AdministrativeLevel.objects.using('mis').get(id=int(_id))

#         ads = ad_obj.administrativelevel_set.get_queryset()
#         _type = ad_obj.type

#         if _type == "Region":
#             # regions = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Region")
#             prefectures = ads
#             communes = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(parent_id__in=[o.id for o in prefectures])
#             cantons = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(parent_id__in=[o.id for o in communes])
#             villages = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(parent_id__in=[o.id for o in cantons])
#         elif _type == "Prefecture":
#             # regions = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Region")
#             prefectures = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Prefecture")
#             communes = ads
#             cantons = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(parent_id__in=[o.id for o in communes])
#             villages = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(parent_id__in=[o.id for o in cantons])
#         elif _type == "Commune":
#             # regions = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Region")
#             prefectures = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Prefecture")
#             communes = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Commune")
#             cantons = ads
#             villages = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(parent_id__in=[o.id for o in cantons])
#         elif _type == "Canton":
#             # regions = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Region")
#             prefectures = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Prefecture")
#             communes = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Commune")
#             cantons = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Canton")
#             villages = ads
#         elif _type == "Village":
#             # regions = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Region")
#             prefectures = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Prefecture")
#             communes = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Commune")
#             cantons = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Canton")
#             villages = ad_obj.parent.administrativelevel_set.get_queryset()
#         else:
#             prefectures = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Prefecture")
#             communes = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Commune")
#             cantons = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Canton")
#             villages = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Village")
#     else:
#         prefectures = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Prefecture")
#         communes = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Commune")
#         cantons = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Canton")
#         villages = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Village")
        
#     datas["prefectures"] = get_administrative_levels_under_json(prefectures)
#     datas["communes"] = get_administrative_levels_under_json(communes)
#     datas["cantons"] = get_administrative_levels_under_json(cantons)
#     datas["villages"] = get_administrative_levels_under_json(villages)

#     return datas




def get_cascade_administrative_levels_by_administrative_level_ids(_ids, request=None):
    datas = {}

    # Assurer que _ids est une liste
    if type(_ids) is not list:
        _ids = [_ids]
    
    # Nettoyer les éléments vides et None
    _ids = list(filter(lambda x: x and str(x).isdigit(), _ids))

    # Si _ids est vide, retourner une liste vide
    if not _ids:
        return {"error": "Aucun ID valide fourni"}

    try:
        # Rechercher les objets administratifs pour ces IDs
        ad_objects = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(id__in=_ids)
        if not ad_objects.exists():
            return {"error": "Aucun niveau administratif trouvé pour ces IDs"}

        ads = []
        for ad_obj in ad_objects:
            ads += list(ad_obj.administrativelevel_set.get_queryset())
        
        _type = ad_objects[0].type  # Utiliser le type du premier objet trouvé

        # Définir les filtres en fonction du type d'ID
        filters = {
            "Region": {
                "prefectures": ads, 
                "communes": "parent_id__in=[o.id for o in ads]",
                "cantons": "parent_id__in=[o.id for o in communes]",
                "villages": "parent_id__in=[o.id for o in cantons]",
            },
            "Prefecture": {
                "prefectures": "type=Prefecture",
                "communes": ads,
                "cantons": "parent_id__in=[o.id for o in communes]",
                "villages": "parent_id__in=[o.id for o in cantons]",
            },
            "Commune": {
                "prefectures": "type=Prefecture",
                "communes": "type=Commune",
                "cantons": ads,
                "villages": "parent_id__in=[o.id for o in cantons]",
            },
            "Canton": {
                "prefectures": "type=Prefecture",
                "communes": "type=Commune",
                "cantons": "type=Canton",
                "villages": ads,
            },
            "Village": {
                "prefectures": "type=Prefecture",
                "communes": "type=Commune",
                "cantons": "type=Canton",
                "villages": ad_objects,
            }
        }

        # Appliquer les filtres pour obtenir les niveaux administratifs
        levels = filters.get(_type, {
            "prefectures": "type=Prefecture",
            "communes": "type=Commune",
            "cantons": "type=Canton",
            "villages": "type=Village",
        })

        for key, query in levels.items():
            datas[key] = get_administrative_levels_under_json(
                administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(eval(query))
            )

        # Si un projet est spécifié dans la session, ajouter les facilitateurs
        if request:
            project_id = request.session.get('project_id')
            if not project_id:
                logger.warning(f"Projet non trouvé dans la session pour l'ID {request.session.get('project_mis_id')}")
                return {"error": "Projet non trouvé dans la session"}
            
            project_mis = mis_objects_call.filter_objects(MisProject, name=request.session.get('project_name'))
            project_mis_id = project_mis.first().id if project_mis.exists() else 1

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
                    projects__id=[project_id]
                )
            else:
                criteria = FacilitatorCriteria(
                    develop_mode=False,
                    training_mode=False,
                    projects__id=[project_id]
                )
            fs = FacilitatorRepository().find_by_criteria(criteria=criteria)
            
            # Ajouter les facilitateurs à la réponse
            _facilitators = [('', '')]
            datas["facilitators"] = [{'id': o.no_sql_db_name, 'name': o.name if o.name else o.username} for o in fs.order_by("name", "username")]
        
        return datas

    except Exception as e:
        logger.error(f"Erreur lors de la récupération des niveaux administratifs : {str(e)}")
        return {"error": str(e)}

# def get_cascade_administrative_levels_by_administrative_level_ids(_ids, request=None):
#     datas = {}
#     if type(_ids) is not list:
#         _ids = [_ids]
    
#     if '' in _ids:
#         del _ids[_ids.index('')]
#     if None in _ids:
#         del _ids[_ids.index(None)]

#     _ids = [int(_id) for _id in _ids if _id if str(_id).isdigit()]

#     if _ids:
#         ad_objects = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(id__in=_ids)

#         ads = []
#         for ad_obj in ad_objects:
#             ads += list(ad_obj.administrativelevel_set.get_queryset())
#         _type = ad_objects[0].type

#         if _type == "Region":
#             # regions = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Region")
#             prefectures = ads
#             communes = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(parent_id__in=[o.id for o in prefectures])
#             cantons = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(parent_id__in=[o.id for o in communes])
#             villages = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(parent_id__in=[o.id for o in cantons])
#         elif _type == "Prefecture":
#             # regions = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Region")
#             prefectures = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Prefecture")
#             communes = ads
#             cantons = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(parent_id__in=[o.id for o in communes])
#             villages = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(parent_id__in=[o.id for o in cantons])
#         elif _type == "Commune":
#             # regions = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Region")
#             prefectures = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Prefecture")
#             communes = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Commune")
#             cantons = ads
#             villages = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(parent_id__in=[o.id for o in cantons])
#         elif _type == "Canton":
#             # regions = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Region")
#             prefectures = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Prefecture")
#             communes = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Commune")
#             cantons = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Canton")
#             villages = ads
#         elif _type == "Village":
#             # regions = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Region")
#             prefectures = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Prefecture")
#             communes = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Commune")
#             cantons = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Canton")
#             villages = ad_objects
#         else:
#             prefectures = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Prefecture")
#             communes = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Commune")
#             cantons = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Canton")
#             villages = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Village")
#     else:
#         prefectures = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Prefecture")
#         communes = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Commune")
#         cantons = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Canton")
#         villages = administrativelevels_models.AdministrativeLevel.objects.using('mis').filter(type="Village")

        
#     datas["prefectures"] = get_administrative_levels_under_json(prefectures)
#     datas["communes"] = get_administrative_levels_under_json(communes)
#     datas["cantons"] = get_administrative_levels_under_json(cantons)
#     datas["villages"] = get_administrative_levels_under_json(villages)

#     if request:
#         project_mis = mis_objects_call.filter_objects(MisProject, name=request.session.get('project_name'))
#         project_mis_id = project_mis.first().id if project_mis.count() >= 1 else 1
        
#         if datas["villages"]:
#             assign_facilitators = AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(
#                 administrative_level_id__in=[str(v['administrative_id']) for v in datas["villages"]],
#                 project_id=project_mis_id,
#                 activated=True
#             )
#             criteria = FacilitatorCriteria(
#                 id__in=list(set([int(f.facilitator_id) for f in assign_facilitators])),
#                 develop_mode=False,
#                 training_mode=False,
#                 projects__id=[request.session.get('project_id')]
#             )

#         else:
#             criteria = FacilitatorCriteria(
#                 develop_mode=False,
#                 training_mode=False,
#                 projects__id=[request.session.get('project_id')]
#             )
#         fs = FacilitatorRepository().find_by_criteria(criteria=criteria)
        
#         _facilitators = [('', '')]
#         datas["facilitators"] = [{'id': o.no_sql_db_name, 'name': o.name if o.name else o.username} for o in fs.order_by("name", "username")]
        
#     return datas