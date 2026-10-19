"""Titre combiné d'une saisie COSOCollect (le libellé qui représente un objet de données).

`title_template` = {
    "parts": [
        {"type": "field", "path": "$0.canton"},          # valeur d'un champ (libellé pour un choix)
        {"type": "meta", "key": "created_at"},           # métadonnée de la saisie
        {"type": "text", "value": "lot1"},               # texte fixe
    ],
    "separator": "_",
    "slugify": true,     # minuscules, sans accents, tout caractère non alphanumérique -> "_"
}

Ex. canton=CINKASSE, village=CINKASSE CENTRE, enregistré le 05/10/2026 à 14:13:50 ->
"cinkasse_cinkasse_centre_20261005141350".

Même algorithme côté mobile (src/utils/collectTitle.ts) et builder web (aperçu) : le serveur recalcule
toujours le titre à l'enregistrement, le client ne l'affiche que tant qu'il n'est pas synchronisé.
"""
import re
import unicodedata
from datetime import datetime

from django.utils import timezone

from .fields import SELECT_TYPES, fields_by_path, resolve

META_KEYS = ('created_at', 'created_date', 'created_time', 'author', 'form')
DEFAULT_SEPARATOR = '_'
MAX_LENGTH = 500


def slugify_piece(value):
    text = unicodedata.normalize('NFD', str(value))
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    text = re.sub(r'[^a-z0-9]+', '_', text.lower())
    return text.strip('_')


def parse_iso(value):
    """Date ISO-8601 -> datetime en conservant son propre fuseau (heure « murale » de l'appareil)."""
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace('Z', '+00:00')
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    for fmt in ('%Y-%m-%dT%H:%M:%S.%f%z', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%d'):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _number(value):
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def field_display(field, value, joiner=' '):
    """Valeur d'un champ telle qu'elle entre dans le titre (libellé d'un choix, date compacte…)."""
    if value is None or value == '' or value == [] or value == {}:
        return ''
    ftype = field['type'] if field else 'text'
    if ftype in SELECT_TYPES:
        values = value if isinstance(value, list) else [value]
        return joiner.join(field['choices'].get(str(v), str(v)) for v in values if v not in (None, ''))
    if ftype in ('date', 'datetime', 'time'):
        dt = parse_iso(value)
        if not dt:
            return str(value)
        return dt.strftime({'date': '%Y%m%d', 'datetime': '%Y%m%d%H%M%S', 'time': '%H%M%S'}[ftype])
    if ftype == 'geopoint' and isinstance(value, dict):
        try:
            return '{:.5f} {:.5f}'.format(float(value['latitude']), float(value['longitude']))
        except (KeyError, TypeError, ValueError):
            return ''
    if ftype in ('photo', 'file') and isinstance(value, dict):
        return str(value.get('name') or '')
    if isinstance(value, (int, float)):
        return _number(value)
    if isinstance(value, (list, dict)):
        return ''
    return str(value)


def meta_display(key, created, author='', form_title=''):
    if key in ('created_at', 'created_date', 'created_time'):
        if not created:
            return ''
        return created.strftime({'created_at': '%Y%m%d%H%M%S', 'created_date': '%Y%m%d',
                                 'created_time': '%H%M%S'}[key])
    if key == 'author':
        return author or ''
    if key == 'form':
        return form_title or ''
    return ''


def normalize_template(raw, form=None):
    """Nettoie un `title_template` reçu (builder, import) : parties connues uniquement ; un champ doit
    exister dans le formulaire (hors répétable) si `form` est fourni."""
    raw = raw if isinstance(raw, dict) else {}
    known = fields_by_path(form) if form is not None else None
    parts = []
    for part in raw.get('parts') or []:
        if not isinstance(part, dict):
            continue
        kind = part.get('type')
        if kind == 'field':
            path = part.get('path')
            if not isinstance(path, str) or not path.startswith('$'):
                continue
            if known is not None:
                field = known.get(path)
                if not field or field['type'] in ('group', 'repeat', 'note') or field['repeat_path']:
                    continue
            parts.append({'type': 'field', 'path': path})
        elif kind == 'meta' and part.get('key') in META_KEYS:
            parts.append({'type': 'meta', 'key': part['key']})
        elif kind == 'text' and str(part.get('value') or '').strip():
            parts.append({'type': 'text', 'value': str(part['value'])[:100]})
    separator = raw.get('separator')
    separator = DEFAULT_SEPARATOR if separator is None else str(separator)[:5]
    return {'parts': parts, 'separator': separator, 'slugify': raw.get('slugify', True) is not False}


def compute_title(form_obj_or_pages, title_template, data, created=None, author='', form_title=''):
    """Titre combiné d'une saisie. `created` : datetime (ou ISO) d'enregistrement de la saisie."""
    pages = getattr(form_obj_or_pages, 'form', form_obj_or_pages) or []
    if hasattr(form_obj_or_pages, 'title') and not form_title:
        form_title = form_obj_or_pages.title
    template = normalize_template(title_template)
    created = parse_iso(created) if not isinstance(created, datetime) else created
    if created is None:
        created = timezone.localtime(timezone.now())
    by_path = fields_by_path(pages)
    do_slug = template['slugify']

    pieces = []
    has_field_part = has_field_value = False
    for part in template['parts']:
        if part['type'] == 'field':
            has_field_part = True
            text = field_display(by_path.get(part['path']), resolve(data, part['path']))
            has_field_value = has_field_value or bool(text)
        elif part['type'] == 'meta':
            text = meta_display(part['key'], created, author, form_title)
        else:
            text = part['value']
        text = slugify_piece(text) if do_slug else str(text).strip()
        if text:
            pieces.append(text)

    if not pieces or (has_field_part and not has_field_value):
        # Pas de titre défini, ou aucun de ses champs n'est encore renseigné (saisie à peine démarrée) :
        # titre de repli « formulaire + date d'enregistrement ».
        base = slugify_piece(form_title) if do_slug else str(form_title or '').strip()
        pieces = [p for p in (base, meta_display('created_at', created)) if p]
    return template['separator'].join(pieces)[:MAX_LENGTH]
