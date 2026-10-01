"""Reconstruit les villages d'affectation des facilitateurs à partir de CouchDB et aligne le registre des
affectations du SIG (`AssignAdministrativeLevelToFacilitator` : affectations actuelles = lignes actives,
anciennes = lignes désactivées ; une seule ligne active par village et par projet).

Source : `administrative_levels` du document facilitateur CouchDB.

  1. Facilitateurs communautaires réels (develop_mode=False et training_mode=False) :
     - CDD : `administrative_levels` = celui de CouchDB, `administrative_levels_ids` = ses ids ;
     - SIG : une ligne ACTIVE pour chaque (village, projet) de CouchDB (sa ligne désactivée est réactivée,
       sinon une ligne est créée) ; ses lignes actives absentes de CouchDB sont désactivées (elles restent
       comme affectations anciennes).
  2. Facilitateurs communautaires de test (develop_mode ou training_mode) : leurs lignes du SIG sont supprimées.
  3. Facilitateurs techniques : villages d'affectation vidés dans CDD et dans CouchDB (avec les unités
     géographiques qui en découlent ; documents des villages sièges renvoyés vers la base de sauvegarde, comme
     lors d'un retrait depuis le dashboard) ; leurs lignes du SIG sont supprimées.

Ne sont pas tranchés (signalés, laissés tels quels dans le SIG) : un même village et projet demandé dans CouchDB
par plusieurs facilitateurs réels, ou encore actif chez un facilitateur qui n'est pas traité. Un facilitateur dont
le document CouchDB est illisible, absent ou en plusieurs exemplaires n'est pas modifié du tout.

Chaque changement des villages d'affectation dans CDD est inscrit dans l'historique des localités (trajets).

Sans --apply : plan détaillé et vérification du résultat simulé, RIEN n'est écrit.

    python manage.py rebuild_assignments_from_couchdb                    # aperçu
    python manage.py rebuild_assignments_from_couchdb --csv plan.csv     # aperçu + plan complet en CSV
    python manage.py rebuild_assignments_from_couchdb --apply --csv applique.csv
"""
import csv
from collections import Counter, defaultdict
from urllib.parse import quote

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from administrativelevels.models import AdministrativeLevel
from assignments.models import AssignAdministrativeLevelToFacilitator
from authentication.models import Facilitator
from cdd.call_objects_from_other_db import mis_objects_call
from dashboard.facilitators.localities import schedule_administrative_levels_documents_moves
from dashboard.facilitators.localities_history import facilitator_state, record_facilitator_changes
from process_manager.models import Project
from subprojects.models import Project as MisProject

REAL, TEST, TECHNICAL, UNKNOWN = "réel", "test", "technique", "inconnu"

ACTIONS = [
    ("sql", "CDD : villages d'affectation remplacés par ceux de CouchDB (ou vidés : technique)"),
    ("reactivate", "SIG : ligne désactivée du facilitateur réactivée"),
    ("create", "SIG : ligne créée"),
    ("deactivate", "SIG : ligne active absente de CouchDB désactivée (reste comme affectation ancienne)"),
    ("delete", "SIG : ligne supprimée (facilitateur de test ou technique)"),
    ("couchdb_clear", "CouchDB : villages d'affectation vidés (facilitateur technique)"),
    ("conflict", "NON TRAITÉ : même village et projet chez plusieurs facilitateurs réels dans CouchDB"),
    ("blocked", "NON TRAITÉ : village encore actif dans le SIG chez un facilitateur non traité"),
    ("unmapped", "NON TRAITÉ dans le SIG : projet de l'élément CouchDB inconnu"),
    ("skipped", "NON TRAITÉ : document facilitateur CouchDB illisible, absent ou multiple"),
    ("unknown_rows", "Information : lignes du SIG d'un facilitateur inconnu de CDD (laissées)"),
]
LABELS = dict(ACTIONS)
WRITES = ("sql", "reactivate", "create", "deactivate", "delete", "couchdb_clear")


class Command(BaseCommand):
    help = "Reconstruit les villages d'affectation (CDD) depuis CouchDB et aligne le SIG. Aperçu sans --apply."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help="Appliquer le plan (sinon aperçu, rien n'est écrit).")
        parser.add_argument('--csv', help="Écrire le plan complet dans ce fichier CSV.")
        parser.add_argument('--limit', type=int, default=25, help="Lignes de détail affichées par action (défaut 25).")

    def handle(self, *args, **options):
        self.auth = (settings.NO_SQL_USER, settings.NO_SQL_PASS)
        self.load()
        self.plan()
        self.verify()
        self.report(options['limit'])
        if options['csv']:
            self.write_csv(options['csv'])
        if not options['apply']:
            self.stdout.write(self.style.WARNING("\nAperçu seulement : rien n'a été écrit (--apply pour appliquer)."))
            return
        if not any(a['action'] in WRITES for a in self.actions):
            self.stdout.write(self.style.SUCCESS("\nRien à appliquer."))
            return
        self.apply()

    # -----------------------------------------------------------------------------------------------
    # Lecture
    # -----------------------------------------------------------------------------------------------

    def load(self):
        self.village_names = dict(mis_objects_call.get_all_objects(AdministrativeLevel).values_list('id', 'name'))
        mis_projects = dict(mis_objects_call.filter_objects(MisProject).values_list('name', 'id'))
        self.project_names = {mis_id: name for name, mis_id in mis_projects.items()}
        self.cdd_to_mis = {p.couch_id: mis_projects.get(p.name) for p in Project.objects.all()}

        self.facilitators = {f.id: f for f in Facilitator.objects.all()}
        self.category = {}
        for f in self.facilitators.values():
            if f.facilitator_type != 'community_facilitator':
                self.category[f.id] = TECHNICAL
            elif f.develop_mode or f.training_mode:
                self.category[f.id] = TEST
            else:
                self.category[f.id] = REAL

        # Documents CouchDB des facilitateurs réels et techniques : liste des éléments, ou None + raison
        self.couch, self.couch_error = {}, {}
        for f in self.facilitators.values():
            if self.category[f.id] == TEST:
                continue
            docs, error = self.facilitator_docs(f)
            if error:
                self.couch_error[f.id] = error
            else:
                self.couch[f.id] = [e for e in (docs[0].get('administrative_levels') or []) if isinstance(e, dict)]

        self.rows = [
            {'id': i, 'fid': int(fid) if str(fid).isdigit() else fid, 'village': v, 'project': p, 'activated': a, 'updated': u}
            for i, fid, v, p, a, u in mis_objects_call.filter_objects(AssignAdministrativeLevelToFacilitator).values_list(
                'id', 'facilitator_id', 'administrative_level_id', 'project_id', 'activated', 'updated_date')
        ]

    def facilitator_docs(self, f, full=False):
        if not f.no_sql_db_name:
            return None, "pas de base CouchDB"
        body = {"selector": {"type": "facilitator"}, "limit": 10}
        if not full:
            body["fields"] = ["_id", "administrative_levels"]
        try:
            response = requests.post(f"{settings.NO_SQL_URL}/{f.no_sql_db_name}/_find", json=body, auth=self.auth, timeout=60)
        except requests.RequestException as exc:
            return None, f"CouchDB injoignable ({exc})"
        if response.status_code != 200:
            return None, f"base {f.no_sql_db_name} : HTTP {response.status_code}"
        docs = response.json().get("docs", [])
        if len(docs) != 1:
            return None, f"{len(docs)} document(s) facilitateur"
        return docs, None

    # -----------------------------------------------------------------------------------------------
    # Plan (aucune écriture)
    # -----------------------------------------------------------------------------------------------

    def add(self, action, fid=None, village=None, project=None, row_id=None, detail="", data=None):
        self.actions.append({'action': action, 'fid': fid, 'village': village, 'project': project,
                             'row_id': row_id, 'detail': detail, 'data': data})

    def plan(self):
        self.actions = []
        self.desired = {}                    # facilitateur réel traité -> {(village, projet SIG)}
        wanted_by = defaultdict(set)         # (village, projet) -> facilitateurs réels qui le demandent

        for f in sorted(self.facilitators.values(), key=lambda x: x.id):
            category = self.category[f.id]
            if category == TEST:
                continue
            if f.id in self.couch_error:
                if category == REAL or f.administrative_levels or f.administrative_levels_ids:
                    self.add("skipped", f.id, detail=self.couch_error[f.id])
                if category == TECHNICAL and (f.administrative_levels or f.administrative_levels_ids):
                    self.add("sql", f.id, detail="vidé (CouchDB non lu)", data={'levels': [], 'ids': []})
                continue
            elements = self.couch[f.id]

            if category == TECHNICAL:
                if f.administrative_levels or f.administrative_levels_ids:
                    self.add("sql", f.id, detail=f"{len(f.administrative_levels or [])} élément(s) -> vidé",
                             data={'levels': [], 'ids': []})
                if elements:
                    self.add("couchdb_clear", f.id, detail=f"{len(elements)} élément(s) : {self.names(e.get('id') for e in elements)}",
                             data={'removed': elements})
                continue

            # --- facilitateur communautaire réel ---
            pairs = set()
            for e in elements:
                if not str(e.get('id')).isdigit():
                    continue
                project = self.cdd_to_mis.get(e.get('project_id'))
                if project is None:
                    self.add("unmapped", f.id, int(e['id']), None, detail=f"projet CouchDB {e.get('project_name') or e.get('project_id')!r}")
                    continue
                pairs.add((int(e['id']), project))
            self.desired[f.id] = pairs
            for pair in pairs:
                wanted_by[pair].add(f.id)

            new_ids = [int(e['id']) for e in elements if str(e.get('id')).isdigit()]
            if (f.administrative_levels or []) != elements or (f.administrative_levels_ids or []) != new_ids:
                detail = (f"{len(f.administrative_levels or [])} -> {len(elements)} élément(s) ; "
                          + self.difference(f.administrative_levels or [], elements, f.administrative_levels_ids or [], new_ids))
                self.add("sql", f.id, detail=detail, data={'levels': elements, 'ids': new_ids})

        # --- SIG : suppressions, désactivations, lignes gardées actives ---
        self.final_active = defaultdict(set)
        rows_by_key = defaultdict(list)
        unknown = Counter()
        for row in self.rows:
            rows_by_key[(row['fid'], row['village'], row['project'])].append(row)
            category = self.category.get(row['fid'], UNKNOWN)
            if category in (TEST, TECHNICAL):
                self.add("delete", row['fid'], row['village'], row['project'], row['id'],
                         detail=f"{category}, ligne {'active' if row['activated'] else 'désactivée'}")
            elif (category == REAL and row['fid'] in self.desired and row['activated']
                  and (row['village'], row['project']) not in self.desired[row['fid']]):
                self.add("deactivate", row['fid'], row['village'], row['project'], row['id'], data={'expected': True})
            elif row['activated']:
                self.final_active[(row['village'], row['project'])].add(row['fid'])
            if category == UNKNOWN:
                unknown[row['fid']] += 1
        for fid, count in unknown.items():
            self.add("unknown_rows", fid, detail=f"{count} ligne(s)")

        # --- SIG : activations ---
        for fid in sorted(self.desired):
            for village, project in sorted(self.desired[fid]):
                if fid in self.final_active[(village, project)]:
                    continue
                if len(wanted_by[(village, project)]) > 1:
                    others = sorted(wanted_by[(village, project)] - {fid})
                    holders = sorted(self.final_active[(village, project)])
                    self.add("conflict", fid, village, project,
                             detail=f"aussi dans CouchDB chez {', '.join(self.who(o) for o in others)} ; actif dans le SIG chez "
                                    f"{', '.join(self.who(h) for h in holders) or 'personne'}")
                    continue
                holders = self.final_active[(village, project)] - {fid}
                if holders:
                    self.add("blocked", fid, village, project, detail="actif chez " + ", ".join(
                        f"{self.who(h)} ({self.category.get(h, UNKNOWN)}{', CouchDB non lu' if h in self.couch_error else ''})" for h in sorted(holders, key=str)))
                    continue
                inactive = sorted(rows_by_key[(fid, village, project)], key=lambda r: (r['updated'] is not None, r['updated'], r['id']))
                inactive = [r for r in inactive if not r['activated']]
                if inactive:
                    row = inactive[-1]
                    self.add("reactivate", fid, village, project, row['id'],
                             detail=f"désactivée le {row['updated']:%d/%m/%Y %H:%M}" if row['updated'] else "", data={'expected': False})
                else:
                    self.add("create", fid, village, project)
                self.final_active[(village, project)].add(fid)

    def verify(self):
        """Contrôle du résultat simulé : règles respectées, sauf les cas signalés non traités."""
        self.remaining = Counter()
        for (village, project), fids in self.final_active.items():
            if len(fids) > 1:
                self.remaining["plusieurs lignes actives pour un village et projet"] += 1
            for fid in fids:
                category = self.category.get(fid, UNKNOWN)
                if category in (TEST, TECHNICAL):
                    self.remaining["ligne active d'un facilitateur de test ou technique"] += 1
                elif fid in self.desired and (village, project) not in self.desired[fid]:
                    self.remaining["ligne active absente de CouchDB"] += 1
        for fid, pairs in self.desired.items():
            for pair in pairs:
                if fid not in self.final_active[pair]:
                    self.remaining["village CouchDB sans ligne active (conflit/bloqué)"] += 1

    # -----------------------------------------------------------------------------------------------
    # Application
    # -----------------------------------------------------------------------------------------------

    def apply(self):
        model = AssignAdministrativeLevelToFacilitator
        by_action = defaultdict(list)
        for a in self.actions:
            by_action[a['action']].append(a)

        with transaction.atomic(using='mis'), transaction.atomic():
            # SIG
            ids = [a['row_id'] for a in by_action['delete']]
            if ids:
                model.objects.using('mis').filter(id__in=ids).delete()
            for a in by_action['deactivate'] + by_action['reactivate']:
                row = model.objects.using('mis').select_for_update().get(id=a['row_id'])
                if row.activated != a['data']['expected']:
                    raise CommandError(f"La ligne SIG {row.id} a changé depuis la lecture : rien n'a été appliqué, relancer.")
                row.activated = not row.activated
                row.save(using='mis')
            for a in by_action['create']:
                if model.objects.using('mis').filter(administrative_level_id=a['village'], project_id=a['project'], activated=True).exists():
                    raise CommandError(f"Village {a['village']} / projet {a['project']} activé entre-temps : rien n'a été appliqué, relancer.")
                row = model(administrative_level_id=a['village'], facilitator_id=a['fid'], project_id=a['project'])
                row.save(using='mis')
            # CDD (SQL) + historique
            for a in by_action['sql']:
                f = Facilitator.objects.select_for_update().get(pk=a['fid'])
                before = facilitator_state(f)
                f.administrative_levels = a['data']['levels']
                f.administrative_levels_ids = a['data']['ids']
                f.simple_save()
                record_facilitator_changes(f, before, 'couchdb_rebuild', sections=['assignment'],
                                           changed_by_label="rebuild_assignments_from_couchdb")
        self.stdout.write(self.style.SUCCESS(
            f"\nSIG et CDD appliqués : {len(by_action['delete'])} suppression(s), {len(by_action['deactivate'])} désactivation(s), "
            f"{len(by_action['reactivate'])} réactivation(s), {len(by_action['create'])} création(s), {len(by_action['sql'])} facilitateur(s) CDD."
        ))

        # CouchDB (facilitateurs techniques), après validation du SIG et de CDD
        for a in by_action['couchdb_clear']:
            f = self.facilitators[a['fid']]
            docs, error = self.facilitator_docs(f, full=True)
            if error:
                self.stderr.write(f"CouchDB non modifié pour {self.who(f.id)} : {error}")
                continue
            doc = dict(docs[0], administrative_levels=[], geographical_units=[])
            response = requests.put(f"{settings.NO_SQL_URL}/{f.no_sql_db_name}/{quote(doc['_id'], safe='')}",
                                    json=doc, auth=self.auth, timeout=60)
            if response.status_code not in (200, 201):
                self.stderr.write(f"CouchDB non modifié pour {self.who(f.id)} : HTTP {response.status_code} {response.text[:200]}")
                continue
            schedule_administrative_levels_documents_moves(f.no_sql_db_name, [], a['data']['removed'])
            self.stdout.write(f"CouchDB vidé : {self.who(f.id)}")

    # -----------------------------------------------------------------------------------------------
    # Affichage
    # -----------------------------------------------------------------------------------------------

    def who(self, fid):
        f = self.facilitators.get(fid)
        return f"{fid} {f.name}" if f else f"{fid} (inconnu)"

    def names(self, ids, limit=12):
        labels = [f"{self.village_names.get(int(i), i)} ({i})" for i in ids if str(i).isdigit()]
        return ", ".join(labels[:limit]) + (f" … (+{len(labels) - limit})" if len(labels) > limit else "")

    def difference(self, old, new, old_ids, new_ids):
        """Ce qui change entre les éléments CDD actuels (`old`) et ceux de CouchDB (`new`)."""
        def key(e):
            return (str(e.get('id')), e.get('project_id'), e.get('cycle_id'))

        def label(k):
            project = self.project_names.get(self.cdd_to_mis.get(k[1]), k[1])
            return f"{self.village_names.get(int(k[0]), k[0]) if k[0].isdigit() else k[0]} [{project}]"

        old_keys, new_keys = Counter(map(key, old)), Counter(map(key, new))
        parts = []
        added, removed = list((new_keys - old_keys).elements()), list((old_keys - new_keys).elements())
        if added:
            parts.append(f"+ {len(added)} : " + ", ".join(label(k) for k in sorted(added)[:10]) + (" …" if len(added) > 10 else ""))
        if removed:
            parts.append(f"- {len(removed)} : " + ", ".join(label(k) for k in sorted(removed)[:10]) + (" …" if len(removed) > 10 else ""))
        if not parts:
            old_by_key = defaultdict(list)
            for e in old:
                old_by_key[key(e)].append(e)
            fields = set()
            for e in new:
                candidates = old_by_key.get(key(e)) or []
                if candidates and e not in candidates:
                    fields |= {k for k in set(e) | set(candidates[0]) if e.get(k) != candidates[0].get(k)}
            if fields:
                parts.append("mêmes villages, champs différents : " + ", ".join(sorted(fields)))
            elif old != new:
                parts.append("ordre des éléments seulement")
            elif old_ids != new_ids:
                parts.append("administrative_levels_ids seulement")
        return " ; ".join(parts)

    def line(self, a):
        f = self.facilitators.get(a['fid'])
        parts = [self.who(a['fid']) + (" (inactif)" if f and not f.active else "")]
        if a['project'] is not None:
            parts.append(self.project_names.get(a['project'], a['project']))
        if a['village'] is not None:
            parts.append(f"{self.village_names.get(a['village'], '')} ({a['village']})")
        if a['row_id']:
            parts.append(f"ligne {a['row_id']}")
        if a['detail']:
            parts.append(a['detail'])
        return " | ".join(str(p) for p in parts)

    def report(self, limit):
        counts = Counter(a['action'] for a in self.actions)
        people = defaultdict(set)
        for a in self.actions:
            people[a['action']].add(a['fid'])
        real = [f for f in self.facilitators.values() if self.category[f.id] == REAL]
        self.stdout.write(self.style.MIGRATE_HEADING("Facilitateurs"))
        self.stdout.write(f"  réels : {len(real)} (dont {sum(1 for f in real if not f.active)} inactifs) ; "
                          f"test : {sum(1 for c in self.category.values() if c == TEST)} ; "
                          f"techniques : {sum(1 for c in self.category.values() if c == TECHNICAL)} ; "
                          f"lignes SIG : {len(self.rows)} ({sum(1 for r in self.rows if r['activated'])} actives)")
        self.stdout.write(self.style.MIGRATE_HEADING("Plan"))
        for action, label in ACTIONS:
            self.stdout.write(f"  {counts.get(action, 0):>5} ({len(people[action]):>3} fac.)  {label}")
        for action, label in ACTIONS:
            items = [a for a in self.actions if a['action'] == action]
            if not items or limit <= 0:
                continue
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n{label} ({len(items)})"))
            for a in items[:limit]:
                self.stdout.write("  " + self.line(a))
            if len(items) > limit:
                self.stdout.write(f"  … {len(items) - limit} autre(s) (voir --csv)")
        self.stdout.write(self.style.MIGRATE_HEADING("\nRésultat simulé après application"))
        if not self.remaining:
            self.stdout.write("  toutes les règles sont respectées")
        for key, value in self.remaining.items():
            self.stdout.write(f"  {value} : {key}")

    def write_csv(self, path):
        with open(path, 'w', newline='', encoding='utf-8-sig') as out:
            writer = csv.writer(out, delimiter=';')
            writer.writerow(["action", "libellé", "facilitateur_id", "facilitateur", "catégorie", "facilitateur actif",
                             "projet", "village_id", "village", "ligne SIG", "détail"])
            for a in self.actions:
                f = self.facilitators.get(a['fid'])
                writer.writerow([
                    a['action'], LABELS[a['action']], a['fid'], f.name if f else "", self.category.get(a['fid'], UNKNOWN),
                    ("oui" if f.active else "non") if f else "", self.project_names.get(a['project'], a['project'] or ""),
                    a['village'] or "", self.village_names.get(a['village'], "") if a['village'] else "", a['row_id'] or "", a['detail'],
                ])
        self.stdout.write(f"\nCSV : {path} ({len(self.actions)} lignes)")
