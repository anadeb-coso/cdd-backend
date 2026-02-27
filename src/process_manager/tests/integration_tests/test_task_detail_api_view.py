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
    Tests for TaskDetailAPIView.

    `administrative_level_id` is an optional query parameter.
    When provided, the response includes the matching submission for the
    authenticated facilitator at that location.
    When omitted, `submission` is null.
    """

    def setUp(self):
        # 1. Authentication
        self.facilitator = FacilitatorFactory()
        self.token = Token.objects.create(user=self.facilitator.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)

        # 2. Project hierarchy
        self.project = ProjectFactory()
        self.project.facilitators.add(self.facilitator)

        self.phase = PhaseFactory(project=self.project)
        self.activity = ActivityFactory(phase=self.phase)
        self.cycle = CycleFactory(project=self.project)

        # 3. Task
        self.task = TaskFactory(
            project=self.project,
            phase=self.phase,
            activity=self.activity,
            support_attachments=True,
        )
        self.task.cycles.add(self.cycle)

        # 4. Submission scoped to a specific administrative level
        self.administrative_level_id = 1986
        self.submission = TaskSubmissionFactory(
            task=self.task,
            facilitator=self.facilitator,
            cycle=self.cycle,
            administrative_level_id=self.administrative_level_id,
            completed=False,
        )
        TaskSubmissionHistoryFactory(
            submission=self.submission,
            intervention_type='create'
        )

        self.url = reverse('api:process_manager:task-detail', kwargs={'pk': self.task.pk})

    def _url_with_level(self, administrative_level_id):
        """Helper: build URL with administrative_level_id query param."""
        return f"{self.url}?administrative_level_id={administrative_level_id}"

    # -------------------------------------------------------------------------
    # Task structure
    # -------------------------------------------------------------------------

    def test_get_task_detail_returns_correct_task_fields(self):
        """Task fields including the new support_attachments are returned correctly."""
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK

        task_data = response.data['task']
        assert task_data['id'] == self.task.id
        assert task_data['name'] == self.task.name
        assert task_data['project']['name'] == self.project.name
        assert len(task_data['cycles']) == 1
        assert 'support_attachments' in task_data
        assert task_data['support_attachments'] is True

    def test_get_task_detail_support_attachments_false(self):
        """support_attachments=False is serialized correctly."""
        task = TaskFactory(
            project=self.project,
            phase=self.phase,
            activity=self.activity,
            support_attachments=False,
        )
        url = reverse('api:process_manager:task-detail', kwargs={'pk': task.pk})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['task']['support_attachments'] is False

    # -------------------------------------------------------------------------
    # administrative_level_id — submission scoping
    # -------------------------------------------------------------------------

    def test_get_task_detail_without_administrative_level_returns_null_submission(self):
        """
        Omitting administrative_level_id must return submission: null,
        regardless of whether submissions exist for this facilitator.
        """
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['submission'] is None

    def test_get_task_detail_with_administrative_level_returns_submission(self):
        """When administrative_level_id matches a submission, it is returned."""
        response = self.client.get(self._url_with_level(self.administrative_level_id))

        assert response.status_code == status.HTTP_200_OK

        submission_data = response.data['submission']
        assert submission_data is not None
        assert submission_data['id'] == self.submission.id
        assert submission_data['completed'] is False

    def test_get_task_detail_with_unknown_administrative_level_returns_null_submission(self):
        """
        Providing an administrative_level_id with no matching submission
        returns submission: null — not a 404.
        """
        response = self.client.get(self._url_with_level(9999))

        assert response.status_code == status.HTTP_200_OK
        assert response.data['submission'] is None

    def test_get_task_detail_does_not_return_other_facilitators_submission(self):
        """
        An administrative_level_id that has a submission belonging to a
        different facilitator must not be exposed — submission must be null.
        """
        other_facilitator = FacilitatorFactory()
        self.project.facilitators.add(other_facilitator)
        other_submission = TaskSubmissionFactory(
            task=self.task,
            facilitator=other_facilitator,
            cycle=self.cycle,
            administrative_level_id=self.administrative_level_id,
        )

        # Authenticated as self.facilitator — should not see other_facilitator's submission
        response = self.client.get(self._url_with_level(self.administrative_level_id))

        assert response.status_code == status.HTTP_200_OK
        submission_data = response.data['submission']
        assert submission_data['id'] != other_submission.id
        assert submission_data['id'] == self.submission.id

    def test_get_task_detail_sibling_administrative_level_not_leaked(self):
        """
        Providing an administrative_level_id must not return a submission
        from a different administrative level of the same facilitator.
        """
        sibling_submission = TaskSubmissionFactory(
            task=self.task,
            facilitator=self.facilitator,
            cycle=self.cycle,
            administrative_level_id=2001,
        )

        response = self.client.get(self._url_with_level(self.administrative_level_id))

        assert response.status_code == status.HTTP_200_OK
        assert response.data['submission']['id'] != sibling_submission.id
        assert response.data['submission']['id'] == self.submission.id

    # -------------------------------------------------------------------------
    # users_involved
    # -------------------------------------------------------------------------

    def test_get_task_detail_users_involved_from_history(self):
        """users_involved lists the facilitators linked via submission history."""
        response = self.client.get(self._url_with_level(self.administrative_level_id))

        users = response.data['submission']['users_involved']
        assert len(users) == 1
        assert users[0]['facilitator_id'] == self.facilitator.id
        assert users[0]['name'] == self.facilitator.get_name()

    def test_get_task_detail_multiple_facilitators_in_users_involved(self):
        """Multiple history entries from different facilitators produce multiple users_involved."""
        other_fac = FacilitatorFactory()
        TaskSubmissionHistoryFactory(
            submission=self.submission,
            facilitator=other_fac,
        )

        response = self.client.get(self._url_with_level(self.administrative_level_id))

        users = response.data['submission']['users_involved']
        assert len(users) == 2
        names = [u['name'] for u in users]
        assert self.facilitator.get_name() in names
        assert other_fac.get_name() in names

    def test_get_task_detail_users_involved_deduplicated(self):
        """Multiple history entries from the same facilitator produce only one users_involved entry."""
        TaskSubmissionHistoryFactory(
            submission=self.submission,
            intervention_type='update'
        )

        response = self.client.get(self._url_with_level(self.administrative_level_id))

        users = response.data['submission']['users_involved']
        assert len(users) == 1

    # -------------------------------------------------------------------------
    # Authorization
    # -------------------------------------------------------------------------

    def test_get_task_detail_no_submission_for_new_task(self):
        """A task with no submission for this facilitator returns submission: null."""
        new_task = TaskFactory(
            project=self.project,
            phase=self.phase,
            activity=self.activity
        )
        url = reverse('api:process_manager:task-detail', kwargs={'pk': new_task.pk})

        response = self.client.get(f"{url}?administrative_level_id={self.administrative_level_id}")

        assert response.status_code == status.HTTP_200_OK
        assert response.data['submission'] is None

    def test_get_task_detail_unassigned_project_returns_403(self):
        """A facilitator cannot access a task from a project they are not assigned to."""
        other_project = ProjectFactory()
        other_task = TaskFactory(project=other_project)

        url = reverse('api:process_manager:task-detail', kwargs={'pk': other_task.pk})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_task_detail_unauthenticated_returns_401(self):
        """Requests without a token are rejected with 401."""
        self.client.credentials()
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED