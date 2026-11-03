"""Allège les historiques des tâches dans toutes les bases CouchDB (voir dashboard/task_history.py).

Sans --apply : rapport seulement (rien n'est écrit). Relançable sans risque : une tâche déjà propre n'est pas
réécrite. Une tâche modifiée au même moment par un téléphone (conflit de révision) est signalée et sera traitée
au passage suivant.

    python manage.py clean_task_histories                 # rapport
    python manage.py clean_task_histories --apply         # écrit
    python manage.py clean_task_histories --db facilitator_123 --apply
"""
import json

from django.core.management.base import BaseCommand

from dashboard.task_history import HISTORY_KEYS, clean_task_doc
from no_sql_client import NoSQLClient

PAGE_SIZE = 200


def _count_entries(doc):
    return sum(len(doc.get(k) or []) for k in HISTORY_KEYS if isinstance(doc.get(k), list))


class Command(BaseCommand):
    help = "Removes form_response/form_fields/attachments and empty entries from the task histories in CouchDB."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write the changes (otherwise: report only).')
        parser.add_argument('--db', action='append', help='Only this CouchDB database (repeatable).')

    def handle(self, *args, **options):
        apply = options['apply']
        nsc = NoSQLClient(timeout=120)
        names = options['db'] or [n for n in nsc.get_dbs() if not n.startswith('_')]
        self.stdout.write(f"{'APPLY' if apply else 'DRY RUN'} on {len(names)} database(s) - {nsc.url}")

        totals = {'docs': 0, 'changed': 0, 'saved': 0, 'conflicts': 0, 'errors': 0,
                  'entries_before': 0, 'entries_after': 0, 'bytes_before': 0, 'bytes_after': 0}
        for name in names:
            stats = self._clean_db(nsc, name, apply)
            for k in totals:
                totals[k] += stats.get(k, 0)
            if stats['changed'] or stats['errors']:
                self.stdout.write(
                    f"  {name}: {stats['changed']}/{stats['docs']} task(s) to clean, "
                    f"entries {stats['entries_before']} -> {stats['entries_after']}, "
                    f"{stats['bytes_before'] // 1024} -> {stats['bytes_after'] // 1024} KB"
                    + (f", saved {stats['saved']}, conflicts {stats['conflicts']}, errors {stats['errors']}" if apply else '')
                )

        self.stdout.write(self.style.SUCCESS(
            f"Done: {totals['changed']}/{totals['docs']} task(s) to clean; history entries "
            f"{totals['entries_before']} -> {totals['entries_after']}; history size "
            f"{totals['bytes_before'] // (1024 * 1024)} -> {totals['bytes_after'] // (1024 * 1024)} MB"
            + (f"; saved {totals['saved']}, conflicts {totals['conflicts']} (run again), errors {totals['errors']}"
               if apply else ' (nothing written: add --apply)')
        ))

    def _clean_db(self, nsc, name, apply):
        stats = {'docs': 0, 'changed': 0, 'saved': 0, 'conflicts': 0, 'errors': 0,
                 'entries_before': 0, 'entries_after': 0, 'bytes_before': 0, 'bytes_after': 0}
        db = nsc.get_db(name)
        selector = {'type': 'task', '$or': [{k: {'$exists': True}} for k in HISTORY_KEYS]}
        bookmark = None
        while True:
            body = {'selector': selector, 'limit': PAGE_SIZE}
            if bookmark:
                body['bookmark'] = bookmark
            try:
                resp = db.r_session.post(f"{db.database_url}/_find", json=body)
                resp.raise_for_status()
                result = resp.json()
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(f"  {name}: read error {exc}")
                stats['errors'] += 1
                return stats
            docs = result.get('docs', [])
            to_save = []
            for doc in docs:
                stats['docs'] += 1
                before = {k: doc.get(k) for k in HISTORY_KEYS if k in doc}
                entries_before = _count_entries(doc)
                if clean_task_doc(doc):
                    stats['changed'] += 1
                    stats['entries_before'] += entries_before
                    stats['entries_after'] += _count_entries(doc)
                    stats['bytes_before'] += len(json.dumps(before, default=str))
                    stats['bytes_after'] += len(json.dumps({k: doc.get(k) for k in HISTORY_KEYS if k in doc}, default=str))
                    to_save.append(doc)
            if apply and to_save:
                self._save(db, name, to_save, stats)
            bookmark = result.get('bookmark')
            if len(docs) < PAGE_SIZE or not bookmark:
                return stats

    def _save(self, db, name, docs, stats):
        try:
            resp = db.r_session.post(f"{db.database_url}/_bulk_docs", json={'docs': docs})
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            self.stderr.write(f"  {name}: write error {exc}")
            stats['errors'] += len(docs)
            return
        for row in resp.json():
            if row.get('ok'):
                stats['saved'] += 1
            elif row.get('error') == 'conflict':
                stats['conflicts'] += 1
            else:
                stats['errors'] += 1
                self.stderr.write(f"  {name}: {row.get('id')} {row.get('error')} {row.get('reason')}")
