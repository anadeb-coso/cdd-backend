"""Migration des enregistrements COSOCollect vers les tâches du cycle d'investissement.

Contexte : en production, des formulaires COSOCollect ont été créés AVANT les tâches du cycle
(« <nom de l'activité> / <nom de la tâche> »). Une fois les tâches créées et distribuées aux
facilitateurs (``sync_tasks``), les réponses et fichiers des enregistrements ENVOYÉS sont recopiés dans
le document CouchDB de la tâche jumelle (``form_response``, ``attachments``) :

- formulaire <-> tâche : titre du formulaire comparé à « activité / tâche » (texte normalisé, puis
  rapprochement approché au-delà d'un seuil), correspondances forcées possibles ;
- enregistrement d'un VILLAGE : le village de l'enregistrement, ou le village siège de son CVD (les tâches
  n'existent que sur les villages sièges) ;
- enregistrement d'un CANTON (pas de village renseigné) : tous les villages du canton ayant la tâche ;
- plusieurs enregistrements pour une même tâche et un même village : le plus récent l'emporte ;
- champs : même clé de premier niveau des deux côtés (les notes et les champs géographiques absents de la
  tâche sont ignorés) ; les champs photo / fichier deviennent des pièces jointes de la tâche, rapprochées
  par nom (défaut) ou par ordre ;
- la tâche est marquée achevée (``completed``), la validation n'est jamais touchée ; une tâche déjà
  remplie est écrasée par défaut (option ``overwrite=False`` pour la conserver) ;
- une tâche VALIDÉE n'est jamais modifiée (ni par défaut, ni avec ``force``), sauf ``force_validated`` : ses
  données sont alors remplacées et la validation reste acquise ;
- provenance écrite sur le document (``cosocollect_import`` + ``cosocollect_history``) : relancer la
  commande ne réécrit pas un document déjà à jour (sauf ``force``).

Aucun nouveau modèle (donc aucune migration de base à appliquer à la main) : le document CouchDB porte
l'état de la migration.
"""
import copy
import difflib
import hashlib
import json
import logging
import os
import re
import time
from urllib.parse import quote
from dataclasses import dataclass, field as dc_field
from datetime import datetime

from django.utils import timezone

from cdd.functions import normalize_text

from .fields import MEDIA_TYPES, field_type, leaf_fields, resolve
from .models import CollectAttachment, CollectForm, CollectSubmission

logger = logging.getLogger(__name__)

ATTACHMENTS_BY_NAME = 'name'
ATTACHMENTS_BY_ORDER = 'order'
FILES_COPY = 'copy'
FILES_LINK = 'link'

DEFAULT_MIN_SCORE = 0.85
# Écart minimal entre la meilleure et la deuxième tâche candidate pour accepter un rapprochement approché.
MIN_SCORE_MARGIN = 0.03
# Rapprochement approché : l'activité du titre doit aussi ressembler à celle de la tâche (le même nom de tâche peut
# exister sous plusieurs activités).
ACTIVITY_MIN_SCORE = 0.75
ATTACHMENT_MIN_SCORE = 0.75

DOC_IMPORT_KEY = 'cosocollect_import'
DOC_HISTORY_KEY = 'cosocollect_history'
# champs écrits par un import : leur état antérieur est gardé dans l'historique pour pouvoir annuler (`undo`)
UNDO_KEYS = ('form_response', 'attachments', 'support_attachments', 'completed', 'completed_date',
             'completed_history', 'last_updated', DOC_IMPORT_KEY)
UNDO_LEVELS = 5   # imports annulables par document (taille du document synchronisé sur le téléphone)
S3_PREFIX = 'task_form_attachments/cosocollect'

GEO_LEVELS = ('region', 'prefecture', 'commune', 'canton', 'village')

# Comptes dont les enregistrements sont importés (option de la page / --accounts) : par défaut les vrais FC seulement.
# Les tâches cibles restent celles des vrais FC (TargetIndex) ; ce filtre porte sur l'AUTEUR de l'enregistrement.
ACCOUNT_REAL_FC = 'real_fc'      # facilitateur communautaire, ni formation ni démonstration
ACCOUNT_REAL_FT = 'real_ft'      # facilitateur technique, ni formation ni démonstration
ACCOUNT_TRAINING = 'training'    # compte de formation (training_mode)
ACCOUNT_DEVELOP = 'develop'      # compte de démonstration / développement (develop_mode)
ACCOUNT_OTHERS = 'others'        # compte web sans facilitateur (ou auteur inconnu)
ACCOUNT_CATEGORIES = (ACCOUNT_REAL_FC, ACCOUNT_REAL_FT, ACCOUNT_TRAINING, ACCOUNT_DEVELOP, ACCOUNT_OTHERS)
DEFAULT_ACCOUNTS = (ACCOUNT_REAL_FC,)


# ---------------------------------------------------------------------------------------------------------------
# Textes
# ---------------------------------------------------------------------------------------------------------------
def norm(text):
    """Texte comparable : sans accents, casse ni ponctuation. La ponctuation devient une espace
    (« village/Recensement » = « village / Recensement », « l'existence » = « l existence »)."""
    return normalize_text(re.sub(r'[^\w\s]', ' ', str(text or '')))


def similarity(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def task_label(task):
    return f"{task.activity.name} / {task.name}"


def now_str():
    now = datetime.now()
    return f"{now.year}-{now.month}-{now.day} {now.hour}:{now.minute}:{now.second}"


# ---------------------------------------------------------------------------------------------------------------
# Formulaire <-> tâche
# ---------------------------------------------------------------------------------------------------------------
@dataclass
class FormMatch:
    form: object
    task: object = None
    method: str = ''          # exact | approx | forced | none | ambiguous
    score: float = 0.0
    candidates: list = dc_field(default_factory=list)   # [(score, task)] les meilleures


def activity_score(title_norm, task):
    """Ressemblance entre le début du titre (« <activité> / … ») et l'activité de la tâche."""
    act = norm(task.activity.name)
    return similarity(title_norm[:len(act)], act) if act else 1.0


def match_forms_to_tasks(forms, tasks, forced=None, min_score=DEFAULT_MIN_SCORE):
    """Rapproche chaque formulaire d'une tâche. ``forced`` = {form_id: task}."""
    forced = forced or {}
    tasks = list(tasks)
    keyed = [(norm(task_label(t)), t) for t in tasks]
    out = []
    for form in forms:
        if form.id in forced:
            out.append(FormMatch(form, forced[form.id], 'forced', 1.0))
            continue
        key = norm(form.title)
        exact = [t for k, t in keyed if k == key]
        if len(exact) == 1:
            out.append(FormMatch(form, exact[0], 'exact', 1.0))
            continue
        if len(exact) > 1:
            out.append(FormMatch(form, None, 'ambiguous', 1.0, [(1.0, t) for t in exact]))
            continue
        scored = sorted(((similarity(key, k), t) for k, t in keyed), key=lambda x: -x[0])[:3]
        best = scored[0] if scored else (0.0, None)
        second = scored[1][0] if len(scored) > 1 else 0.0
        if best[1] is not None and best[0] >= min_score and activity_score(key, best[1]) < ACTIVITY_MIN_SCORE:
            # même nom de tâche sous une AUTRE activité (ex. modules de formation) : jamais rapproché d'office
            out.append(FormMatch(form, None, 'other_activity', best[0], scored))
        elif best[1] is not None and best[0] >= min_score and best[0] - second >= MIN_SCORE_MARGIN:
            out.append(FormMatch(form, best[1], 'approx', best[0], scored))
        elif best[1] is not None and best[0] >= min_score:
            out.append(FormMatch(form, None, 'ambiguous', best[0], scored))
        else:
            out.append(FormMatch(form, None, 'none', best[0], scored))
    return out


# ---------------------------------------------------------------------------------------------------------------
# Lecture du formulaire COSOCollect
# ---------------------------------------------------------------------------------------------------------------
def _top_fields(form_pages):
    """[(page_index, key, prop, opts)] des champs de premier niveau, dans l'ordre d'affichage."""
    from dashboard.process_manager.tasks.form_design import _normalize_order
    out = []
    for page_index, page in enumerate(form_pages or []):
        if not isinstance(page, dict):
            continue
        props = (page.get('page') or {}).get('properties') or {}
        opts = (page.get('options') or {}).get('fields') or {}
        for key in _normalize_order((page.get('options') or {}).get('order'), props):
            out.append((page_index, key, props.get(key) or {}, opts.get(key) or {}))
    return out


def geo_level(key, opts):
    """Niveau géographique d'un champ (region … village) d'après sa source, sinon son nom."""
    source = (opts or {}).get('_source') or {}
    level = norm(source.get('level'))
    if level in GEO_LEVELS:
        return level
    k = norm(key)
    if k in GEO_LEVELS and (source or (opts or {}).get('dataset') is not None):
        return k
    return None


def geo_keys(form_pages):
    """{niveau: (page, clé)} des champs géographiques du formulaire. Un champ placé dans un groupe (ex. groupe
    « Localisation ») est trouvé aussi : sa clé est alors un chemin pointé (« localisation.village »). Les
    répétables ne sont pas parcourus (plusieurs lignes = pas une localisation unique)."""
    out = {}

    def walk(page_index, props, fields_opts, order, prefix):
        from dashboard.process_manager.tasks.form_design import _normalize_order
        for key in _normalize_order(order, props):
            prop, opts = props.get(key) or {}, (fields_opts or {}).get(key) or {}
            path = f'{prefix}{key}'
            level = geo_level(key, opts)
            if level and level not in out:
                out[level] = (page_index, path)
            elif prop.get('type') == 'object':
                walk(page_index, prop.get('properties') or {}, opts.get('fields') or {}, opts.get('order'), path + '.')

    for page_index, page in enumerate(form_pages or []):
        if isinstance(page, dict):
            walk(page_index, (page.get('page') or {}).get('properties') or {},
                 (page.get('options') or {}).get('fields') or {}, (page.get('options') or {}).get('order'), '')
    return out


def _page_value(data, page_index, key):
    """Valeur de `key` (clé, ou chemin pointé dans des groupes) sur la page `page_index`."""
    if not (isinstance(data, list) and 0 <= page_index < len(data) and isinstance(data[page_index], dict)):
        return None
    cur = data[page_index]
    for part in str(key).split('.'):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _as_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def submission_location(submission, geo, geography=None):
    """('village', id) | ('canton', id) | (None, None) — compatibilité ; cf. :func:`submission_locations`."""
    level, ids, _problem = submission_locations(submission, geo, geography)
    return (level, ids[0]) if level and ids else (None, None)


def submission_locations(submission, geo, geography=None):
    """Localisation d'un enregistrement : ``(niveau, [ids], problème)``.

    - village renseigné (identifiant, liste d'identifiants pour un choix multiple, ou NOM cherché parmi les villages
      du canton de l'enregistrement) -> ``('village', [ids], None)`` ;
    - village renseigné mais introuvable -> ``(None, [], 'village_unresolved')`` : JAMAIS traité comme un
      enregistrement de canton (il serait copié dans tous les villages du canton) ;
    - village vide, canton renseigné -> ``('canton', [id], None)`` ;
    - sinon ``(None, [], None)`` (sans localisation)."""
    data = submission.data
    canton_raw = _page_value(data, *geo['canton']) if 'canton' in geo else None
    canton = _as_int(canton_raw)
    if not canton and isinstance(canton_raw, str) and canton_raw.strip() and geography is not None:
        commune = _as_int(_page_value(data, *geo['commune'])) if 'commune' in geo else None
        canton = geography.canton_by_name(canton_raw, commune)     # canton saisi en texte
    if 'village' in geo:
        raw = _page_value(data, *geo['village'])
        values = raw if isinstance(raw, list) else [raw]
        values = [v for v in values if v not in (None, '') and not (isinstance(v, str) and not v.strip())]
        if values:
            ids, unresolved = [], False
            for v in values:
                vid = _as_int(v)
                if not vid and geography is not None and canton:
                    vid = geography.village_by_name(canton, v)
                if vid:
                    if vid not in ids:
                        ids.append(vid)
                else:
                    unresolved = True
            if ids and not unresolved:
                return 'village', ids, None
            return None, ids, 'village_unresolved'
    if canton:
        return 'canton', [canton], None
    if isinstance(canton_raw, str) and canton_raw.strip():
        return None, [], 'canton_unresolved'
    return None, [], None


def collect_values(form_pages, data):
    """{clé: valeur} des champs de premier niveau d'un enregistrement (première page qui porte la clé)."""
    out = {}
    for page_index, key, _prop, _opts in _top_fields(form_pages):
        if key in out:
            continue
        value = _page_value(data, page_index, key)
        if value is not None:
            out[key] = value
    return out


def _page_keys(page):
    return set(((page or {}).get('page') or {}).get('properties') or {}) if isinstance(page, dict) else set()


def align_pages(task_form, collect_form):
    """Page COSOCollect correspondant à chaque page de la tâche (index ou None).

    Une même clé peut figurer sur plusieurs pages (ex. tâche 6.2.1 : deux réunions avec les mêmes champs) :
    associer par clé seule recopierait la 1re réunion sur la 2e. Chaque page de la tâche prend la page COSOCollect
    non encore utilisée qui partage le plus de champs avec elle, en avançant dans l'ordre des pages (à égalité,
    la première qui suit la page précédemment retenue)."""
    collect_keys = [_page_keys(p) for p in (collect_form or [])]
    used, last, out = set(), -1, []
    for page in task_form or []:
        keys = _page_keys(page)
        candidates = [(len(keys & ck), j) for j, ck in enumerate(collect_keys) if j not in used and keys & ck]
        if not candidates:
            out.append(None)
            continue
        # plus de champs communs d'abord ; à égalité, la première page APRÈS la précédente, puis la première tout court
        _score, best = min(candidates, key=lambda c: (-c[0], 0 if c[1] > last else 1, c[1]))
        used.add(best)
        last = best
        out.append(best)
    return out


def values_by_task_page(task_form, collect_form, data):
    """[{clé: valeur}] : valeurs COSOCollect pour chaque page de la tâche (cf. :func:`align_pages`). Une clé absente
    de la page associée est cherchée ailleurs seulement si elle est UNIQUE dans le formulaire COSOCollect."""
    flat = collect_values(collect_form, data)
    counts = {}
    for p in collect_form or []:
        for k in _page_keys(p):
            counts[k] = counts.get(k, 0) + 1
    out = []
    for page, j in zip(task_form or [], align_pages(task_form, collect_form)):
        values = {}
        page_data = data[j] if j is not None and isinstance(data, list) and j < len(data) and isinstance(data[j], dict) else {}
        collect_page_keys = _page_keys(collect_form[j]) if j is not None else set()
        for key in _page_keys(page):
            if key in collect_page_keys:
                if page_data.get(key) is not None:
                    values[key] = page_data[key]
            elif counts.get(key) == 1 and key in flat:
                values[key] = flat[key]
        out.append(values)
    return out


def media_fields(form_pages):
    """[(chemin "$page.a.b", clé, libellé)] des champs photo / fichier, y compris dans un groupe (pas dans un
    répétable : plusieurs fichiers ne tiennent pas dans une seule pièce jointe de tâche)."""
    return [(f['path'], f['key'], f['label']) for f in leaf_fields(form_pages or [])
            if f['type'] in MEDIA_TYPES and not f['repeat_path']]


def repeat_media_fields(form_pages):
    """Libellés des champs photo / fichier placés dans un répétable (non repris, signalés)."""
    return [f['label'] for f in leaf_fields(form_pages or []) if f['type'] in MEDIA_TYPES and f['repeat_path']]


def _is_media_ref(value):
    return isinstance(value, dict) and 'attachment_id' in value


def _strip_media(value):
    """Copie de `value` sans les références de fichiers COSOCollect (groupes / répétables recopiés en bloc :
    un identifiant de pièce jointe COSOCollect n'a pas de sens dans une tâche)."""
    if _is_media_ref(value):
        return None
    if isinstance(value, dict):
        return {k: _strip_media(v) for k, v in value.items() if not _is_media_ref(v)}
    if isinstance(value, list):
        return [_strip_media(v) for v in value]
    return value


def _is_note(prop, opts=None):
    """Note d'information (texte affiché, sans valeur). `editable: false` seul ne suffit pas : il sert aussi
    aux champs calculés, qui ont une valeur à recopier."""
    return bool((prop or {}).get('_note'))


# ---------------------------------------------------------------------------------------------------------------
# Conversion des valeurs selon le schéma de la tâche
# ---------------------------------------------------------------------------------------------------------------
def _enum_values(prop):
    """Valeurs permises d'un choix simple / multiple (liste, ou clés d'un objet {valeur: libellé}), sinon None."""
    prop = prop or {}
    enum = prop.get('enum')
    if enum is None and prop.get('type') == 'array' and isinstance(prop.get('items'), dict):
        enum = prop['items'].get('enum')
    if isinstance(enum, dict):
        return list(enum.keys())
    if isinstance(enum, list):
        return enum
    return None


_NUM_RE = re.compile(r'^\s*[-+]?\d+([.,]\d+)?\s*$')


def coerce_value(value, prop, path, warnings):
    """`value` adaptée au schéma `prop` de la tâche (nombres, texte, choix sans tenir compte de la casse / des
    accents, groupes et répétables récursivement). Valeur inchangée si aucune conversion sûre n'existe ; les
    écarts sont ajoutés à `warnings`."""
    if value is None or not isinstance(prop, dict):
        return value
    ptype = prop.get('type')
    enum = _enum_values(prop)
    if ptype == 'object' and isinstance(value, dict):
        props = prop.get('properties') or {}
        return {k: (coerce_value(v, props[k], f'{path}.{k}', warnings) if k in props else v) for k, v in value.items()}
    if ptype == 'array':
        items = prop.get('items') if isinstance(prop.get('items'), dict) else {}
        if not isinstance(value, list):
            value = [value] if value not in ('', None) else []
        if items.get('type') == 'object':
            return [coerce_value(v, items, f'{path}.{i}', warnings) for i, v in enumerate(value)]
        if enum is not None:
            return [_coerce_choice(v, enum, path, warnings) for v in value]
        return value
    if enum is not None:
        return _coerce_choice(value, enum, path, warnings)
    if ptype in ('integer', 'number'):
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and _NUM_RE.match(value):
            num = float(value.replace(',', '.'))
            value = int(num) if num.is_integer() else num   # "12" -> 12 ; "12,5" -> 12.5
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        if ptype == 'integer' and isinstance(value, float):
            warnings.append(f'{path} : {value} n\'est pas un entier')
        if not isinstance(value, (int, float)):
            warnings.append(f'{path} : « {value} » n\'est pas un nombre')
        return value
    if ptype == 'string' and isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if ptype == 'boolean' and isinstance(value, str) and norm(value) in ('true', 'false', 'oui', 'non', 'yes', 'no'):
        return norm(value) in ('true', 'oui', 'yes')
    return value


def _coerce_choice(value, enum, path, warnings):
    if value in enum:
        return value
    by_norm = {norm(x): x for x in enum}
    hit = by_norm.get(norm(value))
    if hit is not None:
        return hit
    warnings.append(f'{path} : choix « {value} » absent de la tâche')
    return value


# ---------------------------------------------------------------------------------------------------------------
# Comparaison des champs (rapport)
# ---------------------------------------------------------------------------------------------------------------
def compare_fields(collect_form_pages, task_form, attachment_slots, attachments_by=ATTACHMENTS_BY_NAME):
    """Écarts entre le formulaire COSOCollect et celui de la tâche."""
    collect = {k: (p, o) for _i, k, p, o in _top_fields(collect_form_pages)}
    task = {k: (p, o) for _i, k, p, o in _top_fields(task_form)}
    geo = {k for k, (p, o) in collect.items() if geo_level(k, o)}
    # champs fichier de premier niveau (chemin "$p.clé") : deviennent des pièces jointes
    media = {path.split('.', 1)[1] for path, _k, _l in media_fields(collect_form_pages) if path.count('.') == 1}
    # groupe dont tous les champs sont des fichiers (devenus pièces jointes) : pas « non utilisé »
    for key, (prop, opts) in collect.items():
        leaves = [f for f in leaf_fields([{'page': {'type': 'object', 'properties': {key: prop}},
                                           'options': {'fields': {key: opts}, 'order': [key]}}])]
        if field_type(prop, opts) == 'group' and leaves and all(f['type'] in MEDIA_TYPES for f in leaves):
            media.add(key)
    copied = [k for k in task if k in collect and not _is_note(*task[k]) and k not in media]
    task_missing = [k for k in task if k not in collect and not _is_note(*task[k])]
    collect_unused = [k for k in collect if k not in task and k not in geo and k not in media
                      and not _is_note(*collect[k])]
    type_diff = []
    enum_diff = []
    for k in copied:
        a, b = collect[k][0], task[k][0]
        if field_type(a, collect[k][1]) != field_type(b, task[k][1]):
            type_diff.append(k)
        # choix COSOCollect absents de la liste de la tâche (même après casse / accents)
        ca, cb = _enum_values(a), _enum_values(b)
        if ca is not None and cb is not None:
            known = {norm(x) for x in cb}
            missing = [x for x in ca if norm(x) not in known]
            if missing:
                enum_diff.append(f"{k} ({', '.join(map(str, missing[:5]))})")
    pairs, unmatched = match_attachments(media_fields(collect_form_pages), attachment_slots, attachments_by)
    return {
        'copied': copied,
        'task_missing': task_missing,
        'collect_unused': collect_unused,
        'type_diff': type_diff,
        'enum_diff': enum_diff,
        'attachments': [(label, slot.get('name')) for (_p, _k, label), slot in pairs],
        'attachments_unmatched': [label for _p, _k, label in unmatched] + repeat_media_fields(collect_form_pages),
    }


# ---------------------------------------------------------------------------------------------------------------
# Pièces jointes
# ---------------------------------------------------------------------------------------------------------------
def match_attachments(fields, slots, by=ATTACHMENTS_BY_NAME):
    """Champs photo/fichier COSOCollect -> emplacements ``Task.attachments``.

    Renvoie ``([(champ, emplacement)], [champs sans emplacement])``."""
    slots = [s for s in (slots or []) if isinstance(s, dict) and s.get('name')]
    pairs, unmatched = [], []
    if by == ATTACHMENTS_BY_ORDER:
        for i, f in enumerate(fields):
            if i < len(slots):
                pairs.append((f, slots[i]))
            else:
                unmatched.append(f)
        return pairs, unmatched
    free = list(slots)
    pending = []
    for f in fields:  # 1) même nom (clé ou libellé)
        hit = next((s for s in free if norm(s['name']) in (norm(f[2]), norm(f[1]))), None)
        if hit:
            pairs.append((f, hit))
            free.remove(hit)
        else:
            pending.append(f)
    still = []
    for f in pending:  # 2) nom de la pièce jointe contenu en entier (mots complets) dans le libellé
        label = f' {norm(f[2])} '        # ex. « Télécharger le Liste des participants » -> « Liste des participants »
        inside = [s for s in free if norm(s['name']) and f' {norm(s["name"])} ' in label]
        if inside:
            hit = max(inside, key=lambda s: len(norm(s['name'])))   # le nom le plus précis
            pairs.append((f, hit))
            free.remove(hit)
        else:
            still.append(f)
    pending = still
    for f in pending:  # 3) nom approché
        scored = sorted(((max(similarity(f[2], s['name']), similarity(f[1], s['name'])), s) for s in free),
                        key=lambda x: -x[0])
        if scored and scored[0][0] >= ATTACHMENT_MIN_SCORE:
            pairs.append((f, scored[0][1]))
            free.remove(scored[0][1])
        else:
            unmatched.append(f)
    return pairs, unmatched


def stored_file_url(attachment, files_mode, cache, storage=None):
    """URL (en ligne) à écrire dans la tâche pour une pièce jointe COSOCollect.

    ``copy`` : copie dans ``task_form_attachments/cosocollect/...`` (le fichier de la tâche ne dépend plus du
    formulaire COSOCollect) ; repli sur le fichier d'origine si la copie échoue. ``link`` : fichier
    d'origine. Une même pièce jointe n'est copiée qu'une fois (``cache``)."""
    if attachment.id in cache:
        return cache[attachment.id]
    if storage is None:
        storage = attachment.file.storage
    url = None
    if files_mode == FILES_COPY:
        try:
            base = os.path.basename(attachment.name or attachment.file.name or 'fichier')
            base = re.sub(r'[^\w.\-]+', '_', base).strip('_')[:120] or 'fichier'
            path = f"{S3_PREFIX}/{attachment.form.uid}/{int(time.time() * 1000)}-{base}"
            with attachment.file.open('rb') as fh:
                saved = storage.save(path, fh)
            url = storage.url(saved)
        except Exception:
            logger.warning('COSOCollect -> tâche : copie impossible de %s, lien vers l\'original',
                           attachment.file.name, exc_info=True)
    if not url:
        # lien vers l'original, seulement s'il existe encore (jamais de lien mort dans la tâche)
        try:
            exists = attachment.file.storage.exists(attachment.file.name)
        except Exception:
            exists = True   # stockage injoignable pour la vérification : on garde le lien
        url = attachment.file.url if exists else None
    cache[attachment.id] = url
    return url


# ---------------------------------------------------------------------------------------------------------------
# Construction des données de la tâche
# ---------------------------------------------------------------------------------------------------------------
def build_form_response(task_form, values, existing, warnings=None):
    """``form_response`` de la tâche : réponse existante + valeurs COSOCollect de même clé, converties selon le
    schéma de la tâche (:func:`coerce_value` ; écarts ajoutés à ``warnings``).

    ``values`` : liste par page de la tâche (:func:`values_by_task_page`), ou un seul dictionnaire valable pour
    toutes les pages."""
    warnings = [] if warnings is None else warnings
    out = copy.deepcopy(existing) if isinstance(existing, list) else []
    copied = []
    per_page = values if isinstance(values, list) else None
    for page_index, page in enumerate(task_form or []):
        if not isinstance(page, dict):
            continue
        if per_page is not None:
            values = per_page[page_index] if page_index < len(per_page) else {}
        while len(out) <= page_index:
            out.append({})
        if not isinstance(out[page_index], dict):
            out[page_index] = {}
        props = (page.get('page') or {}).get('properties') or {}
        opts = (page.get('options') or {}).get('fields') or {}
        for key, prop in props.items():
            if _is_note(prop, opts.get(key)) or key not in values:
                continue
            if field_type(prop, opts.get(key)) in MEDIA_TYPES or _is_media_ref(values[key]):
                continue
            out[page_index][key] = coerce_value(_strip_media(copy.deepcopy(values[key])), prop, key, warnings)
            copied.append(key)
    return out, copied


def build_attachments(task_slots, doc_attachments, files):
    """Pièces jointes du document : ``files`` = [(emplacement, url, nom, mime)]."""
    out = copy.deepcopy(doc_attachments) if isinstance(doc_attachments, list) else []
    names = []
    for slot, url, name, mime in files:
        target_norm = norm(slot.get('name'))
        idx = next((i for i, s in enumerate(out) if isinstance(s, dict) and norm(
            s.get('name') if not isinstance(s.get('name'), dict) else s['name'].get('name')) == target_norm), None)
        if idx is None:
            entry = {k: v for k, v in slot.items()}
            order = slot.get('order')
            if isinstance(order, int) and order < len(out) and not (isinstance(out[order], dict) and out[order].get('name')):
                idx = order
                out[idx] = entry
            else:
                out.append(entry)
                idx = len(out) - 1
        entry = dict(out[idx]) if isinstance(out[idx], dict) else {'name': slot.get('name')}
        entry['name'] = slot.get('name')
        entry.setdefault('order', slot.get('order', idx))
        entry['attachment'] = {'uri': url, 'name': name}
        if mime:
            entry['type'] = mime
        out[idx] = entry
        names.append(slot.get('name'))
    return out, names


def _response_has_data(form_response):
    def filled(v):
        if v is None or v == '' or v == [] or v == {}:
            return False
        if isinstance(v, dict):
            return any(filled(x) for x in v.values())
        if isinstance(v, list):
            return any(filled(x) for x in v)
        return True
    return any(filled(p) for p in (form_response or []) if isinstance(p, dict))


def _attachments_have_files(attachments):
    for a in attachments or []:
        uri = ((a or {}).get('attachment') or {}).get('uri') if isinstance(a, dict) else None
        if uri:
            return True
    return False


def doc_is_filled(doc):
    return bool(doc.get('completed')) or _response_has_data(doc.get('form_response')) \
        or _attachments_have_files(doc.get('attachments'))


def content_hash(form_response, attachments):
    """Empreinte des réponses + fichiers des pièces jointes d'un document de tâche."""
    files = [((a.get('name') if isinstance(a, dict) else None),
              (((a.get('attachment') or {}).get('uri')) if isinstance(a, dict) else None))
             for a in (attachments or [])]
    raw = json.dumps({'r': form_response or [], 'a': files}, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha1(raw.encode('utf-8')).hexdigest()


def untouched_since_import(doc):
    """Vrai si les réponses et fichiers du document sont exactement ceux écrits par la précédente importation
    COSOCollect (empreinte du contenu, pas l'horodatage : une modification faite dans la même seconde que l'import
    produisait le même `last_updated`)."""
    info = doc.get(DOC_IMPORT_KEY) or {}
    if not info:
        return False
    if info.get('content_hash'):
        return info['content_hash'] == content_hash(doc.get('form_response'), doc.get('attachments'))
    return bool(info.get('last_updated')) and info.get('last_updated') == doc.get('last_updated')


def doc_conflicts(db, doc_id):
    """Révisions en conflit d'un document CouchDB (`?conflicts=true`) : un téléphone a synchronisé une
    modification concurrente ; CouchDB a choisi une version gagnante arbitraire. [] si aucune / illisible."""
    try:
        r = db.r_session.get(f"{db.database_url}/{quote(str(doc_id), safe='')}", params={'conflicts': 'true'})
        if r.status_code != 200:
            return []
        return (r.json() or {}).get('_conflicts') or []
    except Exception:
        return []


def submission_stamp(submission):
    """Empreinte des DONNÉES de l'enregistrement. Pas sa date de modification : une réouverture par un
    administrateur (`set_submission_editable`) change `updated_at` sans changer les données, et aurait réécrit la
    tâche (effaçant les corrections du facilitateur)."""
    raw = json.dumps(submission.data or [], sort_keys=True, default=str, ensure_ascii=False)
    return 'sha1:' + hashlib.sha1(raw.encode('utf-8')).hexdigest()


def submission_sort_key(submission):
    dt = submission.submitted_at or submission.updated_at or submission.created_at
    return dt or timezone.now()


# ---------------------------------------------------------------------------------------------------------------
# Cibles (documents CouchDB des facilitateurs)
# ---------------------------------------------------------------------------------------------------------------
@dataclass
class DocRef:
    facilitator: object
    db_name: str
    doc_id: str


class TargetIndex:
    """(tâche, village) -> documents de tâche des facilitateurs du projet, pour le cycle donné.

    Une requête par facilitateur (``sql_id`` dans la liste des tâches concernées). Facilitateurs actifs,
    hors comptes de démonstration / formation (cf. ``_find_facilitator_task_doc``)."""

    def __init__(self, nsc, project, cycle, tasks, facilitators=None, progress=None):
        from authentication.models import Facilitator
        self.nsc = nsc
        self.index = {}
        self.errors = []
        self._groups = {}
        task_ids = [t.id for t in tasks]
        if facilitators is None:
            facilitators = Facilitator.objects.filter(
                projects__in=[project.id], active=True, develop_mode=False, training_mode=False,
            ).distinct()
        cycle_couch_id = getattr(cycle, 'couch_id', None)
        if progress:
            facilitators = list(facilitators)
            progress('phase', phase='index', total=len(facilitators))
        for facilitator in facilitators:
            if progress:
                progress('step', current=facilitator.no_sql_db_name)
            try:
                db = nsc.get_db(facilitator.no_sql_db_name)
                docs = nsc.find_all(db, {'type': 'task', 'sql_id': {'$in': task_ids}},
                                    fields=['_id', 'sql_id', 'administrative_level_id', 'cycle_id'])
            except Exception as exc:  # base absente / injoignable
                self.errors.append((facilitator, str(exc)))
                continue
            for d in docs:
                if cycle_couch_id and d.get('cycle_id') and d.get('cycle_id') != cycle_couch_id:
                    continue
                key = (d.get('sql_id'), str(d.get('administrative_level_id')))
                self.index.setdefault(key, []).append(DocRef(facilitator, facilitator.no_sql_db_name, d['_id']))

    def refs(self, task, adl_id):
        refs = self.index.get((task.id, str(adl_id))) or []
        if task.id not in self._groups:
            self._groups[task.id] = set(task.groups_collectors.values_list('name', flat=True)) if task.pk else set()
        groups = self._groups[task.id]
        if not groups or len(refs) <= 1:
            return refs
        from authentication import FACILITATORS_TYPES_WITH_GROUP_NAME
        types = {FACILITATORS_TYPES_WITH_GROUP_NAME.get(g) for g in groups}
        kept = [r for r in refs if r.facilitator.facilitator_type in types]
        return kept or refs

    def has(self, task, adl_id):
        return bool(self.index.get((task.id, str(adl_id))))


class Geography:
    """Villages sièges et villages des cantons (base ``mis``), avec cache."""

    def __init__(self):
        from administrativelevels.models import AdministrativeLevel, CVD
        self.ADL = AdministrativeLevel
        self.CVD = CVD
        self._names = {}
        self._hq = {}
        self._canton_hq = {}
        self._canton_villages = {}

    def name(self, adl_id):
        if adl_id not in self._names:
            self._names[adl_id] = self.ADL.objects.using('mis').filter(id=adl_id).values_list(
                'name', flat=True).first() or str(adl_id)
        return self._names[adl_id]

    def cantons_under(self, adl_id):
        """Région, préfecture ou commune -> identifiants de ses cantons (descente par parent_id) ; [] sinon."""
        key = ('cantons_under', adl_id)
        if key not in self._hq:
            level_type = self.ADL.objects.using('mis').filter(id=adl_id).values_list('type', flat=True).first()
            depth = {'Region': 3, 'Prefecture': 2, 'Commune': 1}.get(level_type)
            ids = [adl_id] if depth else []
            for _ in range(depth or 0):
                ids = list(self.ADL.objects.using('mis').filter(parent_id__in=ids).values_list('id', flat=True))
            if ids:
                ids = list(self.ADL.objects.using('mis').filter(id__in=ids, type='Canton').values_list('id', flat=True))
            self._hq[key] = ids
        return self._hq[key]

    def is_canton(self, adl_id):
        key = ('is_canton', adl_id)
        if key not in self._hq:
            self._hq[key] = self.ADL.objects.using('mis').filter(id=adl_id, type='Canton').exists()
        return self._hq[key]

    def headquarters_of(self, village_id):
        if village_id not in self._hq:
            self._hq[village_id] = self.ADL.objects.using('mis').filter(id=village_id).values_list(
                'cvd__headquarters_village_id', flat=True).first()
        return self._hq[village_id]

    def canton_by_name(self, name, commune_id=None):
        """Identifiant du canton de ce nom (dans la commune si connue) ; None si absent ou ambigu."""
        key = ('cantons', commune_id)
        if key not in self._canton_villages:
            qs = self.ADL.objects.using('mis').filter(type='Canton')
            if commune_id:
                qs = qs.filter(parent_id=commune_id)
            by = {}
            for cid, cname in qs.values_list('id', 'name'):
                by.setdefault(norm(cname), []).append(cid)
            self._canton_villages[key] = by
        hits = self._canton_villages[key].get(norm(name)) or []
        return hits[0] if len(hits) == 1 else None

    def village_by_name(self, canton_id, name):
        """Identifiant du village de ce nom parmi les villages du canton (casse, accents, ponctuation ignorés) ;
        None si absent ou ambigu."""
        key = ('names', canton_id)
        if key not in self._canton_villages:
            rows = self.ADL.objects.using('mis').filter(parent_id=canton_id).values_list('id', 'name')
            by = {}
            for vid, vname in rows:
                by.setdefault(norm(vname), []).append(vid)
            self._canton_villages[key] = by
        hits = self._canton_villages[key].get(norm(name)) or []
        return hits[0] if len(hits) == 1 else None

    def canton_headquarters(self, canton_id):
        """Villages sièges des CVD du canton (seuls villages où les tâches sont distribuées)."""
        if canton_id in self._canton_hq:
            return self._canton_hq[canton_id]
        hq = set(self.CVD.objects.using('mis').filter(headquarters_village__parent_id=canton_id).values_list(
            'headquarters_village_id', flat=True))
        hq |= set(self.ADL.objects.using('mis').filter(parent_id=canton_id, cvd__isnull=False).values_list(
            'cvd__headquarters_village_id', flat=True))
        self._canton_hq[canton_id] = sorted(i for i in hq if i)
        return self._canton_hq[canton_id]

    def canton_villages(self, canton_id):
        """Villages du canton + villages sièges des CVD du canton (ids, sans doublon)."""
        if canton_id in self._canton_villages:
            return self._canton_villages[canton_id]
        ids = list(self.ADL.objects.using('mis').filter(parent_id=canton_id).values_list('id', flat=True))
        hq = self.CVD.objects.using('mis').filter(headquarters_village__parent_id=canton_id).values_list(
            'headquarters_village_id', flat=True)
        cvd_hq = self.ADL.objects.using('mis').filter(parent_id=canton_id, cvd__isnull=False).values_list(
            'cvd__headquarters_village_id', flat=True)
        seen, out = set(), []
        for i in list(ids) + list(hq) + list(cvd_hq):
            if i and i not in seen:
                seen.add(i)
                out.append(i)
        self._canton_villages[canton_id] = out
        return out


def resolve_targets(task, level, adl_id, index, geo):
    """Villages cibles (ayant le document de tâche) et villages sans document (en attente)."""
    if level == 'village':
        if index.has(task, adl_id):
            return [adl_id], []
        hq = geo.headquarters_of(adl_id)
        if hq and index.has(task, hq):
            return [hq], []
        return [], [hq or adl_id]
    if level == 'canton':
        villages = geo.canton_villages(adl_id)
        targets = [v for v in villages if index.has(task, v)]
        # villages sièges du canton où la tâche n'est pas (encore) distribuée : en attente
        missing = [v for v in geo.canton_headquarters(adl_id) if v not in targets]
        if not targets and not missing:
            missing = [adl_id]   # canton sans aucun village siège connu
        return targets, missing
    return [], []


# ---------------------------------------------------------------------------------------------------------------
# Plan et exécution
# ---------------------------------------------------------------------------------------------------------------
@dataclass
class PlanItem:
    form: object
    task: object
    adl_id: int
    submission: object
    level: str
    source_id: int
    refs: list
    competing: int = 0      # enregistrements plus anciens écartés pour cette cible


@dataclass
class Pending:
    form: object
    task: object
    submission: object
    level: str
    source_id: int
    reason: str


@dataclass
class Outcome:
    item: PlanItem
    ref: DocRef
    status: str            # written | dry_run | skipped_filled | unchanged | missing_doc | error
    detail: str = ''
    fields: list = dc_field(default_factory=list)
    attachments: list = dc_field(default_factory=list)
    warnings: list = dc_field(default_factory=list)   # valeurs non converties, fichiers introuvables…


# Statuts des enregistrements recopiés par défaut : envoyés seulement (option --status pour les autres).
DEFAULT_STATUSES = (CollectSubmission.STATUS_SUBMITTED,)


def facilitator_categories(facilitator):
    """Catégories de compte d'un facilitateur (cf. ACCOUNT_CATEGORIES) ; aucun facilitateur : « autres »."""
    if facilitator is None:
        return {ACCOUNT_OTHERS}
    cats = set()
    if facilitator.training_mode:
        cats.add(ACCOUNT_TRAINING)
    if facilitator.develop_mode:
        cats.add(ACCOUNT_DEVELOP)
    if cats:
        return cats
    return {ACCOUNT_REAL_FT if facilitator.facilitator_type == 'technical_facilitator' else ACCOUNT_REAL_FC}


class AccountClassifier:
    """Catégories de compte de l'AUTEUR d'un enregistrement : son facilitateur, ou celui de son compte web (règle
    « même personne », authentication/identity.py) ; un compte web sans facilitateur est « autres ». Un compte à la
    fois de formation et de démonstration relève des deux catégories (retenu si l'une est choisie)."""

    def __init__(self):
        self._by_user = {}

    def author_facilitator(self, sub):
        if sub.facilitator_id:
            return sub.facilitator
        if not sub.user_id:
            return None
        if sub.user_id not in self._by_user:
            from authentication.identity import facilitator_of_user
            self._by_user[sub.user_id] = facilitator_of_user(sub.user) if sub.user else None
        return self._by_user[sub.user_id]

    def categories(self, sub):
        return facilitator_categories(self.author_facilitator(sub))

    def allowed(self, sub, accounts):
        return bool(self.categories(sub) & set(accounts or DEFAULT_ACCOUNTS))


def submitted_submissions(form, statuses=None):
    """Enregistrements du formulaire aux statuts donnés (défaut : envoyés)."""
    return list(CollectSubmission.objects.filter(form=form, status__in=list(statuses or DEFAULT_STATUSES))
                .select_related('user', 'facilitator'))


def expand_adl_filter(ids, geo=None):
    """Filtre --village : identifiants de villages, cantons, communes, préfectures et/ou régions -> ensemble
    d'identifiants à comparer aux villages cibles et sources. Un canton vaut pour lui-même (enregistrements de niveau
    canton), ses villages et les villages sièges de ses CVD (enregistrements de niveau village du canton). Une
    commune, une préfecture ou une région vaut pour tous ses cantons, chacun comme ci-dessus."""
    geo = geo or Geography()
    out = set()
    for raw in ids or []:
        try:
            adl_id = int(raw)
        except (TypeError, ValueError):
            continue
        out.add(adl_id)
        cantons = [adl_id] if geo.is_canton(adl_id) else geo.cantons_under(adl_id)
        for canton_id in cantons:
            out.add(canton_id)
            out.update(geo.canton_villages(canton_id))
    return out


def build_plan(matches, index, geo, only_adl_ids=None, statuses=None, accounts=None):
    """Enregistrements (envoyés, ou aux statuts ``statuses``) des comptes ``accounts`` (défaut : vrais FC) ->
    éléments à écrire (le plus récent par tâche et village) + en attente. Un enregistrement d'un compte non retenu
    est écarté AVANT le choix du plus récent (il ne peut pas passer devant celui d'un compte retenu) et listé en
    attente (raison ``account_excluded:<catégories>``)."""
    best = {}       # (task_id, adl) -> PlanItem
    pending = []
    accounts = set(accounts or DEFAULT_ACCOUNTS)
    classifier = AccountClassifier()
    # --village : villages, cantons, communes, préfectures, régions (un niveau vaut pour tous ses villages) ; s'applique aussi aux « en attente »
    only = expand_adl_filter(only_adl_ids, geo) if only_adl_ids else None

    def wanted(*ids):
        return only is None or any(i in only for i in ids if i is not None)

    for m in matches:
        if not m.task:
            continue
        keys = geo_keys(m.form.form)
        for sub in submitted_submissions(m.form, statuses):
            level, source_ids, problem = submission_locations(sub, keys, geo)
            if not classifier.allowed(sub, accounts):
                reason = 'account_excluded:' + '+'.join(sorted(classifier.categories(sub)))
                if not level:
                    if only is None:
                        pending.append(Pending(m.form, m.task, sub, '', None, reason))
                    continue
                for source_id in source_ids:
                    hq = geo.headquarters_of(source_id) if only is not None and level == 'village' else None
                    if wanted(source_id, hq):
                        pending.append(Pending(m.form, m.task, sub, level, source_id, reason))
                continue
            if not level:
                if only is None or (source_ids and wanted(*source_ids)):
                    pending.append(Pending(m.form, m.task, sub, '', None, problem or 'no_location'))
                continue
            for source_id in source_ids:
                targets, missing = resolve_targets(m.task, level, source_id, index, geo)
                for adl in missing:
                    if wanted(adl, source_id):
                        pending.append(Pending(m.form, m.task, sub, level, source_id, f'no_task_doc:{adl}'))
                for adl in targets:
                    if not wanted(adl, source_id):
                        continue
                    key = (m.task.id, adl)
                    current = best.get(key)
                    if current is None or submission_sort_key(sub) > submission_sort_key(current.submission):
                        competing = (current.competing + 1) if current else 0
                        best[key] = PlanItem(m.form, m.task, adl, sub, level, source_id,
                                             index.refs(m.task, adl), competing)
                    elif current.submission.pk != sub.pk:
                        current.competing += 1
    return sorted(best.values(), key=lambda i: (i.task.id, i.adl_id)), pending


def _author(sub):
    if sub.facilitator_id and sub.facilitator:
        return {'name': sub.facilitator.name or sub.facilitator.username, 'email': sub.facilitator.email,
                'facilitator_sql_id': sub.facilitator_id}
    if sub.user_id and sub.user:
        return {'name': (f"{sub.user.first_name} {sub.user.last_name}".strip() or sub.user.username),
                'email': sub.user.email, 'user_id': sub.user_id}
    return None


def _attachment_files(item, attachments_by, files_mode, file_cache, storage=None, warnings=None):
    """[(emplacement, url, nom, mime)] + libellés non rapprochés. Fichier absent -> avertissement."""
    warnings = [] if warnings is None else warnings
    form_pages = item.form.form
    pairs, unmatched = match_attachments(media_fields(form_pages), item.task.attachments, attachments_by)
    out = []
    for (path, _key, _label), slot in pairs:
        value = resolve(item.submission.data, path)
        att_id = _as_int((value or {}).get('attachment_id')) if isinstance(value, dict) else None
        if not att_id:
            continue
        att = CollectAttachment.objects.filter(id=att_id, form=item.form).select_related('form').first()
        if not att or not att.file:
            warnings.append(f"fichier « {slot.get('name')} » : pièce jointe COSOCollect {att_id} introuvable")
            continue
        url = stored_file_url(att, files_mode, file_cache, storage)
        if not url:
            warnings.append(f"fichier « {slot.get('name')} » : {att.file.name} absent du stockage")
            continue
        out.append((slot, url, att.name or (value or {}).get('name') or '', att.mime_type or (value or {}).get('mime')))
    return out, [label for _p, _k, label in unmatched]


def _cap_undo_backups(history, keep=None):
    """Ne garde la sauvegarde (``previous``) que des ``keep`` derniers imports actifs : le document de tâche est
    synchronisé sur le téléphone, il ne doit pas grossir à chaque réimport. Au-delà, ``--undo`` s'arrête
    (« sans sauvegarde »)."""
    keep = UNDO_LEVELS if keep is None else keep
    active = [e for e in history if isinstance(e, dict) and e.get('action', 'import') == 'import'
              and not e.get('undone') and 'previous' in e]
    for entry in active[:-keep] if keep else active:
        entry.pop('previous', None)
        entry['previous_dropped'] = True


def apply_item(nsc, item, ref, geo, *, overwrite=True, force=False, attachments_by=ATTACHMENTS_BY_NAME,
               files_mode=FILES_COPY, file_cache=None, dry_run=True, storage=None, force_validated=False):
    """Écrit (ou simule) un enregistrement dans un document de tâche."""
    file_cache = {} if file_cache is None else file_cache
    try:
        db = nsc.get_db(ref.db_name)
        doc = db[ref.doc_id]  # chauffe le cache local de `db` (cf. _find_facilitator_task_doc)
        doc.fetch()           # ... mais relit toujours la version en base (le cache peut être périmé)
    except Exception as exc:
        return Outcome(item, ref, 'missing_doc', str(exc))
    conflicts_before = doc_conflicts(db, ref.doc_id)

    sub = item.submission
    stamp = submission_stamp(sub)
    info = doc.get(DOC_IMPORT_KEY) or {}
    # Envoi déjà importé : jamais réécrit, même si le facilitateur a corrigé la tâche depuis (ses corrections
    # priment) — sauf `force`. Seul un NOUVEL envoi (ou une modification de l'enregistrement) réécrit.
    if not force and info.get('submission_uuid') == str(sub.uuid) and info.get('submission_stamp') == stamp:
        return Outcome(item, ref, 'unchanged')
    # Tâche validée : jamais modifiée, quels que soient `overwrite` / `force`, sauf `force_validated`.
    if doc.get('validated') is True and not force_validated:
        return Outcome(item, ref, 'skipped_validated')
    if not overwrite and doc_is_filled(doc) and not untouched_since_import(doc):
        return Outcome(item, ref, 'skipped_filled')

    values = values_by_task_page(item.task.form, item.form.form, sub.data)
    warnings = []
    if conflicts_before:
        warnings.append(f'document déjà en conflit CouchDB ({len(conflicts_before)} version(s) concurrente(s)) : '
                        'à vérifier sur le téléphone du facilitateur')
    response, copied = build_form_response(item.task.form, values, doc.get('form_response'), warnings)

    # Aucun champ commun ni fichier : formulaire très probablement rapproché de la MAUVAISE tâche (ex. --map erroné).
    # On n'écrit rien (sinon la tâche serait marquée achevée sans données). Exception : tâche sans champ à remplir.
    task_has_fields = any(not _is_note(p) for page in (item.task.form or []) if isinstance(page, dict)
                          for p in ((page.get('page') or {}).get('properties') or {}).values())
    has_files = any(isinstance(resolve(sub.data, path), dict)
                    for (path, _k, _l), _s in match_attachments(media_fields(item.form.form), item.task.attachments,
                                                                attachments_by)[0])
    if task_has_fields and not copied and not has_files:
        return Outcome(item, ref, 'no_common_fields', 'aucun champ commun avec la tâche : vérifier le rapprochement')

    if dry_run:
        pairs, unmatched = match_attachments(media_fields(item.form.form), item.task.attachments, attachments_by)
        names = [slot.get('name') for (path, _k, _l), slot in pairs if isinstance(resolve(sub.data, path), dict)]
        flags = [flag for flag, on in (('validated', doc.get('validated') is True),
                                       ('filled', doc_is_filled(doc))) if on]
        return Outcome(item, ref, 'dry_run', ','.join(flags), copied, names, warnings)

    files, _unmatched = _attachment_files(item, attachments_by, files_mode, file_cache, storage, warnings)
    attachments, att_names = build_attachments(item.task.attachments, doc.get('attachments'), files)

    stamp_now = now_str()
    author = _author(sub)
    source_name = geo.name(item.source_id) if item.source_id else ''
    updates = {
        'form_response': response,
        'last_updated': stamp_now,
        DOC_IMPORT_KEY: {
            'form_id': item.form.id,
            'form_title': item.form.title,
            'submission_uuid': str(sub.uuid),
            'submission_stamp': stamp,
            'submission_updated_at': sub.updated_at.isoformat() if sub.updated_at else '',
            'source_level': item.level,
            'source_administrative_level_id': item.source_id,
            'source_label': source_name,
            'author': author,
            'date': stamp_now,
            'last_updated': stamp_now,
            # empreinte du contenu écrit : sert à savoir si le facilitateur a modifié la tâche depuis
            'content_hash': content_hash(response, attachments if files else doc.get('attachments')),
        },
    }
    if files:
        updates['attachments'] = attachments
        updates['support_attachments'] = True
    history = list(doc.get(DOC_HISTORY_KEY) or [])
    history.append({
        'date': stamp_now, 'form_id': item.form.id, 'form_title': item.form.title,
        'submission_uuid': str(sub.uuid), 'source_level': item.level, 'source_label': source_name,
        'author': author, 'fields': copied, 'attachments': att_names,
        'overwritten': doc_is_filled(doc) and not untouched_since_import(doc),
        # état AVANT cet import : permet `--undo` (clé absente du document = absente d'ici)
        'previous': {k: copy.deepcopy(doc[k]) for k in UNDO_KEYS if k in doc},
    })
    _cap_undo_backups(history)
    updates[DOC_HISTORY_KEY] = history
    if not doc.get('completed'):
        updates['completed'] = True
        updates['completed_date'] = doc.get('completed_date') or stamp_now
        completed_history = list(doc.get('completed_history') or [])
        completed_history.insert(0, {'type': 'completed', 'date': stamp_now, 'facilitator': author,
                                     'cosocollect': True})
        updates['completed_history'] = completed_history

    result = nsc.update_doc_uncontrolled(db, doc['_id'], updates)
    if result and not conflicts_before and doc_conflicts(db, ref.doc_id):
        warnings.append("conflit CouchDB apparu à l'écriture : vérifier la tâche sur le téléphone du facilitateur")
    if not result:  # update_doc_uncontrolled avale les erreurs et renvoie {}
        return Outcome(item, ref, 'error', 'CouchDB update failed (document modifié en même temps ? relancer)',
                       copied, att_names, warnings)
    return Outcome(item, ref, 'written', '', copied, att_names, warnings)


def run(project, cycle, forms, *, forced=None, min_score=DEFAULT_MIN_SCORE, overwrite=True, force=False,
        attachments_by=ATTACHMENTS_BY_NAME, files_mode=FILES_COPY, dry_run=True, only_adl_ids=None,
        nsc=None, facilitators=None, storage=None, geo=None, force_validated=False, only_task_ids=None,
        progress=None, statuses=None, accounts=None):
    """Point d'entrée : rapprochement, plan, écriture. Renvoie un dict de résultats (pour le rapport).

    ``accounts`` : catégories de compte (ACCOUNT_CATEGORIES) dont les enregistrements sont importés ; défaut
    DEFAULT_ACCOUNTS (vrais FC).

    ``progress(event, **info)`` (facultatif, page « Import vers les tâches ») : ``phase`` (phase=index|write,
    total=…) puis un ``step`` par base parcourue / par document traité (current=…, status=…)."""
    from process_manager.models import Task
    if nsc is None:
        from no_sql_client import NoSQLClient
        nsc = NoSQLClient()
    tasks = list(Task.objects.filter(project=project, cycles=cycle).select_related('activity', 'phase'))
    matches = match_forms_to_tasks(forms, tasks, forced, min_score)
    if only_task_ids:
        matches = [m for m in matches if m.task is not None and m.task.id in set(only_task_ids)]
    matched_tasks = list({m.task.id: m.task for m in matches if m.task}.values())
    index = TargetIndex(nsc, project, cycle, matched_tasks, facilitators, progress=progress)
    geo = geo or Geography()
    items, pending = build_plan(matches, index, geo, only_adl_ids, statuses, accounts)
    outcomes = []
    file_cache = {}
    if progress:
        progress('phase', phase='write', total=sum(len(item.refs) for item in items))
    for item in items:
        if not item.refs:
            continue
        for ref in item.refs:
            try:
                outcomes.append(apply_item(
                    nsc, item, ref, geo, overwrite=overwrite, force=force, attachments_by=attachments_by,
                    files_mode=files_mode, file_cache=file_cache, dry_run=dry_run, storage=storage,
                    force_validated=force_validated,
                ))
            except Exception as exc:  # une cible en échec n'arrête pas le lot
                logger.exception('COSOCollect -> tâche : échec %s %s', item.task.id, item.adl_id)
                outcomes.append(Outcome(item, ref, 'error', str(exc)))
            if progress:
                progress('step', current=ref.db_name, status=outcomes[-1].status)
    return {
        'tasks': tasks, 'matches': matches, 'index': index, 'items': items, 'pending': pending,
        'outcomes': outcomes, 'geo': geo,
    }


# ---------------------------------------------------------------------------------------------------------------
# Annulation (`--undo`)
# ---------------------------------------------------------------------------------------------------------------
@dataclass
class UndoOutcome:
    ref: DocRef
    task_id: int
    adl_id: str
    status: str      # undone | dry_run | skipped_modified | skipped_validated | no_backup | error
    detail: str = ''


def _last_active_import(doc):
    """(index, entrée) du dernier import non annulé de l'historique COSOCollect du document, ou (None, None)."""
    history = doc.get(DOC_HISTORY_KEY) or []
    for i in range(len(history) - 1, -1, -1):
        entry = history[i]
        if isinstance(entry, dict) and entry.get('action', 'import') == 'import' and not entry.get('undone'):
            return i, entry
    return None, None


def restore_before_import(doc, idx, entry, reason=None):
    """Remet le document (cloudant, déjà `fetch()`é) dans l'état d'avant l'import `entry` (index `idx` de son
    historique COSOCollect) et l'enregistre. `reason` : motif noté dans l'entrée d'annulation."""
    previous = entry['previous']
    for key in UNDO_KEYS:
        if key in previous:
            doc[key] = copy.deepcopy(previous[key])
        else:
            doc.pop(key, None)
    history = list(doc.get(DOC_HISTORY_KEY) or [])
    history[idx] = dict(history[idx], undone=True)
    undo_entry = {'action': 'undo', 'date': now_str(), 'form_id': entry.get('form_id'),
                  'form_title': entry.get('form_title'), 'submission_uuid': entry.get('submission_uuid'),
                  'source_label': entry.get('source_label')}
    if reason:
        undo_entry['reason'] = reason
    history.append(undo_entry)
    doc[DOC_HISTORY_KEY] = history
    doc.save()


def undo(project, cycle, forms=None, *, dry_run=True, force=False, force_validated=False, only_adl_ids=None,
         nsc=None, facilitators=None, only_task_ids=None, progress=None):
    """Remet les tâches dans l'état d'avant leur DERNIER import COSOCollect (un niveau par appel).

    Ne touche que les documents portant une importation (``cosocollect_import``), des formulaires ``forms`` si
    donnés. Une tâche modifiée depuis l'import (empreinte du contenu) n'est restaurée qu'avec ``force`` ; une tâche
    validée qu'avec ``force_validated`` (la validation elle-même n'est jamais modifiée)."""
    from authentication.models import Facilitator
    if nsc is None:
        from no_sql_client import NoSQLClient
        nsc = NoSQLClient()
    if facilitators is None:
        facilitators = Facilitator.objects.filter(projects__in=[project.id], active=True, develop_mode=False,
                                                  training_mode=False).distinct()
    form_ids = {f.id for f in forms} if forms else None
    # un canton vaut pour ses villages (les documents de tâche sont toujours sur des villages)
    only = {str(a) for a in expand_adl_filter(only_adl_ids)} if only_adl_ids else None
    outcomes, errors = [], []
    if progress:
        facilitators = list(facilitators)
        progress('phase', phase='undo', total=len(facilitators))
    for facilitator in facilitators:
        if progress:
            progress('step', current=facilitator.no_sql_db_name)
        first_outcome = len(outcomes)
        try:
            db = nsc.get_db(facilitator.no_sql_db_name)
            rows = nsc.find_all(db, {'type': 'task', DOC_IMPORT_KEY: {'$exists': True}},
                                fields=['_id', 'sql_id', 'administrative_level_id', 'cycle_id', DOC_IMPORT_KEY])
        except Exception as exc:
            errors.append((facilitator, str(exc)))
            continue
        for row in rows:
            info = row.get(DOC_IMPORT_KEY) or {}
            if cycle.couch_id and row.get('cycle_id') and row['cycle_id'] != cycle.couch_id:
                continue
            if form_ids is not None and info.get('form_id') not in form_ids:
                continue
            adl = str(row.get('administrative_level_id'))
            if only_task_ids and row.get('sql_id') not in set(only_task_ids):
                continue
            if only and adl not in only:
                continue
            ref = DocRef(facilitator, facilitator.no_sql_db_name, row['_id'])
            out = UndoOutcome(ref, row.get('sql_id'), adl, 'error')
            outcomes.append(out)
            try:
                doc = db[row['_id']]
                doc.fetch()
                idx, entry = _last_active_import(doc)
                if entry is None or 'previous' not in entry:
                    out.status = 'no_backup'
                    continue
                if not force and not untouched_since_import(doc):
                    out.status = 'skipped_modified'
                    continue
                if doc.get('validated') is True and not force_validated:
                    out.status = 'skipped_validated'
                    continue
                if dry_run:
                    out.status = 'dry_run'
                    continue
                restore_before_import(doc, idx, entry)
                out.status = 'undone'
            except Exception as exc:  # une cible en échec n'arrête pas le lot
                out.status, out.detail = 'error', str(exc)
        if progress:
            for out in outcomes[first_outcome:]:
                progress('result', status=out.status)
    return {'outcomes': outcomes, 'errors': errors}
