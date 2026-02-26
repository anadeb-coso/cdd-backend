import pytest
from django.urls import reverse
from django.test import override_settings
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from django.contrib.auth import get_user_model

from authentication.factories import FacilitatorFactory
from process_manager.models import Project

User = get_user_model()


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class ProfileAPIViewTest(APITestCase):
    """
    Tests for ProfileAPIView
    Verifies that User and Facilitator (JSON fields included) are correctly returned.
    """

    def setUp(self):
        # 1. Create Facilitator via Factory
        self.facilitator = FacilitatorFactory(
            sex="M",
            code="FAC-001",
            phone="22899999999",
            develop_mode=False,
            training_mode=True
        )
        self.user = self.facilitator.user
        self.token = Token.objects.create(user=self.user)

        # 3. Assign a project
        self.project = Project.objects.create(name="COSO", couch_id="couch_10")
        self.project.facilitators.add(self.facilitator)

        self.url = reverse('authentication:user-profile')

    def test_get_profile_success(self):
        """Verify the complete profile response for an authenticated facilitator."""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK

        # Check User Data
        assert response.data['user']['username'] == self.user.username
        assert 'first_name' in response.data['user']

        # Check Facilitator Data
        fac_data = response.data['facilitator']
        assert fac_data['sex'] == "M"
        assert fac_data['phone'] == "22899999999"
        assert fac_data['facilitator_type'] == "community_facilitator"
        assert fac_data['code'] == "FAC-001"
        assert fac_data['develop_mode'] is False
        assert fac_data['training_mode'] is True

        # Check Assigned Projects
        assert len(fac_data['assigned_projects']) == 1
        assert fac_data['assigned_projects'][0]['id'] == self.project.id
        assert fac_data['assigned_projects'][0]['name'] == "COSO"

    def test_get_profile_no_facilitator(self):
        """Verify that a user without a facilitator profile gets facilitator: null."""
        admin_user = User.objects.create_user(username='admin_only', password='password')
        admin_token = Token.objects.create(user=admin_user)

        self.client.credentials(HTTP_AUTHORIZATION='Token ' + admin_token.key)
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['user']['username'] == 'admin_only'
        assert response.data['facilitator'] is None

    def test_get_profile_unauthenticated(self):
        """Verify that unauthenticated requests are rejected."""
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED