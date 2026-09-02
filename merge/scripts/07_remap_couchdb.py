"""
Étape 7 — Remappage des références externes (CouchDB).

Les documents CouchDB (bases `facilitator_*`, `administrative_levels`, `eadls`)
recopient des ID relationnels : `sql_id`, `administrative_level_id`,
`administrative_id`, `project_id`, `cycle_id`, `parent_id`, `user_id`, et des
listes d'ID. Cette étape les réécrit d'après `merge/id_map.csv`.

**Dry-run par défaut.** Aucune écriture sans `--apply` explicite.

Rappel de l'analyse (Étapes 3-4) : seuls changent les ID de `auth_user`,
`auth_group`, `process_manager_wave`, `process_manager_administrativelevelwave`
et les PK techniques de `auth_user_groups`. Les ID `administrativelevels_*`,
`subprojects_*`, `authentication_facilitator` (catégories B/C) sont inchangés.
Le remappage CouchDB est donc attendu quasi vide — le script le prouve.

Cible : http://127.0.0.1:5984 (root/root)

Usage :
    python merge/scripts/07_remap_couchdb.py            # dry-run
    python merge/scripts/07_remap_couchdb.py --apply    # écrit réellement
    python merge/scripts/07_remap_couchdb.py --limit-dbs 20
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ID_MAP = REPO / "merge" / "id_map.csv"
OUT = REPO / "merge" / "artifacts" / "70_checks"

BASE = "http://127.0.0.1:5984"
AUTH = "Basic " + base64.b64encode(b"root:root").decode()
csv.field_size_limit(1 << 24)

# champ CouchDB -> table SQL cible dont l'ID pourrait avoir changé
FIELD_TO_TABLE = {
    "user_id": "auth_user",
    "created_by": "auth_user",
    "sql_user_id": "auth_user",
    "wave_id": "process_manager_wave",
    "administrative_level_wave_id": "process_manager_administrativelevelwave",
    # informatifs — catégories B/C, ID inchangés, vérifiés mais jamais réécrits :
    "sql_id": "authentication_facilitator",
    "administrative_level_id": "administrativelevels_administrativelevel",
    "administrative_id": "administrativelevels_administrativelevel",
    "parent_id": "administrativelevels_administrativelevel",
    "project_id": "subprojects_project",
    "cycle_id": "subprojects_cycle",
}
DB_PREFIXES = ("facilitator_", "administrative_levels", "eadls", "adb",
               "process_design")


def http(method, path, body=None):
    req = urllib.request.Request(
        BASE + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": AUTH, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def load_id_map():
    m = defaultdict(dict)
    with ID_MAP.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row["reason"] in ("matched", "new_allocation") and row["new_id"]:
                if row["old_id"] != row["new_id"]:
                    m[row["table"]][row["old_id"]] = row["new_id"]
    return m


def scan_doc(doc, idmap):
    """Retourne [(chemin, table, old, new)] pour les champs à réécrire."""
    hits = []

    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                tbl = FIELD_TO_TABLE.get(k)
                if tbl and isinstance(v, (int, str)) and str(v).isdigit():
                    new = idmap.get(tbl, {}).get(str(v))
                    if new is not None:
                        hits.append((path + "/" + k, tbl, str(v), new))
                walk(v, path + "/" + k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")

    walk(doc, "")
    return hits


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--i-understand-ambiguity", action="store_true",
                    help="requis avec --apply : voir le caveat du rapport")
    ap.add_argument("--limit-dbs", type=int, default=0)
    args = ap.parse_args()
    if args.apply and not args.i_understand_ambiguity:
        raise SystemExit(
            "--apply refusé sans --i-understand-ambiguity : un `user_id` de "
            "valeur N dans un doc CouchDB peut désigner l'utilisateur CDD N "
            "(inchangé) OU l'utilisateur COSOMIS N (remappé). Confirmer que les "
            "bases scannées sont d'origine COSOMIS avant d'écrire.")
    OUT.mkdir(parents=True, exist_ok=True)

    idmap = load_id_map()
    changed_tables = {t: len(v) for t, v in idmap.items() if v}

    all_dbs = [d for d in http("GET", "/_all_dbs")
               if d.startswith(DB_PREFIXES)]
    if args.limit_dbs:
        all_dbs = all_dbs[:args.limit_dbs]

    per_db = {}
    field_hits = Counter()
    total_docs = total_hits = docs_touched = written = 0

    for db in all_dbs:
        rows = http("GET", f"/{db}/_all_docs?include_docs=true")["rows"]
        db_hits = 0
        updates = []
        for row in rows:
            doc = row.get("doc")
            if not doc:
                continue
            total_docs += 1
            hits = scan_doc(doc, idmap)
            if not hits:
                continue
            docs_touched += 1
            db_hits += len(hits)
            for path, tbl, old, new in hits:
                field_hits[f"{tbl}:{path.rsplit('/', 1)[-1]}"] += 1
                # applique dans le doc (copie) pour un éventuel --apply
                # (chemin simple : uniquement clés de 1er niveau ici)
            if args.apply:
                d2 = json.loads(json.dumps(doc))
                for path, tbl, old, new in hits:
                    key = path.strip("/")
                    if "/" not in key and "[" not in key:
                        d2[key] = int(new) if str(doc.get(key)).isdigit() else new
                updates.append(d2)
        total_hits += db_hits
        if db_hits:
            per_db[db] = db_hits
        if args.apply and updates:
            res = http("POST", f"/{db}/_bulk_docs", {"docs": updates})
            written += sum(1 for r in res if r.get("ok"))

    changed_desc = changed_tables or "aucune hors auth_*/wave*"
    rep = ["# Rapport — Étape 7 : Remappage CouchDB\n",
           f"- Généré : {datetime.now().isoformat(timespec='seconds')}",
           f"- Mode : {'APPLY' if args.apply else 'DRY-RUN'}",
           f"- Bases scannées : {len(all_dbs)} (préfixes {DB_PREFIXES})",
           f"- Documents parcourus : {total_docs}",
           f"- id_map : tables dont l'ID change = {changed_desc}",
           "",
           f"## Références à réécrire : **{total_hits}** "
           f"(dans {docs_touched} documents)"]
    if field_hits:
        for k, n in field_hits.most_common():
            rep.append(f"- `{k}` : {n}")
    else:
        rep.append("- **Aucune.** Les ID référencés dans CouchDB "
                   "(`administrative_level_id`, `sql_id`, `parent_id`, "
                   "`project_id`, `cycle_id`) appartiennent tous à des tables "
                   "de catégorie B/C : leurs ID sont transportés inchangés. "
                   "Rien à remapper.")
    if per_db:
        rep.append("\n## Par base")
        for db, n in sorted(per_db.items(), key=lambda x: -x[1]):
            rep.append(f"- `{db}` : {n}")
    rep.append("\n## ⚠ Caveat — ambiguïté d'origine")
    rep.append("Ces occurrences sont des **candidats**, pas des réécritures "
               "sûres. Le scan repère tout `user_id = N` où `N` figure dans "
               "`id_map[auth_user]` (57 utilisateurs COSOMIS dont l'ID a "
               "changé). Mais un `user_id = N` peut aussi désigner "
               "l'utilisateur **CDD** N, dont l'ID est inchangé : le réécrire "
               "corromprait la référence. Avant tout `--apply` :")
    rep.append("1. Confirmer que les bases `facilitator_*` scannées "
               "synchronisent avec le backend **COSOMIS** (donc `user_id` = ID "
               "COSOMIS).")
    rep.append("2. Sinon, restreindre le remap aux bases dont on sait "
               "l'origine, ou ajouter un discriminant dans les docs.")
    if args.apply:
        rep.append(f"\n## Écriture : {written} documents mis à jour")
    else:
        rep.append("\n## Suite")
        rep.append("Dry-run uniquement (décision). `--apply` exige "
                   "`--i-understand-ambiguity` après levée du caveat ci-dessus.")
    (OUT / "rapport_remap_couchdb.md").write_text("\n".join(rep) + "\n", "utf-8")
    print("\n".join(rep))


if __name__ == "__main__":
    main()
