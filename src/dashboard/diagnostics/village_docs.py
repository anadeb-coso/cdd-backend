"""Pages de diagnostic « Documents de villages » : écarts entre les phases/activités/tâches CouchDB d'un facilitateur
communautaire et ses villages d'affectation (`administrative_levels` de son document « facilitator »).

Constat de départ : retirer un village d'un FC ne déplace pas ses documents (les ProcessAddOrRemoveADL programmés
ne sont exécutés par personne) ; le FC à qui on affecte ensuite le village n'en a aucun.

- Page « Documents sans village » (ORPHANS) : groupes (village, projet, cycle) de documents présents dans la base d'un
  FC alors que le village n'est pas (ou plus) dans ses `administrative_levels` pour ce projet et ce cycle. Action :
  transfert vers la base de sauvegarde `backup_db_facilitators_docs` (puis suppression chez le FC).
- Page « Villages sans documents » (MISSING) : villages sièges d'affectation d'un FC sans aucun document dans sa
  base pour ce projet et ce cycle. Actions : transfert depuis la sauvegarde si elle en contient, sinon
  synchronisation des tâches choisies (`dashboard.utils.sync_tasks`, limitée à la base et aux villages choisis).

Un document sans `cycle_id` (anciennes données) appartient au groupe « cycle inconnu » : il compte comme présent pour
tous les cycles du village dans ce projet, et n'est orphelin que si le village n'est plus du tout dans le projet.

Transferts : les documents gardent leur `_id` (les liens phase_id / activity_id et TaskShareRecord.couch_task_id
restent valides) et leurs pièces jointes CouchDB ; chaque transfert est écrit dans `transfer_history`, et la copie en
sauvegarde porte `backup_source` (base, facilitateur, date, auteur) pour pouvoir la rendre au bon village. Rien
n'est supprimé de la base de départ tant que toutes les copies n'ont pas été écrites.
"""
import logging
import threading
from datetime import timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import requests
from django.conf import settings
from django.db import connection, connections, transaction
from django.db.models import F
from django.utils import timezone

from administrativelevels.models import AdministrativeLevel
from assignments.models import AssignAdministrativeLevelToFacilitator
from authentication.models import Facilitator
from process_manager.models import Cycle, Project, Task, TaskShareRecord, VillageDocsComment, VillageDocsOperation

logger = logging.getLogger(__name__)

TYPES = ["phase", "activity", "task"]
BACKUP_DB = "backup_db_facilitators_docs"
SCAN_FIELDS = ["_id", "administrative_level_id", "project_id", "cycle_id", "type", "completed"]
ACCOUNT_KINDS = ("real", "training", "develop")
PAGE_ORPHANS = VillageDocsComment.PAGE_ORPHANS
PAGE_MISSING = VillageDocsComment.PAGE_MISSING
SCAN_WORKERS = 12
WRITE_BATCH = 200
# Clé arbitraire du verrou consultatif PostgreSQL : une seule opération à la fois (deux transferts du même village
# en parallèle se marcheraient dessus).
ADVISORY_LOCK_KEY = 74120931


class CouchError(Exception):
    pass


# ---------------------------------------------------------------------------------------------------------------
# Accès CouchDB (HTTP direct : _find paginé, _bulk_get avec pièces jointes, _bulk_docs)
# ---------------------------------------------------------------------------------------------------------------

class Couch:
    def __init__(self):
        self.base = settings.NO_SQL_URL.rstrip('/')
        self.session = requests.Session()
        self.session.auth = (settings.NO_SQL_USER, settings.NO_SQL_PASS)

    def url(self, db, path=""):
        return f"{self.base}/{db}{path}"

    def find(self, db, selector, fields=None, page=10000):
        docs, bookmark = [], None
        while True:
            body = {"selector": selector, "limit": page}
            if fields:
                body["fields"] = fields
            if bookmark:
                body["bookmark"] = bookmark
            response = self.session.post(self.url(db, "/_find"), json=body, timeout=300)
            if response.status_code == 404:
                raise CouchError(f"base {db} introuvable")
            if response.status_code != 200:
                raise CouchError(f"{db} : _find HTTP {response.status_code} {response.text[:200]}")
            result = response.json()
            docs += result.get("docs", [])
            if len(result.get("docs", [])) < page:
                return docs
            bookmark = result.get("bookmark")

    def bulk_get(self, db, ids):
        """Documents complets (pièces jointes CouchDB incluses, en base64)."""
        out = []
        for start in range(0, len(ids), WRITE_BATCH):
            chunk = ids[start:start + WRITE_BATCH]
            response = self.session.post(self.url(db, "/_bulk_get?attachments=true&revs=false"),
                                         json={"docs": [{"id": i} for i in chunk]}, timeout=300)
            if response.status_code != 200:
                raise CouchError(f"{db} : _bulk_get HTTP {response.status_code} {response.text[:200]}")
            for result in response.json().get("results", []):
                for item in result.get("docs", []):
                    if "ok" in item:
                        out.append(item["ok"])
                    else:
                        raise CouchError(f"{db} : document {result.get('id')} illisible ({item.get('error')})")
        return out

    def live_revs(self, db, ids):
        """{_id: _rev} des documents existants (non supprimés) parmi `ids`."""
        revs = {}
        for start in range(0, len(ids), WRITE_BATCH):
            response = self.session.post(self.url(db, "/_all_docs"), json={"keys": ids[start:start + WRITE_BATCH]}, timeout=120)
            if response.status_code != 200:
                raise CouchError(f"{db} : _all_docs HTTP {response.status_code} {response.text[:200]}")
            for row in response.json().get("rows", []):
                value = row.get("value") or {}
                if row.get("id") and not value.get("deleted") and "error" not in row:
                    revs[row["id"]] = value.get("rev")
        return revs

    def bulk_docs(self, db, docs):
        """(ok, échecs) ; écrit par paquets."""
        ok, failed = [], []
        for start in range(0, len(docs), WRITE_BATCH):
            response = self.session.post(self.url(db, "/_bulk_docs"), json={"docs": docs[start:start + WRITE_BATCH]}, timeout=300)
            if response.status_code not in (200, 201):
                raise CouchError(f"{db} : _bulk_docs HTTP {response.status_code} {response.text[:200]}")
            for result in response.json():
                (ok if result.get("ok") else failed).append(result)
        return ok, failed

    def facilitator_doc(self, db):
        docs = self.find(db, {"type": "facilitator"})
        if len(docs) != 1:
            raise CouchError(f"{len(docs)} document(s) « facilitator » dans {db}")
        return docs[0]


# ---------------------------------------------------------------------------------------------------------------
# Règles de correspondance
# ---------------------------------------------------------------------------------------------------------------

def _str(value):
    return "" if value is None else str(value)


def account_kind(facilitator):
    if facilitator.develop_mode:
        return "develop"
    if facilitator.training_mode:
        return "training"
    return "real"


def element_keys(fac_doc):
    """({(village, projet, cycle)}, {(village, projet)}, {(village, projet, cycle): élément}) des villages
    d'affectation du document facilitateur."""
    full, partial, by_key = set(), set(), {}
    for element in fac_doc.get('administrative_levels') or []:
        if not isinstance(element, dict) or element.get('id') in (None, ""):
            continue
        key = (_str(element.get('id')), _str(element.get('project_id')), _str(element.get('cycle_id')))
        full.add(key)
        partial.add(key[:2])
        by_key.setdefault(key, element)
    return full, partial, by_key


def is_orphan(group_key, full, partial):
    village, project, cycle = group_key
    if cycle == "":
        return (village, project) not in partial
    return group_key not in full


def docs_selector(village, project_couch_id, cycle_couch_id):
    """Phases/activités/tâches du village pour le projet et le cycle (cycle "" = documents sans cycle_id)."""
    selector = {
        "type": {"$in": TYPES},
        "administrative_level_id": {"$in": [str(village)] + ([int(village)] if str(village).isdigit() else [])},
        "project_id": project_couch_id,
    }
    if cycle_couch_id:
        selector["cycle_id"] = cycle_couch_id
    else:
        selector["$or"] = [{"cycle_id": {"$exists": False}}, {"cycle_id": None}, {"cycle_id": ""}]
    return selector


def guard_same_group(docs, village, project_couch_id, cycle_couch_id):
    """Garde-fou avant toute écriture : uniquement des phases/activités/tâches de CE village, projet et cycle."""
    others = [d.get('_id') for d in docs
              if _str(d.get('administrative_level_id')) != str(village) or d.get('project_id') != project_couch_id
              or _str(d.get('cycle_id')) != _str(cycle_couch_id) or d.get('type') not in TYPES]
    if others:
        raise CouchError(f"{len(others)} document(s) hors du village/projet/cycle dans la sélection ({others[:3]})")


def row_key(db, village, project_couch_id, cycle_couch_id):
    return f"{db}|{village}|{project_couch_id}|{cycle_couch_id or ''}"


def parse_row_key(key):
    parts = str(key or "").split("|")
    if len(parts) != 4 or not parts[0] or not parts[1].isdigit() or not parts[2]:
        raise ValueError("clé invalide")
    return parts[0], parts[1], parts[2], parts[3]


# ---------------------------------------------------------------------------------------------------------------
# Scan (lecture seule)
# ---------------------------------------------------------------------------------------------------------------

def scope_facilitators(kinds):
    """Facilitateurs communautaires des types de compte choisis (réels, formation, développement)."""
    qs = Facilitator.objects.filter(facilitator_type='community_facilitator').exclude(no_sql_db_name__isnull=True).exclude(no_sql_db_name='')
    return [f for f in qs.order_by('name', 'id') if account_kind(f) in kinds]


def _scan_one(couch, facilitator, project_couch_ids):
    try:
        fac_doc = couch.facilitator_doc(facilitator.no_sql_db_name)
        docs = couch.find(facilitator.no_sql_db_name,
                          {"type": {"$in": TYPES}, "project_id": {"$in": project_couch_ids}}, fields=SCAN_FIELDS)
        return facilitator, fac_doc, docs, None
    except (CouchError, requests.RequestException) as exc:
        return facilitator, None, [], str(exc)


def _group_stats(docs):
    groups = defaultdict(lambda: {"phase": 0, "activity": 0, "task": 0, "completed": 0})
    for doc in docs:
        key = (_str(doc.get('administrative_level_id')), _str(doc.get('project_id')), _str(doc.get('cycle_id')))
        stats = groups[key]
        stats[doc.get('type')] = stats.get(doc.get('type'), 0) + 1
        if doc.get('type') == 'task' and doc.get('completed'):
            stats["completed"] += 1
    return groups


def backup_groups(couch, project_couch_ids):
    """{(village, projet, cycle): {source_db: stats}} des documents de la sauvegarde (source "" = avant ces pages)."""
    docs = couch.find(BACKUP_DB, {"type": {"$in": TYPES}, "project_id": {"$in": project_couch_ids}},
                      fields=SCAN_FIELDS + ["backup_source"])
    out = defaultdict(lambda: defaultdict(lambda: {"phase": 0, "activity": 0, "task": 0, "completed": 0, "facilitator": ""}))
    for doc in docs:
        key = (_str(doc.get('administrative_level_id')), _str(doc.get('project_id')), _str(doc.get('cycle_id')))
        source = doc.get('backup_source') if isinstance(doc.get('backup_source'), dict) else {}
        stats = out[key][_str(source.get('db'))]
        stats[doc.get('type')] = stats.get(doc.get('type'), 0) + 1
        if doc.get('type') == 'task' and doc.get('completed'):
            stats["completed"] += 1
        if source.get('facilitator_name'):
            stats["facilitator"] = source['facilitator_name']
    return out


def _village_info(village_ids):
    rows = AdministrativeLevel.objects.filter(id__in=[int(v) for v in village_ids if str(v).isdigit()]) \
        .select_related('parent__parent').only('id', 'name', 'parent__name', 'parent__parent__name')
    info = {}
    for adl in rows:
        canton = adl.parent
        commune = canton.parent if canton else None
        info[str(adl.id)] = {"name": adl.name, "canton": canton.name if canton else "", "commune": commune.name if commune else ""}
    return info


def _assigned_facilitators(village_ids, projects):
    """{(village, projet CDD id): [{id, name}]} : affectations SIG actives (AssignAdministrativeLevelToFacilitator).
    Le projet du SIG est celui de même nom ; facilitator_id est un texte en base unifiée."""
    from subprojects.models import Project as MisProject
    from cdd.call_objects_from_other_db import mis_objects_call
    mis_ids = dict(mis_objects_call.filter_objects(MisProject).values_list('name', 'id'))
    cdd_by_mis = {mis_ids.get(p.name): p.id for p in projects if mis_ids.get(p.name)}
    rows = AssignAdministrativeLevelToFacilitator.objects.filter(
        activated=True, project_id__in=list(cdd_by_mis), administrative_level_id__in=[int(v) for v in village_ids if str(v).isdigit()],
    ).values_list('administrative_level_id', 'project_id', 'facilitator_id')
    rows = list(rows)
    fac_ids = {int(r[2]) for r in rows if str(r[2]).isdigit()}
    names = {f.id: f for f in Facilitator.objects.filter(id__in=fac_ids).only('id', 'name', 'username', 'no_sql_db_name')}
    out = defaultdict(list)
    for village, mis_project, fac_id in rows:
        fac = names.get(int(fac_id)) if str(fac_id).isdigit() else None
        if fac:
            out[(str(village), cdd_by_mis[mis_project])].append(
                {"id": fac.id, "name": fac.name or fac.username, "db": fac.no_sql_db_name})
    return out


def _comments(page, village_ids):
    out = defaultdict(list)
    qs = VillageDocsComment.objects.filter(page=page, administrative_level_id__in=[int(v) for v in village_ids if str(v).isdigit()]) \
        .select_related('author', 'assigned_facilitator', 'project', 'cycle')
    for c in qs:
        key = row_key(c.no_sql_db_name, c.administrative_level_id, c.project.couch_id, c.cycle.couch_id if c.cycle else "")
        out[key].append(comment_json(c))
    return out


def comment_json(c):
    return {
        "id": c.id, "text": c.text,
        "author": (c.author.get_full_name() or c.author.username) if c.author else "",
        "at": timezone.localtime(c.created_at).strftime('%d/%m/%Y %H:%M'),
        "assigned": (c.assigned_facilitator.name or c.assigned_facilitator.username) if c.assigned_facilitator else "",
    }


def scan(page, projects, cycle_ids=None, kinds=("real",)):
    """Lignes d'une des deux pages, pour les projets (process_manager.Project) et cycles choisis."""
    projects = list(projects)
    by_couch = {p.couch_id: p for p in projects if p.couch_id}
    cycles = list(Cycle.objects.filter(project__in=projects))
    if cycle_ids:
        wanted = {int(c) for c in cycle_ids}
        chosen_cycles = {c.couch_id for c in cycles if c.id in wanted}
    else:
        chosen_cycles = None
    cycle_by_couch = {c.couch_id: c for c in cycles if c.couch_id}
    couch = Couch()
    facilitators = scope_facilitators(kinds)
    with ThreadPoolExecutor(max_workers=SCAN_WORKERS) as executor:
        results = list(executor.map(lambda f: _scan_one(couch, f, list(by_couch)), facilitators))

    def cycle_ok(cycle):
        return chosen_cycles is None or cycle in chosen_cycles or (page == PAGE_ORPHANS and cycle == "")

    raw, errors = [], []
    for facilitator, fac_doc, docs, error in results:
        if error:
            errors.append({"db": facilitator.no_sql_db_name, "name": facilitator.name, "error": error})
            continue
        full, partial, elements = element_keys(fac_doc)
        groups = _group_stats(docs)
        if page == PAGE_ORPHANS:
            for key, stats in groups.items():
                if key[1] in by_couch and cycle_ok(key[2]) and is_orphan(key, full, partial):
                    raw.append((facilitator, key, stats, None))
        else:
            present = set(groups)
            present_partial = {k[:2] for k in groups if k[2] == ""}
            for key, element in elements.items():
                if not element.get('is_headquarters_village') or key[1] not in by_couch or not cycle_ok(key[2]):
                    continue
                if key in present or key[:2] in present_partial:
                    continue
                raw.append((facilitator, key, None, element))

    village_ids = {r[1][0] for r in raw}
    info = _village_info(village_ids)
    assigned = _assigned_facilitators(village_ids, projects)
    comments = _comments(page, village_ids)
    backup = backup_groups(couch, list(by_couch)) if page == PAGE_MISSING and raw else {}

    rows = []
    for facilitator, (village, project_couch, cycle_couch), stats, element in raw:
        project = by_couch[project_couch]
        cycle = cycle_by_couch.get(cycle_couch)
        key = row_key(facilitator.no_sql_db_name, village, project_couch, cycle_couch)
        village_info = info.get(village, {})
        row = {
            "key": key,
            "village_id": village, "village": village_info.get("name") or (element or {}).get("name") or village,
            "canton": village_info.get("canton", ""), "commune": village_info.get("commune", ""),
            "project_id": project.id, "project": project.name,
            "cycle_id": cycle.id if cycle else None, "cycle": cycle.name if cycle else "",
            "facilitator_id": facilitator.id, "facilitator": facilitator.name or facilitator.username,
            "db": facilitator.no_sql_db_name, "kind": account_kind(facilitator), "active": facilitator.active,
            "assigned": assigned.get((village, project.id), []),
            "comments": comments.get(key, []),
        }
        if stats is not None:
            row.update({"phases": stats["phase"], "activities": stats["activity"], "tasks": stats["task"],
                        "completed": stats["completed"]})
        else:
            sources = []
            for backup_cycle in ([cycle_couch, ""] if cycle_couch else [""]):
                for source_db, s in (backup.get((village, project_couch, backup_cycle)) or {}).items():
                    sources.append({"source": source_db, "backup_cycle": backup_cycle, "facilitator": s["facilitator"],
                                    "phases": s["phase"], "activities": s["activity"], "tasks": s["task"],
                                    "completed": s["completed"]})
            row["backup"] = sources
        rows.append(row)
    rows.sort(key=lambda r: (r["project"], r["cycle"], r["commune"].lower(), r["canton"].lower(), r["village"].lower(), r["facilitator"].lower()))

    result = {"rows": rows, "errors": errors, "facilitators_scanned": len(facilitators)}
    if page == PAGE_MISSING:
        result["tasks"] = tasks_by_project_cycle({(r["project_id"], r["cycle_id"]) for r in rows if r["cycle_id"]})
    return result


def tasks_by_project_cycle(pairs):
    """{"projet|cycle": [{id, name, phase, activity}]} : tâches proposées pour la synchronisation."""
    out = {}
    for project_id, cycle_id in pairs:
        tasks = Task.objects.filter(project_id=project_id, cycles__id=cycle_id).select_related('phase', 'activity') \
            .order_by('phase__order', 'activity__order', 'order', 'id').distinct()
        out[f"{project_id}|{cycle_id}"] = [{
            "id": t.id, "name": t.name, "phase": t.phase.name if t.phase else "",
            "activity": t.activity.name if t.activity else "",
        } for t in tasks]
    return out


# ---------------------------------------------------------------------------------------------------------------
# Opérations (transferts, synchronisation) — exécutées dans un thread, suivies dans VillageDocsOperation
# ---------------------------------------------------------------------------------------------------------------

class OperationBusy(Exception):
    def __init__(self, operation):
        super().__init__("opération en cours")
        self.operation = operation


def running_operation():
    """Opération en cours ou en file (hors opérations restées sans nouvelle : serveur redémarré)."""
    return VillageDocsOperation.objects.filter(
        status__in=VillageDocsOperation.ACTIVE_STATUSES,
        heartbeat__gte=timezone.now() - VillageDocsOperation.STALE_AFTER).order_by('id').first()


def create_operation(kind, user, params, items_total, queue=False, no_sql_db_name=""):
    """Ligne de suivi. Sans `queue` (pages de diagnostic) : refus (OperationBusy) si une autre opération tourne ou
    attend. Avec `queue` (déplacements automatiques des localités) : créée « en attente », exécutée à son tour.
    L'exécution elle-même est sérialisée par le verrou consultatif pris par le thread (voir _acquire_lock)."""
    with transaction.atomic():
        if connection.vendor == 'postgresql':
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", [ADVISORY_LOCK_KEY + 1])
        VillageDocsOperation.objects.filter(
            status__in=VillageDocsOperation.ACTIVE_STATUSES,
            heartbeat__lt=timezone.now() - VillageDocsOperation.STALE_AFTER,
        ).update(status=VillageDocsOperation.STATUS_FAILED, finished_at=timezone.now(),
                 error="Interrompue : aucune nouvelle du serveur depuis 10 minutes (redémarrage ?).")
        running = running_operation()
        if running and not queue:
            raise OperationBusy(running)
        status = VillageDocsOperation.STATUS_PENDING if running else VillageDocsOperation.STATUS_RUNNING
        return VillageDocsOperation.objects.create(kind=kind, started_by=user, params=params, items_total=items_total,
                                                   status=status, no_sql_db_name=no_sql_db_name or "")


_LOCAL_LOCK = threading.Lock()  # repli hors PostgreSQL (tests sur SQLite)


def _acquire_lock(progress):
    """Attend son tour : verrou consultatif PostgreSQL de SESSION (connexion propre au thread), valable entre
    processus et instances. Le « signe de vie » est entretenu pendant l'attente (pas d'interruption à tort)."""
    import time
    waited = False
    while True:
        if connection.vendor == 'postgresql':
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_try_advisory_lock(%s)", [ADVISORY_LOCK_KEY])
                acquired = cursor.fetchone()[0]
        else:
            acquired = _LOCAL_LOCK.acquire(blocking=False)
        if acquired:
            progress.update(status=VillageDocsOperation.STATUS_RUNNING, current="")
            return
        if not waited:
            progress.update(status=VillageDocsOperation.STATUS_PENDING, current="En attente de la fin d'une autre opération…")
            waited = True
        else:
            progress.update()
        time.sleep(2)


def _release_lock():
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [ADVISORY_LOCK_KEY])
    elif _LOCAL_LOCK.locked():
        _LOCAL_LOCK.release()


class Progress:
    def __init__(self, operation_id):
        self.operation_id = operation_id

    def update(self, **fields):
        VillageDocsOperation.objects.filter(pk=self.operation_id).update(heartbeat=timezone.now(), **fields)

    def add_units(self, n):
        self.update(units_done=F('units_done') + n)

    def item_done(self, result):
        op = VillageDocsOperation.objects.get(pk=self.operation_id)
        op.results = list(op.results or []) + [result]
        op.items_done += 1
        op.heartbeat = timezone.now()
        op.save(update_fields=['results', 'items_done', 'heartbeat'])

    def finish(self, error=None):
        fields = {"finished_at": timezone.now(), "current": "",
                  "status": VillageDocsOperation.STATUS_FAILED if error else VillageDocsOperation.STATUS_DONE}
        if error:
            fields["error"] = error[:2000]
        self.update(**fields)


def _clean_for_copy(doc):
    """Copie écrivable ailleurs : sans _rev, pièces jointes avec leurs données seulement."""
    new = {k: v for k, v in doc.items() if k not in ('_rev', '_revisions', '_conflicts', '_deleted')}
    if isinstance(doc.get('_attachments'), dict):
        new['_attachments'] = {name: {"content_type": a.get("content_type"), "data": a.get("data")}
                               for name, a in doc['_attachments'].items() if a.get("data") is not None}
        if not new['_attachments']:
            new.pop('_attachments')
    return new


def _history(doc, entry):
    return list(doc.get('transfer_history') or []) + [entry]


class Transfer:
    """Transfert d'un groupe (village, projet, cycle) entre une base de facilitateur et la sauvegarde."""

    def __init__(self, couch, progress, operation_id, user_label):
        self.couch = couch
        self.progress = progress
        self.operation_id = operation_id
        self.user_label = user_label

    def list_ids(self, db, village, project, cycle, source=None):
        docs = self.couch.find(db, docs_selector(village, project, cycle), fields=["_id", "backup_source"])
        if source is not None:
            docs = [d for d in docs if _str((d.get('backup_source') or {}).get('db') if isinstance(d.get('backup_source'), dict) else None) == source]
        return [d['_id'] for d in docs]

    def copy_then_delete(self, from_db, to_db, ids, village, project, cycle, prepare):
        """Copie `ids` de from_db vers to_db (même _id), puis les supprime de from_db. (copiés, supprimés, avertissements)."""
        docs = self.couch.bulk_get(from_db, ids)
        guard_same_group(docs, village, project, cycle)
        existing = self.couch.live_revs(to_db, [d['_id'] for d in docs])
        copies = []
        for doc in docs:
            new = prepare(_clean_for_copy(doc))
            if doc['_id'] in existing:
                new['_rev'] = existing[doc['_id']]  # copie déjà présente (transfert précédent) : remplacée
            copies.append(new)
        written = 0
        for start in range(0, len(copies), WRITE_BATCH):
            chunk = copies[start:start + WRITE_BATCH]
            _, failed = self.couch.bulk_docs(to_db, chunk)
            if failed:
                raise CouchError(f"{len(failed)} document(s) non écrit(s) dans {to_db} ({failed[:2]}) ; rien n'a été "
                                 f"supprimé de {from_db}")
            written += len(chunk)
            self.progress.add_units(len(chunk))
        _, failed = self.couch.bulk_docs(from_db, [{"_id": d['_id'], "_rev": d['_rev'], "_deleted": True} for d in docs])
        warnings = []
        if failed:
            warnings.append(f"{len(failed)} document(s) copiés mais non supprimés de {from_db} (modifiés entre-temps ?) : "
                            f"{[f.get('id') for f in failed[:5]]}")
        return written, len(docs) - len(failed), warnings

    def to_backup(self, item, ids):
        db, village, project, cycle = item['db'], item['village'], item['project'], item['cycle']
        facilitator = Facilitator.objects.filter(no_sql_db_name=db).first()
        full, partial, _ = element_keys(self.couch.facilitator_doc(db))
        if not is_orphan((village, project, cycle), full, partial):
            return {"status": "refused", "message": "Le village est de nouveau dans les villages d'affectation du facilitateur : rien n'a été transféré."}
        if not ids:
            return {"status": "refused", "message": "Plus aucun document de ce village dans la base."}
        now = timezone.now().isoformat()
        source = {"db": db, "facilitator_id": facilitator.id if facilitator else None,
                  "facilitator_name": (facilitator.name or facilitator.username) if facilitator else "",
                  "moved_at": now, "moved_by": self.user_label, "operation_id": self.operation_id}

        def prepare(doc):
            doc['backup_source'] = source
            doc['transfer_history'] = _history(doc, {"from": db, "to": BACKUP_DB, "at": now, "by": self.user_label})
            return doc
        copied, deleted, warnings = self.copy_then_delete(db, BACKUP_DB, ids, village, project, cycle, prepare)
        return {"status": "ok", "copied": copied, "deleted": deleted, "warnings": warnings,
                "message": f"{copied} document(s) copiés dans la sauvegarde, {deleted} supprimé(s) de la base du facilitateur."}

    def from_backup(self, item, ids):
        db, village, project, cycle = item['db'], item['village'], item['project'], item['cycle']
        backup_cycle, source_db = item.get('backup_cycle', cycle), item.get('source', '')
        target = Facilitator.objects.filter(no_sql_db_name=db).first()
        _, _, elements = element_keys(self.couch.facilitator_doc(db))
        element = elements.get((village, project, cycle))
        if not element or not element.get('is_headquarters_village'):
            return {"status": "refused", "message": "Le village n'est plus un village siège d'affectation de ce facilitateur : rien n'a été transféré."}
        present = self.couch.find(db, docs_selector(village, project, cycle), fields=["_id"])
        present += self.couch.find(db, docs_selector(village, project, ""), fields=["_id"])
        if present:
            return {"status": "refused", "message": f"La base du facilitateur contient déjà {len(present)} document(s) de ce village : rien n'a été transféré."}
        if not ids:
            return {"status": "refused", "message": "Plus aucun document de ce village dans la sauvegarde pour cette source."}
        now = timezone.now().isoformat()

        def prepare(doc):
            doc.pop('backup_source', None)
            doc['transfer_history'] = _history(doc, {"from": BACKUP_DB, "source": source_db, "to": db, "at": now, "by": self.user_label})
            return doc
        copied, deleted, warnings = self.copy_then_delete(BACKUP_DB, db, ids, village, project, backup_cycle, prepare)
        repointed = self.repoint_share_records(village, project, cycle, source_db, target)
        return {"status": "ok", "copied": copied, "deleted": deleted, "warnings": warnings, "share_records": repointed,
                "message": f"{copied} document(s) copiés dans la base du facilitateur, {deleted} retiré(s) de la sauvegarde"
                           + (f", {repointed} suivi(s) de partage repointé(s)" if repointed else "") + "."}

    @staticmethod
    def repoint_share_records(village, project_couch, cycle_couch, source_db, target):
        """Suivis de tâches partageables du village tenus par l'ancien facilitateur -> nouveau (mêmes _id de tâches)."""
        if not target or not source_db:
            return 0
        source = Facilitator.objects.filter(no_sql_db_name=source_db).first()
        if not source:
            return 0
        qs = TaskShareRecord.objects.filter(administrative_level_id=int(village), project__couch_id=project_couch,
                                            facilitator=source, training_mode=target.training_mode,
                                            develop_mode=target.develop_mode)
        if cycle_couch:
            qs = qs.filter(cycle__couch_id=cycle_couch)
        return qs.update(facilitator=target)


def _user_label(user):
    return (user.get_full_name() or user.username) if user else ""


def run_transfers(operation_id, kind, items, user):
    """Corps d'un transfert (plusieurs groupes) : liste les documents de chaque groupe (total de la barre), puis
    transfère groupe par groupe ; un groupe en échec n'arrête pas les suivants."""
    progress = Progress(operation_id)
    couch = Couch()
    transfer = Transfer(couch, progress, operation_id, _user_label(user))
    listed = []
    for item in items:
        try:
            if kind == VillageDocsOperation.KIND_TO_BACKUP:
                ids = transfer.list_ids(item['db'], item['village'], item['project'], item['cycle'])
            else:
                ids = transfer.list_ids(BACKUP_DB, item['village'], item['project'], item.get('backup_cycle', item['cycle']),
                                        source=item.get('source', ''))
            listed.append((item, ids, None))
        except (CouchError, requests.RequestException) as exc:
            listed.append((item, [], str(exc)))
    progress.update(units_total=sum(len(ids) for _, ids, _ in listed))
    for item, ids, error in listed:
        progress.update(current=f"{item.get('label') or item['village']} — {item['db']}"[:255])
        if error:
            result = {"status": "error", "message": error}
        else:
            try:
                if kind == VillageDocsOperation.KIND_TO_BACKUP:
                    result = transfer.to_backup(item, ids)
                else:
                    result = transfer.from_backup(item, ids)
            except (CouchError, requests.RequestException) as exc:
                result = {"status": "error", "message": str(exc)}
        progress.item_done(dict(result, key=item['key'], label=item.get('label', '')))


class _SyncProgress:
    """Rappel `progress` de create_task_all_facilitators : un couple tâche × village traité = une unité."""

    def __init__(self, progress):
        self.progress = progress

    def __call__(self, event, db=None, total=None, created=None):
        if event == 'village':
            self.progress.add_units(1)


def run_sync(operation_id, groups):
    """groups : [{db, project_id, cycle_id, villages: [ids], tasks: [ids], develop_mode, training_mode, labels}]"""
    from dashboard.utils import sync_tasks
    progress = Progress(operation_id)
    callback = _SyncProgress(progress)
    for group in groups:
        progress.update(current=f"{group['db']} — {', '.join(group['labels'])}"[:255])
        before = VillageDocsOperation.objects.get(pk=operation_id).units_done
        try:
            sync_tasks(group['project_id'], group['cycle_id'], develop_mode=group['develop_mode'],
                       training_mode=group['training_mode'], no_sql_dbs=[group['db']],
                       administrativelevel_ids=[str(v) for v in group['villages']], tasks_ids=group['tasks'],
                       progress=callback)
            done = VillageDocsOperation.objects.get(pk=operation_id).units_done - before
            expected = len(group['villages']) * len(group['tasks'])
            result = {"status": "ok" if done >= expected else "warning",
                      "message": f"{done} / {expected} tâche(s) × village(s) synchronisée(s)"
                                 + ("" if done >= expected else " : vérifier que le village est bien un village siège du projet et du cycle dans CouchDB")}
        except Exception as exc:  # noqa: BLE001 - sync_tasks lève des Exception génériques
            logger.exception("Synchronisation documents de villages %s", group)
            result = {"status": "error", "message": f"{type(exc).__name__}: {exc}"}
        for key, label in zip(group['keys'], group['labels']):
            progress.item_done(dict(result, key=key, label=label))


# ---------------------------------------------------------------------------------------------------------------
# Déplacements automatiques à l'enregistrement des « Villages d'affectation (initiaux) » d'un facilitateur
# ---------------------------------------------------------------------------------------------------------------

def localities_move_keys(added, removed, kept):
    """(retirés, ajoutés) en clés (village, projet, cycle). Fonction pure.

    Retiré : élément qui n'est plus dans les villages d'affectation pour ce projet ET ce cycle ; les documents sans
    cycle_id du village partent aussi si le village n'est plus du tout dans le projet. Ajouté : village siège."""
    kept_full, kept_partial, _ = element_keys({'administrative_levels': kept or []})
    removed_keys = []
    for element in removed or []:
        if not isinstance(element, dict) or not str(element.get('id') or '').isdigit():
            continue
        key = (str(element['id']), _str(element.get('project_id')), _str(element.get('cycle_id')))
        if not key[1]:
            continue
        candidates = [key] if key[2] else []
        if key[:2] not in kept_partial:
            candidates.append(key[:2] + ("",))
        for k in candidates:
            if k not in kept_full and k not in removed_keys:
                removed_keys.append(k)
    added_keys = []
    for element in added or []:
        if not isinstance(element, dict) or not element.get('is_headquarters_village') or not str(element.get('id') or '').isdigit():
            continue
        key = (str(element['id']), _str(element.get('project_id')), _str(element.get('cycle_id')))
        if key[1] and key[2] and key not in added_keys:
            added_keys.append(key)
    return removed_keys, added_keys


def _backup_group(couch, village, project, cycle):
    """Meilleur groupe de la sauvegarde pour ce village : même cycle de préférence (sinon documents sans cycle),
    puis le plus de tâches terminées, de documents, le plus récent. (source, cycle du groupe, ids) ou None."""
    docs = couch.find(BACKUP_DB, {"type": {"$in": TYPES}, "project_id": project,
                                  "administrative_level_id": {"$in": [str(village), int(village)]}},
                      fields=["_id", "cycle_id", "type", "completed", "backup_source"])
    groups = {}
    for doc in docs:
        doc_cycle = _str(doc.get('cycle_id'))
        if doc_cycle not in (cycle, ""):
            continue
        source = doc.get('backup_source') if isinstance(doc.get('backup_source'), dict) else {}
        group = groups.setdefault((_str(source.get('db')), doc_cycle), {"ids": [], "completed": 0, "moved_at": ""})
        group["ids"].append(doc['_id'])
        group["completed"] += 1 if doc.get('type') == 'task' and doc.get('completed') else 0
        group["moved_at"] = max(group["moved_at"], _str(source.get('moved_at')))
    if not groups:
        return None
    (source, group_cycle), group = max(groups.items(), key=lambda kv: (
        kv[0][1] == cycle, kv[1]["completed"], len(kv[1]["ids"]), kv[1]["moved_at"]))
    return source, group_cycle, group["ids"]


def _current_holders(village, project, cycle, exclude_db, kind):
    """FC (même type de compte) qui ont maintenant ce village comme village siège d'affectation pour ce projet et ce
    cycle (copie en base `Facilitator.administrative_levels`, revérifiée dans CouchDB par from_backup)."""
    holders = []
    qs = Facilitator.objects.filter(facilitator_type='community_facilitator').exclude(no_sql_db_name=exclude_db) \
        .only('id', 'name', 'username', 'no_sql_db_name', 'administrative_levels', 'develop_mode', 'training_mode')
    for f in qs:
        if account_kind(f) != kind or not f.no_sql_db_name:
            continue
        for e in f.administrative_levels or []:
            if (isinstance(e, dict) and e.get('is_headquarters_village') and _str(e.get('id')) == village
                    and _str(e.get('project_id')) == project and _str(e.get('cycle_id')) == cycle):
                holders.append(f)
                break
    return holders


def run_localities_moves(operation_id, db, removed_keys, added_keys, labels, user):
    """Retirés : base du FC -> sauvegarde ; si un autre FC a déjà reçu ce village (ordre inverse : ajouté chez lui
    avant d'être retiré ici), les documents lui sont transmis aussitôt. Ajoutés : sauvegarde -> base du FC, si elle en
    contient. Un groupe sans document est ignoré sans bruit."""
    progress = Progress(operation_id)
    couch = Couch()
    transfer = Transfer(couch, progress, operation_id, _user_label(user))
    facilitator = Facilitator.objects.filter(no_sql_db_name=db).first()
    kind = account_kind(facilitator) if facilitator else "real"
    planned = []
    for village, project, cycle in removed_keys:
        item = {'key': row_key(db, village, project, cycle), 'db': db, 'village': village, 'project': project,
                'cycle': cycle, 'label': labels.get(village, village)}
        try:
            planned.append(('out', item, transfer.list_ids(db, village, project, cycle), None))
        except (CouchError, requests.RequestException) as exc:
            planned.append(('out', item, [], str(exc)))
    for village, project, cycle in added_keys:
        item = {'key': row_key(db, village, project, cycle), 'db': db, 'village': village, 'project': project,
                'cycle': cycle, 'label': labels.get(village, village)}
        try:
            found = _backup_group(couch, village, project, cycle)
            if found:
                item['source'], item['backup_cycle'], ids = found
                planned.append(('in', item, ids, None))
        except (CouchError, requests.RequestException) as exc:
            planned.append(('in', item, [], str(exc)))
    planned = [p for p in planned if p[2] or p[3]]
    progress.update(items_total=len(planned), units_total=sum(len(p[2]) for p in planned))

    for direction, item, ids, error in planned:
        arrow = "→ sauvegarde" if direction == 'out' else "← sauvegarde"
        label = f"{item['label']} {arrow}"
        progress.update(current=label[:255])
        if error:
            progress.item_done({"status": "error", "message": error, "key": item['key'], "label": label})
            continue
        try:
            if direction == 'out':
                result = transfer.to_backup(item, ids)
                if result.get('status') == 'ok':
                    result = _relay(transfer, progress, item, kind, result)
            else:
                result = transfer.from_backup(item, ids)
        except (CouchError, requests.RequestException) as exc:
            result = {"status": "error", "message": str(exc)}
        progress.item_done(dict(result, key=item['key'], label=label))


def _relay(transfer, progress, item, kind, result):
    """Après un retrait : documents transmis au FC qui a déjà ce village siège (un seul candidat), sinon gardés en
    sauvegarde (la page « Villages sans documents » permet de les transférer)."""
    holders = _current_holders(item['village'], item['project'], item['cycle'], item['db'], kind) if item['cycle'] else []
    if len(holders) != 1:
        return result
    holder = holders[0]
    target = dict(item, key=row_key(holder.no_sql_db_name, item['village'], item['project'], item['cycle']),
                  db=holder.no_sql_db_name, source=item['db'], backup_cycle=item['cycle'])
    ids = transfer.list_ids(BACKUP_DB, item['village'], item['project'], item['cycle'], source=item['db'])
    VillageDocsOperation.objects.filter(pk=progress.operation_id).update(units_total=F('units_total') + len(ids))
    relayed = transfer.from_backup(target, ids)
    name = holder.name or holder.username
    if relayed.get('status') == 'ok':
        return dict(result, message=f"{result['message']} Puis transmis à {name}, qui a ce village : {relayed['message']}")
    return dict(result, status="warning", message=f"{result['message']} Non transmis à {name} : {relayed['message']}")


def start_localities_moves(facilitator_db_name, added, removed, kept, user=None, background=True):
    """Lance (thread, en file derrière toute autre opération) les déplacements de documents des villages
    d'affectation ajoutés / retirés. Renvoie la VillageDocsOperation, ou None s'il n'y a rien à vérifier."""
    removed_keys, added_keys = localities_move_keys(added, removed, kept)
    if not removed_keys and not added_keys:
        return None
    labels = {}
    for element in list(removed or []) + list(added or []):
        if isinstance(element, dict) and element.get('name'):
            labels.setdefault(str(element.get('id')), element['name'])
    user = user if getattr(user, 'pk', None) else None
    op = create_operation(VillageDocsOperation.KIND_LOCALITIES, user,
                          {'db': facilitator_db_name, 'removed': removed_keys, 'added': added_keys},
                          0, queue=True, no_sql_db_name=facilitator_db_name)
    start_in_thread(op.id, run_localities_moves, facilitator_db_name, removed_keys, added_keys, labels, user,
                    background=background)
    return op


def start_in_thread(operation_id, target, *args, background=True):
    def worker():
        progress = Progress(operation_id)
        locked = False
        try:
            _acquire_lock(progress)
            locked = True
            target(operation_id, *args)
            progress.finish()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Opération documents de villages %s", operation_id)
            try:
                progress.finish(error=f"{type(exc).__name__}: {exc}")
            except Exception:  # noqa: BLE001
                logger.exception("VillageDocsOperation %s : échec non enregistré", operation_id)
        finally:
            if locked:
                try:
                    _release_lock()
                except Exception:  # noqa: BLE001 - la fermeture de la connexion libère aussi le verrou
                    logger.exception("VillageDocsOperation %s : verrou non libéré", operation_id)
            for conn in connections.all():
                conn.close()

    if not background:
        worker()
        return None
    thread = threading.Thread(target=worker, name=f"village_docs-{operation_id}", daemon=True)
    thread.start()
    return thread


def operation_json(op):
    now = timezone.now()
    state = 'interrupted' if op.is_stale() else op.status
    results = op.results or []
    return {
        "id": op.id, "kind": op.kind, "kind_label": op.get_kind_display(), "status": state,
        "running": state in VillageDocsOperation.ACTIVE_STATUSES,
        "db": op.no_sql_db_name,
        "started_at": timezone.localtime(op.started_at).strftime('%d/%m/%Y %H:%M:%S'),
        "finished_at": timezone.localtime(op.finished_at).strftime('%d/%m/%Y %H:%M:%S') if op.finished_at else None,
        "elapsed": int(((op.finished_at or now) - op.started_at).total_seconds()),
        "started_by": _user_label(op.started_by),
        "items_total": op.items_total, "items_done": op.items_done,
        "units_total": op.units_total, "units_done": op.units_done,
        "current": op.current, "error": op.error, "results": results,
        "ok": sum(1 for r in results if r.get('status') == 'ok'),
        "problems": sum(1 for r in results if r.get('status') != 'ok'),
    }


# ---------------------------------------------------------------------------------------------------------------
# Encart de progression (layouts/base.html) : déplacements automatiques lancés par l'utilisateur
# ---------------------------------------------------------------------------------------------------------------
# Suivi EN BASE (utilisateur qui a enregistré + `params.acknowledged` posé par « Fermer »), pas dans la session :
#  - visible PENDANT l'enregistrement (la session n'est écrite qu'à la fin de la requête, alors que le déplacement
#    tourne déjà dans son thread) ;
#  - pas de course entre requêtes simultanées qui réécrivaient la session (l'encart « revenait » après Fermer) ;
#  - même résultat quel que soit le processus ou l'instance qui sert la page.

TRACK_WINDOW = timedelta(hours=12)


def _tracked_queryset(user):
    if not getattr(user, 'is_authenticated', False):
        return VillageDocsOperation.objects.none()
    return VillageDocsOperation.objects.filter(
        kind=VillageDocsOperation.KIND_LOCALITIES, started_by=user,
        started_at__gte=timezone.now() - TRACK_WINDOW,
    ).exclude(params__contains={'acknowledged': True})  # pas params__acknowledged : NOT(NULL) exclurait tout


def track_operation(request, operation):
    """Conservée pour les appelants : le suivi se fait désormais en base (opération créée avec started_by)."""
    return operation


def has_tracked_operations(user):
    return _tracked_queryset(user).exists()


def tracked_operations(request):
    """Déplacements de l'utilisateur non fermés (les plus anciens d'abord)."""
    return list(_tracked_queryset(request.user).select_related('started_by').order_by('id')[:20])


def untrack_operations(request, ids):
    """« Fermer » : TOUTES les opérations de l'utilisateur terminées, en échec ou interrompues (sans nouvelle) sont
    masquées, pas seulement celles affichées : l'encart n'en montre que 20, et après un enregistrement de localités
    pour de nombreux facilitateurs, les suivantes réapparaissaient à chaque fermeture. `ids` est ignoré (conservé
    pour les appelants)."""
    for op in _tracked_queryset(request.user):
        if op.status in VillageDocsOperation.ACTIVE_STATUSES and not op.is_stale():
            continue  # encore en cours : reste affichée
        params = dict(op.params or {}, acknowledged=True)
        VillageDocsOperation.objects.filter(pk=op.pk).update(params=params)
