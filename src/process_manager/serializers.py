from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from authentication.models import Facilitator
from process_manager.models import Project, Cycle, Task


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