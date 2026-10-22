"""Mail envoyé à un facilitateur ou à un utilisateur quand ses localités changent (affectation/initiales,
stabilisation, additionnelles, intervention), quelle que soit l'origine : pages « Localités », formulaire du
facilitateur, import Excel ou MGP. Construit à partir des lignes d'historique (`LocalityHistory`) créées par
l'opération : rien n'est envoyé si rien n'a réellement changé (par exemple le renvoi par le MGP des localités
que le DCC vient de lui transmettre)."""
from datetime import datetime

from django.utils.translation import gettext as _

from authentication.accounts import send_mail_to
from .localities import TOGO_ID, AdministrativeTree


def localities_mail_rows(tree, events):
    rows = []
    for event in events:
        whole_country = event.main_after == TOGO_ID
        rows.append({
            'section': str(event.get_section_display()),
            'whole_country': whole_country,
            'first_definition': event.villages_before is None,
            'main': tree.label_of(event.main_after) if event.main_after else None,
            'choices': [tree.label_of(c) for c in event.choices_after or []],
            'added': [tree.name_of(v) for v in event.added or []],
            'removed': [tree.name_of(v) for v in event.removed or []],
            'villages': [tree.name_of(v) for v in event.villages_after or []],
        })
    return rows


def notify_localities_change(account, events, tree=None):
    """Mail à `account` (Facilitator ou User) récapitulant `events` (lignes d'historique créées par une même
    opération). Rien sans changement, sans e-mail ou pour un compte inactif. Renvoie True si envoyé."""
    events = [event for event in events or [] if event is not None]
    email = (getattr(account, 'email', None) or '').strip()
    active = getattr(account, 'active', None) if hasattr(account, 'no_sql_db_name') else getattr(account, 'is_active', False)
    if not events or not email or not active:
        return False
    tree = tree or AdministrativeTree()
    name = getattr(account, 'name', None) or f"{account.last_name or ''} {account.first_name or ''}".strip() or account.username
    title = _("Update of your localities")
    context = {
        'subject': title,
        'title': title,
        'greeting': _("Hello"),
        'all_sex': getattr(account, 'sex', None) or _("Mr./Mrs."),
        'user_full_name': name,
        'rows': localities_mail_rows(tree, events),
        'current_year': datetime.now().year,
    }
    subject = f"[COSO Apps : {datetime.now().strftime('%Y-%m-%d')}] {title}"
    return send_mail_to(subject, 'mail/send/localities_change', context, [email])
