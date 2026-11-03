"""Lie une liste de cantons à un projet, comme le champ « Niveaux administratifs » de l'admin
(/admin/process_manager/project/add/) : chaque canton est ajouté avec ses VILLAGES (enfants) et ses PARENTS
(commune, préfecture, région), puis les cycles COSOMIS du projet sont réalignés (« Cycle 1 » créé s'il n'y en a pas).
Mêmes fonctions que l'admin (dashboard/process_manager/projects.py) ; les financeurs du projet sont conservés.

    python manage.py link_project_cantons --project FA2-COSO --canton 1921 --canton "SAM-NABA"
    python manage.py link_project_cantons --project FA2-COSO --cantons "1921,1928,SAM-NABA"
    python manage.py link_project_cantons --project FA2-COSO --file cantons.txt           # un canton par ligne
    ... --apply        écrire (sans : aperçu, rien n'est modifié)
    ... --replace      remplacer les niveaux du projet (par défaut : ajouter à ceux déjà liés)

Un canton se désigne par son identifiant ou par son nom (casse et accents ignorés) ; un nom porté par plusieurs
cantons doit être précisé « NOM/COMMUNE » ou remplacé par l'identifiant (la commande liste les candidats).
"""
import unicodedata

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from administrativelevels.models import AdministrativeLevel
from dashboard.process_manager.projects import expand_administrative_levels, mis_project, save_cosomis_fields
from process_manager.models import Project


def _norm(text):
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return " ".join(text.upper().split())


class Command(BaseCommand):
    help = "Lie des cantons (avec leurs villages et leurs parents) à un projet, comme l'admin des projets."

    def add_arguments(self, parser):
        parser.add_argument("--project", required=True, help="Nom ou identifiant du projet.")
        parser.add_argument("--canton", action="append", default=[], help="Canton (identifiant ou nom), répétable.")
        parser.add_argument("--cantons", default="", help="Cantons séparés par des virgules.")
        parser.add_argument("--file", help="Fichier texte : un canton (identifiant ou nom) par ligne.")
        parser.add_argument("--replace", action="store_true", help="Remplacer les niveaux déjà liés au projet.")
        parser.add_argument("--apply", action="store_true", help="Écrire les changements (sinon simple aperçu).")

    def _project(self, value):
        query = Project.objects.filter(pk=int(value)) if str(value).isdigit() else Project.objects.filter(name__iexact=value)
        project = query.first()
        if project is None:
            raise CommandError(f"Projet introuvable : {value!r}")
        return project

    def _cantons(self, values):
        cantons = list(AdministrativeLevel.objects.filter(type="Canton").select_related("parent"))
        by_id = {c.id: c for c in cantons}
        by_name = {}
        for c in cantons:
            by_name.setdefault(_norm(c.name), []).append(c)
        found, errors = [], []
        for raw in values:
            value = str(raw).strip()
            if not value:
                continue
            if value.isdigit():
                canton = by_id.get(int(value))
                if canton is None:
                    errors.append(f"{value} : aucun canton avec cet identifiant")
                else:
                    found.append(canton)
                continue
            name, _sep, commune = value.partition("/")
            candidates = by_name.get(_norm(name), [])
            if commune:
                candidates = [c for c in candidates if c.parent and _norm(c.parent.name) == _norm(commune)]
            if len(candidates) == 1:
                found.append(candidates[0])
            elif not candidates:
                errors.append(f"{value!r} : canton introuvable")
            else:
                choices = ", ".join(f"{c.id} ({c.parent.name if c.parent else '?'})" for c in candidates)
                errors.append(f"{value!r} : plusieurs cantons portent ce nom, préciser NOM/COMMUNE ou l'identifiant : {choices}")
        if errors:
            raise CommandError("Cantons non reconnus :\n  - " + "\n  - ".join(errors))
        return list({c.id: c for c in found}.values())

    def handle(self, *args, **options):
        project = self._project(options["project"])
        values = list(options["canton"]) + [v for v in options["cantons"].split(",") if v.strip()]
        if options["file"]:
            try:
                with open(options["file"], encoding="utf-8-sig") as fh:
                    values += [line.strip() for line in fh if line.strip() and not line.strip().startswith("#")]
            except OSError as exc:
                raise CommandError(f"Fichier illisible : {exc}")
        if not values:
            raise CommandError("Aucun canton donné (--canton, --cantons ou --file).")

        cantons = self._cantons(values)
        mirror = mis_project(project)
        current_ids = set(mirror.administrative_levels.values_list("id", flat=True))
        new_ids = set(expand_administrative_levels([c.id for c in cantons]))
        target_ids = new_ids if options["replace"] else current_ids | new_ids
        levels = AdministrativeLevel.objects.filter(id__in=target_ids)

        counts = {}
        for kind in levels.values_list("type", flat=True):
            counts[kind] = counts.get(kind, 0) + 1
        added, removed = target_ids - current_ids, current_ids - target_ids
        self.stdout.write(f"Projet « {project.name} » (id {project.id}) — {len(cantons)} canton(s) :")
        for c in sorted(cantons, key=lambda x: x.name):
            self.stdout.write(f"  - {c.name} (id {c.id}, commune {c.parent.name if c.parent else '?'})")
        self.stdout.write("Niveaux liés après l'opération : " + ", ".join(
            f"{counts.get(k, 0)} {k}" for k in ("Region", "Prefecture", "Commune", "Canton", "Village")))
        self.stdout.write(f"Ajoutés : {len(added)} ; retirés : {len(removed)} ; déjà liés avant : {len(current_ids)}")

        if not options["apply"]:
            self.stdout.write(self.style.WARNING("Aperçu seulement : relancer avec --apply pour écrire."))
            return
        if not added and not removed:
            self.stdout.write("Rien à changer.")
            return
        with transaction.atomic():
            save_cosomis_fields(project, list(mirror.financiers.all()), list(levels))
        self.stdout.write(self.style.SUCCESS("Niveaux administratifs et cycles COSOMIS du projet enregistrés."))
