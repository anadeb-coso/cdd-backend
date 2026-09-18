from django.core.management.base import BaseCommand

from authentication.functions import ensure_facilitator_user, sync_facilitator_user_projects, _unique_facilitator_email
from authentication.models import Facilitator
from no_sql_client import NoSQLClient


class Command(BaseCommand):
    help = (
        "Rattrapage : crée/relie un compte Django User (accès Web DCC limité, cf. "
        "dashboard/templates/layouts/sidebar.html) pour chaque Facilitator existant qui n'en a "
        "pas encore (Facilitator.user). En cas de collision d'email avec un User déjà existant, "
        "corrige l'email du Facilitator (suffixe numérique inséré avant le '@') en Postgres ET "
        "dans son doc CouchDB. Donne aussi à ce User accès aux mêmes projets que le Facilitator "
        "(Project.users, aligné sur Project.facilitators)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help="N'écrit rien : affiche seulement ce qui serait fait.",
        )

    def handle(self, *args, **kwargs):
        dry_run = kwargs['dry_run']
        nsc = NoSQLClient()

        facilitators = Facilitator.objects.filter(user__isnull=True).order_by('id')
        total = facilitators.count()
        created = 0
        email_fixes = []
        errors = []

        self.stdout.write(f"{total} facilitator(s) sans User associé.")
        if dry_run:
            self.stdout.write(self.style.WARNING("--dry-run : aucune écriture ne sera faite."))

        for facilitator in facilitators:
            original_email = facilitator.email
            try:
                if dry_run:
                    # Ne mute rien : on calcule juste ce que ferait ensure_facilitator_user
                    # sur une instance non sauvegardée, pour prévisualiser la collision d'email.
                    final_email = _unique_facilitator_email(facilitator)
                    if final_email != original_email:
                        email_fixes.append((facilitator.username, original_email, final_email))
                    created += 1
                    continue

                ensure_facilitator_user(facilitator)
                created += 1

                if facilitator.email != original_email:
                    email_fixes.append((facilitator.username, original_email, facilitator.email))
                    try:
                        facilitator_db = nsc.get_db(facilitator.no_sql_db_name)
                        rows = facilitator_db.get_query_result({"type": "facilitator"})[:]
                        if rows:
                            nsc.update_doc(facilitator_db, rows[0]['_id'], {"email": facilitator.email})
                        else:
                            errors.append((facilitator.username, "doc CouchDB 'facilitator' introuvable pour la mise à jour de l'email"))
                    except Exception as exc:  # noqa: BLE001
                        errors.append((facilitator.username, f"échec mise à jour CouchDB : {exc}"))
            except Exception as exc:  # noqa: BLE001
                errors.append((facilitator.username, str(exc)))

        for _f in Facilitator.objects.filter(user__isnull=False).order_by('id'):
            try:
                sync_facilitator_user_projects(_f)
            except Exception as exc:  # noqa: BLE001
                errors.append((_f.username, f"échec synchronisation projets : {exc}"))

        self.stdout.write(self.style.SUCCESS(
            f"{created}/{total} facilitator(s) {'à traiter' if dry_run else 'traités'}."
        ))
        if email_fixes:
            self.stdout.write(f"{len(email_fixes)} email(s) corrigé(s) pour collision :")
            for username, old, new in email_fixes:
                self.stdout.write(f"  - {username} : {old} -> {new}")
        if errors:
            self.stdout.write(self.style.ERROR(f"{len(errors)} erreur(s) :"))
            for username, msg in errors:
                self.stdout.write(f"  - {username} : {msg}")
