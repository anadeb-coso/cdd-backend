import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from authentication.factories import FacilitatorFactory
from process_manager.factories import (
    ProjectFactory,
    PhaseFactory,
    ActivityFactory,
    CycleFactory,
    TaskFactory,
    TaskSubmissionFactory,
    TaskSubmissionHistoryFactory
)


@pytest.mark.django_db
class TaskDetailAPIViewTest(APITestCase):
    """
    Tests for TaskDetailAPIView
    Verifies the Spike architecture: Task definition + User Submission + History logic.
    """

    def setUp(self):
        # 1. Setup Facilitator and Authentication
        self.facilitator = FacilitatorFactory()
        self.token = Token.objects.create(user=self.facilitator.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)

        # 2. Setup Project Hierarchy
        self.project = ProjectFactory(name="PURS Project")
        self.project.facilitators.add(self.facilitator)

        # 3. Create Phase, Activity, and Cycle with ORDER
        self.phase = PhaseFactory(project=self.project)
        self.activity = ActivityFactory(phase=self.phase)
        self.cycle = CycleFactory(project=self.project)

        # 4. Create the Task
        self.task = TaskFactory(
            project=self.project,
            phase=self.phase,
            activity=self.activity
        )
        self.task.cycles.add(self.cycle)

        # 5. Create a Submission and History
        self.submission = TaskSubmissionFactory(
            task=self.task,
            project=self.project,
            cycle=self.cycle
        )

        # This history record links the facilitator to the submission
        TaskSubmissionHistoryFactory(
            submission=self.submission,
            facilitator=self.facilitator,
            intervention_type='create'
        )

        self.url = reverse('api:process_manager:task-detail', kwargs={'pk': self.task.pk})

    def test_get_task_detail_success(self):
        """Verify task details and correct submission mapping via history."""
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK

        # Verify Task Structure
        assert response.data['task']['id'] == self.task.id
        assert response.data['task']['name'] == self.task.name
        assert response.data['task']['project']['name'] == "PURS Project"
        assert len(response.data['task']['cycles']) == 1

        # Verify Submission Structure
        assert response.data['submission'] is not None
        assert response.data['submission']['id'] == self.submission.id
        assert response.data['submission']['completed'] is False

        # Verify Users Involved (Inferred from History)
        users = response.data['submission']['users_involved']
        assert len(users) == 1
        assert users[0]['facilitator_id'] == self.facilitator.id
        assert users[0]['name'] == self.facilitator.get_name()

    def test_get_task_detail_no_submission_yet(self):
        """Verify that a task without previous history for the user returns submission: null."""
        # Create a new task in the same assigned project
        new_task = TaskFactory(
            project=self.project,
            phase=self.phase,
            activity=self.activity
        )
        url = reverse('api:process_manager:task-detail', kwargs={'pk': new_task.pk})

        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['submission'] is None

    def test_get_task_detail_forbidden(self):
        """Verify that a facilitator cannot access a task from an unassigned project."""
        other_project = ProjectFactory()
        other_task = TaskFactory(project=other_project)

        url = reverse('api:process_manager:task-detail', kwargs={'pk': other_task.pk})
        response = self.client.get(url)

        # Permission IsProjectAssigned should block this
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_task_multiple_facilitators_history(self):
        """Verify that multiple facilitators in history are listed in users_involved."""
        # Add another facilitator to the history of the same submission
        other_fac = FacilitatorFactory()
        TaskSubmissionHistoryFactory(
            submission=self.submission,
            facilitator=other_fac,
        )

        response = self.client.get(self.url)
        users = response.data['submission']['users_involved']

        # Should show both facilitators who participated
        assert len(users) == 2
        names = [u['name'] for u in users]
        assert self.facilitator.get_name() in names
