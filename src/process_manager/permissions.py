from rest_framework import permissions


class IsProjectAssigned(permissions.BasePermission):
    """
    Permission to allow access only if the project is assigned to the user.
    - If user has a facilitator profile: checks Project.facilitators
    - If user is a regular user: checks Project.users
    """

    def has_object_permission(self, request, view, obj):
        user = request.user

        # Check if user has a facilitator profile
        if hasattr(user, 'facilitator'):
            return obj.facilitators.filter(id=user.facilitator.id).exists()

        # Fallback to regular user assignment
        return obj.users.filter(id=user.id).exists()