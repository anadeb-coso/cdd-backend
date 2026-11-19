"""Recopie dans PostgreSQL (`Facilitator.administrative_levels` / `administrative_levels_ids`) les villages
d'affectation du document facilitateur CouchDB, quand la copie diffère.

Pourquoi : la fenêtre « Synchroniser cette tâche » lit cette copie par défaut ; des comptes (notamment de formation,
créés par `create_training_facilitators`) n'avaient leurs villages que dans CouchDB.

Copie seulement : aucune affectation du SIG (`AssignAdministrativeLevelToFacilitator`) n'est créée ni modifiée.
Aperçu par défaut ; `--apply` pour écrire.

    python manage.py sync_facilitators_levels_from_couch                 # aperçu
    python manage.py sync_facilitators_levels_from_couch --apply
    python manage.py sync_facilitators_levels_from_couch --training-only --apply
"""
import collections

from django.core.management.base import BaseCommand

from authentication.models import Facilitator
from no_sql_client import NoSQLClient


def _ids(levels):
    return sorted({str(x.get('id')) for x in (levels or []) if isinstance(x, dict) and x.get('id') not in (None, '')})


def _keys(levels):
    """(village, projet, cycle, siège) de chaque élément : ce que lit la fenêtre de synchronisation."""
    return sorted((str(x.get('id')), x.get('project_id') or '', x.get('cycle_id') or '', bool(x.get('is_headquarters_village')))
                  for x in (levels or []) if isinstance(x, dict))


class Command(BaseCommand):
    help = "Recopie dans PostgreSQL les villages d'affectation CouchDB des facilitateurs quand la copie diffère."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Écrire (sinon aperçu).')
        parser.add_argument('--training-only', action='store_true', help='Seulement les comptes de formation / développement.')

    def handle(self, *args, **opts):
        nsc = NoSQLClient()
        qs = Facilitator.objects.exclude(no_sql_db_name__isnull=True).exclude(no_sql_db_name='').order_by('id')
        if opts['training_only']:
            qs = qs.filter(training_mode=True) | qs.filter(develop_mode=True)
        kinds, errors, changed = collections.Counter(), [], 0
        for f in qs:
            try:
                docs = nsc.get_db(f.no_sql_db_name).get_query_result({'type': 'facilitator'})[:]
            except Exception as exc:  # noqa: BLE001 - base absente ou injoignable : copie laissée telle quelle
                errors.append((f.pk, f.no_sql_db_name, str(exc)[:80]))
                continue
            if not docs:
                continue
            couch = [x for x in (docs[0].get('administrative_levels') or []) if isinstance(x, dict)]
            # ensembles : un village présent sous deux projets / cycles apparaît deux fois dans administrative_levels_ids
            couch_ids = {int(i) for i in _ids(couch) if i.isdigit()}
            pg_ids = {int(i) for i in (f.administrative_levels_ids or []) if str(i).isdigit()}
            # et les éléments eux-mêmes : même village sous plusieurs projets / cycles, ou drapeau siège différent
            if _ids(couch) == _ids(f.administrative_levels) and couch_ids == pg_ids \
                    and _keys(couch) == _keys(f.administrative_levels):
                continue
            changed += 1
            kind = 'développement' if f.develop_mode else 'formation' if f.training_mode else 'réel'
            kinds[kind] += 1
            self.stdout.write(f"{f.pk} {f.username} ({kind}) {f.no_sql_db_name} : PostgreSQL {_ids(f.administrative_levels)}"
                              f" -> CouchDB {_ids(couch)}")
            if opts['apply']:
                Facilitator.objects.filter(pk=f.pk).update(
                    administrative_levels=couch,
                    # même convention que le reste du code : un id par élément, dans l'ordre
                    administrative_levels_ids=[int(x['id']) for x in couch if str(x.get('id')).isdigit()],
                )
        verb = 'mis à jour' if opts['apply'] else 'à mettre à jour (aperçu, --apply pour écrire)'
        self.stdout.write(self.style.SUCCESS(f"{changed} facilitateur(s) {verb} ; par type : {dict(kinds)}"))
        for e in errors:
            self.stdout.write(self.style.WARNING(f"base illisible {e}"))
