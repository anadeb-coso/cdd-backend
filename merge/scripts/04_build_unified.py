"""
Étape 4 — Jeu de données unifié.

Applique `merge/fusion_plan.yml` + `merge/id_map.csv` aux CSV de l'Étape 0.

Sorties dans `merge/artifacts/40_unified/` :
  - <table>.csv                 jeu unifié normalisé, une table par fichier
                                (séparateur ',', NULL = \\N, en-tête)
  - dump_mysql_unifie.sql       dump MySQL unique (DDL + INSERT), archive —
                                jamais chargé dans un serveur MySQL
  - schema_unifie.json          colonnes finales par table
  - rapport_unifie.md

Règles appliquées :
  - rebuild (§4.6)         : table ignorée (Django la régénère)
  - cdd_only / mis_only    : copie telle quelle de la source
  - mirror (B)             : copie telle quelle depuis le propriétaire, ID inchangés
  - merge (A)              : lignes CDD + lignes COSOMIS (matched → fusionnées
                            dans la ligne CDD, null-fill ; new_allocation →
                            ajoutées avec new_id) ; colonnes = union
  - remap : toute colonne FK (réelle) pointant une table A, sur des lignes
    d'origine COSOMIS, est réécrite via id_map ; les snapshots JSON
    create_by_user / update_by_user voient leur clé "id" réécrite (id_map auth_user)

Ordre d'écriture : tri topologique du graphe de FK ; cycle → tables concernées
en fin de fichier SQL sous SET FOREIGN_KEY_CHECKS=0, et signalé.

Idempotent, lecture seule des entrées. Usage :
    python merge/scripts/04_build_unified.py
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
RAW = REPO / "merge" / "artifacts" / "00_raw"
OUT = REPO / "merge" / "artifacts" / "40_unified"
PLAN = REPO / "merge" / "fusion_plan.yml"
ID_MAP = REPO / "merge" / "id_map.csv"

csv.field_size_limit(1 << 24)
NULL = r"\N"


def read_is(db):
    return json.loads((RAW / db / "_information_schema.json").read_text("utf-8"))


_CSV_INDEX: dict[str, dict[str, str]] = {}


def _csv_index(db):
    if db not in _CSV_INDEX:
        _CSV_INDEX[db] = {p.stem.casefold(): p.stem
                          for p in (RAW / db).glob("*.csv")}
    return _CSV_INDEX[db]


def resolve_csv(db, table):
    """Nom de fichier CSV réel : le code peut utiliser un db_table tronqué par
    Django (>64 c.) ou de casse différente de la table physique."""
    idx = _csv_index(db)
    key = table.casefold()
    if key in idx:
        return idx[key]
    if len(table) >= 60:
        for k, v in idx.items():
            if k[:56] == key[:56]:
                return v
    return None


def read_rows(db, table):
    real = resolve_csv(db, table)
    if real is None:
        raise FileNotFoundError(f"{db}/{table}.csv")
    p = RAW / db / f"{real}.csv"
    with p.open(encoding="utf-8", newline="") as fh:
        r = csv.reader(fh)
        header = next(r)
        return header, [row for row in r]


def load_id_map():
    """{table: {old_id(str): new_id(str)}} ; ignore reason=conflict/vide."""
    m = defaultdict(dict)
    with ID_MAP.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row["reason"] in ("matched", "new_allocation") and row["new_id"]:
                m[row["table"]][row["old_id"]] = row["new_id"]
    return m


def remap_user_snapshot(raw: str, umap: dict) -> str:
    if raw in (NULL, "", "[]", "{}"):
        return raw
    try:
        obj = json.loads(raw)
    except (ValueError, TypeError):
        return raw
    def walk(o):
        if isinstance(o, dict):
            if "id" in o and isinstance(o["id"], (int, str)) and \
                    str(o["id"]) in umap:
                o["id"] = int(umap[str(o["id"])]) if str(o["id"]).isdigit() \
                    else umap[str(o["id"])]
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(obj)
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    plan = yaml.safe_load(PLAN.read_text("utf-8"))
    tables = plan["tables"]
    idmap = load_id_map()

    is_cdd, is_mis = read_is("cdd"), read_is("mis")
    A_TABLES = {t for t, e in tables.items() if e.get("strategy") == "merge"}

    # colonnes physiques par (db, table)
    def cols(meta, table):
        return [c["column_name"] for c in meta["columns"]
                if c["table_name"] == table]

    # FK réelles : (db, table, column) -> referenced_table
    fk = {}
    for db, meta in (("cdd", is_cdd), ("mis", is_mis)):
        for f in meta["foreign_keys"]:
            fk[(db, f["table_name"], f["column_name"])] = f["referenced_table_name"]

    # snapshots user à remapper (fusion_plan.soft_remap, structure user_snapshot)
    snap_cols = defaultdict(set)   # table -> {column}
    for s in plan.get("soft_remap", []):
        if s.get("structure") == "user_snapshot":
            snap_cols[s["table"]].add(s["column"])
    umap = idmap.get("auth_user", {})

    # concepts inter-tables (Project…) : (table, column) -> table CDD survivante
    cross_remap = {}
    for c in (plan.get("cross_concept") or {}).values():
        for rc in c.get("remap_columns", []):
            cross_remap[(rc["table"], rc["column"])] = c["cdd_table"]

    unified_schema: dict[str, list[str]] = {}
    row_counts: dict[str, dict] = {}
    written_tables: list[str] = []
    notes: list[str] = []

    def out_csv(table, header, rows):
        with (OUT / f"{table}.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(header)
            w.writerows(rows)
        unified_schema[table] = header
        written_tables.append(table)

    def remap_row(origin_db, table, header, row, is_A_self):
        """Réécrit une ligne d'origine COSOMIS."""
        row = list(row)
        h = {c: i for i, c in enumerate(header)}
        if is_A_self and "id" in h:
            old = row[h["id"]]
            row[h["id"]] = idmap.get(table, {}).get(old, old)
        for c, i in h.items():
            ref = fk.get(("mis", table, c))
            if ref in A_TABLES and row[i] not in (NULL, ""):
                row[i] = idmap.get(ref, {}).get(row[i], row[i])
            cx = cross_remap.get((table, c))
            if cx and row[i] not in (NULL, ""):
                row[i] = idmap.get(cx, {}).get(row[i], row[i])
            if c in snap_cols.get(table, ()):
                row[i] = remap_user_snapshot(row[i], umap)
        return row

    for table, e in tables.items():
        strat = e.get("strategy")

        if strat in (None, "rebuild", "skip", "TODO"):
            row_counts[table] = {"strategy": strat, "written": 0}
            continue

        if strat in ("cdd_only", "mirror") and e.get("data_source") == "cdd" \
                or strat == "cdd_only":
            header, rows = read_rows("cdd", table)
            out_csv(table, header, rows)
            row_counts[table] = {"strategy": strat, "source": "cdd",
                                 "written": len(rows)}
            continue

        if strat == "mis_only" or (strat == "mirror"
                                   and e.get("data_source") == "cosomis"):
            header, rows = read_rows("mis", table)
            # remap FK -> tables A + snapshots, sur ces lignes d'origine mis
            need = any(fk.get(("mis", table, c)) in A_TABLES for c in header) \
                or table in snap_cols \
                or any((table, c) in cross_remap for c in header)
            if need:
                rows = [remap_row("mis", table, header, r, is_A_self=False)
                        for r in rows]
            out_csv(table, header, rows)
            row_counts[table] = {"strategy": strat, "source": "cosomis",
                                 "written": len(rows), "remapped": need}
            continue

        if strat == "merge":
            c_header, c_rows = read_rows("cdd", table)
            m_header, m_rows = read_rows("mis", table)
            added = [f["name"] for f in e.get("fields_added_from_cosomis", [])]
            header = c_header + [a for a in added if a not in c_header]
            ci = {c: i for i, c in enumerate(c_header)}
            mi = {c: i for i, c in enumerate(m_header)}
            hi = {c: i for i, c in enumerate(header)}

            tmap = idmap.get(table, {})
            # index des lignes CDD par id, complété au format header
            unified: dict[str, list[str]] = {}
            order: list[str] = []
            for r in c_rows:
                full = [NULL] * len(header)
                for c in c_header:
                    full[hi[c]] = r[ci[c]]
                unified[r[ci["id"]]] = full
                order.append(r[ci["id"]])

            merged = new = 0
            for r in m_rows:
                old = r[mi["id"]]
                new_id = tmap.get(old)
                if new_id is None:
                    continue  # ligne mis abandonnée (doublon liaison, etc.)
                rr = remap_row("mis", table, m_header, r, is_A_self=True)
                mrow = {c: rr[mi[c]] for c in m_header}
                if new_id in unified:
                    # matched : null-fill depuis COSOMIS (CDD gagne sinon)
                    tgt = unified[new_id]
                    for c in header:
                        if c in mrow and tgt[hi[c]] in (NULL, "") \
                                and mrow[c] not in (NULL, ""):
                            tgt[hi[c]] = mrow[c]
                    merged += 1
                else:
                    full = [NULL] * len(header)
                    for c in header:
                        if c in mrow:
                            full[hi[c]] = mrow[c]
                    full[hi["id"]] = new_id
                    unified[new_id] = full
                    order.append(new_id)
                    new += 1
            out_csv(table, header, [unified[k] for k in order])
            row_counts[table] = {"strategy": "merge", "cdd": len(c_rows),
                                 "mis_merged": merged, "mis_new": new,
                                 "written": len(order)}
            continue

        row_counts[table] = {"strategy": strat, "written": 0}

    # ---------- tri topologique pour le dump SQL ----------
    uset = set(written_tables)
    graph = defaultdict(set)   # table -> tables dont elle dépend
    for (db, t, c), ref in fk.items():
        if t in uset and ref in uset and ref != t:
            graph[t].add(ref)

    # casser les vrais cycles (DFS) en retirant l'arête retour ; ne signaler
    # que les tables réellement dans un cycle, pas tout leur aval.
    color = defaultdict(int)   # 0 blanc, 1 gris, 2 noir
    cycle_members: set[str] = set()
    broken_edges: list[tuple] = []

    def dfs(n, stack):
        color[n] = 1
        stack.append(n)
        for m in sorted(graph[n]):
            if color[m] == 1:
                cycle_members.update(stack[stack.index(m):])
                cycle_members.add(m)
                broken_edges.append((n, m))
            elif color[m] == 0:
                dfs(m, stack)
        stack.pop()
        color[n] = 2

    for n in sorted(uset):
        if color[n] == 0:
            dfs(n, [])
    for a, b in broken_edges:
        graph[a].discard(b)

    indeg = {t: len(graph.get(t, ())) for t in uset}
    radj = defaultdict(set)
    for t, deps in graph.items():
        for d in deps:
            radj[d].add(t)
    q = deque(sorted(t for t in uset if indeg[t] == 0))
    topo = []
    while q:
        n = q.popleft()
        topo.append(n)
        for m in sorted(radj.get(n, ())):
            indeg[m] -= 1
            if indeg[m] == 0:
                q.append(m)
    leftover = sorted(uset - set(topo))          # ne devrait plus arriver
    ordered = topo + leftover
    cyclic = sorted(cycle_members)
    if cyclic:
        notes.append(
            f"{len(cyclic)} table(s) dans un cycle de FK ({', '.join(cyclic)}) "
            f"— arêtes retour cassées pour l'ordre ({broken_edges}). Le dump "
            "SQL est encadré par SET FOREIGN_KEY_CHECKS=0 ; l'Étape 5 charge "
            "avec contraintes différées.")

    # ---------- dump_mysql_unifie.sql (archive) ----------
    def sql_val(v):
        if v == NULL:
            return "NULL"
        return "'" + v.replace("\\", "\\\\").replace("'", "\\'") \
                       .replace("\n", "\\n").replace("\r", "\\r") + "'"

    dump = OUT / "dump_mysql_unifie.sql"
    with dump.open("w", encoding="utf-8") as fh:
        fh.write("-- Dump MySQL unifié cdd + cosomis — ARCHIVE, ne jamais "
                 "charger dans un serveur MySQL (CLAUDE.md §2).\n")
        fh.write(f"-- Généré : {datetime.now().isoformat(timespec='seconds')}\n")
        fh.write("SET NAMES utf8mb4;\nSET FOREIGN_KEY_CHECKS=0;\n\n")
        for table in ordered:
            header = unified_schema[table]
            real_cdd = resolve_csv("cdd", table)
            owner = "cdd" if real_cdd else "mis"
            real = real_cdd or resolve_csv("mis", table) or table
            ddl = (RAW / owner / f"{real}.ddl.sql")
            fh.write(f"\n-- ---- {table} (schéma : {owner}) ----\n")
            fh.write(f"DROP TABLE IF EXISTS `{table}`;\n")
            if ddl.exists():
                fh.write(ddl.read_text("utf-8").rstrip() + "\n")
            e = tables.get(table, {})
            for f in e.get("fields_added_from_cosomis", []):
                fh.write(f"ALTER TABLE `{table}` ADD COLUMN `{f['name']}` "
                         f"{f['type']} NULL;\n")
            with (OUT / f"{table}.csv").open(encoding="utf-8", newline="") as cf:
                rr = csv.reader(cf)
                next(rr)
                batch = []
                collist = "(" + ",".join(f"`{c}`" for c in header) + ")"
                for row in rr:
                    batch.append("(" + ",".join(sql_val(v) for v in row) + ")")
                    if len(batch) >= 500:
                        fh.write(f"INSERT INTO `{table}` {collist} VALUES\n"
                                 + ",\n".join(batch) + ";\n")
                        batch = []
                if batch:
                    fh.write(f"INSERT INTO `{table}` {collist} VALUES\n"
                             + ",\n".join(batch) + ";\n")
        fh.write("\nSET FOREIGN_KEY_CHECKS=1;\n")

    (OUT / "schema_unifie.json").write_text(
        json.dumps(unified_schema, ensure_ascii=False, indent=1), "utf-8")

    # ---------- rapport ----------
    rep = ["# Rapport — Étape 4 : Jeu de données unifié\n"]
    rep.append(f"- Généré : {datetime.now().isoformat(timespec='seconds')}")
    rep.append(f"- Tables écrites : {len(written_tables)} "
               f"(`merge/artifacts/40_unified/`)")
    rep.append(f"- Dump archive : `dump_mysql_unifie.sql` "
               f"({dump.stat().st_size // 1024} Kio)")
    if notes:
        for n in notes:
            rep.append(f"- ⚠ {n}")
    rep.append("")
    rep.append("## Catégorie A")
    for t in sorted(A_TABLES):
        s = row_counts.get(t, {})
        if s.get("strategy") != "merge":
            rep.append(f"- `{t}` : {s}")
            continue
        rep.append(f"- `{t}` : CDD {s['cdd']} + COSOMIS fusionnées "
                   f"{s['mis_merged']} + nouvelles {s['mis_new']} "
                   f"→ **{s['written']}**")
    rep.append("")
    rep.append("## Contrôle de comptage (§6.1)")
    for t in sorted(A_TABLES):
        s = row_counts.get(t, {})
        if s.get("strategy") == "merge":
            exp = s["cdd"] + (s["mis_merged"] + s["mis_new"]) - s["mis_merged"]
            ok = "OK" if exp == s["written"] else "ÉCART"
            rep.append(f"- `{t}` : cdd+mis-appariées = {exp} ; unifiée = "
                       f"{s['written']} → {ok}")
    rep.append("")
    rep.append("## Suite")
    rep.append("Étape 5 : `merge/scripts/05_load_postgres.py` (charge les CSV "
               "de `40_unified/` dans PostgreSQL via COPY, colonne `id` explicite).")
    (OUT / "rapport_unifie.md").write_text("\n".join(rep) + "\n", "utf-8")

    print("Tables unifiées :", len(written_tables))
    for t in sorted(A_TABLES):
        print("  ", t, row_counts.get(t))
    if notes:
        print("NOTES:", *notes, sep="\n  ")


if __name__ == "__main__":
    main()
