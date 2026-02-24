import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from authentication.factories import FacilitatorFactory, UserFactory
from process_manager.models import Project, Cycle, Phase, Activity, Task


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class AssignmentsAPIViewTest(APITestCase):
    """
    Integration tests for AssignmentsAPIView.
    Ensures that assignments are correctly retrieved and serialized for the logged-in user.
    """

    def setUp(self):
        # Create Facilitator profile
        self.facilitator = FacilitatorFactory()

        # Create Token
        self.token = Token.objects.create(user=self.facilitator.user)

        # Create Project Hierarchy
        self.project = Project.objects.create(name='PURS Project', description='Main project')
        self.project.facilitators.add(self.facilitator)
        self.cycle = Cycle.objects.get(project=self.project, name="Cycle 1")
        self.phase = Phase.objects.create(name='Phase 1', project=self.project, order=1)
        self.activity = Activity.objects.create(
            name='Activity 1', project=self.project, phase=self.phase, order=1, total_tasks=1
        )
        self.task = Task.objects.create(
            name='Task 1', project=self.project, phase=self.phase, activity=self.activity, order=1
        )

        # Updated URL name to match the new urls.py definition
        self.url = reverse('api:process_manager:assignments')

    def test_get_assignments_success(self):
        """Verify successful data retrieval for authenticated facilitator."""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert 'assigned_projects' in response.data
        assert len(response.data['assigned_projects']) == 1

        project = response.data['assigned_projects'][0]
        assert project['name'] == 'PURS Project'
        assert len(project['cycles']) == 1
        assert len(project['tasks']) == 1
        assert project['tasks'][0]['phase_name'] == 'Phase 1'

    def test_get_assignments_unauthenticated(self):
        """Ensure unauthenticated requests are rejected."""
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_assignments_regular_user(self):
        """Ensure users without a Facilitator profile get a 200 OK with their own assignments."""
        other_user = UserFactory()
        other_token = Token.objects.create(user=other_user)

        self.client.credentials(HTTP_AUTHORIZATION='Token ' + other_token.key)
        response = self.client.get(self.url)

        # Since the view now handles regular users, it should return a 200 OK
        assert response.status_code == status.HTTP_200_OK
        assert 'assigned_projects' in response.data

        # The user has not been added to any projects, so the list should be empty
        assert len(response.data['assigned_projects']) == 0
