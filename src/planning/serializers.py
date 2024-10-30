from rest_framework import serializers
from planning.models import *

class PhaseSerializer(serializers.ModelSerializer):
	class Meta:
		"""docstring for Meta"""
		model = Phase
		fields = '__all__'

class ProcessActivitySerializer(serializers.ModelSerializer):
	class Meta:
		"""docstring for Meta"""
		model = ProcessActivity
		fields = '__all__'

class FacilitatorSerializer(serializers.ModelSerializer):
	class Meta:
		"""docstring for Meta"""
		model = Facilitator
		fields = '__all__'

class UserSerializer(serializers.ModelSerializer):
	class Meta:
		"""docstring for Meta"""
		model = User
		fields = '__all__'
  
class ActivityValidateSerializer(serializers.ModelSerializer):
	facilitator = FacilitatorSerializer(many=False)
	user = UserSerializer(many=False)
	class Meta:
		"""docstring for Meta"""
		model = ActivityValidate
		fields = '__all__'

class SaveActivityValidateSerializer(serializers.ModelSerializer):
	class Meta:
		"""docstring for Meta"""
		model = ActivityValidate
		fields = '__all__'


class ActivityFileSerializer(serializers.ModelSerializer):
	class Meta:
		"""docstring for Meta"""
		model = ActivityFile
		fields = '__all__'

class ActivityCommentSerializer(serializers.ModelSerializer):
	facilitator = FacilitatorSerializer(many=False)
	user = UserSerializer(many=False)
	class Meta:
		"""docstring for Meta"""
		model = ActivityComment
		fields = '__all__'

class SaveActivityCommentSerializer(serializers.ModelSerializer):
	class Meta:
		"""docstring for Meta"""
		model = ActivityComment
		fields = '__all__'

class ActivitySerializer(serializers.ModelSerializer):
	phase = PhaseSerializer(many=False)
	activity = ProcessActivitySerializer(many=False)
	facilitator = FacilitatorSerializer(many=False)
	user = UserSerializer(many=False)
	class Meta:
		"""docstring for Meta"""
		model = Activity
		fields = '__all__'
	def to_representation(self, instance):
		data = super().to_representation(instance)

		data['files'] = ActivityFileSerializer(instance.get_files(), many=True).data
		activities_validates = ActivityValidateSerializer(instance.get_activities_validate(), many=True).data
		comments = ActivityCommentSerializer(instance.get_comments(), many=True).data

		data['comments'] = sorted(
			(list(comments) + list(activities_validates)), key=lambda obj: obj.get('created_date'), reverse=True
		)

		return data

class SaveActivitySerializer(serializers.ModelSerializer):
	class Meta:
		"""docstring for Meta"""
		model = Activity
		fields = '__all__'
