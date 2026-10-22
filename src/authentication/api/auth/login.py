from rest_framework import serializers
from django.contrib.auth.models import User
from django.db.models import Q
from django.contrib.auth.hashers import check_password
from django.utils.translation import gettext_lazy as _

from authentication.models import Facilitator
from authentication.platform_tokens import account_from_token, is_platform_token

#Login User Serialization
class CheckUserSerializer(serializers.Serializer):
	"""Compte à l'origine d'un appel du mobile : identifiant + jeton de session (authentication/platform_tokens.py),
	ou identifiant + mot de passe (versions de l'application d'avant les jetons)."""
	username = serializers.CharField(required=False, allow_blank=True)
	password = serializers.CharField(required=False, allow_blank=True)
	token = serializers.CharField(required=False, allow_blank=True)

	def validate(self, data):
		username = data.get('username')
		password = data.get('password')
		token = data.get('token')

		if is_platform_token(token):
			account = account_from_token(token)
			if account is None:
				# `token_invalid` : le mobile ferme la session et redemande la connexion
				raise serializers.ValidationError({
					'non_field_errors': [_("Your session has expired. Please log in again.")],
					'token_invalid': True,
				})
			return account

		if not username or not password:
			raise serializers.ValidationError(_("Incorrect identifiers"))

		# Fusion PostgreSQL : PostgreSQL est sensible à la casse là où MySQL ne
		# l'était pas → __iexact préserve le comportement de connexion historique.
		user = User.objects.filter(Q(email__iexact=username) | Q(username__iexact=username)).first()
		facilitator = Facilitator.objects.filter(Q(email__iexact=username) | Q(username__iexact=username)).first()

		if facilitator and facilitator.is_active:
			user = facilitator
		else:
			user = user if user and user.is_active else None

		if user and check_password(password, user.password):
			if not user.is_active:
				return serializers.ValidationError(_("Your account is inactive"))
			return user

		raise serializers.ValidationError(_("Incorrect identifiers"))
