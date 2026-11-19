"""Renomme un champ d'un groupe de formulaire, partout où il est recopié, sans perdre les valeurs (18/11/2026).

Cas d'origine : tâche 167 « Etablir le profil du village » (FA2-COSO) et formulaire COSOCollect 9, groupe
`generalitiesSurVillage` (« Section 1 : caractéristiques générales du quartier/village ») : le champ calculé
`totalParticipants` « Nombre total des Participants » est en réalité la population totale -> `populationTotal`
« Population totale ». Ce sont les valeurs par défaut des options.

Ce qui est réécrit (le champ est cherché SOUS le groupe, à n'importe quelle profondeur, quelle que soit la page) :
  - le formulaire : Task.form (PostgreSQL) et ses copies CouchDB — base `process_design` et `form` de chaque
    document de tâche des facilitateurs (bases facilitateur, backup_db_facilitators_docs…) : schéma
    (`page.properties`), options et libellé (`options.fields`), ordre d'affichage (`order`), champs requis, et
    toute expression qui cite `groupe.champ` (calculs `calculate`, règles `rules`, messages, conditions de
    visibilité, chemins de partage) ;
  - les réponses : `form_response` des documents de tâche ;
  - les historiques et copies : `old_forms`, `updated_history` (old / new), `completed_history`,
    `share_history`, `cosocollect_history`… (tout le document est parcouru), le registre TaskShareRecord
    (`share_values` indexé par chemin) ;
  - COSOCollect : CollectForm.form + title_template (version incrémentée : le mobile recharge le formulaire),
    CollectSubmission.data + history, CollectAttachment.field_path.

La valeur déjà présente (calculée) est conservée telle quelle, à sa place dans l'ordre des clés. Si le nouveau
nom existe déjà au même endroit, sa valeur est gardée lorsqu'elle est renseignée, sinon elle reprend l'ancienne
(cas signalé). Le calcul continue de fonctionner : sa cible est renommée comme le champ.

Idempotent : relancer ne change plus rien une fois tout renommé. À relancer après quelques jours pour rattraper
les saisies faites hors ligne sur l'ancien formulaire et synchronisées ensuite (mobile tâches et COSOCollect).

Simulation par défaut ; --apply pour écrire. Avant chaque écriture, l'original est ajouté au fichier
--backup (JSON Lines) pour pouvoir revenir en arrière.

Exemple : python manage.py rename_form_field --apply
          python manage.py rename_form_field --task 167 --collect-form 9 --group generalitiesSurVillage \
              --old totalParticipants --new populationTotal --label "Population totale" --apply

Utilisation :
python manage.py rename_form_field            # simulation : montre ce qui serait modifié
python manage.py rename_form_field --apply    # écrit
Sans option, elle traite votre cas : tâche 167 et formulaire COSOCollect 9, groupe generalitiesSurVillage, totalParticipants renommé populationTotal, libellé « Population totale ». Les options (--task, --collect-form, --group, --old, --new, --label) permettent de la réutiliser pour un autre champ.

"""
import copy
import json
import os
import re
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from dashboard.commands_runner.progress import report as report_progress  # menu « Commandes / sync »
from django.db import transaction

from coso_collect.models import CollectAttachment, CollectForm, CollectSubmission
from no_sql_client import NoSQLClient
from process_manager.models import Task, TaskShareRecord


class FieldRenamer:
    """Renommage de `old` -> `new` sous le groupe `group` dans une structure JSON (copie, l'entrée est intacte)."""

    def __init__(self, group, old, new):
        self.group, self.old, self.new = group, old, new
        self.path_re = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(f"{group}.{old}") + r"(?![A-Za-z0-9_])")
        self.changes = 0
        self.conflicts = []

    def _text(self, value):
        new_value, n = self.path_re.subn(f"{self.group}.{self.new}", value)
        self.changes += n
        return new_value

    def apply(self, node, in_group=False, where=""):
        if isinstance(node, dict):
            out = {}
            for key, value in node.items():
                child_in_group = in_group or key == self.group
                new_key = self._text(key) if isinstance(key, str) else key
                if in_group and key == self.old:
                    new_key = self.new
                    self.changes += 1
                    if self.new in node:
                        existing = node[self.new]
                        keep_existing = existing not in (None, "")
                        self.conflicts.append(f"{where}: « {self.new} » déjà présent ({existing!r}), "
                                              f"« {self.old} » = {value!r} -> "
                                              f"{'valeur existante gardée' if keep_existing else 'ancienne valeur reprise'}")
                        if keep_existing:
                            continue
                        out[self.new] = self.apply(value, child_in_group, where)
                        continue
                elif in_group and key == self.new and self.old in node:
                    # Traité avec l'ancienne clé (voir ci-dessus) : on ne garde que la valeur retenue.
                    if node[self.new] in (None, ""):
                        continue
                out[new_key] = self.apply(value, child_in_group, where)
            return out
        if isinstance(node, list):
            items = []
            for item in node:
                if in_group and item == self.old:  # listes `order`, `required`
                    self.changes += 1
                    if self.new in node:
                        continue  # déjà listé sous le nouveau nom : pas de doublon
                    items.append(self.new)
                else:
                    items.append(self.apply(item, in_group, where))
            return items
        if isinstance(node, str):
            return self._text(node)
        return node


def set_label(form_pages, group, field, label):
    """Libellé du champ dans `options.fields.<groupe>.fields.<champ>` de chaque page. Renvoie le nombre posé."""
    count = 0
    if not label or not isinstance(form_pages, list):
        return 0
    for page in form_pages:
        if not isinstance(page, dict):
            continue
        options = ((page.get("options") or {}).get("fields") or {}).get(group) or {}
        field_options = (options.get("fields") or {}).get(field)
        if isinstance(field_options, dict) and field_options.get("label") != label:
            field_options["label"] = label
            count += 1
    return count


class Command(BaseCommand):
    help = ("Renomme un champ de groupe de formulaire (tâche + COSOCollect) dans le formulaire, les réponses et les "
            "historiques, sans perdre les valeurs. Défaut : tâche 167 / COSOCollect 9, generalitiesSurVillage."
            "totalParticipants -> populationTotal « Population totale ».")

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Écrire (sinon simulation).")
        parser.add_argument("--task", type=int, action="append", help="Id CDD de la tâche (répétable). Défaut : 167.")
        parser.add_argument("--collect-form", type=int, action="append",
                            help="Id du formulaire COSOCollect (répétable). Défaut : 9.")
        parser.add_argument("--no-collect", action="store_true", help="Ne pas traiter COSOCollect.")
        parser.add_argument("--no-tasks", action="store_true", help="Ne pas traiter les tâches.")
        parser.add_argument("--group", default="generalitiesSurVillage")
        parser.add_argument("--old", default="totalParticipants")
        parser.add_argument("--new", default="populationTotal")
        parser.add_argument("--label", default="Population totale", help="Nouveau libellé ('' pour le garder).")
        parser.add_argument("--db", action="append",
                            help="Limiter aux bases CouchDB nommées (répétable). Défaut : toutes.")
        parser.add_argument("--backup", help="Fichier de sauvegarde des originaux (JSON Lines). "
                                             "Défaut : media/backups/rename_form_field_<date>.jsonl")

    # ------------------------------------------------------------------ utilitaires

    def _renamer(self):
        return FieldRenamer(self.group, self.old, self.new)

    def _backup(self, kind, ident, original):
        if not self.apply:
            return
        self.backup_file.write(json.dumps({"kind": kind, "id": ident, "original": original},
                                          ensure_ascii=False, default=str) + "\n")
        self.backup_file.flush()

    def _transform(self, value, where, form_keys=()):
        """(nouvelle valeur, nombre de changements) ; `form_keys` = clés contenant un formulaire (libellé)."""
        renamer = self._renamer()
        new_value = renamer.apply(value, where=where)
        changes = renamer.changes
        for conflict in renamer.conflicts:
            self.conflicts.append(conflict)
        if self.label:
            if form_keys == ("__self__",):
                changes += set_label(new_value, self.group, self.new, self.label)
            elif isinstance(new_value, dict):
                for key in form_keys:
                    changes += set_label(new_value.get(key), self.group, self.new, self.label)
                for old_form in new_value.get("old_forms") or []:
                    if isinstance(old_form, dict):
                        changes += set_label(old_form.get("form"), self.group, self.new, self.label)
        return new_value, changes

    def _count(self, key, n=1):
        self.stats[key] = self.stats.get(key, 0) + n

    # ------------------------------------------------------------------ tâches

    def _handle_tasks(self, task_ids):
        tasks = list(Task.objects.filter(id__in=task_ids))
        missing = set(task_ids) - {t.id for t in tasks}
        if missing:
            raise CommandError(f"Tâche(s) introuvable(s) : {sorted(missing)}")

        # 1. Formulaire maître (PostgreSQL). Pas de Task.save() : la copie process_design est traitée plus bas
        #    avec les autres documents CouchDB, et save() aurait d'autres effets (groupes, synchronisation…).
        for task in tasks:
            new_form, changes = self._transform(task.form, f"Task {task.id}.form", form_keys=("__self__",))
            if changes:
                self._count("Task.form (PostgreSQL)")
                self.stdout.write(f"Task {task.id} « {task.name} » : formulaire, {changes} modification(s)")
                if self.apply:
                    self._backup("task.form", task.id, task.form)
                    Task.objects.filter(id=task.id).update(form=new_form)

        # 2. Registre des partages (instantané {chemin: valeur}).
        for record in TaskShareRecord.objects.filter(task_id__in=task_ids):
            new_values, changes = self._transform(record.share_values, f"TaskShareRecord {record.id}")
            if changes:
                self._count("TaskShareRecord.share_values")
                if self.apply:
                    self._backup("task_share_record", record.id, record.share_values)
                    TaskShareRecord.objects.filter(id=record.id).update(share_values=new_values)

        # 3. Documents CouchDB : process_design + copies des facilitateurs + sauvegardes, toutes bases confondues.
        nsc = NoSQLClient(timeout=120)
        couch_ids = [t.couch_id for t in tasks if t.couch_id]
        selector = {"$or": [{"sql_id": {"$in": task_ids}}] + ([{"_id": {"$in": couch_ids}}] if couch_ids else [])}
        db_names = self.db_names or [name for name in nsc.get_dbs() if not name.startswith("_")]
        self.stdout.write(f"Bases CouchDB parcourues : {len(db_names)}")
        for index, db_name in enumerate(db_names, 1):
            report_progress(phase="Documents CouchDB des tâches", done=index - 1, total=len(db_names), current=db_name)
            try:
                db = nsc.get_db(db_name)
                ids = [d["_id"] for d in nsc.find_all(db, selector, fields=["_id"])]
            except Exception as exc:  # base illisible : signalée, on continue
                self.errors.append(f"{db_name} : lecture impossible ({exc})")
                continue
            for doc_id in ids:
                self._update_couch_doc(db, db_name, doc_id)
            if index % 100 == 0:
                self.stdout.write(f"  … {index}/{len(db_names)} bases")

    def _update_couch_doc(self, db, db_name, doc_id, attempt=1):
        from cloudant.document import Document
        from requests.exceptions import HTTPError

        document = Document(db, doc_id)
        document.fetch()
        original = dict(document)
        new_doc, changes = self._transform(original, f"{db_name}/{doc_id}", form_keys=("form",))
        if not changes:
            self._count("documents CouchDB déjà à jour")
            return
        self._count("documents CouchDB modifiés")
        if original.get("form_response") and json.dumps(original.get("form_response")).find(f'"{self.old}"') >= 0:
            self._count("réponses de facilitateurs renommées")
        if not self.apply:
            return
        self._backup("couch", f"{db_name}/{doc_id}", original)
        document.clear()
        document.update(new_doc)  # garde _id et _rev lus : une modification concurrente lève un conflit
        try:
            document.save()
        except HTTPError as exc:
            if getattr(exc.response, "status_code", None) == 409 and attempt < 3:
                return self._update_couch_doc(db, db_name, doc_id, attempt + 1)  # relu puis réécrit
            self.errors.append(f"{db_name}/{doc_id} : écriture impossible ({exc})")

    # ------------------------------------------------------------------ COSOCollect

    def _handle_collect(self, form_ids):
        report_progress(phase="COSOCollect")
        forms = list(CollectForm.objects.filter(id__in=form_ids))
        missing = set(form_ids) - {f.id for f in forms}
        if missing:
            raise CommandError(f"Formulaire(s) COSOCollect introuvable(s) : {sorted(missing)}")
        for form in forms:
            new_form, changes = self._transform(form.form, f"CollectForm {form.id}.form", form_keys=("__self__",))
            new_title, title_changes = self._transform(form.title_template, f"CollectForm {form.id}.title_template")
            if changes or title_changes:
                self._count("CollectForm.form")
                self.stdout.write(f"COSOCollect {form.id} « {form.title} » : formulaire, "
                                  f"{changes + title_changes} modification(s) ; version {form.version} -> "
                                  f"{form.version + 1}")
                if self.apply:
                    self._backup("collect_form", form.id, {"form": form.form, "title_template": form.title_template,
                                                           "version": form.version})
                    # update() : pas d'auto_now sur updated_at, la liste des formulaires garde son ordre.
                    CollectForm.objects.filter(id=form.id).update(form=new_form, title_template=new_title,
                                                                  version=form.version + 1)

            for submission in CollectSubmission.objects.filter(form=form).iterator():
                new_data, data_changes = self._transform(submission.data, f"CollectSubmission {submission.id}.data")
                new_history, history_changes = self._transform(submission.history,
                                                               f"CollectSubmission {submission.id}.history")
                if data_changes or history_changes:
                    self._count("CollectSubmission (data / history)")
                    if self.apply:
                        self._backup("collect_submission", submission.id,
                                     {"data": submission.data, "history": submission.history})
                        CollectSubmission.objects.filter(id=submission.id).update(data=new_data,
                                                                                  history=new_history)

            for attachment in CollectAttachment.objects.filter(form=form).exclude(field_path=""):
                new_path, path_changes = self._transform(attachment.field_path, f"CollectAttachment {attachment.id}")
                if path_changes:
                    self._count("CollectAttachment.field_path")
                    if self.apply:
                        self._backup("collect_attachment", attachment.id, attachment.field_path)
                        CollectAttachment.objects.filter(id=attachment.id).update(field_path=new_path)

    # ------------------------------------------------------------------ entrée

    def handle(self, *args, **options):
        self.apply = options["apply"]
        self.group, self.old, self.new = options["group"], options["old"], options["new"]
        self.label = options["label"]
        self.db_names = options["db"]
        if self.old == self.new:
            raise CommandError("--old et --new sont identiques.")
        self.stats, self.conflicts, self.errors = {}, [], []

        self.backup_file = None
        if self.apply:
            path = options["backup"] or os.path.join(
                "media", "backups", f"rename_form_field_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl")
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            self.backup_file = open(path, "a", encoding="utf-8")
            self.stdout.write(f"Sauvegarde des originaux : {path}")

        self.stdout.write(f"{'ÉCRITURE' if self.apply else 'SIMULATION (--apply pour écrire)'} : "
                          f"{self.group}.{self.old} -> {self.group}.{self.new}"
                          + (f" « {self.label} »" if self.label else ""))
        try:
            if not options["no_collect"]:
                with transaction.atomic():
                    self._handle_collect(options["collect_form"] or [9])
            if not options["no_tasks"]:
                self._handle_tasks(options["task"] or [167])
        finally:
            if self.backup_file:
                self.backup_file.close()

        self.stdout.write("\nRésumé :")
        for key, value in sorted(self.stats.items()):
            self.stdout.write(f"  {key} : {value}")
        if self.conflicts:
            self.stdout.write(self.style.WARNING(f"\n{len(self.conflicts)} cas où les deux noms coexistaient :"))
            for conflict in self.conflicts[:50]:
                self.stdout.write(f"  - {conflict}")
        if self.errors:
            self.stdout.write(self.style.ERROR(f"\n{len(self.errors)} erreur(s) :"))
            for error in self.errors[:50]:
                self.stdout.write(f"  - {error}")
        if not self.apply:
            self.stdout.write("\nAucune écriture (simulation). Relancer avec --apply.")
