"""Lecture d'un formulaire COSOCollect (pages au format `Task.form`) champ par champ.

Même décompilation que le builder web (`nodeFromSchema` de static/dashboard/js/task_form_builder.js) et
que le moteur de remplissage (`fieldFromSchema` de task_cycle_fill_form.js) : un champ est décrit par
`{key, label, type, ...}` où `type` vaut text, note, integer, decimal, select_one, select_multiple,
select_multiple_check, date, datetime, time, geopoint, photo, file, group ou repeat.

Les chemins suivent la convention du builder : `"$<page>.<chemin.pointé>"`.
"""
from dashboard.process_manager.tasks.form_design import _normalize_order

MEDIA_TYPES = {'photo', 'file'}
SELECT_TYPES = {'select_one', 'select_multiple', 'select_multiple_check'}
CONTAINER_TYPES = {'group', 'repeat'}


def _choices_map(enum):
    """`enum` d'un select : liste (valeur = libellé) ou objet {valeur: libellé} (sources dynamiques)."""
    if isinstance(enum, dict):
        return {str(k): str(v) for k, v in enum.items()}
    if isinstance(enum, list):
        return {str(v): str(v) for v in enum}
    return {}


def _dataset_map(opts):
    out = {}
    for row in (opts or {}).get('dataset') or []:
        if isinstance(row, dict) and row.get('v') not in (None, ''):
            out[str(row['v'])] = str(row.get('l') if row.get('l') not in (None, '') else row['v'])
    return out


def field_type(prop, opts):
    prop = prop or {}
    opts = opts or {}
    if prop.get('type') == 'object':
        return 'group'
    if prop.get('type') == 'array' and isinstance(prop.get('items'), dict) and prop['items'].get('type') == 'object':
        return 'repeat'
    if prop.get('type') == 'array' and isinstance(prop.get('items'), dict) and 'enum' in prop['items']:
        return 'select_multiple_check' if opts.get('mode') == 'checklist' else 'select_multiple'
    if 'enum' in prop:
        return 'select_one'
    if prop.get('type') == 'geopoint' or opts.get('mode') == 'geopoint':
        return 'geopoint'
    if prop.get('type') in MEDIA_TYPES or opts.get('mode') in MEDIA_TYPES:
        return prop.get('type') if prop.get('type') in MEDIA_TYPES else opts.get('mode')
    if prop.get('type') == 'integer':
        return 'integer'
    if prop.get('type') == 'number':
        return 'decimal'
    if prop.get('format') in ('date', 'datetime', 'time'):
        return prop['format']
    if prop.get('_note'):
        return 'note'
    return 'text'


def _children(obj_schema, opts, page_index, prefix, repeat_path, group_labels):
    props = (obj_schema or {}).get('properties') or {}
    fields_opts = (opts or {}).get('fields') or {}
    out = []
    for key in _normalize_order((opts or {}).get('order'), props):
        out.append(_field(key, props[key], fields_opts.get(key) or {}, page_index, prefix, repeat_path, group_labels))
    return out


def _field(key, prop, opts, page_index, prefix, repeat_path, group_labels):
    ftype = field_type(prop, opts)
    local_path = f'{prefix}.{key}' if prefix else key
    field = {
        'key': key,
        'label': opts.get('label') or key,
        'type': ftype,
        'page': page_index,
        'local_path': local_path,
        'path': f'${page_index}.{local_path}',
        'repeat_path': repeat_path,  # chemin ($p.x) du répétable le plus proche qui contient le champ
        'group_labels': list(group_labels),
        'children': [],
        'choices': {},
    }
    if ftype in SELECT_TYPES:
        enum = prop.get('enum') if ftype == 'select_one' else (prop.get('items') or {}).get('enum')
        choices = _choices_map(enum)
        choices.update(_dataset_map(opts))
        field['choices'] = choices
    if ftype == 'group':
        field['children'] = _children(prop, opts, page_index, local_path, repeat_path,
                                      group_labels + [field['label']])
    elif ftype == 'repeat':
        item_opts = opts.get('item') if isinstance(opts.get('item'), dict) and opts['item'].get('fields') else opts
        field['children'] = _children(prop.get('items') or {}, item_opts, page_index, local_path,
                                      field['path'], group_labels + [field['label']])
    return field


def form_fields(form):
    """Arbre des champs de tout le formulaire (une liste par page, concaténées)."""
    out = []
    for page_index, page in enumerate(form or []):
        if not isinstance(page, dict):
            continue
        out.extend(_children(page.get('page') or {}, page.get('options') or {}, page_index, '', None, []))
    return out


def iter_fields(fields):
    for field in fields:
        yield field
        if field['children']:
            yield from iter_fields(field['children'])


def leaf_fields(form, include_notes=False):
    """Champs feuilles (hors groupes/répétables), dans l'ordre d'affichage."""
    return [
        f for f in iter_fields(form_fields(form))
        if f['type'] not in CONTAINER_TYPES and (include_notes or f['type'] != 'note')
    ]


def fields_by_path(form):
    return {f['path']: f for f in iter_fields(form_fields(form))}


def resolve(data, path):
    """Valeur au chemin `"$<page>.<a.b>"` dans `data` (liste de pages) — None si absente ou si le
    chemin traverse un répétable (une liste : pas de valeur unique)."""
    if not isinstance(path, str) or not path.startswith('$'):
        return None
    head, _, rest = path[1:].partition('.')
    try:
        page_index = int(head)
    except ValueError:
        return None
    if not isinstance(data, list) or not (0 <= page_index < len(data)):
        return None
    cur = data[page_index]
    for part in rest.split('.') if rest else []:
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def local_get(values, local_path):
    cur = values
    for part in (local_path or '').split('.'):
        if not part:
            continue
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return None
    return cur


def choice_label(field, value):
    if value is None:
        return None
    return field.get('choices', {}).get(str(value), str(value))


def is_empty(value):
    return value is None or value == '' or value == [] or value == {}


def media_values(data, form=None):
    """Toutes les valeurs de champs photo/fichier présentes dans `data`, avec leur chemin concret
    (index de ligne compris pour les répétables) : [(path, field, value_dict)]."""
    out = []
    fields = form_fields(form) if form is not None else []

    def walk(field_list, values, prefix):
        for f in field_list:
            if not isinstance(values, dict):
                return
            val = values.get(f['key'])
            path = f'{prefix}.{f["key"]}'
            if f['type'] == 'group':
                walk(f['children'], val or {}, path)
            elif f['type'] == 'repeat':
                for i, row in enumerate(val if isinstance(val, list) else []):
                    walk(f['children'], row or {}, f'{path}.{i}')
            elif f['type'] in MEDIA_TYPES and isinstance(val, dict):
                out.append((path, f, val))

    by_page = {}
    for f in fields:
        by_page.setdefault(f['page'], []).append(f)
    for page_index, page_fields in by_page.items():
        values = data[page_index] if isinstance(data, list) and page_index < len(data) else {}
        walk(page_fields, values or {}, f'${page_index}')
    return out


def geopoint_values(data, form):
    """Points GPS d'une saisie : [(path, field, {latitude, longitude, ...})], répétables compris."""
    out = []

    def walk(field_list, values, prefix):
        for f in field_list:
            if not isinstance(values, dict):
                return
            val = values.get(f['key'])
            path = f'{prefix}.{f["key"]}'
            if f['type'] == 'group':
                walk(f['children'], val or {}, path)
            elif f['type'] == 'repeat':
                for i, row in enumerate(val if isinstance(val, list) else []):
                    walk(f['children'], row or {}, f'{path}.{i}')
            elif f['type'] == 'geopoint' and isinstance(val, dict):
                try:
                    lat, lng = float(val.get('latitude')), float(val.get('longitude'))
                except (TypeError, ValueError):
                    continue
                out.append((path, f, dict(val, latitude=lat, longitude=lng)))

    by_page = {}
    for f in form_fields(form):
        by_page.setdefault(f['page'], []).append(f)
    for page_index, page_fields in by_page.items():
        values = data[page_index] if isinstance(data, list) and page_index < len(data) else {}
        walk(page_fields, values or {}, f'${page_index}')
    return out
