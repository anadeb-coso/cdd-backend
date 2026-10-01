"""Contrôle en LECTURE SEULE de la cohérence entre les villages d'affectation des facilitateurs
(`Facilitator.administrative_levels`/`administrative_levels_ids` dans CDD, `administrative_levels` du
document facilitateur CouchDB) et le registre des affectations du SIG
(`AssignAdministrativeLevelToFacilitator`), par projet.

Règles contrôlées (facilitateurs communautaires RÉELS = develop_mode=False et training_mode=False) :
  - le SIG répertorie les affectations actuelles (lignes actives) et anciennes (désactivées) des
    facilitateurs communautaires réels ; les comptes de test et les facilitateurs techniques n'y ont aucune ligne ;
  - un village d'affectation d'un facilitateur communautaire réel dans CDD a une ligne ACTIVE du SIG pour ce
    facilitateur et ce projet, et inversement ;
  - un village n'a qu'une ligne active par projet ;
  - un facilitateur technique n'a ni village d'affectation ni document de village (tâches, activités,
    phases) dans sa base CouchDB.

    python manage.py check_assignments                         # résumé + détail
    python manage.py check_assignments --csv controle.csv      # + toutes les lignes dans un CSV
    python manage.py check_assignments --no-couchdb            # sans lire CouchDB
"""
import csv
from collections import Counter, defaultdict

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from administrativelevels.models import AdministrativeLevel
from assignments.models import AssignAdministrativeLevelToFacilitator
from authentication.models import Facilitator
from cdd.call_objects_from_other_db import mis_objects_call
from process_manager.models import Project
from subprojects.models import Project as MisProject

CATEGORIES = [
    ("A", "Désactivation suspecte : village encore affecté dans CDD, ligne SIG du facilitateur désactivée"),
    ("B1", "Affecté dans CDD, aucune ligne SIG pour ce facilitateur ; village actif chez un autre dans le SIG"),
    ("B2", "Affecté dans CDD, aucune ligne SIG pour ce facilitateur ; village libre dans le SIG"),
    ("C", "Actif dans le SIG, absent des villages d'affectation CDD du facilitateur"),
    ("D", "Plusieurs lignes actives pour un même village et projet"),
    ("E", "Ligne du SIG (active ou non) d'un compte de test, d'un facilitateur technique ou inconnu"),
    ("F", "Même village et projet chez plusieurs facilitateurs communautaires réels dans CDD"),
    ("G", "Écart entre CDD (SQL) et CouchDB sur les villages d'affectation"),
    ("H", "Écart entre administrative_levels et administrative_levels_ids (CDD)"),
    ("I", "Facilitateur technique avec des villages d'affectation dans CDD ou CouchDB"),
    ("J", "Facilitateur technique : documents de village (tâches, activités, phases) dans sa base CouchDB"),
]
VILLAGE_DOC_TYPES = ["task", "activity", "phase"]
LABELS = dict(CATEGORIES)


class Command(BaseCommand):
    help = "Contrôle (lecture seule) des affectations CDD / CouchDB / SIG par projet."

    def add_arguments(self, parser):
        parser.add_argument('--csv', help="Écrire toutes les lignes dans ce fichier CSV.")
        parser.add_argument('--no-couchdb', action='store_true', help="Ne pas comparer avec CouchDB.")
        parser.add_argument('--limit', type=int, default=40, help="Lignes de détail affichées par catégorie (défaut 40).")

    def handle(self, *args, **options):
        self.rows = []
        self.villages = dict(mis_objects_call.get_all_objects(AdministrativeLevel).values_list('id', 'name'))
        mis_projects = dict(mis_objects_call.filter_objects(MisProject).values_list('name', 'id'))
        self.project_names = {mis_id: name for name, mis_id in mis_projects.items()}
        # projet CDD (couch_id) -> projet du SIG (même nom)
        cdd_to_mis = {p.couch_id: mis_projects.get(p.name) for p in Project.objects.all()}

        facilitators = {f.id: f for f in Facilitator.objects.all()}
        # communautaires réels : les seuls concernés par le SIG et par la cohérence CDD / CouchDB
        community = {i for i, f in facilitators.items()
                     if f.facilitator_type == 'community_facilitator' and not f.develop_mode and not f.training_mode}
        self.community = community

        # --- CDD : (facilitateur, village, projet SIG) -----------------------------------------
        cdd = defaultdict(set)            # (village, projet) -> facilitateurs
        cdd_by_facilitator = defaultdict(set)
        for f in facilitators.values():
            pairs = set()
            for elt in f.administrative_levels or []:
                project = cdd_to_mis.get(elt.get('project_id'))
                if str(elt.get('id')).isdigit() and project:
                    pairs.add((int(elt['id']), project))
            cdd_by_facilitator[f.id] = pairs
            if f.id in community:
                for pair in pairs:
                    cdd[pair].add(f.id)
            elif f.facilitator_type != 'community_facilitator' and (f.administrative_levels or f.administrative_levels_ids):
                self.add("I", f, None, None, f"CDD : {len(f.administrative_levels or [])} élément(s)")
            ids = {int(i) for i in (f.administrative_levels_ids or []) if str(i).isdigit()}
            elements = {int(e['id']) for e in (f.administrative_levels or []) if str(e.get('id')).isdigit()}
            if f.id in community and ids != elements:
                self.add("H", f, None, None, f"ids sans élément : {sorted(ids - elements)} ; éléments sans id : {sorted(elements - ids)}")

        # --- SIG ------------------------------------------------------------------------------------
        active = defaultdict(list)        # (village, projet) -> [facilitator_id]
        inactive = defaultdict(list)      # (facilitateur, village, projet) -> [date de désactivation]
        rows_by_facilitator = defaultdict(set)
        for facilitator_id, village_id, project_id, activated, updated in mis_objects_call.filter_objects(
            AssignAdministrativeLevelToFacilitator
        ).values_list('facilitator_id', 'administrative_level_id', 'project_id', 'activated', 'updated_date'):
            fid = int(facilitator_id) if str(facilitator_id).isdigit() else facilitator_id
            rows_by_facilitator[(fid, village_id, project_id)].add(activated)
            if activated:
                active[(village_id, project_id)].append(fid)
            else:
                inactive[(fid, village_id, project_id)].append(updated)

        # E : lignes (actives ou non) des comptes de test, techniques ou inconnus
        for (fid, village_id, project_id), states in rows_by_facilitator.items():
            if fid not in community:
                f = facilitators.get(fid)
                kind = "facilitateur inconnu" if f is None else (
                    "compte de test" if f.facilitator_type == 'community_facilitator' else f"type {f.facilitator_type}")
                self.add("E", f, village_id, project_id, f"{kind} ; ligne {'active' if True in states else 'désactivée'}", fid=fid)
        # C, D : lignes actives
        for (village_id, project_id), fids in active.items():
            if len(fids) > 1:
                self.add("D", None, village_id, project_id, "facilitateurs : " + ", ".join(self.who(i) for i in fids))
            for fid in fids:
                if fid in community and (village_id, project_id) not in cdd_by_facilitator[fid]:
                    self.add("C", facilitators[fid], village_id, project_id, "")

        # A, B : villages d'affectation CDD des facilitateurs communautaires
        for (village_id, project_id), fids in cdd.items():
            if len(fids) > 1:
                self.add("F", None, village_id, project_id, "facilitateurs : " + ", ".join(self.who(i) for i in sorted(fids)))
            holders = active.get((village_id, project_id), [])
            for fid in fids:
                if fid in holders:
                    continue
                others_cdd = sorted(fids - {fid})
                context = (f"actif dans le SIG chez : {', '.join(self.who(h) for h in holders) or 'personne'}"
                           f" ; aussi dans CDD chez : {', '.join(self.who(o) for o in others_cdd) or 'personne'}")
                if (fid, village_id, project_id) in inactive:
                    last = max(d for d in inactive[(fid, village_id, project_id)] if d) if any(inactive[(fid, village_id, project_id)]) else None
                    self.add("A", facilitators[fid], village_id, project_id,
                             f"désactivée le {last:%d/%m/%Y %H:%M} ; {context}" if last else context)
                else:
                    self.add("B1" if holders else "B2", facilitators[fid], village_id, project_id, context)

        # G, J : CouchDB
        if not options['no_couchdb']:
            self.check_couchdb(facilitators, cdd_to_mis, cdd_by_facilitator)
            self.check_technical_documents(facilitators, cdd_to_mis)

        self.report(options['limit'])
        if options['csv']:
            with open(options['csv'], 'w', newline='', encoding='utf-8-sig') as out:
                writer = csv.writer(out, delimiter=';')
                writer.writerow(["catégorie", "libellé", "projet", "village_id", "village", "facilitateur_id", "facilitateur",
                                 "type", "facilitateur actif", "détail"])
                for row in self.rows:
                    writer.writerow([row['cat'], LABELS[row['cat']], row['project'], row['village_id'], row['village'],
                                     row['fid'], row['name'], row['type'], row['active'], row['detail']])
            self.stdout.write(f"CSV : {options['csv']} ({len(self.rows)} lignes)")

    # -- helpers ------------------------------------------------------------------------------------

    def who(self, fid):
        f = Facilitator.objects.filter(pk=fid).only('name').first() if isinstance(fid, int) else None
        return f"{fid} ({f.name})" if f else str(fid)

    def add(self, cat, facilitator, village_id, project_id, detail, fid=None):
        self.rows.append({
            'cat': cat,
            'project': self.project_names.get(project_id, project_id or ""),
            'village_id': village_id or "",
            'village': self.villages.get(village_id, "") if village_id else "",
            'fid': facilitator.id if facilitator else (fid or ""),
            'name': facilitator.name if facilitator else "",
            'type': facilitator.facilitator_type if facilitator else "",
            'active': ("oui" if facilitator.active else "non") if facilitator else "",
            'detail': detail,
        })

    def check_couchdb(self, facilitators, cdd_to_mis, cdd_by_facilitator):
        auth = (settings.NO_SQL_USER, settings.NO_SQL_PASS)
        self.couch_villages = {}          # facilitateur -> villages d'affectation du document CouchDB
        for f in facilitators.values():
            is_technical = f.facilitator_type != 'community_facilitator'
            if not f.no_sql_db_name or (f.id not in self.community and not is_technical):
                continue
            try:
                response = requests.post(
                    f"{settings.NO_SQL_URL}/{f.no_sql_db_name}/_find", auth=auth, timeout=30,
                    json={"selector": {"type": "facilitator"}, "fields": ["_id", "administrative_levels"], "limit": 10},
                )
            except requests.RequestException as exc:
                self.add("G", f, None, None, f"CouchDB injoignable : {exc}")
                continue
            if response.status_code != 200:
                self.add("G", f, None, None, f"base CouchDB {f.no_sql_db_name} : HTTP {response.status_code}")
                continue
            docs = response.json().get("docs", [])
            if len(docs) != 1:
                self.add("G", f, None, None, f"{len(docs)} document(s) facilitateur dans CouchDB")
                if not docs:
                    continue
            couch = {
                (int(e['id']), cdd_to_mis.get(e.get('project_id')))
                for doc in docs for e in (doc.get("administrative_levels") or [])
                if isinstance(e, dict) and str(e.get('id')).isdigit() and cdd_to_mis.get(e.get('project_id'))
            }
            self.couch_villages[f.id] = {
                int(e['id']) for doc in docs for e in (doc.get("administrative_levels") or [])
                if isinstance(e, dict) and str(e.get('id')).isdigit()
            }
            if is_technical:
                if self.couch_villages[f.id]:
                    self.add("I", f, None, None, f"CouchDB : {len(self.couch_villages[f.id])} village(s)")
                continue
            sql = cdd_by_facilitator[f.id]
            for village_id, project_id in sorted(sql - couch):
                self.add("G", f, village_id, project_id, "dans CDD (SQL), absent de CouchDB")
            for village_id, project_id in sorted(couch - sql):
                self.add("G", f, village_id, project_id, "dans CouchDB, absent de CDD (SQL)")

    def check_technical_documents(self, facilitators, cdd_to_mis):
        """J : tâches/activités/phases rattachées à un village dans la base CouchDB d'un facilitateur
        technique. Si le village n'est pas (ou plus) dans ses villages d'affectation, le renvoi vers la base de
        sauvegarde (retrait depuis le dashboard ou rebuild_assignments_from_couchdb) ne les déplacera pas."""
        for f in facilitators.values():
            if f.facilitator_type == 'community_facilitator' or not f.no_sql_db_name:
                continue
            try:
                docs = self.find_all(f.no_sql_db_name, {"type": {"$in": VILLAGE_DOC_TYPES}},
                                     ["type", "administrative_level_id", "project_id"])
            except requests.RequestException as exc:
                self.add("J", f, None, None, f"base CouchDB non lue : {exc}")
                continue
            by_village = defaultdict(Counter)
            for doc in docs:
                village = doc.get('administrative_level_id')
                village = int(village) if str(village).isdigit() else village
                by_village[(village, cdd_to_mis.get(doc.get('project_id'), doc.get('project_id')))][doc.get('type')] += 1
            assigned = self.couch_villages.get(f.id, set())
            for (village, project), counter in sorted(by_village.items(), key=lambda x: (str(x[0][1]), str(x[0][0]))):
                counts = ", ".join(f"{counter[t]} {t}" for t in VILLAGE_DOC_TYPES if counter[t])
                where = ("village d'affectation" if village in assigned
                         else "hors villages d'affectation : non déplacés par le renvoi vers la sauvegarde")
                self.add("J", f, village if isinstance(village, int) else None, project,
                         f"{counts} ; {where}" + ("" if isinstance(village, int) else f" ; administrative_level_id={village!r}"))

    @staticmethod
    def find_all(db_name, selector, fields):
        """Tous les documents d'une requête Mango, page par page (signet)."""
        auth = (settings.NO_SQL_USER, settings.NO_SQL_PASS)
        docs, bookmark = [], None
        while True:
            body = {"selector": selector, "fields": fields, "limit": 5000}
            if bookmark:
                body["bookmark"] = bookmark
            response = requests.post(f"{settings.NO_SQL_URL}/{db_name}/_find", json=body, auth=auth, timeout=120)
            response.raise_for_status()
            page = response.json()
            docs += page.get("docs", [])
            if len(page.get("docs", [])) < 5000:
                return docs
            bookmark = page.get("bookmark")

    def report(self, limit):
        counts = Counter(row['cat'] for row in self.rows)
        self.stdout.write(self.style.MIGRATE_HEADING("Résumé"))
        for cat, label in CATEGORIES:
            self.stdout.write(f"  {cat:>2} : {counts.get(cat, 0):>4}  {label}")
        for cat, label in CATEGORIES:
            rows = [row for row in self.rows if row['cat'] == cat]
            if not rows:
                continue
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n{cat} — {label} ({len(rows)})"))
            for row in sorted(rows, key=lambda r: (str(r['project']), str(r['name']), str(r['village'])))[:limit]:
                self.stdout.write(
                    f"  [{row['project']}] {row['village']} ({row['village_id']}) | {row['fid']} {row['name']}"
                    f"{'' if row['active'] != 'non' else ' (inactif)'} | {row['detail']}"
                )
            if len(rows) > limit:
                self.stdout.write(f"  … {len(rows) - limit} autre(s) (voir --csv)")
