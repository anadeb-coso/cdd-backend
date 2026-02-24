import pytest
from django.urls import reverse
from django.test import override_settings
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.authtoken.models import Token

from process_manager.models import Project
from authentication.factories import FacilitatorFactory, UserFactory


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class ProjectTreeAPIViewTest(APITestCase):
    """
    Tests for ProjectTreeAPIView
    Verifies recursive tree structure and project assignment permissions.
    """

    def setUp(self):
        # 1. Setup User and Facilitator
        self.facilitator = FacilitatorFactory()
        self.user = self.facilitator.user
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)

        # 2. Create Project Hierarchy
        # Root Project
        self.root_project = Project.objects.create(
            name="Root Project",
            description="Main root",
            couch_id="root_123"
        )
        # Assign root to facilitator
        self.root_project.facilitators.add(self.facilitator)

        # Child Level 1
        self.child_1 = Project.objects.create(
            name="Child Level 1",
            description="First descendant",
            parent=self.root_project,
            couch_id="child_1_123"
        )

        # Child Level 2 (Grandchild)
        self.grandchild = Project.objects.create(
            name="Grandchild Level 2",
            description="Deep descendant",
            parent=self.child_1,
            couch_id="grandchild_123"
        )

        # 3. Create another project NOT assigned to this user
        self.unassigned_project = Project.objects.create(
            name="Private Project",
            description="No access for you"
        )

        self.url = lambda pk: reverse('api:process_manager:project-tree', kwargs={'pk': pk})

    def test_get_project_tree_success(self):
        """Verify that the full recursive tree is returned for an assigned project."""
        response = self.client.get(self.url(self.root_project.pk))

        assert response.status_code == status.HTTP_200_OK

        # Verify Root
        assert response.data['id'] == self.root_project.pk
        assert response.data['name'] == "Root Project"

        # Verify Level 1
        assert len(response.data['children']) == 1
        child_data = response.data['children'][0]
        assert child_data['name'] == "Child Level 1"
        assert child_data['parent'] == self.root_project.pk

        # Verify Level 2 (Recursion)
        assert len(child_data['children']) == 1
        grandchild_data = child_data['children'][0]
        assert grandchild_data['name'] == "Grandchild Level 2"
        assert grandchild_data['parent'] == self.child_1.pk
        assert grandchild_data['children'] == []  # Leaf node

    def test_get_project_tree_forbidden(self):
        """Verify that accessing a project not assigned to the user returns 403 Forbidden."""
        response = self.client.get(self.url(self.unassigned_project.pk))

        # The permission class IsProjectAssigned should block this
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_project_tree_not_found(self):
        """Verify that requesting a non-existent project ID returns 404."""
        response = self.client.get(self.url(99999))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_project_tree_unauthenticated(self):
        """Verify that unauthenticated requests are rejected with 401."""
        self.client.credentials()  # Clear token
        response = self.client.get(self.url(self.root_project.pk))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_project_tree_regular_user_access(self):
        """Verify that a regular user (not facilitator) can access if assigned via 'users' field."""
        regular_user = UserFactory()
        regular_token = Token.objects.create(user=regular_user)

        # Assign regular user directly to the root project
        self.root_project.users.add(regular_user)

        self.client.credentials(HTTP_AUTHORIZATION='Token ' + regular_token.key)
        response = self.client.get(self.url(self.root_project.pk))

        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == self.root_project.pk