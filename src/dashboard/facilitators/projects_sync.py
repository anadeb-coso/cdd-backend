"""Projets d'un facilitateur : lien en base (`Project.facilitators`) ↔ document CouchDB 'facilitator'
(`project_id` / `projects_ids` / `projects_names`).

Les pages du facilitateur (profil…) cherchent son document par le couch_id du projet de la session. Un
facilitateur rattaché à un projet en base sans que son document le soit (formulaire de projet, admin,
COSOMIS…) donnait « Page introuvable » : le document est donc complété à chaque rattachement, et la recherche
se replie sur le lien en base."""
import logging

from cloudant.document import Document

from no_sql_client import NoSQLClient

logger = logging.getLogger(__name__)


def find_facilitator_doc(facilitator_db, project_couch_id, facilitator=None, project_id=None):
    """Document 'facilitator' du projet (`project_id` ou `projects_ids`) ; à défaut, si le facilitateur est
    rattaché en base à ce projet, son document 'facilitator' quel qu'il soit. None si rien."""
    query_result = facilitator_db.get_query_result({
        "type": 'facilitator',
        "$or": [
            {"project_id": project_couch_id},
            {"projects_ids": {"$in": [project_couch_id]}},
        ]
    })[:]
    if query_result:
        return query_result[0]
    if facilitator is not None and project_id and facilitator.projects.filter(pk=project_id).exists():
        query_result = facilitator_db.get_query_result({"type": 'facilitator'})[:]
        if query_result:
            return query_result[0]
    return None


def missing_projects(facilitator, doc):
    """Projets liés en base absents du document (couch_id ni dans `projects_ids` ni en `project_id`)."""
    present = set(doc.get('projects_ids') or []) | {doc.get('project_id')}
    return [p for p in facilitator.projects.all() if p.couch_id and p.couch_id not in present]


def sync_facilitator_projects_to_couch(facilitator, apply=True, nsc=None):
    """Ajoute au document CouchDB les projets liés en base qui y manquent (rien n'est retiré). Renvoie la liste
    des projets ajoutés (ou à ajouter si apply=False)."""
    if not facilitator.no_sql_db_name:
        return []
    nsc = nsc or NoSQLClient()
    db = nsc.get_db(facilitator.no_sql_db_name)
    docs = db.get_query_result({"type": 'facilitator'})[:]
    if not docs:
        return []
    # Lecture fraîche (pas le cache du client) avant modification.
    doc = Document(db, docs[0]['_id'])
    doc.fetch()
    added = missing_projects(facilitator, doc)
    if added and apply:
        ids = list(doc.get('projects_ids') or [])
        names = list(doc.get('projects_names') or [])
        for p in added:
            ids.append(p.couch_id)
            if p.name not in names:
                names.append(p.name)
        doc['projects_ids'] = ids
        doc['projects_names'] = names
        if not doc.get('project_id'):
            doc['project_id'] = added[0].couch_id
            doc['project_name'] = added[0].name
        doc.save()
    return added


def sync_facilitators_projects_safely(facilitators):
    """Pour les signaux : une base CouchDB indisponible ne doit pas faire échouer l'enregistrement."""
    for facilitator in facilitators:
        try:
            sync_facilitator_projects_to_couch(facilitator)
        except Exception:
            logger.exception("Projets du facilitateur %s non reportés dans CouchDB", facilitator.pk)
