"""Localités d'un facilitateur : villages d'affectation (`administrative_levels` / `administrative_levels_ids`),
villages de stabilisation et additionnels (`stabilization_administrative_ids` / `additional_administrative_ids`)
avec les choix tels que saisis (`main_administrative_id`, `*_administrative_choices`).

Règles de calcul identiques au GRM (dashboard/adls/views.py::_administrative_ids et
authentication/utils.py::generate_administrative_regions_objects côté grm-backend) :
  - choisir un village rattaché à un CVD ajoute tous les villages de ce CVD ;
  - une région, préfecture, commune ou un canton est remplacé par les villages qu'il contient ;
  - "1" (TOGO) ne donne aucun village.
"""
from collections import defaultdict

from django.db.models import CharField
from django.db.models.functions import Cast
from django.utils.translation import gettext_lazy as _

from administrativelevels.models import AdministrativeLevel
from assignments.models import AssignAdministrativeLevelToFacilitator
from cdd.call_objects_from_other_db import mis_objects_call
from cdd.functions import exists_id_in_a_dict_by_project_and_cycle
from process_manager.models import ProcessAddOrRemoveADL, Project as CddProject
from subprojects.models import Project as MisProject

TOGO_ID = "1"
# Peuvent ouvrir la page « Localités » d'un facilitateur. « ADLAssigner » : même groupe que celui qui
# modifie les localités d'un EADL dans le GRM.
LOCALITIES_EDITOR_GROUPS = {"Admin", "FullStack", "Supervisor", "ADLAssigner"}
# Seuls à pouvoir modifier des villages d'affectation déjà renseignés.
ASSIGNMENT_OVERWRITE_GROUPS = {"Admin", "FullStack"}
# Peuvent attribuer leurs localités d'intervention aux utilisateurs (superviseurs surtout). Un superviseur ne
# modifie que les localités des facilitateurs : ADLAssigner ne lui donne pas ce droit (seuls Admin/FullStack/
# superutilisateur l'ont, cf. can_assign_user_localities).
USER_LOCALITIES_ASSIGNER_GROUPS = {"Admin", "FullStack", "ADLAssigner"}
USER_LOCALITIES_ASSIGNER_OVER_SUPERVISOR_GROUPS = {"Admin", "FullStack"}
LEVEL_TYPES_ORDER = ["Region", "Prefecture", "Commune", "Canton", "Village"]


def administrative_choices(ids):
    """Ids en entiers, sans doublon, ordre conservé (ids non numériques ignorés)."""
    choices = []
    for _id in ids or []:
        if str(_id).strip().isdigit() and int(_id) not in choices:
            choices.append(int(_id))
    return choices


# ---------------------------------------------------------------------------------------------
# Droits
# ---------------------------------------------------------------------------------------------

def _group_names(user):
    names = getattr(user, '_group_names', None)
    if names is None:
        names = user._group_names = {group.name for group in user.groups.all()}
    return names


def can_edit_localities(user):
    return bool(user.is_authenticated and (user.is_superuser or _group_names(user) & LOCALITIES_EDITOR_GROUPS))


def can_edit_assignment(user, facilitator, doc=None):
    """Villages d'affectation (initiaux) vides : tout éditeur de localités peut les renseigner ; déjà renseignés
    (dans CDD ou dans le document CouchDB `doc`) : seuls Admin, FullStack et superutilisateur peuvent les modifier
    — un superviseur, même ADLAssigner, ne le peut pas. Stabilisation et additionnelles : tout éditeur."""
    if not can_edit_localities(user):
        return False
    if facilitator.administrative_levels or (doc and doc.get('administrative_levels')):
        return bool(user.is_superuser or _group_names(user) & ASSIGNMENT_OVERWRITE_GROUPS)
    return True


def can_assign_user_localities(user):
    """Superutilisateur, Admin, FullStack, ADLAssigner — mais pas un superviseur (il ne modifie que les localités
    des facilitateurs), sauf s'il est aussi Admin, FullStack ou superutilisateur."""
    if not user.is_authenticated:
        return False
    groups = _group_names(user)
    if user.is_superuser or groups & USER_LOCALITIES_ASSIGNER_OVER_SUPERVISOR_GROUPS:
        return True
    return bool(groups & USER_LOCALITIES_ASSIGNER_GROUPS) and "Supervisor" not in groups


def can_assign_localities_of(user, account):
    """`can_assign_user_localities`, et jamais sa propre zone pour un superviseur. `account` : User ou id."""
    account_id = getattr(account, 'pk', account)
    if str(account_id) == str(user.pk) and is_supervisor(user):
        return False
    return can_assign_user_localities(user)


def can_view_localities_history(user):
    return can_edit_localities(user) or can_assign_user_localities(user)


def is_supervisor(user):
    return "Supervisor" in _group_names(user)


# ---------------------------------------------------------------------------------------------
# Arbre administratif (≈2 200 niveaux, une requête)
# ---------------------------------------------------------------------------------------------

class AdministrativeTree:

    def __init__(self):
        rows = mis_objects_call.get_all_objects(AdministrativeLevel).values_list('id', 'name', 'type', 'parent_id', 'cvd_id')
        self.levels = {row[0]: row for row in rows}
        self.children = defaultdict(list)
        self.cvd_members = defaultdict(list)
        for _id, name, _type, parent_id, cvd_id in rows:
            if parent_id:
                self.children[parent_id].append(_id)
            if cvd_id:
                self.cvd_members[cvd_id].append(_id)
        for ids in self.children.values():
            ids.sort()
        for ids in self.cvd_members.values():
            ids.sort()

    def type_of(self, _id):
        level = self.levels.get(_id)
        return level[2] if level else None

    def name_of(self, _id):
        if str(_id) == TOGO_ID and _id not in self.levels:
            return "TOGO"
        level = self.levels.get(int(_id)) if str(_id).isdigit() else None
        return level[1] if level else str(_id)

    def label(self, _id):
        """Même libellé que les formulaires EADL du GRM : « Type: Nom (Parent) »."""
        level = self.levels.get(_id)
        if not level:
            return str(_id)
        parent = self.levels.get(level[3])
        return f"{level[2]}: {level[1]} ({parent[1] if parent else 'TOGO'})"

    def expand_with_cvd(self, ids, main=None):
        """`_administrative_ids` du GRM : ajoute `main`, puis remplace chaque village rattaché à un CVD
        par tous les villages de ce CVD. Ordre conservé, sans doublon."""
        ids = administrative_choices(ids)
        main = int(main) if main is not None and str(main).isdigit() else None
        if main is not None and main not in ids:
            ids.append(main)
        expanded = []
        for _id in ids:
            level = self.levels.get(_id)
            for member in (self.cvd_members[level[4]] if level and level[4] else [_id]):
                if member not in expanded:
                    expanded.append(member)
        return expanded

    def villages(self, ids):
        """Villages contenus dans ces niveaux (un village donne lui-même ; "1" = TOGO ne donne rien)."""
        villages = []
        for _id in administrative_choices(ids):
            if str(_id) == TOGO_ID:
                continue
            stack = [_id]
            while stack:
                current = stack.pop(0)
                if self.type_of(current) == "Village":
                    if current not in villages:
                        villages.append(current)
                else:
                    stack.extend(self.children.get(current, []))
        return villages

    def label_of(self, _id):
        """`label`, ids texte ou entiers acceptés ; "1" = TOGO."""
        if str(_id) == TOGO_ID:
            return f"{_('Country')}: TOGO"
        return self.label(int(_id)) if str(_id).isdigit() else (str(_id) if _id else "-")

    def options(self, ids=None):
        """(id, libellé) triés par type (région -> village) puis nom ; `ids` restreint la liste."""
        ids = self.levels.keys() if ids is None else [i for i in ids if i in self.levels]
        rank = {t: n for n, t in enumerate(LEVEL_TYPES_ORDER)}
        return [
            (i, self.label(i))
            for i in sorted(ids, key=lambda i: (rank.get(self.levels[i][2], len(rank)), self.levels[i][1] or '', i))
        ]

    def ancestors_and_self(self, ids):
        result = set()
        for _id in ids:
            while _id and _id not in result:
                result.add(_id)
                level = self.levels.get(_id)
                _id = level[3] if level else None
        return result


def with_stabilization_localities(facilitators):
    """Facilitateurs ayant des localités de stabilisation/additionnelles, triés par nom, chacun complété
    de `administrative_regions_objects` (cantons -> villages, une seule requête) : lignes des modales
    « Facilitateurs techniques », lues dans CDD au lieu de l'API GRM."""
    import grm_client

    facilitators = sorted(
        (f for f in facilitators if f.stabilization_administrative_ids or f.additional_administrative_ids),
        key=lambda f: ((f.name or '').lower(), f.pk),
    )
    docs = grm_client.attach_administrative_regions_objects_bulk([
        (f.stabilization_administrative_ids or []) + (f.additional_administrative_ids or []) for f in facilitators
    ])
    for facilitator, doc in zip(facilitators, docs):
        facilitator.administrative_regions_objects = doc['administrative_regions_objects']
    return facilitators


# ---------------------------------------------------------------------------------------------
# Villages d'affectation : logique commune avec UpdateFacilitatorView
# ---------------------------------------------------------------------------------------------

def cdd_to_mis_projects():
    """Projet CDD (couch_id) -> id du projet du SIG (même nom)."""
    mis_projects = dict(mis_objects_call.filter_objects(MisProject).values_list('name', 'id'))
    return {p.couch_id: mis_projects.get(p.name) for p in CddProject.objects.all()}


def administrative_levels_to_unassign(kept, removed, default_project_mis_id, projects_mis_ids):
    """[(élément retiré, projet du SIG)] à désaffecter.

    Le projet est celui du village retiré (le formulaire d'édition affiche les villages de tous les projets), à
    défaut celui de la session ; rien n'est désaffecté si le village reste affecté dans ce projet sous un autre
    cycle (le SIG raisonne par projet). Fonction pure : aucune lecture ni écriture en base."""
    def project_of(elt):
        return projects_mis_ids.get(elt.get('project_id')) or default_project_mis_id

    remaining = {(str(e.get('id')), project_of(e)) for e in kept or []}
    result, seen = [], set()
    for adl in removed or []:
        if not str(adl.get('id')).isdigit():
            continue
        key = (str(adl['id']), project_of(adl))
        if key in remaining or key in seen:
            continue
        seen.add(key)
        result.append((adl, key[1]))
    return result


def headquarters_villages_to_move_out(removed, kept):
    """Villages sièges retirés dont les documents partent vers la base de sauvegarde : seulement ceux qui ne
    restent chez le facilitateur dans aucun projet ni cycle — le déplacement se fait par village, tous projets
    confondus : sinon le travail d'un autre projet partirait aussi. Fonction pure."""
    kept_ids = {str(e.get('id')) for e in kept or []}
    ids = []
    for d in removed or []:
        if d.get('is_headquarters_village') and str(d.get('id')) not in kept_ids and d.get('id') not in ids:
            ids.append(d.get('id'))
    return ids


def keep_other_projects_levels(submitted, old, current_project_couch_id):
    """Éléments soumis par le formulaire d'édition, complétés des villages des AUTRES projets qui en manquent :
    depuis la session d'un projet, on ne retire que les villages de ce projet. Fonction pure."""
    submitted = list(submitted or [])
    present = {(str(e.get('id')), e.get('project_id'), e.get('cycle_id')) for e in submitted}
    for elt in old or []:
        key = (str(elt.get('id')), elt.get('project_id'), elt.get('cycle_id'))
        if elt.get('project_id') != current_project_couch_id and key not in present:
            submitted.append(dict(elt))
            present.add(key)
    return submitted


def apply_administrative_levels(facilitator, administrative_levels_old, submitted_administrative_levels,
                                project_cdd, cycle_cdd, project_mis_id, project_name):
    """Calcule les villages d'affectation à partir des éléments soumis ({id, name, project_id,
    project_name, cycle_id, cycle_name}), puis affecte/désaffecte dans `AssignAdministrativeLevelToFacilitator`.
    Renvoie (_administrative_levels, administrative_levels_new, administrative_levels_remove)."""
    administrative_levels_old = administrative_levels_old or []
    administrative_levels_remove = []
    _administrative_levels = []
    administrative_levels_new = []

    if submitted_administrative_levels:

        project_mis = mis_objects_call.filter_objects(MisProject, name=project_name).first()
        villages_ids = [o.id for o in project_mis.administrative_levels.filter(type="Village")] if project_mis else []

        for elt in submitted_administrative_levels:
            administrativelevel_obj = AdministrativeLevel.objects.using('mis').filter(id=int(elt['id'])).first()
            if administrativelevel_obj:
                if administrativelevel_obj.cvd and administrativelevel_obj.cvd.headquarters_village and str(administrativelevel_obj.cvd.headquarters_village.id) == elt['id']:
                    elt['is_headquarters_village'] = True

                if elt.get("project_id") == project_cdd.couch_id and elt.get("cycle_id") == cycle_cdd.couch_id:
                    _elt = exists_id_in_a_dict_by_project_and_cycle(administrative_levels_old, elt.get('id'), elt.get('project_id'), elt.get('cycle_id'))
                    if not _elt: # Useless
                        # if project_mis and project_mis.administrative_levels.filter(id=int(elt['id'])).exists():
                        if int(elt['id']) in villages_ids:
                            elt["project_id"] = project_cdd.couch_id
                            elt["project_name"] = project_cdd.name
                            elt["cycle_id"] = cycle_cdd.couch_id
                            elt["cycle_name"] = cycle_cdd.name
                        administrative_levels_new.append(elt)

                    else:
                        elt["project_id"] = _elt["project_id"]
                        elt["project_name"] = _elt["project_name"]
                        elt["cycle_id"] = _elt["cycle_id"]
                        elt["cycle_name"] = _elt["cycle_name"]
                        # elt = _elt
                    # if not exists_id_in_a_dict_by_project_and_cycle(_administrative_levels, elt.get('id'), elt.get('project_id'), elt.get('cycle_id')):
                _administrative_levels.append(elt)


    for ad in administrative_levels_old:
        if ad.get('id') and not exists_id_in_a_dict_by_project_and_cycle(_administrative_levels, ad.get('id'), ad.get('project_id'), ad.get('cycle_id')):
            administrative_levels_remove.append(ad)

    #Assign ADL
    for adl in administrative_levels_new:
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

    #Unassign ADL
    # Chaque village retiré est désaffecté dans SON projet (pas celui de la session), s'il n'y reste pas sous un
    # autre cycle, et seulement la ligne de CE facilitateur : sans ce filtre, retirer un village qu'il n'avait pas
    # dans le SIG (déjà affecté à un autre à l'ajout, donc aucune ligne créée) désactivait l'affectation de l'autre.
    # `facilitator_id` : IntegerField dans le modèle, colonne texte dans la base unifiée -> comparer en texte.
    for adl, unassign_project_mis_id in administrative_levels_to_unassign(
        _administrative_levels, administrative_levels_remove, project_mis_id, cdd_to_mis_projects()
    ):
        assign = AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(
            administrative_level_id=int(adl['id']), project_id=unassign_project_mis_id, activated=True,
        ).annotate(_facilitator_id=Cast('facilitator_id', output_field=CharField())).filter(
            _facilitator_id=str(facilitator.id)
        ).first()
        if assign:
                try:
                    assign.activated = False
                    assign.save(using='mis')
                except Exception as exc:
                    print(exc)
    #End Unassign ADL

    return _administrative_levels, administrative_levels_new, administrative_levels_remove


def schedule_administrative_levels_documents_moves(facilitator_db_name, administrative_levels_new, administrative_levels_remove,
                                                   kept_administrative_levels=None):
    """Planifie le déplacement des documents CouchDB des villages sièges ajoutés (backup -> base du
    facilitateur) et retirés (base du facilitateur -> backup) ; un village retiré qui reste chez le facilitateur
    dans un autre projet ou cycle (`kept_administrative_levels`) garde ses documents."""
    process_adls = [d.get('id') for d in administrative_levels_new if d.get('is_headquarters_village')]
    if process_adls:
        process_add_or_remove_adl = ProcessAddOrRemoveADL(
            name = f"backup_db_facilitators_docs_{facilitator_db_name}",
            move_from = "backup_db_facilitators_docs",
            move_to = facilitator_db_name,
            administrative_levels = process_adls,
            query_action = "update"
        )
        process_add_or_remove_adl.save()

    process_adls = headquarters_villages_to_move_out(administrative_levels_remove, kept_administrative_levels)
    if process_adls:
        process_add_or_remove_adl = ProcessAddOrRemoveADL(
            name = f"{facilitator_db_name}_backup_db_facilitators_docs",
            move_from = facilitator_db_name,
            move_to = "backup_db_facilitators_docs",
            administrative_levels = process_adls,
            query_action = "update"
        )
        process_add_or_remove_adl.save()


# ---------------------------------------------------------------------------------------------
# Page « Localités » : calcul (aperçu) puis application
# ---------------------------------------------------------------------------------------------

class LocalitiesChange:
    """Résultat calculé d'une saisie, comparé à l'état actuel ; rien n'est écrit tant que `apply`
    n'est pas appelé (confirmation de l'utilisateur)."""

    def __init__(self, tree, facilitator, doc, user, project_cdd, cycle_cdd, project_mis,
                 submitted_assignment, submitted_stabilization, submitted_additional):
        self.tree = tree
        self.facilitator = facilitator
        self.doc = doc
        self.project_cdd = project_cdd
        self.cycle_cdd = cycle_cdd
        self.project_mis = project_mis
        self.errors = []
        self.warnings = []

        self.can_edit_assignment = can_edit_assignment(user, facilitator, doc)

        # --- Villages d'affectation (projet/cycle courants uniquement) ---------------------------
        self.old_levels = list(doc.get('administrative_levels') or []) if doc else list(facilitator.administrative_levels or [])
        current = lambda elt: elt.get('project_id') == project_cdd.couch_id and elt.get('cycle_id') == cycle_cdd.couch_id
        self.old_assignment = administrative_choices(elt.get('id') for elt in self.old_levels if current(elt))
        self.project_villages = set(project_mis.administrative_levels.filter(type="Village").values_list('id', flat=True)) if project_mis else set()

        if submitted_assignment is None or not self.can_edit_assignment:
            self.new_assignment = list(self.old_assignment)
            self.assignment_changed = False
        else:
            chosen = administrative_choices(submitted_assignment)
            villages = tree.villages(tree.expand_with_cvd(chosen))
            outside_project = [v for v in villages if v not in self.project_villages]
            if outside_project:
                self.warnings.append(_("%(n)s village(s) outside the project ignored for the assignment: %(names)s") % {
                    'n': len(outside_project), 'names': self._names(outside_project)})
            self.new_assignment = [v for v in villages if v in self.project_villages]
            self.assignment_changed = set(self.new_assignment) != set(self.old_assignment)
            assigned_elsewhere = self._assigned_to_others(set(self.new_assignment) - set(self.old_assignment))
            if assigned_elsewhere:
                self.warnings.append(_("Already assigned to another facilitator in this project (MIS assignment unchanged for these villages): %(names)s") % {
                    'names': self._names(assigned_elsewhere)})

        other_projects_ids = [int(elt['id']) for elt in self.old_levels if not current(elt) and str(elt.get('id')).isdigit()]
        self.new_administrative_levels_ids = administrative_choices(other_projects_ids + self.new_assignment)

        # --- Stabilisation (niveau principal = 1er choisi) --------------------------------------
        self.old_main = facilitator.main_administrative_id
        self.old_stabilization_choices = self._current_choices(facilitator.stabilization_administrative_choices, facilitator.stabilization_administrative_ids, self.old_main)
        self.old_stabilization = administrative_choices(facilitator.stabilization_administrative_ids)
        stabilization = self.old_stabilization_choices if submitted_stabilization is None else administrative_choices(submitted_stabilization)
        self.copied_from_assignment = False
        if not stabilization and self.new_administrative_levels_ids:
            stabilization = list(self.new_administrative_levels_ids)
            self.copied_from_assignment = True
        self.new_main = str(stabilization[0]) if stabilization else None
        self.new_stabilization_choices = tree.expand_with_cvd(stabilization, self.new_main)
        self.new_stabilization = tree.villages(self.new_stabilization_choices)

        # --- Localités additionnelles -------------------------------------------------------------
        self.old_additional_choices = self._current_choices(facilitator.additional_administrative_choices, facilitator.additional_administrative_ids)
        self.old_additional = administrative_choices(facilitator.additional_administrative_ids)
        additional = self.old_additional_choices if submitted_additional is None else administrative_choices(submitted_additional)
        self.new_additional_choices = tree.expand_with_cvd(additional)
        self.new_additional = tree.villages(self.new_additional_choices)

        self.stabilization_changed = (
            set(self.new_stabilization) != set(self.old_stabilization)
            or set(self.new_additional) != set(self.old_additional)
            or (self.new_main or None) != (self.old_main or None)
            or self.new_stabilization_choices != administrative_choices(facilitator.stabilization_administrative_choices)
            or self.new_additional_choices != administrative_choices(facilitator.additional_administrative_choices)
        )

    # -- helpers ----------------------------------------------------------------------------------

    @staticmethod
    def _current_choices(choices, villages, main=None):
        current = administrative_choices(choices) or administrative_choices(villages)
        if main is not None and str(main).isdigit():
            current = [int(main)] + [c for c in current if c != int(main)]
        return current

    def _names(self, ids, limit=15):
        names = [self.tree.name_of(i) for i in ids]
        return ", ".join(names[:limit]) + (f" … (+{len(names) - limit})" if len(names) > limit else "")

    def _assigned_to_others(self, village_ids):
        if not village_ids or not self.project_mis:
            return []
        return sorted(mis_objects_call.filter_objects(
            AssignAdministrativeLevelToFacilitator, administrative_level_id__in=village_ids,
            project_id=self.project_mis.id, activated=True,
        # `facilitator_id` : IntegerField dans le modèle, colonne texte dans la base unifiée -> comparer en texte
        ).annotate(_facilitator_id=Cast('facilitator_id', output_field=CharField())).exclude(
            _facilitator_id=str(self.facilitator.id)
        ).values_list('administrative_level_id', flat=True))

    def diff(self, old, new):
        return {
            'before': len(old), 'after': len(new),
            'added': self._names([v for v in new if v not in old]), 'added_count': len([v for v in new if v not in old]),
            'removed': self._names([v for v in old if v not in new]), 'removed_count': len([v for v in old if v not in new]),
        }

    def summary(self):
        return {
            'assignment': self.diff(self.old_assignment, self.new_assignment),
            'stabilization': self.diff(self.old_stabilization, self.new_stabilization),
            'additional': self.diff(self.old_additional, self.new_additional),
            'main_before': self.tree.label_of(self.old_main),
            'main_after': self.tree.label_of(self.new_main),
            'stabilization_choices': [self.tree.label(c) for c in self.new_stabilization_choices],
            'additional_choices': [self.tree.label(c) for c in self.new_additional_choices],
            'copied_from_assignment': self.copied_from_assignment,
            'changed': self.assignment_changed or self.stabilization_changed,
        }

    def new_administrative_levels_elements(self):
        """Éléments `administrative_levels` à soumettre : autres projets/cycles inchangés + villages
        du projet/cycle courants."""
        current = lambda elt: elt.get('project_id') == self.project_cdd.couch_id and elt.get('cycle_id') == self.cycle_cdd.couch_id
        elements = [dict(elt) for elt in self.old_levels if not current(elt)]
        for village_id in self.new_assignment:
            elements.append({
                "name": self.tree.name_of(village_id), "id": str(village_id),
                "project_id": self.project_cdd.couch_id, "project_name": self.project_cdd.name,
                "cycle_id": self.cycle_cdd.couch_id, "cycle_name": self.cycle_cdd.name,
            })
        return elements


# ---------------------------------------------------------------------------------------------
# Localités d'intervention des utilisateurs (superviseurs surtout)
# ---------------------------------------------------------------------------------------------

def user_display_name(user):
    """NOM Prénom (même format que les facilitateurs), à défaut le nom d'utilisateur."""
    return f"{user.last_name or ''} {user.first_name or ''}".strip() or user.username


def user_localities_state(record):
    """État enregistré d'un utilisateur : (principal, choix, villages, choix additionnels, villages additionnels)."""
    if record is None:
        return None, [], [], [], []
    main = record.administrative_id
    return (
        main,
        LocalitiesChange._current_choices(record.administrative_choices, record.village_ids, main),
        administrative_choices(record.village_ids),
        LocalitiesChange._current_choices(record.additional_administrative_choices, record.additional_village_ids),
        administrative_choices(record.additional_village_ids),
    )


def describe_user_zone(tree, account, record):
    """Libellé des localités d'intervention : « Tout le pays », les niveaux choisis ou « Aucune »."""
    main, choices, villages, additional_choices, additional = user_localities_state(record)
    if main == TOGO_ID or (not choices and not additional and not is_supervisor(account)):
        return _("Whole country (TOGO)")
    labels = [tree.label_of(c) for c in choices + [c for c in additional_choices if c not in choices]]
    return ", ".join(labels) if labels else _("None")


class UserLocalitiesChange:
    """Localités d'intervention d'un utilisateur : même calcul que la stabilisation d'un facilitateur
    (1er choix = niveau principal, extension au CVD, descente aux villages). TOGO choisi, ou aucun
    choix pour un non-superviseur = tout le pays ("1", comme les comptes GRM du personnel)."""

    def __init__(self, tree, account, record, submitted_intervention=None, submitted_additional=None):
        self.tree = tree
        self.account = account
        self.record = record
        self.supervisor = is_supervisor(account)
        self.errors = []
        self.warnings = []

        (self.old_main, self.old_choices, self.old_villages,
         self.old_additional_choices, self.old_additional) = user_localities_state(record)

        chosen = self.old_choices if submitted_intervention is None else administrative_choices(submitted_intervention)
        additional = self.old_additional_choices if submitted_additional is None else administrative_choices(submitted_additional)

        self.whole_country = int(TOGO_ID) in chosen or (not chosen and not additional and not self.supervisor)
        if self.whole_country:
            if len(chosen) > 1 or additional:
                self.warnings.append(_("Whole country chosen: the other choices are ignored."))
            self.new_main, self.new_choices, self.new_villages = TOGO_ID, [], []
            self.new_additional_choices, self.new_additional = [], []
        else:
            if not chosen and self.supervisor:
                self.warnings.append(_("Without intervention localities, this supervisor will no longer have access to the dashboard data."))
            self.new_main = str(chosen[0]) if chosen else None
            self.new_choices = tree.expand_with_cvd(chosen, self.new_main)
            self.new_villages = tree.villages(self.new_choices)
            self.new_additional_choices = tree.expand_with_cvd(additional)
            self.new_additional = tree.villages(self.new_additional_choices)

        self.changed = (
            record is None
            or (self.new_main or None) != (self.old_main or None)
            or set(self.new_choices) != set(administrative_choices(record.administrative_choices))
            or set(self.new_additional_choices) != set(administrative_choices(record.additional_administrative_choices))
            or set(self.new_villages) != set(self.old_villages)
            or set(self.new_additional) != set(self.old_additional)
        )

    def _names(self, ids, limit=15):
        names = [self.tree.name_of(i) for i in ids]
        return ", ".join(names[:limit]) + (f" … (+{len(names) - limit})" if len(names) > limit else "")

    def diff(self, old, new):
        return LocalitiesChange.diff(self, old, new)

    def summary(self):
        return {
            'intervention': self.diff(self.old_villages, self.new_villages),
            'intervention_additional': self.diff(self.old_additional, self.new_additional),
            'main_before': self.tree.label_of(self.old_main) if self.record else _("Not defined"),
            'main_after': self.tree.label_of(self.new_main),
            'choices': [self.tree.label_of(c) for c in self.new_choices] or ([self.tree.label_of(TOGO_ID)] if self.whole_country else []),
            'additional_choices': [self.tree.label_of(c) for c in self.new_additional_choices],
            'whole_country': self.whole_country,
            'changed': self.changed,
        }


def all_canton_ids():
    return [str(_id) for _id in mis_objects_call.filter_objects(AdministrativeLevel, type="Canton").values_list('id', flat=True)]


def supervisor_canton_ids(user):
    """Cantons de la zone d'un superviseur (`session['cantons_stabilized_ids']`) d'après ses localités
    d'intervention enregistrées dans CDD : cantons parents de ses villages, comme le faisait la lecture de
    son EADL dans le GRM ; tout le pays = tous les cantons. None : aucune localité enregistrée dans CDD
    (l'appelant se replie alors sur le GRM)."""
    import grm_client
    from authentication.models import UserLocalities

    record = UserLocalities.objects.filter(user=user).first()
    if record is None:
        return None
    if record.administrative_id == TOGO_ID:
        return all_canton_ids()
    administrative_regions_objects = grm_client.attach_administrative_regions_objects(
        (record.village_ids or []) + (record.additional_village_ids or [])
    ).get('administrative_regions_objects')
    return list(set(
        str(ad['id']) for ad in (administrative_regions_objects or []) if ad and type(ad) is dict and 'id' in ad
    ))


# ---------------------------------------------------------------------------------------------
# Changement de zone d'un superviseur connecté : déconnexion à sa requête suivante
# ---------------------------------------------------------------------------------------------

ZONE_CHANGED_SESSION_KEY = 'intervention_zone_changed'


def flag_sessions_for_zone_change(user, exclude_session_key=None):
    """Marque les sessions CDD ouvertes de `user` (celles qui portent un projet choisi, donc une zone) : à sa
    requête suivante, il est déconnecté (authentication.middleware.ZoneChangeLogoutMiddleware) et sa nouvelle
    zone sera calculée au choix du projet. Renvoie le nombre de sessions marquées.

    La table django_session est partagée avec le SIG, dont les sessions sont signées avec une autre SECRET_KEY :
    elles sont décodées sans `get_decoded()`, qui journaliserait « Session data corrupted » pour chacune."""
    from django.contrib.sessions.backends.db import SessionStore
    from django.contrib.sessions.models import Session
    from django.core import signing
    from django.utils import timezone

    decoder = SessionStore()
    count = 0
    for session in Session.objects.filter(expire_date__gt=timezone.now()):
        if session.session_key == exclude_session_key:
            continue
        try:
            data = signing.loads(session.session_data, salt=decoder.key_salt, serializer=decoder.serializer)
        except signing.BadSignature:
            continue  # session du SIG (autre clé) ou illisible : jamais modifiée
        if data.get('_auth_user_id') != str(user.pk) or 'project_couch_id' not in data or data.get(ZONE_CHANGED_SESSION_KEY):
            continue
        store = SessionStore(session_key=session.session_key)
        store[ZONE_CHANGED_SESSION_KEY] = True
        store.save()
        count += 1
    return count
