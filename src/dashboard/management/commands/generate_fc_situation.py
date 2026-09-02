"""Génère « une seule fois » le classeur FC_SITUATION directement depuis CouchDB.

Exemples :
    # Reproduction du fichier de référence (tâche de priorisation COSO + FA-COSO)
    python manage.py generate_fc_situation --project COSO --projects COSO,FA-COSO \
        --tasks 59 128 --output D:/COSO/.../context/8_1_FC_SITUATION.xlsx

    # Situation multi-tâches d'une phase
    python manage.py generate_fc_situation --project COSO --phases 12

    # Situation d'une autre tâche (règle « 3 priorités » désactivée automatiquement)
    python manage.py generate_fc_situation --project COSO --tasks 40
"""
import os
import shutil

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from process_manager.models import Cycle, Project
from dashboard.reports.excel_csv.fc_situation import build_fc_situation_workbook


class Command(BaseCommand):
    help = "Génère le classeur FC_SITUATION (situation par FC + feuilles CVD) depuis CouchDB."

    def add_arguments(self, parser):
        parser.add_argument("--project", default="COSO",
                            help="Projet CDD de référence (nom ou id). Défaut : COSO.")
        parser.add_argument("--projects", default=None,
                            help="Noms des projets CDD à inclure, séparés par des virgules "
                                 "(défaut : l'arbre du projet de référence, ex. COSO,FA-COSO).")
        parser.add_argument("--cycle", default=None,
                            help="Nom ou order du cycle (défaut : dernier cycle de chaque projet).")
        parser.add_argument("--phases", nargs="*", type=int, default=None, help="Ids de phases.")
        parser.add_argument("--activities", nargs="*", type=int, default=None, help="Ids d'activités.")
        parser.add_argument("--tasks", nargs="*", type=int, default=None, help="Ids de tâches.")
        parser.add_argument("--adl", default=None,
                            help="Id d'un niveau administratif (zone) pour restreindre le périmètre.")
        parser.add_argument("--three-priorities-rule", choices=["auto", "on", "off"], default="auto",
                            help="Force le volet « au moins 3 priorités » (défaut : auto).")
        parser.add_argument("--output", default=None,
                            help="Chemin de destination du .xlsx (sinon garde le fichier sous media/).")

    def _resolve_project(self, value):
        project = Project.objects.filter(name=value).first()
        if project is None and str(value).isdigit():
            project = Project.objects.filter(id=int(value)).first()
        if project is None:
            raise CommandError(f"Projet CDD introuvable : {value!r}")
        return project

    def handle(self, *args, **options):
        project = self._resolve_project(options["project"])

        cycle_couch_id = None
        if options["cycle"]:
            cycle = Cycle.objects.filter(project=project, name=options["cycle"]).first()
            if cycle is None and str(options["cycle"]).isdigit():
                cycle = Cycle.objects.filter(project=project, order=int(options["cycle"])).first()
            if cycle is None:
                raise CommandError(f"Cycle introuvable pour {project.name} : {options['cycle']!r}")
            cycle_couch_id = cycle.couch_id
        else:
            last_cycle = Cycle.objects.filter(project=project).order_by("-order").first()
            cycle_couch_id = last_cycle.couch_id if last_cycle else None

        rule_opt = options["three_priorities_rule"]
        three_priorities_rule = None if rule_opt == "auto" else (rule_opt == "on")

        params = {
            "session_project_id": project.id,
            "session_project_name": project.name,
            "session_project_couch_id": project.couch_id,
            "session_cycle_couch_id": cycle_couch_id,
            "type": "All",
            "ids_administrativelevel": [options["adl"]] if options["adl"] else [],
            "facilitator_dbs_name": [],
            "ids_phase": options["phases"] or [],
            "ids_activity": options["activities"] or [],
            "ids_task": options["tasks"] or [],
            "cdd_project_names": (
                [n.strip() for n in options["projects"].split(",") if n.strip()]
                if options["projects"] else None
            ),
            "three_priorities_rule": three_priorities_rule,
        }

        self.stdout.write("Génération en cours (lecture CouchDB)…")
        rel_path = build_fc_situation_workbook(params)
        abs_path = os.path.join(settings.MEDIA_ROOT, rel_path.replace("\\\\", os.sep))

        if options["output"]:
            os.makedirs(os.path.dirname(os.path.abspath(options["output"])) or ".", exist_ok=True)
            shutil.copyfile(abs_path, options["output"])
            self.stdout.write(self.style.SUCCESS(f"Fichier écrit : {options['output']}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Fichier généré : {abs_path}"))
