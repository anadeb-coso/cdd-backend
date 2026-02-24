from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from process_manager.models import Project
from process_manager.permissions import IsProjectAssigned
from process_manager.serializers import ProjectAssignmentSerializer
from process_manager.serializers import ProjectTreeSerializer


class AssignmentsAPIView(APIView):
    """
    API View to retrieve all assignments (Projects, Cycles, Tasks)
    for the currently authenticated user (Admin or Facilitator).
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id="get_assignments",
        operation_description="Fetches the list of projects, cycles, and tasks assigned to the authenticated "
                              "user for the current session.",
        tags=['Assignments'],
        security=[{'Token': []}],
        responses={
            200: openapi.Response(
                description="Successful retrieval of assignments.",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'assigned_projects': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            description="List of projects assigned to the user",
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'name': openapi.Schema(type=openapi.TYPE_STRING),
                                    'description': openapi.Schema(type=openapi.TYPE_STRING),
                                    'cycles': openapi.Schema(
                                        type=openapi.TYPE_ARRAY,
                                        items=openapi.Schema(
                                            type=openapi.TYPE_OBJECT,
                                            properties={
                                                'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                                'name': openapi.Schema(type=openapi.TYPE_STRING),
                                                'order': openapi.Schema(type=openapi.TYPE_INTEGER),
                                            }
                                        )
                                    ),
                                    'tasks': openapi.Schema(
                                        type=openapi.TYPE_ARRAY,
                                        items=openapi.Schema(
                                            type=openapi.TYPE_OBJECT,
                                            properties={
                                                'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                                'name': openapi.Schema(type=openapi.TYPE_STRING),
                                                'phase_name': openapi.Schema(type=openapi.TYPE_STRING),
                                                'activity_name': openapi.Schema(type=openapi.TYPE_STRING),
                                            }
                                        )
                                    ),
                                }
                            )
                        )
                    }
                )
            ),
            401: openapi.Response(
                description="Unauthorized - Authentication credentials were not provided or are invalid."),
        }
    )
    def get(self, request, *args, **kwargs):
        user = request.user

        # Validates if the user has a facilitator profile linked
        if hasattr(user, 'facilitator'):
            # Extract the facilitator profile linked to the authenticated user via the OneToOneField
            user = request.user.facilitator

        # Fetch projects assigned to this user via the ManyToMany relationship
        # prefetch_related is crucial here to prevent N+1 query performance issues
        assigned_projects = user.projects.prefetch_related(
            'cycle_set',
            'task_set__phase',
            'task_set__activity'
        ).all()

        # Serialize the query set
        serializer = ProjectAssignmentSerializer(assigned_projects, many=True)

        return Response({
            "assigned_projects": serializer.data
        }, status=status.HTTP_200_OK)


class ProjectTreeAPIView(RetrieveAPIView):
    """
    API View to retrieve a project and all its descendants in a tree structure.
    Access is restricted to users assigned to the project.
    """
    queryset = Project.objects.all()
    serializer_class = ProjectTreeSerializer
    # Combine IsAuthenticated (login check) and IsProjectAssigned (ownership check)
    permission_classes = [IsAuthenticated, IsProjectAssigned]

    @swagger_auto_schema(
        operation_id="get_project_tree",
        operation_description="Returns the recursive tree of subprojects. Only accessible if the project is assigned to the user.",
        tags=['Projects'],
        responses={
            200: ProjectTreeSerializer(),
            403: "Forbidden - You are not assigned to this project.",
            404: "Not Found - Project does not exist."
        }
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        """
        Optimization: prefetch children to reduce database hits during recursion.
        """
        return Project.objects.prefetch_related('children')
