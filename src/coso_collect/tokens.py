"""Jeton d'accès de l'API COSOCollect pour le mobile.

Le mobile n'a pas de session Django : il échange l'identifiant et le mot de passe saisis à la connexion
(déjà conservés sur l'appareil, cf. Login.tsx) contre un jeton signé (SECRET_KEY), envoyé ensuite dans
`Authorization: Token <jeton>`. Le jeton désigne un compte Facilitator ou User et embarque une empreinte
du hash du mot de passe : changer le mot de passe invalide les jetons déjà émis.
"""
import hashlib
from functools import wraps

from django.contrib.auth.models import User
from django.core import signing
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from authentication.api.auth.login import CheckUserSerializer
from authentication.identity import is_active, is_facilitator
from authentication.models import Facilitator

SALT = 'coso_collect.api.token'
MAX_AGE = 60 * 60 * 24 * 3650  # 10 ans ; le mobile en redemande un avec son jeton de session à l'expiration


def _fingerprint(account):
    return hashlib.sha256((account.password or '').encode('utf-8')).hexdigest()[:16]


def issue_token(account):
    kind = 'f' if is_facilitator(account) else 'u'
    return signing.dumps({'k': kind, 'i': account.pk, 'h': _fingerprint(account)}, salt=SALT, compress=True)


def account_from_token(token):
    try:
        payload = signing.loads(token, salt=SALT, max_age=MAX_AGE)
    except signing.BadSignature:
        return None
    model = Facilitator if payload.get('k') == 'f' else User
    account = model.objects.filter(pk=payload.get('i')).first()
    if not account or not is_active(account) or _fingerprint(account) != payload.get('h'):
        return None
    return account


def authenticate_credentials(username, password):
    serializer = CheckUserSerializer(data={'username': username or '', 'password': password or ''})
    if not serializer.is_valid():
        return None
    account = serializer.validated_data
    return account if is_active(account) else None


def request_account(request):
    """Compte à l'origine de la requête : jeton (mobile) ou session web."""
    header = request.META.get('HTTP_AUTHORIZATION', '')
    token = header[6:].strip() if header.lower().startswith('token ') else request.GET.get('token')
    if token:
        return account_from_token(token)
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated and user.is_active:
        return user
    return None


def api_view(view):
    """Vue JSON de l'API COSOCollect : compte authentifié requis (jeton ou session), pas de CSRF pour
    les appels par jeton (le jeton n'est jamais envoyé automatiquement par un navigateur)."""

    @csrf_exempt
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        account = request_account(request)
        if account is None:
            return JsonResponse({'ok': False, 'code': 'unauthorized', 'message': 'Authentication required.'},
                                status=401)
        uses_token = request.META.get('HTTP_AUTHORIZATION', '').lower().startswith('token ') or 'token' in request.GET
        if not uses_token and request.method not in ('GET', 'HEAD', 'OPTIONS'):
            # Session web : la protection CSRF reste due.
            from django.middleware.csrf import CsrfViewMiddleware

            reason = CsrfViewMiddleware(lambda r: None).process_view(request, None, (), {})
            if reason is not None:
                return reason
        request.collect_account = account
        return view(request, *args, **kwargs)

    return wrapper
