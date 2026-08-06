"""Client HTTP vers l'API inter-services de grm-backend (Section B du CLAUDE.md GRM :
`D:\\COSO\\PROJECTS\\GRM\\claude\\CLAUDE.md`).

Remplace les accès directs à la base CouchDB partagée `eadls` (facilitateurs/ADL) — celle-ci a
été migrée vers Postgres côté GRM (`issue.models.Adl`) et n'est plus la source de vérité.
Authentification par secret partagé (`settings.GRM_SECRET_KEY_GENRATE`), même mécanisme que
l'intégration GRM -> CDD déjà existante (authentication/api/facilitators/update-user-adls/).

Chaque fonction renvoie la même forme de dict que l'ancien document CouchDB `eadls`
(`_id`, `type`, `name`, `location_name`, `administrative_region`, `administrative_regions`,
`additional_administrative_regions`, `representative: {id, name, email, phone, photo,
is_active, password, groups}`) pour ne pas avoir à réécrire le code consommateur existant.
"""
import requests
from django.conf import settings

_TIMEOUT = 15


def _headers():
    return {'X-GRM-Secret': settings.GRM_SECRET_KEY_GENRATE}


def get_facilitator_by_email(emails):
    """Remplace `nsc.get_db('eadls').get_query_result({"type": "adl", "representative.email": email})`.
    Renvoie None si aucun facilitateur GRM ne correspond à cet email (au lieu de lever une
    exception d'index sur une liste vide, comme le faisait souvent l'ancien code)."""
    if not emails:
        return None
    
    if isinstance(emails, str):
        params = {'email': emails}
    elif isinstance(emails, list):
        params = {'emails': emails}
    try:
        response = requests.get(
            f"{settings.GRM_URL_BASE}/api/service/adls/by-email/",
            params=params, headers=_headers(), timeout=_TIMEOUT,
        )
    except requests.RequestException:
        return None
    if response.status_code != 200:
        return None
    return response.json()


def get_facilitator_by_village(village_ids):
    """Remplace la vue CouchDB `eadls` `_design/adl_village_filter/by_village_id`. Renvoie une
    liste (peut être vide) des facilitateurs GRM gérant ce village."""
    if not village_ids:
        return []
    
    if isinstance(village_ids, str):
        params = {'village_id': village_ids}
    elif isinstance(village_ids, int):
        params = {'village_id': str(village_ids)}
    elif isinstance(village_ids, list):
        params = {'village_ids': village_ids}
    else:
        raise ValueError("Undefined village id type")

    try:
        response = requests.get(
            f"{settings.GRM_URL_BASE}/api/service/adls/by-village/",
            params=params, headers=_headers(), timeout=_TIMEOUT,
        )
    except requests.RequestException:
        return []
    if response.status_code != 200:
        return []
    return response.json()


def get_villages_with_facilitators(village_ids):
    if not village_ids:
        return []
    
    if isinstance(village_ids, str):
        params = {'village_id': village_ids}
    elif isinstance(village_ids, int):
        params = {'village_id': str(village_ids)}
    elif isinstance(village_ids, list):
        params = {'village_ids': village_ids}
    else:
        raise ValueError("Undefined village id type")

    try:
        response = requests.get(
            f"{settings.GRM_URL_BASE}/api/service/adls/villages-with-adls/",
            params=params, headers=_headers(), timeout=_TIMEOUT,
        )
    except requests.RequestException:
        return {}
    if response.status_code != 200:
        return {}
    return response.json()


def get_all_facilitators():
    """Remplace un parcours complet de la base CouchDB `eadls` (`all_docs`/`get_query_result`
    sans filtre), utilisé par les écrans d'export/statistiques."""
    try:
        response = requests.get(
            f"{settings.GRM_URL_BASE}/api/service/adls/", headers=_headers(), timeout=_TIMEOUT,
        )
    except requests.RequestException:
        return []
    if response.status_code != 200:
        return []
    return response.json()


def attach_administrative_regions_objects(eadl_doc):
    """Reconstruit localement la clé `administrative_regions_objects` (arbre canton/village)
    que portaient les anciens documents CouchDB `eadls`, mais que les dicts renvoyés par
    l'API GRM n'incluent plus (le modèle Postgres `issue.models.Adl` ne stocke que des listes
    d'ids plates `administrative_regions`). On la reconstruit à partir de la base MySQL `mis`
    (déjà utilisée ailleurs dans ce backend via `administrativelevels.models.AdministrativeLevel`,
    cf. `dashboard/utils.py::get_parent_administrative_level_mis`), pour ne pas casser le code
    consommateur qui lit `doc.get('administrative_regions_objects')`.

    Mute et renvoie `eadl_doc` (no-op si `eadl_doc` est None ou n'a pas de
    `administrative_regions`)."""
    
    if eadl_doc is None:
        return eadl_doc
    
    region_ids = []
    if isinstance(eadl_doc, str) and '@' in eadl_doc:
        from authentication.models import Facilitator
        facilitator = Facilitator.objects.filter(email=eadl_doc).first()
        if facilitator:
            region_ids = (facilitator.stabilization_administrative_ids or []) + (facilitator.additional_administrative_ids or [])
        eadl_doc = {}
    elif isinstance(eadl_doc, list):
        region_ids = list(eadl_doc)
        eadl_doc = {}
    elif isinstance(eadl_doc, dict):
        region_ids = (eadl_doc.get('smallest_administrative_level_ids') or []) + eadl_doc.get('additional_smallest_administrative_level_ids') or []
    
    region_ids = list(set(region_ids))

    from administrativelevels.models import AdministrativeLevel
    
    adls = AdministrativeLevel.objects.using('mis').filter(
        id__in=region_ids,
        type="Village"
    ).values_list('id', 'name', 'parent__id', 'parent__name')

    objects = {}

    for village_id, village_name, parent_id, parent_name in adls:
        objects.setdefault(
            parent_id,
            {
                "id": parent_id,
                "name": parent_name,
                "villages": []
            }
        )["villages"].append({
            "id": village_id,
            "name": village_name
        })

    objects = list(objects.values())

    # objects = []
    # for region_id in region_ids:
    #     try:
    #         region_id_int = int(region_id)
    #     except (TypeError, ValueError):
    #         continue

    #     region = AdministrativeLevel.objects.using('mis').filter(id=region_id_int).first()
    #     if not region:
    #         continue

    #     children = list(AdministrativeLevel.objects.using('mis').filter(parent_id=region_id_int))
    #     if children:
    #         villages = [{'id': child.id, 'name': child.name} for child in children]
    #     else:
    #         # Pas d'enfants : la région est déjà elle-même un village.
    #         villages = [{'id': region.id, 'name': region.name}]

    #     objects.append({'id': region.id, 'name': region.name, 'villages': villages})

    eadl_doc['administrative_regions_objects'] = objects
    return eadl_doc


def set_grm_user_password(email, new_password):
    """Pousse un changement de mot de passe vers le compte GRM (`auth.User`) correspondant,
    pour garder les comptes CDD et GRM synchronisés — remplace l'ancienne écriture directe dans
    CouchDB `eadls`/MySQL legacy `grm` (usermanager/views_forget_password.py,
    usermanager/views_change_password.py). Best-effort : ne bloque jamais le flux CDD si GRM est
    injoignable ou si l'utilisateur n'a pas de compte GRM."""
    try:
        response = requests.post(
            f"{settings.GRM_URL_BASE}/api/service/users/set-password/",
            json={'email': email, 'new_password': new_password},
            headers=_headers(), timeout=_TIMEOUT,
        )
        return response.status_code == 200
    except requests.RequestException:
        return False
