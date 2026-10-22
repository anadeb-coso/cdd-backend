"""Jetons de session du mobile DCC, valables sur le DCC, le SIG et le MGP.

À la connexion (`authentication/obtain-auth-credentials/`), le DCC délivre un jeton aléatoire ; le mobile l'envoie
ensuite à chaque appel à la place du mot de passe, qu'il ne garde plus :
- DCC et SIG : champ `token` du corps de la requête, avec `username` (CheckUserSerializer de chaque projet) ;
- MGP : en-tête `Authorization: Bearer <jeton>` (PlatformTokenAuthentication du MGP).

Le jeton n'est rangé que sous forme d'empreinte (table PlatformAccessToken, base partagée) ; le SIG et le MGP le
vérifient en lisant cette table (SQL brut, mêmes règles qu'ici). Il ne vaut plus après son expiration, sa révocation
(déconnexion, renouvellement) ou un changement de mot de passe du compte. Le préfixe distingue ces jetons des autres
jetons acceptés par les mêmes champs (JWT du SIG et du MGP, jetons COSOCollect)."""
import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone

from authentication.identity import is_active, is_facilitator
from authentication.models import Facilitator, PlatformAccessToken

PREFIX = 'cps_'
# Durée de validité ; le mobile demande un nouveau jeton quand il en reste moins de RENEW_BEFORE_DAYS.
TOKEN_DAYS = getattr(settings, 'PLATFORM_TOKEN_DAYS', 90)
RENEW_BEFORE_DAYS = getattr(settings, 'PLATFORM_TOKEN_RENEW_BEFORE_DAYS', 30)
# Date de dernière utilisation : mise à jour au plus une fois par heure (pas d'écriture à chaque appel).
TOUCH_INTERVAL = timedelta(hours=1)
KEEP_ENDED_TOKENS = timedelta(days=30)


def is_platform_token(value):
    return isinstance(value, str) and value.startswith(PREFIX)


def token_hash(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def password_fingerprint(password_hash):
    """Empreinte du hash du mot de passe : un changement de mot de passe invalide les jetons déjà délivrés."""
    return hashlib.sha256((password_hash or '').encode('utf-8')).hexdigest()


def issue_token(account, client='dcc_mobile'):
    """Nouveau jeton pour le compte (Facilitator ou User). Renvoie (jeton, date d'expiration)."""
    token = PREFIX + secrets.token_urlsafe(32)
    now = timezone.now()
    expires_at = now + timedelta(days=TOKEN_DAYS)
    kind = PlatformAccessToken.KIND_FACILITATOR if is_facilitator(account) else PlatformAccessToken.KIND_USER
    # jetons du compte expirés ou révoqués depuis plus de 30 jours : supprimés (gardés un temps pour le suivi)
    PlatformAccessToken.objects.filter(account_kind=kind, account_id=account.pk).filter(
        Q(expires_at__lt=now - KEEP_ENDED_TOKENS) | Q(revoked_at__lt=now - KEEP_ENDED_TOKENS)).delete()
    PlatformAccessToken.objects.create(
        key_hash=token_hash(token),
        account_kind=kind,
        account_id=account.pk,
        email=(account.email or '').strip().lower(),
        username=account.username or '',
        password_fingerprint=password_fingerprint(account.password),
        client=client,
        expires_at=expires_at,
    )
    return token, expires_at


def _valid_record(token):
    if not is_platform_token(token):
        return None
    return PlatformAccessToken.objects.filter(
        key_hash=token_hash(token), revoked_at__isnull=True, expires_at__gt=timezone.now()
    ).first()


def account_from_token(token, touch=True):
    """Compte actif désigné par un jeton valide, sinon None."""
    record = _valid_record(token)
    if record is None:
        return None
    model = Facilitator if record.account_kind == PlatformAccessToken.KIND_FACILITATOR else User
    account = model.objects.filter(pk=record.account_id).first()
    if not is_active(account) or password_fingerprint(account.password) != record.password_fingerprint:
        return None
    now = timezone.now()
    if touch and (record.last_used_at is None or record.last_used_at < now - TOUCH_INTERVAL):
        PlatformAccessToken.objects.filter(pk=record.pk).update(last_used_at=now)
    return account


def renew_token(token):
    """Jeton valide échangé contre un nouveau (l'ancien est révoqué). Renvoie (jeton, expiration) ou None."""
    account = account_from_token(token, touch=False)
    if account is None:
        return None
    record = _valid_record(token)
    new_token = issue_token(account, client=record.client if record else 'dcc_mobile')
    revoke_token(token)
    return new_token


def revoke_token(token):
    """Déconnexion : le jeton ne vaut plus. True s'il était valide."""
    if not is_platform_token(token):
        return False
    return PlatformAccessToken.objects.filter(key_hash=token_hash(token), revoked_at__isnull=True).update(
        revoked_at=timezone.now()) > 0


def token_payload(token, expires_at):
    """Champs ajoutés aux réponses de connexion."""
    return {'access': token, 'access_expires_at': expires_at.isoformat(), 'access_renew_before_days': RENEW_BEFORE_DAYS}
