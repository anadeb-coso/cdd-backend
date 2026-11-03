"""Compte MGP des comptes créés dans le DCC (facilitateurs et utilisateurs web).

Le MGP ne crée jamais de compte dans le DCC : c'est le DCC qui crée, sur le MGP, le compte de même e-mail avec la
même empreinte de mot de passe. Un compte MGP déjà existant pour cet e-mail est laissé tel quel ('exists')."""
from django.contrib.auth.models import User

import grm_client
from authentication.accounts import grm_account, split_full_name


def linked_facilitator(user):
    """Facilitateur de la même personne qu'un compte web (lien, ou même e-mail), ou None."""
    from authentication.models import Facilitator

    facilitator = Facilitator.objects.filter(user=user).first()
    if facilitator is None and (user.email or '').strip():
        facilitator = Facilitator.objects.filter(email__iexact=user.email.strip()).first()
    return facilitator


def create_user_on_mgp(user):
    """Compte MGP d'un utilisateur web non facilitateur : (statut, détail) ; statut None sans e-mail.
    Statuts : 'created', 'exists', 'error'."""
    from authentication.models import UserLocalities

    if not (user.email or '').strip():
        return None, None
    record = UserLocalities.objects.filter(user=user).first()
    ok, detail = grm_client.create_user_on_grm(
        email=user.email.strip(), first_name=user.first_name, last_name=user.last_name, phone=None,
        groups=list(user.groups.values_list('name', flat=True)), password_hash=user.password, is_active=user.is_active,
        administrative_id=record.administrative_id if record else None,
        administrative_ids=(record.administrative_choices or []) if record else [],
        additional_administrative_ids=(record.additional_administrative_choices or []) if record else [],
    )
    if not ok:
        return 'error', detail
    return (detail or {}).get('status', 'created'), None


def create_account_on_mgp(account):
    """Compte MGP d'un `User` ou d'un `Facilitator` (un compte web lié à un facilitateur est créé comme
    facilitateur : groupe et localités de stabilisation). (statut, détail)."""
    from authentication.models import Facilitator
    from dashboard.facilitators.creation import create_facilitator_on_mgp

    facilitator = account if isinstance(account, Facilitator) else linked_facilitator(account)
    if facilitator is not None and facilitator.facilitator_type and (facilitator.email or '').strip():
        if isinstance(account, User) and (account.first_name or account.last_name):
            first_names, last_name = account.first_name, account.last_name
        else:
            last_name, first_names = split_full_name(facilitator.name)
        return create_facilitator_on_mgp(facilitator, first_names, last_name)
    if isinstance(account, Facilitator):
        return None, None  # facilitateur sans e-mail : pas de compte MGP possible
    return create_user_on_mgp(account)


def mgp_account_exists(email):
    """True / False ; None si la base du MGP n'est pas lisible depuis le DCC ou sans e-mail."""
    from django.db import connections

    if not (email or '').strip() or 'grm' not in connections:
        return None
    return grm_account(email) is not None
