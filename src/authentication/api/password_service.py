"""Services used by the SIG (COSOMIS) and the MGP (GRM) for their own Profile pages.

- `RestChangePasswordAllPlatforms`: change of password requested from a Profile page. The current password of one
  of the person's accounts (DCC web/SIG, facilitator, or MGP account of the same e-mail) is checked, then the new
  password is set on all of them by `set_person_password` (same as the DCC Profile page and the password reset),
  which also lifts a pending "change at first login" requirement.
- `RestPersonProfile`: what the DCC knows about a person (accounts, roles, projects, area of intervention), so that
  the MGP, which does not read the DCC database, can show the same Profile page as the DCC.

Both are server-to-server calls authenticated by the shared secret already used between the platforms
(`settings.GRM_SECRET_KEY_GENRATE`, field `secret`)."""
import logging

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.utils import translation
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.accounts import (
    PLATFORMS, grm_account, person_accounts, set_person_password, validate_new_password,
)

logger = logging.getLogger(__name__)


def _authorized(data):
    secret = getattr(settings, 'GRM_SECRET_KEY_GENRATE', None)
    return bool(secret) and data.get('secret') == secret


def _activate(language):
    if language in ('fr', 'en'):
        translation.activate(language)


class RestChangePasswordAllPlatforms(APIView):
    """Input: secret, login (e-mail or username), current_password, new_password, new_password_confirm,
    platform (sig_web, mgp_web...), language. Output: {ok, message, errors, mgp}."""
    authentication_classes = ()
    permission_classes = ()
    throttle_classes = ()

    def post(self, request, *args, **kwargs):
        data = request.data
        _activate(data.get('language'))
        if not _authorized(data):
            return Response({'ok': False, 'message': 'Forbidden', 'errors': ['Forbidden']}, status=status.HTTP_403_FORBIDDEN)

        login = (data.get('login') or '').strip()
        current_password = data.get('current_password') or ''
        if not login or not current_password:
            return self._error([_("You have to fill all the fields")])

        person = person_accounts(login=login)
        hashes = person.password_hashes()
        mgp_emails = person.emails or ([login.lower()] if '@' in login else [])
        for email in mgp_emails:
            account = grm_account(email)
            if account and account['password']:
                hashes.append(account['password'])
        if not hashes or not any(check_password(current_password, h) for h in hashes):
            return self._error([_('Current password does not match.')])

        errors = validate_new_password(data.get('new_password'), data.get('new_password_confirm'), current_password)
        if errors:
            return self._error(errors)

        if person.exists:
            platform = data.get('platform') if data.get('platform') in PLATFORMS else 'profile'
            result = set_person_password(person, data['new_password'], platform)
            mgp = result.get('mgp')
        else:
            # Account that only exists on the MGP: nothing to change on the DCC side.
            import grm_client
            mgp = all(bool(grm_client.set_grm_user_password(email, data['new_password'])) for email in mgp_emails)
        message = _('The password has been successfully changed.')
        if mgp is False:
            message = f"{message} {_('The MGP password could not be updated.')}"
        return Response({'ok': True, 'message': message, 'errors': [], 'mgp': mgp}, status=status.HTTP_200_OK)

    @staticmethod
    def _error(errors):
        errors = [str(e) for e in errors]
        return Response({'ok': False, 'message': ' '.join(errors), 'errors': errors}, status=status.HTTP_400_BAD_REQUEST)


class RestPersonProfile(APIView):
    """Input: secret, email, language. Output: the DCC part of the Profile page (accounts, roles, projects, area)."""
    authentication_classes = ()
    permission_classes = ()
    throttle_classes = ()

    def post(self, request, *args, **kwargs):
        data = request.data
        _activate(data.get('language'))
        if not _authorized(data):
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
        email = (data.get('email') or '').strip()
        if not email:
            return Response({'detail': 'email is required'}, status=status.HTTP_400_BAD_REQUEST)

        from usermanager.profile_details import build_profile_details

        person = person_accounts(login=email)
        user = person.users[0] if person.users else None
        facilitator = person.facilitators[0] if person.facilitators else None
        try:
            details = build_profile_details(user, facilitator, user, None)
        except Exception as exc:  # noqa: BLE001 - the Profile page must always be shown
            logger.exception(exc)
            details = {'groups': [], 'projects': [], 'zone': None}

        zone = details.get('zone') or {}
        return Response({
            'dcc_web': user is not None,
            'dcc_mobile': facilitator is not None,
            'sig': user is not None,  # web accounts are shared by the DCC and the SIG
            'groups': list(details.get('groups') or []),
            'projects': [
                {'name': p['name'], 'description': p.get('description'), 'parent': p.get('parent'),
                 'cycles': list(p.get('cycles') or []), 'roles': [str(r) for r in p.get('roles') or []]}
                for p in details.get('projects') or []
            ],
            'zone': {'labels': [str(label) for label in zone.get('labels') or []],
                     'villages': zone.get('villages'), 'additional': list(zone.get('additional') or [])},
            'facilitator': None if facilitator is None else {
                'code': facilitator.code, 'username': facilitator.username, 'phone': facilitator.phone,
                'sex': facilitator.sex, 'type': str(details.get('facilitator_type') or ''),
                'training_mode': bool(getattr(facilitator, 'training_mode', False)),
            },
        }, status=status.HTTP_200_OK)
