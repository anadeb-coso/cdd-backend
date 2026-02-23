from django.utils.translation import gettext_lazy as _
from rest_framework import serializers


class CredentialSerializer(serializers.Serializer):
    no_sql_user = serializers.CharField(allow_blank=True, allow_null=True)
    no_sql_pass = serializers.CharField(allow_blank=True, allow_null=True)
    no_sql_db_name = serializers.CharField(allow_blank=True, allow_null=True)
    no_sql_dbs_names = serializers.JSONField(allow_null=True)
    username = serializers.CharField(allow_blank=True, allow_null=True)
    password = serializers.CharField(allow_blank=True, allow_null=True)
    first_name = serializers.CharField(allow_blank=True, allow_null=True)
    last_name = serializers.CharField(allow_blank=True, allow_null=True)
    email = serializers.CharField(allow_blank=True, allow_null=True)
    name = serializers.CharField(allow_blank=True, allow_null=True)
    is_superuser = serializers.BooleanField(allow_null=True)
    groups = serializers.JSONField(allow_null=True)
    # refresh = serializers.CharField(allow_blank=True, allow_null=True)
    # access = serializers.CharField(allow_blank=True, allow_null=True)


class LoginSerializer(serializers.Serializer):
    """
    Serializer for user login credentials.

    This serializer validates username and password for authentication
    and returns appropriate error messages for invalid credentials.
    """

    username = serializers.CharField(max_length=150, help_text=_("Username for authentication"))
    password = serializers.CharField(
        write_only=True, style={'input_type': 'password'}, help_text=_("Password for authentication")
    )
