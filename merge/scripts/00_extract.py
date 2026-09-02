"""
Étape 0 — Extraction des bases sources (lecture seule).

Source : bases **locales** (décision prise) —
    cdd : mysql://root:@127.0.0.1/cdd
    mis : mysql://root:@127.0.0.1/mis   (base COSOMIS)

Copies locales statiques → une passe unique suffit, le delta de
PLAN_ETAPE_0.md reste dormant. `cutpoint.json` est tout de même produit
(MAX(id) par table) comme point d'audit et pour l'idempotence.

Sorties sous `merge/artifacts/00_raw/<base>/` :
    _information_schema.json   tables, colonnes, FK réelles, index, charset/collation
    <table>.ddl.sql            SHOW CREATE TABLE
    <table>.csv               données, séparateur ',', NULL = \\N (convention mysqldump)
  + merge/artifacts/00_raw/cutpoint.json
  + merge/artifacts/00_raw/rapport_extraction.md

Lecture seule stricte : `SET SESSION TRANSACTION READ ONLY`, `REPEATABLE READ`,
aucun `FLUSH`, aucun `LOCK`. Le script n'émet que des `SELECT` / `SHOW`.

Usage :
    python merge/scripts/00_extract.py            # dry-run : métadonnées + comptages, aucune donnée écrite
    python merge/scripts/00_extract.py --apply    # extraction réelle
    python merge/scripts/00_extract.py --apply --only cdd
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import MySQLdb  # présent dans venv_cdd et venv_mis

REPO = Path(__file__).resolve().parents[2]
OUT_ROOT = REPO / "merge" / "artifacts" / "00_raw"

SOURCES = {
    "cdd": dict(host="127.0.0.1", user="root", passwd="", db="cdd"),
    "mis": dict(host="127.0.0.1", user="root", passwd="", db="mis"),
}

NULL_SENTINEL = r"\N"
PAGE = 5000


def connect(cfg: dict) -> "MySQLdb.Connection":
    conn = MySQLdb.connect(charset="utf8mb4", **cfg)
    cur = conn.cursor()
    cur.execute("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ")
    try:
        cur.execute("SET SESSION TRANSACTION READ ONLY")
    except MySQLdb.OperationalError:
        pass  # MariaDB <10.5 : ignore, le script reste en lecture seule de fait
    cur.close()
    return conn


def scalar(cur, sql, args=None):
    cur.execute(sql, args or ())
    row = cur.fetchone()
    return row[0] if row else None


def fmt(value) -> str:
    if value is None:
        return NULL_SENTINEL
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, timedelta):
        return str(value)
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", "replace")
    return str(value)


def information_schema(cur, db: str) -> dict:
    def rows(sql, args=()):
        cur.execute(sql, args)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    meta = {
        "database": db,
        "server_version": scalar(cur, "SELECT VERSION()"),
        "extracted_at": datetime.now().isoformat(timespec="seconds"),
        "charset_server": scalar(cur, "SELECT @@character_set_server"),
        "collation_server": scalar(cur, "SELECT @@collation_server"),
        "tables": rows(
            "SELECT table_name, engine, table_rows, table_collation, auto_increment "
            "FROM information_schema.tables WHERE table_schema=%s ORDER BY table_name",
            (db,),
        ),
        "columns": rows(
            "SELECT table_name, column_name, ordinal_position, column_type, data_type, "
            "is_nullable, column_default, column_key, extra, character_maximum_length, "
            "character_set_name, collation_name "
            "FROM information_schema.columns WHERE table_schema=%s "
            "ORDER BY table_name, ordinal_position",
            (db,),
        ),
        "foreign_keys": rows(
            "SELECT k.table_name, k.column_name, k.constraint_name, "
            "k.referenced_table_name, k.referenced_column_name, r.delete_rule, r.update_rule "
            "FROM information_schema.key_column_usage k "
            "JOIN information_schema.referential_constraints r "
            "  ON r.constraint_schema=k.table_schema AND r.constraint_name=k.constraint_name "
            "WHERE k.table_schema=%s AND k.referenced_table_name IS NOT NULL "
            "ORDER BY k.table_name, k.constraint_name, k.ordinal_position",
            (db,),
        ),
        "indexes": rows(
            "SELECT table_name, index_name, non_unique, seq_in_index, column_name "
            "FROM information_schema.statistics WHERE table_schema=%s "
            "ORDER BY table_name, index_name, seq_in_index",
            (db,),
        ),
    }
    return meta


def table_pk(meta: dict, table: str) -> list[str]:
    pk = [c["column_name"] for c in meta["columns"]
          if c["table_name"] == table and c["column_key"] == "PRI"]
    return pk


def has_id_col(meta: dict, table: str) -> bool:
    return any(c["table_name"] == table and c["column_name"] == "id"
              for c in meta["columns"])


def extract_source(name: str, apply: bool) -> dict:
    cfg = SOURCES[name]
    out_dir = OUT_ROOT / name
    conn = connect(cfg)
    cur = conn.cursor()
    print(f"[{name}] connecté à {cfg['host']}/{cfg['db']}", flush=True)

    meta = information_schema(cur, cfg["db"])
    tables = [t["table_name"] for t in meta["tables"]]
    summary = {"database": cfg["db"], "server_version": meta["server_version"],
               "n_tables": len(tables), "tables": {}}
    cutpoints = {}

    if apply:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "_information_schema.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=1, default=str),
            encoding="utf-8",
        )

    for table in tables:
        n = scalar(cur, f"SELECT COUNT(*) FROM `{table}`")
        pk = table_pk(meta, table)
        max_id = None
        if has_id_col(meta, table):
            max_id = scalar(cur, f"SELECT MAX(`id`) FROM `{table}`")
        cutpoints[table] = {"count": int(n), "max_id": max_id,
                            "pk": pk or None}
        summary["tables"][table] = {"count": int(n), "max_id": max_id}

        if not apply:
            continue

        # DDL
        cur.execute(f"SHOW CREATE TABLE `{table}`")
        ddl = cur.fetchone()[1]
        (out_dir / f"{table}.ddl.sql").write_text(ddl + ";\n", encoding="utf-8")

        # Données, pagination par PK entière si possible, sinon LIMIT/OFFSET
        cur.execute(f"SELECT * FROM `{table}` LIMIT 0")
        cols = [c[0] for c in cur.description]
        order = ", ".join(f"`{c}`" for c in (pk or cols))
        written = 0
        with (out_dir / f"{table}.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(cols)
            offset = 0
            while True:
                cur.execute(
                    f"SELECT * FROM `{table}` ORDER BY {order} "
                    f"LIMIT {PAGE} OFFSET {offset}"
                )
                batch = cur.fetchall()
                if not batch:
                    break
                for row in batch:
                    w.writerow([fmt(v) for v in row])
                written += len(batch)
                offset += PAGE
        status = "OK" if written == int(n) else f"ATTENTION {written}/{n}"
        print(f"[{name}] {table:<55} {written:>8} lignes  {status}", flush=True)
        summary["tables"][table]["written"] = written

    cur.close()
    conn.close()
    return summary, cutpoints


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="extraction réelle (par défaut : dry-run)")
    ap.add_argument("--only", choices=sorted(SOURCES), help="une seule base")
    args = ap.parse_args()

    names = [args.only] if args.only else list(SOURCES)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    all_summary, all_cut = {}, {}
    for name in names:
        s, c = extract_source(name, args.apply)
        all_summary[name] = s
        all_cut[name] = c

    if args.apply:
        (OUT_ROOT / "cutpoint.json").write_text(
            json.dumps({"generated_at": datetime.now().isoformat(timespec="seconds"),
                        "sources": all_cut}, ensure_ascii=False, indent=1, default=str),
            encoding="utf-8",
        )

    rep = ["# Rapport — Étape 0 : Extraction\n"]
    rep.append(f"- Mode : {'APPLY (données écrites)' if args.apply else 'DRY-RUN (métadonnées seules)'}")
    rep.append(f"- Généré : {datetime.now().isoformat(timespec='seconds')}")
    rep.append(f"- Convention CSV : séparateur `,`, fin de ligne `\\n`, NULL = `{NULL_SENTINEL}`, "
               "encodage UTF-8. L'Étape 5 (COPY) devra utiliser `NULL E'\\\\N'`.")
    rep.append("")
    for name, s in all_summary.items():
        total = sum(t["count"] for t in s["tables"].values())
        rep.append(f"## {name} — `{s['database']}` (MySQL/MariaDB {s['server_version']})")
        rep.append(f"- {s['n_tables']} tables, {total} lignes au total")
        mism = [t for t, v in s["tables"].items()
                if args.apply and v.get("written") != v["count"]]
        if mism:
            rep.append(f"- ⚠ écarts written/count : {', '.join(mism)}")
        rep.append("")
        rep.append("| table | lignes | max(id) |")
        rep.append("|---|---:|---:|")
        for t, v in sorted(s["tables"].items()):
            rep.append(f"| `{t}` | {v['count']} | {v['max_id'] if v['max_id'] is not None else ''} |")
        rep.append("")
    (OUT_ROOT / "rapport_extraction.md").write_text("\n".join(rep) + "\n", encoding="utf-8")

    print("\nRapport :", OUT_ROOT / "rapport_extraction.md")
    if not args.apply:
        print("Dry-run terminé. Relancer avec --apply pour extraire les données.")


if __name__ == "__main__":
    main()
