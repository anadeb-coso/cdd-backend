"""Remet d'aplomb les données partagées entre villages sièges qui ont traversé les types de compte (14/11/2026).

Règle : le partage (copie à la validation, bouton mobile « Charger les données ») ne se fait qu'entre comptes du MÊME
type — (training_mode, develop_mode) identiques. Avant ce correctif, le registre TaskShareRecord ne distinguait pas
les comptes de formation / démonstration des vrais FC travaillant sur les mêmes villages : une même ligne pouvait
porter les VALEURS d'un vrai FC (écrites à la validation de sa tâche) et le NOM d'un compte de formation (écrit par le
dernier achèvement mobile). D'où deux sortes d'anomalies :
  - historique « Données chargées depuis une autre tâche » au mauvais nom (valeurs d'un vrai FC affichées
    « Training1 ») ;
  - valeurs réellement venues d'un compte d'un autre type.

On ne se fie donc PAS au nom inscrit dans l'historique : pour chaque entrée `share_history` dont le facilitateur
indiqué n'est pas du type du propriétaire, on cherche la VRAIE origine — la tâche du village source (chez les
facilitateurs des projets du propriétaire, tous types) dont les valeurs partagées sont identiques à celles du document :
  - origine du MÊME type trouvée -> seul le nom de l'historique est corrigé, les données restent ;
  - origine d'un AUTRE type seulement -> les champs / pièces jointes encore identiques à cette origine sont vidés,
    l'entrée d'historique est retirée, ainsi que l'achèvement / la validation d'office (`auto_shared`) qu'elle avait
    entraînés (la tâche repasse non achevée / non validée si rien d'autre ne l'achève / ne la valide) ;
  - aucune origine identifiable (valeurs modifiées depuis, tâche source changée...) -> rien n'est touché, signalé.

Puis le registre : chaque ligne TaskShareRecord dont le document (facilitator + couch_task_id) est lisible reprend les
valeurs partagées de CE document (une ligne de formation ne garde pas les valeurs d'un vrai FC, et inversement).

Enfin les imports COSOCollect (onglet « Import vers les tâches » / migrate_cosocollect_to_tasks) : une tâche d'un VRAI
FC dont le dernier import vient d'un enregistrement saisi par un compte de formation / démonstration (auteur de
l'enregistrement, ou facilitateur de son compte web) est remise dans son état d'avant cet import (même mécanisme que
l'annulation de l'onglet), sauf si elle a été modifiée depuis l'import ou validée (signalée seulement). Relancer
ensuite l'import (comptes retenus par défaut : vrais FC) pour y mettre l'enregistrement du vrai FC.

Simulation par défaut ; --apply pour écrire. Options : --project <id>, --facilitator <no_sql_db_name>,
--skip-registry, --skip-cosocollect.
"""
import copy

from django.core.management.base import BaseCommand

from authentication.models import Facilitator
from coso_collect.models import CollectSubmission
from coso_collect.task_migration import (
    ACCOUNT_DEVELOP, ACCOUNT_OTHERS, ACCOUNT_TRAINING, DOC_IMPORT_KEY, AccountClassifier, _last_active_import,
    facilitator_categories, restore_before_import, untouched_since_import,
)
from no_sql_client import NoSQLClient
from process_manager.models import Task, TaskShareRecord
from dashboard.process_manager.tasks.form_design import (
    ATTACHMENT_SHARE_PREFIX, extract_share_values, extract_attachment_share_values, merge_share_values,
    _norm_attachment_name,
)
from dashboard.utils import facilitator_account_kind

KIND_LABELS = {
    (False, False): "vrai FC",
    (True, False): "formation",
    (False, True): "démonstration",
    (True, True): "formation + démonstration",
}

TASK_FIELDS = [
    "_id", "type", "sql_id", "administrative_level_id", "administrative_level_name", "name",
    "form_response", "attachments", "share_history", "completed", "completed_history", "validated", "actions_by",
]


def _kind_label(fac):
    return KIND_LABELS.get(facilitator_account_kind(fac), "?")


def _fac_info(fac):
    return {"sql_id": fac.id, "name": fac.name, "email": fac.email}


class Command(BaseCommand):
    help = ("Corrige les partages de données de tâche entre types de compte différents (vrai FC / formation / démo) "
            "et le registre TaskShareRecord.")

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Écrire (sinon simulation).")
        parser.add_argument("--project", type=int, help="Limiter aux facilitateurs de ce projet (id CDD).")
        parser.add_argument("--facilitator", help="Limiter au facilitateur de cette base CouchDB.")
        parser.add_argument("--skip-registry", action="store_true", help="Ne pas resynchroniser TaskShareRecord.")
        parser.add_argument("--skip-cosocollect", action="store_true",
                            help="Ne pas vérifier les imports COSOCollect venus de comptes de test.")

    def handle(self, *args, **opts):
        self.apply = opts["apply"]
        self.nsc = NoSQLClient()
        self.facilitators = {f.id: f for f in Facilitator.objects.all()}
        self.village_docs_cache = {}
        self.tasks = {}
        self.totals = {"docs": 0, "relabel": 0, "foreign": 0, "unknown": 0, "cleared": 0, "kept": 0, "records": 0}
        self.collect = {"undone": 0, "modified": 0, "validated": 0, "no_backup": 0, "error": 0}
        self.classifier = AccountClassifier()
        self.submissions = {}

        owners = Facilitator.objects.exclude(no_sql_db_name__isnull=True).exclude(no_sql_db_name="")
        if opts.get("project"):
            owners = owners.filter(projects__in=[opts["project"]]).distinct()
        if opts.get("facilitator"):
            owners = owners.filter(no_sql_db_name=opts["facilitator"])

        self.stdout.write(self.style.MIGRATE_HEADING(
            ("ÉCRITURE" if self.apply else "SIMULATION (aucune écriture, --apply pour corriger)")
            + f" — {owners.count()} base(s) à parcourir"))

        for owner in owners.order_by("id"):
            try:
                db = self.nsc.get_db(owner.no_sql_db_name)
                rows = self.nsc.find_all(db, {"type": "task", "share_history": {"$exists": True}}, fields=TASK_FIELDS)
            except Exception as exc:
                self.stderr.write(f"  {owner.no_sql_db_name} : base illisible ({exc})")
                continue
            owner_kind = facilitator_account_kind(owner)
            for doc in rows:
                suspects = []
                for idx, entry in enumerate(doc.get("share_history") or []):
                    src = (entry.get("source_facilitator") or {}) if isinstance(entry, dict) else {}
                    named = self.facilitators.get(src.get("sql_id"))
                    if named is not None and facilitator_account_kind(named) != owner_kind:
                        suspects.append((idx, entry, named))
                if suspects:
                    self.totals["docs"] += 1
                    self.handle_doc(db, owner, owner_kind, doc, suspects)
            if not opts.get("skip_cosocollect") and owner_kind == (False, False):
                self.check_cosocollect_imports(db, owner)

        if not opts.get("skip_registry"):
            self.resync_registry(opts)

        if not opts.get("skip_cosocollect"):
            c = self.collect
            found = sum(c.values())
            self.stdout.write(self.style.SUCCESS(
                f"\nImports COSOCollect venus de comptes de test dans des tâches de vrais FC : {found} — "
                f"{c['undone']} {'annulé(s)' if self.apply else 'à annuler'}, {c['modified']} modifié(s) depuis l'import "
                f"(laissé(s)), {c['validated']} validé(s) (laissé(s)), {c['no_backup']} sans sauvegarde, "
                f"{c['error']} erreur(s)."
                + (" Relancer ensuite l'import (comptes retenus : vrais FC) pour y mettre les enregistrements des vrais "
                   "FC." if c['undone'] else "")))

        t = self.totals
        verb = "" if self.apply else "à "
        self.stdout.write(self.style.SUCCESS(
            f"\n{t['docs']} tâche(s) à historique suspect : {t['relabel']} nom(s) {verb}corriger (données d'un compte du "
            f"même type), {t['foreign']} chargement(s) réellement venus d'un autre type de compte, {t['unknown']} "
            f"origine(s) indéterminée(s) (laissées) ; {t['cleared']} valeur(s) {'vidée(s)' if self.apply else 'à vider'}, "
            f"{t['kept']} modifiée(s) depuis (laissées) ; {t['records']} ligne(s) du registre "
            f"{'resynchronisée(s)' if self.apply else 'à resynchroniser'}."))

    # ------------------------------------------------------------------
    def task_model(self, sql_id):
        if sql_id not in self.tasks:
            self.tasks[sql_id] = Task.objects.filter(id=sql_id).first()
        return self.tasks[sql_id]

    @staticmethod
    def doc_share_values(task, doc):
        values = extract_share_values(task.form, doc.get("form_response") or [])
        values.update(extract_attachment_share_values(task.attachments, doc.get("attachments")))
        return values

    def village_docs(self, owner, task, adl_id):
        """[(facilitateur, valeurs partagées)] des tâches `task` du village `adl_id`, chez les facilitateurs des
        projets du propriétaire (tous types de compte)."""
        project_ids = tuple(sorted(owner.projects.values_list("id", flat=True)))
        key = (project_ids, task.id, str(adl_id))
        if key in self.village_docs_cache:
            return self.village_docs_cache[key]
        village = [str(adl_id)]
        try:
            village.append(int(adl_id))
        except (TypeError, ValueError):
            pass
        found = []
        facs = Facilitator.objects.filter(projects__in=project_ids).exclude(no_sql_db_name__isnull=True) \
            .exclude(no_sql_db_name="").distinct()
        for fac in facs:
            try:
                db = self.nsc.get_db(fac.no_sql_db_name)
                rows = self.nsc.find_all(db, {"type": "task", "sql_id": task.id,
                                              "administrative_level_id": {"$in": village}},
                                         fields=["form_response", "attachments"])
            except Exception:
                continue
            for row in rows:
                found.append((fac, self.doc_share_values(task, row)))
        self.village_docs_cache[key] = found
        return found

    def handle_doc(self, db, owner, owner_kind, doc, suspects):
        task = self.task_model(doc.get("sql_id"))
        self.stdout.write(
            f"\n{owner.name} [{KIND_LABELS.get(owner_kind)}] — {doc.get('administrative_level_name') or ''} "
            f"({doc.get('administrative_level_id')}) — tâche {doc.get('sql_id')} {doc.get('name') or ''} — doc {doc['_id']}")
        if task is None:
            self.stdout.write("   tâche SQL introuvable : ignorée")
            return
        current = self.doc_share_values(task, doc)

        history = copy.deepcopy(doc.get("share_history") or [])
        remove_idx, to_clear, foreign_sources = set(), set(), []
        changed = False
        for idx, entry, named in suspects:
            fields = [f for f in (entry.get("fields") or []) if f in current]
            src_adl = entry.get("source_administrative_level_id")
            self.stdout.write(f"   {entry.get('date')} : historique au nom de {named.name} [{_kind_label(named)}] — "
                              f"{entry.get('source_label') or src_adl}")
            matches = []
            if fields:
                for fac, values in self.village_docs(owner, task, src_adl):
                    if all(f in values and values[f] == current[f] for f in fields):
                        matches.append(fac)
            same = [f for f in matches if facilitator_account_kind(f) == owner_kind]
            other = [f for f in matches if facilitator_account_kind(f) != owner_kind]
            if same:
                origin = same[0]
                self.totals["relabel"] += 1
                self.stdout.write(f"      données identiques à celles de {origin.name} [{_kind_label(origin)}] -> "
                                  f"nom {'corrigé' if self.apply else 'à corriger'}, données conservées")
                history[idx] = dict(entry, source_facilitator=_fac_info(origin))
                changed = True
            elif other:
                origin = other[0]
                self.totals["foreign"] += 1
                foreign_sources.append((entry, origin))
                remove_idx.add(idx)
                changed = True
                for f in entry.get("fields") or []:
                    if f in fields:
                        to_clear.add(f)
                        self.totals["cleared"] += 1
                        self.stdout.write(f"      {f} : venu de {origin.name} [{_kind_label(origin)}] -> "
                                          f"{'vidé' if self.apply else 'à vider'}")
                    else:
                        self.stdout.write(f"      {f} : déjà vide")
            else:
                self.totals["unknown"] += 1
                self.totals["kept"] += len(fields)
                self.stdout.write("      origine indéterminée (valeurs modifiées depuis, ou tâche source changée) : "
                                  "laissé tel quel")

        # Achèvement / validation d'office entraînés par un chargement venu d'un autre type de compte.
        completed_history = list(doc.get("completed_history") or [])
        actions_by = list(doc.get("actions_by") or [])
        auto_completed, auto_validated = [], []
        if foreign_sources:
            ids = {f.id for _, f in foreign_sources} | {
                (e.get("source_facilitator") or {}).get("sql_id") for e, _ in foreign_sources}
            labels = {str(e.get("source_label") or e.get("source_administrative_level_id")) for e, _ in foreign_sources}
            auto_completed = [h for h in completed_history if isinstance(h, dict) and h.get("auto_shared")
                              and (h.get("facilitator") or {}).get("sql_id") in ids]
            auto_validated = [h for h in actions_by if isinstance(h, dict) and h.get("auto_shared")
                              and any(lbl in str(h.get("comment") or "") for lbl in labels)]
            if auto_completed or auto_validated:
                self.stdout.write(f"   achèvement/validation d'office : {len(auto_completed)} + {len(auto_validated)} "
                                  f"entrée(s) {'retirée(s)' if self.apply else 'à retirer'}")

        if not (self.apply and changed):
            return

        updates = {"share_history": [e for i, e in enumerate(history) if i not in remove_idx]}
        field_paths = [f for f in to_clear if not str(f).startswith(ATTACHMENT_SHARE_PREFIX)]
        if field_paths:
            updates["form_response"] = merge_share_values(
                task.form, doc.get("form_response") or [], {p: None for p in field_paths})
        att_names = {_norm_attachment_name(str(f)[len(ATTACHMENT_SHARE_PREFIX):])
                     for f in to_clear if str(f).startswith(ATTACHMENT_SHARE_PREFIX)}
        if att_names:
            attachments = copy.deepcopy(doc.get("attachments") or [])
            for slot in attachments:
                if isinstance(slot, dict) and _norm_attachment_name(slot.get("name")) in att_names:
                    slot["attachment"] = None
            updates["attachments"] = attachments
        if auto_completed:
            remaining = [h for h in completed_history if h not in auto_completed]
            updates["completed_history"] = remaining
            if not remaining:  # rien d'autre ne l'avait achevée
                updates["completed"] = False
                updates["completed_date"] = None
        if auto_validated:
            remaining = [h for h in actions_by if h not in auto_validated]
            updates["actions_by"] = remaining
            if not remaining or not (isinstance(remaining[0], dict) and remaining[0].get("type") == "Validated"):
                updates["validated"] = False
                updates["date_validated"] = None

        db[doc["_id"]]  # chauffe le cache local de `db` (cf. dashboard.utils._find_facilitator_task_doc)
        self.nsc.update_doc_uncontrolled(db, doc["_id"], updates)

    # ------------------------------------------------------------------
    def import_author_categories(self, info):
        """Catégories de compte de l'auteur de l'enregistrement importé (lu par son uuid ; enregistrement supprimé :
        auteur noté dans l'import)."""
        uuid = info.get("submission_uuid")
        if uuid and uuid not in self.submissions:
            self.submissions[uuid] = CollectSubmission.objects.filter(uuid=uuid) \
                .select_related("user", "facilitator").first()
        sub = self.submissions.get(uuid) if uuid else None
        if sub is not None:
            return self.classifier.categories(sub)
        author = info.get("author") or {}
        if author.get("facilitator_sql_id"):
            return facilitator_categories(self.facilitators.get(author["facilitator_sql_id"]))
        if author.get("user_id"):
            from django.contrib.auth.models import User
            from authentication.identity import facilitator_of_user
            user = User.objects.filter(pk=author["user_id"]).first()
            return facilitator_categories(facilitator_of_user(user) if user else None)
        return {ACCOUNT_OTHERS}

    def check_cosocollect_imports(self, db, owner):
        """Tâches de ce vrai FC dont le DERNIER import COSOCollect vient d'un compte de formation / démonstration."""
        try:
            rows = self.nsc.find_all(db, {"type": "task", DOC_IMPORT_KEY: {"$exists": True}},
                                     fields=["_id", "sql_id", "administrative_level_id", "administrative_level_name",
                                             "name", DOC_IMPORT_KEY])
        except Exception as exc:
            self.stderr.write(f"  {owner.no_sql_db_name} : imports COSOCollect illisibles ({exc})")
            return
        for row in rows:
            info = row.get(DOC_IMPORT_KEY) or {}
            cats = self.import_author_categories(info)
            test_cats = cats & {ACCOUNT_TRAINING, ACCOUNT_DEVELOP}
            if not test_cats:
                continue
            author = (info.get("author") or {}).get("name") or "?"
            label = (f"\n[COSOCollect] {owner.name} — {row.get('administrative_level_name') or ''} "
                     f"({row.get('administrative_level_id')}) — tâche {row.get('sql_id')} {row.get('name') or ''} — "
                     f"doc {row['_id']}\n   importé le {info.get('date')} depuis « {info.get('form_title')} », "
                     f"enregistrement de {author} [{'+'.join(sorted(test_cats))}]")
            self.stdout.write(label)
            try:
                doc = db[row["_id"]]
                doc.fetch()
                idx, entry = _last_active_import(doc)
                if entry is None or "previous" not in entry:
                    self.collect["no_backup"] += 1
                    self.stdout.write("   sans sauvegarde de l'état d'avant l'import : laissé")
                    continue
                if not untouched_since_import(doc):
                    self.collect["modified"] += 1
                    self.stdout.write("   modifié par le facilitateur depuis l'import : laissé (à vérifier)")
                    continue
                if doc.get("validated") is True:
                    self.collect["validated"] += 1
                    self.stdout.write("   tâche validée : laissée (à vérifier)")
                    continue
                self.collect["undone"] += 1
                if self.apply:
                    restore_before_import(doc, idx, entry, reason="test_account")
                self.stdout.write(f"   -> {'remis' if self.apply else 'à remettre'} dans l'état d'avant l'import")
            except Exception as exc:
                self.collect["error"] += 1
                self.stdout.write(f"   erreur : {exc}")

    # ------------------------------------------------------------------
    def resync_registry(self, opts):
        """Chaque ligne du registre reprend les valeurs partagées de SON document (facilitator + couch_task_id)."""
        records = TaskShareRecord.objects.exclude(facilitator=None).exclude(couch_task_id="").select_related("facilitator")
        if opts.get("project"):
            records = records.filter(project_id=opts["project"])
        if opts.get("facilitator"):
            records = records.filter(facilitator__no_sql_db_name=opts["facilitator"])
        self.stdout.write(self.style.MIGRATE_HEADING(f"\nRegistre TaskShareRecord — {records.count()} ligne(s)"))
        for record in records.order_by("id"):
            task = self.task_model(record.task_id)
            fac = record.facilitator
            if task is None or not fac.no_sql_db_name:
                continue
            kind = facilitator_account_kind(fac)
            if (record.training_mode, record.develop_mode) != kind:
                self.stdout.write(f"   ligne {record.id} : type {KIND_LABELS.get((record.training_mode, record.develop_mode))}"
                                  f" mais facilitateur {fac.name} [{_kind_label(fac)}] — laissée, à examiner")
                continue
            try:
                db = self.nsc.get_db(fac.no_sql_db_name)
                rows = self.nsc.find_all(db, {"_id": record.couch_task_id}, fields=["form_response", "attachments"])
            except Exception:
                rows = []
            if not rows:
                self.stdout.write(f"   ligne {record.id} (tâche {record.task_id}, village {record.administrative_level_id}) :"
                                  f" document {record.couch_task_id} absent de la base de {fac.name} — laissée")
                continue
            values = self.doc_share_values(task, rows[0]) or None
            if (record.share_values or None) == values:
                continue
            self.totals["records"] += 1
            self.stdout.write(f"   ligne {record.id} (tâche {record.task_id}, village {record.administrative_level_id}, "
                              f"{fac.name} [{_kind_label(fac)}]) : valeurs {'resynchronisées' if self.apply else 'à resynchroniser'}"
                              f" depuis son document")
            if self.apply:
                TaskShareRecord.objects.filter(pk=record.pk).update(share_values=values)
