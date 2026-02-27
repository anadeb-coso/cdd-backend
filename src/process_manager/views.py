from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from process_manager.models import Project, Task, TaskSubmission, TaskSubmissionHistory
from process_manager.permissions import IsProjectAssigned
from process_manager.serializers import (
    ProjectAssignmentSerializer,
    ProjectTreeSerializer,
    SubmissionSerializer,
    TaskWithSubmissionSerializer, TaskCompletionToggleSerializer
)


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


class TaskDetailAPIView(RetrieveAPIView):
    """
    Retrieves the task definition and the specific submission for the
    authenticated facilitator.

    If `administrative_level_id` is provided as a query parameter, the response
    includes the submission for that location. Otherwise, `submission` is null.
    """
    queryset = Task.objects.all()
    serializer_class = TaskWithSubmissionSerializer
    permission_classes = [IsAuthenticated, IsProjectAssigned]

    @swagger_auto_schema(
        operation_id="get_task_detail",
        operation_description=(
            "Returns task metadata and, optionally, the facilitator's submission "
            "for a specific administrative level.\n\n"
            "If `administrative_level_id` is omitted, the `submission` field is `null`."
        ),
        manual_parameters=[
            openapi.Parameter(
                name='administrative_level_id',
                in_=openapi.IN_QUERY,
                description=(
                    "ID of the administrative level. "
                    "When provided, the response includes the matching submission."
                ),
                type=openapi.TYPE_INTEGER,
                required=False,
            ),
        ],
        responses={
            200: TaskWithSubmissionSerializer(),
            401: openapi.Response(description="Unauthenticated."),
            403: openapi.Response(description="Not assigned to this project."),
            404: openapi.Response(description="Task not found."),
        },
        tags=['Tasks']
    )
    def get(self, request, *args, **kwargs):
        # Decorated for swagger — delegate to retrieve() without touching the context
        return self.retrieve(request, *args, **kwargs)

    def get_queryset(self):
        return Task.objects.select_related(
            'project', 'phase', 'activity'
        ).prefetch_related('cycles')

    def get_serializer_context(self):
        context = super().get_serializer_context()

        facilitator = getattr(self.request.user, 'facilitator', None)
        if not facilitator:
            return context

        administrative_level_id = self.request.query_params.get('administrative_level_id')

        if not administrative_level_id:
            # No location provided — submission will be null, no DB query needed
            return context

        context['preloaded_submissions'] = list(
            TaskSubmission.objects.filter(
                facilitator=facilitator,
                administrative_level_id=administrative_level_id,
            ).prefetch_related(
                Prefetch(
                    'history',
                    queryset=TaskSubmissionHistory.objects.select_related('facilitator')
                )
            )
        )
        return context


class TaskCompletionToggleAPIView(APIView):
    """
    Toggles the completion status of a TaskSubmission identified by
    task ID and administrative level ID.

    The submission is scoped to the authenticated facilitator, so a
    facilitator can only toggle their own submissions.
    """
    permission_classes = [IsAuthenticated, IsProjectAssigned]

    @swagger_auto_schema(
        operation_id="toggle_task_completion",
        operation_description=(
            "Toggles the `completed` status of a task submission for the authenticated "
            "facilitator at the given administrative level.\n\n"
            "- Setting `completed=true` sets `completed_date` to now.\n"
            "- Setting `completed=false` clears `completed_date`.\n\n"
            "An audit entry is created in `TaskSubmissionHistory` on every call."
        ),
        manual_parameters=[
            openapi.Parameter(
                name='pk',
                in_=openapi.IN_PATH,
                description="ID of the Task.",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
            openapi.Parameter(
                name='administrative_level_id',
                in_=openapi.IN_PATH,
                description="ID of the administrative level that identifies the submission.",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
        ],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['completed'],
            properties={
                'completed': openapi.Schema(
                    type=openapi.TYPE_BOOLEAN,
                    description="New completion status."
                ),
            },
        ),
        responses={
            200: SubmissionSerializer,
            400: openapi.Response(description="Invalid payload — 'completed' missing or not boolean."),
            401: openapi.Response(description="Unauthenticated — no token provided."),
            403: openapi.Response(description="No Facilitator profile, or not assigned to this project."),
            404: openapi.Response(description="Task not found, or no submission exists for this facilitator + administrative level."),
        },
        tags=['Tasks']
    )
    def patch(self, request, pk, administrative_level_id):
        # 1. Check if the authenticated user has a Facilitator profile
        if not hasattr(request.user, 'facilitator'):
            return Response(
                {"detail": "Authenticated user does not have an associated Facilitator profile."},
                status=status.HTTP_403_FORBIDDEN
            )

        facilitator = request.user.facilitator

        # 2. Validate task existence and project-level permissions
        task = get_object_or_404(Task, pk=pk)
        self.check_object_permissions(request, task)

        # 3. Retrieve the submission scoped to this facilitator + administrative level
        submission = TaskSubmission.objects.filter(
            task=task,
            facilitator=facilitator,
            administrative_level_id=administrative_level_id
        ).first()

        if not submission:
            return Response(
                {"detail": "No submission found for this task, facilitator, and administrative level."},
                status=status.HTTP_404_NOT_FOUND
            )

        # 4. Validate input
        input_serializer = TaskCompletionToggleSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        completed_status = input_serializer.validated_data['completed']

        # 5. Atomic update + audit trail
        with transaction.atomic():
            intervention = submission.toggle_completed(completed_status)

            TaskSubmissionHistory.objects.create(
                submission=submission,
                facilitator=facilitator,
                intervention_type=intervention,
                form_response_snapshot=submission.form_response or {},
                form_fields_snapshot=task.form or {},
                fields_updated=['completed', 'completed_date']
            )

        output_serializer = SubmissionSerializer(submission, context={'request': request})
        return Response(output_serializer.data, status=status.HTTP_200_OK)
