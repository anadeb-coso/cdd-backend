"""Téléchargement des documents générés à partir d'une tâche (``Task.generated_document``).

- Web : ``village-profile/download/?db=<base facilitateur>&administrative_level=<id>&task=<sql_id>&format=docx|pdf``
  (ou ``&doc=<_id CouchDB>``) — lit la réponse dans la base du facilitateur (repli sur les autres
  facilitateurs du projet, comme le détail de tâche).
- Mobile : ``village-profile/api/`` (POST JSON : identifiant + jeton, ``task_sql_id``,
  ``administrative_level_id``, ``form_response``, ``format``) — réponses envoyées par le téléphone, même non
  synchronisées ; renvoie le fichier en base64.
"""
import base64
import json

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from authentication.models import Facilitator
from cdd.my_librairies.doc_convert import DocConversionError, docx_bytes_to_pdf_bytes
from no_sql_client import NoSQLClient
from process_manager.models import Task

from .village_profile import build_meta, build_village_profile_docx, file_name

MIME = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}


def _task_allows_village_profile(sql_id):
    try:
        return Task.objects.filter(
            id=int(sql_id), generated_document=Task.GENERATED_DOCUMENT_VILLAGE_PROFILE
        ).exists()
    except (TypeError, ValueError):
        return False


def render_village_profile(form_response, meta, fmt):
    """(octets, nom de fichier, type MIME) ; lève DocConversionError si le PDF est impossible."""
    fmt = "pdf" if fmt == "pdf" else "docx"
    content = build_village_profile_docx(form_response, meta)
    if fmt == "pdf":
        content = docx_bytes_to_pdf_bytes(content)
    return content, file_name(meta, fmt), MIME[fmt]


def _doc_date(doc):
    return doc.get("completed_date") or doc.get("last_updated") or ""


def _find_task_doc(request, db_name, adl_id, sql_id, doc_id):
    """Document CouchDB de la tâche et base où il a été trouvé."""
    nsc = NoSQLClient()
    db = None
    if db_name:
        try:
            db = nsc.get_db(db_name)
        except Exception:  # noqa: BLE001 - base inconnue
            db = None
    if db is not None and doc_id:
        try:
            doc = db[doc_id]
            if doc.get("type") == "task":
                return dict(doc), db_name
        except KeyError:
            pass
    if not (adl_id and sql_id):
        return None, db_name
    try:
        sql_id = int(sql_id)
    except (TypeError, ValueError):
        return None, db_name
    if db is not None:
        selector = {"type": "task", "administrative_level_id": str(adl_id), "sql_id": sql_id}
        if request.session.get("cycle_couch_id"):
            selector["cycle_id"] = request.session.get("cycle_couch_id")
        try:
            rows = list(db.get_query_result(selector))
            if rows:
                return rows[0], db_name
        except Exception:  # noqa: BLE001
            pass
    # repli : tâche du village dans la base d'un autre facilitateur du projet (cf. détail de tâche)
    from dashboard.utils import _find_facilitator_task_doc

    project_id = Task.objects.filter(id=sql_id).values_list("project_id", flat=True).first()
    facilitator, _db, doc = _find_facilitator_task_doc(
        nsc, project_id, sql_id, adl_id, request.session.get("cycle_id"),
    )
    if doc is not None:
        return doc, facilitator.no_sql_db_name
    return None, db_name


@login_required
@require_GET
def village_profile_download(request):
    fmt = request.GET.get("format", "docx")
    doc, db_name = _find_task_doc(
        request, request.GET.get("db"), request.GET.get("administrative_level"),
        request.GET.get("task"), request.GET.get("doc"),
    )
    if doc is None or not _task_allows_village_profile(doc.get("sql_id")):
        raise Http404(_("No village profile can be generated for this task."))
    facilitator = Facilitator.objects.filter(no_sql_db_name=db_name).first()
    meta = build_meta(doc.get("administrative_level_id"), facilitator.name if facilitator else "", _doc_date(doc))
    try:
        content, name, mime = render_village_profile(doc.get("form_response") or [], meta, fmt)
    except DocConversionError as exc:
        return HttpResponse(str(exc), status=502, content_type="text/plain; charset=utf-8")
    response = HttpResponse(content, content_type=mime)
    response["Content-Disposition"] = f'attachment; filename="{name}"'
    return response


@csrf_exempt
@require_POST
def village_profile_api(request):
    from authentication.api.auth.login import CheckUserSerializer

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": _("Invalid request.")}, status=400)
    serializer = CheckUserSerializer(data=payload)
    if not serializer.is_valid():
        errors = serializer.errors
        status = 401
        return JsonResponse(dict({"ok": False}, **{k: v for k, v in errors.items()}), status=status)
    account = serializer.validated_data
    if not _task_allows_village_profile(payload.get("task_sql_id")):
        return JsonResponse({"ok": False, "error": _("No village profile can be generated for this task.")}, status=404)
    form_response = payload.get("form_response")
    if not isinstance(form_response, list):
        return JsonResponse({"ok": False, "error": _("Invalid request.")}, status=400)
    # Facilitator (attribut name) ou compte web (nom complet), sinon l'identifiant
    name = (getattr(account, "name", "")
            or (account.get_full_name() if hasattr(account, "get_full_name") else "")
            or getattr(account, "username", ""))
    meta = build_meta(payload.get("administrative_level_id"), name or "", payload.get("date") or "")
    try:
        content, filename, mime = render_village_profile(form_response, meta, payload.get("format"))
    except DocConversionError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=502)
    return JsonResponse({
        "ok": True, "filename": filename, "mime": mime, "content": base64.b64encode(content).decode("ascii"),
    })
