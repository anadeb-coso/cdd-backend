"""API COSOCollect du mobile (préfixe `api/coso-collect/`).

    POST auth/token/                              {username, password} -> {token}
    GET  forms/                                   formulaires que le compte peut remplir
    GET  forms/<id>/                              définition complète d'un formulaire
    GET  forms/<id>/submissions/?since=<iso>      saisies du compte (toutes appareils / web confondus)
    POST forms/<id>/submissions/sync/             {submissions: [...]} -> résultat par saisie
    POST attachments/upload/                      fichier d'un champ photo/fichier (multipart)
    GET  attachments/<id>/                        téléchargement (auteur ou administrateur)
"""
import json

from django.conf import settings
from django.db.models import Count
from django.http import FileResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from authentication.identity import is_facilitator
from authentication.platform_tokens import account_from_token as account_from_platform_token, is_platform_token

from . import access
from .models import CollectAttachment, CollectForm, CollectSubmission
from .services import CollectError, as_uuid, save_submission, store_attachment, submission_payload
from .titles import parse_iso
from .tokens import api_view, authenticate_credentials, issue_token, MAX_AGE


def _error(code, message, status=400, **extra):
    payload = {'ok': False, 'code': code, 'message': message}
    payload.update(extra)
    return JsonResponse(payload, status=status)


def form_summary(form, counts=None):
    counts = counts or {}
    return {
        'id': form.pk,
        'uid': str(form.uid),
        'title': form.title,
        'description': form.description,
        'version': form.version,
        'status': form.status,
        'close_message': form.close_message,
        'single_submission': form.single_submission,
        'published_at': form.published_at and form.published_at.isoformat(),
        'closed_at': form.closed_at and form.closed_at.isoformat(),
        'updated_at': form.updated_at and form.updated_at.isoformat(),
        'my_counts': counts,
    }


def form_definition(form):
    out = form_summary(form)
    out.update({'form': form.form or [], 'title_template': form.title_template or {}})
    return out


@csrf_exempt
@require_POST
def token_view(request):
    try:
        body = json.loads(request.body.decode('utf-8') or '{}')
    except (ValueError, UnicodeDecodeError):
        body = request.POST
    # jeton de session du mobile (valable sur le DCC, le SIG et le MGP) ou, avant les jetons, identifiant + mot de passe
    platform_token = body.get('token')
    if is_platform_token(platform_token):
        account = account_from_platform_token(platform_token)
    else:
        account = authenticate_credentials(body.get('username'), body.get('password'))
    if account is None:
        return _error('invalid_credentials', 'Incorrect identifiers.', status=401)
    name = (account.name or account.username) if is_facilitator(account) else (account.get_full_name() or account.username)
    return JsonResponse({
        'ok': True,
        'token': issue_token(account),
        'expires_in': MAX_AGE,
        'account': {
            'kind': 'facilitator' if is_facilitator(account) else 'user', 'id': account.pk, 'name': name,
            # identifiants de connexion du compte (le mobile range ses données par compte, quel que soit
            # l'identifiant tapé : nom d'utilisateur ou e-mail)
            'logins': sorted({str(v).strip().lower() for v in (account.username, account.email) if v}),
        },
    })


def _my_counts(account, form_ids):
    rows = (access.own_submissions(account).filter(form_id__in=form_ids)
            .values('form_id', 'status').annotate(n=Count('pk')))
    counts = {}
    for row in rows:
        counts.setdefault(row['form_id'], {})[row['status']] = row['n']
    return counts


@require_GET
@api_view
def forms_view(request):
    account = request.collect_account
    forms = list(access.fillable_forms(account).order_by('-published_at', '-updated_at'))
    counts = _my_counts(account, [f.pk for f in forms])
    return JsonResponse({'ok': True, 'forms': [form_summary(f, counts.get(f.pk, {})) for f in forms]})


@require_GET
@api_view
def form_view(request, pk):
    account = request.collect_account
    form = get_object_or_404(CollectForm, pk=pk)
    if form.status == CollectForm.STATUS_DRAFT or not access.can_access_form(account, form):
        return _error('forbidden', 'You do not have access to this form.', status=403)
    return JsonResponse({'ok': True, 'form': form_definition(form)})


@require_GET
@api_view
def my_submissions_view(request, pk):
    account = request.collect_account
    form = get_object_or_404(CollectForm, pk=pk)
    if not access.can_access_form(account, form):
        return _error('forbidden', 'You do not have access to this form.', status=403)
    qs = access.own_submissions(account, form).select_related('user', 'facilitator', 'form')
    since = parse_iso(request.GET.get('since'))
    if since is not None:
        if timezone.is_naive(since):
            since = timezone.make_aware(since, timezone.utc)
        qs = qs.filter(updated_at__gt=since)
    items = [submission_payload(s) for s in qs.order_by('updated_at')[:2000]]
    return JsonResponse({
        'ok': True,
        'form': form_summary(form),
        'server_time': timezone.now().isoformat(),
        'submissions': items,
    })


@require_POST
@api_view
def sync_view(request, pk):
    """Envoie les saisies locales. Chaque saisie est traitée indépendamment : une saisie refusée
    (formulaire clôturé, saisie verrouillée…) n'empêche pas les autres d'être enregistrées."""
    account = request.collect_account
    form = get_object_or_404(CollectForm, pk=pk)
    try:
        body = json.loads(request.body.decode('utf-8') or '{}')
    except (ValueError, UnicodeDecodeError):
        return _error('invalid', 'Invalid payload.')
    results = []
    for item in (body.get('submissions') or [])[:200]:
        item = item if isinstance(item, dict) else {}
        try:
            submission = save_submission(form, account, item, CollectSubmission.SOURCE_MOBILE)
            results.append({'uuid': str(submission.uuid), 'ok': True, 'submission': submission_payload(submission)})
        except CollectError as exc:
            result = {'uuid': str(item.get('uuid')), 'ok': False, 'code': exc.code, 'message': exc.message}
            item_uuid = as_uuid(item.get('uuid'))
            existing = CollectSubmission.objects.filter(uuid=item_uuid).first() if item_uuid else None
            if existing is not None and access.owns_submission(account, existing):
                # Copie serveur faisant foi (ex. saisie verrouillée) : le mobile s'y réaligne.
                result['submission'] = submission_payload(existing)
            results.append(result)
    form.refresh_from_db()
    return JsonResponse({'ok': True, 'form': form_summary(form), 'results': results})


@require_POST
@api_view
def upload_view(request):
    account = request.collect_account
    uploaded = request.FILES.get('file')
    if not uploaded:
        return _error('invalid', 'No file.')
    if uploaded.size > settings.MAX_UPLOAD_SIZE:
        return _error('too_large', 'File too large.')
    form = CollectForm.objects.filter(pk=request.POST.get('form_id') or 0).first()
    if form is None:
        return _error('not_found', 'Form not found.', status=404)
    try:
        attachment = store_attachment(form, account, uploaded, request.POST.get('submission_uuid'),
                                      request.POST.get('field_path'))
    except CollectError as exc:
        return _error(exc.code, exc.message,
                      status=409 if exc.code in ('locked', 'form_closed', 'single_submission') else 403)
    return JsonResponse({'ok': True, 'attachment': attachment_payload(attachment)})


def attachment_payload(attachment):
    return {
        'attachment_id': attachment.pk,
        'name': attachment.name,
        'mime': attachment.mime_type,
        'size': attachment.size,
    }


def serve_attachment(attachment):
    """Fichier d'une pièce jointe : redirection vers le stockage (S3) ou lecture directe."""
    try:
        url = attachment.file.url.split('?')[0]  # S3 / stockage distant
    except Exception:  # stockage sans URL publique
        url = None
    if url and url.startswith('http'):
        return HttpResponseRedirect(url)
    response = FileResponse(attachment.file.open('rb'), content_type=attachment.mime_type or None)
    response['Content-Disposition'] = 'inline; filename="{}"'.format(attachment.name.replace('"', ''))
    return response


@require_GET
@api_view
def attachment_view(request, pk):
    account = request.collect_account
    attachment = get_object_or_404(CollectAttachment.objects.select_related('form', 'submission'), pk=pk)
    if not access.can_view_attachment(account, attachment):
        return _error('forbidden', 'Forbidden.', status=403)
    return serve_attachment(attachment)
