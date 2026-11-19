"""Sauvegarde toutes les bases CouchDB vers S3.

Équivalent serveur de `export_code_original.py` (COUCHDB/requests/exports).
Le zip `<AAAAMMJJHHMM>.zip` envoyé dans s3://.../backupsdb/couchdb/ contient :
     - `<AAAAMMJJHHMM>/dbs_<date>.json`        liste des bases (_all_dbs)
     - `<AAAAMMJJHHMM>/original/<base>.json`   réponse brute de _all_docs?include_docs=true
                                               (seulement avec --add-original)
     - `<AAAAMMJJHHMM>/<base>.json`            {"docs": [...]} avec `_rev` renommé en `rev`
                                               (format lu par import_code.py / _bulk_docs)
     - `<AAAAMMJJHHMM>/failures_<date>.json`   bases en échec, s'il y en a

Espace disque (incident du 13/11/2026 : « No space left on device » en
production après ~145 bases, la 1re version écrivait tout le dossier JSON non
compressé avant de zipper) :
- par défaut, le zip est écrit AU FIL DE L'EAU directement dans
  `aws s3 cp - s3://.../<AAAAMMJJHHMM>.zip` (entrée standard) : rien n'est
  stocké sur le serveur, ni dossier, ni zip ;
- seule une base à la fois transite par un fichier temporaire (deux avec
  --add-original) (en mémoire
  jusqu'à 32 Mo, sinon sur disque dans --workdir), versés dans le zip une fois la
  base lue en entier, puis supprimés ;
- arrêt immédiat de toute la sauvegarde au premier « No space left on device »
  ou si l'espace libre de --workdir descend sous --min-free-mb (500 Mo par
  défaut) : on ne remplit jamais le disque du serveur web ;
- `--via-file` : ancien fonctionnement (zip complet sur disque puis
  `aws s3 cp <zip>`), dans /var/tmp par défaut (/tmp est souvent un tmpfs en
  mémoire sur Amazon Linux 2023).
Dans tous les cas, tout fichier local est supprimé à la fin, même en cas d'échec.

Lecture calquée sur `dashboard.tasks.sync_celery_tasks_re` pour ne pas charger
le serveur :
- connexion par `NoSQLClient` (session cloudant authentifiée, renouvelée
  automatiquement), avec un timeout pour qu'une base lente ne bloque pas tout ;
- une base à la fois (`nsc.get_db`), lue par pages de `--page-size` documents
  (1000 par défaut, comme `NoSQLClient.find_all`) ;
- l'objet base est retiré du cache du client une fois exporté.
On lit `_all_docs` et non `_find` (utilisé par `find_all`) parce que `_find`
ne renvoie pas les documents de conception (`_design/...`) : la sauvegarde
doit être complète.

En plus : processus en priorité basse (`nice`), courte pause entre les bases,
une base en échec (hors disque plein) est réessayée puis signalée sans arrêter
les autres.

Pour la lancer en production (en SSH sur l'instance EB) :

cd /var/app/current
source /var/app/venv/*/bin/activate
export $(/opt/elasticbeanstalk/bin/get-config --output YAML environment | sed 's/: /=/' | xargs)   # si les variables d'environnement ne sont pas chargées
python manage.py backup_couchdb

Options :

--add-original : ajoute aussi original/<base>.json (réponse brute) dans le zip ;
--dry-run : écrit le zip sur disque (dans --workdir) sans l'envoyer, puis le supprime (sauf --keep) ;
--via-file : construit le zip sur disque puis `aws s3 cp <zip>` (au lieu de l'envoi direct) ;
--dbs a,b : exporter seulement certaines bases ;
--start-db X : reprendre à partir d'une base ;
--exclude-system : ignorer les bases système (_users, etc.) ;
--workdir : dossier des fichiers temporaires (défaut /var/tmp, sinon /tmp) ;
--min-free-mb : espace libre minimal à préserver dans --workdir (défaut 500) ;
--keep : garder le zip local, pour déboguer (implique un zip sur disque) ;
--s3-uri : changer la destination S3.
"""
import contextlib
import errno
import json
import os
import shutil
import subprocess
import tempfile
import time
import zipfile
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from dashboard.commands_runner.progress import report as report_progress  # menu « Commandes / sync »

from no_sql_client import NoSQLClient

DEFAULT_S3_URI = "s3://elasticbeanstalk-us-west-1-371600284712/backupsdb/couchdb/"
RETRIES = 3
SPOOL_MAX_BYTES = 32 * 1024 * 1024
COPY_CHUNK = 1024 * 1024


class DiskFull(CommandError):
    """Disque plein ou sous le seuil --min-free-mb : on arrête tout."""


class UploadBroken(CommandError):
    """`aws s3 cp -` s'est arrêté, ou l'écriture dans le zip a échoué (une
    entrée à moitié écrite ne se rattrape pas) : on arrête tout."""


class _WriteOnly:
    """Flux en écriture seule (ni tell ni seek) : `zipfile` passe alors en mode
    flux (descripteurs de données) au lieu de revenir en arrière pour réécrire
    les en-têtes — impossible sur un tube. Sans cette enveloppe, un tube dont
    `tell()` ne lève pas d'erreur (Windows) donne un zip corrompu."""

    def __init__(self, raw):
        self._raw = raw

    def write(self, b):
        return self._raw.write(b)

    def flush(self):
        self._raw.flush()

    def close(self):
        self._raw.close()


def _default_workdir():
    # /var/tmp est sur le disque ; /tmp est souvent un tmpfs (RAM) sous AL2023.
    return "/var/tmp" if os.path.isdir("/var/tmp") else tempfile.gettempdir()


class Command(BaseCommand):
    help = ("Exporte toutes les bases CouchDB dans un zip envoyé sur S3 "
            "(aws s3 cp), sans rien laisser sur le serveur.")

    # Aucune requête ORM.
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--s3-uri", default=DEFAULT_S3_URI,
                            help=f"Destination S3 (défaut : {DEFAULT_S3_URI}).")
        parser.add_argument("--via-file", action="store_true",
                            help="Construit le zip sur disque puis l'envoie "
                                 "(au lieu de l'envoyer au fil de l'eau).")
        parser.add_argument("--workdir", default=None,
                            help="Dossier des fichiers temporaires (défaut : "
                                 "/var/tmp, sinon dossier temporaire système).")
        parser.add_argument("--min-free-mb", type=int, default=500,
                            help="Arrêt si l'espace libre de --workdir passe "
                                 "sous ce seuil (défaut : 500 Mo).")
        parser.add_argument("--dbs", default=None,
                            help="Bases à exporter, séparées par des virgules "
                                 "(défaut : toutes).")
        parser.add_argument("--start-db", default=None,
                            help="Reprendre à partir de cette base (ordre de "
                                 "_all_dbs).")
        parser.add_argument("--exclude-system", action="store_true",
                            help="Ignore les bases système (_users, "
                                 "_replicator, _global_changes).")
        parser.add_argument("--page-size", type=int, default=1000,
                            help="Documents lus par requête (défaut : 1000, "
                                 "comme NoSQLClient.find_all).")
        parser.add_argument("--timeout", type=int, default=120,
                            help="Timeout d'une requête CouchDB en secondes "
                                 "(défaut : 120).")
        parser.add_argument("--pause", type=float, default=0.2,
                            help="Pause en secondes entre deux bases (défaut : 0.2).")
        parser.add_argument("--add-original", "--add--original", action="store_true",
                            dest="add_original",
                            help="Ajoute aussi original/<base>.json (réponse brute "
                                 "de _all_docs) dans le zip. Par défaut, seul "
                                 "<base>.json (format d'import) est sauvegardé.")
        parser.add_argument("--dry-run", action="store_true",
                            help="Écrit le zip sur disque sans l'envoyer sur S3 "
                                 "(supprimé ensuite, sauf --keep).")
        parser.add_argument("--keep", action="store_true",
                            help="Débogage : conserve le zip local.")

    # ------------------------------------------------------------------ #
    def handle(self, *args, **opts):
        self.page_size = max(1, opts["page_size"])
        self.add_original = opts["add_original"]
        self.min_free = max(0, opts["min_free_mb"]) * 1024 * 1024
        to_file = opts["via_file"] or opts["dry_run"] or opts["keep"]

        s3_uri = opts["s3_uri"]
        if not s3_uri.startswith("s3://"):
            raise CommandError("--s3-uri doit commencer par s3://")
        if not s3_uri.endswith("/"):
            s3_uri += "/"
        if not opts["dry_run"] and shutil.which("aws") is None:
            raise CommandError("La commande `aws` est introuvable sur ce serveur.")

        # Priorité CPU basse : le serveur web reste prioritaire (Linux seulement).
        if hasattr(os, "nice"):
            os.nice(10)

        stamp = datetime.now().strftime("%Y%m%d%H%M")
        self.workdir = opts["workdir"] or _default_workdir()
        os.makedirs(self.workdir, exist_ok=True)
        self._check_free_space()
        zip_name = stamp + ".zip"
        zip_path = os.path.join(self.workdir, zip_name)
        if to_file and os.path.exists(zip_path):
            raise CommandError(f"{zip_path} existe déjà : relancer dans une minute.")

        self.nsc = NoSQLClient(timeout=opts["timeout"])
        self.stdout.write(f"CouchDB : {self.nsc.url}")
        self.stdout.write(f"Fichiers temporaires : {self.workdir} "
                          f"({self._free_mb():.0f} Mo libres)")

        started = time.time()
        failures = []
        proc = None
        success = False
        try:
            if to_file:
                sink = open(zip_path, "wb")
            else:
                cmd = ["aws", "s3", "cp", "-", s3_uri + zip_name]
                self.stdout.write("$ " + " ".join(cmd) + "   (envoi au fil de l'eau)")
                proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
                sink = _WriteOnly(proc.stdin)
            self.proc = proc

            zf = zipfile.ZipFile(sink, "w", zipfile.ZIP_DEFLATED, allowZip64=True)
            try:
                total_docs, n_dbs = self._export_all(zf, stamp, opts, failures)
            except BaseException:
                # Échec (ou Ctrl+C) : couper aws AVANT de fermer le zip. Sinon
                # zf.close() écrirait un zip partiel mais valide et la fermeture
                # du tube ferait finaliser son envoi sur S3.
                if proc is not None:
                    proc.kill()
                    proc.wait()
                for close in (zf.close, sink.close):
                    try:
                        close()
                    except Exception:
                        pass
                raise
            zf.close()
            sink.close()

            if proc is not None:
                rc = proc.wait()
                proc = None
                if rc != 0:
                    raise CommandError(f"aws s3 cp a échoué (code {rc}).")
                self.stdout.write(self.style.SUCCESS(
                    f"Envoyé : {s3_uri}{zip_name} — {n_dbs - len(failures)}/{n_dbs} "
                    f"bases, {total_docs} docs ({time.time() - started:.0f} s)"))
            else:
                size_mb = os.path.getsize(zip_path) / (1024 * 1024)
                self.stdout.write(f"{n_dbs - len(failures)}/{n_dbs} bases, "
                                  f"{total_docs} docs, zip {size_mb:.1f} Mo")
                if opts["dry_run"]:
                    self.stdout.write(self.style.WARNING("--dry-run : pas d'envoi sur S3."))
                else:
                    self._upload(zip_path, s3_uri)
                    self.stdout.write(self.style.SUCCESS(
                        f"Envoyé : {s3_uri}{zip_name} "
                        f"({time.time() - started:.0f} s)"))
            success = True
        finally:
            if proc is not None:
                # Échec en cours d'envoi : on coupe aws, l'envoi multipart n'est
                # pas finalisé donc aucun zip tronqué n'apparaît sur S3.
                proc.kill()
                proc.wait()
                if not success:
                    self.stderr.write("Envoi S3 interrompu : aucun zip créé sur S3.")
            if opts["keep"] and os.path.exists(zip_path):
                self.stdout.write(f"--keep : conservé {zip_path}")
            elif os.path.exists(zip_path):
                os.remove(zip_path)
                self.stdout.write("Zip supprimé du serveur.")
            try:
                self.nsc.client.disconnect()
            except Exception:
                pass

        if failures:
            raise CommandError(
                f"{len(failures)} base(s) non exportée(s) (liste dans "
                f"failures_{stamp}.json du zip) : "
                + ", ".join(name for name, _ in failures))

    # ------------------------------------------------------------------ #
    def _check_upload_alive(self):
        proc = getattr(self, "proc", None)
        if proc is not None and proc.poll() is not None:
            raise UploadBroken(f"aws s3 cp s'est arrêté (code {proc.returncode}) : "
                               "sauvegarde interrompue.")

    def _free_mb(self):
        return shutil.disk_usage(self.workdir).free / (1024 * 1024)

    def _check_free_space(self):
        free = shutil.disk_usage(self.workdir).free
        if free < self.min_free:
            raise DiskFull(
                f"seulement {free / (1024 * 1024):.0f} Mo libres dans {self.workdir} "
                f"(minimum {self.min_free // (1024 * 1024)} Mo, --min-free-mb).")

    def _export_all(self, zf, stamp, opts, failures):
        dbs, all_dbs = self._list_dbs(opts)
        zf.writestr(f"{stamp}/dbs_{stamp}.json", json.dumps(all_dbs, ensure_ascii=False))
        total_docs = 0
        for i, db_name in enumerate(dbs, start=1):
            report_progress(phase="Export des bases CouchDB", done=i - 1, total=len(dbs), current=db_name)
            self._check_free_space()
            self._check_upload_alive()
            try:
                n = self._export_db_with_retry(db_name, zf, stamp)
                total_docs += n
                self.stdout.write(f"  [{i}/{len(dbs)}] {db_name} : {n} docs")
            except (DiskFull, UploadBroken):
                raise
            except Exception as e:  # une base en échec n'arrête pas les autres
                failures.append((db_name, repr(e)))
                self.stderr.write(f"  [{i}/{len(dbs)}] {db_name} : ÉCHEC {e!r}")
            finally:
                # Comme un dict : évite d'accumuler ~1000 objets base en cache.
                self.nsc.client.pop(db_name, None)
            if opts["pause"]:
                time.sleep(opts["pause"])
        if failures:
            zf.writestr(f"{stamp}/failures_{stamp}.json",
                        json.dumps(failures, ensure_ascii=False, indent=1))
        return total_docs, len(dbs)

    def _list_dbs(self, opts):
        all_dbs = self.nsc.get_dbs()
        dbs = list(all_dbs)
        if opts["dbs"]:
            wanted = [d.strip() for d in opts["dbs"].split(",") if d.strip()]
            missing = [d for d in wanted if d not in all_dbs]
            if missing:
                raise CommandError(f"Bases inexistantes : {', '.join(missing)}")
            dbs = [d for d in dbs if d in wanted]
        if opts["exclude_system"]:
            dbs = [d for d in dbs if not d.startswith("_")]
        if opts["start_db"]:
            if opts["start_db"] not in dbs:
                raise CommandError(f"--start-db {opts['start_db']} introuvable.")
            dbs = dbs[dbs.index(opts["start_db"]):]
        self.stdout.write(f"{len(dbs)} base(s) à exporter sur {len(all_dbs)}.")
        return dbs, all_dbs

    def _iter_pages(self, db):
        """_all_docs?include_docs=true par pages (startkey + limit), comme
        `find_all` pagine `_find` par bookmark."""
        startkey = None
        while True:
            params = {"include_docs": True, "limit": self.page_size + 1}
            if startkey is not None:
                params["startkey"] = startkey
            data = db.all_docs(**params)
            rows = data.get("rows", [])
            yield data, rows[:self.page_size]
            if len(rows) <= self.page_size:
                return
            startkey = rows[self.page_size]["key"]

    def _export_db_with_retry(self, db_name, zf, stamp):
        for attempt in range(1, RETRIES + 1):
            try:
                return self._export_db(db_name, zf, stamp)
            except (DiskFull, UploadBroken):
                raise
            except OSError as e:
                if e.errno == errno.ENOSPC:
                    raise DiskFull(f"disque plein dans {self.workdir} ({db_name}).")
                if attempt == RETRIES:
                    raise
                self._retry_msg(db_name, attempt, e)
            except Exception as e:
                if attempt == RETRIES:
                    raise
                self._retry_msg(db_name, attempt, e)

    def _retry_msg(self, db_name, attempt, e):
        self._check_upload_alive()
        self.stderr.write(f"    {db_name} : tentative {attempt} échouée "
                          f"({e!r}), nouvel essai…")
        time.sleep(3 * attempt)

    def _export_db(self, db_name, zf, stamp):
        """Lit la base dans un fichier temporaire (converti ; plus le brut avec
        --add-original), puis le(s) verse dans le zip seulement si la lecture a réussi en entier : une
        nouvelle tentative ne laisse donc jamais d'entrée tronquée ou en double."""
        db = self.nsc.get_db(db_name)
        # Un nom de base CouchDB peut contenir "/" : interdit dans un nom de fichier.
        fname = db_name.replace("/", "%2F") + ".json"
        count = n_docs = 0
        with contextlib.ExitStack() as stack:
            def spool():
                return stack.enter_context(tempfile.SpooledTemporaryFile(
                    SPOOL_MAX_BYTES, "w+b", dir=self.workdir))
            conv = spool()
            orig = spool() if self.add_original else None

            def w(f, s):
                if f is not None:
                    f.write(s.encode("utf-8"))

            total_rows = None
            for data, rows in self._iter_pages(db):
                if total_rows is None:
                    total_rows = json.dumps(data.get("total_rows"))
                    w(orig, '{"total_rows": %s, "offset": 0, "rows": [' % total_rows)
                    w(conv, '{"docs": [')
                for row in rows:
                    if orig is not None:
                        w(orig, ("," if count else "") + json.dumps(row, ensure_ascii=False))
                    doc = row.get("doc")
                    if doc:
                        if "_rev" in doc:
                            doc["rev"] = doc.pop("_rev")
                        w(conv, ("," if n_docs else "") + json.dumps(doc, ensure_ascii=False))
                        n_docs += 1
                    count += 1
            w(orig, "]}")
            w(conv, '], "total_rows": %s, "offset": 0}' % total_rows)

            # Jusqu'ici, rien n'est écrit dans le zip : une erreur de lecture
            # peut être réessayée. À partir d'ici, toute erreur est fatale.
            try:
                if orig is not None:
                    self._add_to_zip(zf, f"{stamp}/original/{fname}", orig)
                self._add_to_zip(zf, f"{stamp}/{fname}", conv)
            except OSError as e:
                if e.errno == errno.ENOSPC:
                    raise DiskFull(f"disque plein dans {self.workdir} ({db_name}).")
                self._check_upload_alive()
                raise UploadBroken(f"écriture du zip impossible ({db_name}) : {e!r}")
        return count

    @staticmethod
    def _add_to_zip(zf, arcname, fileobj):
        size = fileobj.tell()
        fileobj.seek(0)
        info = zipfile.ZipInfo(arcname, date_time=time.localtime()[:6])
        info.compress_type = zipfile.ZIP_DEFLATED
        with zf.open(info, "w", force_zip64=size > zipfile.ZIP64_LIMIT // 2) as dst:
            shutil.copyfileobj(fileobj, dst, COPY_CHUNK)

    def _upload(self, zip_path, s3_uri):
        cmd = ["aws", "s3", "cp", zip_path, s3_uri]
        self.stdout.write("$ " + " ".join(cmd))
        res = subprocess.run(cmd)
        if res.returncode != 0:
            raise CommandError(f"aws s3 cp a échoué (code {res.returncode}).")
