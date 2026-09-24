"""Exporte toute une base PostgreSQL (schéma `public`) dans un fichier .sql.

Équivalent texte de `export_postgres_db` : mêmes tables, mêmes contraintes,
mêmes données, mais dans un fichier SQL lisible (extension `.sql.gz` : compressé
en gzip). Sans pg_dump : uniquement psycopg2, donc utilisable en production.

Le fichier est un script SQL idempotent (une instruction par ligne) :
  CREATE … IF NOT EXISTS, INSERT … ON CONFLICT (clé primaire) DO UPDATE.
Il se réimporte avec `import_postgres_db_sql` (mise à jour par ID, option
--drop-all-tables) ; il est aussi conçu pour être exécutable avec `psql -f`.

L'export est lu dans une transaction REPEATABLE READ en lecture seule
(instantané cohérent, la base peut rester en service).

Exemple :
    python manage.py export_postgres_db_sql \
        --url postgres://postgres:root@127.0.0.1:5432/cdd_cosomis_unified \
        --output cdd_cosomis_unified.sql
"""
import gzip
import json
import os
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from ._pg_snapshot import (
    SCHEMA, SQL_MAGIC, TABLE_MARKER, NEXTVAL_RE, add_constraint_sql, connect,
    create_index_sql, create_table_sql, describe_database, mask_url, oneline,
    qi, qt, reset_sequence_sql, sql_literal,
)

BATCH_ROWS = 500
BATCH_CHARS = 1_000_000


class Command(BaseCommand):
    help = ("Exporte toute une base PostgreSQL (schéma + données) dans un "
            "fichier .sql, sans pg_dump.")

    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument(
            "--url", default=None,
            help="URL de la base à exporter (postgres://user:mdp@hote:5432/base). "
                 "Défaut : variable d'environnement DATABASE_URL.")
        parser.add_argument("--output", "-o", required=True,
                            help="Fichier .sql (ou .sql.gz) à créer.")
        parser.add_argument("--overwrite", action="store_true",
                            help="Écrase le fichier de sortie s'il existe.")

    def handle(self, *args, **options):
        url = options["url"] or os.environ.get("DATABASE_URL")
        if not url:
            raise CommandError("--url manquant (et DATABASE_URL non définie).")
        output = os.path.abspath(options["output"])
        if os.path.exists(output) and not options["overwrite"]:
            raise CommandError(f"{output} existe déjà (utiliser --overwrite).")
        os.makedirs(os.path.dirname(output), exist_ok=True)

        conn = connect(url)
        conn.set_session(isolation_level="REPEATABLE READ", readonly=True)
        part = output + ".part"
        try:
            with conn.cursor() as cur:
                # Représentation texte stable des valeurs, quelle que soit la
                # configuration du serveur source.
                for stmt in ("SET TIME ZONE 'UTC'", "SET DateStyle = 'ISO, YMD'",
                             "SET extra_float_digits = 3",
                             "SET bytea_output = 'hex'"):
                    cur.execute(stmt)
                cur.execute("SHOW server_version")
                server_version = cur.fetchone()[0]
                cur.execute("SELECT current_database()")
                dbname = cur.fetchone()[0]
                self.stdout.write(
                    f"Export de {mask_url(url)} (PostgreSQL {server_version})")
                opener = gzip.open if output.endswith(".gz") else open
                with opener(part, "wt", encoding="utf-8", newline="\n") as f:
                    tables = self._export(conn, cur, f, dbname, server_version)
            os.replace(part, output)
        except Exception:
            if os.path.exists(part):
                os.remove(part)
            raise
        finally:
            conn.close()

        rows = sum(rows for _, rows in tables)
        size = os.path.getsize(output) / (1024 * 1024)
        self.stdout.write(self.style.SUCCESS(
            f"{len(tables)} tables, {rows} lignes -> {output} ({size:.1f} Mo)"))

    # ------------------------------------------------------------------ #
    def _export(self, conn, cur, f, dbname, server_version):
        table_defs, sequences = describe_database(cur)

        def w(line=""):
            f.write(line + "\n")

        w(SQL_MAGIC)
        w(f"-- source : {oneline(dbname)} (PostgreSQL {server_version}), "
          f"schéma {SCHEMA}")
        w(f"-- généré : {datetime.now().isoformat(timespec='seconds')}")
        w("-- Une instruction par ligne ; les lignes « -- @table » sont des "
          "marqueurs de progression.")
        w("SET client_encoding = 'UTF8';")
        w("SET standard_conforming_strings = on;")
        w("SET TIME ZONE 'UTC';")
        w("SET DateStyle = 'ISO, YMD';")
        w("BEGIN;")
        w("SET CONSTRAINTS ALL DEFERRED;")

        w("-- séquences")
        for s in sequences:
            w(oneline(s["sql"]) + ";")

        w("-- tables, contraintes et données")
        owned = {(s["owned_by"][0], s["name"]): s["owned_by"][1]
                 for s in sequences if s["owned_by"]}
        seq_names = {s["name"] for s in sequences}
        summary = []
        for i, t in enumerate(table_defs):
            w(create_table_sql(t))
            for name in sorted(seq_names):           # OWNED BY des séquences serial
                col = owned.get((t["name"], name))
                if col:
                    w(f"ALTER SEQUENCE {qt(name)} OWNED BY "
                      f"{qt(t['name'])}.{qi(col)};")
            for c in t["constraints"]:
                if c["type"] in ("p", "u", "c", "x"):
                    w(add_constraint_sql(t["name"], c))
            rows = self._write_data(conn, cur, w, i, t)
            summary.append((t["name"], rows))
            self.stdout.write(f"  {t['name']}: {rows} lignes")

        # Les lignes mises à jour laissent des vérifications de FK différées en
        # attente ; PostgreSQL interdit alors tout CREATE INDEX / ALTER TABLE sur
        # ces tables dans la même transaction. Toutes les données sont chargées :
        # on peut valider les FK maintenant.
        w("SET CONSTRAINTS ALL IMMEDIATE;")
        w("-- index")
        for t in table_defs:
            for ix in t["indexes"]:
                w(create_index_sql(ix["def"]))

        w("-- clés étrangères")
        for t in table_defs:
            for c in t["constraints"]:
                if c["type"] == "f":
                    w(add_constraint_sql(t["name"], c))

        w("-- séquences : recalage sur le plus grand ID (sans jamais reculer)")
        for t in table_defs:
            for c in t["columns"]:
                if c["identity"] or NEXTVAL_RE.search(c["default"] or ""):
                    w(reset_sequence_sql(t["name"], c["name"]))
        w("COMMIT;")
        return summary

    def _write_data(self, conn, cur, w, index, t):
        name = t["name"]
        cur.execute(f"SELECT count(*) FROM {qt(name)}")
        total = cur.fetchone()[0]
        w(TABLE_MARKER + json.dumps({"name": name, "rows": total}))
        if not total:
            return 0

        cols = [c for c in t["columns"] if not c["generated"]]
        pk = t["pk"]
        names = ", ".join(qi(c["name"]) for c in cols)
        override = (" OVERRIDING SYSTEM VALUE"
                    if any(c["identity"] == "a" for c in cols) else "")
        head = f"INSERT INTO {qt(name)} ({names}){override} VALUES "
        if pk:
            conflict = ", ".join(qi(k) for k in pk)
            others = [c["name"] for c in cols if c["name"] not in pk]
            tail = (f" ON CONFLICT ({conflict}) DO UPDATE SET "
                    + ", ".join(f"{qi(c)} = EXCLUDED.{qi(c)}" for c in others)
                    if others else f" ON CONFLICT ({conflict}) DO NOTHING")
        else:
            tail = ""      # sans clé primaire : insertion simple (voir la docstring de l'import)
        tail += ";"
        select = ", ".join(f"{qi(c['name'])}::text" for c in cols)
        order = (" ORDER BY " + ", ".join(qi(k) for k in pk)) if pk else ""

        batch, size = [], 0
        with conn.cursor(name=f"snap_{index}") as ncur:
            ncur.itersize = 2000
            ncur.execute(f"SELECT {select} FROM {qt(name)}{order}")
            for row in ncur:
                lit = "(" + ",".join(sql_literal(v) for v in row) + ")"
                batch.append(lit)
                size += len(lit)
                if len(batch) >= BATCH_ROWS or size >= BATCH_CHARS:
                    w(head + ",".join(batch) + tail)
                    batch, size = [], 0
        if batch:
            w(head + ",".join(batch) + tail)
        return total
