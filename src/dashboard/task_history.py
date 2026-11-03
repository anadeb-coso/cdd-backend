"""Forme allégée des historiques des tâches CouchDB (`updated_history`, `updated_after_invalidation_history`,
`completed_history`).

Chaque entrée garde `facilitator` = identité (name, email, phone, sex, sql_id, type) + ce qui a changé :
- `administrative_levels` : seulement la liste des ids (plus les noms / villages sièges) ;
- plus de `form_fields` (le formulaire entier), `attachments` ni `form_response` (copie des réponses) ;
- `updated_history` / `updated_after_invalidation_history` : une entrée sans aucune modification (ni
  `fields_updated`, ni `attachments_updated`) est retirée. Quand une ancienne entrée a `fields_updated` sans
  `fields_updated_response`, celui-ci est reconstitué depuis son `form_response` (nouvelle valeur) et le dernier
  état connu de la même page dans l'historique (ancienne valeur ; None si inconnu) avant de retirer `form_response`.
  Une ancienne entrée sans `fields_updated` mais avec `form_response` est comparée de la même façon.
- `completed_history` : les entrées (achevée / rouverte) sont toutes gardées, seulement allégées.

Le mobile et le web (menu Tâches) écrivent déjà cette forme ; `clean_task_histories` corrige l'existant.
"""
import json

HISTORY_KEYS = ('updated_history', 'updated_after_invalidation_history', 'completed_history')
HEAVY_KEYS = ('form_response', 'form_fields', 'attachments')


def _same(a, b):
    return json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)


def administrative_level_ids(levels):
    if not isinstance(levels, list):
        return []
    ids = []
    for level in levels:
        _id = level.get('id') if isinstance(level, dict) else level
        if _id not in (None, '') and _id not in ids:
            ids.append(_id)
    return ids


def _page_index(page):
    try:
        return int(page)
    except (TypeError, ValueError):
        return 0


def _page_values(form_response, page):
    """Réponses de la page de l'entrée : `form_response` est la page elle-même (dict) ou toutes les pages."""
    if isinstance(form_response, dict):
        return form_response
    if isinstance(form_response, list):
        index = _page_index(page)
        value = form_response[index] if 0 <= index < len(form_response) else None
        return value if isinstance(value, dict) else {}
    return None


def clean_history(entries, kind):
    """(entrées nettoyées, a changé ?) ; `kind` = 'updated' (2 premiers historiques) ou 'completed'."""
    if not isinstance(entries, list):
        return entries, False
    known = {}  # page -> dernières valeurs connues
    out = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get('facilitator'), dict):
            out.append(entry)
            continue
        fac = dict(entry['facilitator'])

        if kind == 'updated':
            page = _page_index(fac.get('page'))
            values = _page_values(fac.get('form_response'), fac.get('page')) if 'form_response' in fac else None
            previous = known.get(page)
            fields = fac.get('fields_updated')
            responses = fac.get('fields_updated_response')
            if values is not None:
                if fields is None:
                    base = previous or {}
                    fields = [k for k, v in values.items() if not _same(v, base.get(k))]
                    fac['fields_updated'] = fields
                if fields and not responses:
                    fac['fields_updated_response'] = {
                        k: {'old': (previous or {}).get(k), 'new': values.get(k)} for k in fields
                    }
                known[page] = dict(values)
            elif isinstance(responses, dict) and responses:
                state = dict(previous or {})
                for k, change in responses.items():
                    if isinstance(change, dict) and 'new' in change:
                        state[k] = change['new']
                known[page] = state
            if not fac.get('fields_updated') and not fac.get('attachments_updated'):
                continue  # aucune modification : pas d'historique

        for key in HEAVY_KEYS:
            fac.pop(key, None)
        if 'administrative_levels' in fac:
            fac['administrative_levels'] = administrative_level_ids(fac['administrative_levels'])
        out.append(dict(entry, facilitator=fac))
    return out, not _same(out, entries)


def clean_task_doc(doc):
    """Nettoie les 3 historiques d'une tâche (en place) ; True si le document a changé."""
    changed = False
    for key in HISTORY_KEYS:
        if key in doc:
            cleaned, did = clean_history(doc[key], 'completed' if key == 'completed_history' else 'updated')
            if did:
                doc[key] = cleaned
                changed = True
    return changed
