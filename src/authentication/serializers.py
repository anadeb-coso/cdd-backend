from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from authentication.models import Facilitator
from process_manager.models import Project

User = get_user_model()


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


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class ProjectLiteSerializer(serializers.ModelSerializer):
    """Simple serializer for listing assigned projects in the profile."""

    class Meta:
        model = Project
        fields = ['id', 'name', 'couch_id']


class FacilitatorProfileSerializer(serializers.ModelSerializer):
    assigned_projects = ProjectLiteSerializer(source='projects', many=True, read_only=True)

    class Meta:
        model = Facilitator
        fields = [
            'id', 'phone', 'sex', 'facilitator_type', 'assigned_projects',
            'code', 'develop_mode', 'training_mode',
        ]


class FullProfileSerializer(serializers.Serializer):
    """
    Combines User and Facilitator data into a single response.
    """
    # 'source=*' tells DRF to pass the entire User object to this internal serializer.
    user = UserProfileSerializer(source='*')
    facilitator = serializers.SerializerMethodField()

    def get_facilitator(self, obj):
        if hasattr(obj, 'facilitator'):
            return FacilitatorProfileSerializer(obj.facilitator).data
        return None

