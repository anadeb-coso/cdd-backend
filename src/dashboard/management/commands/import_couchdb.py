"""Importe dans CouchDB les bases d'une sauvegarde `backup_couchdb`.

Équivalent serveur de `import_by_doc_locale.py` (COUCHDB/requests/exports) :
pour chaque `<base>.json`, crée la base si besoin puis y verse les documents
par `_bulk_docs`.

GARDE-FOU : sans `--drop-existing`, l'import est REFUSÉ si le CouchDB cible
contient déjà au moins une base `facilitator_*` (jamais de mélange d'une
sauvegarde avec des données vivantes). Avec `--drop-existing`, il est autorisé :
les bases de la source sont remplacées, et les bases `facilitator_*` de la cible
ABSENTES de la source sont signalées (elles sont conservées telles quelles).

Source (`--source`), au choix :
- un zip produit par `backup_couchdb` (entrées `<AAAAMMJJHHMM>/<base>.json`) ;
- une URI `s3://.../<AAAAMMJJHHMM>.zip` : téléchargée avec `aws s3 cp` dans
  --workdir, puis supprimée à la fin (même en cas d'échec) ;
- un dossier contenant des `<base>.json` (format de l'ancien script).
Formats lus : `{"docs": [...]}` (rev ou _rev) et `{"rows": [{"doc": ...}]}`.
Les fichiers `dbs_*`, `failures_*` et le dossier `original/` sont ignorés.

Révisions : par défaut, les `_rev` d'origine sont CONSERVÉS
(`_bulk_docs` avec `new_edits: false`, comme une réplication). Les documents
restaurés sont alors identiques à la source, ce qui évite des conflits avec les
téléphones qui synchronisent encore les bases facilitateur, et un nouvel import
de la même sauvegarde ne crée aucun doublon. `--new-revisions` reprend le
comportement de l'ancien script (rev supprimé, nouvelles révisions 1-xxx).

Mémoire : les fichiers sont lus en flux (document par document, sans charger le
JSON entier) et envoyés par lots de `--batch-size` documents.

Sécurité d'écriture :
- sans `--apply`, simple simulation (rien n'est écrit) : bases et nombre de
  documents qui seraient importés ;
- avec `--apply`, l'URL du CouchDB cible est affichée et une confirmation est
  demandée (`--yes` pour l'automatiser) ;
- `_replicator` et `_global_changes` sont ignorées par défaut (importer
  `_replicator` relancerait d'anciennes réplications).

Suppression préalable (`--drop-existing`) : chaque base de la source (après
--dbs / --skip-dbs) qui existe déjà sur la cible est SUPPRIMÉE puis recréée
avant l'import, pour repartir exactement de la sauvegarde. Seules les bases
présentes dans le zip ou le dossier sont concernées ; les autres bases de la
cible ne sont jamais touchées. Le fichier de la base est d'abord relu en entier :
s'il est illisible ou tronqué, la base est signalée en échec SANS être supprimée.
La simulation et la confirmation listent les bases qui seront supprimées.

Exemples :
    python manage.py import_couchdb --source s3://elasticbeanstalk-us-west-1-371600284712/backupsdb/couchdb/202611131533.zip
    python manage.py import_couchdb --source 202611131533.zip --apply
    python manage.py import_couchdb --source D:/couchdb/exports/ --apply --dbs administrative_levels
    python manage.py import_couchdb --source 202611131533.zip --apply --drop-existing
"""
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile

from django.core.management.base import BaseCommand, CommandError

from no_sql_client import NoSQLClient

DEFAULT_SKIP = "_replicator,_global_changes"
READ_CHUNK = 1024 * 1024
BATCH_MAX_CHARS = 8 * 1024 * 1024
ARRAY_START_RE = re.compile(r'"(docs|rows)"\s*:\s*\[')
SKIPPED_PREFIXES = ("dbs_", "failures_")


def iter_array_items(text):
    """Parcourt en flux les objets du tableau "docs" (ou "rows") d'un fichier
    JSON, sans le charger en entier. Renvoie des couples (clé, objet)."""
    dec = json.JSONDecoder()
    buf = ""
    while True:
        m = ARRAY_START_RE.search(buf)
        if m:
            key = m.group(1)
            buf = buf[m.end():]
            break
        chunk = text.read(READ_CHUNK)
        if not chunk:
            return  # ni "docs" ni "rows" : rien à importer
        buf = buf[-64:] + chunk
    pos = 0
    while True:
        while pos < len(buf) and buf[pos] in " \t\r\n,":
            pos += 1
        if pos >= len(buf):
            chunk = text.read(READ_CHUNK)
            if not chunk:
                raise ValueError("fichier tronqué (tableau non fermé)")
            buf, pos = buf[pos:] + chunk, 0
            continue
        if buf[pos] == "]":
            return
        try:
            obj, end = dec.raw_decode(buf, pos)
        except json.JSONDecodeError:
            # Objet coupé par la fin du morceau lu : lire la suite.
            chunk = text.read(READ_CHUNK)
            if not chunk:
                raise
            buf, pos = buf[pos:] + chunk, 0
            continue
        yield key, obj
        pos = end
        if pos > READ_CHUNK:
            buf, pos = buf[pos:], 0


class Command(BaseCommand):
    help = ("Importe dans CouchDB les bases d'une sauvegarde backup_couchdb "
            "(zip, s3:// ou dossier). Refusé si une base facilitator_* existe déjà, "
            "sauf avec --drop-existing.")

    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--source", required=True,
                            help="Zip de backup_couchdb, URI s3://…zip, ou dossier de <base>.json.")
        parser.add_argument("--apply", action="store_true",
                            help="Écrit réellement dans CouchDB (sinon simulation).")
        parser.add_argument("--yes", action="store_true",
                            help="Avec --apply : ne pas demander de confirmation.")
        parser.add_argument("--url", default=None,
                            help="CouchDB cible (défaut : NO_SQL_URL des réglages).")
        parser.add_argument("--user", default=None,
                            help="Utilisateur CouchDB (défaut : NO_SQL_USER).")
        parser.add_argument("--password", default=None,
                            help="Mot de passe CouchDB (défaut : NO_SQL_PASS).")
        parser.add_argument("--dbs", default=None,
                            help="Bases à importer, séparées par des virgules (défaut : toutes).")
        parser.add_argument("--skip-dbs", default=DEFAULT_SKIP,
                            help=f"Bases ignorées (défaut : {DEFAULT_SKIP} ; \"\" pour aucune).")
        parser.add_argument("--drop-existing", action="store_true",
                            help="Supprime puis recrée, avant l'import, les bases de la "
                                 "source qui existent déjà sur la cible (les autres "
                                 "bases de la cible ne sont pas touchées).")
        parser.add_argument("--new-revisions", action="store_true",
                            help="Comme l'ancien script : supprime rev/_rev et crée de "
                                 "nouvelles révisions (défaut : révisions d'origine conservées).")
        parser.add_argument("--batch-size", type=int, default=500,
                            help="Documents par requête _bulk_docs (défaut : 500).")
        parser.add_argument("--timeout", type=int, default=300,
                            help="Timeout d'une requête CouchDB en secondes (défaut : 300).")
        parser.add_argument("--workdir", default=None,
                            help="Dossier du téléchargement S3 (défaut : /var/tmp, sinon temporaire système).")

    # ------------------------------------------------------------------ #
    def handle(self, *args, **opts):
        self.batch_size = max(1, opts["batch_size"])
        self.keep_revs = not opts["new_revisions"]
        self.drop_existing = opts["drop_existing"]
        kwargs = {"timeout": opts["timeout"]}
        for opt, arg in (("url", "url"), ("user", "username"), ("password", "password")):
            if opts[opt]:
                kwargs[arg] = opts[opt]
        self.nsc = NoSQLClient(**kwargs)
        target = self.nsc.url
        self.stdout.write(f"CouchDB cible : {target}")

        # 1) Garde-fou : aucune base facilitateur sur la cible.
        existing = self.nsc.get_dbs()
        fac = [d for d in existing if d.startswith("facilitator_")]
        if fac and not self.drop_existing:
            raise CommandError(
                f"Import refusé : le CouchDB cible contient déjà {len(fac)} base(s) "
                f"facilitator_* (ex. {', '.join(fac[:3])}). L'import est réservé à un "
                "CouchDB sans base facilitateur, sauf avec --drop-existing (les bases "
                "de la source sont alors supprimées puis recréées).")
        if fac:
            self.stdout.write(self.style.WARNING(
                f"{len(fac)} base(s) facilitator_* sur la cible : import autorisé car "
                "--drop-existing est demandé."))
        else:
            self.stdout.write(f"Aucune base facilitator_* sur la cible ({len(existing)} base(s) "
                              "existante(s)) : import autorisé.")

        downloaded = None
        try:
            source = opts["source"]
            if source.startswith("s3://"):
                downloaded = source = self._download(source, opts["workdir"])
            entries = self._list_entries(source)
            entries = self._filter(entries, opts)
            if not entries:
                raise CommandError("Aucune base à importer dans la source.")

            mode = "révisions d'origine conservées" if self.keep_revs else "nouvelles révisions"
            self.stdout.write(f"{len(entries)} base(s) dans la source ({mode}).")
            to_drop = ([n for n, _ in entries if n in set(existing)]
                       if self.drop_existing else [])
            if self.drop_existing:
                if to_drop:
                    self.stdout.write(self.style.WARNING(
                        f"--drop-existing : {len(to_drop)} base(s) existante(s) seront "
                        f"SUPPRIMÉES puis recréées : {', '.join(to_drop[:10])}"
                        f"{f', … (+{len(to_drop) - 10})' if len(to_drop) > 10 else ''}"))
                else:
                    self.stdout.write("--drop-existing : aucune base de la source "
                                      "n'existe sur la cible, rien à supprimer.")
                source_names = {n for n, _ in entries}
                kept = [d for d in fac if d not in source_names]
                if kept:
                    self.stdout.write(self.style.WARNING(
                        f"{len(kept)} base(s) facilitator_* de la cible sont ABSENTES de "
                        f"la source et resteront telles quelles (ex. {', '.join(kept[:5])})."))

            if opts["apply"] and not opts["yes"]:
                drop_msg = (f" en SUPPRIMANT d'abord {len(to_drop)} base(s) existante(s)"
                            if to_drop else "")
                answer = input(f"Importer {len(entries)} base(s) dans {target}{drop_msg} ? "
                               "Taper « oui » pour confirmer : ")
                if answer.strip().lower() not in ("oui", "yes"):
                    raise CommandError("Import annulé.")

            existing = set(existing)
            totals = {"docs": 0, "errors": 0, "created": 0, "dropped": 0}
            failed = []
            for i, (db_name, opener) in enumerate(entries, start=1):
                try:
                    n, errors, created, dropped = self._import_db(
                        db_name, opener, db_name in existing, opts["apply"])
                except Exception as e:
                    failed.append(db_name)
                    self.stderr.write(f"  [{i}/{len(entries)}] {db_name} : ÉCHEC {e!r}")
                    continue
                finally:
                    self.nsc.client.pop(db_name, None)
                totals["docs"] += n
                totals["errors"] += errors
                totals["created"] += created
                totals["dropped"] += dropped
                if db_name not in existing:
                    state = "créée" if opts["apply"] else "à créer"
                elif self.drop_existing:
                    state = ("supprimée puis recréée" if opts["apply"]
                             else "à supprimer puis recréer")
                else:
                    state = "existante"
                err = f", {errors} rejeté(s)" if errors else ""
                self.stdout.write(f"  [{i}/{len(entries)}] {db_name} ({state}) : {n} docs{err}")

            verb = "importés" if opts["apply"] else "à importer (simulation, rien n'a été écrit)"
            msg = (f"{len(entries) - len(failed)}/{len(entries)} bases, {totals['docs']} docs {verb}, "
                   f"{totals['created']} base(s) créée(s) (dont {totals['dropped']} supprimée(s) "
                   f"au préalable), {totals['errors']} doc(s) rejeté(s).")
            if failed or totals["errors"]:
                self.stdout.write(self.style.WARNING(msg))
            else:
                self.stdout.write(self.style.SUCCESS(msg))
            if not opts["apply"]:
                self.stdout.write("Relancer avec --apply pour importer.")
            if failed:
                raise CommandError(f"{len(failed)} base(s) en échec : {', '.join(failed)}")
        finally:
            if downloaded and os.path.exists(downloaded):
                os.remove(downloaded)
                self.stdout.write("Zip téléchargé supprimé.")
            try:
                self.nsc.client.disconnect()
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    def _download(self, uri, workdir):
        if shutil.which("aws") is None:
            raise CommandError("La commande `aws` est introuvable sur ce serveur.")
        workdir = workdir or ("/var/tmp" if os.path.isdir("/var/tmp") else tempfile.gettempdir())
        os.makedirs(workdir, exist_ok=True)
        path = os.path.join(workdir, "import_couchdb_" + os.path.basename(uri.rstrip("/")))
        cmd = ["aws", "s3", "cp", uri, path]
        self.stdout.write("$ " + " ".join(cmd))
        if subprocess.run(cmd).returncode != 0:
            if os.path.exists(path):
                os.remove(path)
            raise CommandError("Téléchargement S3 impossible.")
        return path

    def _list_entries(self, source):
        """Liste des (nom de base, ouvreur de flux texte) de la source."""
        def is_db_file(name):
            return name.endswith(".json") and not name.startswith(SKIPPED_PREFIXES)

        def db_name_of(name):
            return name[:-len(".json")].replace("%2F", "/")

        if os.path.isdir(source):
            out = []
            for name in sorted(os.listdir(source)):
                full = os.path.join(source, name)
                if os.path.isfile(full) and is_db_file(name):
                    out.append((db_name_of(name),
                                lambda p=full: open(p, encoding="utf-8")))
            return out
        if zipfile.is_zipfile(source):
            zf = zipfile.ZipFile(source)
            self._zip = zf  # gardé ouvert pendant l'import
            out = []
            for name in zf.namelist():
                parts = name.split("/")
                if "original" in parts[:-1]:
                    continue
                base = parts[-1]
                if is_db_file(base):
                    out.append((db_name_of(base),
                                lambda n=name: io.TextIOWrapper(zf.open(n), encoding="utf-8")))
            return sorted(out, key=lambda e: e[0])
        if not os.path.exists(source):
            raise CommandError(
                f"Source introuvable : {source} (vue depuis ce processus : système "
                f"{os.name}, dossier courant {os.getcwd()}). Si la commande tourne dans "
                "WSL, Docker ou sur un serveur, ce chemin Windows n'y existe pas.")
        raise CommandError(f"Format non reconnu (ni dossier ni zip valide) : {source}")

    def _filter(self, entries, opts):
        names = [n for n, _ in entries]
        if len(set(names)) != len(names):
            raise CommandError("La source contient plusieurs fichiers pour une même base.")
        if opts["dbs"]:
            wanted = [d.strip() for d in opts["dbs"].split(",") if d.strip()]
            missing = [d for d in wanted if d not in names]
            if missing:
                raise CommandError(f"Absentes de la source : {', '.join(missing)}")
            entries = [e for e in entries if e[0] in wanted]
        skip = {d.strip() for d in (opts["skip_dbs"] or "").split(",") if d.strip()}
        return [e for e in entries if e[0] not in skip]

    def _iter_docs(self, text):
        for key, item in iter_array_items(text):
            doc = item.get("doc") if key == "rows" else item
            if not doc:
                continue
            rev = doc.pop("rev", None)
            rev = doc.pop("_rev", None) or rev
            if self.keep_revs and rev:
                doc["_rev"] = rev
            yield doc

    def _import_db(self, db_name, opener, exists, apply):
        created = dropped = 0
        db = None
        if apply:
            if exists and self.drop_existing:
                # Relire tout le fichier AVANT de supprimer : un fichier illisible
                # ou tronqué lève ici une erreur et la base reste intacte.
                with opener() as text:
                    for _ in self._iter_docs(text):
                        pass
                self.nsc.client.delete_database(db_name)
                self.nsc.client.pop(db_name, None)
                dropped = 1
                exists = False
            if exists:
                db = self.nsc.get_db(db_name)
            else:
                db = self.nsc.create_db(db_name, throw_on_exists=False)
                created = 1
        count = errors = 0
        batch, size = [], 0
        with opener() as text:
            for doc in self._iter_docs(text):
                count += 1
                if not apply:
                    continue
                batch.append(doc)
                size += len(json.dumps(doc, ensure_ascii=False))
                if len(batch) >= self.batch_size or size >= BATCH_MAX_CHARS:
                    errors += self._send(db, batch)
                    batch, size = [], 0
        if apply and batch:
            errors += self._send(db, batch)
        return count, errors, created, dropped

    def _send(self, db, docs):
        """Envoie un lot ; renvoie le nombre de documents rejetés."""
        errors = 0
        with_rev = [d for d in docs if "_rev" in d] if self.keep_revs else []
        without_rev = [d for d in docs if "_rev" not in d] if self.keep_revs else docs
        url = "/".join((db.database_url, "_bulk_docs"))
        for group, new_edits in ((with_rev, False), (without_rev, True)):
            if not group:
                continue
            body = {"docs": group}
            if not new_edits:
                body["new_edits"] = False
            resp = self.nsc.client.r_session.post(
                url, data=json.dumps(body), headers={"Content-Type": "application/json"})
            resp.raise_for_status()
            result = resp.json()
            if isinstance(result, list):
                for r in result:
                    if isinstance(r, dict) and r.get("error"):
                        errors += 1
                        if errors <= 3:
                            self.stderr.write(f"    rejeté {r.get('id')} : {r.get('error')} "
                                              f"{r.get('reason', '')}")
        return errors
