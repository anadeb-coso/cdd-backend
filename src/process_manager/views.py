from django.core.exceptions import ObjectDoesNotExist
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from process_manager.serializers import ProjectAssignmentSerializer


class FacilitatorAssignmentsAPIView(APIView):
    """
    API View to retrieve all assignments (Projects, Cycles, Tasks)
    for the currently authenticated facilitator.
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id="get_facilitator_assignments",
        operation_description="Fetches the list of projects, cycles, and tasks assigned to the authenticated "
                              "facilitator for the current session.",
        security=[{'Token': []}],
        responses={
            200: openapi.Response(
                description="Successful retrieval of assignments.",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'assigned_projects': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            description="List of projects assigned to the facilitator",
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'name': openapi.Schema(type=openapi.TYPE_STRING),
                                    'description': openapi.Schema(type=openapi.TYPE_STRING),
                                    'cycles': openapi.Schema(type=openapi.TYPE_ARRAY,
                                                             items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                                    'tasks': openapi.Schema(type=openapi.TYPE_ARRAY,
                                                            items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                                }
                            )
                        )
                    }
                )
            ),
            401: openapi.Response(
                description="Unauthorized - Authentication credentials were not provided or are invalid."),
            403: openapi.Response(description="Forbidden - The authenticated user does not have a Facilitator profile.")
        }
    )
    def get(self, request, *args, **kwargs):
        try:
            # Extract the facilitator profile linked to the authenticated user via the OneToOneField
            facilitator = request.user.facilitator
        except ObjectDoesNotExist:
            return Response(
                {"error": "The authenticated user is not associated with any facilitator profile."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Fetch projects assigned to this facilitator via the ManyToMany relationship
        # prefetch_related is crucial here to prevent N+1 query performance issues
        assigned_projects = facilitator.projects.prefetch_related(
            'cycle_set',
            'task_set__phase',
            'task_set__activity'
        ).all()

        # Serialize the query set
        serializer = ProjectAssignmentSerializer(assigned_projects, many=True)

        return Response({
            "assigned_projects": serializer.data
        }, status=status.HTTP_200_OK)
