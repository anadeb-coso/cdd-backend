"""Création d'un facilitateur depuis le DCC (formulaire « Créer un facilitateur » ou import Excel) :

  - identifiant `prénom.nom` et mot de passe initial générés ;
  - compte DCC (base CouchDB et son document, compte web lié, projets), villages d'affectation éventuels ;
  - sans localités de stabilisation, les villages d'affectation y sont répliqués ;
  - compte MGP de même e-mail (même mot de passe, même groupe, mêmes localités de stabilisation) ;
  - mot de passe à changer à la première connexion (toutes plateformes) et mail des identifiants.

Le MGP ne crée jamais de facilitateur dans le DCC (sens unique)."""
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User

import grm_client
from administrativelevels import models as administrativelevels_models
from assignments.models import AssignAdministrativeLevelToFacilitator
from authentication.accounts import generate_password, generate_username, require_password_change, send_account_credentials
from authentication.functions import ensure_facilitator_user, sync_facilitator_user_projects
from authentication.models import Facilitator
from cdd.call_objects_from_other_db import mis_objects_call
from no_sql_client import NoSQLClient
from process_manager.models import Cycle, ProcessAddOrRemoveADL, Project
from subprojects.models import Project as MisProject

from .localities import AdministrativeTree
from .localities_apply import replicate_assignment_to_stabilization
from .localities_history import facilitator_state, record_facilitator_changes, record_localities_change

SEX_CHOICES = ("M.", "Mme")


def full_name(last_name, first_names):
    """Nom complet au format du DCC : « NOM Prénoms »."""
    return f"{(last_name or '').strip().upper()} {(first_names or '').strip()}".strip()


class FacilitatorCreation:
    """Résultat d'une création : le facilitateur, ses identifiants (le mot de passe n'est conservé qu'en mémoire,
    pour l'afficher une fois si le mail n'est pas parti), l'envoi du mail et le compte MGP."""

    def __init__(self, facilitator, username, password):
        self.facilitator = facilitator
        self.username = username
        self.password = password
        self.mail_sent = False
        self.mgp_status = None  # 'created' | 'exists' | 'error' | None (pas d'e-mail)
        self.mgp_detail = None
        self.stabilization_replicated = False

    def as_row(self):
        facilitator = self.facilitator
        return {
            'kind': 'facilitator',
            'name': facilitator.name,
            'email': facilitator.email,
            'username': self.username,
            'password': None if self.mail_sent else self.password,
            'mail_sent': self.mail_sent,
            'mgp_status': self.mgp_status,
            'mgp_detail': self.mgp_detail,
            'facilitator_type': facilitator.get_facilitator_type_display(),
        }


def decorate_administrative_levels(elements, project_cdd, cycle_cdd, project_mis):
    """Éléments `administrative_levels` soumis par le formulaire de création, complétés comme avant (village siège
    de CVD ; projet/cycle de la session si le village appartient au projet)."""
    decorated = []
    for elt in elements or []:
        administrativelevel_obj = administrativelevels_models.AdministrativeLevel.objects.using('mis').get(id=int(elt['id']))
        if administrativelevel_obj.cvd and administrativelevel_obj.cvd.headquarters_village and str(administrativelevel_obj.cvd.headquarters_village.id) == elt['id']:
            elt['is_headquarters_village'] = True

        if project_mis and project_mis.administrative_levels.filter(id=int(elt['id'])).exists():
            elt["project_id"] = project_cdd.couch_id
            elt["project_name"] = project_cdd.name
            elt["cycle_id"] = cycle_cdd.couch_id
            elt["cycle_name"] = cycle_cdd.name

        decorated.append(elt)
    return decorated


def localities_summary(facilitator, tree):
    """Localités présentées dans le mail des identifiants."""
    rows = []
    if facilitator.administrative_levels_ids:
        rows.append({'label': 'assignment', 'value': ", ".join(tree.name_of(v) for v in facilitator.administrative_levels_ids)})
    if facilitator.stabilization_administrative_ids:
        rows.append({'label': 'stabilization', 'value': ", ".join(tree.name_of(v) for v in facilitator.stabilization_administrative_ids)})
    return rows


def create_facilitator_on_mgp(facilitator, first_names, last_name):
    """Compte MGP de même e-mail : (statut, détail) ; statut None sans e-mail."""
    if not (facilitator.email or '').strip():
        return None, None
    ok, detail = grm_client.create_facilitator_on_grm(
        email=facilitator.email, first_name=first_names, last_name=last_name, phone=facilitator.phone,
        facilitator_type=facilitator.facilitator_type, password_hash=facilitator.password, is_active=facilitator.active,
        administrative_id=facilitator.main_administrative_id,
        administrative_ids=facilitator.stabilization_administrative_choices or [],
        additional_administrative_ids=facilitator.additional_administrative_choices or [],
    )
    if not ok:
        return 'error', detail
    return (detail or {}).get('status', 'created'), None


def create_facilitator(*, last_name, first_names, email, phone, sex, facilitator_type, projects, created_by,
                       project_id, cycle_id, project_couch_id, project_name, administrative_levels=None, tree=None,
                       reserved_usernames=()):
    """Crée le facilitateur et tout ce qui l'accompagne (cf. docstring du module). `administrative_levels` :
    éléments {id, name} soumis par le formulaire (aucun pour l'import). Renvoie un `FacilitatorCreation`."""
    from dashboard.utils import search_facilitators_db_with_villages_stabilized, sync_geographicalunits_with_cvd_on_facilittor

    email = (email or '').strip() or None
    last_name = (last_name or '').strip().upper()
    first_names = (first_names or '').strip()
    username = generate_username(first_names, last_name, reserved=reserved_usernames)
    password = generate_password()

    facilitator = Facilitator(username=username, password=make_password(password, salt=None, hasher='default'), active=True)
    facilitator.name = full_name(last_name, first_names)
    facilitator.email = email
    facilitator.phone = (str(phone).strip() if phone not in (None, '') else None)
    facilitator.sex = sex if sex in SEX_CHOICES else None
    facilitator.facilitator_type = facilitator_type
    facilitator.save(replicate_design=False)
    creation = FacilitatorCreation(facilitator, username, password)

    project_cdd = Project.objects.get(id=project_id)
    cycle_cdd = Cycle.objects.get(id=cycle_id, project_id=project_id)
    project_mis = mis_objects_call.filter_objects(MisProject, name=project_name).first()
    project_mis_id = project_mis.id if project_mis else 1

    _administrative_levels = decorate_administrative_levels(administrative_levels, project_cdd, cycle_cdd, project_mis)

    #Assign ADL
    for adl in _administrative_levels:
        _assign = AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(administrative_level_id=int(adl['id']), project_id=project_mis_id, activated=True).first()

        if (adl.get('id') and str(adl.get('id')).isdigit() and not _assign):
                try:
                    assign = AssignAdministrativeLevelToFacilitator()
                    assign.administrative_level_id = int(adl['id'])
                    assign.facilitator_id = facilitator.id
                    assign.project_id = project_mis_id
                    assign.save(using='mis')
                except Exception as exc:
                    print(exc)
    #End Assign ADL

    # Compte web lié (connexion au Web DCC et au SIG). L'e-mail a été vérifié libre avant la création : il
    # n'est donc pas modifié ici (cf. résolution de collision d'ensure_facilitator_user).
    ensure_facilitator_user(facilitator)
    User.objects.filter(pk=facilitator.user_id).update(first_name=first_names, last_name=last_name)

    doc = {
        "name": facilitator.name,
        "email": facilitator.email,
        "phone": facilitator.phone,
        "sex": facilitator.sex,
        "facilitator_type": facilitator_type,
        "administrative_levels": _administrative_levels,
        "type": "facilitator",
        "develop_mode": facilitator.develop_mode,
        "training_mode": facilitator.training_mode,
        "sql_id": int(facilitator.pk),
        "project_id": project_couch_id,
        "project_name": project_name,
        "projects_ids": [p.couch_id for p in projects or []],
        "projects_names": [p.name for p in projects or []],
    }

    facilitator.administrative_levels = _administrative_levels
    facilitator.administrative_levels_ids = [int(_adl['id']) for _adl in _administrative_levels]
    facilitator.simple_save()
    record_localities_change(
        'assignment', 'facilitator_creation', {'villages': facilitator.administrative_levels_ids}, {'villages': []},
        facilitator=facilitator, changed_by=created_by, project_id=project_id,
    )

    nsc = NoSQLClient()
    facilitator_database = nsc.get_db(facilitator.no_sql_db_name)
    nsc.create_document(facilitator_database, doc)

    process_adls = [d.get('id') for d in _administrative_levels if d.get('is_headquarters_village')]
    if process_adls:
        process_add_or_remove_adl = ProcessAddOrRemoveADL(
            name = f"backup_db_facilitators_docs_{facilitator.no_sql_db_name}",
            move_from = "backup_db_facilitators_docs",
            move_to = facilitator.no_sql_db_name,
            administrative_levels = process_adls,
            query_action = "create"
        )
        process_add_or_remove_adl.save()

    # Unités géographiques, CVD et nombres de tâches du document du facilitateur (lus par le mobile)
    sync_geographicalunits_with_cvd_on_facilittor(
        project_id, facilitator.develop_mode, facilitator.training_mode, facilitator.no_sql_db_name
    )

    for p in projects or []:
        p.facilitators.add(facilitator)
        p.save()

    # Donne au User web de ce facilitator accès aux mêmes projets (Project.users), une fois Project.facilitators à
    # jour ci-dessus.
    sync_facilitator_user_projects(facilitator)

    for p in projects or []:
        try:
            nsc_database = nsc.get_db("process_design")
            project = nsc_database.get_query_result({"_id": p.couch_id})[0]

            fc_project = facilitator_database.get_query_result(
                {"type": "project", "name": project[0]['name']}
            )[0]

            # check if the project exists
            if not fc_project:
                # create the project on the facilitator database
                nsc.create_document(facilitator_database, project[0])
        except:
            pass

    # Sans stabilisation : les villages d'affectation y sont répliqués (et envoyés au MGP avec le compte).
    tree = tree or AdministrativeTree()
    before = facilitator_state(facilitator)
    if replicate_assignment_to_stabilization(facilitator, tree):
        creation.stabilization_replicated = True
        record_facilitator_changes(facilitator, before, 'facilitator_creation', sections=['stabilization'],
                                   changed_by=created_by, project_id=project_id)
        try:
            search_facilitators_db_with_villages_stabilized(project_name, no_sql_db=facilitator.no_sql_db_name)
        except Exception as exc:
            print(exc)

    require_password_change(email=facilitator.email, user=facilitator.user, facilitator=facilitator, created_by=created_by)

    creation.mgp_status, creation.mgp_detail = create_facilitator_on_mgp(facilitator, first_names, last_name)

    if facilitator.email:
        creation.mail_sent = send_account_credentials(
            facilitator.name, facilitator.email, username, password, facilitator=True, sex=facilitator.sex,
            localities=localities_rows(localities_summary(facilitator, tree)),
        )
    return creation


def localities_rows(rows):
    """Libellés traduits des localités du mail des identifiants."""
    from django.utils.translation import gettext as _

    labels = {'assignment': _("Assignment villages"), 'stabilization': _("Stabilization villages")}
    return [{'label': labels[row['label']], 'value': row['value']} for row in rows]
