from rest_framework import serializers
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django.conf import settings

from authentication.models import Facilitator


class FacilitatorUpdateAdlSerializer(serializers.Serializer):
    facilitator_email = serializers.CharField()
    grm_secret_key_generate = serializers.CharField()
    stabilization_administrative_ids = serializers.JSONField()
    additional_administrative_ids = serializers.JSONField()

    def validate(self, data):
        facilitator_email = data.get('facilitator_email')
        grm_secret_key_generate = data.get('grm_secret_key_generate')
        stabilization_administrative_ids = data.get('stabilization_administrative_ids')
        additional_administrative_ids = data.get('additional_administrative_ids')

        if grm_secret_key_generate != settings.GRM_SECRET_KEY_GENRATE:
            raise serializers.ValidationError(_("Incorrect identifiers"))

        user = Facilitator.objects.filter(active=True).filter(Q(email=facilitator_email) | Q(username=facilitator_email)).first()
        if not user:
            raise serializers.ValidationError(_("Incorrect identifiers"))
        
        return {
            "facilitator_email": facilitator_email,
            "stabilization_administrative_ids": stabilization_administrative_ids,
            "additional_administrative_ids": additional_administrative_ids,
            "user": user
        }