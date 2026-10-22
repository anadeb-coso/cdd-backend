"""Enregistrement des localités d'un facilitateur : commun à la page « Localités », au formulaire de
modification, à la création et à l'import Excel des affectations.

Règle : un facilitateur sans localités de stabilisation reçoit ses villages d'affectation (localités initiales)
comme stabilisation ; la stabilisation et les localités additionnelles sont ensuite envoyées au MGP (compte de
même e-mail), et le facilitateur reçoit un mail récapitulant les changements."""
from no_sql_client import NoSQLClient

from .localities import AdministrativeTree, LocalitiesChange, administrative_choices, apply_administrative_levels, \
    schedule_administrative_levels_documents_moves


def has_stabilization(facilitator):
    """Même critère que la page « Localités » (choix, villages ou niveau principal déjà renseignés)."""
    return bool(LocalitiesChange._current_choices(
        facilitator.stabilization_administrative_choices, facilitator.stabilization_administrative_ids,
        facilitator.main_administrative_id,
    ))


def replicate_assignment_to_stabilization(facilitator, tree=None):
    """Sans stabilisation : stabilisation = villages d'affectation (niveau principal = 1er village, extension aux
    villages du CVD), comme la copie faite par la page « Localités ». Enregistre ; renvoie True si appliqué."""
    assignment = administrative_choices(facilitator.administrative_levels_ids)
    if not assignment or has_stabilization(facilitator):
        return False
    tree = tree or AdministrativeTree()
    main = str(assignment[0])
    facilitator.main_administrative_id = main
    facilitator.stabilization_administrative_choices = tree.expand_with_cvd(assignment, main)
    facilitator.stabilization_administrative_ids = tree.villages(facilitator.stabilization_administrative_choices)
    facilitator.simple_save()
    return True


def send_stabilization_to_grm(facilitator):
    """Stabilisation et localités additionnelles vers le compte MGP de même e-mail. (ok, détail) ; ok None :
    pas d'e-mail, rien n'est envoyé."""
    import grm_client

    if not (facilitator.email or '').strip():
        return None, "no email"
    return grm_client.update_localities_on_grm(
        facilitator.email, facilitator.main_administrative_id,
        facilitator.stabilization_administrative_choices or [], facilitator.additional_administrative_choices or [],
    )


def apply_facilitator_localities(change, facilitator, facilitator_db, doc, project_id, project_name, history, source):
    """Applique un `LocalitiesChange` calculé (aperçu confirmé) : villages d'affectation (affectations SIG,
    document CouchDB, déplacements de documents, unités géographiques), puis stabilisation/additionnelles
    (accès aux bases des autres facilitateurs, envoi au MGP). `history` : changed_by, changed_at, project_id…
    Renvoie {'events': lignes d'historique créées, 'grm': (ok, détail) | None, 'databases_error': str | None}."""
    from dashboard.utils import search_facilitators_db_with_villages_stabilized, sync_geographicalunits_with_cvd_on_facilittor
    from .localities_history import facilitator_state, record_facilitator_changes

    result = {'events': [], 'grm': None, 'databases_error': None}
    before = facilitator_state(facilitator)

    if change.assignment_changed:
        _administrative_levels, administrative_levels_new, administrative_levels_remove = apply_administrative_levels(
            facilitator, change.old_levels, change.new_administrative_levels_elements(),
            change.project_cdd, change.cycle_cdd, change.project_mis.id if change.project_mis else 1, project_name,
        )
        facilitator.administrative_levels = _administrative_levels
        facilitator.administrative_levels_ids = [int(_adl['id']) for _adl in _administrative_levels]
        facilitator.simple_save()
        if doc:
            # `update_doc_uncontrolled` : une liste vidée doit aussi l'être dans CouchDB.
            NoSQLClient().update_doc_uncontrolled(facilitator_db, doc['_id'], {"administrative_levels": _administrative_levels})
        schedule_administrative_levels_documents_moves(facilitator.no_sql_db_name, administrative_levels_new, administrative_levels_remove,
                                                       kept_administrative_levels=_administrative_levels)
        sync_geographicalunits_with_cvd_on_facilittor(
            project_id, facilitator.develop_mode, facilitator.training_mode, facilitator.no_sql_db_name
        )
        result['events'] += record_facilitator_changes(facilitator, before, source, sections=['assignment'], **history)

    if change.stabilization_changed:
        facilitator.main_administrative_id = change.new_main
        facilitator.stabilization_administrative_choices = change.new_stabilization_choices
        facilitator.stabilization_administrative_ids = change.new_stabilization
        facilitator.additional_administrative_choices = change.new_additional_choices
        facilitator.additional_administrative_ids = change.new_additional
        facilitator.simple_save()
        result['events'] += record_facilitator_changes(facilitator, before, source, sections=['stabilization', 'additional'], **history)
        try:
            # Bases CouchDB des facilitateurs affectés à ces villages (même traitement que l'envoi du GRM).
            search_facilitators_db_with_villages_stabilized(project_name, no_sql_db=facilitator.no_sql_db_name)
        except Exception as exc:
            result['databases_error'] = str(exc)
        result['grm'] = send_stabilization_to_grm(facilitator)

    return result
