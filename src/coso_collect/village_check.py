"""Contrôle des villages des saisies COSOCollect (onglet « Villages » de l'administration d'un formulaire).

Un formulaire « à village » a un champ dont la source est la liste des niveaux administratifs de type Village
(`options._source = {kind: admin_levels, level: Village}`), ou un champ nommé `village` à liste de choix ; il peut
être placé dans un groupe (« localisation.village »), pas dans un répétable. La saisie y garde l'IDENTIFIANT du
village (texte), parfois un NOM (saisie libre, anciens formulaires). Le nom du village au moment de la saisie est
celui de la liste de choix enregistrée dans le formulaire (`enum` {id: nom} et/ou `dataset` [{v, l, p}]).

Une valeur est signalée quand :
- ``unknown_id`` : l'identifiant n'est plus un village de la base ;
- ``renamed`` : l'identifiant existe, mais son nom en base n'est plus celui de la liste du formulaire (village
  renommé, ou identifiant réattribué à un autre village) ;
- ``text`` : la valeur est un nom, pas un identifiant.

Pour chacune, des villages candidats sont proposés : nom proche du nom connu (sans accents, casse ni
ponctuation), avec un bonus pour les villages du canton (puis de la commune) de la saisie. Sans bonne proposition, les morceaux
du titre de la saisie (souvent « canton_village_date ») sont essayés comme noms. Le canton et la commune
de la saisie sont lus dans ses champs canton/commune (identifiant, ou nom de la liste du formulaire retrouvé en base).

`relink` remplace la valeur par l'identifiant du village choisi (et, au choix, les champs région ... canton de la
saisie par ses parents), trace l'action dans l'historique de la saisie et recalcule son titre.
"""
import difflib
import re
import unicodedata

from django.db import transaction

GEO_LEVELS = ('region', 'prefecture', 'commune', 'canton', 'village')
GEO_TYPES = {'Region': 'region', 'Prefecture': 'prefecture', 'Commune': 'commune', 'Canton': 'canton',
             'Village': 'village'}
MAX_CANDIDATES = 6
MIN_SIMILARITY = 0.6
CANTON_BONUS, COMMUNE_BONUS = 0.15, 0.05
GOOD_SCORE = 0.85          # en deçà, le titre de la saisie est aussi essayé
TITLE_MIN_SIMILARITY = 0.8   # plus strict pour les morceaux du titre (mots courants)
TITLE_MAX_WORDS = 5


def norm(text):
    """Texte comparable : sans accents, casse, ponctuation ni espaces multiples."""
    text = unicodedata.normalize('NFKD', str(text or '')).encode('ascii', 'ignore').decode()
    return ' '.join(re.sub(r'[^\w\s]', ' ', text).lower().split())


def similarity(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def _as_id(value):
    text = str(value).strip() if value is not None else ''
    if text.endswith('.0'):
        text = text[:-2]
    return int(text) if text.isdigit() else None


# ------------------------------------------------------------------------------------------- champs du formulaire
def _choice_labels(prop, opts):
    labels = {}
    enum = prop.get('enum')
    if enum is None and isinstance(prop.get('items'), dict):
        enum = prop['items'].get('enum')
    if isinstance(enum, dict):
        labels.update({str(k): str(v) for k, v in enum.items()})
    for row in (opts or {}).get('dataset') or []:
        if isinstance(row, dict) and row.get('v') not in (None, '') and row.get('l') not in (None, ''):
            labels[str(row['v'])] = str(row['l'])
    return labels


def _geo_level(key, prop, opts):
    source = (opts or {}).get('_source') or {}
    level = norm(source.get('level'))
    if level in GEO_LEVELS:
        return level
    has_choices = source or (opts or {}).get('dataset') is not None or 'enum' in (prop or {})
    return norm(key) if norm(key) in GEO_LEVELS and has_choices else None


def geo_fields(form_pages):
    """{niveau: {'page', 'path', 'label', 'labels', 'multiple'}} : premier champ de chaque niveau géographique
    (pages et groupes parcourus, pas les répétables)."""
    from dashboard.process_manager.tasks.form_design import _normalize_order
    out = {}

    def walk(page_index, props, fields_opts, order, prefix):
        for key in _normalize_order(order, props):
            prop, opts = props.get(key) or {}, (fields_opts or {}).get(key) or {}
            level = _geo_level(key, prop, opts)
            if level and level not in out:
                out[level] = {'page': page_index, 'path': prefix + key, 'label': opts.get('label') or key,
                              'labels': _choice_labels(prop, opts), 'multiple': prop.get('type') == 'array'}
            elif prop.get('type') == 'object':
                walk(page_index, prop.get('properties') or {}, opts.get('fields') or {}, opts.get('order'),
                     prefix + key + '.')

    for page_index, page in enumerate(form_pages or []):
        if isinstance(page, dict):
            options = page.get('options') or {}
            walk(page_index, (page.get('page') or {}).get('properties') or {}, options.get('fields') or {},
                 options.get('order'), '')
    return out


def has_village_field(form):
    return 'village' in geo_fields(form.form or [])


def _get(data, page, path):
    if not (isinstance(data, list) and 0 <= page < len(data) and isinstance(data[page], dict)):
        return None
    cur = data[page]
    for part in path.split('.'):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _set(data, page, path, value):
    while len(data) <= page:
        data.append({})
    if not isinstance(data[page], dict):
        data[page] = {}
    cur = data[page]
    parts = path.split('.')
    for part in parts[:-1]:
        if not isinstance(cur.get(part), dict):
            cur[part] = {}
        cur = cur[part]
    cur[parts[-1]] = value


# --------------------------------------------------------------------------------------------- niveaux en base
class Geography:
    """Tous les niveaux administratifs (lus une fois) : noms, parents, villages par canton."""

    def __init__(self):
        from administrativelevels.models import AdministrativeLevel
        self.levels = {row[0]: {'type': row[1], 'parent': row[2], 'name': row[3]}
                       for row in AdministrativeLevel.objects.values_list('id', 'type', 'parent_id', 'name')}
        self.villages = [i for i, lv in self.levels.items() if lv['type'] == 'Village']
        self.by_parent = {}
        for i in self.villages:
            self.by_parent.setdefault(self.levels[i]['parent'], []).append(i)
        self.norm_names = {i: norm(self.levels[i]['name']) for i in self.villages}
        self.exact_names = {}
        for i, name in self.norm_names.items():
            self.exact_names.setdefault(name, []).append(i)
        self.cantons_of = {}
        for i, lv in self.levels.items():
            if lv['type'] == 'Canton':
                self.cantons_of.setdefault(lv['parent'], []).append(i)

    def is_village(self, level_id):
        return level_id in self.levels and self.levels[level_id]['type'] == 'Village'

    def chain(self, level_id):
        """{niveau: id} : le niveau et ses parents."""
        out, cur, seen = {}, level_id, set()
        while cur in self.levels and cur not in seen:
            seen.add(cur)
            key = GEO_TYPES.get(self.levels[cur]['type'])
            if key and key not in out:
                out[key] = cur
            cur = self.levels[cur]['parent']
        return out

    def path_label(self, village_id):
        chain = self.chain(village_id)
        return ' › '.join(self.levels[chain[k]]['name'] for k in ('region', 'prefecture', 'commune', 'canton')
                          if k in chain)

    def find_level(self, adm_type, name, parent_id=None):
        """Identifiant du niveau de ce type et de ce nom (sous `parent_id` si donné), s'il est unique."""
        target = norm(name)
        if not target:
            return None
        hits = [i for i, lv in self.levels.items() if lv['type'] == adm_type and norm(lv['name']) == target
                and (parent_id is None or lv['parent'] == parent_id)]
        return hits[0] if len(hits) == 1 else None


# ------------------------------------------------------------------------------------------------------ analyse
def _context_level(data, geo, key, adm_type, geography, parent_id=None):
    """(id, nom affiché) du canton / de la commune de la saisie, si retrouvé en base."""
    field = geo.get(key)
    if not field:
        return None, ''
    raw = _get(data, field['page'], field['path'])
    level_id = _as_id(raw)
    if level_id and level_id in geography.levels and geography.levels[level_id]['type'] == adm_type:
        return level_id, geography.levels[level_id]['name']
    name = field['labels'].get(str(raw).strip(), raw) if raw not in (None, '') else ''
    found = geography.find_level(adm_type, name, parent_id) if name else None
    return found, str(name or '')


def _matches(reference, geography, pool, minimum=MIN_SIMILARITY, scope=None):
    """{village: ressemblance} des villages au nom proche de `reference` (et de tous ceux de `pool`) ; avec
    `scope`, la ressemblance approchée n'est cherchée que parmi ces villages (les noms exacts partout)."""
    ref = norm(reference)
    out = {}
    if not ref:
        return out
    for vid in geography.exact_names.get(ref, ()):
        out[vid] = 1.0
    for vid in (geography.norm_names if scope is None else scope):
        name = geography.norm_names.get(vid)
        if name is None or vid in out:
            continue
        in_pool = vid in pool
        if not in_pool and abs(len(name) - len(ref)) > max(3, len(ref) // 2):
            continue
        matcher = difflib.SequenceMatcher(None, ref, name)
        if not in_pool and (matcher.real_quick_ratio() < minimum or matcher.quick_ratio() < minimum):
            continue
        ratio = matcher.ratio()
        if in_pool or ratio >= minimum:
            out[vid] = ratio
    return out


def title_names(title, skip_names=()):
    """Noms possibles tirés du titre de la saisie (souvent « canton_village_date » en minuscules) : suites de 1 à
    TITLE_MAX_WORDS mots, sans les nombres (date, heure) ni, une fois, le nom du canton / de la commune."""
    words = re.split(r'[\W_]+', unicodedata.normalize('NFKD', str(title or '')).encode('ascii', 'ignore')
                     .decode().lower())
    segments, current = [], []
    for word in words:
        if not word or word.isdigit():
            if current:
                segments.append(current)
            current = []
        else:
            current.append(word)
    if current:
        segments.append(current)
    for name in skip_names:                       # le canton n'est pas le village (sauf s'il est répété)
        target = norm(name).split()
        if not target:
            continue
        for n, seg in enumerate(segments):
            at = next((i for i in range(len(seg) - len(target) + 1) if seg[i:i + len(target)] == target), None)
            if at is not None:
                segments[n:n + 1] = [part for part in (seg[:at], seg[at + len(target):]) if part]
                break
    out = []
    for seg in segments:
        for size in range(1, TITLE_MAX_WORDS + 1):
            for i in range(len(seg) - size + 1):
                name = ' '.join(seg[i:i + size])
                if len(name.replace(' ', '')) >= 3 and name not in out:
                    out.append(name)
    return out


def candidates(reference_name, canton_id, commune_id, geography, keep_id=None, title=None, skip_names=()):
    """Villages proposés, du plus probable au moins probable :
    [{id, name, path, score, exact, same_canton, current, title_hint}].
    Sans bonne proposition (score < GOOD_SCORE) pour `reference_name`, les noms tirés du titre de la saisie
    (`title`) sont essayés aussi ; `title_hint` = le morceau du titre qui a donné le village."""
    pool = set(geography.by_parent.get(canton_id, [])) if canton_id else set()
    sims = _matches(reference_name, geography, pool)
    hints = {}

    def bonus(vid):
        village_canton = geography.levels[vid]['parent']
        village_commune = geography.levels.get(village_canton, {}).get('parent')
        return (CANTON_BONUS if canton_id and village_canton == canton_id else 0.0)             + (COMMUNE_BONUS if commune_id and village_commune == commune_id else 0.0)

    if title and not any(sim + bonus(vid) >= GOOD_SCORE for vid, sim in sims.items()):
        # canton / commune connus : nom approché cherché parmi leurs villages seulement (rapide, moins de bruit)
        scope = None
        if canton_id or commune_id:
            scope = set(pool)
            for canton in (geography.cantons_of.get(commune_id, ()) if commune_id else ()):
                scope.update(geography.by_parent.get(canton, ()))
        for name in title_names(title, skip_names):
            for vid, sim in _matches(name, geography, pool, TITLE_MIN_SIMILARITY, scope).items():
                if sim >= TITLE_MIN_SIMILARITY and sim > sims.get(vid, -1.0):
                    sims[vid], hints[vid] = sim, name
    scored = bool(norm(reference_name)) or bool(hints)
    if keep_id and geography.is_village(keep_id):
        sims.setdefault(keep_id, similarity(reference_name, geography.levels[keep_id]['name']))
    ids = set(sims) | pool
    out = []
    for vid in ids:
        same_canton = bool(canton_id) and geography.levels[vid]['parent'] == canton_id
        sim = sims.get(vid, 0.0) if scored else None
        if scored and sim < MIN_SIMILARITY and not same_canton and vid != keep_id:
            continue
        score = (sim or 0.0) + bonus(vid)
        out.append({'id': vid, 'name': geography.levels[vid]['name'], 'path': geography.path_label(vid),
                    'score': round(min(score, 1.0) * 100) if scored else None, 'exact': scored and sim == 1.0,
                    'same_canton': same_canton, 'current': vid == keep_id, 'title_hint': hints.get(vid, '')})
    out.sort(key=lambda c: (-(c['score'] or 0), not c['same_canton'], norm(c['name'])))
    return out[:MAX_CANDIDATES] if scored else out[:MAX_CANDIDATES * 3]


def _sure(cands, canton_id):
    """Proposition « sûre » : un seul village de même nom exact (dans le canton de la saisie s'il est connu ; un
    nom tiré du titre n'est sûr que dans le canton de la saisie)."""
    exact = [c for c in cands if c['exact'] and (c['same_canton'] or (not canton_id and not c['title_hint']))]
    return exact[0]['id'] if len(exact) == 1 else None


def analyze(form, submissions, geography=None):
    """Valeurs de village à revoir : [{submission, value, recorded_name, problem, db_name, canton, commune,
    candidates, sure}] ; `None` si le formulaire n'a pas de champ village."""
    geo = geo_fields(form.form or [])
    if 'village' not in geo:
        return None
    geography = geography or Geography()
    field = geo['village']
    issues = []
    for submission in submissions:
        raw = _get(submission.data, field['page'], field['path'])
        values = raw if isinstance(raw, list) else [raw]
        for value in values:
            if value in (None, '') or (isinstance(value, str) and not value.strip()):
                continue
            value_id = _as_id(value)
            recorded = field['labels'].get(str(value).strip())
            db_name = geography.levels[value_id]['name'] if value_id and geography.is_village(value_id) else None
            if value_id and db_name is not None:
                if not recorded or norm(recorded) == norm(db_name):
                    continue
                # Identifiant confirmé par un administrateur (village gardé malgré le changement de nom).
                if any(h.get('action') == 'village_relinked' and str(h.get('to')) == str(value_id)
                       for h in (submission.history or []) if isinstance(h, dict)):
                    continue
                problem = 'renamed'
            elif value_id:
                problem = 'unknown_id'
            else:
                problem, recorded = 'text', str(value).strip()
            commune_id, commune_name = _context_level(submission.data, geo, 'commune', 'Commune', geography)
            canton_id, canton_name = _context_level(submission.data, geo, 'canton', 'Canton', geography, commune_id)
            if canton_id and not commune_id:
                commune_id = geography.levels[canton_id]['parent']
            cands = candidates(recorded, canton_id, commune_id, geography,
                               keep_id=value_id if problem == 'renamed' else None, title=submission.title,
                               skip_names=[n for n in (canton_name, commune_name) if n])
            issues.append({
                'submission': submission, 'value': str(value), 'recorded_name': recorded or '', 'problem': problem,
                'db_name': db_name, 'canton_id': canton_id, 'canton': canton_name, 'commune': commune_name,
                'candidates': cands, 'sure': _sure(cands, canton_id) if problem != 'renamed' else None,
            })
    return issues


# ------------------------------------------------------------------------------------------------- correction
class RelinkError(Exception):
    pass


@transaction.atomic
def relink(submission, user, old_value, village_id, update_parents=True, geography=None):
    """Remplace la valeur `old_value` du champ village de la saisie par `village_id` ; avec `update_parents`,
    les champs région / préfecture / commune / canton de la saisie reçoivent les parents du village (même
    forme que la valeur en place : identifiant, ou nom si le champ contenait un nom)."""
    from coso_collect.models import CollectSubmission
    from coso_collect.services import _history, refresh_title
    geography = geography or Geography()
    if not geography.is_village(village_id):
        raise RelinkError('unknown_village')
    submission = CollectSubmission.objects.select_for_update().select_related('form').get(pk=submission.pk)
    geo = geo_fields(submission.form.form or [])
    if 'village' not in geo:
        raise RelinkError('no_village_field')
    field = geo['village']
    data = submission.data if isinstance(submission.data, list) else []
    current = _get(data, field['page'], field['path'])
    new_value = str(village_id)
    if isinstance(current, list):
        if old_value not in [str(v) for v in current]:
            raise RelinkError('changed')
        replaced = [new_value if str(v) == old_value else v for v in current]
        _set(data, field['page'], field['path'], list(dict.fromkeys(replaced)))
    else:
        if str(current if current is not None else '') != old_value:
            raise RelinkError('changed')
        _set(data, field['page'], field['path'], new_value)
    parents = {}
    if update_parents:
        chain = geography.chain(village_id)
        for key in ('region', 'prefecture', 'commune', 'canton'):
            if key in geo and key in chain and not geo[key]['multiple']:
                before = _get(data, geo[key]['page'], geo[key]['path'])
                as_name = before not in (None, '') and _as_id(before) is None
                after = geography.levels[chain[key]]['name'] if as_name else str(chain[key])
                if str(before if before is not None else '') != after:
                    _set(data, geo[key]['page'], geo[key]['path'], after)
                    parents[key] = {'from': before, 'to': after}
    submission.data = data
    _history(submission, 'village_relinked', user, field=field['path'], **{
        'from': old_value, 'to': new_value, 'to_name': geography.levels[village_id]['name'], 'parents': parents,
    })
    refresh_title(submission)
    submission.save()
    return submission

