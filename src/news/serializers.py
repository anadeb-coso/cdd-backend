from rest_framework import serializers
from news.models import *

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

class CategorySerializer(serializers.ModelSerializer):
	class Meta:
		"""docstring for Meta"""
		model = Category
		fields = '__all__'
  
class TagSerializer(serializers.ModelSerializer):
	class Meta:
		"""docstring for Meta"""
		model = Tag
		fields = '__all__'

class NewsFileSerializer(serializers.ModelSerializer):
	class Meta:
		"""docstring for Meta"""
		model = NewsFile
		fields = '__all__'

class NewsSerializer(serializers.ModelSerializer):
	category = CategorySerializer(many=False)
	tags = TagSerializer(many=True)
	facilitator = FacilitatorSerializer(many=False)
	user = UserSerializer(many=False)
	class Meta:
		"""docstring for Meta"""
		model = News
		fields = '__all__'
	def to_representation(self, instance):
		data = super().to_representation(instance)

		data['files'] = NewsFileSerializer(instance.get_files(), many=True).data

		return data

class SaveNewsSerializer(serializers.ModelSerializer):
	class Meta:
		"""docstring for Meta"""
		model = News
		fields = '__all__'