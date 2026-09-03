# authentication.py

from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password

from authentication.models import Facilitator

User = get_user_model()


class MultiModelBackend(BaseBackend):

    def authenticate(self, request, username=None, password=None):

        # Fusion PostgreSQL : __iexact préserve la connexion insensible à la
        # casse (MySQL utf8mb4_general_ci historique).
        try:
            user = User.objects.get(username__iexact=username)
            if check_password(password, user.password):
                return user
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            pass

        try:
            facilitator = Facilitator.objects.get(username__iexact=username)
            if check_password(password, facilitator.password):
                return facilitator
        except (Facilitator.DoesNotExist, Facilitator.MultipleObjectsReturned):
            pass

        return None