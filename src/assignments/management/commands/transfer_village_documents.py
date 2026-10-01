"""Transfère à la CIBLE (qui garde le village siège) le travail qu'une SOURCE a fait sur ce village, puis retire
le village de la source, dans CouchDB.

Cas visé : un transfert de village dont le document facilitateur de la source n'a pas été mis à jour ; la
synchronisation des tâches a régénéré chez la source ses propres documents du village (autres `_id`), et la
source a continué à y travailler.

Seuls les documents de CE village et de CE projet sont modifiés, créés ou supprimés (phases, activités et
tâches dont `administrative_level_id` est le village et `project_id` le projet, contrôlé à nouveau juste avant
d'écrire) ; les autres villages et projets des deux facilitateurs ne sont pas touchés.

  1. Tâches : chaque tâche de la cible reçoit le travail de la même tâche de la source (même type, `sql_id` et
     cycle) : réponses, fichiers, achèvement, validation, historiques. La définition de la tâche (formulaire,
     cycles…) et ses liens (`_id`, activité, phase) restent ceux de la cible.
     CONFLIT — la tâche de la cible contient déjà du travail : la cible est gardée, on continue.
     Une phase, activité ou tâche de la source absente chez la cible y est créée (nouvel `_id`, rattachée aux
     phases/activités de la cible).
  2. Les phases, activités et tâches du village de la source sont supprimées.
  3. Le village est retiré du document facilitateur de la source ; il est ajouté à celui de la cible s'il n'y
     était pas ; les unités géographiques des documents modifiés sont recalculées (comme depuis le dashboard).
  4. Les suivis de tâches partageables (`TaskShareRecord`) de la source pointent vers les tâches de la cible.
  5. Les déplacements de documents du village encore en attente entre ces bases (ProcessAddOrRemoveADL) sont
     annulés : exécutés après coup, ils déferaient ce résultat.

Refus (rien n'est écrit) seulement si CouchDB ne peut pas être lu de façon sûre (base illisible, document
facilitateur absent ou multiple).

Ensuite, lancer `rebuild_assignments_from_couchdb` pour aligner CDD (SQL) et le SIG sur CouchDB.

Sans --apply : aperçu, rien n'est écrit.

    python manage.py transfer_village_documents --village 5844 --project PURS --from 496 --to 481
    python manage.py transfer_village_documents --village 5844 --project PURS --from 496 --to 481 --apply
"""
import uuid
from collections import Counter, defaultdict
from urllib.parse import quote

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from authentication.models import Facilitator
from dashboard.utils import sync_geographicalunits_with_cvd_on_facilittor
from process_manager.models import ProcessAddOrRemoveADL, Project, TaskShareRecord

TYPES = ["phase", "activity", "task"]
EMPTY_DATES = (None, "", "0000-00-00 00:00:00")
# Champs écrits par le travail sur une tâche : achèvement (mobile), validation (dashboard), historiques, partage.
# S'y ajoutent les champs présents chez la source mais absents de la tâche de la cible.
WORK_FIELDS = {
    "completed", "completed_date", "completed_date_moment", "form_response", "attachments", "last_updated",
    "last_updated_moment", "validated", "date_validated", "completed_history", "updated_history",
    "updated_after_invalidation", "updated_after_invalidation_history", "updated_date", "share_history", "actions_by",
}


def key(doc):
    return doc.get('type'), str(doc.get('sql_id')), doc.get('cycle_id')


class Command(BaseCommand):
    help = "Transfère à la cible le travail de la source sur un village, puis retire le village de la source (CouchDB)."

    def add_arguments(self, parser):
        parser.add_argument('--village', type=int, required=True, help="Id du village (AdministrativeLevel).")
        parser.add_argument('--project', required=True, help="Projet CDD (nom ou couch_id).")
        parser.add_argument('--from', dest='source', type=int, required=True, help="Id du facilitateur source (retiré du village).")
        parser.add_argument('--to', dest='target', type=int, required=True, help="Id du facilitateur cible (garde le village).")
        parser.add_argument('--apply', action='store_true', help="Appliquer (sinon aperçu, rien n'est écrit).")

    def handle(self, *args, **options):
        self.auth = (settings.NO_SQL_USER, settings.NO_SQL_PASS)
        self.village = options['village']
        self.project = Project.objects.filter(Q(name=options['project']) | Q(couch_id=options['project'])).first()
        if not self.project:
            raise CommandError(f"Projet inconnu : {options['project']}")
        self.source = Facilitator.objects.filter(pk=options['source']).first()
        self.target = Facilitator.objects.filter(pk=options['target']).first()
        if not self.source or not self.target or self.source.pk == self.target.pk:
            raise CommandError("Facilitateurs source et cible : deux ids existants et différents.")

        self.source_fac, self.source_docs = self.load(self.source)
        self.target_fac, self.target_docs = self.load(self.target)
        self.plan()
        self.report()
        if not options['apply']:
            self.stdout.write(self.style.WARNING("\nAperçu seulement : rien n'a été écrit (--apply pour appliquer)."))
            return
        self.apply()

    # -- lecture ------------------------------------------------------------------------------------

    def url(self, f, path=""):
        return f"{settings.NO_SQL_URL}/{f.no_sql_db_name}{path}"

    def find(self, f, selector):
        docs, bookmark = [], None
        while True:
            body = {"selector": selector, "limit": 5000}
            if bookmark:
                body["bookmark"] = bookmark
            response = requests.post(self.url(f, "/_find"), json=body, auth=self.auth, timeout=120)
            if response.status_code != 200:
                raise CommandError(f"Base {f.no_sql_db_name} : HTTP {response.status_code} {response.text[:200]}")
            page = response.json()
            docs += page.get("docs", [])
            if len(page.get("docs", [])) < 5000:
                return docs
            bookmark = page.get("bookmark")

    def load(self, f):
        """(document facilitateur, phases/activités/tâches du village pour le projet)."""
        fac_docs = self.find(f, {"type": "facilitator"})
        if len(fac_docs) != 1:
            raise CommandError(f"{f.pk} {f.name} : {len(fac_docs)} document(s) facilitateur dans {f.no_sql_db_name} : rien n'a été écrit.")
        docs = self.find(f, {
            "type": {"$in": TYPES},
            "administrative_level_id": {"$in": [str(self.village), self.village]},
            "project_id": self.project.couch_id,
        })
        return fac_docs[0], docs

    def elements(self, fac_doc):
        return [e for e in (fac_doc.get('administrative_levels') or [])
                if isinstance(e, dict) and str(e.get('id')) == str(self.village) and e.get('project_id') == self.project.couch_id]

    @staticmethod
    def uploaded(doc):
        """Pièces jointes réellement envoyées (les emplacements vides ont `attachment: null`)."""
        return [a for a in (doc.get('attachments') or []) if isinstance(a, dict) and a.get('attachment')]

    def has_work(self, doc):
        return bool(
            doc.get('completed') or doc.get('form_response') or self.uploaded(doc) or doc.get('_attachments')
            or doc.get('last_updated') not in EMPTY_DATES or doc.get('validated') is not None
        )

    def describe(self, doc):
        parts = [f"terminée le {doc.get('completed_date')}" if doc.get('completed') else "non terminée"]
        if doc.get('form_response'):
            parts.append("réponses")
        if self.uploaded(doc):
            parts.append(f"{len(self.uploaded(doc))} fichier(s)")
        if doc.get('validated') is not None:
            parts.append("validée" if doc.get('validated') else "invalidée")
        if doc.get('last_updated') not in EMPTY_DATES:
            parts.append(f"maj {doc.get('last_updated')}")
        return " ; ".join(parts)

    # -- plan (aucune écriture) ---------------------------------------------------------------------

    def plan(self):
        by_key_source, by_key_target = defaultdict(list), defaultdict(list)
        for d in self.source_docs:
            by_key_source[key(d)].append(d)
        for d in self.target_docs:
            by_key_target[key(d)].append(d)
        source_by_id = {d['_id']: d for d in self.source_docs}

        self.updates, self.copied, self.conflicts, self.kept, self.creations, self.skipped = [], [], [], [], [], []
        # correspondance des phases/activités source -> cible (existantes ou créées)
        mapping = {}

        def target_for(source_doc):
            """_id chez la cible de la phase/activité correspondant à `source_doc` (créée si absente)."""
            if source_doc is None:
                return None
            if source_doc['_id'] in mapping:
                return mapping[source_doc['_id']]
            targets = by_key_target.get(key(source_doc), [])
            if targets:
                mapping[source_doc['_id']] = targets[0]['_id']
            else:
                new = {k: v for k, v in source_doc.items() if k != '_rev'}
                new['_id'] = uuid.uuid4().hex
                if source_doc['type'] == 'activity':
                    new['phase_id'] = target_for(source_by_id.get(source_doc.get('phase_id')))
                    if new['phase_id'] is None:
                        self.skipped.append((source_doc, "phase de la source introuvable"))
                        return None
                self.creations.append(new)
                mapping[source_doc['_id']] = new['_id']
            return mapping[source_doc['_id']]

        for k, sources in sorted(by_key_source.items(), key=lambda x: str(x[0])):
            if k[0] != 'task':
                continue
            worked = [s for s in sources if self.has_work(s)]
            if len(worked) > 1:
                self.skipped.append((worked[0], f"{len(worked)} tâches travaillées de même sql_id/cycle chez la source"))
                continue
            source = worked[0] if worked else sources[0]
            targets = by_key_target.get(k, [])
            if len(targets) > 1:
                self.skipped.append((source, f"{len(targets)} tâches de même sql_id/cycle chez la cible : cible gardée"))
                continue
            if targets:
                target = targets[0]
                if not self.has_work(source):
                    if self.has_work(target):
                        self.kept.append((target, source))
                    continue
                if self.has_work(target):
                    self.conflicts.append((target, source))   # CONFLIT : la cible est gardée
                    continue
                fields = WORK_FIELDS | (set(source) - set(target))
                new = dict(target)
                for field in fields:
                    if field in source:
                        new[field] = source[field]
                    else:
                        new.pop(field, None)
                self.updates.append(new)
                self.copied.append((target, source))
            else:
                # tâche absente chez la cible : créée et rattachée aux activité/phase de la cible
                activity_id = target_for(source_by_id.get(source.get('activity_id')))
                phase_id = target_for(source_by_id.get(source.get('phase_id')))
                if activity_id is None or phase_id is None:
                    self.skipped.append((source, "activité ou phase de la source introuvable"))
                    continue
                new = {k2: v for k2, v in source.items() if k2 != '_rev'}
                new.update({'_id': uuid.uuid4().hex, 'activity_id': activity_id, 'phase_id': phase_id})
                self.creations.append(new)
                self.copied.append((None, source))

        self.add_element = not self.elements(self.target_fac)
        self.records = list(TaskShareRecord.objects.filter(
            administrative_level_id=self.village, project=self.project, facilitator=self.source))
        self.pending = [p for p in ProcessAddOrRemoveADL.objects.filter(executed=False)
                        if str(self.village) in [str(x) for x in (p.administrative_levels or [])]
                        and {p.move_from, p.move_to} & {self.source.no_sql_db_name, self.target.no_sql_db_name}]

    def report(self):
        self.stdout.write(self.style.MIGRATE_HEADING(f"Village {self.village} — projet {self.project.name}"))
        for label, f, fac_doc, docs in (("SOURCE", self.source, self.source_fac, self.source_docs),
                                        ("CIBLE", self.target, self.target_fac, self.target_docs)):
            worked = [d for d in docs if d['type'] == 'task' and self.has_work(d)]
            self.stdout.write(
                f"  {label} {f.pk} {f.name} ({f.no_sql_db_name}) : {dict(Counter(d['type'] for d in docs))} ; "
                f"{len(worked)} tâche(s) avec du travail ; village dans son document facilitateur : "
                f"{'oui' if self.elements(fac_doc) else 'non'}"
            )
        self.stdout.write(self.style.MIGRATE_HEADING("Plan"))
        self.stdout.write(f"  1. CIBLE : travail de la source copié dans {len(self.updates)} tâche(s) ; "
                          f"{len(self.creations)} document(s) créé(s)")
        for target, source in self.copied:
            self.stdout.write(f"      + {source.get('name')} (sql_id {source.get('sql_id')}) : {self.describe(source)}"
                              + ("" if target else " [tâche créée chez la cible]"))
        self.stdout.write(f"     CONFLITS, cible gardée : {len(self.conflicts)}")
        for target, source in self.conflicts:
            self.stdout.write(f"      = {target.get('name')} (sql_id {target.get('sql_id')}) : cible [{self.describe(target)}] "
                              f"/ source ignorée [{self.describe(source)}]")
        if self.kept:
            self.stdout.write(f"     travail déjà chez la cible seulement (gardé) : {len(self.kept)}")
        for doc, reason in self.skipped:
            self.stdout.write(self.style.WARNING(f"      ! non copié : {doc.get('name')} ({doc.get('_id')}) : {reason}"))
        self.stdout.write(f"  2. SOURCE : {len(self.source_docs)} document(s) du village supprimé(s)")
        self.stdout.write(f"  3. SOURCE : village retiré du document facilitateur ({len(self.elements(self.source_fac))} élément(s))"
                          + (" ; CIBLE : village ajouté à son document facilitateur" if self.add_element else ""))
        self.stdout.write(f"  4. TaskShareRecord repointés vers la cible : {len(self.records)}")
        self.stdout.write(f"  5. Déplacements en attente annulés : {len(self.pending)}"
                          + "".join(f"\n      #{p.id} {p.move_from} -> {p.move_to} {p.administrative_levels}" for p in self.pending))

    # -- écriture -----------------------------------------------------------------------------------

    def only_this_village(self, docs):
        """Garde-fou avant toute écriture : uniquement des phases/activités/tâches de CE village et de CE projet."""
        others = [d.get('_id') for d in docs
                  if str(d.get('administrative_level_id')) != str(self.village)
                  or d.get('project_id') != self.project.couch_id or d.get('type') not in TYPES]
        if others:
            raise CommandError(f"{len(others)} document(s) hors du village {self.village} / projet {self.project.name} "
                               f"dans la sélection ({others[:5]}) : rien n'a été appliqué.")

    def bulk(self, f, docs):
        if not docs:
            return [], []
        response = requests.post(self.url(f, "/_bulk_docs"), json={"docs": docs}, auth=self.auth, timeout=300)
        if response.status_code not in (200, 201):
            raise CommandError(f"{f.no_sql_db_name} : _bulk_docs HTTP {response.status_code} {response.text[:200]}")
        results = response.json()
        return [r for r in results if r.get('ok')], [r for r in results if not r.get('ok')]

    def update_facilitator_doc(self, f, fac_doc, change):
        doc = requests.get(self.url(f, f"/{quote(fac_doc['_id'], safe='')}"), auth=self.auth, timeout=60).json()
        change(doc)
        response = requests.put(self.url(f, f"/{quote(doc['_id'], safe='')}"), json=doc, auth=self.auth, timeout=60)
        if response.status_code not in (200, 201):
            raise CommandError(f"Document facilitateur {f.pk} non modifié : HTTP {response.status_code} {response.text[:200]}")
        sync_geographicalunits_with_cvd_on_facilittor(self.project.id, f.develop_mode, f.training_mode, f.no_sql_db_name)

    def apply(self):
        self.only_this_village(self.source_docs)
        self.only_this_village(self.updates + self.creations)

        # 1. cible : phases/activités créées d'abord, puis tâches créées ou complétées
        creations = sorted(self.creations, key=lambda d: TYPES.index(d['type']))
        _, failed = self.bulk(self.target, creations + self.updates)
        if failed:
            raise CommandError(f"Cible : {len(failed)} document(s) non écrit(s) ({failed[:3]}). La source n'a pas été "
                               "touchée : relancer la commande (l'aperçu tiendra compte de ce qui a été écrit).")
        self.stdout.write(self.style.SUCCESS(f"1. cible : {len(self.updates)} tâche(s) complétée(s), {len(creations)} document(s) créé(s)"))
        if self.add_element:
            element = dict(self.elements(self.source_fac)[0]) if self.elements(self.source_fac) else {
                "id": str(self.village), "project_id": self.project.couch_id, "project_name": self.project.name}
            self.update_facilitator_doc(self.target, self.target_fac,
                                        lambda doc: doc.setdefault('administrative_levels', []).append(element))
            self.stdout.write(self.style.SUCCESS("   cible : village ajouté à son document facilitateur"))

        # 2. source : suppression des documents du village
        _, failed = self.bulk(self.source, [{"_id": d['_id'], "_rev": d['_rev'], "_deleted": True} for d in self.source_docs])
        if failed:
            raise CommandError(f"Source : {len(failed)} document(s) non supprimé(s) ({failed[:3]}). La cible est à jour : relancer.")
        self.stdout.write(self.style.SUCCESS(f"2. source : {len(self.source_docs)} document(s) du village supprimé(s)"))

        # 3. source : village retiré de son document facilitateur
        if self.elements(self.source_fac):
            def remove(doc):
                doc['administrative_levels'] = [
                    e for e in (doc.get('administrative_levels') or [])
                    if not (isinstance(e, dict) and str(e.get('id')) == str(self.village) and e.get('project_id') == self.project.couch_id)
                ]
            self.update_facilitator_doc(self.source, self.source_fac, remove)
            self.stdout.write(self.style.SUCCESS("3. source : village retiré de son document facilitateur"))

        # 4. suivis des tâches partageables
        target_tasks = {(str(d.get('sql_id')), d.get('cycle_id')): d['_id']
                        for d in self.target_docs + self.creations if d['type'] == 'task'}
        for record in self.records:
            record.facilitator = self.target
            record.couch_task_id = target_tasks.get((str(record.task_id), record.cycle.couch_id if record.cycle else None), record.couch_task_id)
            record.save()
        self.stdout.write(self.style.SUCCESS(f"4. {len(self.records)} TaskShareRecord repointé(s) vers la cible"))

        # 5. déplacements en attente qui déferaient le résultat
        for process in self.pending:
            process.delete()
        self.stdout.write(self.style.SUCCESS(f"5. {len(self.pending)} déplacement(s) en attente annulé(s)"))

        _, source_after = self.load(self.source)
        _, target_after = self.load(self.target)
        worked = [d for d in target_after if d['type'] == 'task' and self.has_work(d)]
        self.stdout.write(f"\nAprès : source {dict(Counter(d['type'] for d in source_after))} ; cible "
                          f"{dict(Counter(d['type'] for d in target_after))}, {len(worked)} tâche(s) avec du travail")
        self.stdout.write(self.style.WARNING("Lancer ensuite rebuild_assignments_from_couchdb (aperçu puis --apply)."))
