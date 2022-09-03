from django.contrib.auth.hashers import check_password
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from authentication.models import Facilitator


class CredentialSerializer(serializers.Serializer):
    no_sql_user = serializers.CharField()
    no_sql_pass = serializers.CharField()
    no_sql_db_name = serializers.CharField()


class UserAuthSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(
        label=_("Password"),
        style={'input_type': 'password'},
        trim_whitespace=False,
    )
    default_error_messages = {
        'invalid': _('Invalid data. Expected a dictionary, but got {datatype}.'),
        'credentials': _('Unable to log in with provided credentials.'),
    }

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        if username and password:
            facilitator = Facilitator.objects.filter(username=username, active=True).first()
            if not facilitator or not check_password(password, facilitator.password):
                msg = self.default_error_messages['credentials']
                raise serializers.ValidationError(msg, code='authorization')
        else:
            msg = _('Must include "username" and "password".')
            raise serializers.ValidationError(msg, code='authorization')

        attrs['no_sql_user'] = facilitator.no_sql_user
        attrs['no_sql_pass'] = facilitator.no_sql_pass
        attrs['no_sql_db_name'] = facilitator.no_sql_db_name
        return attrs
