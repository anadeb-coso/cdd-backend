"""
Étape 5 — Chargement PostgreSQL.

1. (Re)crée la base cible PostgreSQL.
2. `manage.py migrate` — CDD (venv_cdd) puis COSOMIS (venv_mis) via un overlay
   de settings qui pointe `default` (+ alias croisé) sur la base PG et injecte
   les routeurs de l'Étape 6. Les dépôts ne sont pas modifiés.
3. `COPY` des CSV de `merge/artifacts/40_unified/` — colonne `id` explicite
   (§5 : les ID sont transportés, pas régénérés), FK différées le temps du
   chargement, session en UTC (datetime naïfs), dates `0000-00-00` -> NULL.
4. Recalage des séquences : `setval(pg_get_serial_sequence(t,'id'), MAX(id))`.

Sorties : merge/artifacts/50_postgres/{overlay/,rapport_postgres.md}

Cible : postgres://postgres:root@127.0.0.1/cdd_cosomis_unified  (PG 18)

Usage :
    python merge/scripts/05_load_postgres.py --step provision,migrate,load,seq
    python merge/scripts/05_load_postgres.py            # tout
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import psycopg2

REPO = Path(__file__).resolve().parents[2]
UNI = REPO / "merge" / "artifacts" / "40_unified"
CODE = REPO / "merge" / "artifacts" / "60_code"
OUT = REPO / "merge" / "artifacts" / "50_postgres"
OVERLAY = OUT / "overlay"

csv.field_size_limit(1 << 24)
NULL = r"\N"

PG = dict(host="127.0.0.1", user="postgres", password="root")
TARGET_DB = "cdd_cosomis_unified"
PG_URL = f"postgres://postgres:root@127.0.0.1/{TARGET_DB}"

CDD_ROOT = REPO / "src"
COSOMIS_ROOT = Path(r"D:\COSO\PROJECTS\MIS\cosomis\cosomis")
CDD_PY = Path(r"D:\COSO\PROJECTS\CDD\backend\venv_cdd\Scripts\python.exe")
COSOMIS_PY = Path(r"D:\COSO\PROJECTS\MIS\venv_mis\Scripts\python.exe")

BASE_ENV = {
    "SECRET_KEY": "merge-etape5",
    "DATABASE_URL": PG_URL,
    "LEGACY_DATABASE_URL": PG_URL,
    "LEGACY_GRM_DATABASE_URL": "sqlite:////tmp/grm-none.db",
    "GRM_DATABASE_URL": "sqlite:////tmp/grm-none.db",
    "DEBUG": "False",
    "ALLOWED_HOSTS": "*",
}


def provision():
    conn = psycopg2.connect(dbname="postgres", **PG)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (TARGET_DB,))
    cur.execute(f'DROP DATABASE IF EXISTS "{TARGET_DB}"')
    cur.execute(f'CREATE DATABASE "{TARGET_DB}" ENCODING \'UTF8\' '
                f'TEMPLATE template0')
    conn.close()
    print(f"[provision] base {TARGET_DB} recréée")


def write_overlay():
    OVERLAY.mkdir(parents=True, exist_ok=True)
    (OVERLAY / "__init__.py").write_text("", "utf-8")
    for name in ("cdd_merge_router.py", "cosomis_merge_router.py"):
        (OVERLAY / name).write_text(
            (CODE / "routers" / name).read_text("utf-8"), "utf-8")
    # routeur spécifique au chargement : COSOMIS crée le schéma de ses apps
    # possédées + les tables mis_only des apps homonymes (periodwave*, usertoken)
    (OVERLAY / "syncdb_router.py").write_text(
        "_ALLOW = {'subprojects', 'administrativelevels', 'assignments',\n"
        "          'financial', 'custom_file', 'kobotoolbox', 'unicorn',\n"
        "          'process_manager', 'usermanager'}\n"
        "class SyncdbRouter:\n"
        "    def db_for_read(self, m, **h): return None\n"
        "    def db_for_write(self, m, **h): return None\n"
        "    def allow_relation(self, a, b, **h): return True\n"
        "    def allow_migrate(self, db, app_label, model_name=None, **h):\n"
        "        return db == 'default' and app_label in _ALLOW\n",
        "utf-8")
    (OVERLAY / "cdd_pg_settings.py").write_text(
        "import os\n"
        "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cdd.settings')\n"
        "from cdd.settings import *  # noqa\n"
        f"_PG = {{'ENGINE': 'django.db.backends.postgresql', 'NAME': '{TARGET_DB}',"
        " 'USER': 'postgres', 'PASSWORD': 'root', 'HOST': '127.0.0.1', 'PORT': '5432'}\n"
        "DATABASES = {'default': dict(_PG), 'mis': dict(_PG), 'grm': dict(_PG)}\n"
        "DATABASE_ROUTERS = ['cdd_merge_router.CddMergeRouter']\n",
        "utf-8")
    # COSOMIS ne migre QUE ses apps propriétaires + ses apps propres. Toutes les
    # autres sont neutralisées (MIGRATION_MODULES=None) pour que leur historique
    # de migrations (divergent de celui de CDD, déjà appliqué) n'entre pas dans
    # le graphe et ne casse pas check_consistent_history.
    (OVERLAY / "cosomis_pg_settings.py").write_text(
        "import os\n"
        "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cosomis.settings')\n"
        "from cosomis.settings import *  # noqa\n"
        f"_PG = {{'ENGINE': 'django.db.backends.postgresql', 'NAME': '{TARGET_DB}',"
        " 'USER': 'postgres', 'PASSWORD': 'root', 'HOST': '127.0.0.1', 'PORT': '5432'}\n"
        "DATABASES = {'default': dict(_PG), 'cdd': dict(_PG)}\n"
        "DATABASE_ROUTERS = ['syncdb_router.SyncdbRouter']\n"
        "# Toutes les apps sont neutralisées : le schéma des apps possédées par\n"
        "# COSOMIS est créé par `migrate --run-syncdb` à partir de l'état ACTUEL\n"
        "# des modèles (évite de rejouer 50+ AlterField incompatibles PG). Le\n"
        "# routeur limite la création aux 7 apps COSOMIS ; les tables déjà\n"
        "# présentes (auth, contenttypes… créées par CDD) sont ignorées.\n"
        "_labels = {a.split('.')[-1] for a in INSTALLED_APPS}\n"
        "_labels |= {'admin', 'auth', 'contenttypes', 'sessions', 'messages',\n"
        "            'staticfiles', 'authtoken', 'django_celery_results',\n"
        "            'process_manager', 'authentication', 'usermanager',\n"
        "            'reports', 'attachments', 'dashboard', 'subprojects',\n"
        "            'administrativelevels', 'assignments', 'financial',\n"
        "            'custom_file', 'kobotoolbox'}\n"
        "MIGRATION_MODULES = {l: None for l in _labels}\n",
        "utf-8")


def run_migrate(label, py, root, settings_mod, log):
    env = dict(os.environ)
    env.update(BASE_ENV)
    env["PYTHONPATH"] = os.pathsep.join([str(OVERLAY), str(root)])
    env["DJANGO_SETTINGS_MODULE"] = settings_mod
    # --skip-checks : COSOMIS exécute des requêtes DB à l'import de l'URLconf
    # (subprojects/vars.py) — le framework de checks planterait avant migration.
    cmd = [str(py), "manage.py", "migrate", "--noinput", "--skip-checks", "-v", "1"]
    if label == "cosomis":
        # schéma des 7 apps COSOMIS créé depuis l'état actuel des modèles
        cmd.append("--run-syncdb")
    print(f"[migrate:{label}] {' '.join(cmd[3:])}  (cwd={root})")
    res = subprocess.run(cmd, cwd=root, env=env, capture_output=True,
                         text=True, encoding="utf-8")
    log.append(f"\n===== migrate {label} (rc={res.returncode}) =====\n"
               + res.stdout[-9000:] + "\n--- stderr ---\n" + res.stderr[-5000:])
    print(f"[migrate:{label}] rc={res.returncode}")
    return res.returncode == 0


def pg_columns(cur, table):
    cur.execute("SELECT column_name, data_type, is_nullable FROM "
                "information_schema.columns WHERE table_name=%s AND "
                "table_schema='public' ORDER BY ordinal_position", (table,))
    return {r[0]: (r[1], r[2]) for r in cur.fetchall()}


ZERO_DATES = {"0000-00-00", "0000-00-00 00:00:00", "0000-00-00 00:00:00.000000"}


def transform(value, pgtype):
    if value == NULL:
        return NULL
    if pgtype in ("date", "timestamp without time zone",
                  "timestamp with time zone", "time without time zone"):
        if value in ZERO_DATES or value.startswith("0000-00-00"):
            return NULL
    if pgtype in ("json", "jsonb"):
        if value in ("", "\\N"):
            return NULL
        try:
            json.loads(value)
        except ValueError:
            return None  # sentinelle -> ligne rejetée / signalée
    return value


def load(cur, log):
    order_file = UNI / "schema_unifie.json"
    schema = json.loads(order_file.read_text("utf-8"))
    cur.execute("SET session_replication_role = replica")   # FK/triggers off
    cur.execute("SET TIME ZONE 'UTC'")
    cur.execute("SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public'")
    pg_tables = {r[0].casefold(): r[0] for r in cur.fetchall()}

    def resolve_pg(table):
        k = table.casefold()
        if k in pg_tables:
            return pg_tables[k]
        if len(table) >= 60:
            for kk, vv in pg_tables.items():
                if kk[:40] == k[:40]:
                    return vv
        return None

    ok, fail = {}, {}
    for csv_name, header in schema.items():
        table = resolve_pg(csv_name)
        if table is None:
            fail[csv_name] = "table absente en PG (migration non appliquée)"
            continue
        pgcols = pg_columns(cur, table)
        if not pgcols:
            fail[csv_name] = "table absente en PG (migration non appliquée)"
            continue
        common = [c for c in header if c in pgcols]
        if "id" in header and "id" not in common:
            fail[csv_name] = "colonne id absente en PG"
            continue
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        src = UNI / f"{csv_name}.csv"
        bad = 0
        with src.open(encoding="utf-8", newline="") as fh:
            r = csv.reader(fh)
            head = next(r)
            hi = {c: i for i, c in enumerate(head)}
            for row in r:
                out = []
                for c in common:
                    v = transform(row[hi[c]], pgcols[c][0])
                    if v is None:
                        bad += 1
                        v = NULL
                    out.append(v)
                w.writerow(out)
        buf.seek(0)
        collist = ", ".join(f'"{c}"' for c in common)
        try:
            cur.execute("SAVEPOINT s")
            cur.copy_expert(
                f'COPY "{table}" ({collist}) FROM STDIN WITH '
                f"(FORMAT csv, NULL '\\N')", buf)
            cur.execute("RELEASE SAVEPOINT s")
            cur.execute(f'SELECT count(*) FROM "{table}"')
            ok[table] = {"rows": cur.fetchone()[0], "cols": len(common),
                         "json_invalides": bad}
        except Exception as e:  # noqa
            cur.execute("ROLLBACK TO SAVEPOINT s")
            fail[table] = str(e).strip().splitlines()[0][:200]
    cur.execute("SET session_replication_role = DEFAULT")
    log.append(f"\n===== COPY : {len(ok)} OK / {len(fail)} en échec =====")
    return ok, fail


def reseq(cur, ok):
    fixed = 0
    for table in ok:
        try:
            cur.execute("SAVEPOINT sq")
            cur.execute("SELECT pg_get_serial_sequence(%s, 'id')", (table,))
            seq = cur.fetchone()[0]
            if seq:
                cur.execute(
                    f'SELECT setval(%s, COALESCE((SELECT MAX(id) FROM "{table}"), 1))',
                    (seq,))
                fixed += 1
            cur.execute("RELEASE SAVEPOINT sq")
        except Exception:
            cur.execute("ROLLBACK TO SAVEPOINT sq")   # pas de colonne id
    return fixed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", default="provision,migrate,load,seq")
    args = ap.parse_args()
    steps = set(args.step.split(","))
    OUT.mkdir(parents=True, exist_ok=True)
    log: list[str] = [f"# Étape 5 — {datetime.now().isoformat(timespec='seconds')}"]

    if "provision" in steps:
        provision()
    write_overlay()

    mig_ok = {"cdd": None, "cosomis": None}
    if "migrate" in steps:
        mig_ok["cdd"] = run_migrate("cdd", CDD_PY, CDD_ROOT,
                                    "cdd_pg_settings", log)
        mig_ok["cosomis"] = run_migrate("cosomis", COSOMIS_PY, COSOMIS_ROOT,
                                        "cosomis_pg_settings", log)

    ok, fail = {}, {}
    seq_fixed = 0
    if "load" in steps or "seq" in steps:
        conn = psycopg2.connect(dbname=TARGET_DB, **PG)
        conn.autocommit = False
        cur = conn.cursor()
        if "load" in steps:
            ok, fail = load(cur, log)
            conn.commit()
        if "seq" in steps:
            seq_fixed = reseq(cur, ok or {})
            conn.commit()
        conn.close()

    (OUT / "migrate.log").write_text("\n".join(log), "utf-8")

    rep = ["# Rapport — Étape 5 : Chargement PostgreSQL\n",
           f"- Base : `{TARGET_DB}` (PostgreSQL 18)",
           f"- Généré : {datetime.now().isoformat(timespec='seconds')}",
           f"- migrate CDD : {mig_ok['cdd']} ; migrate COSOMIS : {mig_ok['cosomis']}",
           f"- COPY : **{len(ok)} tables OK**, {len(fail)} en échec",
           f"- Séquences recalées : {seq_fixed}",
           ""]
    if ok:
        tot = sum(v["rows"] for v in ok.values())
        rep.append(f"## Chargées ({len(ok)} tables, {tot} lignes)")
        badj = {t: v for t, v in ok.items() if v["json_invalides"]}
        if badj:
            rep.append("- JSON invalides mis à NULL : "
                       + ", ".join(f"{t}({v['json_invalides']})"
                                   for t, v in badj.items()))
    if fail:
        rep.append(f"\n## Échecs COPY ({len(fail)})")
        for t, why in sorted(fail.items()):
            rep.append(f"- `{t}` : {why}")
    rep.append("\n## Suite")
    rep.append("Étape 7 (`07_remap_couchdb.py`, dry-run) puis contrôles "
               "d'acceptation (`merge/scripts/checks/`).")
    (OUT / "rapport_postgres.md").write_text("\n".join(rep) + "\n", "utf-8")
    print("\n".join(rep[:6]))
    print("détails :", OUT / "rapport_postgres.md")


if __name__ == "__main__":
    main()
