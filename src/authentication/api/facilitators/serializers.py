from rest_framework import serializers
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.contrib.auth.models import User

from authentication.models import Facilitator


class FacilitatorUpdateAdlSerializer(serializers.Serializer):
    facilitator_email = serializers.CharField()
    grm_secret_key_generate = serializers.CharField()
    stabilization_administrative_ids = serializers.JSONField()
    additional_administrative_ids = serializers.JSONField()
    # Facultatifs (anciens envois du GRM sans eux) : niveau principal et niveaux choisis avant calcul
    # des villages ; `notify=False` pour ne pas envoyer d'email au facilitateur (remplissage initial).
    administrative_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    administrative_ids = serializers.JSONField(required=False, allow_null=True)
    additional_administrative_region_ids = serializers.JSONField(required=False, allow_null=True)
    notify = serializers.BooleanField(required=False, default=True)

    def validate(self, data):
        facilitator_email = data.get('facilitator_email')
        grm_secret_key_generate = data.get('grm_secret_key_generate')
        stabilization_administrative_ids = data.get('stabilization_administrative_ids')
        additional_administrative_ids = data.get('additional_administrative_ids')

        if grm_secret_key_generate != settings.GRM_SECRET_KEY_GENRATE:
            raise serializers.ValidationError(_("Incorrect identifiers"))

        user = Facilitator.objects.filter(Q(email=facilitator_email) | Q(username=facilitator_email)).first()
        # Pas un facilitateur : utilisateur du dashboard de même email (localités d'intervention).
        account = None
        if not user and facilitator_email and facilitator_email.strip():
            account = User.objects.filter(email__iexact=facilitator_email.strip()).first()
        if not user and not account:
            raise serializers.ValidationError(_("Incorrect identifiers"))
        
        validated = {
            "facilitator_email": facilitator_email,
            "stabilization_administrative_ids": stabilization_administrative_ids,
            "additional_administrative_ids": additional_administrative_ids,
            "notify": data.get('notify', True),
            "user": user,
            "account": account,
        }
        for key in ('administrative_id', 'administrative_ids', 'additional_administrative_region_ids'):
            if key in data:
                validated[key] = data[key]
        return validated