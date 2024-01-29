from django.contrib.auth.hashers import check_password
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from django.db.models import Q

from authentication.models import Facilitator
from django.contrib.auth.models import User


# class CredentialSerializer(serializers.Serializer):
#     no_sql_user = serializers.CharField()
#     no_sql_pass = serializers.CharField()
#     no_sql_db_name = serializers.CharField()


# class UserAuthSerializer(serializers.Serializer):
#     username = serializers.CharField()
#     password = serializers.CharField(
#         label=_("Password"),
#         style={'input_type': 'password'},
#         trim_whitespace=False,
#     )
#     default_error_messages = {
#         'invalid': _('Invalid data. Expected a dictionary, but got {datatype}.'),
#         'credentials': _('Unable to log in with provided credentials.'),
#     }

#     def validate(self, attrs):
#         username = attrs.get('username')
#         password = attrs.get('password')

#         if username and password:
#             facilitator = Facilitator.objects.filter(username=username, active=True).first()
#             if not facilitator or not check_password(password, facilitator.password):
#                 msg = self.default_error_messages['credentials']
#                 raise serializers.ValidationError(msg, code='authorization')
#         else:
#             msg = _('Must include "username" and "password".')
#             raise serializers.ValidationError(msg, code='authorization')

#         attrs['no_sql_user'] = facilitator.no_sql_user
#         attrs['no_sql_pass'] = facilitator.no_sql_pass
#         attrs['no_sql_db_name'] = facilitator.no_sql_db_name
#         return attrs


class CredentialSerializer(serializers.Serializer):
    no_sql_user = serializers.CharField(allow_blank=True, allow_null=True)
    no_sql_pass = serializers.CharField(allow_blank=True, allow_null=True)
    no_sql_db_name = serializers.CharField(allow_blank=True, allow_null=True)
    first_name = serializers.CharField(allow_blank=True, allow_null=True)
    last_name = serializers.CharField(allow_blank=True, allow_null=True)
    email = serializers.CharField(allow_blank=True, allow_null=True)
    
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
            user = Facilitator.objects.filter(Q(email=username) | Q(username=username), active=True).first()
            user = User.objects.filter(Q(email=username) | Q(username=username), is_active=True).first() if not user else user
            
            if not user or not check_password(password, user.password):
                msg = self.default_error_messages['credentials']
                raise serializers.ValidationError(msg, code='authorization')
        else:
            msg = _('Must include "username" and "password".')
            raise serializers.ValidationError(msg, code='authorization')
        
        attrs['no_sql_user'] = None
        attrs['no_sql_pass'] = None
        attrs['no_sql_db_name'] = None
        attrs['first_name'] = None
        attrs['last_name'] = None
        attrs['email'] = None
        if hasattr(user, 'no_sql_user'):
            attrs['no_sql_user'] = user.no_sql_user
            attrs['no_sql_pass'] = user.no_sql_pass
            attrs['no_sql_db_name'] = user.no_sql_db_name
        else:
            attrs['first_name'] = user.first_name
            attrs['last_name'] = user.last_name
            attrs['email'] = user.email
            
            
        return attrs
