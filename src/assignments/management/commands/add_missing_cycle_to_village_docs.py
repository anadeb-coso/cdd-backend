"""Ajoute le cycle du projet (`cycle_id`, `cycle_name`) aux phases, activités et tâches CouchDB qui n'en ont pas.

Bases traitées : celles des facilitateurs (tous, ou --db / --facilitator) et la base de sauvegarde
`backup_db_facilitators_docs` (sauf --no-backup).

Choix du cycle d'un document sans cycle (projet lu dans `project_id`, à défaut `project_name`) :
  1. le projet n'a qu'un cycle : ce cycle ;
  2. sinon, le cycle de l'élément `administrative_levels` du document facilitateur pour ce village et ce projet, s'il
     n'y en a qu'un (base de facilitateur seulement) ;
  3. sinon : document NON modifié, signalé (cycle ambigu, projet inconnu ou absent).
Une phase, une activité et ses tâches d'un même village reçoivent ainsi le même cycle. Seuls `cycle_id` et
`cycle_name` sont ajoutés ; aucun autre champ n'est touché.

Sans --apply : aperçu, rien n'est écrit. Un document modifié entre la lecture et l'écriture (conflit, ex. synchro
mobile) est signalé et laissé tel quel : relancer la commande.

    python manage.py add_missing_cycle_to_village_docs
    python manage.py add_missing_cycle_to_village_docs --project COSO --apply
    python manage.py add_missing_cycle_to_village_docs --db facilitator_1670842896 --apply
"""
from collections import Counter, defaultdict

import requests
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from authentication.models import Facilitator
from dashboard.diagnostics.village_docs import BACKUP_DB, TYPES, Couch, CouchError
from process_manager.models import Cycle, Project

NO_CYCLE = [{"cycle_id": {"$exists": False}}, {"cycle_id": None}, {"cycle_id": ""}]


class Command(BaseCommand):
    help = "Ajoute le cycle du projet aux phases/activités/tâches CouchDB sans cycle (aperçu sans --apply)."

    def add_arguments(self, parser):
        parser.add_argument('--project', action='append', default=[], help="Projet CDD (nom ou couch_id) ; répétable. Défaut : tous.")
        parser.add_argument('--db', action='append', default=[], help="Base CouchDB d'un facilitateur ; répétable. Défaut : toutes.")
        parser.add_argument('--facilitator', action='append', type=int, default=[], help="Id du facilitateur ; répétable.")
        parser.add_argument('--no-backup', action='store_true', help="Ne pas traiter la base de sauvegarde.")
        parser.add_argument('--apply', action='store_true', help="Écrire (sinon aperçu, rien n'est écrit).")

    def handle(self, *args, **options):
        self.couch = Couch()
        projects = Project.objects.all()
        if options['project']:
            wanted = Q()
            for value in options['project']:
                wanted |= Q(name=value) | Q(couch_id=value)
            projects = projects.filter(wanted)
            if not projects.exists():
                raise CommandError(f"Projet inconnu : {options['project']}")
        self.projects = {p.couch_id: p for p in projects if p.couch_id}
        self.by_name = {p.name: p for p in projects}
        self.cycles = defaultdict(list)
        for cycle in Cycle.objects.filter(project__in=projects).order_by('order', 'id'):
            if cycle.couch_id:
                self.cycles[cycle.project.couch_id].append(cycle)
        self.cycle_by_couch = {c.couch_id: c for cs in self.cycles.values() for c in cs}

        dbs = self.databases(options)
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"{len(dbs)} base(s), projets : {', '.join(p.name for p in self.projects.values())}"
            + ("" if options['apply'] else " — APERÇU")))
        totals = Counter()
        for db, is_backup in dbs:
            try:
                totals += self.process(db, is_backup, options['apply'])
            except (CouchError, requests.RequestException) as exc:
                totals['bases illisibles'] += 1
                self.stderr.write(f"{db} : {exc}")
        self.stdout.write(self.style.MIGRATE_HEADING("Total"))
        for label, n in sorted(totals.items()):
            self.stdout.write(f"  {label} : {n}")
        if not options['apply']:
            self.stdout.write(self.style.WARNING("Aperçu seulement : rien n'a été écrit (--apply pour appliquer)."))

    def databases(self, options):
        qs = Facilitator.objects.exclude(no_sql_db_name__isnull=True).exclude(no_sql_db_name='')
        if options['db'] or options['facilitator']:
            qs = qs.filter(Q(no_sql_db_name__in=options['db']) | Q(pk__in=options['facilitator']))
            unknown = set(options['db']) - set(qs.values_list('no_sql_db_name', flat=True))
            if unknown:
                raise CommandError(f"Base(s) de facilitateur inconnue(s) : {sorted(unknown)}")
        dbs = [(db, False) for db in qs.order_by('id').values_list('no_sql_db_name', flat=True).distinct()]
        if not options['no_backup'] and not (options['db'] or options['facilitator']):
            dbs.append((BACKUP_DB, True))
        return dbs

    def element_cycles(self, db):
        """{(village, projet): {cycle_id}} des villages d'affectation du document facilitateur."""
        out = defaultdict(set)
        for element in self.couch.facilitator_doc(db).get('administrative_levels') or []:
            if isinstance(element, dict) and element.get('cycle_id') and element.get('project_id'):
                out[(str(element.get('id')), element['project_id'])].add(element['cycle_id'])
        return out

    def resolve(self, doc, elements):
        """(cycle, None) ou (None, raison)."""
        project = self.projects.get(doc.get('project_id')) or (None if doc.get('project_id') else self.by_name.get(doc.get('project_name')))
        if project is None:
            return None, "projet absent ou hors périmètre"
        cycles = self.cycles.get(project.couch_id) or []
        if len(cycles) == 1:
            return cycles[0], None
        if not cycles:
            return None, f"projet {project.name} sans cycle"
        candidates = [self.cycle_by_couch[c] for c in elements.get((str(doc.get('administrative_level_id')), project.couch_id), set())
                      if c in self.cycle_by_couch]
        if len(candidates) == 1:
            return candidates[0], None
        return None, f"projet {project.name} : {len(cycles)} cycles, village {doc.get('administrative_level_id')} ambigu"

    def process(self, db, is_backup, apply):
        docs = self.couch.find(db, {"type": {"$in": TYPES}, "$or": NO_CYCLE})
        if not docs:
            return Counter()
        elements = {} if is_backup else self.element_cycles(db)
        updates, skipped = [], Counter()
        per_cycle = Counter()
        for doc in docs:
            cycle, reason = self.resolve(doc, elements)
            if cycle is None:
                skipped[reason] += 1
                continue
            new = dict(doc, cycle_id=cycle.couch_id, cycle_name=cycle.name)
            if not new.get('project_id'):
                new['project_id'] = cycle.project.couch_id
            updates.append(new)
            per_cycle[f"{cycle.project.name} / {cycle.name}"] += 1
        written, conflicts = 0, []
        if apply and updates:
            ok, failed = self.couch.bulk_docs(db, updates)
            written, conflicts = len(ok), failed
        line = (f"{db} : {len(docs)} sans cycle -> {len(updates)} {'mis à jour' if apply else 'à mettre à jour'} "
                f"{dict(per_cycle)}")
        if skipped:
            line += f" ; non modifiés : {dict(skipped)}"
        self.stdout.write(line)
        if conflicts:
            self.stdout.write(self.style.WARNING(f"   {len(conflicts)} conflit(s) (modifiés entre-temps), à relancer : "
                                                 f"{[c.get('id') for c in conflicts[:5]]}"))
        result = Counter({'documents sans cycle': len(docs), 'à mettre à jour' if not apply else 'mis à jour': written if apply else len(updates)})
        for reason, n in skipped.items():
            result[f"non modifiés ({reason})"] += n
        if conflicts:
            result['conflits'] += len(conflicts)
        return result
