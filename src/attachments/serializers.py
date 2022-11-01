from django.conf import settings
from django.template.defaultfilters import filesizeformat
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from django.contrib.auth.hashers import make_password

from authentication.models import Facilitator


class AuthMixinSerializer(serializers.Serializer):
    no_sql_user = serializers.CharField()
    no_sql_pass = serializers.CharField()

    def validate(self, attrs):
        username = attrs.get('no_sql_user')
        password = attrs.get('no_sql_pass')
        print(username, password)
        facilitator = Facilitator.objects.filter(no_sql_user=username, no_sql_pass=password)
        if not facilitator:
            raise serializers.ValidationError(self.default_error_messages.get('credentials'), code='authorization')

        return super().validate(attrs)

    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)
        self.default_error_messages['credentials'] = _('Unauthorized access with the credentials provided.')


class FileSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, value):
        max_upload_size = settings.MAX_UPLOAD_SIZE
        if value.size > max_upload_size:
            raise serializers.ValidationError(
                self.default_error_messages['file_size'] % {
                    'max_size': filesizeformat(max_upload_size),
                    'size': filesizeformat(value.size)})
        return value

    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)
        self.default_error_messages['file_size'] = _(
            'Select a file size less than or equal to %(max_size)s. The selected file size is %(size)s.')


class TaskFileSerializer(AuthMixinSerializer, FileSerializer):
    pass
