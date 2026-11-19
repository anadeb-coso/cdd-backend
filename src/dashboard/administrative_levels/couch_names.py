"""Noms corrigés sur le SIG (orthographe des villages, cantons, CVD, unités géographiques) -> bases CouchDB des
facilitateurs. Lancé depuis la page « Vérification des villages » (/administrative-levels/checking/).

Le nom est RECOPIÉ dans CouchDB à la distribution, puis n'est plus relu dans le SIG :
- document « facilitator » : `administrative_levels[].name` (villages d'affectation), `geographical_units[].name`
  (unité géographique = noms de ses villages) et `geographical_units[].cvd_groups[].name` (CVD) — lus par le mobile ;
- documents « task » : `administrative_level_name` (village, ou canton pour les tâches cantonales) ;
- la base de sauvegarde `backup_db_facilitators_docs` (tâches des villages retirés, reprises telles quelles au retour).
La copie SQL `Facilitator.administrative_levels` (mêmes éléments que le document « facilitator ») suit aussi.

Deux temps, chacun dans un thread suivi par une VillageDocsOperation (genre « names », même verrou que les
transferts de documents : jamais deux écritures en même temps dans les bases des facilitateurs) :
1. analyse : écarts entre le SIG et CouchDB, regroupés par niveau / CVD / unité (rien n'est écrit) ;
2. mise à jour des écarts cochés : seul le nom change ; écriture avec la révision lue (`_bulk_docs`), un document
   modifié entre-temps (mobile) est relu puis réécrit.
"""
import logging

from administrativelevels.models import CVD, AdministrativeLevel, GeographicalUnit
from authentication.models import Facilitator
from dashboard.diagnostics import village_docs as vd
from process_manager.models import VillageDocsOperation

logger = logging.getLogger(__name__)

KIND_LEVEL, KIND_CVD, KIND_UNIT = "level", "cvd", "unit"
MODE_SCAN, MODE_APPLY = "scan", "apply"
KIND_LABELS = {KIND_CVD: "CVD", KIND_UNIT: "Unité géographique"}
RETRIES = 3


def _int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def entry_key(kind, sql_id):
    return f"{kind}:{sql_id}"


class SqlNames:
    """Noms de référence (SIG). CVD et unités : `get_name()`, comme à la distribution
    (sync_geographicalunits_with_cvd_on_facilittor), calculés à la demande."""

    def __init__(self):
        self.levels = {row[0]: row[1:] for row in AdministrativeLevel.objects.values_list('id', 'name', 'type', 'parent_id')}
        self._cvd, self._unit = {}, {}

    def level(self, sql_id):
        row = self.levels.get(sql_id)
        return row[0] if row else None

    def level_type(self, sql_id):
        row = self.levels.get(sql_id)
        return row[1] if row else ""

    def parent_name(self, sql_id):
        row = self.levels.get(sql_id)
        return self.level(row[2]) if row and row[2] else ""

    def _memo(self, cache, model, sql_id):
        if sql_id not in cache:
            obj = model.objects.filter(id=sql_id).first()
            cache[sql_id] = obj.get_name() if obj else None
        return cache[sql_id]

    def cvd(self, sql_id):
        return self._memo(self._cvd, CVD, sql_id)

    def unit(self, sql_id):
        return self._memo(self._unit, GeographicalUnit, sql_id)

    def get(self, kind, sql_id):
        return {KIND_LEVEL: self.level, KIND_CVD: self.cvd, KIND_UNIT: self.unit}[kind](sql_id)


def _parts(name):
    return sorted(part.strip() for part in (name or "").split("/"))


def _differs(current, expected, kind=KIND_LEVEL):
    """Nom à corriger. Unité / CVD sans nom propre : noms des villages joints par « / » dans un ordre non fixé
    (requête sans tri) -> l'ordre seul n'est pas un écart."""
    if not expected or (current or "") == expected:
        return False
    return kind == KIND_LEVEL or _parts(current) != _parts(expected)


# ---------------------------------------------------------------------------------------------------------------
# Lecture des noms d'une base
# ---------------------------------------------------------------------------------------------------------------

def facilitator_doc_names(fac_doc):
    """[(kind, sql_id, nom actuel, villages)] des éléments nommés du document « facilitator »."""
    out = []
    for element in fac_doc.get('administrative_levels') or []:
        if isinstance(element, dict) and _int(element.get('id')) is not None:
            out.append((KIND_LEVEL, _int(element['id']), element.get('name'), {_int(element['id'])}))
    for unit in fac_doc.get('geographical_units') or []:
        if not isinstance(unit, dict):
            continue
        if _int(unit.get('sql_id')) is not None:
            out.append((KIND_UNIT, _int(unit['sql_id']), unit.get('name'), {_int(v) for v in unit.get('villages') or []}))
        for group in unit.get('cvd_groups') or []:
            if isinstance(group, dict) and _int(group.get('sql_id')) is not None:
                out.append((KIND_CVD, _int(group['sql_id']), group.get('name'),
                            {_int(v) for v in group.get('villages') or []}))
    return out


def rename_facilitator_doc(fac_doc, wanted):
    """Applique {(kind, sql_id): nouveau nom} au document (en place) ; nombre de noms changés."""
    changed = 0

    def rename(obj, field, kind, sql_id):
        nonlocal changed
        new = wanted.get((kind, sql_id))
        if new and obj.get(field) != new:
            obj[field] = new
            changed += 1

    for element in fac_doc.get('administrative_levels') or []:
        if isinstance(element, dict):
            rename(element, 'name', KIND_LEVEL, _int(element.get('id')))
    for unit in fac_doc.get('geographical_units') or []:
        if not isinstance(unit, dict):
            continue
        rename(unit, 'name', KIND_UNIT, _int(unit.get('sql_id')))
        for group in unit.get('cvd_groups') or []:
            if isinstance(group, dict):
                rename(group, 'name', KIND_CVD, _int(group.get('sql_id')))
    return changed


def _databases():
    """[(base, libellé)] : bases des facilitateurs (existantes) puis la base de sauvegarde."""
    couch = vd.Couch()
    response = couch.session.get(f"{couch.base}/_all_dbs", timeout=120)
    response.raise_for_status()
    existing = set(response.json())
    rows = Facilitator.objects.exclude(no_sql_db_name__isnull=True).exclude(no_sql_db_name='') \
        .order_by('name').values_list('no_sql_db_name', 'name', 'username')
    out, seen = [], set()
    for db, name, username in rows:
        if db in existing and db not in seen:
            seen.add(db)
            out.append((db, name or username or db))
    if vd.BACKUP_DB in existing:
        out.append((vd.BACKUP_DB, "Base de sauvegarde"))
    return out


# ---------------------------------------------------------------------------------------------------------------
# 1. Analyse
# ---------------------------------------------------------------------------------------------------------------

def run_scan(operation_id, level_ids):
    """Écarts SIG / CouchDB. `level_ids` : niveaux du périmètre de la page (villages + leurs parents) ; une CVD ou
    une unité est retenue si l'un de ses villages en fait partie. Les écarts sont écrits dans `results` (un
    élément par niveau / CVD / unité), à la fin, d'un coup."""
    progress = vd.Progress(operation_id)
    couch = vd.Couch()
    names = SqlNames()
    scope = set(level_ids or [])
    databases = _databases()
    progress.update(items_total=len(databases))
    entries = {}

    def note(kind, sql_id, current, db, label, field):
        expected = names.get(kind, sql_id)
        if not _differs(current, expected, kind):
            return
        key = entry_key(kind, sql_id)
        entry = entries.setdefault(key, {
            "key": key, "kind": kind, "id": sql_id, "new": expected, "old": [], "dbs": {},
            "type": names.level_type(sql_id) if kind == KIND_LEVEL else KIND_LABELS[kind],
            "parent": names.parent_name(sql_id) if kind == KIND_LEVEL else "",
        })
        if current not in entry["old"]:
            entry["old"].append(current)
        per_db = entry["dbs"].setdefault(db, {"label": label, "facilitator": 0, "tasks": 0})
        per_db[field] += 1

    for index, (db, label) in enumerate(databases):
        progress.update(current=f"{label} ({db})")
        if db != vd.BACKUP_DB:
            try:
                fac_doc = couch.facilitator_doc(db)
            except vd.CouchError:
                fac_doc = {}
            for kind, sql_id, current, villages in facilitator_doc_names(fac_doc):
                if kind == KIND_LEVEL and sql_id not in scope:
                    continue
                if kind != KIND_LEVEL and not villages & scope:
                    continue
                note(kind, sql_id, current, db, label, "facilitator")
        for task in couch.find(db, {"type": "task"}, fields=["_id", "administrative_level_id", "administrative_level_name"]):
            sql_id = _int(task.get('administrative_level_id'))
            if sql_id in scope:
                note(KIND_LEVEL, sql_id, task.get('administrative_level_name'), db, label, "tasks")
        progress.update(items_done=index + 1)

    results = []
    for entry in sorted(entries.values(), key=lambda e: (e["kind"] != KIND_LEVEL, e["type"], e["parent"], e["new"])):
        entry["documents"] = sum(d["facilitator"] + d["tasks"] for d in entry["dbs"].values())
        entry.update(status="ok", label=f'{entry["type"]} {entry["new"]}',
                     message=f'{" / ".join(o or "—" for o in entry["old"])} -> {entry["new"]} '
                             f'({len(entry["dbs"])} base(s), {entry["documents"]} document(s))')
        results.append(entry)
    progress.update(results=results, units_total=sum(e["documents"] for e in results), current="")


# ---------------------------------------------------------------------------------------------------------------
# 2. Mise à jour
# ---------------------------------------------------------------------------------------------------------------

def _write_facilitator_doc(couch, db, wanted):
    for _ in range(RETRIES):
        fac_doc = couch.facilitator_doc(db)
        changed = rename_facilitator_doc(fac_doc, wanted)
        if not changed:
            return 0
        _ok, failed = couch.bulk_docs(db, [fac_doc])
        if not failed:
            return changed
    raise vd.CouchError(f"{db} : document « facilitator » modifié pendant la mise à jour (réessayer)")


def _write_tasks(couch, db, level_names):
    """Tâches dont le nom de niveau diffère ; conflits (document modifié entre-temps) relus et réécrits."""
    ids = [str(i) for i in level_names] + [i for i in level_names]
    selector = {"type": "task", "administrative_level_id": {"$in": ids}}
    written, pending = 0, None
    for _ in range(RETRIES):
        docs = couch.find(db, selector if pending is None else dict(selector, _id={"$in": pending}))
        todo = []
        for doc in docs:
            new = level_names.get(_int(doc.get('administrative_level_id')))
            if new and doc.get('administrative_level_name') != new:
                doc['administrative_level_name'] = new
                todo.append(doc)
        if not todo:
            return written, 0
        ok, failed = couch.bulk_docs(db, todo)
        written += len(ok)
        pending = [f.get("id") for f in failed if f.get("error") == "conflict"]
        if len(pending) != len(failed):
            raise vd.CouchError(f"{db} : écriture refusée ({failed[0]})")
        if not pending:
            return written, 0
    return written, len(pending)


def _update_sql_copy(db, level_names):
    """Facilitator.administrative_levels (copie SQL des éléments du document « facilitator »)."""
    changed = 0
    for facilitator in Facilitator.objects.filter(no_sql_db_name=db).only('id', 'administrative_levels'):
        elements = facilitator.administrative_levels
        if not isinstance(elements, list):
            continue
        touched = False
        for element in elements:
            new = level_names.get(_int(element.get('id'))) if isinstance(element, dict) else None
            if new and element.get('name') != new:
                element['name'] = new
                touched = True
        if touched:
            Facilitator.objects.filter(pk=facilitator.pk).update(administrative_levels=elements)  # sans save() : pas de réplication
            changed += 1
    return changed


def run_apply(operation_id, entries):
    """`entries` : écarts cochés (issus de l'analyse), avec les bases concernées. Le nouveau nom est relu dans le
    SIG au moment d'écrire."""
    progress = vd.Progress(operation_id)
    couch = vd.Couch()
    names = SqlNames()
    per_db = {}
    for entry in entries:
        new = names.get(entry["kind"], entry["id"])
        if not new:
            continue
        for db, info in entry["dbs"].items():
            target = per_db.setdefault(db, {"label": info.get("label") or db, "wanted": {}, "levels": {}})
            target["wanted"][(entry["kind"], entry["id"])] = new
            if entry["kind"] == KIND_LEVEL:
                target["levels"][entry["id"]] = new
    progress.update(items_total=len(per_db))

    for db, target in per_db.items():
        label = f'{target["label"]} ({db})'
        progress.update(current=label)
        result = {"db": db, "label": label}
        try:
            fac = _write_facilitator_doc(couch, db, target["wanted"]) if db != vd.BACKUP_DB else 0
            tasks, left = _write_tasks(couch, db, target["levels"]) if target["levels"] else (0, 0)
            sql = _update_sql_copy(db, target["levels"]) if target["levels"] and db != vd.BACKUP_DB else 0
            progress.add_units(fac + tasks)
            message = f"{fac} nom(s) dans le document facilitateur, {tasks} tâche(s)"
            if sql:
                message += ", copie SQL du facilitateur"
            if left:
                message += f" ; {left} tâche(s) modifiée(s) en même temps par le mobile, non mises à jour (relancer)"
            result.update(status="warning" if left else "ok", message=message, facilitator=fac, tasks=tasks)
        except Exception as exc:  # noqa: BLE001 - une base en erreur n'arrête pas les autres
            logger.exception("Noms CouchDB : %s", db)
            result.update(status="error", message=f"{type(exc).__name__}: {exc}")
        progress.item_done(result)


def run(operation_id, mode, payload):
    if mode == MODE_SCAN:
        run_scan(operation_id, payload)
    else:
        run_apply(operation_id, payload)


def last_operation(mode=None):
    qs = VillageDocsOperation.objects.filter(kind=VillageDocsOperation.KIND_NAMES).select_related('started_by')
    if mode:
        qs = qs.filter(params__mode=mode)
    return qs.order_by('-id').first()
