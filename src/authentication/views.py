from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.constants import (
    INVALID_INPUT_ERROR_MESSAGE,
    INACTIVE_USER_ERROR_MESSAGE,
    LOGIN_ERROR_MESSAGE,
    LOGIN_SUCCESS_MESSAGE, FACILITATOR_GROUP, SUPERUSER_GROUP
)
from authentication.serializers import LoginSerializer

User = get_user_model()


class AuthenticateAPIView(APIView):
    """
    API endpoint for user authentication and token generation.

    This view authenticates users with username/password and returns
    an authentication token for subsequent API requests.

    Authentication is not required for this endpoint as it's used to obtain tokens.
    """

    authentication_classes = []  # No authentication required
    permission_classes = []  # No permissions required

    @swagger_auto_schema(
        operation_summary="User Login",
        operation_description="Authenticate user credentials and return authentication token.",
        request_body=LoginSerializer,
        responses={
            200: openapi.Response(
                description="Login successful",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'token': openapi.Schema(
                            type=openapi.TYPE_STRING, description="Authentication token for API requests"
                        ),
                        'user_id': openapi.Schema(
                            type=openapi.TYPE_INTEGER, description="Unique identifier for the authenticated user"
                        ),
                        'username': openapi.Schema(
                            type=openapi.TYPE_STRING, description="Username of the authenticated user"
                        ),
                        'message': openapi.Schema(type=openapi.TYPE_STRING, description="Success message"),
                    },
                ),
            ),
            400: openapi.Response(
                description="Bad request - Invalid input data",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'error': openapi.Schema(
                            type=openapi.TYPE_STRING, description="Error message describing the validation issue"
                        ),
                        'details': openapi.Schema(
                            type=openapi.TYPE_OBJECT, description="Field-specific validation errors"
                        ),
                    },
                ),
            ),
            401: openapi.Response(
                description="Unauthorized - Invalid credentials",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'error': openapi.Schema(type=openapi.TYPE_STRING, description="Authentication error message"),
                    },
                ),
            ),
            403: openapi.Response(
                description="Forbidden - User account is inactive",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'error': openapi.Schema(type=openapi.TYPE_STRING, description="Account status error message"),
                    },
                ),
            ),
        },
        tags=['Authentication'],
    )
    def post(self, request):
        """
        Handle POST request for user authentication.

        Validates user credentials and returns authentication token.

        Args:
            request: HTTP request containing username and password

        Returns:
            Response: JSON response with token and user info or error message
        """
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "error": INVALID_INPUT_ERROR_MESSAGE,
                    "details": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]

        return self.handle_login(username, password)

    def handle_login(self, username, password):
        """
        Core login logic shared by all login views.
        """
        # Check if user exists and active
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = None

        if user is not None and not user.is_active:
            return Response(
                {"error": INACTIVE_USER_ERROR_MESSAGE},
                status=status.HTTP_403_FORBIDDEN,
            )

        user = authenticate(username=username, password=password)
        if user is None:
            return Response(
                {"error": LOGIN_ERROR_MESSAGE},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Get or create token for the user
        token, _ = Token.objects.get_or_create(user=user)

        # Update last_login
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])

        facilitator_id = None
        if hasattr(user, 'facilitator'):
            groups = [FACILITATOR_GROUP]
            facilitator_id = user.facilitator.id
        else:
            groups = [g.name for g in user.groups.all()]
            if user.is_superuser:
                groups = [SUPERUSER_GROUP] + groups

        return Response(
            {
                "token": token.key,
                "user_id": user.id,
                "facilitator_id": facilitator_id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "is_superuser": user.is_superuser,
                "groups": groups,
                "message": LOGIN_SUCCESS_MESSAGE,
            },
            status=status.HTTP_200_OK,
        )


def get_csrf_token(request):
    print(request)
    return JsonResponse({'csrfToken': get_token(request)})
