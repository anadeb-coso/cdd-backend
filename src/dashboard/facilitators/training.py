"""Comptes de formation (training_mode) : création depuis le Web DCC, comme `dashboard.utils.create_training_facilitators`.

Différences voulues avec la fonction d'origine :
- villages choisis (villages sièges de CVD du projet, et les autres villages de leur CVD) au lieu de SANFATOUTE codé
  en dur ;
- copie en base `Facilitator.administrative_levels` remplie comme le document CouchDB (la fenêtre « Synchroniser
  cette tâche » lit cette copie) ;
- mot de passe haché avant la création, comme creation.py (`Facilitator.save` ne hache pas un mot de passe passé au
  constructeur : il le compare à sa valeur initiale) ;
- AUCUNE affectation du SIG (`AssignAdministrativeLevelToFacilitator`) : réservées aux vrais FC
  (cf. localities.has_sig_assignments) ;
- ni compte MGP, ni mail, ni compte web : ce sont des comptes de test pour l'application mobile.
"""
import copy
import logging
import re

from django.contrib.auth.hashers import make_password
from django.db import connections

from administrativelevels.models import AdministrativeLevel
from authentication.models import Facilitator
from cdd.call_objects_from_other_db import mis_objects_call
from no_sql_client import NoSQLClient
from process_manager.models import Task
from subprojects.models import Project as MisProject

from .creation import decorate_administrative_levels

logger = logging.getLogger(__name__)

USERNAME_PREFIX = 'training'
DEFAULT_PASSWORD = '123learn'
MAX_ACCOUNTS = 50
USERNAME_RE = re.compile(rf'^{USERNAME_PREFIX}(\d+)$')


def next_number():
    """Premier numéro libre après le plus grand `trainingN` existant (tous projets)."""
    numbers = [int(m.group(1)) for m in (USERNAME_RE.match(u or '') for u in
                                         Facilitator.objects.filter(username__startswith=USERNAME_PREFIX)
                                         .values_list('username', flat=True)) if m]
    return max(numbers, default=0) + 1


def usernames(start, count):
    return [f'{USERNAME_PREFIX}{n}' for n in range(start, start + count)]


def project_mis_of(project):
    return mis_objects_call.filter_objects(MisProject, name=project.name).first()


def headquarters_choices(project):
    """[(id, libellé)] des villages sièges de CVD du projet (village (canton) — CVD)."""
    project_mis = project_mis_of(project)
    if not project_mis:
        return []
    out = []
    for v in project_mis.administrative_levels.filter(type='Village', cvd__isnull=False).select_related('cvd', 'parent'):
        if v.cvd.headquarters_village_id == v.id:
            out.append((v.id, f"{v.name} ({v.parent.name if v.parent else '—'}) — {v.cvd.name}"))
    return sorted(out, key=lambda x: x[1].lower())


def villages_of_headquarters(project, headquarters_ids):
    """Villages sièges choisis + les autres villages de leur CVD présents dans le projet : [{id, name}], siège en
    premier pour chaque CVD."""
    project_mis = project_mis_of(project)
    in_project = set(project_mis.administrative_levels.filter(type='Village').values_list('id', flat=True)) \
        if project_mis else set()
    out, seen = [], set()
    for hq in AdministrativeLevel.objects.using('mis').filter(id__in=headquarters_ids).select_related('cvd'):
        members = [hq] + [v for v in AdministrativeLevel.objects.using('mis').filter(cvd_id=hq.cvd_id, type='Village')
                          .exclude(id=hq.id).order_by('name') if v.id in in_project]
        for v in members:
            if v.id not in seen:
                seen.add(v.id)
                out.append({'id': str(v.id), 'name': v.name})
    return out


def sig_assignments_count(facilitators):
    """{facilitator_id: nombre de lignes du SIG} (doit rester 0 pour un compte de formation)."""
    ids = [str(f.id) for f in facilitators]
    if not ids:
        return {}
    with connections['mis'].cursor() as cursor:
        cursor.execute("SELECT facilitator_id, COUNT(*) FROM assignments_assignadministrativeleveltofacilitator "
                       "WHERE facilitator_id = ANY(%s) GROUP BY facilitator_id", [ids])
        return {int(fid): n for fid, n in cursor.fetchall()}


def _remove(facilitator, nsc):
    """Annule une création incomplète (base et utilisateur CouchDB, ligne PostgreSQL)."""
    try:
        nsc.delete_db(facilitator.no_sql_db_name)
    except Exception:  # noqa: BLE001
        logger.exception('Compte de formation %s : base CouchDB non supprimée', facilitator.username)
    try:
        nsc.delete_user(facilitator.no_sql_user)
    except Exception:  # noqa: BLE001
        logger.exception('Compte de formation %s : utilisateur CouchDB non supprimé', facilitator.username)
    facilitator.projects.clear()
    # sans les signaux de suppression (lents : parcours CouchDB) ; rien d'autre n'a encore été créé pour ce compte
    Facilitator.objects.filter(pk=facilitator.pk)._raw_delete(Facilitator.objects.db)


def create_training_accounts(project, cycle, start, count, password, headquarters_ids):
    """Crée `count` comptes trainingN (N = start…) dans le projet et le cycle. Renvoie la liste des facilitateurs
    créés ; une erreur sur un compte annule CE compte et arrête la série (les précédents sont gardés)."""
    from dashboard.utils import sync_geographicalunits_with_cvd_on_facilittor

    elements = villages_of_headquarters(project, headquarters_ids)
    if not elements:
        raise ValueError('Aucun village')
    levels = decorate_administrative_levels(copy.deepcopy(elements), project, cycle, project_mis_of(project))
    total_tasks = Task.objects.filter(project_id=project.id, cycles__in=[cycle.id]).count()
    nsc = NoSQLClient()
    created = []
    for n in range(start, start + count):
        facilitator = Facilitator(
            username=f'{USERNAME_PREFIX}{n}', password=make_password(password, salt=None, hasher='default'),
            active=True, training_mode=True, develop_mode=False,
            facilitator_type='community_facilitator', name=f'Training{n} Account', email=f'training{n}@test.com',
            phone=f'123456{n}', sex='M.',
        )
        facilitator.save(replicate_design=False)   # base + utilisateur CouchDB
        try:
            account_levels = copy.deepcopy(levels)
            facilitator.administrative_levels = account_levels
            facilitator.administrative_levels_ids = [int(x['id']) for x in account_levels]
            facilitator.simple_save()
            project.facilitators.add(facilitator)
            doc = {
                'name': facilitator.name, 'email': facilitator.email, 'phone': facilitator.phone, 'sex': facilitator.sex,
                'administrative_levels': account_levels, 'type': 'facilitator', 'geographical_units': [],
                'develop_mode': False, 'training_mode': True, 'sql_id': facilitator.id,
                'facilitator_type': 'community_facilitator',
                'project_id': project.couch_id, 'project_name': project.name,
                'projects_ids': [project.couch_id], 'projects_names': [project.name],
                'total_number_of_tasks': total_tasks,
                'total_tasks_by_project_by_cycle': {
                    project.couch_id: {cycle.couch_id: total_tasks},
                    project.name: {cycle.name: total_tasks},
                },
            }
            nsc.create_document(nsc.get_db(facilitator.no_sql_db_name), doc)
            # Unités géographiques (CVD) déduites des villages, comme à la création d'un FC
            sync_geographicalunits_with_cvd_on_facilittor(project.id, False, True, facilitator.no_sql_db_name)
        except Exception:
            logger.exception('Compte de formation %s : création annulée', facilitator.username)
            _remove(facilitator, nsc)
            raise
        created.append(facilitator)
    return created
