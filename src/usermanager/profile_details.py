"""Informations affichées sur la page Profil de l'utilisateur connecté (servie par le CDD pour DCC, SIG et MGP)."""
import logging

from django.templatetags.static import static
from django.utils.translation import gettext as _

from authentication import FACILITATORS_TYPES
from authentication.models import UserLocalities

FEMALE_VALUES = {'mme', 'mlle', 'f', 'femme', 'female', 'féminin', 'feminin'}
MALE_VALUES = {'m.', 'm', 'mr', 'homme', 'male', 'masculin'}


def gender_of(sex):
    """'female', 'male' ou None à partir de la civilité enregistrée ("M." / "Mme")."""
    value = (sex or '').strip().lower()
    if value in FEMALE_VALUES:
        return 'female'
    if value in MALE_VALUES:
        return 'male'
    return None


def avatar_url(gender):
    return static(f"images/avatars/{gender or 'neutral'}.svg")


def _ids(values):
    """Liste d'identifiants à partir d'un JSON (ids ou dicts {id: ...})."""
    result = []
    for value in values or []:
        if isinstance(value, dict):
            value = value.get('id') or value.get('administrative_id')
        if value not in (None, '') and value not in result:
            result.append(value)
    return result


def _facilitator_zone(tree, facilitator):
    """Villages du facilitateur regroupés par canton : [« Canton: X »], noms de villages, nombre."""
    village_ids = _ids(facilitator.administrative_levels_ids) or _ids(facilitator.administrative_levels)
    cantons, villages = [], []
    for _id in village_ids:
        if not str(_id).isdigit():
            continue
        level = tree.levels.get(int(_id))
        if level is None:
            continue
        villages.append(level[1])
        parent = level[3]
        while parent and tree.type_of(parent) not in ('Canton', None):
            parent = tree.levels[parent][3] if parent in tree.levels else None
        if parent and parent not in cantons:
            cantons.append(parent)
    labels = [tree.label_of(c) for c in cantons]
    if not labels and facilitator.main_administrative_id:
        labels = [tree.label_of(facilitator.main_administrative_id)]
    return {'labels': labels, 'additional': sorted(villages), 'villages': len(villages)}


def _projects(user, facilitator):
    from process_manager.models import Cycle, Project

    from django.db.models import Q

    filters = None
    if user is not None:
        filters = Q(users=user)
    if facilitator is not None:
        filters = (filters | Q(facilitators=facilitator)) if filters is not None else Q(facilitators=facilitator)
    if filters is None:
        return []
    projects = list(Project.objects.filter(filters).select_related('parent').distinct().order_by('name'))
    cycles = {}
    for cycle in Cycle.objects.filter(project__in=projects).order_by('order', 'id'):
        cycles.setdefault(cycle.project_id, []).append(cycle.name)
    rows = []
    for project in projects:
        roles = []
        if user is not None and project.users.filter(pk=user.pk).exists():
            roles.append(_('User'))
        if facilitator is not None and project.facilitators.filter(pk=facilitator.pk).exists():
            roles.append(str(dict(FACILITATORS_TYPES).get(facilitator.facilitator_type) or _('Facilitator')))
        rows.append({
            'name': project.name,
            'description': project.description,
            'status': project.status,
            'parent': project.parent.name if project.parent else None,
            'cycles': cycles.get(project.pk, []),
            'roles': roles,
        })
    return rows


def build_profile_details(cdd_user, facilitator, mis_user, grm_user):
    """Dictionnaire prêt pour le gabarit ; chaque bloc est protégé (la page doit toujours s'afficher)."""
    user = cdd_user or mis_user
    if facilitator is None and user is not None:
        facilitator = getattr(user, 'facilitator', None)  # compte web lié (OneToOne), même personne

    gender = gender_of(getattr(facilitator, 'sex', None))
    details = {
        'gender': gender,
        'avatar': avatar_url(gender),
        'civility': getattr(facilitator, 'sex', None),
        'facilitator': facilitator,
        'facilitator_type': dict(FACILITATORS_TYPES).get(facilitator.facilitator_type) if facilitator else None,
        'user': user,
        'usernames': [],
        'groups': [],
        'projects': [],
        'zone': None,
        'platforms': [],
    }

    usernames = []
    for name in (getattr(user, 'username', None), getattr(facilitator, 'username', None), (grm_user or {}).get('username')):
        if name and name not in usernames:
            usernames.append(name)
    details['usernames'] = usernames

    groups = set(user.groups.values_list('name', flat=True)) if user is not None else set()
    groups.update((grm_user or {}).get('groups') or [])
    details['groups'] = sorted(groups)

    details['platforms'] = [
        {'name': _('Web DCC'), 'icon': 'fa-desktop', 'active': cdd_user is not None},
        {'name': _('Mobile DCC'), 'icon': 'fa-mobile-alt', 'active': facilitator is not None},
        {'name': _('SIG (COSOMIS)'), 'icon': 'fa-map-marked-alt', 'active': mis_user is not None},
        {'name': _('MGP (GRM)'), 'icon': 'fa-comments', 'active': bool(grm_user)},
    ]

    try:
        details['projects'] = _projects(user, facilitator)
    except Exception as exc:  # noqa: BLE001
        logging.exception(exc)

    try:
        from dashboard.facilitators.localities import AdministrativeTree, describe_user_zone
        tree = AdministrativeTree()
        if facilitator is not None:
            details['zone'] = _facilitator_zone(tree, facilitator)
        elif user is not None:
            record = UserLocalities.objects.filter(user=user).first()
            details['zone'] = {'labels': [describe_user_zone(tree, user, record)], 'additional': [], 'villages': None}
    except Exception as exc:  # noqa: BLE001
        logging.exception(exc)

    return details
