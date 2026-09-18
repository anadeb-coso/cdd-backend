import json

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from no_sql_client import NoSQLClient
from dashboard.administrative_levels.views_adl import build_admin_level_planning_cycle


def _resolve_owner_db(nsc, village_id, own_db, own_db_name, no_sql_dbs_names_with_village_ids):
    """Le village siege d'une CVD de stabilisation appartient a un AUTRE
    facilitateur (cf. get_search_for_stabilized_facilitator_dbs) - ses
    documents CouchDB ne sont pas dans own_db. Meme convention de resolution
    que administrative_level_list.html (lien construit avec cvd.last_facilitator,
    pas avec l'id de la page)."""
    for db_name, info in (no_sql_dbs_names_with_village_ids or {}).items():
        if str(village_id) in [str(i) for i in info.get('ids', [])]:
            return nsc.get_db(db_name), db_name
    return own_db, own_db_name


def list_cvds_with_overview(request, own_db, own_db_name, cvds, no_sql_dbs_names_with_village_ids):
    """Une entree par CVD (propres + stabilisation, deja fusionnees et triees
    par FacilitatorMixin.dispatch dans `cvds`). Le diagnostic d'une CVD est
    celui de son seul village siege - meme convention que SelectVillage.tsx
    cote mobile (tasks_stats[village_siege.id]), pas une agregation sur tous
    les villages du groupe. Un seul appel CouchDB par CVD."""
    nsc = NoSQLClient()
    results = []
    for cvd in cvds:
        village_id = cvd.get('village_id')
        if not village_id:
            continue
        db, db_name = _resolve_owner_db(
            nsc, village_id, own_db, own_db_name, no_sql_dbs_names_with_village_ids
        )
        _phases, overview = build_admin_level_planning_cycle(request, db, village_id)
        results.append({
            'cvd': cvd,
            'village_id': village_id,
            'db_name': db_name,
            'overview': overview,
        })
    return results


# ---------------------------------------------------------------------------
# E7 — remplissage web d'une tâche : résolution du doc + sauvegarde avec piste
# d'audit, miroir de `insertTaskToLocalDb` (mobile TaskDetail.tsx ~L1258-1483).
# ---------------------------------------------------------------------------

def resolve_task_doc(nsc, request, no_sql_db_name, administrative_level_id, sql_id):
    """Résout (db, doc, found_db_name) pour (no_sql_db_name, administrative_level_id,
    sql_id) — même sélecteur/repli cross-facilitateur que
    AdministrativeLevelTaskDetailAjaxView. Le doc est re-fetché via `db[doc_id]`
    (accès crochet, pas le dict brut renvoyé par la requête Mango) pour
    "chauffer" le cache local de l'objet `db` AVANT toute écriture — sans ça,
    `update_doc_uncontrolled` (no_sql_client.py, `db.get(id)` = lookup dict
    LOCAL, pas un fetch réseau) échoue silencieusement (cf. docstring de
    `dashboard.utils._find_facilitator_task_doc`, même piège, déjà rencontré
    et corrigé sur ce chemin de repli — le chemin PRINCIPAL ci-dessous devait
    déjà l'appliquer lui aussi, jamais vérifié avant faute d'écriture sur ce
    chemin jusqu'ici)."""
    db = nsc.get_db(no_sql_db_name)
    selector = {"type": "task", "administrative_level_id": str(administrative_level_id)}
    try:
        selector["sql_id"] = int(sql_id)
    except (TypeError, ValueError):
        selector["sql_id"] = sql_id
    if request.session.get("project_couch_id"):
        selector["project_id"] = request.session.get("project_couch_id")
    if request.session.get("cycle_couch_id"):
        selector["cycle_id"] = request.session.get("cycle_couch_id")

    doc = None
    try:
        rows = list(db.get_query_result(selector))
        if rows:
            doc = db[rows[0]['_id']]
    except Exception as exc:  # noqa: BLE001
        print(f"[task_cycle] resolve_task_doc CouchDB KO: {exc}")
        doc = None

    if doc is not None:
        return db, doc, no_sql_db_name

    from dashboard.utils import _find_facilitator_task_doc
    try:
        task_sql_id = int(sql_id)
    except (TypeError, ValueError):
        task_sql_id = sql_id
    other_facilitator, other_db, other_doc = _find_facilitator_task_doc(
        nsc, request.session.get('project_id'), task_sql_id, administrative_level_id,
        request.session.get('cycle_id'),
    )
    if other_doc is not None:
        return other_db, other_doc, other_facilitator.no_sql_db_name
    return db, None, no_sql_db_name


def _facilitator_identity(request):
    """Identité de l'utilisateur web courant pour la piste d'audit — même
    forme que le sous-objet `facilitator` posé par mobile (name/email/phone/
    sex/sql_id/type). Utilise `Facilitator.user` (OneToOne) s'il existe,
    sinon replie sur les infos du `User` Django (ex. staff remplissant pour
    le compte d'un facilitateur)."""
    facilitator = getattr(request.user, 'facilitator', None)
    if facilitator:
        return {
            'name': facilitator.name, 'email': facilitator.email, 'phone': facilitator.phone,
            'sex': getattr(facilitator, 'sex', None), 'sql_id': facilitator.id,
            'type': facilitator.facilitator_type,
        }
    return {
        'name': request.user.get_full_name() or request.user.username,
        'email': request.user.email, 'phone': '', 'sex': None, 'sql_id': None, 'type': None,
    }


def _json_eq(a, b):
    try:
        return json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)
    except TypeError:
        return a == b


def diff_form_pages(old_form_response, new_values):
    """Diffe chaque page (comparaison superficielle champ par champ, comme
    `insertTaskToLocalDb` sur `form_response[currentPage]`) — seule
    différence avec mobile : mobile ne sauvegarde/diffe QUE la page courante
    (navigation = sauvegarde immédiate) ; ici toutes les pages sont envoyées
    en un seul appel web, donc chacune est diffée, préfixée par son numéro
    UNIQUEMENT si le formulaire a plusieurs pages (repli sur la clé nue pour
    un formulaire mono-page, identique à mobile)."""
    old_pages = old_form_response or []
    multi = len(new_values) > 1
    fields_updated = []
    fields_updated_response = {}
    for page_index, new_page in enumerate(new_values):
        if not isinstance(new_page, dict):
            continue
        old_page = old_pages[page_index] if page_index < len(old_pages) and isinstance(old_pages[page_index], dict) else {}
        for key, value in new_page.items():
            old_value = old_page.get(key)
            if not _json_eq(old_value, value):
                label = f"page{page_index + 1}.{key}" if multi else key
                fields_updated.append(label)
                fields_updated_response[label] = {"old": old_value, "new": value}
    return fields_updated, fields_updated_response


def diff_attachments(old_attachments, new_attachments):
    """Diffe les pièces jointes par position (comme `insertTaskToLocalDb`,
    ~L1317-1329 : `doc.attachments[i].attachment.uri !== task.attachments[i].
    attachment.uri`). Renvoie (attachments_updated: [nom...],
    attachments_updated_response: {nom: {old,new}})."""
    old_list = old_attachments or []
    new_list = new_attachments or []
    attachments_updated = []
    attachments_updated_response = {}
    for i, new_att in enumerate(new_list):
        if not isinstance(new_att, dict):
            continue
        old_att = old_list[i] if i < len(old_list) and isinstance(old_list[i], dict) else {}
        old_uri = (old_att.get('attachment') or {}).get('uri')
        new_uri = (new_att.get('attachment') or {}).get('uri')
        if old_uri != new_uri:
            name = new_att.get('name') or old_att.get('name') or f"attachment{i + 1}"
            attachments_updated.append(name)
            attachments_updated_response[name] = {'old': old_uri, 'new': new_uri}
    return attachments_updated, attachments_updated_response


def save_task_form(request, doc, db, found_db_name, new_values, new_attachments=None):
    """Sauvegarde `new_values` (form_response complet, toutes pages) + les
    pièces jointes éventuelles dans le doc CouchDB déjà résolu
    (`resolve_task_doc`), avec piste d'audit — miroir de `insertTaskToLocalDb`
    (TaskDetail.tsx). Déclenche l'email "tâche invalidée reprise" (même vue
    que mobile, `cdd.views_api_send_mail.send_invalidation_reviewed_mail`,
    appelée directement en Python plutôt que via un aller-retour HTTP) si le
    doc était invalidé ET qu'un champ ou une pièce jointe a réellement changé.

    **Écart volontaire avec mobile** : `insertTaskToLocalDb` (~L1317-1329)
    déclenche `updated_after_invalidation=True`+email sur un simple
    changement de pièce jointe, SANS vérifier `validated===false` (contrairement
    au bloc juste après pour les champs de formulaire, ~L1354) — en pratique
    l'email planterait sans `action_by` (tâche jamais invalidée). Ici les
    changements de pièces jointes sont traités EXACTEMENT comme les champs de
    formulaire (gate unique `was_invalidated`), plus sûr et cohérent, sans
    rien perdre du comportement réellement voulu (notifier après reprise d'une
    tâche invalidée). Renvoie {ok, message, mail_sent, mail_message}."""
    if doc.get('validated') is True:
        return {
            'ok': False,
            'message': str(_("This task has already been validated — changes can no longer be saved.")),
        }

    identity = _facilitator_identity(request)
    fields_updated, fields_updated_response = diff_form_pages(doc.get('form_response'), new_values)
    attachments_updated, attachments_updated_response = (
        diff_attachments(doc.get('attachments'), new_attachments) if new_attachments is not None else ([], {})
    )

    now_str = timezone.now().strftime('%Y-%m-%d %H:%M:%S')

    users_involved = list(doc.get('users_involved_in_task') or [])
    found = False
    for u in users_involved:
        if u.get('email') == identity['email']:
            u['last_intervention_date'] = now_str
            found = True
            break
    if not found:
        users_involved.append(dict(identity, first_intervention_date=now_str, last_intervention_date=now_str))

    updates = {
        'form_response': new_values,
        'last_updated': now_str,
        'users_involved_in_task': users_involved,
    }
    if new_attachments is not None:
        updates['attachments'] = new_attachments

    was_invalidated = doc.get('validated') is False
    something_changed = bool(fields_updated) or bool(attachments_updated)
    if something_changed:
        history_entry = {
            'facilitator': dict(
                identity,
                fields_updated_response=fields_updated_response,
                fields_updated=fields_updated,
                attachments_updated=attachments_updated,
                attachments_updated_response=attachments_updated_response,
                page=None,
            ),
            'date': now_str,
        }
        updated_history = list(doc.get('updated_history') or [])
        updated_history.append(history_entry)
        updates['updated_history'] = updated_history

        if was_invalidated:
            updates['updated_after_invalidation'] = True
            updated_after_invalidation_history = list(doc.get('updated_after_invalidation_history') or [])
            updated_after_invalidation_history.append(history_entry)
            updates['updated_after_invalidation_history'] = updated_after_invalidation_history

    NoSQLClient().update_doc_uncontrolled(db, doc['_id'], updates)

    mail_sent = False
    mail_message = None
    if something_changed and was_invalidated and doc.get('action_by'):
        from cdd.views_api_send_mail import send_invalidation_reviewed_mail
        merged_doc = dict(doc)
        merged_doc.update(updates)
        mail_sent, mail_message = send_invalidation_reviewed_mail(
            request, merged_doc, identity, fields_updated, attachments_updated, found_db_name
        )

    return {'ok': True, 'message': None, 'mail_sent': mail_sent, 'mail_message': mail_message}
