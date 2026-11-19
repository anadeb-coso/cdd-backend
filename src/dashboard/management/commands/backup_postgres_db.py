"""Exporte la base PostgreSQL avec `export_postgres_db` (.zip), envoie le zip sur
S3 (`aws s3 cp` vers backupsdb/cdd_cosomis/) puis le supprime du serveur.

Exemples (sur l'instance EB) :
    python manage.py backup_postgres_db
    python manage.py backup_postgres_db --dry-run
Réimport : télécharger le zip puis `import_postgres_db`.
"""
from ._s3_backup import S3BackupCommand


class Command(S3BackupCommand):
    help = ("Exporte la base PostgreSQL (export_postgres_db, .zip), l'envoie "
            "sur S3 puis supprime le fichier du serveur.")
    export_command = "export_postgres_db"
    extension = ".zip"
