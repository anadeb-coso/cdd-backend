from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from authentication.models import Facilitator
from grm_client import attach_administrative_regions_objects


class RestFacilitatorEadlByEmail(APIView):
    """Proxy pour l'application mobile CDD : elle interrogeait auparavant directement la base
    CouchDB partagée `eadls` (`getDocumentsByAttributes('eadls', {'representative.email': email})`)
    pour récupérer son propre profil ADL GRM (villages/cantons gérés). Les villages sont lus dans CDD
    (`Facilitator.stabilization_administrative_ids` + `additional_administrative_ids`, copie de l'EADL
    que le GRM envoie par `update-user-adls/`), sans appel au GRM.

    Pas d'authentification JWT ici (même choix que le endpoint jumeau
    `RestUpdateFacilitatorAdl`/`update-user-adls/` dans ce même dossier) : le mobile CDD n'obtient
    actuellement pas de JWT exploitable au login (génération commentée dans
    authentication/serializers.py) — hors périmètre de cette migration CouchDB à corriger."""
    throttle_classes = ()
    permission_classes = ()

    def get(self, request, *args, **kwargs):
        email = request.GET.get('email')
        if not email:
            return Response({'error': 'email is required', 'status': 'error'}, status=status.HTTP_400_BAD_REQUEST)
        eadl = attach_administrative_regions_objects(email)
        # `representative` de l'ancien document EADL, lu par le mobile (SelectVillage.tsx : name/email/phone)
        facilitator = Facilitator.objects.filter(email=email).first()
        if facilitator:
            eadl['representative'] = {'name': facilitator.name, 'email': facilitator.email, 'phone': facilitator.phone}
        return Response(eadl, status=status.HTTP_200_OK)
