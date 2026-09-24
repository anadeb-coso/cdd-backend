"""Importe un fichier produit par `export_postgres_db` dans une base PostgreSQL.

Comportement (tout se passe dans UNE transaction : en cas d'erreur, la base
est laissée exactement comme avant, y compris avec --drop-all-tables) :

- table absente de la base cible -> créée d'après le fichier, puis chargée ;
- table déjà présente            -> mise à jour PAR CLÉ PRIMAIRE : la ligne
  existante est mise à jour, la ligne absente est créée. Les lignes de la
  base qui ne sont pas dans le fichier sont conservées ;
- --drop-all-tables : supprime d'abord TOUTES les tables du schéma public
  (irréversible une fois la transaction validée), donc import sur base vide.

Les séquences sont recalées à la fin (jamais en arrière), pour que la prochaine
création d'objet ne viole pas une clé primaire.

Exemple :
    python manage.py import_postgres_db \
        --url postgres://postgres:root@127.0.0.1:5432/cdd_cosomis_unified \
        --file cdd_cosomis_unified.zip [--drop-all-tables]

Limites : une colonne présente dans le fichier mais absente de la table cible
est ignorée (avertissement) ; une table existante sans clé primaire n'est
chargée que si elle est vide ; une contrainte UNIQUE violée par une ligne
d'un autre ID fait échouer (et annuler) tout l'import. Prévoir une fenêtre de
maintenance : l'application ne doit pas écrire pendant l'import.
"""
import json
import os
import zipfile

import psycopg2
from django.core.management.base import BaseCommand, CommandError

from ._pg_snapshot import (
    COPY_OPTS, FORMAT_NAME, FORMAT_VERSION, MANIFEST_NAME, NEXTVAL_RE, SCHEMA,
    connect, mask_url, qi, qt, seq_name,
)


class Command(BaseCommand):
    help = ("Importe un export `export_postgres_db` : crée les tables "
            "manquantes, met à jour/crée les lignes par ID.")

    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument(
            "--url", default=None,
            help="URL de la base cible (postgres://user:mdp@hote:5432/base). "
                 "Défaut : variable d'environnement DATABASE_URL.")
        parser.add_argument("--file", "-f", required=True,
                            help="Fichier .zip à importer.")
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
        if not os.path.isfile(path) or not zipfile.is_zipfile(path):
            raise CommandError(f"{path} n'est pas un fichier .zip valide.")

        zf = zipfile.ZipFile(path)
        try:
            manifest = json.loads(zf.read(MANIFEST_NAME).decode("utf-8"))
        except KeyError:
            raise CommandError(f"{MANIFEST_NAME} absent : ce n'est pas un export "
                               "produit par export_postgres_db.")
        if manifest.get("format") != FORMAT_NAME or \
                manifest.get("version") != FORMAT_VERSION:
            raise CommandError("Format d'export non reconnu "
                               f"({manifest.get('format')} v{manifest.get('version')}).")

        conn = connect(url)
        dbname = conn.get_dsn_parameters().get("dbname")
        try:
            with conn.cursor() as cur:
                cur.execute("SHOW server_version")
                self.stdout.write(
                    f"Import de {os.path.basename(path)} (export de "
                    f"{manifest['source']['database']}, PostgreSQL "
                    f"{manifest['source']['server_version']}, "
                    f"{manifest['created_at']}) vers {mask_url(url)} "
                    f"(PostgreSQL {cur.fetchone()[0]})")
                if options["drop_all_tables"]:
                    self._confirm_drop(cur, dbname, options["noinput"])
                self._run(cur, zf, manifest, options["drop_all_tables"])
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
            zf.close()

    # ------------------------------------------------------------------ #
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

    def _run(self, cur, zf, manifest, drop_all):
        tables = manifest["tables"]                    # déjà triées par dépendance
        sequences = {s["name"]: s for s in manifest["sequences"]}

        if drop_all:
            self._drop_all(cur)
        # FK DEFERRABLE (Django) : contrôlées au COMMIT ; sans effet sur les autres.
        cur.execute("SET CONSTRAINTS ALL DEFERRED")

        existing = self._existing_tables(cur)
        created = [t for t in tables if t["name"] not in existing]

        # 1. schéma des tables manquantes
        for t in created:
            self._create_table(cur, t, sequences)
        if created:
            self.stdout.write(f"{len(created)} table(s) créée(s).")
        created_names = {t["name"] for t in created}

        # 2. données
        totals = {"inserted": 0, "updated": 0, "skipped": 0}
        for t in tables:
            self._load_table(cur, zf, t, t["name"] in created_names, totals)

        # 3. contraintes / index / clés étrangères des tables créées
        for t in created:
            for c in t["constraints"]:
                if c["type"] in ("p", "u", "c", "x"):
                    cur.execute(f"ALTER TABLE {qt(t['name'])} ADD CONSTRAINT "
                                f"{qi(c['name'])} {c['def']}")
        for t in created:
            for ix in t["indexes"]:
                cur.execute(ix["def"]
                            .replace("CREATE UNIQUE INDEX ", "CREATE UNIQUE INDEX IF NOT EXISTS ", 1)
                            .replace("CREATE INDEX ", "CREATE INDEX IF NOT EXISTS ", 1))
        for t in created:
            for c in t["constraints"]:
                if c["type"] == "f":
                    cur.execute(f"ALTER TABLE {qt(t['name'])} ADD CONSTRAINT "
                                f"{qi(c['name'])} {c['def']}")

        # 4. séquences
        fixed = self._reset_sequences(cur, tables)

        self.stdout.write(self.style.SUCCESS(
            f"Terminé : {totals['inserted']} ligne(s) créée(s), "
            f"{totals['updated']} mise(s) à jour, {fixed} séquence(s) recalée(s)"
            + (f", {totals['skipped']} table(s) ignorée(s) (voir avertissements)"
               if totals["skipped"] else "") + "."))

    # ------------------------------------------------------------------ #
    def _existing_tables(self, cur):
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = %s",
                    (SCHEMA,))
        return {r[0] for r in cur.fetchall()}

    def _drop_all(self, cur):
        names = sorted(self._existing_tables(cur))
        if names:
            cur.execute("DROP TABLE IF EXISTS "
                        + ", ".join(qt(n) for n in names) + " CASCADE")
        cur.execute("SELECT sequencename FROM pg_sequences WHERE schemaname = %s",
                    (SCHEMA,))
        for (seq,) in cur.fetchall():
            cur.execute(f"DROP SEQUENCE IF EXISTS {qt(seq)} CASCADE")
        self.stdout.write(f"{len(names)} table(s) supprimée(s).")

    def _create_table(self, cur, t, sequences):
        wanted = set()
        for c in t["columns"]:
            m = NEXTVAL_RE.search(c["default"] or "")
            if m:
                wanted.add(seq_name(m.group(1)))
        for name in sorted(wanted):
            if name in sequences:
                cur.execute(sequences[name]["sql"])

        defs = []
        for c in t["columns"]:
            d = f"{qi(c['name'])} {c['type']}"
            if c["generated"] == "s":
                d += f" GENERATED ALWAYS AS ({c['default']}) STORED"
            elif c["identity"] == "a":
                d += " GENERATED ALWAYS AS IDENTITY"
            elif c["identity"] == "d":
                d += " GENERATED BY DEFAULT AS IDENTITY"
            elif c["default"] is not None:
                d += f" DEFAULT {c['default']}"
            if c["notnull"]:
                d += " NOT NULL"
            defs.append(d)
        cur.execute(f"CREATE TABLE {qt(t['name'])} ({', '.join(defs)})")

        for name in sorted(wanted):
            owner = sequences.get(name, {}).get("owned_by")
            if owner and owner[0] == t["name"]:
                cur.execute(f"ALTER SEQUENCE {qt(name)} OWNED BY "
                            f"{qt(owner[0])}.{qi(owner[1])}")

    def _target_columns(self, cur, table):
        cur.execute(
            "SELECT attname, attidentity, attgenerated FROM pg_attribute "
            "WHERE attrelid = %s::regclass AND attnum > 0 AND NOT attisdropped",
            (qt(table),))
        return {n: (i or "", g or "") for n, i, g in cur.fetchall()}

    def _target_pk(self, cur, table):
        cur.execute(
            "SELECT a.attname FROM pg_constraint c "
            "CROSS JOIN LATERAL unnest(c.conkey) WITH ORDINALITY k(attnum, ord) "
            "JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum "
            "WHERE c.conrelid = %s::regclass AND c.contype = 'p' ORDER BY k.ord",
            (qt(table),))
        return [r[0] for r in cur.fetchall()]

    def _load_table(self, cur, zf, t, is_new, totals):
        name = t["name"]
        dump_cols = [c for c in t["columns"] if not c["generated"]]
        if not t["rows"]:
            self.stdout.write(f"  {name}: 0 ligne")
            return
        member = t["file"]
        target = self._target_columns(cur, name)
        common = [c["name"] for c in dump_cols
                  if c["name"] in target and not target[c["name"]][1]]
        dropped = [c["name"] for c in dump_cols if c["name"] not in common]
        if dropped:
            self.stdout.write(self.style.WARNING(
                f"  {name}: colonne(s) du fichier absente(s) de la base, "
                f"ignorée(s) : {', '.join(dropped)}"))
        always = any(target[c][0] == "a" for c in common)
        cols_sql = ", ".join(qi(c) for c in common)
        dump_cols_sql = ", ".join(qi(c["name"]) for c in dump_cols)

        cur.execute(f"SELECT EXISTS (SELECT 1 FROM {qt(name)})")
        empty = not cur.fetchone()[0]

        # Chemin rapide : table vide, mêmes colonnes, pas d'IDENTITY ALWAYS.
        if (is_new or empty) and not dropped and not always:
            with zf.open(member) as fh:
                cur.copy_expert(
                    f"COPY {qt(name)} ({cols_sql}) FROM STDIN {COPY_OPTS}", fh)
            totals["inserted"] += cur.rowcount
            self.stdout.write(f"  {name}: {cur.rowcount} créée(s)")
            return

        # Chemin général : table de transit, puis INSERT … ON CONFLICT.
        stg_cols = ", ".join(f"{qi(c['name'])} {c['type']}" for c in dump_cols)
        cur.execute(f"CREATE TEMP TABLE _stg ({stg_cols}) ON COMMIT DROP")
        with zf.open(member) as fh:
            cur.copy_expert(
                f"COPY _stg ({dump_cols_sql}) FROM STDIN {COPY_OPTS}", fh)

        override = " OVERRIDING SYSTEM VALUE" if always else ""
        if is_new or empty:
            cur.execute(f"INSERT INTO {qt(name)} ({cols_sql}){override} "
                        f"SELECT {cols_sql} FROM _stg")
            n = cur.rowcount
            cur.execute("DROP TABLE _stg")
            totals["inserted"] += n
            self.stdout.write(f"  {name}: {n} créée(s)")
            return

        pk = self._target_pk(cur, name)
        if not pk or any(k not in common for k in pk):
            cur.execute("DROP TABLE _stg")
            totals["skipped"] += 1
            self.stdout.write(self.style.WARNING(
                f"  {name}: IGNORÉE — table non vide sans clé primaire "
                "exploitable (impossible de mettre à jour par ID)."))
            return
        others = [c for c in common if c not in pk]
        conflict = ", ".join(qi(k) for k in pk)
        action = ("DO UPDATE SET " + ", ".join(f"{qi(c)} = EXCLUDED.{qi(c)}"
                                               for c in others)
                  if others else "DO NOTHING")
        cur.execute(
            f"WITH r AS (INSERT INTO {qt(name)} ({cols_sql}){override} "
            f"SELECT {cols_sql} FROM _stg ON CONFLICT ({conflict}) {action} "
            f"RETURNING (xmax = 0) AS ins) "
            f"SELECT count(*) FILTER (WHERE ins), "
            f"       count(*) FILTER (WHERE NOT ins) FROM r")
        ins, upd = cur.fetchone()
        cur.execute("DROP TABLE _stg")
        totals["inserted"] += ins
        totals["updated"] += upd
        self.stdout.write(f"  {name}: {ins} créée(s), {upd} mise(s) à jour")

    def _reset_sequences(self, cur, tables):
        """setval(séquence, max(id)) sans jamais reculer."""
        fixed = 0
        for t in tables:
            for c in t["columns"]:
                if not (c["identity"] or NEXTVAL_RE.search(c["default"] or "")):
                    continue
                cur.execute("SELECT pg_get_serial_sequence(%s, %s)",
                            (qt(t["name"]), c["name"]))
                seq = cur.fetchone()[0]
                if not seq:
                    continue
                cur.execute(f"SELECT COALESCE(MAX({qi(c['name'])}), 0) "
                            f"FROM {qt(t['name'])}")
                max_id = cur.fetchone()[0]
                cur.execute(f"SELECT last_value, is_called FROM {seq}")
                last, called = cur.fetchone()
                new = max(max_id, last if called else 0)
                if new == 0:
                    cur.execute("SELECT setval(%s, 1, false)", (seq,))
                else:
                    cur.execute("SELECT setval(%s, %s, true)", (seq, new))
                fixed += 1
        return fixed
