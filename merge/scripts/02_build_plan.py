"""
Étape 2 — Plan de fusion.

Produit `merge/fusion_plan.yml` (déclaratif) + `merge/artifacts/20_plan/rapport_plan.md`.

Entrées : artefacts des Étapes 0 et 1
  - merge/artifacts/10_inventory/ownership.csv        (catégories §4.1 fermes)
  - merge/artifacts/10_inventory/schema_inventory.json
  - merge/artifacts/00_raw/{cdd,mis}/_information_schema.json
  - merge/artifacts/00_raw/{cdd,mis}/<table>.csv      (contrôle d'unicité des clés)

Le plan ne contient AUCUNE règle métier en dur côté code de fusion : tout est ici.

§4.5 : pour chaque table de catégorie A dotée d'une clé naturelle, l'unicité
réelle est vérifiée des deux côtés. Si elle échoue, le plan est marqué BLOCKED
et le script sort en code 2.

Idempotent, lecture seule des artefacts. Aucune connexion base.

Usage :
    python merge/scripts/02_build_plan.py
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
INV = REPO / "merge" / "artifacts" / "10_inventory"
RAW = REPO / "merge" / "artifacts" / "00_raw"
OUT = REPO / "merge" / "artifacts" / "20_plan"
PLAN_YML = REPO / "merge" / "fusion_plan.yml"

csv.field_size_limit(1 << 24)

# --- Config des décisions (voir merge/README.md) -------------------------
NATURAL_KEYS: dict[str, dict] = {
    "auth_group": {"key": ["name"]},
    "auth_user": {"key": ["username"], "crosscheck": ["email"]},
    "process_manager_wave": {"key": ["number"]},
    "process_manager_administrativelevelwave": {
        # (project, wave.number, administrative_level_id)
        "key": ["project_id", "wave.number", "administrative_level_id"],
        "resolve": {"wave.number": ("wave_id", "process_manager_wave", "number")},
    },
}
# Tables A « techniques » (M2M / jetons) : pas de clé naturelle, PK id
# transportée (§4.4), FK remappées, dédoublonnage sur le couple de FK.
LINK_TABLES_A = {
    "auth_user_groups": ["user_id", "group_id"],
    "auth_group_permissions": ["group_id", "permission_id"],
    "auth_user_user_permissions": ["user_id", "permission_id"],
    "authtoken_token": ["user_id"],  # PK = key (chaîne), user_id unique
}
# Étape 3 : champs où COSOMIS gagne le conflit de valeur (sinon CDD gagne).
# Les seules tables A sont auth_* et process_manager_wave* : aucun champ
# financier/statut ici. Laisser vide sauf décision explicite.
COSOMIS_WINS_FIELDS: dict[str, list[str]] = {}

DJANGO_REBUILT = {
    "django_migrations", "django_content_type", "auth_permission",
    "django_session", "django_admin_log",
}
DJANGO_REBUILT_PREFIX = ("django_celery_results", "django_celery_beat")

PERMISSIVE_RANK = ["tinyint", "smallint", "int", "bigint",
                   "float", "double", "decimal"]


def load_is(db: str) -> dict:
    return json.loads((RAW / db / "_information_schema.json").read_text("utf-8"))


def cols_of(meta: dict, table: str) -> dict:
    return {c["column_name"]: c for c in meta["columns"]
            if c["table_name"] == table}


def more_permissive(t_cdd: str, t_mis: str) -> str:
    def rank(t):
        base = t.split("(")[0].strip().lower()
        return PERMISSIVE_RANK.index(base) if base in PERMISSIVE_RANK else -1
    if t_cdd == t_mis:
        return t_cdd
    r1, r2 = rank(t_cdd), rank(t_mis)
    if r1 >= 0 and r2 >= 0:
        return t_cdd if r1 >= r2 else t_mis
    # longueurs varchar : prendre la plus grande
    def length(t):
        if "(" in t and t.split("(")[0].strip() in ("varchar", "char"):
            try:
                return int(t.split("(")[1].split(")")[0])
            except ValueError:
                return -1
        return -1
    l1, l2 = length(t_cdd), length(t_mis)
    if l1 >= 0 and l2 >= 0:
        return t_cdd if l1 >= l2 else t_mis
    return f"{t_cdd} | {t_mis}  # à trancher"


def read_csv_rows(db: str, table: str) -> tuple[list[str], list[list[str]]]:
    p = RAW / db / f"{table}.csv"
    with p.open(encoding="utf-8", newline="") as fh:
        r = csv.reader(fh)
        header = next(r)
        return header, list(r)


def check_natural_key_unique(table: str, spec: dict, report: list) -> dict:
    """Retourne {'cdd': 'unique'|'DOUBLONS: ...', 'mis': ...}. §4.5."""
    result = {}
    key = spec["key"]
    resolve = spec.get("resolve", {})
    for db in ("cdd", "mis"):
        try:
            header, rows = read_csv_rows(db, table)
        except FileNotFoundError:
            result[db] = "table absente"
            continue
        idx = {c: i for i, c in enumerate(header)}
        # tables de résolution (ex. wave_id -> wave.number)
        maps = {}
        for logical, (fkcol, rtable, rcol) in resolve.items():
            rh, rr = read_csv_rows(db, rtable)
            ridx = {c: i for i, c in enumerate(rh)}
            maps[logical] = (fkcol, {row[ridx["id"]]: row[ridx[rcol]]
                                    for row in rr})
        seen = Counter()
        for row in rows:
            parts = []
            for k in key:
                if k in maps:
                    fkcol, m = maps[k]
                    parts.append(m.get(row[idx[fkcol]], "<?>"))
                else:
                    parts.append(row[idx[k]])
            seen[tuple(parts)] += 1
        dups = {k: v for k, v in seen.items() if v > 1}
        if dups:
            sample = list(dups.items())[:5]
            result[db] = f"DOUBLONS ({len(dups)}) ex.{sample}"
            report.append(f"⛔ {table} [{db}] clé {key} NON UNIQUE : {sample}")
        else:
            result[db] = "unique"
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    own = list(csv.DictReader((INV / "ownership.csv").open(encoding="utf-8")))
    sinv = json.loads((INV / "schema_inventory.json").read_text("utf-8"))
    is_cdd, is_mis = load_is("cdd"), load_is("mis")

    # index modèles par db_table pour retrouver la déclaration miroir à retirer
    models_by_table = defaultdict(list)
    for proj in ("cdd", "cosomis"):
        for m in sinv["projects"][proj]["models"]:
            models_by_table[(proj, m["db_table"])].append(m)

    # FK réelles -> pour calculer les colonnes à remapper
    fk_to = defaultdict(list)   # referenced_table -> [(db, table, column)]
    for db, meta in (("cdd", is_cdd), ("mis", is_mis)):
        for f in meta["foreign_keys"]:
            fk_to[f["referenced_table_name"]].append(
                (db, f["table_name"], f["column_name"]))

    report: list[str] = []
    blocked = False
    tables_plan: dict[str, dict] = {}

    A_TABLES = {r["table"] for r in own if r["categorie"].startswith("A")}

    for r in own:
        t = r["categorie"]
        table = r["table"]
        cat = t.split(" ")[0]
        entry: dict = {"category": cat}

        if table in DJANGO_REBUILT or table.startswith(DJANGO_REBUILT_PREFIX):
            entry.update(strategy="rebuild",
                         note="reconstruite par Django (§4.6) — non fusionnée")
            tables_plan[table] = entry
            continue

        if cat == "A":
            entry["strategy"] = "merge"
            entry["rows"] = {"cdd": r["lignes_cdd"], "mis": r["lignes_cosomis"]}
            if table in NATURAL_KEYS:
                spec = NATURAL_KEYS[table]
                entry["natural_key"] = spec["key"]
                if spec.get("crosscheck"):
                    entry["natural_key_crosscheck"] = spec["crosscheck"]
                chk = check_natural_key_unique(table, spec, report)
                entry["natural_key_unicity"] = chk
                if any(v.startswith("DOUBLONS") for v in chk.values()):
                    blocked = True
                    entry["status"] = "BLOCKED — clé naturelle non unique (§4.5)"
            elif table in LINK_TABLES_A:
                entry["natural_key"] = None
                entry["link_columns"] = LINK_TABLES_A[table]
                entry["dedupe_on"] = LINK_TABLES_A[table]
                entry["note"] = ("table de liaison : PK id transportée (§4.4), "
                                 "FK remappées, dédoublonnage sur link_columns")
            # réconciliation de schéma sur colonnes physiques (§4.2/§4.3)
            cc, mc = cols_of(is_cdd, table), cols_of(is_mis, table)
            added = sorted(set(mc) - set(cc))
            if added:
                entry["fields_added_from_cosomis"] = [
                    {"name": n, "type": mc[n]["column_type"],
                     "force": "null=True, blank=True"} for n in added]
            conflicts = []
            for n in sorted(set(cc) & set(mc)):
                if cc[n]["column_type"] != mc[n]["column_type"]:
                    conflicts.append({
                        "name": n,
                        "cdd": cc[n]["column_type"], "cosomis": mc[n]["column_type"],
                        "retained": more_permissive(cc[n]["column_type"],
                                                    mc[n]["column_type"]),
                    })
            if conflicts:
                entry["field_conflicts"] = conflicts
            only_cdd = sorted(set(cc) - set(mc))
            if only_cdd:
                entry["fields_cdd_only_kept"] = only_cdd
            # id + valeurs
            entry["id_policy"] = ("ligne appariée → id CDD ; ligne COSOMIS "
                                  "seule → nouvel id > MAX(cdd.id) ; via id_map")
            entry["value_conflict"] = "cdd_wins"
            if COSOMIS_WINS_FIELDS.get(table):
                entry["value_conflict_exceptions_cosomis_wins"] = \
                    COSOMIS_WINS_FIELDS[table]
            # colonnes d'autres tables qui référencent cette table A -> remap
            remap = sorted({(db, tb, col) for (db, tb, col) in fk_to.get(table, [])
                            if db == "mis"})
            entry["remap_incoming_fk"] = [
                {"db": db, "table": tb, "column": col} for db, tb, col in remap]

        elif cat == "B":
            owner = "cosomis" if "propriétaire=cosomis" in t else "cdd"
            non_owner = "cdd" if owner == "cosomis" else "cosomis"
            entry["strategy"] = "mirror"
            entry["schema_owner"] = owner
            entry["data_source"] = owner
            entry["id_policy"] = "aucun — table physique unique (§4.4)"
            entry["id_map_entries"] = "aucune"
            dead = models_by_table.get((non_owner, table), [])
            entry["code_action"] = {
                "project": non_owner,
                "remove_mirror_declaration": [m["model_key"] for m in dead]
                or ["(déclaration à localiser manuellement)"],
                "modules": sorted({m["model_module"] for m in dead}),
            }

        elif cat == "C":
            side = "cdd" if "cdd_only" in t else "mis"
            entry["strategy"] = f"{side}_only"
            entry["data_source"] = "cdd" if side == "cdd" else "cosomis"
            entry["id_policy"] = "transport tel quel (ids inchangés)"

        elif cat.startswith("orpheline"):
            entry["strategy"] = "skip"
            entry["note"] = ("déclarée dans le code, aucune table physique — "
                             "déclaration morte, nettoyage Étape 6")
        elif cat.startswith("physique_sans"):
            entry["strategy"] = "skip"
            entry["note"] = "table physique sans modèle Django — ignorée"
        else:
            entry["strategy"] = "TODO"
            entry["note"] = t

        tables_plan[table] = entry

    # --- FK molles / JSON listes d'ID (§1) --------------------------------
    # Seuls les ID de catégorie A changent (auth_user, auth_group,
    # process_manager_wave*). Les ID B/C sont transportés tels quels → aucun
    # remap. Côté CDD, tous les ID sont conservés (§4.4) → aucun remap non plus.
    # Ne reste donc à traiter que des colonnes « molles » CÔTÉ MIS.
    #
    # Échantillonnage des données (Étape 0) :
    #   - create_by_user / update_by_user : snapshot JSON de l'objet user
    #     ({"id": N, "username": ..., "password": ...}) → remapper la clé .id
    #   - users_involved : journal d'audit libre imbriqué → PAS de remap fiable
    #   - *_administrative_ids / administrative_level_id : pointent adl
    #     (catégorie B, ID inchangés) → aucun remap
    real_fk_cols = {(db, f["table_name"], f["column_name"])
                    for db, meta in (("cdd", is_cdd), ("mis", is_mis))
                    for f in meta["foreign_keys"]}
    soft_remap: list[dict] = []
    for m in sinv["projects"]["cosomis"]["models"]:
        tb, db = m["db_table"], "mis"
        strat = tables_plan.get(tb, {}).get("strategy", "")
        if strat not in ("merge", "mirror", "cdd_only", "mis_only"):
            continue
        for f in m["fields"]:
            nm, ft = f["name"], f["type"]
            if (db, tb, f.get("column")) in real_fk_cols:
                continue
            if nm in ("create_by_user", "update_by_user") and ft == "JSONField":
                soft_remap.append({
                    "db": db, "table": tb, "column": nm, "structure":
                    "user_snapshot", "target": "auth_user",
                    "action": "remap_json_key:id via id_map(auth_user)",
                    "confirm": True})
            elif nm == "users_involved" and ft == "JSONField":
                soft_remap.append({
                    "db": db, "table": tb, "column": nm, "structure":
                    "audit_libre", "target": "auth_user",
                    "action": "aucun_remap (journal d'audit — trop imbriqué)",
                    "confirm": False})
            elif nm.endswith(("_administrative_ids", "_ids")) and ft == "JSONField":
                soft_remap.append({
                    "db": db, "table": tb, "column": nm, "structure":
                    "id_list", "target": "administrativelevels_administrativelevel",
                    "action": "aucun_remap (cat. B, ID inchangés)",
                    "confirm": False})
            elif nm == "administrative_level_id":
                soft_remap.append({
                    "db": db, "table": tb, "column": nm, "structure": "soft_fk",
                    "target": "administrativelevels_administrativelevel",
                    "action": "aucun_remap (cat. B, ID inchangés)",
                    "confirm": False})

    plan = {
        "meta": {
            "generated_by": "merge/scripts/02_build_plan.py",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "pilote": "src/CLAUDE.md §4-5",
            "source_databases": {
                "cdd": {"engine": is_cdd["server_version"],
                        "charset": is_cdd["charset_server"],
                        "collation": is_cdd["collation_server"]},
                "mis": {"engine": is_mis["server_version"],
                        "charset": is_mis["charset_server"],
                        "collation": is_mis["collation_server"]},
            },
            "status": "BLOCKED" if blocked else "OK",
        },
        "defaults": {
            "value_conflict": "cdd_wins",
            "null_fill_from_cosomis": True,
            "case_insensitive_lookup_scope": ["auth_user.username", "auth_user.email"],
            "mysql_to_pg": {
                "tinyint1_to_bool": True,
                "zero_dates_to_null": True,
                "naive_datetime_tz": "UTC (à vérifier sur échantillon — Togo = UTC+0)",
                "json_validate_before_load": True,
            },
        },
        "categories_count": dict(Counter(v["category"].split(" ")[0]
                                         for v in tables_plan.values())),
        "soft_remap": soft_remap,
        "tables": tables_plan,
    }

    PLAN_YML.write_text(
        "# Généré par merge/scripts/02_build_plan.py — déclaratif, à relire.\n"
        "# Ne pas éditer le code de fusion pour y mettre des règles : tout est ici.\n\n"
        + yaml.safe_dump(plan, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
    )

    # -------- rapport --------
    rep = ["# Rapport — Étape 2 : Plan de fusion\n"]
    rep.append(f"- Généré : {plan['meta']['generated_at']}")
    rep.append(f"- Statut : **{plan['meta']['status']}**")
    rep.append(f"- Plan : `merge/fusion_plan.yml` ({len(tables_plan)} tables)")
    rep.append("")
    rep.append("## Répartition")
    for k, v in sorted(plan["categories_count"].items()):
        rep.append(f"- {k} : {v}")
    rep.append("")
    rep.append("## Catégorie A — réconciliation")
    for tb in sorted(A_TABLES):
        e = tables_plan[tb]
        rep.append(f"\n### `{tb}`")
        rep.append(f"- clé naturelle : {e.get('natural_key')}")
        if "natural_key_unicity" in e:
            rep.append(f"- unicité : {e['natural_key_unicity']}")
        if e.get("fields_added_from_cosomis"):
            rep.append("- champs ajoutés de COSOMIS (null=True) : "
                       + ", ".join(f["name"] for f in e["fields_added_from_cosomis"]))
        if e.get("field_conflicts"):
            for c in e["field_conflicts"]:
                rep.append(f"- conflit type `{c['name']}` : CDD {c['cdd']} / "
                           f"COSOMIS {c['cosomis']} → retenu {c['retained']}")
        if e.get("fields_cdd_only_kept"):
            rep.append("- champs CDD seuls conservés : "
                       + ", ".join(e["fields_cdd_only_kept"]))
        if e.get("remap_incoming_fk"):
            rep.append("- FK entrantes à remapper (côté mis) : "
                       + ", ".join(f"{x['table']}.{x['column']}"
                                   for x in e["remap_incoming_fk"]))
        if e.get("status"):
            rep.append(f"- ⚠ {e['status']}")
    rep.append("")
    rep.append("## Catégorie B — miroirs (déclaration en double à retirer)")
    for r in own:
        if not r["categorie"].startswith("B"):
            continue
        e = tables_plan[r["table"]]
        ca = e["code_action"]
        rep.append(f"- `{r['table']}` — propriétaire **{e['schema_owner']}** ; "
                   f"retirer dans **{ca['project']}** : "
                   f"{', '.join(ca['remove_mirror_declaration'])}")
    rep.append("")
    rep.append("## FK molles / JSON (§1) — côté mis uniquement")
    to_remap = [s for s in soft_remap if s["confirm"]]
    no_remap = [s for s in soft_remap if not s["confirm"]]
    rep.append(f"- **{len(to_remap)}** colonne(s) `create_by_user`/`update_by_user` "
               "(snapshot user) → remapper la clé JSON `.id` via id_map(auth_user).")
    rep.append(f"- {len(no_remap)} colonne(s) sans remap : `users_involved` "
               "(audit libre) et les listes d'ID adl (catégorie B, ID inchangés).")
    rep.append("- Détail complet dans `fusion_plan.yml` → `soft_remap`.")
    rep.append("")
    if report:
        rep.append("## Alertes")
        for line in report:
            rep.append(f"- {line}")
    rep.append("")
    rep.append("## Suite")
    if blocked:
        rep.append("Plan **BLOCKED** : corriger les clés naturelles non uniques "
                   "avant l'Étape 3.")
    else:
        rep.append("Plan **OK** → Étape 3 : `merge/scripts/03_build_id_map.py`.")
    (OUT / "rapport_plan.md").write_text("\n".join(rep) + "\n", encoding="utf-8")

    print("fusion_plan.yml :", plan["meta"]["status"])
    print("rapport :", OUT / "rapport_plan.md")
    for line in report:
        print("  ", line)
    if blocked:
        sys.exit(2)


if __name__ == "__main__":
    main()
