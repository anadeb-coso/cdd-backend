"""Importe un fichier .sql produit par `export_postgres_db_sql`.

Équivalent texte de `import_postgres_db`. Le fichier est exécuté instruction par
instruction (une par ligne) dans UNE transaction : en cas d'erreur, la base est
laissée exactement comme avant, y compris avec --drop-all-tables.

- table absente de la base cible -> créée d'après le fichier, puis chargée ;
- table déjà présente            -> mise à jour PAR CLÉ PRIMAIRE (INSERT … ON
  CONFLICT DO UPDATE) : ligne existante mise à jour, ligne absente créée ; les
  lignes de la base absentes du fichier sont conservées ;
- contraintes / index / clés étrangères du fichier absents de la base : ajoutés
  (ceux qui existent déjà sont laissés tels quels) ;
- --drop-all-tables : supprime d'abord TOUTES les tables du schéma public
  (irréversible une fois la transaction validée), donc import sur base vide.

Les séquences sont recalées à la fin, sans jamais reculer.

Exemple :
    python manage.py import_postgres_db_sql \
        --url postgres://postgres:root@127.0.0.1:5432/cdd_cosomis_unified \
        --file cdd_cosomis_unified.sql [--drop-all-tables]

Limites : le fichier étant du SQL exécuté tel quel, une colonne du fichier
absente de la table cible fait ÉCHOUER (et annuler) l'import ; une table sans
clé primaire est simplement insérée (des doublons apparaissent si on la
réimporte) ; une contrainte UNIQUE violée par une ligne d'un autre ID annule
tout l'import. Prévoir une fenêtre de maintenance : l'application ne doit pas
écrire pendant l'import. Pour importer un fichier plus léger, .sql.gz est accepté.
"""
import gzip
import json
import os

import psycopg2
from django.core.management.base import BaseCommand, CommandError

from ._pg_snapshot import (
    SCHEMA, SQL_MAGIC, TABLE_MARKER, connect, mask_url, qt,
)


class Command(BaseCommand):
    help = ("Importe un export `export_postgres_db_sql` : crée les tables "
            "manquantes, met à jour/crée les lignes par ID.")

    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument(
            "--url", default=None,
            help="URL de la base cible (postgres://user:mdp@hote:5432/base). "
                 "Défaut : variable d'environnement DATABASE_URL.")
        parser.add_argument("--file", "-f", required=True,
                            help="Fichier .sql (ou .sql.gz) à importer.")
        parser.add_argument(
            "--drop-all-tables", action="store_true",
            help="Supprime TOUTES les tables du schéma public avant l'import.")
        parser.add_argument(
            "--noinput", "--no-input", action="store_true", dest="noinput",
            help="Ne demande pas de confirmation pour --drop-all-tables.")

    def handle(self, *args, **options):
        url = options["url"] or os.environ.get("DATABASE_URL")
        if not url:
            raise CommandError("--url manquant (et DATABASE_URL non définie).")
        path = os.path.abspath(options["file"])
        if not os.path.isfile(path):
            raise CommandError(f"{path} introuvable.")
        opener = gzip.open if path.endswith(".gz") else open

        with opener(path, "rt", encoding="utf-8", newline="\n") as fh:
            first = fh.readline().rstrip("\n")
        if first != SQL_MAGIC:
            raise CommandError("Ce fichier n'a pas été produit par "
                               "export_postgres_db_sql (en-tête absent).")

        conn = connect(url)
        dbname = conn.get_dsn_parameters().get("dbname")
        try:
            with conn.cursor() as cur:
                cur.execute("SHOW server_version")
                self.stdout.write(
                    f"Import de {os.path.basename(path)} vers {mask_url(url)} "
                    f"(PostgreSQL {cur.fetchone()[0]})")
                if options["drop_all_tables"]:
                    self._confirm_drop(cur, dbname, options["noinput"])
                    self._drop_all(cur)
                self._run(cur, opener, path)
            conn.commit()
        except psycopg2.Error as exc:
            conn.rollback()
            raise CommandError(
                f"Import annulé (base inchangée) : {str(exc).strip()}")
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    def _run(self, cur, opener, path):
        table, processed = None, 0
        statements = 0

        def flush():
            if table is not None:
                self.stdout.write(f"  {table['name']}: {processed} ligne(s) "
                                  f"créée(s) ou mise(s) à jour")

        with opener(path, "rt", encoding="utf-8", newline="\n") as fh:
            for lineno, line in enumerate(fh, start=1):
                line = line.rstrip("\n")
                if not line:
                    continue
                if line.startswith("--"):
                    if line.startswith(TABLE_MARKER):
                        flush()
                        table = json.loads(line[len(TABLE_MARKER):])
                        processed = 0
                    continue
                if line in ("BEGIN;", "COMMIT;"):
                    continue       # la transaction est gérée ici
                try:
                    cur.execute(line)
                except psycopg2.Error as exc:
                    where = f" (table {table['name']})" if table else ""
                    raise CommandError(
                        f"Import annulé (base inchangée) : ligne {lineno}"
                        f"{where} : {str(exc).strip()}")
                statements += 1
                if line.startswith("INSERT INTO"):
                    processed += cur.rowcount
        flush()
        self.stdout.write(self.style.SUCCESS(
            f"Terminé : {statements} instruction(s) exécutée(s)."))

    def _confirm_drop(self, cur, dbname, noinput):
        cur.execute("SELECT count(*) FROM pg_tables WHERE schemaname = %s",
                    (SCHEMA,))
        n = cur.fetchone()[0]
        self.stdout.write(self.style.WARNING(
            f"--drop-all-tables : les {n} tables de la base « {dbname} » "
            "seront SUPPRIMÉES avec leurs données."))
        if noinput:
            return
        answer = input(f"Tapez le nom de la base ({dbname}) pour confirmer : ")
        if answer.strip() != dbname:
            raise CommandError("Confirmation incorrecte : import annulé.")

    def _drop_all(self, cur):
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = %s",
                    (SCHEMA,))
        names = sorted(r[0] for r in cur.fetchall())
        if names:
            cur.execute("DROP TABLE IF EXISTS "
                        + ", ".join(qt(n) for n in names) + " CASCADE")
        cur.execute("SELECT sequencename FROM pg_sequences WHERE schemaname = %s",
                    (SCHEMA,))
        for (seq,) in cur.fetchall():
            cur.execute(f"DROP SEQUENCE IF EXISTS {qt(seq)} CASCADE")
        self.stdout.write(f"{len(names)} table(s) supprimée(s).")
