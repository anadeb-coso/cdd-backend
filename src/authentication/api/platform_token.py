"""Jeton de session du mobile DCC (voir authentication/platform_tokens.py) : conversion d'une session ouverte avant
les jetons, renouvellement avant expiration, révocation à la déconnexion. Sans session web : aucun contrôle CSRF."""
from django.utils.translation import gettext as _
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.accounts import password_change_required
from authentication.platform_tokens import issue_token, renew_token, revoke_token, token_payload
from authentication.serializers import UserAuthSerializer


class _TokenSerializer(serializers.Serializer):
    token = serializers.CharField()


class RestPlatformToken(APIView):
    """Identifiant + mot de passe -> jeton. Pour les sessions du mobile ouvertes avant les jetons (mot de passe encore
    gardé sur l'appareil) : le mobile l'échange une fois contre un jeton puis efface le mot de passe.
    Mêmes contrôles que la connexion (identifiants, mot de passe initial à changer)."""
    authentication_classes = ()
    permission_classes = ()
    throttle_classes = ()

    def post(self, request, *args, **kwargs):
        serializer = UserAuthSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        account = serializer.validated_data['user']
        if password_change_required(account=account):
            return Response({
                'non_field_errors': [_("You must change your password before your first login.")],
                'password_change_required': True,
            }, status=status.HTTP_403_FORBIDDEN)
        token, expires_at = issue_token(account, client=request.data.get('client') or 'dcc_mobile')
        return Response(token_payload(token, expires_at), status=status.HTTP_200_OK)


class RestRenewPlatformToken(APIView):
    """Jeton encore valide -> nouveau jeton (l'ancien est révoqué). Le mobile le demande quand l'expiration approche."""
    authentication_classes = ()
    permission_classes = ()
    throttle_classes = ()

    def post(self, request, *args, **kwargs):
        serializer = _TokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        renewed = renew_token(serializer.validated_data['token'])
        if renewed is None:
            return Response({
                'non_field_errors': [_("Your session has expired. Please log in again.")],
                'token_invalid': True,
            }, status=status.HTTP_401_UNAUTHORIZED)
        return Response(token_payload(*renewed), status=status.HTTP_200_OK)


class RestRevokePlatformToken(APIView):
    """Déconnexion du mobile : le jeton ne vaut plus nulle part. Toujours 200 (jeton déjà invalide compris)."""
    authentication_classes = ()
    permission_classes = ()
    throttle_classes = ()

    def post(self, request, *args, **kwargs):
        serializer = _TokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({'ok': True, 'revoked': revoke_token(serializer.validated_data['token'])}, status=status.HTTP_200_OK)
