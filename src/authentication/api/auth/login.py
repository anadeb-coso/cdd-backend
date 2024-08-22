from rest_framework import serializers
from django.contrib.auth.models import User
from django.db.models import Q
from django.contrib.auth.hashers import check_password
from django.utils.translation import gettext_lazy as _

from authentication.models import Facilitator

#Login User Serialization
class CheckUserSerializer(serializers.Serializer):
	username = serializers.CharField()
	password = serializers.CharField()
	def validate(self, data):
		username = data.get('username')
		password = data.get('password')
	
		user = User.objects.filter(Q(email=username) | Q(username=username)).first()
		user = Facilitator.objects.filter(Q(email=username) | Q(username=username)).first() if not user else user

		if user and check_password(password, user.password):
			if not user.is_active:
				return serializers.ValidationError(_("Your account is inactive"))
			return user
    			
		raise serializers.ValidationError(_("Incorrect identifiers"))