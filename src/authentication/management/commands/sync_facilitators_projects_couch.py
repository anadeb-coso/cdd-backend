"""Reporte dans le document CouchDB de chaque facilitateur les projets auxquels il est rattaché en base mais qui
n'y figurent pas (`projects_ids`) — cause des « Page introuvable » sur le profil dans ces projets.

Aperçu par défaut ; `--apply` pour écrire. Rien n'est retiré des documents."""
import collections

from django.core.management.base import BaseCommand

from authentication.models import Facilitator
from dashboard.facilitators.projects_sync import sync_facilitator_projects_to_couch
from no_sql_client import NoSQLClient


class Command(BaseCommand):
    help = "Ajoute aux documents CouchDB des facilitateurs les projets liés en base qui y manquent."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help="Écrire (sinon aperçu)")
        parser.add_argument('--project', type=int, help="Seulement les facilitateurs de ce projet (id)")

    def handle(self, *args, **options):
        apply = options['apply']
        nsc = NoSQLClient()
        qs = Facilitator.objects.exclude(no_sql_db_name__isnull=True).exclude(no_sql_db_name='').prefetch_related('projects')
        if options['project']:
            qs = qs.filter(projects__id=options['project'])
        per_project, errors, touched = collections.Counter(), [], 0
        for facilitator in qs.order_by('id').distinct():
            try:
                added = sync_facilitator_projects_to_couch(facilitator, apply=apply, nsc=nsc)
            except Exception as exc:
                errors.append((facilitator.pk, facilitator.no_sql_db_name, str(exc)[:120]))
                continue
            if added:
                touched += 1
                per_project.update(p.name for p in added)
                self.stdout.write(f"{facilitator.pk} {facilitator.no_sql_db_name} : + {', '.join(p.name for p in added)}")
        verb = "mis à jour" if apply else "à mettre à jour (aperçu, --apply pour écrire)"
        self.stdout.write(self.style.SUCCESS(f"{touched} facilitateur(s) {verb} ; par projet : {dict(per_project)}"))
        for e in errors:
            self.stdout.write(self.style.WARNING(f"erreur {e}"))
