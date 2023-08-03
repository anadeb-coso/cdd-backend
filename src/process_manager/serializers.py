from django.contrib.auth.hashers import check_password
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from authentication.models import Facilitator


class SaveFormDatasSerializer(serializers.Serializer):
    tasks = serializers.JSONField()
    facilitator = serializers.JSONField()

    default_error_messages = {
        'invalid': _('Invalid data. Expected a dictionary, but got {datatype}.'),
        'credentials': _('Unable to log in with provided credentials.'),
    }

    def validate(self, attrs):
        facilitator = attrs.get('facilitator')

        if facilitator and facilitator.get("sql_id"):
            facilitator = Facilitator.objects.filter(id=facilitator["sql_id"]).first()
            if not facilitator:
                msg = self.default_error_messages['credentials']
                raise serializers.ValidationError(msg, code='authorization')
        else:
            msg = _('Must include "username" and "password".')
            raise serializers.ValidationError(msg, code='authorization')

        attrs['no_sql_db_name'] = facilitator.no_sql_db_name
        return attrs
