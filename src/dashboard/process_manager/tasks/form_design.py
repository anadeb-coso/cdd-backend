"""
Spécification, validation et conversion XLSForm du format de formulaire de tâche
(`process_manager.models.Task.form`).

Un formulaire est une liste de "pages". Chaque page garde la forme historique
consommée par ``tcomb-json-schema`` / ``tcomb-form-native`` côté mobile :

    {
        "options": {"fields": { <name>: <field-options>, ... }},
        "page":    {"type": "object",
                    "properties": { <name>: <json-schema>, ... },
                    "required": [ <name>, ... ]},

        # --- extensions rétro-compatibles (toutes optionnelles) ---
        "rules":     [ { "when": <cond>, "then": [ {"action": <act>, "target": <path>} ] } ],
        "calculate": [ { "target": <path>, "expr": "<expression arithmétique>" } ],
        "messages":  { <name>: { "required": "...", "range": "...",
                                 "regex": "...", "type": "..." } }
    }

<cond>   = {"field": <path>, "op": <op>, "value": <any>}
         | {"all": [<cond>, ...]}
         | {"any": [<cond>, ...]}
<op>     = eq | ne | in | nin | gt | gte | lt | lte | contains | empty | notEmpty
<act>    = show | hide | require | optional | enable | disable
<path>   = "champ" | "groupe.champ" (chemin pointé, relatif à la page)
           préfixe "$<index>." autorisé UNIQUEMENT dans ``when.field`` pour viser
           une autre page (réponse déjà saisie).

Le compilateur "arbre d'édition -> format stocké" vit côté JS (builder). Ici on
se contente de VALIDER la structure finale reçue et d'assurer le round-trip
XLSForm (feuilles ``survey`` / ``choices`` / ``settings``).
"""

import ast
import copy
import io

CONDITION_OPERATORS = {
    "eq", "ne", "in", "nin", "gt", "gte", "lt", "lte",
    "contains", "empty", "notEmpty",
}
RULE_ACTIONS = {"show", "hide", "require", "optional", "enable", "disable"}

# Partage entre villages sièges (form builder web) : modes valides pour un
# champ marqué "share" — mêmes valeurs que Task.SHARE_MODE_* (hors "none", qui
# correspond simplement à l'ABSENCE du champ dans page["share"], cf. plus bas).
# Dupliqué ici plutôt qu'importé de process_manager.models.Task pour garder ce
# module découplé de Django/l'ORM (déjà le cas pour tout le reste du fichier).
SHARE_MODE_FIXED_CANTON = "fixed_canton"
SHARE_MODE_FACILITATOR_THEN_VALIDATOR = "facilitator_then_validator"
SHARE_MODE_VALIDATOR_ONLY = "validator_only"
SHARE_MODES = {SHARE_MODE_FIXED_CANTON, SHARE_MODE_FACILITATOR_THEN_VALIDATOR, SHARE_MODE_VALIDATOR_ONLY}
SHARE_MODE_DEFAULT = SHARE_MODE_FIXED_CANTON

# Types manipulés par le builder -> (json-schema, options tcomb) est reconstruit
# côté JS ; cette table sert au mapping XLSForm.
BUILDER_FIELD_TYPES = {
    "text", "note", "integer", "decimal", "number",
    "select_one", "select_multiple", "select_multiple_check",
    "date", "datetime", "time",
    "geopoint",
    "group", "repeat",
}

# Fonctions autorisées dans les expressions ``calculate``.
CALC_FUNCTIONS = {"sum", "min", "max", "round", "abs", "int", "float"}


class FormDesignError(Exception):
    """Erreur de validation d'un design de formulaire."""


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_form_design(form):
    """Valide et RÉPARE ``form`` (liste de pages au format stocké).

    Retourne ``(clean_form, errors)``. Les incohérences bénignes des
    formulaires historiques écrits à la main (entrée ``required`` orpheline,
    clé ``options.fields`` avec espace superflu ou sans propriété
    correspondante, message pour champ absent) sont corrigées silencieusement.
    On ne renvoie une erreur bloquante que pour ce qui casserait le rendu
    mobile ou la logique conditionnelle. ``errors`` vide -> ``clean_form``
    réutilisable tel quel pour ``Task.form``.
    """
    errors = []

    # Un formulaire absent / vide est valide (tâche sans formulaire).
    if form in (None, [], {}, ""):
        return [], []
    if not isinstance(form, list):
        return None, ["Le formulaire doit être une liste de pages."]

    form = copy.deepcopy(form)

    for p_index, page in enumerate(form):
        prefix = f"Page {p_index + 1}"
        if not isinstance(page, dict):
            errors.append(f"{prefix} : chaque page doit être un objet.")
            continue

        schema = page.get("page")
        if not isinstance(schema, dict) or schema.get("type") != "object":
            errors.append(f"{prefix} : 'page' doit être un JSON-schema objet.")
            continue

        properties = schema.get("properties")
        if not isinstance(properties, dict) or not properties:
            errors.append(f"{prefix} : 'page.properties' est vide.")
            continue

        # -- required : on retire les entrées orphelines --------------------
        req = schema.get("required")
        if isinstance(req, list):
            schema["required"] = [n for n in req if n in properties]

        # Un groupe qui contient au moins un champ requis doit lui-même être
        # requis (sinon tcomb le rend optionnel -> "groupe vide" passe).
        _ensure_group_required(schema)

        # -- options.fields / options.order : réalignés sur properties ------
        options = page.get("options")
        if isinstance(options, dict):
            if isinstance(options.get("fields"), dict):
                options["fields"] = _clean_options_fields(options["fields"], properties)
            if "order" in options:
                # PostgreSQL/jsonb ne conserve pas l'ordre des clés d'objet ->
                # `options.order` fait foi. On le rend complet (toutes les
                # propriétés, sans clé inconnue ni doublon) : tcomb-form-native
                # n'affiche QUE les champs listés dans `order`.
                options["order"] = _normalize_order(options.get("order"), properties)

        # -- rules : erreurs bloquantes (produites par le builder) --------
        for r_index, rule in enumerate(page.get("rules", []) or []):
            _validate_rule(rule, form, p_index, f"{prefix} règle {r_index + 1}", errors)

        # -- calculate : erreurs bloquantes ------------------------------
        _validate_calculate(page.get("calculate", []) or [], properties, prefix, errors)

        # -- messages : on élague les champs absents ---------------------
        msgs = page.get("messages")
        if isinstance(msgs, dict):
            page["messages"] = {
                k: v for k, v in msgs.items() if _resolve_local_path(k, properties)
            }

        # -- share : mode de partage marqué PAR CHAMP (villages sièges) -----
        # élagué sur les mêmes bases que `messages` ; dédupliqué, ordre stable.
        # Chaque entrée est {"path": <chemin pointé>, "mode": <mode>} — un champ
        # peut avoir son propre mode, indépendamment des autres champs de la
        # même tâche. Tolère les entrées historiques (chaîne nue = juste un
        # chemin, sans mode explicite) en leur affectant SHARE_MODE_DEFAULT.
        share = page.get("share")
        if isinstance(share, list):
            seen = set()
            clean_share = []
            for entry in share:
                if isinstance(entry, str):
                    path, mode = entry, SHARE_MODE_DEFAULT
                elif isinstance(entry, dict):
                    path, mode = entry.get("path"), entry.get("mode")
                else:
                    continue
                if not isinstance(path, str) or path in seen or not _resolve_local_path(path, properties):
                    continue
                if mode not in SHARE_MODES:
                    mode = SHARE_MODE_DEFAULT
                seen.add(path)
                clean_share.append({"path": path, "mode": mode})
            page["share"] = clean_share

        # -- choicesFrom : options d'un select_one/select_multiple construites --
        # dynamiquement à partir de la réponse d'un AUTRE select_one/select_multiple
        # — même page, autre page de la même tâche (chemin "$<index>.<chemin>",
        # même convention que `rules`/`when.field`), ou champ d'une AUTRE tâche
        # (``sourceTaskId``, non vérifiable ici — ce module reste découplé de
        # l'ORM, cf. commentaire en tête de fichier ; l'existence réelle de la
        # tâche source est vérifiée par la vue appelante). Élagué comme `share`
        # (repli silencieux, pas d'erreur bloquante) : une entrée invalide ne
        # doit pas empêcher d'enregistrer le reste du formulaire.
        choices_from = page.get("choicesFrom")
        if isinstance(choices_from, list):
            seen_targets = set()
            clean_choices_from = []
            for entry in choices_from:
                if not isinstance(entry, dict):
                    continue
                path = entry.get("path")
                source_path = entry.get("sourcePath")
                source_task_id = entry.get("sourceTaskId")

                if not isinstance(path, str) or path in seen_targets:
                    continue
                target_prop = _resolve_local_prop(path, properties)
                if target_prop is None or not _is_select_prop(target_prop):
                    continue

                if not isinstance(source_path, str) or not source_path:
                    continue

                try:
                    source_task_id = int(source_task_id) if source_task_id is not None else None
                except (TypeError, ValueError):
                    source_task_id = None

                if source_task_id is not None:
                    # Tâche différente : seule la forme "$<index>.<chemin>" est
                    # valide (les pages de la tâche source ne sont pas connues
                    # ici) — vérifié structurellement, pas résolu.
                    if not source_path.startswith("$"):
                        continue
                    head, _, rest = source_path[1:].partition(".")
                    if not head.isdigit() or not rest:
                        continue
                elif source_path.startswith("$"):
                    head, _, rest = source_path[1:].partition(".")
                    try:
                        source_page_index = int(head)
                    except ValueError:
                        continue
                    if not (0 <= source_page_index < len(form)):
                        continue
                    source_props = form[source_page_index]["page"].get("properties", {})
                    source_prop = _resolve_local_prop(rest, source_props) if rest else None
                    if source_prop is None or not _is_select_prop(source_prop):
                        continue
                else:
                    source_prop = _resolve_local_prop(source_path, properties)
                    if source_prop is None or not _is_select_prop(source_prop):
                        continue

                seen_targets.add(path)
                clean_choices_from.append({
                    "path": path, "sourceTaskId": source_task_id, "sourcePath": source_path,
                })
            page["choicesFrom"] = clean_choices_from

        # -- crossTaskVisibility : afficher/cacher un champ de CETTE page ------
        # en fonction de la valeur d'un champ d'une AUTRE tâche (jamais la même
        # tâche — ce cas est déjà couvert par `rules`/`when.field` avec le
        # préfixe "$<index>."). Mécanisme séparé de `rules`, résolu entièrement
        # côté écran mobile (aucune lecture CouchDB inter-tâches possible dans
        # le moteur synchrone `cdd-form-logic.js`) — cf. `crossTaskVisibility.ts`.
        # Même philosophie d'élagage silencieux que `choicesFrom` ci-dessus.
        cross_task_visibility = page.get("crossTaskVisibility")
        if isinstance(cross_task_visibility, list):
            seen_cv_targets = set()
            clean_cross_task_visibility = []
            for entry in cross_task_visibility:
                clean_entry = _clean_visibility_condition(entry, target_properties=properties)
                if clean_entry is None:
                    continue
                path = clean_entry.pop("path", None)
                if not isinstance(path, str) or path in seen_cv_targets:
                    continue
                if _resolve_local_prop(path, properties) is None:
                    continue
                seen_cv_targets.add(path)
                clean_entry["path"] = path
                clean_cross_task_visibility.append(clean_entry)
            page["crossTaskVisibility"] = clean_cross_task_visibility

    return (form if not errors else None), errors


def _valid_cross_task_source_path(source_path):
    """Vrai si ``source_path`` a la forme structurelle "$<index>.<chemin>"
    (chemin dans une AUTRE tâche — ses pages ne sont pas connues ici, donc
    seule la forme est vérifiée, jamais la résolution réelle, même principe
    que `choicesFrom` ci-dessus)."""
    if not isinstance(source_path, str) or not source_path.startswith("$"):
        return False
    head, _, rest = source_path[1:].partition(".")
    return head.isdigit() and bool(rest)


def _clean_visibility_condition(entry, target_properties=None, allow_same_task=False,
                                 allowed_actions=frozenset({"show", "hide"})):
    """Valide/nettoie une entrée de condition (``page["crossTaskVisibility"][i]``,
    ``Task.visibility_condition``, OU ``Task.attachments[i]["conditions"][j]``)
    — forme uniquement, jamais de vérification bloquante. Renvoie ``None`` si
    l'entrée est structurellement invalide.

    ``target_properties`` : si fourni (cas ``crossTaskVisibility``, cible = un
    champ de CETTE page), la clé ``"path"`` est conservée dans le résultat
    pour validation ultérieure par l'appelant (qui connaît, lui, le chemin
    réellement attendu) ; sans ``target_properties`` (cas
    ``Task.visibility_condition``/``attachments``, cible implicite), aucune
    clé ``"path"`` n'est produite ni attendue.

    ``allow_same_task`` : si ``True``, ``sourceTaskId`` peut être absent/``None``
    (= source dans LA MÊME tâche, résolue côté écran contre les réponses déjà
    saisies — cas ``Task.attachments``) ; sinon (comportement historique,
    ``crossTaskVisibility``/``visibility_condition``) ``sourceTaskId`` est
    TOUJOURS requis, contrairement à `choicesFrom`.

    ``allowed_actions`` : vocabulaire d'action accepté (``show``/``hide`` par
    défaut ; ``Task.attachments`` y ajoute ``require``/``optional``, cf.
    ``_clean_attachment_condition``)."""
    if not isinstance(entry, dict):
        return None

    source_task_id = entry.get("sourceTaskId")
    if source_task_id is None:
        if not allow_same_task:
            return None
    else:
        try:
            source_task_id = int(source_task_id)
        except (TypeError, ValueError):
            return None

    source_path = entry.get("sourcePath")
    if not _valid_cross_task_source_path(source_path):
        return None

    op = entry.get("op")
    if op not in CONDITION_OPERATORS:
        return None

    action = entry.get("action")
    if action not in allowed_actions:
        return None

    default_when_unknown = entry.get("defaultWhenUnknown")
    if default_when_unknown not in {"visible", "hidden"}:
        default_when_unknown = "hidden"

    clean = {
        "sourceTaskId": source_task_id,
        "sourcePath": source_path,
        "op": op,
        "value": entry.get("value"),
        "action": action,
        "defaultWhenUnknown": default_when_unknown,
    }
    if target_properties is not None and isinstance(entry.get("path"), str):
        clean["path"] = entry["path"]
    return clean


def validate_visibility_condition(cond):
    """Valide/nettoie ``Task.visibility_condition`` (condition de visibilité
    de LA TÂCHE ENTIÈRE, hors de ``form`` — mirroir task-level de
    ``crossTaskVisibility``, appelé depuis la vue de sauvegarde, pas depuis
    `validate_form_design`, même principe que ``share_mode``). Renvoie
    ``None`` si ``cond`` est vide/invalide (= "toujours visible", comportement
    historique), sinon l'entrée nettoyée (sans clé ``"path"``, la cible étant
    implicitement la tâche elle-même)."""
    if not cond:
        return None
    return _clean_visibility_condition(cond)


# Actions pertinentes pour une condition de pièce jointe (`Task.attachments`) :
# afficher/cacher le slot, ou le rendre obligatoire/facultatif — `enable`/
# `disable` (pertinent seulement pour un champ de formulaire éditable) n'a pas
# de sens ici, donc volontairement exclu de RULE_ACTIONS.
ATTACHMENT_CONDITION_ACTIONS = frozenset({"show", "hide", "require", "optional"})


def _clean_attachment_condition(entry):
    """Valide/nettoie une entrée de ``Task.attachments[i]["conditions"][j]`` —
    mirroir de `_clean_visibility_condition`, sauf que ``sourceTaskId`` peut
    être absent/``None`` (= champ de LA MÊME tâche, résolu côté écran mobile
    contre ``task.form_response`` — aucune lecture CouchDB nécessaire, cf.
    ``attachmentConditions.ts``) et que le vocabulaire d'action couvre aussi
    ``require``/``optional`` en plus de ``show``/``hide``."""
    return _clean_visibility_condition(
        entry, allow_same_task=True, allowed_actions=ATTACHMENT_CONDITION_ACTIONS,
    )


def validate_attachments(raw):
    """Valide/nettoie ``Task.attachments`` (pièces jointes façon kobocollect
    attendues pour cette tâche — slots ``{name, type, optional, order,
    conditions?}``, configurés depuis l'onglet "Pièces jointes" du Générateur
    de formulaire, PAS dans ``form``). Repli silencieux par entrée (même
    philosophie que `validate_form_design`/`choicesFrom`) : une pièce jointe
    ou une condition individuellement malformée est éliminée plutôt que de
    bloquer l'enregistrement du reste. Renvoie ``(clean_list, errors)`` —
    ``errors`` seulement si le payload lui-même n'est pas une liste."""
    if raw is None:
        return [], []
    if not isinstance(raw, list):
        return None, ["« attachments » doit être une liste."]

    clean = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        attach_type = entry.get("type")
        if not isinstance(attach_type, str) or not attach_type.strip():
            attach_type = "autre document"

        conditions = []
        for cond in entry.get("conditions") or []:
            clean_cond = _clean_attachment_condition(cond)
            if clean_cond is not None:
                conditions.append(clean_cond)

        slot = {
            "name": name.strip(),
            "type": attach_type,
            "optional": bool(entry.get("optional")),
        }
        if conditions:
            slot["conditions"] = conditions
        clean.append(slot)

    for order, slot in enumerate(clean):
        slot["order"] = order

    return clean, []


def _normalize_order(order, properties):
    """Liste d'ordre complète : les clés demandées d'abord (dédupliquées, sans
    clé absente de ``properties``), puis les clés manquantes. tcomb-form-native
    n'affiche que les champs listés -> `order` doit couvrir toutes les
    propriétés."""
    prop_keys = list(properties.keys()) if isinstance(properties, dict) else list(properties)
    seen, out = set(), []
    for key in order or []:
        if key in prop_keys and key not in seen:
            seen.add(key)
            out.append(key)
    for key in prop_keys:
        if key not in seen:
            out.append(key)
    return out


def _clean_options_fields(fields, properties):
    """Retourne une copie de ``fields`` limitée aux clés présentes dans
    ``properties`` (avec rattrapage des clés à espace superflu), en
    descendant récursivement dans les groupes / répétables."""
    out = {}
    for name, opts in fields.items():
        prop = properties.get(name)
        if prop is None and isinstance(name, str) and name.strip() in properties:
            name, prop = name.strip(), properties[name.strip()]
        if prop is None:
            continue
        if isinstance(opts, dict):
            sub_props = _sub_properties(prop)
            # groupe : options.fields ; répétable tcomb : options.item.fields
            if sub_props is not None and isinstance(opts.get("fields"), dict):
                opts = dict(opts)
                opts["fields"] = _clean_options_fields(opts["fields"], sub_props)
                if "order" in opts:
                    opts["order"] = _normalize_order(opts.get("order"), sub_props)
            if sub_props is not None and isinstance(opts.get("item"), dict) \
                    and isinstance(opts["item"].get("fields"), dict):
                opts = dict(opts)
                opts["item"] = dict(opts["item"])
                opts["item"]["fields"] = _clean_options_fields(opts["item"]["fields"], sub_props)
                if "order" in opts["item"]:
                    opts["item"]["order"] = _normalize_order(opts["item"].get("order"), sub_props)
        out[name] = opts
    return out


def _sub_properties(prop):
    """Retourne le dict properties enfant d'un schéma object / array<object>."""
    if not isinstance(prop, dict):
        return None
    if prop.get("type") == "object":
        return prop.get("properties") or {}
    if prop.get("type") == "array":
        items = prop.get("items") or {}
        if isinstance(items, dict) and items.get("type") == "object":
            return items.get("properties") or {}
    return None


def _has_required_leaf(obj_schema):
    """Vrai si ``obj_schema`` (type:object) a >= 1 feuille requise, en descendant
    dans les sous-groupes et les items de répétables."""
    props = obj_schema.get("properties") or {}
    req = set(obj_schema.get("required") or [])
    for name, prop in props.items():
        if not isinstance(prop, dict):
            continue
        if prop.get("type") == "object":
            if _has_required_leaf(prop):
                return True
        elif prop.get("type") == "array" and isinstance(prop.get("items"), dict) \
                and prop["items"].get("type") == "object":
            if _has_required_leaf(prop["items"]):
                return True
        elif name in req:
            return True
    return False


def _ensure_group_required(obj_schema):
    """Ajoute au ``required`` de ``obj_schema`` tout sous-groupe (type:object)
    contenant au moins une feuille requise. Récursif. Les répétables ne sont
    pas ajoutés d'office (``minItems`` gère le "au moins N")."""
    props = obj_schema.get("properties") or {}
    req = obj_schema.get("required")
    if not isinstance(req, list):
        req = []
        obj_schema["required"] = req
    for name, prop in props.items():
        if not isinstance(prop, dict):
            continue
        if prop.get("type") == "object":
            _ensure_group_required(prop)
            if name not in req and _has_required_leaf(prop):
                req.append(name)
        elif prop.get("type") == "array" and isinstance(prop.get("items"), dict) \
                and prop["items"].get("type") == "object":
            _ensure_group_required(prop["items"])


def _resolve_local_path(path, properties):
    """Vrai si ``path`` (pointé) existe dans ``properties`` (récursif groupes)."""
    parts = path.split(".")
    props = properties
    for part in parts:
        if not isinstance(props, dict) or part not in props:
            return False
        props = _sub_properties(props[part])
        if props is None:
            props = {}  # feuille : ok si c'était le dernier segment
    return True


def _resolve_local_prop(path, properties):
    """Comme ``_resolve_local_path`` mais renvoie le schéma (``prop``) de la
    feuille résolue, ou ``None`` si le chemin n'existe pas — utilisé par
    ``choicesFrom`` pour vérifier que la cible est bien un select_one/
    select_multiple (cf. ``_is_select_prop``)."""
    parts = path.split(".")
    props = properties
    prop = None
    for part in parts:
        if not isinstance(props, dict) or part not in props:
            return None
        prop = props[part]
        props = _sub_properties(prop)
        if props is None:
            props = {}  # feuille : ok si c'était le dernier segment
    return prop


def _is_select_prop(prop):
    """Vrai si ``prop`` (schéma JSON d'un champ) est un select_one
    (``"enum" in prop``) ou select_multiple/select_multiple_check
    (``type == "array"`` et ``"enum" in items``) — même détection que
    ``_xls_type`` (export XLSForm)."""
    if not isinstance(prop, dict):
        return False
    if "enum" in prop:
        return True
    if prop.get("type") == "array" and isinstance(prop.get("items"), dict):
        return "enum" in prop["items"]
    return False


# ---------------------------------------------------------------------------
# Partage entre villages sièges : extraction / fusion des valeurs des champs
# marqués `share` dans `page["share"]` (liste de {"path", "mode"} — LE MODE EST
# PORTÉ PAR CHAMP, pas par tâche : deux champs de la même tâche peuvent
# partager selon des modes différents, ex. l'un automatique vers tout le
# canton, l'autre au choix du facilitateur). Source et cible sont TOUJOURS la
# même Task (même `form`, même `sql_id`) — seul le village (donc le document
# CouchDB) diffère -> pas besoin de mapping de schéma.
# ---------------------------------------------------------------------------

def _value_by_path(data, path):
    cur = data
    for part in str(path).split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _set_value_by_path(data, path, value):
    parts = str(path).split(".")
    cur = data
    for part in parts[:-1]:
        if not isinstance(cur.get(part), dict):
            cur[part] = {}
        cur = cur[part]
    cur[parts[-1]] = value


def _share_entries(page):
    """Normalise ``page["share"]`` en liste de ``{"path", "mode"}`` — tolère
    les entrées historiques (chaîne nue, sans mode explicite)."""
    out = []
    for entry in (page.get("share") or []) if isinstance(page, dict) else []:
        if isinstance(entry, str):
            out.append({"path": entry, "mode": SHARE_MODE_DEFAULT})
        elif isinstance(entry, dict) and isinstance(entry.get("path"), str):
            mode = entry.get("mode")
            out.append({"path": entry["path"], "mode": mode if mode in SHARE_MODES else SHARE_MODE_DEFAULT})
    return out


def group_share_paths_by_mode(form):
    """``{mode: [chemin_pointé, ...]}`` — tous les champs ``share`` de
    ``form``, groupés par mode (un même chemin ne peut apparaître qu'une fois,
    dans le groupe de SON mode). Modes absents du formulaire -> absents du
    dict (pas de clé avec liste vide)."""
    groups = {}
    if not isinstance(form, list):
        return groups
    for page in form:
        if not isinstance(page, dict):
            continue
        for entry in _share_entries(page):
            groups.setdefault(entry["mode"], []).append(entry["path"])
    return groups


def extract_share_values(form, form_response, mode=None):
    """``{chemin_pointé: valeur}`` pour les champs marqués ``share`` dans
    ``form`` (tous, ou seulement ceux du ``mode`` donné), lus dans
    ``form_response`` (liste par page, même index que ``form``). Ignore les
    valeurs absentes/vides (``None``, ``""``)."""
    values = {}
    if not isinstance(form, list) or not isinstance(form_response, list):
        return values
    for idx, page in enumerate(form):
        if not isinstance(page, dict):
            continue
        for entry in _share_entries(page):
            if mode is not None and entry["mode"] != mode:
                continue
            path = entry["path"]
            page_values = form_response[idx] if idx < len(form_response) else None
            val = _value_by_path(page_values, path) if isinstance(page_values, dict) else None
            if val is not None and val != "":
                values[path] = val
    return values


def merge_share_values(form, form_response, values):
    """Copie de ``form_response`` avec ``values`` (``{chemin: valeur}``, cf.
    :func:`extract_share_values`) fusionnées aux emplacements définis par
    ``form[*]["share"]``. Ne modifie que les chemins présents dans ``values``
    (le mode n'a pas d'importance ici : l'appelant a déjà filtré ``values`` au
    mode/groupe de cibles pertinent, cf. :func:`group_share_paths_by_mode`) ;
    tout le reste de ``form_response`` (déjà saisi par le facilitateur de la
    tâche cible) est préservé tel quel."""
    out = copy.deepcopy(form_response) if isinstance(form_response, list) else []
    if not isinstance(form, list) or not values:
        return out
    for idx, page in enumerate(form):
        if not isinstance(page, dict):
            continue
        paths = [e["path"] for e in _share_entries(page)]
        if not paths:
            continue
        while len(out) <= idx:
            out.append({})
        if not isinstance(out[idx], dict):
            out[idx] = {}
        for path in paths:
            if path in values:
                _set_value_by_path(out[idx], path, values[path])
    return out


def has_share_fields(form):
    """Vrai si au moins une page du design porte des champs ``share`` (quel
    que soit leur mode)."""
    return any(isinstance(p, dict) and p.get("share") for p in (form or []))


def _leaf_field_paths(properties, prefix=""):
    """Chemins pointés de toutes les feuilles "de données" de ``properties``
    (descend récursivement dans les groupes/répétables via
    :func:`_sub_properties`) — à l'exclusion des champs "note" (marqués
    ``_note`` par le convertisseur XLSForm, affichage seul, aucune valeur ->
    jamais proposés au partage par le builder, cf.
    ``applyShareModeToAllFields`` côté JS, qui les exclut de la même façon)."""
    out = []
    if not isinstance(properties, dict):
        return out
    for name, prop in properties.items():
        if not isinstance(prop, dict):
            continue
        path = f"{prefix}.{name}" if prefix else name
        sub = _sub_properties(prop)
        if sub is not None:
            out.extend(_leaf_field_paths(sub, path))
        elif not prop.get("_note"):
            out.append(path)
    return out


def all_fields_shared(form, mode=None):
    """Vrai si TOUTES les feuilles "de données" du formulaire (toutes pages
    confondues, groupes/répétables compris) sont marquées ``share`` —
    optionnellement restreint à un seul ``mode`` (sinon : partagée dans
    N'IMPORTE QUEL mode). Faux si le formulaire n'a aucune feuille de données
    du tout (rien à partager).

    Distingue "toute la tâche doit être copiée telle quelle" (une seule
    saisie qui vaut pour tout le canton, ex. réunion cantonale — AUCUN champ
    ne reste à la discrétion du facilitateur du village cible) du cas "juste
    quelques champs partagés parmi d'autres" (ex. coordonnées GPS au sein
    d'un formulaire par ailleurs propre à chaque village) : seul le premier
    cas doit entraîner la propagation de ``completed``/``validated`` sur les
    tâches cibles (cf. ``dashboard.utils.copy_shared_task_data`` /
    ``_copy_shared_task_data_to_target``, appelé avec le même ``mode`` que la
    copie en cours — si les champs d'une même tâche sont répartis sur
    PLUSIEURS modes, aucun des deux passages de copie ne verra "tous les
    champs" pour SON mode, et la propagation ne se déclenche pour aucun :
    comportement voulu, ce cas correspond à un formulaire réellement mixte)."""
    if not isinstance(form, list) or not form:
        return False
    total = 0
    for page in form:
        if not isinstance(page, dict):
            continue
        props = (page.get("page") or {}).get("properties") or {}
        leaves = _leaf_field_paths(props)
        if not leaves:
            continue
        total += len(leaves)
        shared_paths = {e["path"] for e in _share_entries(page) if mode is None or e["mode"] == mode}
        if not set(leaves) <= shared_paths:
            return False
    return total > 0


def _validate_rule(rule, form, page_index, prefix, errors):
    if not isinstance(rule, dict):
        errors.append(f"{prefix} : règle mal formée.")
        return
    if "when" not in rule or "then" not in rule:
        errors.append(f"{prefix} : 'when' et 'then' sont obligatoires.")
        return

    _validate_condition(rule["when"], form, page_index, prefix, errors)

    then = rule["then"]
    if not isinstance(then, list) or not then:
        errors.append(f"{prefix} : 'then' doit être une liste non vide d'actions.")
        return

    local_props = form[page_index]["page"].get("properties", {})
    for action in then:
        if not isinstance(action, dict):
            errors.append(f"{prefix} : action mal formée.")
            continue
        if action.get("action") not in RULE_ACTIONS:
            errors.append(
                f"{prefix} : action inconnue '{action.get('action')}' "
                f"(attendu : {', '.join(sorted(RULE_ACTIONS))})."
            )
        target = action.get("target", "")
        if target.startswith("$"):
            errors.append(f"{prefix} : 'target' ne peut pas viser une autre page.")
        elif not _resolve_local_path(target, local_props):
            errors.append(f"{prefix} : cible d'action inconnue '{target}'.")


def _validate_condition(cond, form, page_index, prefix, errors):
    if not isinstance(cond, dict):
        errors.append(f"{prefix} : condition mal formée.")
        return
    if "all" in cond or "any" in cond:
        group = cond.get("all") or cond.get("any")
        if not isinstance(group, list) or not group:
            errors.append(f"{prefix} : 'all'/'any' doit être une liste non vide.")
            return
        for sub in group:
            _validate_condition(sub, form, page_index, prefix, errors)
        return

    op = cond.get("op")
    if op not in CONDITION_OPERATORS:
        errors.append(
            f"{prefix} : opérateur inconnu '{op}' "
            f"(attendu : {', '.join(sorted(CONDITION_OPERATORS))})."
        )
    field = cond.get("field", "")
    if not isinstance(field, str) or not field:
        errors.append(f"{prefix} : 'field' manquant dans la condition.")
        return

    if field.startswith("$"):
        head, _, rest = field[1:].partition(".")
        try:
            target_page = int(head)
        except ValueError:
            errors.append(f"{prefix} : index de page invalide dans '{field}'.")
            return
        if not (0 <= target_page < len(form)):
            errors.append(f"{prefix} : page {target_page} hors bornes dans '{field}'.")
            return
        props = form[target_page]["page"].get("properties", {})
        if rest and not _resolve_local_path(rest, props):
            errors.append(f"{prefix} : champ '{rest}' introuvable en page {target_page}.")
    else:
        props = form[page_index]["page"].get("properties", {})
        if not _resolve_local_path(field, props):
            errors.append(f"{prefix} : champ de condition inconnu '{field}'.")


def _validate_calculate(calculate, properties, prefix, errors):
    if not isinstance(calculate, list):
        errors.append(f"{prefix} : 'calculate' doit être une liste.")
        return

    targets = []
    for item in calculate:
        if not isinstance(item, dict) or "target" not in item or "expr" not in item:
            errors.append(f"{prefix} : entrée calculate mal formée (target/expr).")
            continue
        target = item["target"]
        if not _resolve_local_path(target, properties):
            errors.append(f"{prefix} : cible de calcul inconnue '{target}'.")
        names = _calc_expression_names(item["expr"])
        if names is None:
            errors.append(f"{prefix} : expression invalide pour '{target}'.")
            continue
        for name in names:
            if name in CALC_FUNCTIONS:
                continue
            if not _resolve_local_path(name, properties):
                errors.append(
                    f"{prefix} : '{name}' utilisé dans le calcul de "
                    f"'{target}' n'existe pas."
                )
        targets.append((target, names))

    _detect_calc_cycles(targets, prefix, errors)


def _calc_expression_names(expr):
    """Analyse ``expr`` (arithmétique) ; retourne l'ensemble des identifiants,
    ou ``None`` si l'expression contient une construction interdite."""
    if not isinstance(expr, str) or not expr.strip():
        return None
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return None

    allowed_nodes = (
        ast.Expression, ast.BinOp, ast.UnaryOp, ast.Num, ast.Constant,
        ast.Name, ast.Load, ast.Call, ast.Attribute,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow,
        ast.USub, ast.UAdd, ast.FloorDiv, ast.List, ast.Tuple,
    )
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, allowed_nodes):
            return None
        if isinstance(node, ast.Call):
            func = node.func
            if not isinstance(func, ast.Name) or func.id not in CALC_FUNCTIONS:
                return None
        if isinstance(node, ast.Attribute):
            # autorise "groupe.champ" -> reconstruit le chemin pointé
            path = _dotted_from_attribute(node)
            if path is None:
                return None
            names.add(path)
        elif isinstance(node, ast.Name):
            names.add(node.id)
    # retire les segments intermédiaires déjà couverts par un chemin pointé
    return {n for n in names if "." in n or all(not p.startswith(n + ".") for p in names)}


def _dotted_from_attribute(node):
    parts = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if not isinstance(cur, ast.Name):
        return None
    parts.append(cur.id)
    return ".".join(reversed(parts))


def _detect_calc_cycles(targets, prefix, errors):
    graph = {t: {n for n in deps if "." not in n or True} for t, deps in targets}
    known = set(graph)

    def visit(node, stack):
        for dep in graph.get(node, ()):  # noqa: B007
            if dep not in known:
                continue
            if dep in stack:
                errors.append(
                    f"{prefix} : dépendance circulaire de calcul "
                    f"({' -> '.join(stack + [dep])})."
                )
                return
            visit(dep, stack + [dep])

    for target in graph:
        visit(target, [target])


# ---------------------------------------------------------------------------
# XLSForm  (feuilles survey / choices / settings) — openpyxl uniquement
# ---------------------------------------------------------------------------
def form_design_to_xlsform(form, form_title="form"):
    """Sérialise ``form`` en classeur XLSForm (bytes .xlsx)."""
    from openpyxl import Workbook

    wb = Workbook()
    survey = wb.active
    survey.title = "survey"
    survey.append(["type", "name", "label", "hint", "required",
                   "relevant", "constraint", "calculation", "appearance"])
    choices = wb.create_sheet("choices")
    choices.append(["list_name", "name", "label"])
    settings = wb.create_sheet("settings")
    settings.append(["form_title", "form_id"])
    settings.append([form_title, _slugify(form_title)])

    choice_lists = {}

    # Chaque page du formulaire (form[i]) est encadrée par un groupe XLSForm
    # dédié (`begin group page_N ... end group`, appearance="field-list") --
    # convention standard ODK/Enketo pour dire "tous ces champs sur UN SEUL
    # écran", donc l'équivalent le plus proche d'une "page" en XLSForm (qui
    # n'a pas de notion de page native). C'est un marqueur SANS AMBIGUÏTÉ
    # possible avec un vrai groupe de champs de CETTE app : un groupe normal
    # (`type:"object"` dans le schéma) n'a jamais cette appearance, seule une
    # page en porte une (cf. `_emit_survey_row`, groupes réels -> appearance
    # toujours vide). Reconnu à l'import par `xlsform_to_form_design`.
    for page_index, page in enumerate(form):
        schema = page.get("page", {})
        properties = schema.get("properties", {})
        required = set(schema.get("required", []) or [])
        page_opts = page.get("options") or {}
        fields = page_opts.get("fields", {}) or {}
        rules_by_target = _rules_by_target(page.get("rules", []) or [])
        calc_by_target = {c["target"]: c["expr"] for c in page.get("calculate", []) or []}

        page_name = f"page_{page_index + 1}"
        survey.append(["begin group", page_name, f"Page {page_index + 1}", "", "", "", "", "", "field-list"])
        for name in _normalize_order(page_opts.get("order"), properties):
            prop = properties[name]
            _emit_survey_row(
                survey, choices, choice_lists, name, prop,
                fields.get(name, {}), name in required,
                rules_by_target.get(name), calc_by_target.get(name),
            )
        survey.append(["end group", page_name, "", "", "", "", "", "", ""])

    return _workbook_bytes(wb)


def _emit_survey_row(survey, choices, choice_lists, name, prop, opts,
                     is_required, relevant, calculation):
    xls_type, list_name = _xls_type(prop, name, choices, choice_lists)
    label = opts.get("label", name)
    hint = opts.get("help", "")
    # `mode:"checklist"` (select_multiple rendu en cases à cocher) -> appearance ODK.
    appearance = "list" if opts.get("mode") == "checklist" else ""

    if prop.get("type") == "object":
        survey.append(["begin group", name, label, hint, "", relevant or "", "", "", ""])
        sub_props = prop.get("properties") or {}
        for sub in _normalize_order(opts.get("order"), sub_props):
            _emit_survey_row(survey, choices, choice_lists, sub, sub_props[sub],
                             (opts.get("fields") or {}).get(sub, {}),
                             sub in (prop.get("required") or []), None, None)
        survey.append(["end group", name, "", "", "", "", "", "", ""])
        return

    if prop.get("type") == "array" and isinstance(prop.get("items"), dict) \
            and prop["items"].get("type") == "object":
        survey.append(["begin repeat", name, label, hint, "", relevant or "", "", "", ""])
        sub_props = prop["items"].get("properties") or {}
        item_opts = opts.get("item") if isinstance(opts.get("item"), dict) else opts
        for sub in _normalize_order(item_opts.get("order"), sub_props):
            _emit_survey_row(survey, choices, choice_lists, sub, sub_props[sub],
                             (item_opts.get("fields") or opts.get("fields") or {}).get(sub, {}),
                             sub in (prop["items"].get("required") or []), None, None)
        survey.append(["end repeat", name, "", "", "", "", "", "", ""])
        return

    if list_name:
        xls_type = f"{xls_type} {list_name}"

    survey.append([
        xls_type, name, label, hint,
        "yes" if is_required else "",
        relevant or "",
        _xls_constraint(prop),
        calculation or "",
        appearance,
    ])


def _xls_type(prop, name, choices, choice_lists):
    t = prop.get("type")
    fmt = prop.get("format")
    if t == "geopoint":
        return "geopoint", None
    if "enum" in prop:
        list_name = _register_choice_list(prop["enum"], name, choices, choice_lists)
        return "select_one", list_name
    if t == "array":
        items = prop.get("items") or {}
        if "enum" in items:
            list_name = _register_choice_list(items["enum"], name, choices, choice_lists)
            return "select_multiple", list_name
        return "text", None
    if t in ("number", "integer"):
        return ("integer" if t == "integer" else "decimal"), None
    if fmt == "date":
        return "date", None
    if fmt == "datetime":
        return "dateTime", None
    if fmt == "time":
        return "time", None
    if prop.get("_note"):
        return "note", None
    return "text", None


def _register_choice_list(values, name, choices, choice_lists):
    key = tuple(values)
    if key in choice_lists:
        return choice_lists[key]
    list_name = f"{_slugify(name)}_choices"
    i = 2
    while list_name in choice_lists.values():
        list_name = f"{_slugify(name)}_choices_{i}"
        i += 1
    choice_lists[key] = list_name
    for value in values:
        choices.append([list_name, _slugify(str(value)), str(value)])
    return list_name


def _xls_constraint(prop):
    parts = []
    if "minimum" in prop:
        parts.append(f". >= {prop['minimum']}")
    if "maximum" in prop:
        parts.append(f". <= {prop['maximum']}")
    if "minLength" in prop:
        parts.append(f"string-length(.) >= {prop['minLength']}")
    if "maxLength" in prop:
        parts.append(f"string-length(.) <= {prop['maxLength']}")
    if "pattern" in prop:
        parts.append(f"regex(., '{prop['pattern']}')")
    return " and ".join(parts)


def _rules_by_target(rules):
    out = {}
    for rule in rules:
        expr = _condition_to_xpath(rule.get("when", {}))
        for action in rule.get("then", []) or []:
            if action.get("action") == "show":
                out[action.get("target")] = expr
            elif action.get("action") == "hide":
                out[action.get("target")] = f"not({expr})"
    return out


def _condition_to_xpath(cond):
    if "all" in cond or "any" in cond:
        joiner = " and " if "all" in cond else " or "
        return "(" + joiner.join(
            _condition_to_xpath(c) for c in (cond.get("all") or cond.get("any"))
        ) + ")"
    # XLSForm est un survey unique : on aplatit un éventuel préfixe de page
    # "$<index>." (les noms de champs restent uniques sur le survey fusionné).
    raw = cond.get("field", "")
    if raw.startswith("$"):
        raw = raw.split(".", 1)[1] if "." in raw else raw[1:]
    field = "${" + raw.replace(".", "/") + "}"
    op = cond.get("op")
    value = cond.get("value")
    literal = f"'{value}'" if isinstance(value, str) else value
    return {
        "eq": f"{field} = {literal}",
        "ne": f"{field} != {literal}",
        "gt": f"{field} > {literal}",
        "gte": f"{field} >= {literal}",
        "lt": f"{field} < {literal}",
        "lte": f"{field} <= {literal}",
        "in": f"selected({field}, {literal})",
        "nin": f"not(selected({field}, {literal}))",
        "contains": f"contains({field}, {literal})",
        "empty": f"{field} = ''",
        "notEmpty": f"{field} != ''",
    }.get(op, f"{field} = {literal}")


def xlsform_to_form_design(file_obj):
    """Parse un .xlsx XLSForm en design de formulaire (une ou plusieurs pages).

    Portée volontairement restreinte : ``survey`` + ``choices`` + groupes /
    repeats + ``required`` / ``relevant`` (``field = 'valeur'`` et combinaisons
    ``and`` / ``or``) / ``constraint`` simples / ``calculation``.

    Pages : reconnaît le marqueur émis par ``form_design_to_xlsform``
    (groupe de premier niveau, ``appearance = "field-list"``) comme une
    frontière de page plutôt qu'un groupe de champs imbriqué -- SANS
    ambiguïté possible avec un vrai groupe de cette app (jamais cette
    appearance côté export). Un fichier XLSForm sans un tel marqueur (fichier
    plat/externe classique) retombe sur l'ancien comportement : tout en une
    seule page.
    """
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(file_obj.read()) if hasattr(file_obj, "read") else file_obj)
    survey = _sheet_rows(wb["survey"])
    choices_rows = _sheet_rows(wb["choices"]) if "choices" in wb.sheetnames else []

    choice_map = {}
    for row in choices_rows:
        choice_map.setdefault(row.get("list_name"), []).append(
            row.get("label") or row.get("name")
        )

    def new_page_state():
        return {"properties": {}, "options_fields": {}, "required": [], "rules": [], "calculate": []}

    pages_state = [new_page_state()]
    cur = pages_state[-1]
    stack = [(cur["properties"], cur["options_fields"], cur["required"])]  # (props, opts, required-list)
    open_kinds = []  # parallèle conceptuel de `stack`, mais une entrée "page" ne pousse rien dessus

    for row in survey:
        raw_type = (row.get("type") or "").strip()
        if not raw_type:
            continue
        name = (row.get("name") or "").strip()
        head = raw_type.split()[0]

        if head in ("begin", "end"):
            kind = raw_type.split()[1] if len(raw_type.split()) > 1 else ""
            if head == "begin":
                is_page_marker = (
                    kind == "group" and len(stack) == 1
                    and (row.get("appearance") or "").strip().lower() == "field-list"
                )
                if is_page_marker:
                    if cur["properties"] or cur["required"] or cur["rules"] or cur["calculate"]:
                        cur = new_page_state()
                        pages_state.append(cur)
                        stack = [(cur["properties"], cur["options_fields"], cur["required"])]
                    # sinon : page initiale encore vide -> réutilisée pour CE
                    # premier groupe-page plutôt que de créer une page vide en tête.
                    open_kinds.append("page")
                else:
                    sub_props, sub_opts, sub_req = {}, {}, []
                    container = {
                        "props": sub_props, "opts": sub_opts, "req": sub_req,
                        "name": name, "kind": kind,
                        "parent": stack[-1],
                        "label": row.get("label") or name,
                        "relevant": row.get("relevant"),
                    }
                    stack.append((sub_props, sub_opts, sub_req, container))
                    open_kinds.append("group")
            else:
                last_kind = open_kinds.pop() if open_kinds else None
                if last_kind == "page":
                    pass  # la page reste "courante" jusqu'au prochain marqueur de page (ou la fin)
                else:
                    top = stack.pop()
                    container = top[3]
                    parent_props, parent_opts, parent_req = container["parent"][:3]
                    inner = {"type": "object", "properties": container["props"]}
                    if container["req"]:
                        inner["required"] = container["req"]
                    if container["kind"] == "repeat":
                        parent_props[container["name"]] = {"type": "array", "items": inner}
                    else:
                        parent_props[container["name"]] = inner
                    parent_opts[container["name"]] = {
                        "label": container["label"], "fields": container["opts"],
                        "order": list(container["props"].keys()),
                    }
                    if container["relevant"]:
                        _relevant_to_rule(container["relevant"], container["name"], cur["rules"])
            continue

        prop, opt = _xls_row_to_prop(row, head, raw_type, choice_map)
        cur_props, cur_opts, cur_req = stack[-1][0], stack[-1][1], stack[-1][2]
        if head == "calculate" or row.get("calculation"):
            if row.get("calculation"):
                cur["calculate"].append({
                    "target": name,
                    "expr": _xpath_calc_to_expr(row["calculation"]),
                })
            if head == "calculate":
                continue
        cur_props[name] = prop
        cur_opts[name] = opt
        if (row.get("required") or "").strip().lower() in ("yes", "true", "1"):
            cur_req.append(name)
        if row.get("relevant"):
            _relevant_to_rule(row["relevant"], name, cur["rules"])

    pages = []
    for ps in pages_state:
        page = {
            "options": {"fields": ps["options_fields"], "order": list(ps["properties"].keys())},
            "page": {"type": "object", "properties": ps["properties"], "required": ps["required"]},
        }
        if ps["rules"]:
            page["rules"] = ps["rules"]
        if ps["calculate"]:
            page["calculate"] = ps["calculate"]
        pages.append(page)
    return pages


def _xls_row_to_prop(row, head, raw_type, choice_map):
    label = row.get("label") or row.get("name")
    opt = {"label": label, "help": row.get("hint") or "", "i18n": {"optional": "", "required": "*"}}
    list_name = raw_type.split()[1] if len(raw_type.split()) > 1 else None
    values = choice_map.get(list_name, []) if list_name else []

    if head == "select_one":
        prop = {"type": "string", "enum": values}
    elif head == "select_multiple":
        prop = {"type": "array", "items": {"type": "string", "enum": values}}
        appearance = (row.get("appearance") or "").lower()
        if "list" in appearance or "check" in appearance:
            opt["mode"] = "checklist"
            opt["options"] = [{"value": v, "text": v} for v in values]
    elif head == "integer":
        prop = {"type": "integer"}
    elif head in ("decimal", "number", "range"):
        prop = {"type": "number"}
    elif head == "date":
        prop = {"type": "string", "format": "date"}
        opt["mode"] = "date"
    elif head in ("datetime", "dateTime"):
        prop = {"type": "string", "format": "datetime"}
    elif head == "time":
        prop = {"type": "string", "format": "time"}
    elif head == "note":
        prop = {"type": "string", "_note": True}
    elif head in ("geopoint", "geotrace", "geoshape"):
        prop = {"type": "geopoint"}
        opt["mode"] = "geopoint"
    else:
        prop = {"type": "string"}

    _merge_xls_constraint(row.get("constraint"), prop)
    return prop, opt


def _merge_xls_constraint(constraint, prop):
    if not constraint:
        return
    import re

    for m in re.finditer(r"\.\s*(>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)", constraint):
        op, num = m.group(1), float(m.group(2))
        num = int(num) if num.is_integer() else num
        if op in (">=", ">"):
            prop["minimum"] = num
        else:
            prop["maximum"] = num
    m = re.search(r"string-length\(\.\)\s*>=\s*(\d+)", constraint)
    if m:
        prop["minLength"] = int(m.group(1))
    m = re.search(r"string-length\(\.\)\s*<=\s*(\d+)", constraint)
    if m:
        prop["maxLength"] = int(m.group(1))
    m = re.search(r"regex\(\.\s*,\s*'([^']+)'\)", constraint)
    if m:
        prop["pattern"] = m.group(1)


def _relevant_to_rule(relevant, target, rules):
    """Traduit un ``relevant`` XPath simple en règle ``show``."""
    import re

    negate = False
    expr = relevant.strip()
    m = re.match(r"^not\((.*)\)$", expr)
    if m:
        negate, expr = True, m.group(1).strip()

    joiner = " and " if " and " in expr else (" or " if " or " in expr else None)
    chunks = re.split(r"\s+and\s+|\s+or\s+", expr) if joiner else [expr]
    conds = []
    for chunk in chunks:
        c = _xpath_atom_to_condition(chunk)
        if c:
            conds.append(c)
    if not conds:
        return
    when = conds[0] if len(conds) == 1 else {
        ("all" if joiner == " and " else "any"): conds
    }
    rules.append({
        "when": when,
        "then": [{"action": "hide" if negate else "show", "target": target}],
    })


def _xpath_atom_to_condition(chunk):
    import re

    chunk = chunk.strip().strip("()")
    m = re.match(r"\$\{([^}]+)\}\s*(=|!=|>=|<=|>|<)\s*'?([^']*)'?$", chunk)
    if not m:
        m2 = re.match(r"selected\(\s*\$\{([^}]+)\}\s*,\s*'([^']+)'\s*\)$", chunk)
        if m2:
            return {"field": m2.group(1).replace("/", "."), "op": "in", "value": m2.group(2)}
        return None
    field = m.group(1).replace("/", ".")
    op = {"=": "eq", "!=": "ne", ">=": "gte", "<=": "lte", ">": "gt", "<": "lt"}[m.group(2)]
    value = m.group(3)
    if value == "" and op == "eq":
        return {"field": field, "op": "empty"}
    if value == "" and op == "ne":
        return {"field": field, "op": "notEmpty"}
    try:
        value = int(value)
    except ValueError:
        try:
            value = float(value)
        except ValueError:
            pass
    return {"field": field, "op": op, "value": value}


def _xpath_calc_to_expr(calculation):
    import re

    return re.sub(r"\$\{([^}]+)\}", lambda m: m.group(1).replace("/", "."), calculation).strip()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _sheet_rows(sheet):
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        return []
    header = [str(h).strip() if h is not None else "" for h in rows[0]]
    out = []
    for raw in rows[1:]:
        if raw is None or all(c is None for c in raw):
            continue
        out.append({header[i]: raw[i] for i in range(len(header)) if header[i]})
    return out


def _workbook_bytes(wb):
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# --- Choix (enum) d'un champ select_one / select_multiple : import / export .xlsx

_CHOICE_VALUE_HEADERS = {
    "value", "valeur", "valeurs", "choix", "choice", "choices", "name", "code",
}
_CHOICE_LABEL_HEADERS = {
    "label", "labels", "libelle", "libellé", "libelles", "libellés",
    "text", "texte", "intitule", "intitulé",
}


def choices_to_xlsx(choices, sheet_title="choix"):
    """Classeur .xlsx à deux colonnes (``valeur`` / ``libelle``) listant les
    choix fournis. Sert aussi de gabarit du format attendu à l'import."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title
    ws.append(["valeur", "libelle"])
    for choice in choices or []:
        if isinstance(choice, dict):
            ws.append([choice.get("value", ""), choice.get("label", "")])
        else:
            ws.append([choice, ""])
    return _workbook_bytes(wb)


def xlsx_to_choices(file_obj, limit=2000):
    """Lit un .xlsx et renvoie la liste des valeurs de choix.

    La colonne des valeurs est repérée par son en-tête (``valeur`` / ``value`` /
    ``choix``…) ; sans en-tête reconnu, la 1re colonne est utilisée et toutes
    ses cellules sont considérées comme des valeurs. Les doublons et cellules
    vides sont ignorés, le résultat est borné à ``limit``.
    """
    from openpyxl import load_workbook

    src = io.BytesIO(file_obj.read()) if hasattr(file_obj, "read") else file_obj
    wb = load_workbook(src, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []

    first = [str(c).strip().lower() if c is not None else "" for c in rows[0]]
    has_header = any(
        h in _CHOICE_VALUE_HEADERS or h in _CHOICE_LABEL_HEADERS for h in first
    )
    col = 0
    if has_header:
        for i, head in enumerate(first):
            if head in _CHOICE_VALUE_HEADERS:
                col = i
                break
        data_rows = rows[1:]
    else:
        data_rows = rows

    out, seen = [], set()
    for raw in data_rows:
        if raw is None or col >= len(raw) or raw[col] is None:
            continue
        val = str(raw[col]).strip()
        if not val or val in seen:
            continue
        seen.add(val)
        out.append(val)
        if len(out) >= limit:
            break
    return out


def _slugify(value):
    import re

    value = re.sub(r"[^\w]+", "_", str(value).strip().lower(), flags=re.UNICODE)
    return value.strip("_") or "item"


# ---------------------------------------------------------------------------
# Sources dynamiques d'un champ de sélection : PostgreSQL (liste blanche de
# tables de référence) / fichier Excel / niveaux administratifs, + cascade.
# Le résultat est un "snapshot" figé dans Task.form : chaque champ porte
# ``options.fields.<name>.dataset = [{v, l, p}]`` (+ ``cascadeFrom``) et
# ``page.properties.<name>.enum`` = { valeur: libellé }. Le filtrage de la
# cascade est fait côté mobile sur ce snapshot (hors ligne).
# ---------------------------------------------------------------------------

# Liste blanche : seules ces tables peuvent alimenter un champ « base de données ».
ALLOWED_DATASOURCE_TABLES = {
    "administrativelevels_administrativelevel",
    "administrativelevels_geographicalunit",
    "administrativelevels_cvd",
    "subprojects_subproject"
}
_SENSITIVE_COLUMN_TOKENS = (
    "password", "passwd", "token", "secret", "hash", "salt",
    "api_key", "apikey", "private_key", "session",
)
DATASOURCE_OPS = {
    "eq": "=", "ne": "<>", "gt": ">", "gte": ">=", "lt": "<", "lte": "<=",
    "contains": "ILIKE", "in": "IN",
}
# Opérateurs sans valeur (test de nullité).
_DATASOURCE_NULL_OPS = {"isnull", "notnull"}
ADMIN_LEVEL_TYPES = ["Region", "Prefecture", "Commune", "Canton", "Village"]
_DATASOURCE_ROW_CAP = 5000


def _is_sensitive_column(name):
    low = str(name).lower()
    return any(tok in low for tok in _SENSITIVE_COLUMN_TOKENS)


def _table_columns(table):
    """Colonnes réelles d'une table du schéma ``public`` (hors colonnes sensibles)."""
    from django.db import connection

    with connection.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s "
            "ORDER BY ordinal_position",
            [table],
        )
        return [r[0] for r in cur.fetchall() if not _is_sensitive_column(r[0])]


def list_datasources():
    """Tables autorisées existantes + leurs colonnes (sélecteurs du builder)."""
    out = []
    for table in sorted(ALLOWED_DATASOURCE_TABLES):
        cols = _table_columns(table)
        if cols:
            out.append({"table": table, "columns": cols})
    return out


def _require_column(name, allowed):
    name = str(name or "").strip()
    if name not in allowed:
        raise ValueError(f"Colonne non autorisée : {name!r}")
    return name


def query_datasource(spec, row_cap=_DATASOURCE_ROW_CAP):
    """Exécute une source dynamique -> ``(rows, truncated)`` où chaque ligne est
    ``{"v": <valeur>, "l": <libellé>, "p": <parent|"">}`` (v/p en chaîne : ce
    sont des clés d'``enum``). ``truncated`` = plus de lignes que le plafond."""
    kind = (spec or {}).get("kind")
    if kind == "admin_levels":
        return _query_admin_levels(spec, row_cap)
    if kind == "db":
        return _query_db_table(spec, row_cap)
    raise ValueError(f"Source inconnue : {kind!r}")


def _query_admin_levels(spec, row_cap):
    from administrativelevels.models import AdministrativeLevel

    level = spec.get("level")
    if level not in ADMIN_LEVEL_TYPES:
        raise ValueError(f"Niveau administratif invalide : {level!r}")
    qs = AdministrativeLevel.objects.using("mis").filter(type=level)
    safe_cols = {"name", "type", "parent_id", "rural", "frontalier"}
    for f in (spec.get("filters") or []):
        col, op = f.get("column"), f.get("op", "eq")
        sval = "" if f.get("value") is None else str(f.get("value")).strip()
        if col not in safe_cols:
            continue
        if op == "isnull" or (op == "eq" and sval.lower() in ("none", "null")):
            qs = qs.filter(**{f"{col}__isnull": True})
            continue
        if op == "notnull" or (op == "ne" and sval.lower() in ("none", "null")):
            qs = qs.filter(**{f"{col}__isnull": False})
            continue
        if sval == "":
            continue
        lookup = {
            "eq": "", "ne": "", "gt": "__gt", "gte": "__gte",
            "lt": "__lt", "lte": "__lte", "contains": "__icontains",
        }.get(op, "")
        key = f"{col}{lookup}"
        try:
            qs = qs.exclude(**{key: sval}) if op == "ne" else qs.filter(**{key: sval})
        except (ValueError, TypeError):
            raise ValueError(
                f"Filtre invalide : « {col} {op} {sval} » (type de colonne incompatible)."
            )
    qs = qs.order_by("name")
    total = qs.count()
    rows = [
        {
            "v": str(o.id),
            "l": o.name or str(o.id),
            "p": "" if o.parent_id is None else str(o.parent_id),
        }
        for o in qs.only("id", "name", "parent_id")[:row_cap]
    ]
    return rows, total > row_cap


def _query_db_table(spec, row_cap):
    from django.db import connection
    from psycopg2 import sql as _sql

    table = spec.get("table")
    if table not in ALLOWED_DATASOURCE_TABLES:
        raise ValueError(f"Table non autorisée : {table!r}")
    cols = set(_table_columns(table))
    if not cols:
        raise ValueError(f"Table introuvable : {table!r}")

    value_col = _require_column(spec.get("value_column"), cols)
    label_col = _require_column(spec.get("label_column") or spec.get("value_column"), cols)
    parent_col = spec.get("parent_column") or ""
    if parent_col:
        parent_col = _require_column(parent_col, cols)

    select_parts = [
        _sql.SQL("{} AS v").format(_sql.Identifier(value_col)),
        _sql.SQL("{} AS l").format(_sql.Identifier(label_col)),
    ]
    if parent_col:
        select_parts.append(_sql.SQL("{} AS p").format(_sql.Identifier(parent_col)))

    where_sql, params = [], []
    for f in (spec.get("filters") or []):
        col, op = f.get("column"), f.get("op", "eq")
        sval = "" if f.get("value") is None else str(f.get("value")).strip()
        if col not in cols:
            continue
        ident = _sql.Identifier(col)
        # "= None/null" (saisi tel quel) -> test de nullité (intention courante).
        if op in _DATASOURCE_NULL_OPS or (op in ("eq", "ne") and sval.lower() in ("none", "null")):
            is_null = op == "isnull" or op == "eq"
            where_sql.append(_sql.SQL(
                "{} IS NULL" if is_null else "{} IS NOT NULL"
            ).format(ident))
            continue
        if op not in DATASOURCE_OPS or sval == "":
            continue  # filtre incomplet -> ignoré
        if op == "contains":
            where_sql.append(_sql.SQL("{} ILIKE %s").format(ident))
            params.append(f"%{sval}%")
        elif op == "in":
            items = [x.strip() for x in sval.split(",") if x.strip()]
            if not items:
                continue
            where_sql.append(_sql.SQL("{} IN %s").format(ident))
            params.append(tuple(items))
        else:
            where_sql.append(
                _sql.SQL("{} " + DATASOURCE_OPS[op] + " %s").format(ident)
            )
            params.append(sval)

    order_col = spec.get("order_by") or label_col
    if order_col not in cols:
        order_col = label_col
    try:
        limit = max(1, min(int(spec.get("limit") or row_cap), row_cap))
    except (TypeError, ValueError):
        limit = row_cap

    query = _sql.SQL(
        "SELECT {sel} FROM {tbl}{whr} ORDER BY {ord} LIMIT {lim}"
    ).format(
        sel=_sql.SQL(", ").join(select_parts),
        tbl=_sql.Identifier(table),
        whr=(
            _sql.SQL(" WHERE ") + _sql.SQL(" AND ").join(where_sql)
            if where_sql else _sql.SQL("")
        ),
        ord=_sql.Identifier(order_col),
        lim=_sql.Literal(limit),
    )

    from django.db import DatabaseError

    connection.ensure_connection()
    sql_text = query.as_string(connection.connection)
    try:
        with connection.cursor() as cur:
            cur.execute(sql_text, params)
            fetched = cur.fetchall()
            colnames = [c[0] for c in cur.description]
    except DatabaseError as exc:
        # ex. filtre "parent_id = 'None'" sur une colonne entière -> on renvoie
        # un message exploitable plutôt qu'une 500 / trace.
        raise ValueError(
            "Requête refusée par la base (vérifiez les filtres / le type des "
            "colonnes) : " + str(exc).splitlines()[0]
        ) from exc

    rows = []
    for rec in fetched:
        d = dict(zip(colnames, rec))
        rows.append({
            "v": "" if d.get("v") is None else str(d["v"]),
            "l": "" if d.get("l") is None else str(d["l"]),
            "p": "" if d.get("p") is None else str(d.get("p", "")),
        })
    return rows, len(fetched) >= limit


def read_sheet_table(file_obj, limit=_DATASOURCE_ROW_CAP):
    """Lit un .xlsx -> ``(columns, rows)`` : ``columns`` = en-têtes de la 1re
    ligne ; ``rows`` = liste de dicts {colonne: valeur}, au plus ``limit``."""
    from openpyxl import load_workbook

    src = io.BytesIO(file_obj.read()) if hasattr(file_obj, "read") else file_obj
    wb = load_workbook(src, read_only=True, data_only=True)
    ws = wb.active
    it = ws.iter_rows(values_only=True)
    try:
        header = next(it)
    except StopIteration:
        return [], []
    columns = []
    for i, h in enumerate(header):
        name = str(h).strip() if h is not None else ""
        columns.append(name or f"col{i + 1}")
    rows = []
    for rec in it:
        if rec is None or all(c is None for c in rec):
            continue
        rows.append({
            columns[i]: (
                "" if i >= len(rec) or rec[i] is None else str(rec[i]).strip()
            )
            for i in range(len(columns))
        })
        if len(rows) >= limit:
            break
    return columns, rows
