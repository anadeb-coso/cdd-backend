from drf_spectacular.utils import extend_schema
from rest_framework import parsers, renderers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.serializers import CredentialSerializer, UserAuthSerializer


class AuthenticateAPIView(APIView):
    throttle_classes = ()
    permission_classes = ()
    parser_classes = (parsers.FormParser, parsers.MultiPartParser, parsers.JSONParser,)
    renderer_classes = (renderers.JSONRenderer,)
    serializer_class = UserAuthSerializer

    def get_serializer_context(self):
        return {
            'request': self.request,
            'format': self.format_kwarg,
            'view': self
        }

    def get_serializer(self, *args, **kwargs):
        kwargs['context'] = self.get_serializer_context()
        return self.serializer_class(*args, **kwargs)

    @extend_schema(
        request=UserAuthSerializer,
        responses={200: CredentialSerializer},
    )
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        credentials = {
            'no_sql_user': serializer.validated_data['no_sql_user'],
            'no_sql_pass': serializer.validated_data['no_sql_pass'],
            'no_sql_db_name': serializer.validated_data['no_sql_db_name']
        }
        credential_serializer = CredentialSerializer(data=credentials)
        credential_serializer.is_valid(raise_exception=True)
        return Response(credential_serializer.data, status=status.HTTP_200_OK)
