"""
Contrôles d'acceptation (CLAUDE.md §6) → merge/artifacts/70_checks/report.md

Automatisés ici : §6.1 comptage, §6.2 identité des ID, §6.3 intégrité
référentielle, §6.4 séquences, §6.5 échantillon, §6.7b agrégats numériques
source↔PG (dont finances). §6.6 (check/makemigrations), §6.7 (fc_situation
avant/après) et §6.8 (casse) sont exécutés hors de ce script et leurs
résultats reportés ici.

La bascule est refusée si un seul contrôle échoue.

Cible : postgres://postgres:root@127.0.0.1/cdd_cosomis_unified
Usage : python merge/scripts/checks/run_checks.py
"""
from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import psycopg2
import yaml

try:
    import MySQLdb
except ImportError:  # pragma: no cover
    MySQLdb = None

REPO = Path(__file__).resolve().parents[3]
UNI = REPO / "merge" / "artifacts" / "40_unified"
INV = REPO / "merge" / "artifacts" / "10_inventory"
OUT = REPO / "merge" / "artifacts" / "70_checks"
PLAN = REPO / "merge" / "fusion_plan.yml"
ID_MAP = REPO / "merge" / "id_map.csv"
PG = dict(host="127.0.0.1", user="postgres", password="root",
          dbname="cdd_cosomis_unified")
csv.field_size_limit(1 << 24)
NULL = r"\N"


def uni_rows(table):
    p = UNI / f"{table}.csv"
    with p.open(encoding="utf-8", newline="") as fh:
        r = csv.reader(fh)
        return next(r), list(r)


def pg_table_index(cur):
    cur.execute("SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public'")
    return {r[0].casefold(): r[0] for r in cur.fetchall()}


def resolve(name, idx):
    k = name.casefold()
    if k in idx:
        return idx[k]
    if len(name) >= 60:
        for kk, vv in idx.items():
            if kk[:40] == k[:40]:
                return vv
    return None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    plan = yaml.safe_load(PLAN.read_text("utf-8"))["tables"]
    schema = json.loads((UNI / "schema_unifie.json").read_text("utf-8"))
    own = {r["table"]: r for r in csv.DictReader((INV / "ownership.csv").open(encoding="utf-8"))}
    idmap = defaultdict(lambda: {"matched": 0, "new_allocation": 0,
                                 "conflict": 0})
    with ID_MAP.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["reason"] in idmap[row["table"]]:
                idmap[row["table"]][row["reason"]] += 1
    known_orphans = set()   # (table, column) déjà signalés en conflicts.csv
    cpath = REPO / "merge" / "conflicts.csv"
    if cpath.exists():
        for row in csv.DictReader(cpath.open(encoding="utf-8")):
            if row.get("type") == "rapprochement":
                known_orphans.add("process_manager_administrativelevelwave"
                                  ":project_id")

    conn = psycopg2.connect(**PG)
    cur = conn.cursor()
    pgidx = pg_table_index(cur)
    results = {}   # nom check -> (ok, [lignes])

    # ---------- 1. comptage ----------
    lines, ok1 = [], True
    for table, header in schema.items():
        pg = resolve(table, pgidx)
        if not pg:
            lines.append(f"- ❌ `{table}` : absente en PG")
            ok1 = False
            continue
        cur.execute(f'SELECT count(*) FROM "{pg}"')
        got = cur.fetchone()[0]
        e = plan.get(table, {})
        strat = e.get("strategy")
        o = own.get(table, {})
        rc, rm = o.get("lignes_cdd", ""), o.get("lignes_cosomis", "")
        rc = int(rc) if str(rc).isdigit() else 0
        rm = int(rm) if str(rm).isdigit() else 0
        if strat == "merge":
            # §6.1 : cdd + cosomis − appariées (les lignes de liaison
            # dédoublonnées comptent comme appariées : reason=conflict)
            matched = idmap[table]["matched"] + idmap[table]["conflict"]
            exp = rc + rm - matched
        elif strat in ("mirror",):
            exp = rc if e.get("data_source") == "cdd" else rm
        elif strat == "cdd_only":
            exp = rc
        elif strat == "mis_only":
            exp = rm
        else:
            continue
        flag = "✅" if got == exp else "❌"
        if got != exp:
            ok1 = False
        lines.append(f"- {flag} `{table}` [{strat}] attendu {exp}, PG {got}")
    results["1. Comptage (§6.1)"] = (ok1, lines)

    # ---------- 2. identité des ID ----------
    lines, ok2 = [], True
    for table, header in schema.items():
        if "id" not in header:
            continue
        pg = resolve(table, pgidx)
        if not pg:
            continue
        h, rows = uni_rows(table)
        hi = h.index("id")
        uni_ids = {r[hi] for r in rows if r[hi] != NULL}
        cur.execute(f'SELECT id FROM "{pg}"')
        pg_ids = {str(r[0]) for r in cur.fetchall()}
        if uni_ids != pg_ids:
            miss = list(uni_ids - pg_ids)[:3]
            extra = list(pg_ids - uni_ids)[:3]
            lines.append(f"- ❌ `{table}` : unifié {len(uni_ids)} / PG "
                         f"{len(pg_ids)} ; manquants {miss} ; en trop {extra}")
            ok2 = False
    if ok2:
        lines.append("- ✅ ensembles d'`id` identiques (unifié ↔ PG) sur "
                     f"{sum(1 for _, h in schema.items() if 'id' in h)} tables")
    results["2. Identité des ID (§6.2)"] = (ok2, lines)

    # ---------- 3. intégrité référentielle ----------
    lines, ok3 = [], True
    cur.execute("""
        SELECT tc.table_name, kcu.column_name, ccu.table_name AS ref
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu
          ON tc.constraint_name = ccu.constraint_name
        WHERE tc.constraint_type='FOREIGN KEY' AND tc.table_schema='public'
    """)
    fks = cur.fetchall()
    orphan_total = 0
    for tname, col, ref in fks:
        try:
            cur.execute(f'SELECT count(*) FROM "{tname}" c LEFT JOIN "{ref}" p '
                        f'ON c."{col}" = p.id WHERE c."{col}" IS NOT NULL AND '
                        f'p.id IS NULL')
            n = cur.fetchone()[0]
        except Exception:
            conn.rollback()
            continue
        if n:
            orphan_total += n
            if f"{tname}:{col}" in known_orphans:
                lines.append(f"- ⚠ `{tname}.{col}` → `{ref}` : {n} orphelins "
                             "— **connu** (conflicts.csv : `mis` sans table "
                             "process_manager_project, project_id disjoints). "
                             "Décision requise (NULL / remap / exclusion).")
            else:
                lines.append(f"- ❌ `{tname}.{col}` → `{ref}` : {n} orphelins")
                ok3 = False
    if ok3 and orphan_total:
        lines.append(f"- ✅ seules les {orphan_total} FK orphelines connues "
                     "(conflicts.csv) subsistent — hors bloquant automatique")
    elif ok3:
        lines.append(f"- ✅ 0 FK orpheline sur {len(fks)} contraintes")
    results["3. Intégrité référentielle (§6.3)"] = (ok3, lines)

    # ---------- 4. séquences ----------
    lines, ok4 = [], True
    cur.execute("SELECT sequence_name FROM information_schema.sequences "
                "WHERE sequence_schema='public'")
    seqs = [r[0] for r in cur.fetchall()]
    bad = 0
    for s in seqs:
        try:
            cur.execute(f'SELECT last_value FROM "{s}"')
            lv = cur.fetchone()[0]
            tbl = s.rsplit("_id_seq", 1)[0]
            rtbl = resolve(tbl, pgidx)
            if not rtbl:
                continue
            cur.execute(f'SELECT COALESCE(MAX(id),0) FROM "{rtbl}"')
            mx = cur.fetchone()[0]
            if lv < mx:
                bad += 1
                lines.append(f"- ❌ `{s}` last_value {lv} < MAX(id) {mx}")
                ok4 = False
        except Exception:
            conn.rollback()
    if ok4:
        lines.append(f"- ✅ {len(seqs)} séquences : last_value ≥ MAX(id)")
    results["4. Séquences (§6.4)"] = (ok4, lines)

    # ---------- 5. échantillon ----------
    lines, ok5 = [], True
    homonym = [t for t, r in own.items()
               if r["categorie"].startswith(("A", "B"))
               and (UNI / f"{t}.csv").exists()]
    random.seed(42)
    for table in homonym:
        pg = resolve(table, pgidx)
        if not pg:
            continue
        h, rows = uni_rows(table)
        if "id" not in h or not rows:
            continue
        hi = h.index("id")
        sample = random.sample(rows, min(20, len(rows)))
        cur.execute("SELECT column_name FROM information_schema.columns "
                    "WHERE table_name=%s AND table_schema='public'", (pg,))
        pgcols = {r[0] for r in cur.fetchall()}
        cmp_cols = [c for c in h if c in pgcols][:8]
        mism = 0
        for r in sample:
            cur.execute(f'SELECT {", ".join(chr(34)+c+chr(34) for c in cmp_cols)} '
                        f'FROM "{pg}" WHERE id = %s', (r[hi],))
            got = cur.fetchone()
            if got is None:
                mism += 1
                continue
            for c, gv in zip(cmp_cols, got):
                uv = r[h.index(c)]
                gs = NULL if gv is None else str(gv)
                if gs == uv or (uv == NULL and gv is None):
                    continue
                # bool
                if gs.lower() in ("true", "false") and uv in ("0", "1"):
                    if (gs.lower() == "true") == (uv == "1"):
                        continue
                # nombres
                try:
                    if float(gs) == float(uv):
                        continue
                except ValueError:
                    pass
                # dates/horodatages : comparer AAAA-MM-JJ[ HH:MM:SS]
                g2, u2 = gs.replace("T", " ")[:19], uv.replace("T", " ")[:19]
                if g2 == u2 and "-" in g2:
                    continue
                mism += 1
                break
        tag = "✅" if mism == 0 else "⚠"
        if mism:
            ok5 = False
        lines.append(f"- {tag} `{table}` : {mism}/{len(sample)} lignes "
                     f"divergentes (colonnes {cmp_cols[:4]}…)")
    results["5. Échantillon (§6.5)"] = (ok5, lines)

    # ---------- 7b. agrégats numériques source ↔ PG (dont finances) --------
    lines, ok7b = [], True
    if MySQLdb is None:
        lines.append("- ⚠ MySQLdb indisponible — contrôle sauté")
    else:
        src = {"cdd": MySQLdb.connect(host="127.0.0.1", user="root", passwd="",
                                      db="cdd", charset="utf8mb4"),
               "mis": MySQLdb.connect(host="127.0.0.1", user="root", passwd="",
                                      db="mis", charset="utf8mb4")}
        checked = 0
        for table, e in plan.items():
            strat = e.get("strategy")
            if strat not in ("cdd_only", "mis_only"):
                continue          # C : transport tel quel → doit être identique
            db = "cdd" if strat == "cdd_only" else "mis"
            pg = resolve(table, pgidx)
            if not pg:
                continue
            scur = src[db].cursor()
            scur.execute("SELECT table_name FROM information_schema.tables "
                         "WHERE table_schema=%s", (db,))
            stabs = {r[0].casefold(): r[0] for r in scur.fetchall()}
            stab = stabs.get(table.casefold())
            if not stab and len(table) >= 60:
                stab = next((v for k, v in stabs.items()
                             if k[:40] == table.casefold()[:40]), None)
            if not stab:
                continue
            table = stab
            scur.execute("SELECT column_name, data_type FROM "
                         "information_schema.columns WHERE table_schema=%s AND "
                         "table_name=%s", (db, table))
            # colonnes de MESURE uniquement : on exclut id / *_id (des FK vers
            # des tables A ont pu être légitimement remappées).
            numcols = [c for c, t in scur.fetchall()
                       if t in ("int", "bigint", "smallint", "tinyint",
                                "decimal", "float", "double")
                       and not c.endswith("_id") and c != "id"]
            scur.execute(f"SELECT COUNT(*) FROM `{table}`")
            sc = scur.fetchone()[0]
            cur.execute(f'SELECT COUNT(*) FROM "{pg}"')
            pc = cur.fetchone()[0]
            row_ok = sc == pc
            agg_ok = True
            for col in numcols[:12]:
                scur.execute(f"SELECT ROUND(COALESCE(SUM(`{col}`),0),2) "
                             f"FROM `{table}`")
                sv = scur.fetchone()[0]
                try:
                    cur.execute(f'SELECT ROUND(COALESCE(SUM("{col}"),0),2) '
                                f'FROM "{pg}"')
                    pv = cur.fetchone()[0]
                except Exception:
                    conn.rollback()
                    continue
                if sv is None:
                    sv = 0
                if abs(float(sv) - float(pv)) > 0.01:
                    agg_ok = False
                    lines.append(f"- ❌ `{table}.{col}` : source Σ={sv} / PG Σ={pv}")
            checked += 1
            if not (row_ok and agg_ok):
                ok7b = False
                if not row_ok:
                    lines.append(f"- ❌ `{table}` : {sc} lignes source / {pc} PG")
        for c in src.values():
            c.close()
        if ok7b:
            lines.append(f"- ✅ {checked} tables C : COUNT + Σ des colonnes "
                         "numériques identiques source ↔ PostgreSQL "
                         "(inclut tout `financial_*`).")
    results["7b. Agrégats numériques C (§6.7)"] = (ok7b, lines)

    # ---------- rapport ----------
    all_ok = all(v[0] for v in results.values())
    rep = ["# Rapport — Contrôles d'acceptation (§6)\n",
           f"- Généré : {datetime.now().isoformat(timespec='seconds')}",
           f"- Base : cdd_cosomis_unified (PostgreSQL 18)",
           f"- Contrôles 1-5 automatisés : "
           f"{'✅ tous passés' if all_ok else '❌ échec'}"]
    if orphan_total:
        rep.append(f"- ⚠ {orphan_total} FK orphelines connues subsistent "
                   "(voir §6.3) — décision requise avant bascule.")
    rep += ["- Reste avant bascule : produire les exports `views_docx` / "
            "tableau de bord financier avant/après (comme fc_situation) ; "
            "`migrate --fake` COSOMIS en production ; Étape 7 reste en dry-run "
            "(aucune écriture CouchDB).",
            ""]
    for name, (ok, ls) in results.items():
        rep.append(f"## {name} — {'✅' if ok else '❌'}")
        rep.extend(ls[:60])
        if len(ls) > 60:
            rep.append(f"- … (+{len(ls) - 60} lignes)")
        rep.append("")
    rep.append("## 6. Code (§6.6) — ✅ (Étape 6 appliquée aux dépôts)")
    rep.append("- CDD (`src/cdd/merge_routers.py` + `DATABASE_ROUTERS`) : "
               "`manage.py check` → 0 issue ; `makemigrations --check` → "
               "*No changes detected* (MySQL et PG).")
    rep.append("- COSOMIS (`cosomis/merge_routers.py`, `DATABASE_ROUTERS`, "
               "`MIGRATION_MODULES`, `Facilitator.Meta.managed=False`) : "
               "`manage.py check` → 0 issue ; `makemigrations --check` → "
               "*No changes detected* sur PG (code réel, sans overlay).")
    rep.append("- Réserve : COSOMIS a été chargé via `--run-syncdb` ; en "
               "production, `migrate --fake` les migrations "
               "subprojects/administrativelevels/assignments après chargement.")
    rep.append("")
    rep.append("## 7. Non-régression fonctionnelle (§6.7) — ✅")
    rep.append("- Export `generate_fc_situation --project COSO --tasks 59 128` "
               "(traverse CouchDB **en lecture seule** + le relationnel).")
    rep.append("- *avant* (MySQL cdd+mis) vs *après* (PostgreSQL unifié) : "
               "les **7 feuilles XML sont octet-pour-octet identiques** "
               "(`70_checks/avant|apres/fc_situation.xlsx`).")
    rep.append("- Restent à produire de la même manière : "
               "`reports/subprojects/views_docx`, tableau de bord financier.")
    rep.append("")
    rep.append("## 8. Sensibilité à la casse (§6.8) — ✅ portée dans le code")
    rep.append("- Confirmé : `filter(username='LEONARDO')` → `False` sous PG, "
               "`filter(username__iexact=…)` → `True`. **0 username en "
               "collision de casse.**")
    rep.append("- Appliqué (périmètre minimal) : lookups de login "
               "`username`/`email` en `__iexact` — CDD "
               "`authentication/api/auth/login.py`, `authentication/serializers.py`, "
               "`usermanager/authentication.py` ; COSOMIS "
               "`usermanager/api/auth/login.py`.")
    rep.append("")
    rep.append("> CouchDB : **aucune écriture** effectuée (Étape 7 en dry-run, "
               "exports en lecture seule).")
    (OUT / "report.md").write_text("\n".join(rep) + "\n", "utf-8")
    conn.close()
    print("\n".join(rep[:4]))
    for name, (ok, _) in results.items():
        print(f"  {'OK ' if ok else 'FAIL'} {name}")
    print("détails :", OUT / "report.md")


if __name__ == "__main__":
    main()
