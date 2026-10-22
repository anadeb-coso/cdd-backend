from django.utils import translation
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.accounts import change_initial_password


class RestFirstLoginPassword(APIView):
    """Changement du mot de passe initial (première connexion), pour toutes les plateformes : applications mobiles
    du DCC et du MGP, pages de changement imposé du SIG et du MGP. Authentifié par l'identifiant (e-mail ou nom
    d'utilisateur) et le mot de passe actuel ; le nouveau mot de passe s'applique à tous les comptes de la
    personne (DCC, SIG, MGP). Sans session : aucun contrôle CSRF.

    Entrée : login, current_password, new_password, new_password_confirm, platform (dcc_mobile, mgp_mobile,
    mgp_web, sig_web…), language (facultatif). Réponse : {ok, message, errors}."""
    authentication_classes = ()
    permission_classes = ()
    throttle_classes = ()

    def post(self, request, *args, **kwargs):
        data = request.data
        language = data.get('language')
        if language in ('fr', 'en'):
            translation.activate(language)
        ok, errors, _person = change_initial_password(
            data.get('login'), data.get('current_password'), data.get('new_password'),
            data.get('new_password_confirm'), data.get('platform'),
        )
        if ok:
            return Response({'ok': True, 'message': _('The password has been successfully changed.'), 'errors': []},
                            status=status.HTTP_200_OK)
        return Response({'ok': False, 'message': ' '.join(str(e) for e in errors), 'errors': [str(e) for e in errors]},
                        status=status.HTTP_400_BAD_REQUEST)
