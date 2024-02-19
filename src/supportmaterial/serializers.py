from rest_framework import serializers
from supportmaterial.models import *


class SupportingMaterialSerializer(serializers.ModelSerializer):
	class Meta:
		"""docstring for Meta"""
		model = SupportingMaterial
		exclude = ['subject', 'lesson']


  
class SubjectSerializer(serializers.ModelSerializer):
	# lessons = serializers.SerializerMethodField()
 
	class Meta:
		"""docstring for Meta"""
		model = Subject
		fields = '__all__'

	# def get_lessons(self, obj):
	# 	return LessonSerializer(obj.subject, many=True).data

	def to_representation(self, instance):
		data = super().to_representation(instance)
  
		data['lessons'] = LessonSerializer(instance.lessons(), many=True).data
		data['subjects'] = SubjectSerializer(instance.subjects(), many=True).data

		return data
  
    

class LessonSerializer(serializers.ModelSerializer):
	# subject = SubjectSerializer()

	class Meta:
		"""docstring for Meta"""
		model = Lesson
		exclude = ['subject']

	# def get_subject(self, obj):
	# 	return SubjectSerializer(obj.subject).data

	def to_representation(self, instance):
		data = super().to_representation(instance)
  
		data['supportingmaterials'] = SupportingMaterialSerializer(instance.supportingmaterials(), many=True).data

		return data