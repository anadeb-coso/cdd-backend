import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from authentication.factories import FacilitatorFactory, UserFactory
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
class TaskCompletionToggleAPIViewTest(APITestCase):
    """
    Integration tests for TaskCompletionToggleAPIView.

    The administrative_level_id is a path parameter because it identifies
    *which* submission to act on — it is context for resource lookup, not
    a value being modified.
    """

    def setUp(self):
        # 1. Authentication
        self.facilitator = FacilitatorFactory()
        self.token = Token.objects.create(user=self.facilitator.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)

        # 2. Project structure
        self.project = ProjectFactory()
        self.project.facilitators.add(self.facilitator)
        self.phase = PhaseFactory(project=self.project)
        self.activity = ActivityFactory(phase=self.phase, project=self.project)
        self.cycle = CycleFactory(project=self.project)

        # 3. Task
        self.task = TaskFactory(
            project=self.project,
            phase=self.phase,
            activity=self.activity
        )
        self.task.cycles.add(self.cycle)

        # 4. Submission for a specific administrative level
        self.administrative_level_id = 1986
        self.submission = TaskSubmissionFactory(
            task=self.task,
            facilitator=self.facilitator,
            project=self.project,
            cycle=self.cycle,
            administrative_level_id=self.administrative_level_id,
            completed=False,
            completed_date=None
        )
        TaskSubmissionHistoryFactory(
            submission=self.submission,
            intervention_type='create'
        )

        self.url = self._build_url(self.task.pk, self.administrative_level_id)

    def _build_url(self, task_pk, administrative_level_id):
        return reverse(
            'api:process_manager:task-toggle-completion',
            kwargs={'pk': task_pk, 'administrative_level_id': administrative_level_id}
        )

    # -------------------------------------------------------------------------
    # Happy path
    # -------------------------------------------------------------------------

    def test_patch_task_complete_success(self):
        """Setting completed=True updates status and sets completed_date."""
        response = self.client.patch(self.url, {'completed': True}, format='json')

        assert response.status_code == status.HTTP_200_OK

        self.submission.refresh_from_db()
        assert self.submission.completed is True
        assert self.submission.completed_date is not None

        last_history = self.submission.history.latest('created_at')
        assert last_history.intervention_type == 'complete'
        assert 'completed_date' in last_history.fields_updated

    def test_patch_task_reopen_success(self):
        """Setting completed=False clears completed_date."""
        self.submission.completed = True
        self.submission.completed_date = timezone.now()
        self.submission.save()

        response = self.client.patch(self.url, {'completed': False}, format='json')

        assert response.status_code == status.HTTP_200_OK

        self.submission.refresh_from_db()
        assert self.submission.completed is False
        assert self.submission.completed_date is None

        last_history = self.submission.history.latest('created_at')
        assert last_history.intervention_type == 'reopen'

    def test_patch_task_complete_is_idempotent(self):
        """
        Toggling to the current status must still succeed and produce
        a history entry, so the mobile retry queue is safe to replay.
        """
        self.submission.completed = True
        self.submission.completed_date = timezone.now()
        self.submission.save()

        history_count_before = self.submission.history.count()

        response = self.client.patch(self.url, {'completed': True}, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert self.submission.history.count() == history_count_before + 1

    # -------------------------------------------------------------------------
    # administrative_level_id scoping
    # -------------------------------------------------------------------------

    def test_patch_unknown_administrative_level_returns_404(self):
        """
        A valid task but an administrative_level_id with no submission
        for this facilitator must return 404.
        """
        url = self._build_url(self.task.pk, administrative_level_id=9999)
        response = self.client.patch(url, {'completed': True}, format='json')

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_patch_does_not_affect_sibling_submission(self):
        """
        Toggling one administrative level must not modify the submission
        for the same task under a different administrative level.
        """
        sibling_submission = TaskSubmissionFactory(
            task=self.task,
            facilitator=self.facilitator,
            project=self.project,
            cycle=self.cycle,
            administrative_level_id=2001,
            completed=False,
        )

        response = self.client.patch(self.url, {'completed': True}, format='json')
        assert response.status_code == status.HTTP_200_OK

        sibling_submission.refresh_from_db()
        assert sibling_submission.completed is False

    # -------------------------------------------------------------------------
    # Authorization
    # -------------------------------------------------------------------------

    def test_patch_unauthenticated_returns_401(self):
        """Requests without a token must be rejected with 401."""
        self.client.credentials()
        response = self.client.patch(self.url, {'completed': True}, format='json')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_patch_no_facilitator_profile_returns_403(self):
        """A plain User without a Facilitator profile receives 403."""
        plain_user = UserFactory()
        plain_token = Token.objects.create(user=plain_user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + plain_token.key)

        response = self.client.patch(self.url, {'completed': True}, format='json')

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data['detail'] == (
            "Authenticated user does not have an associated Facilitator profile."
        )

    def test_patch_unassigned_project_returns_403(self):
        """A facilitator not assigned to the project is rejected with 403."""
        other_project = ProjectFactory()
        other_task = TaskFactory(project=other_project)

        url = self._build_url(other_task.pk, self.administrative_level_id)
        response = self.client.patch(url, {'completed': True}, format='json')

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_patch_other_facilitators_submission_returns_404(self):
        """
        A facilitator assigned to the same project cannot toggle another
        facilitator's submission — it is simply invisible to them (404).
        """
        other_facilitator = FacilitatorFactory()
        self.project.facilitators.add(other_facilitator)
        other_token = Token.objects.create(user=other_facilitator.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + other_token.key)

        # self.submission belongs to self.facilitator, not other_facilitator
        response = self.client.patch(self.url, {'completed': True}, format='json')

        assert response.status_code == status.HTTP_404_NOT_FOUND

    # -------------------------------------------------------------------------
    # Input validation
    # -------------------------------------------------------------------------

    def test_patch_no_submission_for_task_returns_404(self):
        """404 when the task exists but has no submission for this facilitator + level."""
        new_task = TaskFactory(project=self.project)
        new_task.cycles.add(self.cycle)

        url = self._build_url(new_task.pk, self.administrative_level_id)
        response = self.client.patch(url, {'completed': True}, format='json')

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_patch_invalid_boolean_returns_400(self):
        """400 if 'completed' is a string instead of a boolean."""
        response = self.client.patch(
            self.url, {'completed': 'invalid value'}, format='json'
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_patch_missing_completed_field_returns_400(self):
        """400 if the 'completed' field is absent from the payload."""
        response = self.client.patch(self.url, {}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_patch_extra_fields_in_payload_are_ignored(self):
        """Extra payload fields must not cause an error."""
        payload = {'completed': True, 'unexpected_field': 'ignored'}
        response = self.client.patch(self.url, payload, format='json')

        assert response.status_code == status.HTTP_200_OK