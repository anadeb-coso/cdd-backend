from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from authentication.models import Facilitator
from process_manager.models import Task, Project, Phase, Activity, Cycle, TaskSubmission


class CycleSerializer(serializers.ModelSerializer):
    class Meta:
        """docstring for Meta"""
        model = Cycle
        fields = '__all__'


class SaveFormDatasSerializer(serializers.Serializer):
    tasks = serializers.JSONField()
    facilitator = serializers.JSONField()

    default_error_messages = {
        'invalid': _('Invalid data. Expected a dictionary, but got {datatype}.'),
        'credentials': _('Unable to log in with provided credentials.'),
    }

    def validate(self, attrs):
        facilitator = attrs.get('facilitator')

        if facilitator and facilitator.get("sql_id"):
            facilitator = Facilitator.objects.filter(id=facilitator["sql_id"]).first()
            if not facilitator:
                msg = self.default_error_messages['credentials']
                raise serializers.ValidationError(msg, code='authorization')
        else:
            msg = _('Must include "username" and "password".')
            raise serializers.ValidationError(msg, code='authorization')

        attrs['no_sql_db_name'] = facilitator.no_sql_db_name
        return attrs


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        """docstring for Meta"""
        model = Project
        fields = '__all__'

    def to_representation(self, instance):
        data = super().to_representation(instance)

        data['cycles'] = CycleSerializer(instance.get_cycles(), many=True).data

        return data


class TaskAssignmentSerializer(serializers.ModelSerializer):
    """
    Serializer for Task model to return assigned task details.
    Includes related phase and activity names for better frontend display.
    """
    phase_name = serializers.CharField(source='phase.name', read_only=True)
    activity_name = serializers.CharField(source='activity.name', read_only=True)

    class Meta:
        model = Task
        fields = ['id', 'name', 'description', 'order', 'task_order', 'phase_name', 'activity_name']


class CycleAssignmentSerializer(serializers.ModelSerializer):
    """
    Serializer for Cycle model to return project cycle details.
    """

    class Meta:
        model = Cycle
        fields = ['id', 'name', 'description', 'order']


class ProjectAssignmentSerializer(serializers.ModelSerializer):
    """
    Serializer for Project model.
    Nests the related cycles and tasks that belong to this project.
    """
    # Uses the reverse relationships (cycle_set and task_set) to fetch nested data
    cycles = CycleAssignmentSerializer(source='cycle_set', many=True, read_only=True)
    tasks = TaskAssignmentSerializer(source='task_set', many=True, read_only=True)

    class Meta:
        model = Project
        fields = ['id', 'name', 'description', 'cycles', 'tasks']


class ProjectTreeSerializer(serializers.ModelSerializer):
    """
    Recursive serializer to represent the project hierarchy.
    """
    children = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            'id',
            'couch_id',
            'name',
            'description',
            'parent',
            'created_date',
            'updated_date',
            'children'
        ]

    def get_children(self, obj):
        # We access the related_name='children' defined in the ForeignKey of the Project model
        children = obj.children.all()
        return ProjectTreeSerializer(children, many=True).data


class ProjectLiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ['id', 'name']


class PhaseLiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Phase
        fields = ['id', 'name']


class ActivityLiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = ['id', 'name']


class CycleLiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cycle
        fields = ['id', 'name']


class TaskDetailSerializer(serializers.ModelSerializer):
    project = ProjectLiteSerializer(read_only=True)
    phase = PhaseLiteSerializer(read_only=True)
    activity = ActivityLiteSerializer(read_only=True)
    cycles = CycleLiteSerializer(many=True, read_only=True)

    class Meta:
        model = Task
        fields = [
            'id', 'couch_id', 'name', 'description', 'order',
            'form', 'attachments', 'capacity_attachments',
            'project', 'phase', 'activity', 'cycles'
        ]


class SubmissionSerializer(serializers.ModelSerializer):
    users_involved = serializers.SerializerMethodField()

    class Meta:
        model = TaskSubmission
        fields = ['id', 'completed', 'form_response', 'validated', 'users_involved']

    def get_users_involved(self, obj):
        """
        Retrieves unique facilitators from the related TaskSubmissionHistory records.
        """
        # Get all facilitators associated with history entries for this submission
        histories = obj.history.select_related('facilitator__user').all()

        # Extract unique facilitators using a dictionary to avoid duplicates
        involved = {}
        for h in histories:
            fac = h.facilitator
            if fac and fac.id not in involved:
                involved[fac.id] = {
                    "facilitator_id": fac.id,
                    "name": fac.get_name()
                }

        return list(involved.values())


class TaskWithSubmissionSerializer(serializers.Serializer):
    # 'source=*' tells DRF to pass the entire Task object to this internal serializer.
    task = TaskDetailSerializer(source='*')
    submission = serializers.SerializerMethodField()

    def get_submission(self, obj):
        request = self.context.get('request')
        if not request or not hasattr(request.user, 'facilitator'):
            return None

        facilitator = request.user.facilitator
        preloaded = self.context.get('preloaded_submissions')

        submission = None

        # 1. Try searching the pre-loaded list (Optimization)
        if preloaded is not None:
            submission = next((s for s in preloaded if s.task_id == obj.id), None)

        # 2. Fallback: If it's not on the list, search in the DB (Security for Testing)
        if not submission:
            submission = TaskSubmission.objects.filter(
                task=obj,
                history__facilitator=facilitator
            ).distinct().first()

        if submission:
            # Important: Pass the context to the next serializer
            return SubmissionSerializer(submission, context=self.context).data
        return None
