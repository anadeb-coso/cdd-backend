"""Marque tous les déplacements de documents programmés (ProcessAddOrRemoveADL) comme déjà exécutés.

Ces lignes n'ont jamais été exécutées (aucun exécuteur dans le code) ; elles sont périmées (villages réaffectés
depuis) et ne doivent plus l'être : les déplacements se font désormais au moment de l'enregistrement des villages
d'affectation (dashboard.diagnostics.village_docs.start_localities_moves), et l'historique se corrige depuis les
pages Diagnostics « Documents sans village » / « Villages sans documents ». Aucun document CouchDB n'est touché.

Sans --apply : aperçu, rien n'est écrit.

    python manage.py mark_process_add_or_remove_adl_executed
    python manage.py mark_process_add_or_remove_adl_executed --apply
"""
from collections import Counter

from django.core.management.base import BaseCommand

from process_manager.models import ProcessAddOrRemoveADL


class Command(BaseCommand):
    help = "Marque tous les ProcessAddOrRemoveADL non exécutés comme exécutés (aperçu sans --apply)."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help="Écrire (sinon aperçu, rien n'est écrit).")

    def handle(self, *args, **options):
        pending = ProcessAddOrRemoveADL.objects.filter(executed=False)
        total = ProcessAddOrRemoveADL.objects.count()
        count = pending.count()
        self.stdout.write(f"ProcessAddOrRemoveADL : {total} ligne(s), dont {count} non exécutée(s).")
        directions = Counter(
            'base -> sauvegarde' if move_to == 'backup_db_facilitators_docs' else 'sauvegarde -> base' if move_from == 'backup_db_facilitators_docs' else 'autre'
            for move_from, move_to in pending.values_list('move_from', 'move_to')
        )
        for direction, n in directions.most_common():
            self.stdout.write(f"  {direction} : {n}")
        first = pending.exclude(created_date=None).order_by('created_date').values_list('created_date', flat=True).first()
        if first:
            self.stdout.write(f"  plus ancienne : {first:%d/%m/%Y}")
        if not options['apply']:
            self.stdout.write(self.style.WARNING("Aperçu seulement : rien n'a été écrit (--apply pour appliquer)."))
            return
        updated = pending.update(executed=True)
        self.stdout.write(self.style.SUCCESS(f"{updated} ligne(s) marquée(s) comme exécutée(s)."))
