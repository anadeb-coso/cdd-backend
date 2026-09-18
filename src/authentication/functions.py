from django.utils.translation import gettext_lazy
from django.contrib.auth.models import Group, User

from assignments.models import AssignAdministrativeLevelToFacilitator
from cdd.call_objects_from_other_db import mis_objects_call
from authentication import PROFESSIONAL_GROUPS, FACILITATOR_TYPE_TO_GROUP_NAME, FACILITATORS_TYPES_WITH_GROUP_NAME


def get_assign_adl_by_facilitatr(facilitator_id, project_id, activated):
    return mis_objects_call.filter_objects(
                AssignAdministrativeLevelToFacilitator, 
                facilitator_id=facilitator_id, project_id=project_id, activated=activated
            )

def get_assigns_adl_by_facilitatrs(facilitator_ids, project_id, activated):
    return mis_objects_call.filter_objects(
                AssignAdministrativeLevelToFacilitator, 
                facilitator_id__in=facilitator_ids, project_id=project_id, activated=activated
            )


def get_group_high(group: Group):
    if group.name in PROFESSIONAL_GROUPS:

        if group.name == "Minister":
            return gettext_lazy("Minister").__str__()
        if group.name == "Advisor":
            return gettext_lazy("Advisor").__str__()
        if group.name == "GeneralManager":
            return gettext_lazy("General Manager").__str__()
        if group.name == "NationalCoordinator":
            return gettext_lazy("National Coordinator").__str__()
        if group.name == "RegionalCoordinator":
            return gettext_lazy("Regional Coordinator").__str__()
        if group.name == "Director":
            return gettext_lazy("Director").__str__()
        
        if group.name == "Evaluator":
            return gettext_lazy("Evaluator").__str__()
        if group.name == "Financial":
            return gettext_lazy("Financial ").__str__()
        if group.name == "ProcurementSpecialist":
            return gettext_lazy("Procurement Specialist").__str__()
        if group.name == "KnowledgeManager":
            return gettext_lazy("Knowledge manager").__str__()
        if group.name == "CDDSpecialist":
            return gettext_lazy("CDD Specialist").__str__()
        if group.name == "Accountant":
            return gettext_lazy("Accountant").__str__()
        if group.name == "Infra":
            return gettext_lazy("Infra").__str__()
        if group.name == "YouthProgramSpecialist":
            return gettext_lazy("Youth Program Specialist").__str__()
        if group.name == "LocalEconomicDevelopmentSpecialist":
            return gettext_lazy("Local Economic Development Specialist").__str__()
        if group.name == "CommunicationSpecialist":
            return gettext_lazy("Communication Specialist").__str__()
        if group.name == "FullStack":
            return gettext_lazy("FullStack").__str__()
        
        if group.name == "Supervisor":
            return gettext_lazy("Supervisor").__str__()
        
        if group.name == "CommunityFacilitator":
            return gettext_lazy("Community Facilitator").__str__()
        if group.name == "TechnicalFacilitator":
            return gettext_lazy("Technical Facilitator").__str__()


    return gettext_lazy("User").__str__()


# ---------------------------------------------------------------------------
# Connexion des Facilitators au Web DCC (Facilitator.user, OneToOne vers
# django.contrib.auth.models.User) : voir dashboard/facilitators/views.py
# (CreateFacilitatorView/UpdateFacilitatorView, qui appellent
# ensure_facilitator_user après avoir posé name/email/phone/sex/
# facilitator_type sur l'instance) et
# authentication/management/commands/link_facilitators_to_users.py (rattrapage
# des facilitators déjà en base).
# ---------------------------------------------------------------------------

def _insert_suffix_before_at(value, suffix):
    """"local@domain" -> "local<suffix>@domain". Générique à tout domaine
    (gmail.com/test.com/yahoo.fr tous rencontrés en base) — pas restreint à
    "@gmail.com". Renvoie `value` tel quel si aucun "@" n'est trouvé."""
    if not value or "@" not in value:
        return value
    local, _, domain = value.partition("@")
    return f"{local}{suffix}@{domain}"


def _unique_facilitator_email(facilitator):
    """Email à utiliser pour le `User` de ce facilitator : celui déjà sur
    `facilitator.email` s'il est libre, sinon le même avec un suffixe
    numérique inséré juste avant le "@", incrémenté jusqu'à trouver une
    valeur libre (ex. training1@gmail.com -> training11@gmail.com). Exclut
    le `User` déjà lié à CE facilitator (ré-appel idempotent)."""
    base = facilitator.email
    candidate = base
    suffix = 1
    existing_qs = User.objects.all()
    if facilitator.user_id:
        existing_qs = existing_qs.exclude(pk=facilitator.user_id)
    while base and existing_qs.filter(email__iexact=candidate).exists():
        candidate = _insert_suffix_before_at(base, str(suffix))
        suffix += 1
    return candidate


def _unique_facilitator_username(facilitator):
    """Même principe que `_unique_facilitator_email`, appliqué au
    `User.username` dérivé de `facilitator.username` — JAMAIS écrit sur
    `Facilitator.username` lui-même (utilisé par CouchDB/mobile/`code`, hors
    périmètre de cette fonctionnalité : la modifier casserait l'identifiant
    mobile). Cas réel trouvé en base : les facilitators en collision d'email
    sont aussi en collision de username avec le même compte staff. Sans
    impact pour l'utilisateur : le login web n'utilise que l'email
    (EmailAuthenticationForm), jamais ce username."""
    base = facilitator.username
    candidate = base
    suffix = 1
    existing_qs = User.objects.all()
    if facilitator.user_id:
        existing_qs = existing_qs.exclude(pk=facilitator.user_id)
    while existing_qs.filter(username=candidate).exists():
        candidate = f"{base}{suffix}"
        suffix += 1
    return candidate


def ensure_facilitator_user(facilitator):
    """Crée ou met à jour le `User` Django lié à ce `Facilitator` (accès web
    limité à quelques menus, cf. dashboard/templates/layouts/sidebar.html) —
    réutilisée par les vues de création/édition de facilitator ET par la
    commande de rattrapage `link_facilitators_to_users`. Idempotente : un
    ré-appel sur un facilitator déjà lié met à jour son `User` existant,
    jamais de doublon créé.

    Effet de bord : peut modifier et SAUVEGARDER `facilitator.email` (en
    Postgres uniquement, via `simple_save()`) si l'email actuel est déjà
    pris par un AUTRE `User` — l'appelant reste responsable de répercuter ce
    changement dans le doc CouchDB du facilitator (cf.
    dashboard/facilitators/views.py, où `doc["email"]` est construit APRÈS
    cet appel, précisément pour ça)."""
    group_name = FACILITATOR_TYPE_TO_GROUP_NAME.get(facilitator.facilitator_type)
    group = Group.objects.get_or_create(name=group_name)[0] if group_name else None

    final_email = _unique_facilitator_email(facilitator)
    email_changed = final_email != facilitator.email
    facilitator.email = final_email

    last_name, first_name = "", ""
    if facilitator.name:
        # Découpage volontairement identique à l'ancien code
        # (dashboard/facilitators/views.py, précédent mort remplacé par cet
        # appel) : le 1er mot dans `last_name`, le reste dans `first_name`.
        parts = facilitator.name.split(" ")
        last_name = parts[0]
        first_name = " ".join(parts[1:])

    is_new_link = not facilitator.user_id
    if is_new_link:
        user = User(username=_unique_facilitator_username(facilitator), email=final_email or "")
    else:
        user = facilitator.user
        user.email = final_email or ""

    user.password = facilitator.password  # déjà hashé (make_password, même hasher que User)
    user.is_active = facilitator.active
    user.is_staff = False
    user.last_name = last_name
    user.first_name = first_name
    user.save()

    if group is not None:
        other_group_names = [n for n in FACILITATORS_TYPES_WITH_GROUP_NAME if n != group_name]
        if other_group_names:
            user.groups.remove(*Group.objects.filter(name__in=other_group_names))
        user.groups.add(group)

    if is_new_link or email_changed:
        facilitator.user = user
        facilitator.simple_save()

    return user


def sync_facilitator_user_projects(facilitator):
    """Aligne les projets accessibles au `User` web de ce facilitator
    (Project.users) sur ceux auxquels le Facilitator est CURRENTLY associé
    (Project.facilitators, exposé via facilitator.projects, related_name
    symétrique). Remplace la liste entière (.set, pas .add) pour refléter
    l'état courant plutôt que de ne faire qu'accumuler.

    Appelée APRÈS que Project.facilitators soit à jour pour cet appel (donc
    après la boucle `p.facilitators.add(facilitator)` des vues create/update,
    PAS depuis ensure_facilitator_user lui-même qui tourne avant cette boucle
    dans ces 2 vues — cf. dashboard/facilitators/views.py)."""
    if not facilitator.user_id:
        return
    facilitator.user.projects.set(facilitator.projects.all())