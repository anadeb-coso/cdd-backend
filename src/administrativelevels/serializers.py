from rest_framework import serializers

from administrativelevels.models import AdministrativeLevel


class AdministrativeLevelSerializer(serializers.ModelSerializer):
	
	class Meta:
		"""docstring for Meta"""
		model = AdministrativeLevel
		fields = '__all__'





