import pytest
from django.contrib.auth.models import User, Group
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from authentication.constants import (
    INACTIVE_USER_ERROR_MESSAGE,
    INVALID_INPUT_ERROR_MESSAGE,
    LOGIN_ERROR_MESSAGE,
    LOGIN_SUCCESS_MESSAGE,
    FACILITATOR_GROUP,
    SUPERUSER_GROUP,
)
from authentication.factories import UserFactory, FacilitatorFactory


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class AuthenticateAPIViewTest(APITestCase):
    """
    Test cases for the authentication login API endpoint.

    This test class covers various scenarios including successful login,
    invalid credentials, inactive users, and response format validation.
    """

    def setUp(self):
        """Set up test data and URL for each test."""
        self.url = reverse("authentication:obtain_auth_credentials")

        # Create test user with known credentials
        self.username = "testuser"
        self.password = "testpassword123"

        self.user = UserFactory(username=self.username, password=self.password, is_active=True)
        group = Group.objects.create(name="Test")
        self.user.groups.add(group)

    def test_successful_login(self):
        """Test successful login with valid credentials."""
        login_data = {'username': self.username, 'password': self.password}
        before = timezone.now()
        response = self.client.post(self.url, login_data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, dict)

        # Check required fields in response
        required_fields = [
            'token',
            'user_id',
            'facilitator_id',
            'username',
            'first_name',
            'last_name',
            'is_superuser',
            'groups',
            'message'
        ]
        for field in required_fields:
            assert field in response.data

        # Verify response data
        assert isinstance(response.data['token'], str)
        assert len(response.data['token']) == 40  # Token length
        assert response.data['user_id'] == self.user.id
        assert response.data['facilitator_id'] is None
        assert response.data['username'] == self.username
        assert response.data['first_name'] == self.user.first_name
        assert response.data['last_name'] == self.user.last_name
        assert response.data['email'] == self.user.email
        assert response.data['is_superuser'] == self.user.is_superuser == False
        assert response.data['groups'] == ['Test']
        assert response.data['message'] == LOGIN_SUCCESS_MESSAGE

        # Verify token was created in database
        token = Token.objects.get(user=self.user)
        assert token.key == response.data['token']

        # Check last_login was updated
        self.user.refresh_from_db()
        assert self.user.last_login >= before

    def test_successful_facilitator_login(self):
        """Test successful login with facilitator."""
        login_data = {'username': self.username, 'password': self.password}
        facilitator = FacilitatorFactory(user=self.user)
        response = self.client.post(self.url, login_data, format='json')

        assert response.status_code == status.HTTP_200_OK

        # Verify response data
        assert response.data['facilitator_id'] == facilitator.id
        assert response.data['groups'] == [FACILITATOR_GROUP]

    def test_successful_superuser_login(self):
        """Test successful login with superuser."""
        login_data = {'username': self.username, 'password': self.password}
        User.objects.filter(id=self.user.id).update(is_superuser=True)
        response = self.client.post(self.url, login_data, format='json')

        assert response.status_code == status.HTTP_200_OK

        # Verify response data
        assert response.data['is_superuser'] is True
        assert response.data['groups'] == [SUPERUSER_GROUP, 'Test']

    def test_invalid_username(self):
        """Test login with invalid username."""
        login_data = {'username': 'invaliduser', 'password': self.password}

        response = self.client.post(self.url, login_data, format='json')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data['error'] == LOGIN_ERROR_MESSAGE

    def test_invalid_password(self):
        """Test login with invalid password."""
        login_data = {'username': self.username, 'password': 'wrongpassword'}

        response = self.client.post(self.url, login_data, format='json')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data['error'] == LOGIN_ERROR_MESSAGE

    def test_missing_username(self):
        """Test login with missing username field."""
        login_data = {'password': self.password}

        response = self.client.post(self.url, login_data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error'] == INVALID_INPUT_ERROR_MESSAGE
        assert 'username' in response.data['details']

    def test_missing_password(self):
        """Test login with missing password field."""
        login_data = {'username': self.username}

        response = self.client.post(self.url, login_data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error'] == INVALID_INPUT_ERROR_MESSAGE
        assert 'password' in response.data['details']

    def test_empty_credentials(self):
        """Test login with empty username and password."""
        login_data = {'username': '', 'password': ''}

        response = self.client.post(self.url, login_data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'details' in response.data
        assert response.data['error'] == INVALID_INPUT_ERROR_MESSAGE

    def test_inactive_user(self):
        """Test login with inactive user account."""
        # Create inactive user
        password = 'password123'
        inactive_user = UserFactory(password=password, is_active=False)

        login_data = {'username': inactive_user.username, 'password': password}

        response = self.client.post(self.url, login_data, format='json')

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data['error'] == INACTIVE_USER_ERROR_MESSAGE

    def test_reuse_existing_token(self):
        """Test that existing token is returned for user who already has one."""
        # Create token for user first
        existing_token = Token.objects.create(user=self.user)

        login_data = {'username': self.username, 'password': self.password}

        response = self.client.post(self.url, login_data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['token'] == existing_token.key

        # Verify only one token exists for user
        tokens_count = Token.objects.filter(user=self.user).count()
        assert tokens_count == 1

    def test_multiple_successful_logins(self):
        """Test multiple successful logins return same token."""
        login_data = {'username': self.username, 'password': self.password}

        # First login
        response1 = self.client.post(self.url, login_data, format='json')
        assert response1.status_code == status.HTTP_200_OK
        token1 = response1.data['token']

        # Second login
        response2 = self.client.post(self.url, login_data, format='json')
        assert response2.status_code == status.HTTP_200_OK
        token2 = response2.data['token']

        # Should be the same token
        assert token1 == token2

    def test_whitespace_in_username(self):
        """Test login with whitespace in credentials."""

        existing_token = Token.objects.create(user=self.user)

        login_data = {'username': f" {self.username} ", 'password': self.password}  # Whitespace around username

        response = self.client.post(self.url, login_data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['token'] == existing_token.key

    def test_sql_injection_attempt(self):
        """Test security against SQL injection attempts."""
        login_data = {'username': "admin'; DROP TABLE users; --", 'password': "password"}

        response = self.client.post(self.url, login_data, format='json')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data['error'] == LOGIN_ERROR_MESSAGE

        # Verify user still exists (table wasn't dropped)
        assert User.objects.filter(username=self.username).exists()

    def test_post_method_only(self):
        """Test that only POST method is allowed."""
        login_data = {'username': self.username, 'password': self.password}

        # GET should not be allowed
        response_get = self.client.get(self.url)
        assert response_get.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

        # PUT should not be allowed
        response_put = self.client.put(self.url, login_data, format='json')
        assert response_put.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

        # DELETE should not be allowed
        response_delete = self.client.delete(self.url)
        assert response_delete.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

        # PATCH should not be allowed
        response_patch = self.client.patch(self.url, login_data, format='json')
        assert response_patch.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

        # POST should work
        response_post = self.client.post(self.url, login_data, format='json')
        assert response_post.status_code == status.HTTP_200_OK

    def test_content_type_header(self):
        """Test that the response has correct content type."""
        login_data = {'username': self.username, 'password': self.password}

        response = self.client.post(self.url, login_data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert 'application/json' in response.get('Content-Type', '')

    def test_response_format_consistency(self):
        """Test that response format is consistent across different scenarios."""
        # Test successful login format
        login_data = {'username': self.username, 'password': self.password}

        response = self.client.post(self.url, login_data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, dict)

        # Test error format
        invalid_login_data = {'username': 'invalid', 'password': 'invalid'}

        error_response = self.client.post(self.url, invalid_login_data, format='json')
        assert error_response.status_code == status.HTTP_401_UNAUTHORIZED
        assert isinstance(error_response.data, dict)
        assert 'error' in error_response.data

    def test_long_username_handling(self):
        """Test handling of very long usernames."""
        long_username = 'a' * 200  # Longer than max_length
        login_data = {'username': long_username, 'password': self.password}

        response = self.client.post(self.url, login_data, format='json')

        # Should return validation error for too long username
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error'] == INVALID_INPUT_ERROR_MESSAGE

    def test_unicode_credentials(self):
        """Test handling of Unicode characters in credentials."""
        # Create user with Unicode username
        unicode_username = "тестユーザー"
        unicode_password = "пароль123"

        unicode_user = UserFactory(
            username=unicode_username, email='user@example.com', password=unicode_password, is_active=True
        )

        login_data = {'username': unicode_username, 'password': unicode_password}

        response = self.client.post(self.url, login_data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['username'] == unicode_username
        assert response.data['user_id'] == unicode_user.id
