# authentication.py

from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password

from authentication.models import Facilitator

User = get_user_model()


class MultiModelBackend(BaseBackend):

    def authenticate(self, request, username=None, password=None):

        try:
            user = User.objects.get(username=username)
            if check_password(password, user.password):
                return user
        except User.DoesNotExist:
            pass

        try:
            facilitator = Facilitator.objects.get(username=username)
            if check_password(password, facilitator.password):
                return facilitator
        except Facilitator.DoesNotExist:
            pass

        return None