from rest_framework import serializers
from storeapp.models import *


class StoreAppSerializer(serializers.ModelSerializer):
	class Meta:
		"""docstring for Meta"""
		model = StoreApp
		fields = '__all__'
  

class StoreProjectSerializer(serializers.ModelSerializer):
	class Meta:
		"""docstring for Meta"""
		model = StoreProject
		fields = '__all__'
  
	def to_representation(self, instance):
		data = super().to_representation(instance)
  
		storeapps = instance.storeapp_set.get_queryset()
		if storeapps:
			data['apps'] = StoreAppSerializer(storeapps, many=True).data
			data['app'] = StoreAppSerializer(storeapps.order_by('-created_date').first()).data


		return data
  