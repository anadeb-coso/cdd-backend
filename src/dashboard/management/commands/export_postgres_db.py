"""Exporte toute une base PostgreSQL (schéma `public`) dans un fichier .zip.

Sans pg_dump : uniquement psycopg2, donc utilisable en production. L'export est
lu dans une transaction REPEATABLE READ en lecture seule (instantané cohérent,
aucun verrou d'écriture, la base peut rester en service).

Exemple :
    python manage.py export_postgres_db \
        --url postgres://postgres:root@127.0.0.1:5432/cdd_cosomis_unified \
        --output cdd_cosomis_unified.zip

Le fichier se réimporte avec `import_postgres_db`. Variante en fichier texte
.sql : `export_postgres_db_sql` / `import_postgres_db_sql`.
"""
import json
import os
import zipfile
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from ._pg_snapshot import (
    COPY_OPTS, FORMAT_NAME, FORMAT_VERSION, MANIFEST_NAME, SCHEMA,
    connect, describe_database, mask_url, qi, qt,
)


class Command(BaseCommand):
    help = ("Exporte toute une base PostgreSQL (schéma + données) dans un "
            "fichier .zip, sans pg_dump.")

    # Aucune requête ORM : inutile de lancer les checks (et de dépendre de la
    # base configurée dans settings).
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument(
            "--url", default=None,
            help="URL de la base à exporter (postgres://user:mdp@hote:5432/base). "
                 "Défaut : variable d'environnement DATABASE_URL.")
        parser.add_argument("--output", "-o", required=True,
                            help="Fichier .zip à créer.")
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
                cur.execute("SHOW server_version")
                server_version = cur.fetchone()[0]
                cur.execute("SELECT current_database()")
                dbname = cur.fetchone()[0]
                self.stdout.write(
                    f"Export de {mask_url(url)} (PostgreSQL {server_version})")
                manifest = self._export(cur, part, dbname, server_version)
            os.replace(part, output)
        except Exception:
            if os.path.exists(part):
                os.remove(part)
            raise
        finally:
            conn.close()

        rows = sum(t["rows"] for t in manifest["tables"])
        size = os.path.getsize(output) / (1024 * 1024)
        self.stdout.write(self.style.SUCCESS(
            f"{len(manifest['tables'])} tables, {rows} lignes -> {output} "
            f"({size:.1f} Mo)"))

    def _export(self, cur, part, dbname, server_version):
        table_defs, sequences = describe_database(cur)
        manifest = {
            "format": FORMAT_NAME,
            "version": FORMAT_VERSION,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source": {"database": dbname, "server_version": server_version,
                       "schema": SCHEMA},
            "sequences": sequences,
            "tables": table_defs,
        }
        with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED,
                             allowZip64=True) as zf:
            for i, t in enumerate(table_defs, start=1):
                t["file"] = f"data/{i:04d}.csv"
                cols = ", ".join(qi(c["name"]) for c in t["columns"]
                                 if not c["generated"])
                sql = f"COPY {qt(t['name'])} ({cols}) TO STDOUT {COPY_OPTS}"
                with zf.open(t["file"], "w", force_zip64=True) as w:
                    cur.copy_expert(sql, w)
                t["rows"] = cur.rowcount
                self.stdout.write(f"  {t['name']}: {t['rows']} lignes")
            zf.writestr(MANIFEST_NAME,
                        json.dumps(manifest, ensure_ascii=False, indent=1))
        return manifest
