"""Complète les cycles du SIG avec les niveaux administratifs de leur projet.

Pourquoi : les statistiques du DCC (`update_funnel` -> `sync_celery_tasks_re`) ne retiennent que les villages du
projet ET du cycle dans le SIG. Le SIG retire bien d'un cycle les niveaux enlevés du projet, mais n'y ajoutait pas
ceux ajoutés ensuite au projet : FA2-COSO (cycle SIG 4) n'avait que 802 des 1 601 villages du projet, dont aucun
des villages où les FC ont des tâches -> aucune statistique.

Règle : projet à UN SEUL cycle -> le cycle reçoit tous les niveaux du projet (régions… villages), comme les autres
projets. Projet à plusieurs cycles : signalé, rien n'est modifié (les cycles peuvent couvrir des zones
différentes). Rien n'est jamais retiré d'un cycle.

Aperçu par défaut ; `--apply` pour écrire.

    python manage.py align_sig_cycles_with_projects
    python manage.py align_sig_cycles_with_projects --project FA2-COSO --apply
"""
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction

from cdd.call_objects_from_other_db import mis_objects_call
from subprojects.models import Cycle as MisCycle, Project as MisProject


def missing_levels(project, cycle):
    """Niveaux du projet absents du cycle (queryset)."""
    in_cycle = set(cycle.administrative_levels.values_list('id', flat=True))
    return project.administrative_levels.exclude(id__in=in_cycle)


class Command(BaseCommand):
    help = "Ajoute aux cycles du SIG (projets à un seul cycle) les niveaux administratifs du projet qui y manquent."

    def add_arguments(self, parser):
        parser.add_argument('--project', action='append', default=[], help='Nom du projet SIG (répétable). Défaut : tous.')
        parser.add_argument('--apply', action='store_true', help='Écrire (sinon aperçu).')

    def handle(self, *args, **opts):
        projects = mis_objects_call.filter_objects(MisProject).order_by('id')
        if opts['project']:
            projects = projects.filter(name__in=opts['project'])
        total = 0
        for project in projects:
            cycles = list(mis_objects_call.filter_objects(MisCycle, project_id=project.id).order_by('order'))
            if not cycles:
                continue
            if len(cycles) > 1:
                gaps = {c.id: missing_levels(project, c).count() for c in cycles}
                if any(gaps.values()):
                    self.stdout.write(self.style.WARNING(
                        f"{project.name} : {len(cycles)} cycles, non modifiés (niveaux du projet absents par cycle : {gaps})"))
                continue
            cycle = cycles[0]
            missing = list(missing_levels(project, cycle))
            if not missing:
                continue
            total += len(missing)
            by_type = dict(Counter(level.type for level in missing))
            villages = [level for level in missing if level.type == 'Village']
            self.stdout.write(f"{project.name} (cycle SIG {cycle.id} « {cycle.name} ») : {len(missing)} niveau(x) à ajouter "
                              f"{by_type} ; ex. villages : {', '.join(f'{v.id} {v.name}' for v in villages[:5])}")
            if opts['apply']:
                with transaction.atomic(using=cycle._state.db):
                    cycle.administrative_levels.add(*missing)
        verb = 'ajoutés' if opts['apply'] else 'à ajouter (aperçu, --apply pour écrire)'
        self.stdout.write(self.style.SUCCESS(f"{total} niveau(x) {verb}"))
