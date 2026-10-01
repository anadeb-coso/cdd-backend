"""Trajet des facilitateurs et des utilisateurs : enregistrement de chaque changement de localités
(`authentication.models.LocalityHistory`) et lecture (chronologie d'une personne, présences dans une
localité)."""
from datetime import date, datetime, time, timedelta

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .localities import TOGO_ID, administrative_choices, user_display_name


# ---------------------------------------------------------------------------------------------
# Date du changement sur le terrain (saisie sur les pages Localités)
# ---------------------------------------------------------------------------------------------

def last_change_at(facilitator=None, user=None):
    """Date du dernier changement enregistré dans le trajet de ce facilitateur / cet utilisateur (ou None)."""
    from authentication.models import LocalityHistory

    events = LocalityHistory.objects.filter(facilitator=facilitator) if facilitator is not None else \
        LocalityHistory.objects.filter(user=user)
    return events.order_by('-changed_at', '-id').values_list('changed_at', flat=True).first()


def min_change_date(last_changed_at):
    return timezone.localtime(last_changed_at).date() if last_changed_at else None


def parse_change_date(raw, last_changed_at):
    """(date, erreur) de la date du changement sur le terrain saisie (AAAA-MM-JJ), aujourd'hui par défaut ; pas
    avant le dernier changement enregistré (le trajet reste dans l'ordre chronologique)."""
    today = timezone.localdate()
    if not raw:
        return today, None
    try:
        value = date.fromisoformat(str(raw).strip())
    except ValueError:
        return None, _("Invalid date of the change in the field.")
    minimum = min_change_date(last_changed_at)
    if minimum and value < minimum:
        return None, _("The date of the change in the field cannot be earlier than the last recorded change (%(date)s).") % {
            'date': minimum.strftime('%d/%m/%Y')}
    return value, None


def change_datetime(value, last_changed_at):
    """Horodatage de l'événement : maintenant pour aujourd'hui, midi pour une autre date ; toujours après le
    dernier changement enregistré (même jour)."""
    if value == timezone.localdate():
        at = timezone.now()
    else:
        at = timezone.make_aware(datetime.combine(value, time(12, 0)))
    if last_changed_at and at <= last_changed_at:
        at = last_changed_at + timedelta(seconds=1)
    return at


def _main(value):
    return str(value) if value not in (None, '') else None


def record_localities_change(section, source, after, before=None, facilitator=None, user=None, changed_by=None,
                             changed_by_label=None, project_id=None, changed_at=None, approximate_date=False):
    """Ajoute une ligne d'historique si les localités ont changé.

    `before`/`after` : dict(main=..., choices=[...], villages=[...]) ; `before=None` = état antérieur
    inconnu (1re définition, état initial constaté). Villages, niveau principal et choix sont comparés
    sans tenir compte de l'ordre (le GRM renvoie les choix dans un autre ordre)."""
    from authentication.models import LocalityHistory

    after_villages = administrative_choices(after.get('villages'))
    after_choices = administrative_choices(after.get('choices'))
    after_main = _main(after.get('main'))
    if before is None:
        if not after_villages and not after_choices and not after_main:
            return None
        before_villages, before_choices, before_main = None, None, None
    else:
        before_villages = administrative_choices(before.get('villages'))
        before_choices = administrative_choices(before.get('choices'))
        before_main = _main(before.get('main'))
        if (set(before_villages) == set(after_villages) and set(before_choices) == set(after_choices)
                and before_main == after_main):
            return None

    before_set, after_set = set(before_villages or []), set(after_villages)
    if changed_by is not None and not getattr(changed_by, 'is_authenticated', False):
        changed_by = None
    return LocalityHistory.objects.create(
        facilitator=facilitator,
        user=user,
        email=facilitator.email if facilitator else (user.email if user else None),
        name=facilitator.name if facilitator else (user_display_name(user) if user else None),
        section=section,
        main_before=before_main,
        main_after=after_main,
        choices_before=before_choices,
        choices_after=after_choices,
        villages_before=before_villages,
        villages_after=after_villages,
        added=[v for v in after_villages if v not in before_set],
        removed=[v for v in (before_villages or []) if v not in after_set],
        project_id=project_id,
        source=source,
        changed_by=changed_by,
        changed_by_label=changed_by_label or (user_display_name(changed_by) if changed_by else None),
        changed_at=changed_at or timezone.now(),
        approximate_date=approximate_date,
    )


def facilitator_state(facilitator):
    """États courants d'un facilitateur par section (pour `before`/`after`)."""
    return {
        'assignment': {'villages': facilitator.administrative_levels_ids or []},
        'stabilization': {
            'main': facilitator.main_administrative_id,
            'choices': facilitator.stabilization_administrative_choices or [],
            'villages': facilitator.stabilization_administrative_ids or [],
        },
        'additional': {
            'choices': facilitator.additional_administrative_choices or [],
            'villages': facilitator.additional_administrative_ids or [],
        },
    }


def user_state(record):
    """États courants des localités d'intervention d'un utilisateur (None : jamais définies)."""
    if record is None:
        return {'intervention': None, 'intervention_additional': None}
    return {
        'intervention': {
            'main': record.administrative_id,
            'choices': record.administrative_choices or [],
            'villages': record.village_ids or [],
        },
        'intervention_additional': {
            'choices': record.additional_administrative_choices or [],
            'villages': record.additional_village_ids or [],
        },
    }


def record_facilitator_changes(facilitator, before, source, sections=None, **kwargs):
    """Compare `before` (= `facilitator_state` avant modification) à l'état actuel et enregistre chaque
    section modifiée."""
    after = facilitator_state(facilitator)
    for section in sections or after.keys():
        record_localities_change(section, source, after[section], before[section], facilitator=facilitator, **kwargs)


def record_user_changes(account, before, record, source, **kwargs):
    after = user_state(record)
    for section in ('intervention', 'intervention_additional'):
        record_localities_change(section, source, after[section], before[section], user=account, **kwargs)


# ---------------------------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------------------------

def event_rows(tree, events):
    """Lignes d'affichage des événements (noms des villages ajoutés/retirés, niveaux principaux)."""
    def names(ids, limit=30):
        labels = [tree.name_of(i) for i in ids]
        return ", ".join(labels[:limit]) + (f" … (+{len(labels) - limit})" if len(labels) > limit else "")

    rows = []
    for event in events:
        rows.append({
            'event': event,
            'added_count': len(event.added or []),
            'removed_count': len(event.removed or []),
            'added': names(event.added or []),
            'removed': names(event.removed or []),
            'after_count': len(event.villages_after or []),
            'first_definition': event.villages_before is None,
            'main_changed': event.main_before != event.main_after,
            'main_before': tree.label_of(event.main_before) if event.main_before else "-",
            'main_after': tree.label_of(event.main_after) if event.main_after else "-",
            'whole_country': event.main_after == TOGO_ID,
        })
    return rows


def presence_periods(events, village_ids):
    """Périodes pendant lesquelles chaque personne avait au moins un village de `village_ids`, par section,
    reconstituées à partir des événements (quelle que soit leur ordre). Une période qui commence par un état
    initial constaté ou une 1re définition n'a pas de date d'arrivée exacte (« au moins depuis »)."""
    village_ids = set(village_ids)
    by_subject = {}
    for event in sorted(events, key=lambda e: (e.changed_at, e.id)):
        key = ('facilitator', event.facilitator_id) if event.facilitator_id else ('user', event.user_id or event.email)
        by_subject.setdefault((key, event.section), []).append(event)

    periods = []
    for (_key, section), subject_events in by_subject.items():
        current = None
        for event in subject_events:
            inside_after = bool(village_ids & set(event.villages_after or []))
            if current is None and inside_after:
                current = {
                    'event': event, 'section': section, 'start': event.changed_at,
                    'start_known': event.villages_before is not None and event.source not in ('initial_state',),
                    'start_approximate': event.approximate_date,
                    'villages': sorted(village_ids & set(event.villages_after or [])),
                    'end': None, 'end_approximate': False,
                }
            elif current is not None and not inside_after:
                current['end'] = event.changed_at
                current['end_approximate'] = event.approximate_date
                periods.append(current)
                current = None
            elif current is not None:
                current['villages'] = sorted(set(current['villages']) | (village_ids & set(event.villages_after or [])))
        if current is not None:
            periods.append(current)
    return sorted(periods, key=lambda p: (p['end'] is not None, p['event'].name or '', p['start']))
