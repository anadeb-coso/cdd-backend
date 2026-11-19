"""Base commune des commandes `backup_postgres_db` / `backup_postgres_db_sql`.

Lance une commande d'export existante (`export_postgres_db` ou
`export_postgres_db_sql`, inchangées) vers un fichier temporaire, envoie ce
fichier sur S3 avec `aws s3 cp`, puis le supprime du serveur — y compris si
l'export ou l'envoi échoue (le `.part` laissé par un export interrompu est
supprimé aussi).

Le module commence par `_` : Django ne le prend pas pour une commande.


Pour les lancer en production, sur l'instance EB :

cd /var/app/current && source /var/app/venv/*/bin/activate
python manage.py backup_postgres_db_sql      # ou backup_postgres_db
Par défaut, la base exportée est celle de DATABASE_URL, donc la RDS en production.

Options :

--url : exporter une autre base ;
--name : changer le début du nom de fichier (par défaut cdd_cosomis) ;
--s3-uri : changer la destination S3 ;
--workdir : choisir le dossier temporaire (défaut /var/tmp) ;
--min-free-mb : espace libre minimal pour démarrer (défaut 500) ;
--dry-run : export sans envoi ;
--keep : garder le fichier, pour déboguer.
--zip (backup_postgres_db_sql seulement) : exporter en .sql puis le zipper
        (.sql.zip) avant l'envoi, au lieu du .sql.gz.

"""
import os
import shutil
import subprocess
import tempfile
import time
import zipfile
from datetime import datetime

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from dashboard.commands_runner.progress import report as report_progress  # menu « Commandes / sync »

DEFAULT_S3_URI = "s3://elasticbeanstalk-us-west-1-371600284712/backupsdb/cdd_cosomis/"


def _default_workdir():
    # /var/tmp est sur le disque ; /tmp est souvent un tmpfs (RAM) sous Amazon
    # Linux 2023 (cf. incident backup_couchdb du 13/11/2026, disque plein).
    return "/var/tmp" if os.path.isdir("/var/tmp") else tempfile.gettempdir()


class S3BackupCommand(BaseCommand):
    # À définir dans les sous-classes.
    export_command = None   # ex. "export_postgres_db"
    extension = None        # ex. ".zip"
    # Option --zip : extension de l'export brut, zippé ensuite en
    # <fichier><zip_suffix>. None = option non proposée.
    zip_source_extension = None   # ex. ".sql"
    zip_suffix = ".zip"

    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument(
            "--url", default=None,
            help="URL de la base à exporter (postgres://user:mdp@hote:5432/base). "
                 "Défaut : variable d'environnement DATABASE_URL.")
        parser.add_argument("--s3-uri", default=DEFAULT_S3_URI,
                            help=f"Destination S3 (défaut : {DEFAULT_S3_URI}).")
        parser.add_argument("--name", default="cdd_cosomis",
                            help="Préfixe du fichier : <name>_<AAAAMMJJHHMM>"
                                 f"{self.extension} (défaut : cdd_cosomis).")
        parser.add_argument("--workdir", default=None,
                            help="Dossier temporaire (défaut : /var/tmp, "
                                 "sinon dossier temporaire système).")
        parser.add_argument("--min-free-mb", type=int, default=500,
                            help="Refuse de démarrer si l'espace libre du "
                                 "dossier temporaire est sous ce seuil "
                                 "(défaut : 500 Mo).")
        parser.add_argument("--dry-run", action="store_true",
                            help="Exporte sans envoyer sur S3 (le fichier est "
                                 "quand même supprimé, sauf --keep).")
        parser.add_argument("--keep", action="store_true",
                            help="Débogage : ne supprime pas le fichier exporté.")
        if self.zip_source_extension:
            parser.add_argument(
                "--zip", action="store_true",
                help=f"Exporte en {self.zip_source_extension} puis le zippe "
                     f"({self.zip_source_extension}{self.zip_suffix}) avant "
                     f"l'envoi, au lieu de {self.extension}.")

    def handle(self, *args, **opts):
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
        workdir = opts["workdir"] or _default_workdir()
        os.makedirs(workdir, exist_ok=True)
        free_mb = shutil.disk_usage(workdir).free / (1024 * 1024)
        if free_mb < opts["min_free_mb"]:
            raise CommandError(
                f"Seulement {free_mb:.0f} Mo libres dans {workdir} (minimum "
                f"{opts['min_free_mb']} Mo, --min-free-mb) : export annulé.")
        self.stdout.write(f"Dossier temporaire : {workdir} ({free_mb:.0f} Mo libres)")
        use_zip = bool(opts.get("zip"))
        base = os.path.join(workdir, f"{opts['name']}_{stamp}")
        if use_zip:
            exported = base + self.zip_source_extension
            output = exported + self.zip_suffix
        else:
            exported = output = base + self.extension
        for p in {exported, output}:
            if os.path.exists(p):
                raise CommandError(f"{p} existe déjà : relancer dans une minute.")

        started = time.time()
        try:
            export_opts = {"output": exported}
            if opts["url"]:
                export_opts["url"] = opts["url"]
            report_progress(phase="Export de la base PostgreSQL")
            call_command(self.export_command, stdout=self.stdout,
                         stderr=self.stderr, **export_opts)

            if use_zip:
                report_progress(phase="Compression")
                self.stdout.write(f"Compression -> {output}")
                with zipfile.ZipFile(output + ".part", "w", zipfile.ZIP_DEFLATED,
                                     allowZip64=True) as zf:
                    zf.write(exported, os.path.basename(exported))
                os.replace(output + ".part", output)
                # Le fichier brut n'est plus utile dès que le zip existe.
                if not opts["keep"]:
                    os.remove(exported)
                self.stdout.write(
                    f"Zip : {os.path.getsize(output) / (1024 * 1024):.1f} Mo")

            if opts["dry_run"]:
                self.stdout.write(self.style.WARNING("--dry-run : pas d'envoi sur S3."))
            else:
                report_progress(phase="Envoi sur S3")
                cmd = ["aws", "s3", "cp", output, s3_uri]
                self.stdout.write("$ " + " ".join(cmd))
                res = subprocess.run(cmd)
                if res.returncode != 0:
                    raise CommandError(f"aws s3 cp a échoué (code {res.returncode}).")
                self.stdout.write(self.style.SUCCESS(
                    f"Envoyé : {s3_uri}{os.path.basename(output)} "
                    f"({time.time() - started:.0f} s)"))
        finally:
            if opts["keep"]:
                self.stdout.write(f"--keep : conservé(s) {', '.join(sorted({exported, output}))}")
            else:
                for p in {exported, exported + ".part", output, output + ".part"}:
                    if os.path.exists(p):
                        os.remove(p)
                self.stdout.write("Export supprimé du serveur.")
