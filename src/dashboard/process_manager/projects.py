"""Création et modification d'un projet depuis le Web DCC (page dédiée et admin) — mêmes champs que dans COSOMIS.

Le projet est la table commune `process_manager_project` (base unifiée DCC + COSOMIS) :
- le DCC y lie les facilitateurs et les utilisateurs (`process_manager.Project.facilitators` / `.users`) ;
- COSOMIS y lie les financeurs et les niveaux administratifs (modèle miroir `subprojects.Project`, mêmes tables) et
  aligne ses cycles (`subprojects.Cycle`) sur ces niveaux.

Les modèles miroirs sont utilisés ici sur l'alias par défaut (et non `mis`, qui pointe la même base par une autre
connexion) : le projet et tous ses liens sont ainsi enregistrés dans la même transaction.
Règles reprises de COSOMIS (cosomis/subprojects/forms_project.py, administrativelevels/functions_adl.py,
subprojects/models.py::sync_project_cycles) : les garder alignées.
"""
from django.db import connection

from administrativelevels.models import AdministrativeLevel
from subprojects.models import Cycle as MisCycle, Project as MisProject

ADMINISTRATIVE_LEVEL_TABLE = 'administrativelevels_administrativelevel'


def _int_ids(ids):
    return [int(i) for i in ids if str(i).strip().lstrip('-').isdigit()]


def expand_administrative_levels(level_ids):
    """Niveaux choisis + villages des cantons choisis + parents de chaque niveau (jusqu'à la région) — comme
    `get_multiple_administrative_hierarchies` de COSOMIS."""
    ids = _int_ids(level_ids)
    if not ids:
        return []
    with connection.cursor() as cursor:
        cursor.execute(f"""
            WITH RECURSIVE descendants AS (
                SELECT id, type FROM {ADMINISTRATIVE_LEVEL_TABLE} WHERE id = ANY(%s)
                UNION ALL
                SELECT al.id, al.type FROM {ADMINISTRATIVE_LEVEL_TABLE} al
                INNER JOIN descendants d ON al.parent_id = d.id AND d.type = 'Canton'
            ),
            ancestors AS (
                SELECT id, parent_id FROM {ADMINISTRATIVE_LEVEL_TABLE} WHERE id = ANY(%s)
                UNION ALL
                SELECT al.id, al.parent_id FROM {ADMINISTRATIVE_LEVEL_TABLE} al
                INNER JOIN ancestors a ON a.parent_id = al.id
            )
            SELECT id FROM descendants UNION SELECT id FROM ancestors
        """, [ids, ids])
        return sorted(row[0] for row in cursor.fetchall())


def cascade_village_ids(level_ids):
    """Villages situés sous les niveaux donnés (eux-mêmes s'ils sont des villages) — comme
    `get_cascade_villages_ids_by_administrative_level_id` de COSOMIS."""
    ids = _int_ids(level_ids)
    if not ids:
        return set()
    with connection.cursor() as cursor:
        cursor.execute(f"""
            WITH RECURSIVE descendants AS (
                SELECT id, type FROM {ADMINISTRATIVE_LEVEL_TABLE} WHERE id = ANY(%s)
                UNION ALL
                SELECT al.id, al.type FROM {ADMINISTRATIVE_LEVEL_TABLE} al INNER JOIN descendants d ON al.parent_id = d.id
            )
            SELECT DISTINCT id FROM descendants WHERE type = 'Village'
        """, [ids])
        return {row[0] for row in cursor.fetchall()}


def mis_project(project):
    return MisProject.objects.get(pk=project.pk)


def save_cosomis_fields(project, financiers, administrative_levels):
    """Financeurs et niveaux administratifs du projet (tables de COSOMIS), puis alignement de ses cycles COSOMIS."""
    mirror = mis_project(project)
    mirror.financiers.set(financiers)
    mirror.administrative_levels.set(administrative_levels)
    sync_project_cycles(mirror)


def sync_project_cycles(mirror):
    """Comme `sync_project_cycles` de COSOMIS : « Cycle 1 » créé au premier niveau administratif ; les niveaux
    retirés du projet sont retirés de ses cycles (qui ne gardent que des villages du projet)."""
    project_level_ids = set(mirror.administrative_levels.values_list('id', flat=True))
    cycles = list(MisCycle.objects.filter(project_id=mirror.pk))
    if not cycles and project_level_ids:
        cycle = MisCycle.objects.create(name="Cycle 1", description=f"Cycle 1 du projet ({mirror.name})",
                                        project_id=mirror.pk, order=1)
        cycle.administrative_levels.set(project_level_ids)
        return
    for cycle in cycles:
        if not project_level_ids:
            cycle.administrative_levels.set([])
            continue
        cycle_level_ids = list(cycle.administrative_levels.values_list('id', flat=True))
        keep = project_level_ids & cascade_village_ids(cycle_level_ids) if cycle_level_ids else project_level_ids
        cycle.administrative_levels.set(AdministrativeLevel.objects.filter(id__in=keep))
