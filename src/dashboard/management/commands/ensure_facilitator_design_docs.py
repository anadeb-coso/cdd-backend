"""Ajoute aux bases CouchDB des facilitateurs les documents de conception qui leur manquent.

Documents concernés (référence : base `process_design`, cf. no_sql_client.FACILITATOR_DESIGN_DOC_IDS) :
`_design/task_stats`, `_design/tasks_number`, `_design/views_docs`. Sans `_design/task_stats`, l'application
mobile n'affiche aucun CVD dans « Cycle d'investissement ».

Sans --apply : rapport seulement (rien n'est écrit). Relançable sans risque : un document déjà présent et
identique n'est pas réécrit. Un document présent mais différent de la référence est signalé (« outdated ») et
n'est remplacé qu'avec --update.

    python manage.py ensure_facilitator_design_docs                        # rapport sur toutes les bases facilitator_*
    python manage.py ensure_facilitator_design_docs --apply                # crée les documents manquants
    python manage.py ensure_facilitator_design_docs --apply --update       # + remplace ceux qui diffèrent
    python manage.py ensure_facilitator_design_docs --db facilitator_1794569576 --apply
"""
from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from no_sql_client import DESIGN_SOURCE_DB, FACILITATOR_DESIGN_DOC_IDS, NoSQLClient

DB_PREFIX = 'facilitator_'


class Command(BaseCommand):
    help = "Adds the missing design documents (task_stats, tasks_number, views_docs) to the facilitators' CouchDB databases."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write the changes (otherwise: report only).')
        parser.add_argument('--update', action='store_true',
                            help='Also replace design documents that differ from the reference version.')
        parser.add_argument('--db', action='append', help='Only this CouchDB database (repeatable).')
        parser.add_argument('--source', default=DESIGN_SOURCE_DB,
                            help=f'Database holding the reference design documents (default: {DESIGN_SOURCE_DB}).')

    def handle(self, *args, **options):
        apply, update = options['apply'], options['update']
        nsc = NoSQLClient(timeout=120)

        existing = set(nsc.get_dbs())
        if options['db']:
            names = [n.strip().lower() for n in options['db'] if n.strip()]
            unknown = [n for n in names if n not in existing]
            if unknown:
                self.stdout.write(self.style.WARNING(f"Unknown database(s), skipped: {', '.join(unknown)}"))
            names = [n for n in names if n in existing]
        else:
            names = sorted(n for n in existing if n.startswith(DB_PREFIX))

        source_docs = nsc.load_design_docs(FACILITATOR_DESIGN_DOC_IDS, options['source'])
        missing_source = [d for d in FACILITATOR_DESIGN_DOC_IDS if d not in source_docs]
        if missing_source:
            raise CommandError(f"Not found in '{options['source']}': {', '.join(missing_source)}")

        self.stdout.write(f"{'APPLY' if apply else 'DRY RUN'}{' + UPDATE' if update else ''} on {len(names)} "
                          f"database(s) - {nsc.url}")

        totals = Counter()
        dbs_touched = 0
        for name in names:
            try:
                statuses = nsc.ensure_design_docs(nsc.get_db(name), update=update, dry_run=not apply,
                                                  source_docs=source_docs)
            except Exception as exc:  # noqa: BLE001
                statuses = {d: f'error: {exc}' for d in FACILITATOR_DESIGN_DOC_IDS}
            for status in statuses.values():
                totals['error' if status.startswith('error') else status] += 1
            interesting = {d: s for d, s in statuses.items() if s != 'unchanged'}
            if interesting:
                dbs_touched += 1
                self.stdout.write(f"  {name}: " + ', '.join(f"{d.split('/', 1)[1]}={s}" for d, s in interesting.items()))

        verb = '' if apply else ' (would be)'
        self.stdout.write(self.style.SUCCESS(
            f"Done: {dbs_touched}/{len(names)} database(s) concerned; "
            f"created{verb} {totals['created']}, updated{verb} {totals['updated']}, unchanged {totals['unchanged']}, "
            f"outdated {totals['outdated']}{'' if update else ' (add --update to replace)'}, "
            f"conflicts {totals['conflict']}, errors {totals['error']}"
            + ('' if apply else ' - nothing written: add --apply')
        ))
