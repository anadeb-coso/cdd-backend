from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response

from dashboard.facilitators.repository.db_facilitator_repository import FacilitatorRepository
# from dashboard.facilitators.repository.facilitator_criteria import FacilitatorCriteria
from authentication.models import Facilitator
from planning.serializers import *
from planning.models import *
from authentication.api.facilitators.serializers import FacilitatorUpdateAdlSerializer
from cdd.functions import get_dates_between
from dashboard.utils import search_facilitators_db_with_villages_stabilized
from dashboard.facilitators.localities import administrative_choices, flag_sessions_for_zone_change, is_supervisor, supervisor_canton_ids
from dashboard.facilitators.localities_history import facilitator_state, record_facilitator_changes, record_user_changes, user_state
from authentication.models import UserLocalities
from dashboard.facilitators.localities_notify import notify_localities_change



class RestUpdateFacilitatorAdl(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = FacilitatorUpdateAdlSerializer
    
    def post(self, request, *args, **kwargs):
        try:
            serializer = self.serializer_class(data=request.data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data

            if validated_data.get("account") is not None:
                events = self.update_user_localities(validated_data["account"], validated_data)
                if validated_data.get("notify", True):
                    notify_localities_change(validated_data["account"], events)
                return Response({'success': 'ok', 'status': 'success', 'type': 'user'}, status=status.HTTP_200_OK)
            
            facilitator = validated_data["user"]
            localities_before = facilitator_state(facilitator)

            facilitator.stabilization_administrative_ids = validated_data["stabilization_administrative_ids"]
            facilitator.additional_administrative_ids = validated_data["additional_administrative_ids"]
            # Choix de l'agent (envoyés par les versions récentes du GRM seulement).
            if "administrative_id" in validated_data:
                facilitator.main_administrative_id = validated_data["administrative_id"] or None
            if "administrative_ids" in validated_data:
                facilitator.stabilization_administrative_choices = administrative_choices(validated_data["administrative_ids"])
            if "additional_administrative_region_ids" in validated_data:
                facilitator.additional_administrative_choices = administrative_choices(validated_data["additional_administrative_region_ids"])

            facilitator.simple_save()
            events = record_facilitator_changes(facilitator, localities_before, 'grm', sections=['stabilization', 'additional'], changed_by_label="GRM")

            # Update facilitator no_sql_dbs_names
            if hasattr(facilitator, 'projects') and hasattr(facilitator, 'no_sql_db_name') and facilitator.no_sql_db_name:
                project = facilitator.projects.first()
                if project:
                    search_facilitators_db_with_villages_stabilized(project.name, no_sql_db=facilitator.no_sql_db_name)

            # Mail au facilitateur seulement si ses localités ont réellement changé : le renvoi par le GRM des
            # localités que CDD vient de lui transmettre n'en produit pas un second.
            if validated_data.get("notify", True):
                notify_localities_change(facilitator, events)

        except Exception as exc:
            return Response(
                {'error': exc.__str__(), 'status': 'error'}, 
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(
                {'success': 'ok', 'status': 'success'}, 
                status=status.HTTP_200_OK
            )

    @staticmethod
    def update_user_localities(account, validated_data):
        """Localités d'intervention d'un utilisateur du dashboard (non facilitateur), copiées de son compte
        GRM de même email. Renvoie les lignes d'historique créées (mail à l'utilisateur)."""
        record = UserLocalities.objects.filter(user=account).first()
        before = user_state(record)
        # zone d'un superviseur avant l'envoi (None : pas encore dans CDD, sa zone venait déjà du GRM)
        zone_before = supervisor_canton_ids(account) if is_supervisor(account) else None
        if record is None:
            record = UserLocalities(user=account)
        record.village_ids = administrative_choices(validated_data["stabilization_administrative_ids"])
        record.additional_village_ids = administrative_choices(validated_data["additional_administrative_ids"])
        if "administrative_id" in validated_data:
            record.administrative_id = validated_data["administrative_id"] or None
        if "administrative_ids" in validated_data:
            record.administrative_choices = administrative_choices(validated_data["administrative_ids"])
        if "additional_administrative_region_ids" in validated_data:
            record.additional_administrative_choices = administrative_choices(validated_data["additional_administrative_region_ids"])
        record.save()
        events = record_user_changes(account, before, record, 'grm', changed_by_label="GRM")
        if zone_before is not None and set(zone_before) != set(supervisor_canton_ids(account) or []):
            # zone changée depuis le GRM : ses sessions CDD ouvertes sont déconnectées à leur requête suivante
            flag_sessions_for_zone_change(account)
        return events