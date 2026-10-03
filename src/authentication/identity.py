"""Une même personne peut avoir un compte web (`User`) et un compte facilitateur (`Facilitator`, mobile). Pour la
récupération de SES données (planification, nouvelles, menu « Tâches »), les deux comptes sont équivalents :
ceux qui partagent un e-mail ou un identifiant (sans tenir compte de la casse), ou le lien `Facilitator.user`.

Règle : seuls les comptes ACTIFS comptent, des deux côtés. Un compte web actif ne voit pas les données de son
facilitateur inactif, et un facilitateur actif ne voit pas celles de son compte web inactif ; un compte inactif
n'obtient rien.
"""
from django.contrib.auth.models import User
from django.db.models import Q

from authentication.models import Facilitator


def _identifiers(*values):
    return {value.strip() for value in values if value and value.strip()}


def _matching(identifiers):
    """Condition « e-mail ou identifiant égal à l'une de ces valeurs » (aucune valeur -> rien)."""
    condition = Q(pk__in=[])
    for value in identifiers:
        condition |= Q(email__iexact=value) | Q(username__iexact=value)
    return condition


def is_facilitator(account):
    return isinstance(account, Facilitator)


def is_active(account):
    return bool(account) and (account.active if is_facilitator(account) else account.is_active)


def same_person_accounts(account):
    """Comptes actifs (ids des `User`, ids des `Facilitator`) de la même personne que `account`, lui compris.
    Compte absent ou inactif : aucun."""
    if not is_active(account):
        return set(), set()
    identifiers = _identifiers(account.email, account.username)
    if is_facilitator(account):
        users = set(User.objects.filter(_matching(identifiers) | Q(pk=account.user_id or 0), is_active=True)
                    .values_list('pk', flat=True))
        facilitators = {account.pk}
    else:
        users = {account.pk}
        facilitators = set(Facilitator.objects.filter(_matching(identifiers) | Q(user_id=account.pk), active=True)
                           .values_list('pk', flat=True))
    return users, facilitators


def accounts_for_identifier(identifier):
    """Comptes actifs de la (des) personne(s) qui se connecte(nt) avec cet e-mail ou cet identifiant : les comptes
    actifs qui le portent, et leurs équivalents actifs (cas des API du mobile, qui n'envoient qu'un identifiant)."""
    identifiers = _identifiers(identifier)
    users, facilitators = set(), set()
    if not identifiers:
        return users, facilitators
    for account in list(User.objects.filter(_matching(identifiers), is_active=True)) + \
            list(Facilitator.objects.filter(_matching(identifiers), active=True)):
        same_users, same_facilitators = same_person_accounts(account)
        users |= same_users
        facilitators |= same_facilitators
    return users, facilitators


def owned_by(accounts, user_field='user', facilitator_field='facilitator'):
    """Condition « l'objet appartient à l'un de ces comptes » pour un modèle à deux propriétaires possibles
    (`user` / `facilitator`, éventuellement préfixés : 'activity__user'). `accounts` = (ids User, ids Facilitator)."""
    users, facilitators = accounts
    return Q(**{f'{user_field}_id__in': list(users)}) | Q(**{f'{facilitator_field}_id__in': list(facilitators)})


def facilitator_of_user(user):
    """Le facilitateur ACTIF d'un compte web actif : celui qui lui est lié (`Facilitator.user`), sinon celui qui a le
    même e-mail ou identifiant. Aucun si l'un des deux est inactif."""
    _, facilitators = same_person_accounts(user)
    if not facilitators:
        return None
    candidates = Facilitator.objects.filter(pk__in=facilitators)
    return candidates.filter(user_id=user.pk).first() or candidates.order_by('pk').first()
