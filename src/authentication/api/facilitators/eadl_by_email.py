from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from grm_client import get_facilitator_by_email, attach_administrative_regions_objects


class RestFacilitatorEadlByEmail(APIView):
    """Proxy pour l'application mobile CDD : elle interrogeait auparavant directement la base
    CouchDB partagée `eadls` (`getDocumentsByAttributes('eadls', {'representative.email': email})`)
    pour récupérer son propre profil ADL GRM (villages/cantons gérés). `eadls` est désormais
    Postgres côté GRM (issue.models.Adl) et n'est plus accessible en direct par le mobile : ce
    proxy passe par le backend CDD, qui appelle la nouvelle API inter-services GRM
    (grm_client.py) pour le compte du mobile.

    Pas d'authentification JWT ici (même choix que le endpoint jumeau
    `RestUpdateFacilitatorAdl`/`update-user-adls/` dans ce même dossier) : le mobile CDD n'obtient
    actuellement pas de JWT exploitable au login (génération commentée dans
    authentication/serializers.py) — hors périmètre de cette migration CouchDB à corriger."""
    throttle_classes = ()
    permission_classes = ()

    def get(self, request, *args, **kwargs):
        email = request.GET.get('email')
        try:
            eadl = attach_administrative_regions_objects(email)
        except Exception as e:
            if not email:
                return Response({'error': 'email is required', 'status': 'error'}, status=status.HTTP_400_BAD_REQUEST)

            eadl = get_facilitator_by_email(email)
            if not eadl:
                return Response({'error': 'not found', 'status': 'error'}, status=status.HTTP_404_NOT_FOUND)

            eadl = attach_administrative_regions_objects(eadl)
        return Response(eadl, status=status.HTTP_200_OK)
