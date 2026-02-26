from rest_framework import permissions


class IsProjectAssigned(permissions.BasePermission):
    """
    Permission to allow access only if the project is assigned to the user.
    - If user has a facilitator profile: checks Project.facilitators
    - If user is a regular user: checks Project.users
    """

    def has_object_permission(self, request, view, obj):
        user = request.user

        # Logic for determining the project according to the type of object
        if hasattr(obj, 'facilitators'):  # If the object is a Project
            project = obj
        elif hasattr(obj, 'project'):  # If the object is Task, TaskSubmission, etc.
            project = obj.project
        else:
            return False

        # Check if user has a facilitator profile
        if hasattr(user, 'facilitator'):
            return project.facilitators.filter(id=user.facilitator.id).exists()

        # Fallback to regular user assignment
        return project.users.filter(id=user.id).exists()