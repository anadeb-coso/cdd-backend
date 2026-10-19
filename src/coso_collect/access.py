"""Droits COSOCollect.

- Créer un formulaire : web uniquement, superutilisateur ou membre d'un des groupes `FORM_CREATOR_GROUPS`
  (`Admin`, `FormCreator` — ce dernier créé par la migration 0002, attribuable depuis la page Utilisateurs).
- Administrer un formulaire : superutilisateur et créateur (tous les droits, eux seuls gèrent la liste des
  administrateurs), ou administrateur désigné (`CollectFormAdmin`) avec les seuls droits que le créateur
  lui a accordés (`CollectFormAdmin.RIGHTS`).
- Remplir : formulaire publié (ou clôturé : lecture seule) accessible à tous les comptes connectés, ou
  restreint aux utilisateurs / groupes / facilitateurs choisis. Un compte web et un compte facilitateur de
  la même personne sont équivalents (authentication/identity.py).
"""
from django.contrib.auth.models import Group, User
from django.db.models import Q

from authentication.identity import is_facilitator, owned_by, same_person_accounts

from .models import CollectForm, CollectFormAdmin, CollectSubmission

FACILITATOR_GROUPS = ('CommunityFacilitator', 'TechnicalFacilitator')
FORM_CREATOR_GROUP = 'FormCreator'
FORM_CREATOR_GROUPS = ('Admin', FORM_CREATOR_GROUP)

RIGHT_CODES = [code for code, _label in CollectFormAdmin.RIGHTS]
# Droits qui portent sur les saisies des autres : impossibles sans les voir.
RIGHT_REQUIRES = {
    'export': 'view_data',
    'reopen_records': 'view_data',
    'edit_data': 'view_data',
    'delete_records': 'view_data',
}


def accounts(actor):
    """(ids User, ids Facilitator) de la même personne que `actor` (comptes actifs)."""
    return same_person_accounts(actor)


def _user_ids(actor):
    return accounts(actor)[0]


def can_create_forms(user):
    if not user or not getattr(user, 'is_authenticated', False) or is_facilitator(user):
        return False
    return user.is_superuser or user.groups.filter(name__in=FORM_CREATOR_GROUPS).exists()


def normalize_rights(codes):
    """Droits cochés -> ensemble cohérent (un droit sur les saisies entraîne la lecture des données)."""
    codes = {c for c in codes if c in RIGHT_CODES}
    if any(c in RIGHT_REQUIRES for c in codes):
        codes.add('view_data')
    return codes


class FormRights:
    """Droits d'un compte sur un formulaire.

    En Python : `rights.has('export')` ; dans les gabarits : `{% if rights.export %}`.
    `full` : superutilisateur ou créateur (tous les droits + gestion des administrateurs)."""

    def __init__(self, user, form, user_ids=None, rows=None):
        self.form = form
        self.full = False
        self.codes = set()
        self.is_admin = False
        if not user or not getattr(user, 'is_authenticated', False) or is_facilitator(user):
            return  # l'administration se fait sur le web, avec un compte web
        user_ids = _user_ids(user) if user_ids is None else user_ids
        if user.is_superuser or form.created_by_id in user_ids:
            self.full = self.is_admin = True
            self.codes = set(RIGHT_CODES)
            return
        if rows is None:
            rows = list(CollectFormAdmin.objects.filter(form=form, user_id__in=user_ids))
        self.is_admin = bool(rows)
        for row in rows:  # plusieurs comptes web de la même personne : union des droits
            self.codes.update(row.granted())

    def has(self, code):
        return code in self.codes

    @property
    def manage_admins(self):
        return self.full

    def first_tab(self):
        """Onglet d'arrivée d'un administrateur : le premier qu'il a le droit d'ouvrir."""
        if self.has('view_data'):
            return 'summary'
        if self.has('export'):
            return 'export'
        if self.has('edit_form'):
            return 'builder'
        return 'settings'

    def __getattr__(self, name):
        # Accès « rights.export » depuis les gabarits.
        if name in RIGHT_CODES:
            return name in self.codes
        raise AttributeError(name)


def form_rights(user, form):
    return FormRights(user, form)


def rights_by_form(user, forms):
    """{form.pk: FormRights} pour une liste de formulaires, sans requête par formulaire."""
    if not user or is_facilitator(user):
        return {f.pk: FormRights(None, f) for f in forms}
    user_ids = _user_ids(user)
    rows = {}
    for row in CollectFormAdmin.objects.filter(form__in=[f.pk for f in forms], user_id__in=user_ids):
        rows.setdefault(row.form_id, []).append(row)
    return {f.pk: FormRights(user, f, user_ids=user_ids, rows=rows.get(f.pk, [])) for f in forms}


def has_right(user, form, code):
    return form_rights(user, form).has(code)


def admin_filter(user):
    """Condition « formulaires administrés par `user` » (quels que soient ses droits)."""
    if getattr(user, 'is_superuser', False):
        return Q()
    user_ids = list(_user_ids(user))
    return Q(created_by_id__in=user_ids) | Q(admin_rights__user_id__in=user_ids)


def is_form_admin(user, form):
    return form_rights(user, form).is_admin


def administered_forms(user):
    if not user or is_facilitator(user):
        return CollectForm.objects.none()
    return CollectForm.objects.filter(admin_filter(user)).distinct()


def _group_ids(actor):
    users, facilitators = accounts(actor)
    group_ids = set(Group.objects.filter(user__in=users).values_list('pk', flat=True))
    if facilitators:
        group_ids |= set(Group.objects.filter(name__in=('Facilitator',) + FACILITATOR_GROUPS).values_list('pk', flat=True))
    return group_ids


def fill_filter(actor):
    """Condition « formulaires que `actor` peut remplir / consulter » (hors statut)."""
    users, facilitators = accounts(actor)
    if not users and not facilitators:
        return Q(pk__in=[])
    if users and User.objects.filter(pk__in=users, is_superuser=True).exists():
        return Q()
    return (
        Q(access_scope=CollectForm.ACCESS_ALL)
        | Q(allowed_users__in=list(users))
        | Q(allowed_facilitators__in=list(facilitators))
        | Q(allowed_groups__in=list(_group_ids(actor)))
        | Q(created_by_id__in=list(users))
        | Q(admin_rights__user_id__in=list(users))
    )


def fillable_forms(actor, include_closed=True):
    statuses = [CollectForm.STATUS_PUBLISHED] + ([CollectForm.STATUS_CLOSED] if include_closed else [])
    return CollectForm.objects.filter(fill_filter(actor), status__in=statuses).distinct()


def can_access_form(actor, form):
    """Peut voir le formulaire et ses propres saisies (publié ou clôturé)."""
    if form.status == CollectForm.STATUS_DRAFT:
        return is_form_admin(actor, form)
    return CollectForm.objects.filter(fill_filter(actor), pk=form.pk).exists()


def own_submissions(actor, form=None):
    qs = CollectSubmission.objects.filter(owned_by(accounts(actor)))
    if form is not None:
        qs = qs.filter(form=form)
    return qs


def owns_submission(actor, submission):
    users, facilitators = accounts(actor)
    return submission.user_id in users or submission.facilitator_id in facilitators


def can_view_submission(actor, submission):
    return owns_submission(actor, submission) or has_right(actor, submission.form, 'view_data')


def can_view_attachment(actor, attachment):
    """Pièce jointe : son auteur, l'auteur de la saisie, ou un administrateur qui lit les données."""
    users, facilitators = accounts(actor)
    if attachment.user_id in users or attachment.facilitator_id in facilitators:
        return True
    if attachment.submission_id and owns_submission(actor, attachment.submission):
        return True
    return has_right(actor, attachment.form, 'view_data')
