"""Exporte la base PostgreSQL avec `export_postgres_db_sql` (.sql.gz), envoie le
fichier sur S3 (`aws s3 cp` vers backupsdb/cdd_cosomis/) puis le supprime du
serveur.

Le fichier est compressé en gzip (extension .sql.gz, gérée par
export_postgres_db_sql) : beaucoup plus léger à stocker et à envoyer.

Option --zip : export en .sql brut, zippé en .sql.zip avant l'envoi (le .sql
est supprimé dès que le zip est prêt) ; c'est le .sql.zip qui part sur S3.

Exemples (sur l'instance EB) :
    python manage.py backup_postgres_db_sql
    python manage.py backup_postgres_db_sql --zip
    python manage.py backup_postgres_db_sql --dry-run
Réimport : télécharger le fichier, le décompresser si .sql.zip, puis
`import_postgres_db_sql` (ou `gunzip` + `psql -f` pour le .sql.gz).
"""
from ._s3_backup import S3BackupCommand


class Command(S3BackupCommand):
    help = ("Exporte la base PostgreSQL (export_postgres_db_sql, .sql.gz), "
            "l'envoie sur S3 puis supprime le fichier du serveur.")
    export_command = "export_postgres_db_sql"
    extension = ".sql.gz"
    zip_source_extension = ".sql"
