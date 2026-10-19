"""Enregistrement d'une saisie COSOCollect, commun à l'API mobile (synchronisation) et au web.

Règles :
- le formulaire doit être publié : clôturé -> refus `form_closed` (le client garde sa saisie et affiche
  `CollectForm.close_message`) ;
- une saisie appartient à son auteur (ou à un autre compte de la même personne) ;
- formulaire « un seul enregistrement par personne » (`single_submission`) : la création d'une seconde
  saisie est refusée (`single_submission`), la personne reprend la sienne ;
- une saisie envoyée (`submitted`) est verrouillée tant qu'un administrateur ne la rouvre pas
  (`editable`) ; la renvoyer la reverrouille ;
- un administrateur ayant le droit `edit_data` corrige les données de n'importe quelle saisie
  (`admin_update_submission`), sans en changer l'auteur ni le statut.
"""
import copy
import logging
import uuid as uuid_lib

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _

from authentication.identity import is_facilitator

from . import access
from .fields import media_values
from .models import CollectAttachment, CollectForm, CollectSubmission
from .titles import compute_title, parse_iso

STATUSES = {s for s, _label in CollectSubmission.STATUSES}

logger = logging.getLogger(__name__)


def discard_stored_file(field_file):
    """Supprime du stockage (S3) le fichier d'une pièce jointe dont la ligne est supprimée.

    - APRÈS validation de la transaction : si elle est annulée, la ligne revient et son fichier doit
      encore exister ;
    - sans jamais faire échouer l'opération (enregistrement d'une saisie, suppression…) : un refus du
      stockage (droits, réseau) laisse seulement un fichier orphelin, signalé dans les journaux. Cas réel :
      clé AWS mise en quarantaine (`AWSCompromisedKeyQuarantineV2` refuse s3:DeleteObject) -> la
      synchronisation mobile tombait en erreur 500 et la saisie n'était jamais enregistrée."""
    name = getattr(field_file, 'name', '') or ''
    storage = getattr(field_file, 'storage', None)
    if not name or storage is None:
        return

    def _delete():
        try:
            storage.delete(name)
        except Exception:  # noqa: BLE001 - jamais bloquant, cf. docstring
            logger.warning('COSOCollect : fichier non supprimé du stockage : %s', name, exc_info=True)

    transaction.on_commit(_delete)


class CollectError(Exception):
    """Refus d'enregistrement : `code` stable (lu par le mobile), `message` lisible."""

    def __init__(self, code, message=''):
        super().__init__(message or code)
        self.code = code
        self.message = message or code


def actor_name(actor):
    if not actor:
        return ''
    if is_facilitator(actor):
        return actor.name or actor.username
    return actor.get_full_name() or actor.username


def as_uuid(value):
    try:
        return uuid_lib.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def _aware(value):
    dt = parse_iso(value)
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.utc)
    return dt


def clean_media_value(value):
    """Valeur d'un champ photo/fichier telle que stockée côté serveur : référence de la pièce jointe
    (jamais le chemin local de l'appareil)."""
    if not isinstance(value, dict):
        return None
    out = {k: value.get(k) for k in ('attachment_id', 'name', 'mime', 'size') if value.get(k) not in (None, '')}
    return out or None


def clean_data(form, data):
    """Copie de `data` dont les valeurs photo/fichier sont réduites à leur référence serveur."""
    if not isinstance(data, list):
        return []
    data = copy.deepcopy(data)
    data = [page if isinstance(page, dict) else {} for page in data]
    for path, field, value in media_values(data, form.form):
        cleaned = clean_media_value(value)
        _set_concrete(data, path, cleaned)
    return data


def _set_concrete(data, path, value):
    head, _, rest = path[1:].partition('.')
    cur = data[int(head)]
    parts = rest.split('.')
    for part in parts[:-1]:
        cur = cur[int(part)] if isinstance(cur, list) else cur.get(part)
        if cur is None:
            return
    if isinstance(cur, dict):
        if value is None:
            cur.pop(parts[-1], None)
        else:
            cur[parts[-1]] = value


def referenced_attachment_ids(form, data):
    ids = set()
    for _path, _field, value in media_values(data, form.form):
        try:
            ids.add(int(value.get('attachment_id')))
        except (TypeError, ValueError):
            continue
    return ids


def single_submission_error():
    return CollectError('single_submission', _('This form accepts only one record per person: you already have '
                                               'one. Open it to continue it.'))


def has_own_submission(actor, form):
    return access.own_submissions(actor, form).exists()


def _history(submission, action, actor, **extra):
    entry = {'at': timezone.now().isoformat(), 'action': action, 'by': actor_name(actor)}
    entry.update(extra)
    submission.history = (submission.history or []) + [entry]


def refresh_title(submission):
    submission.title = compute_title(
        submission.form, submission.form.title_template, submission.data,
        created=submission.started_at_local or submission.started_at or submission.created_at,
        author=submission.author_name,
    )


@transaction.atomic
def save_submission(form, actor, payload, source):
    """Crée ou met à jour la saisie décrite par `payload` :
    {uuid, status, data, created_at, updated_at, submitted_at, form_version}.
    Retourne la saisie enregistrée ; lève CollectError en cas de refus."""
    sub_uuid = as_uuid(payload.get('uuid'))
    if sub_uuid is None:
        raise CollectError('invalid', _('Invalid identifier.'))
    status = payload.get('status') or CollectSubmission.STATUS_DRAFT
    if status not in STATUSES:
        raise CollectError('invalid', _('Invalid status.'))
    data = payload.get('data')
    if not isinstance(data, list):
        raise CollectError('invalid', _('Invalid data.'))

    submission = CollectSubmission.objects.select_for_update().filter(uuid=sub_uuid).first()
    if submission and submission.form_id != form.pk:
        raise CollectError('invalid', _('This record belongs to another form.'))
    if submission and not access.owns_submission(actor, submission):
        raise CollectError('forbidden', _('This record belongs to another user.'))
    if not submission and not access.can_access_form(actor, form):
        raise CollectError('forbidden', _('You do not have access to this form.'))
    if form.status == CollectForm.STATUS_CLOSED:
        raise CollectError('form_closed', form.close_message or _('This form is closed: no more data can be sent.'))
    if form.status != CollectForm.STATUS_PUBLISHED:
        raise CollectError('form_unavailable', _('This form is not published.'))
    if submission and submission.is_locked:
        raise CollectError('locked', _('This record has already been sent and can no longer be modified.'))

    created = submission is None
    if created and form.single_submission:
        # Verrou sur le formulaire : deux créations simultanées (web + mobile) ne passent pas toutes les deux.
        CollectForm.objects.select_for_update().filter(pk=form.pk).first()
        if has_own_submission(actor, form):
            raise single_submission_error()
    if created:
        submission = CollectSubmission(form=form, uuid=sub_uuid, source=source)
        if is_facilitator(actor):
            submission.facilitator = actor
        else:
            submission.user = actor
        submission.started_at = _aware(payload.get('created_at')) or timezone.now()
        submission.started_at_local = str(payload.get('created_at') or '')[:40] or submission.started_at.isoformat()
        _history(submission, 'created', actor, source=source)

    previous_status = submission.status
    submission.data = clean_data(form, data)
    submission.form_version = int(payload.get('form_version') or form.version)
    submission.client_updated_at = _aware(payload.get('updated_at')) or timezone.now()
    submission.status = status
    if status == CollectSubmission.STATUS_SUBMITTED:
        if previous_status != CollectSubmission.STATUS_SUBMITTED or submission.editable:
            submission.submitted_at = _aware(payload.get('submitted_at')) or timezone.now()
            _history(submission, 'submitted', actor, source=source)
        submission.editable = False
    elif not created:
        _history(submission, 'updated', actor, source=source)
    refresh_title(submission)
    submission.save()

    # Pièces jointes : rattachement de celles déjà envoyées, suppression de celles remplacées.
    referenced = referenced_attachment_ids(form, submission.data)
    CollectAttachment.objects.filter(submission_uuid=sub_uuid, submission__isnull=True, form=form) \
        .update(submission=submission)
    for orphan in CollectAttachment.objects.filter(submission_uuid=sub_uuid).exclude(pk__in=referenced):
        discard_stored_file(orphan.file)
        orphan.delete()
    return submission


@transaction.atomic
def admin_update_submission(submission, user, data):
    """Modification des données d'une saisie par un administrateur ayant le droit `edit_data`.

    Possible quel que soit l'état (envoyée, verrouillée, formulaire clôturé) : l'auteur, le statut et les
    dates d'envoi sont conservés ; seule l'action est tracée dans l'historique. La copie de l'auteur sur
    son appareil est réalignée à sa prochaine synchronisation (si elle n'a pas de modification locale)."""
    if not isinstance(data, list):
        raise CollectError('invalid', _('Invalid data.'))
    submission = CollectSubmission.objects.select_for_update().select_related('form').get(pk=submission.pk)
    form = submission.form
    before = referenced_attachment_ids(form, submission.data)
    submission.data = clean_data(form, data)
    _history(submission, 'edited_by_admin', user)
    refresh_title(submission)
    submission.save()

    after = referenced_attachment_ids(form, submission.data)
    CollectAttachment.objects.filter(submission_uuid=submission.uuid, submission__isnull=True, form=form) \
        .update(submission=submission)
    # Fichiers retirés par l'administrateur, et ses propres envois non retenus. Les envois en attente de
    # l'auteur (pas encore référencés par sa saisie) ne sont pas touchés.
    removed = CollectAttachment.objects.filter(submission_uuid=submission.uuid).exclude(pk__in=after) \
        .filter(Q(pk__in=before) | Q(user=user))
    for attachment in removed:
        discard_stored_file(attachment.file)
        attachment.delete()
    return submission


def store_attachment(form, actor, uploaded_file, submission_uuid, field_path='', as_admin=False):
    """Fichier d'un champ photo / fichier. `as_admin` : envoi fait en modifiant la saisie d'un autre
    (droit `edit_data`, vérifié par l'appelant) — ni propriété, ni verrou, ni clôture ne s'appliquent."""
    sub_uuid = as_uuid(submission_uuid)
    if sub_uuid is None:
        raise CollectError('invalid', _('Invalid identifier.'))
    submission = CollectSubmission.objects.filter(uuid=sub_uuid).first()
    if as_admin:
        if submission is None or submission.form_id != form.pk:
            raise CollectError('invalid', _('This record belongs to another form.'))
    elif submission:
        if submission.form_id != form.pk:
            raise CollectError('invalid', _('This record belongs to another form.'))
        if not access.owns_submission(actor, submission):
            raise CollectError('forbidden', _('This record belongs to another user.'))
        if submission.is_locked:
            raise CollectError('locked', _('This record has already been sent and can no longer be modified.'))
    else:
        if not access.can_access_form(actor, form):
            raise CollectError('forbidden', _('You do not have access to this form.'))
        if form.single_submission and has_own_submission(actor, form):
            raise single_submission_error()  # fichier d'un second enregistrement : refusé d'emblée
    if form.status == CollectForm.STATUS_CLOSED and not as_admin:
        raise CollectError('form_closed', form.close_message or _('This form is closed: no more data can be sent.'))

    attachment = CollectAttachment(
        form=form, submission=submission, submission_uuid=sub_uuid, field_path=str(field_path or '')[:500],
        name=(uploaded_file.name or 'fichier')[:255],
        mime_type=(getattr(uploaded_file, 'content_type', '') or '')[:150],
        size=uploaded_file.size or 0,
    )
    if is_facilitator(actor):
        attachment.facilitator = actor
    else:
        attachment.user = actor
    attachment.file.save(uploaded_file.name or 'fichier', uploaded_file, save=False)
    attachment.save()
    return attachment


def set_submission_editable(submission, user, editable):
    submission.editable = bool(editable)
    if editable:
        submission.reopened_at = timezone.now()
        submission.reopened_by = user
    _history(submission, 'reopened' if editable else 'locked', user)
    submission.save(update_fields=['editable', 'reopened_at', 'reopened_by', 'history', 'updated_at'])


def bump_version(form):
    form.version = (form.version or 0) + 1


def submission_payload(submission):
    """Représentation d'une saisie pour le mobile / le web."""
    return {
        'uuid': str(submission.uuid),
        'form_id': submission.form_id,
        'form_version': submission.form_version,
        'title': submission.title,
        'status': submission.status,
        'editable': submission.editable,
        'locked': submission.is_locked,
        'data': submission.data,
        'created_at': submission.started_at_local or (submission.started_at and submission.started_at.isoformat()),
        'submitted_at': submission.submitted_at and submission.submitted_at.isoformat(),
        'updated_at': submission.updated_at and submission.updated_at.isoformat(),
        'source': submission.source,
        'author': submission.author_name,
    }
