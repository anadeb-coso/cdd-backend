"""Mise en forme lisible d'une saisie COSOCollect (page de détail web) : arbre de champs avec libellés,
valeurs affichables (libellés des choix, dates formatées, photos, coordonnées GPS), dans l'ordre du
formulaire et page par page."""
from .fields import form_fields, leaf_fields, resolve
from .titles import parse_iso


def _display_value(field, value):
    ftype = field['type']
    if value is None or value == '' or value == []:
        return ''
    if ftype == 'select_one':
        return field['choices'].get(str(value), str(value))
    if ftype in ('select_multiple', 'select_multiple_check'):
        values = value if isinstance(value, list) else [value]
        return [field['choices'].get(str(v), str(v)) for v in values]
    if ftype in ('date', 'datetime', 'time'):
        dt = parse_iso(value)
        if not dt:
            return str(value)
        return dt.strftime({'date': '%d/%m/%Y', 'datetime': '%d/%m/%Y %H:%M', 'time': '%H:%M'}[ftype])
    if isinstance(value, (dict, list)):
        return ''
    return value


def build_tree(form_pages, data, attachment_url):
    """[{index, nodes}] ; chaque nœud : {label, type, value, media, geo, children, rows}."""
    data = data if isinstance(data, list) else []

    def node(field, value):
        item = {'label': field['label'], 'type': field['type'], 'key': field['key'],
                'value': '', 'media': None, 'geo': None, 'children': [], 'rows': []}
        if field['type'] == 'group':
            item['children'] = nodes(field['children'], value if isinstance(value, dict) else {})
        elif field['type'] == 'repeat':
            for row in value if isinstance(value, list) else []:
                item['rows'].append(nodes(field['children'], row if isinstance(row, dict) else {}))
        elif field['type'] in ('photo', 'file') and isinstance(value, dict):
            attachment_id = value.get('attachment_id')
            mime = value.get('mime') or ''
            item['media'] = {
                'name': value.get('name') or '',
                'url': attachment_url(attachment_id) if attachment_id else '',
                'is_image': field['type'] == 'photo' or mime.startswith('image/'),
                'size': value.get('size'),
            }
        elif field['type'] == 'geopoint' and isinstance(value, dict):
            try:
                item['geo'] = {
                    'lat': float(value.get('latitude')), 'lng': float(value.get('longitude')),
                    'accuracy': value.get('accuracy'), 'altitude': value.get('altitude'),
                }
            except (TypeError, ValueError):
                item['geo'] = None
        elif field['type'] == 'note':
            item['value'] = ''
        else:
            item['value'] = _display_value(field, value)
            item['is_list'] = isinstance(item['value'], list)
        return item

    def nodes(field_list, values):
        return [node(f, values.get(f['key'])) for f in field_list]

    pages = {}
    for field in form_fields(form_pages):
        pages.setdefault(field['page'], []).append(field)
    out = []
    for index in sorted(pages):
        values = data[index] if index < len(data) and isinstance(data[index], dict) else {}
        out.append({'index': index, 'number': index + 1, 'nodes': nodes(pages[index], values)})
    return out


def table_columns(form_pages, limit=8):
    """Premiers champs « affichables en tableau » (hors groupes répétables, notes et médias)."""
    out = []
    for field in leaf_fields(form_pages):
        if field['repeat_path'] or field['type'] in ('photo', 'file', 'geopoint'):
            continue
        out.append(field)
        if len(out) >= limit:
            break
    return out


def cell_value(field, data):
    value = _display_value(field, resolve(data, field['path']))
    if isinstance(value, list):
        return ', '.join(str(v) for v in value)
    return value
