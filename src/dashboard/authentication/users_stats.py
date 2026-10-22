"""Statistiques des utilisateurs (pages Utilisateurs, Diagnostics et Diagnostics global) : une personne n'est comptée
qu'une fois dans le total.

Une personne peut avoir un compte facilitateur (mobile) et un compte web (`User`, souvent créé pour lui :
`Facilitator.user`). Ce sont alors les comptes d'une même personne (authentication/identity.py : lien, ou même e-mail,
ou même identifiant).
- Facilitateurs communautaires / techniques : comptes facilitateurs actifs, hors mode développement et formation.
- Superviseurs, Spécialistes DCC : comptes web actifs de ces groupes (rôles : un superviseur qui est aussi facilitateur
  figure dans les deux cartes).
- Spécialistes/Autres : les autres comptes web actifs, SAUF ceux des facilitateurs déjà comptés (jusqu'ici comptés une
  seconde fois : le compte web créé pour chaque facilitateur tombait dans cette carte).
- Total : personnes distinctes ; la liste complète (clic sur le total) donne chaque personne une fois, avec ses rôles.
"""
from django.contrib.auth.models import User
from django.utils.translation import gettext as _

from authentication.models import Facilitator
from dashboard.facilitators.repository.db_facilitator_repository import FacilitatorRepository
from dashboard.facilitators.repository.facilitator_criteria import FacilitatorCriteria
from dashboard.templatetags.custom_tags import get_group_high

FACILITATOR_GROUPS = {'CommunityFacilitator', 'TechnicalFacilitator'}
ROLE_GROUPS = ['Supervisor', 'CDDSpecialist']


def _key(value):
    return (value or '').strip().lower()


class Person:
    """Une personne : son compte facilitateur compté (s'il y en a un) et ses comptes web actifs du périmètre."""

    def __init__(self, facilitator=None):
        self.facilitator = facilitator
        self.users = []

    @property
    def account(self):
        return self.facilitator or self.users[0]

    @property
    def name(self):
        if self.facilitator:
            return self.facilitator.name or self.facilitator.username
        return self.users[0].get_full_name() or self.users[0].username

    @property
    def username(self):
        return self.account.username

    @property
    def email(self):
        return self.account.email or next((u.email for u in self.users if u.email), '')

    @property
    def phone(self):
        return getattr(self.facilitator, 'phone', None) or ''

    @property
    def roles(self):
        """Rôles sans doublon : type de facilitateur, puis rôle de chaque compte web (hors groupes de facilitateur)."""
        roles = [self.facilitator.get_facilitator_type_display()] if self.facilitator else []
        for user in self.users:
            groups = {group.name for group in user.groups.all()}
            if self.facilitator and groups and groups <= FACILITATOR_GROUPS and not user.is_superuser:
                continue  # compte web du facilitateur : même rôle
            role = get_group_high(user)
            if role and role not in roles:
                roles.append(role)
        return roles

    @property
    def accounts_label(self):
        if self.facilitator and self.users:
            return _('Mobile and web')
        return _('Mobile') if self.facilitator else _('Web')


def users_statistics(project_id=None):
    """Cartes et liste complète des utilisateurs, d'un projet (`project_id`) ou de tous les projets."""
    facilitator_filters = {'develop_mode': False, 'training_mode': False, 'active': True}
    if project_id:
        facilitator_filters['projects__id'] = [project_id]
    community_facilitators = FacilitatorRepository().find_by_criteria(
        criteria=FacilitatorCriteria(facilitator_type='community_facilitator', **facilitator_filters))
    technical_facilitators = FacilitatorRepository().find_by_criteria(
        criteria=FacilitatorCriteria(facilitator_type='technical_facilitator', **facilitator_filters))

    users = User.objects.filter(is_active=True)
    if project_id:
        users = users.filter(projects__in=[project_id])
    # `prefetch_related('groups')` : les modales affichent le groupe de chaque utilisateur, sans requête par ligne
    supervisors = users.filter(groups__name__in=['Supervisor']).prefetch_related('groups')
    CDDSpecialists = users.filter(groups__name__in=['CDDSpecialist']).prefetch_related('groups')

    # comptes web des facilitateurs comptés (même personne : lien, e-mail ou identifiant)
    people = {}
    by_user_id, by_email, by_username = {}, {}, {}
    for facilitator in list(community_facilitators) + list(technical_facilitators):
        if facilitator.pk in people:
            continue
        people[facilitator.pk] = Person(facilitator)
        if facilitator.user_id:
            by_user_id.setdefault(facilitator.user_id, facilitator.pk)
        if _key(facilitator.email):
            by_email.setdefault(_key(facilitator.email), facilitator.pk)
        if _key(facilitator.username):
            by_username.setdefault(_key(facilitator.username), facilitator.pk)

    def facilitator_of(user):
        return by_user_id.get(user.pk) or by_email.get(_key(user.email)) or by_username.get(_key(user.username))

    all_users = list(users.distinct().order_by('last_name', 'first_name', 'username').prefetch_related('groups'))
    facilitator_user_ids = set()
    web_people = []
    for user in all_users:
        facilitator_id = facilitator_of(user)
        if facilitator_id:
            facilitator_user_ids.add(user.pk)
            people[facilitator_id].users.append(user)
        else:
            person = Person()
            person.users.append(user)
            web_people.append(person)

    others_users = users.exclude(groups__name__in=ROLE_GROUPS).exclude(pk__in=facilitator_user_ids).prefetch_related('groups')
    all_people = sorted(list(people.values()) + web_people, key=lambda p: (_key(p.name), _key(p.username)))

    return {
        'community_facilitators': community_facilitators,
        'community_facilitators_count': community_facilitators.count(),
        'technical_facilitators': technical_facilitators,
        'technical_facilitators_count': technical_facilitators.count(),
        'supervisors': supervisors,
        'supervisors_count': supervisors.count(),
        'CDDSpecialists': CDDSpecialists,
        'CDDSpecialists_count': CDDSpecialists.count(),
        'others_users': others_users,
        'others_users_count': others_users.count(),
        # personnes distinctes : facilitateurs comptés + comptes web qui ne sont pas les leurs
        'total_users': len(all_people),
        'all_people': all_people,
    }
