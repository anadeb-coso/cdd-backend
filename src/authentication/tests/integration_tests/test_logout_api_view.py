import pytest
from django.urls import reverse
from django.test import override_settings
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from authentication.factories import UserFactory


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class LogoutAPIViewTest(APITestCase):
    """
    Integration tests for the Logout endpoint.
    Verify the invalidation of the authentication token.
    """

    def setUp(self):
        # Create a test user
        self.user = UserFactory()
        # Generate a token for the user
        self.token = Token.objects.create(user=self.user)

        self.url = reverse('authentication:logout')

    def test_logout_success(self):
        """
        Verify that upon logging out, the token is removed and subsequent access is denied.
        """
        # 1. Make sure the token exists in the database before starting
        assert Token.objects.filter(key=self.token.key).exists()

        # 2. Configure credentials and make the POST request
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        response = self.client.post(self.url)

        # 3. Verify successful response
        assert response.status_code == status.HTTP_200_OK
        assert response.data['detail'] == "Successfully logged out."

        # 4. Verify that the token no longer exists in the database
        assert not Token.objects.filter(key=self.token.key).exists()

        # 5. Attempting to access a protected endpoint with the same token
        # (We used the same logout for testing, which requires IsAuthenticated)
        second_response = self.client.post(self.url)
        assert second_response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_unauthenticated(self):
        """
        Verify that you cannot log out without a valid token.
        """
        # We did not configure credentials
        response = self.client.post(self.url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_with_invalid_token(self):
        """
        Verify that a malformed or nonexistent token returns 401.
        """
        self.client.credentials(HTTP_AUTHORIZATION='Token token_falso_123')
        response = self.client.post(self.url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED