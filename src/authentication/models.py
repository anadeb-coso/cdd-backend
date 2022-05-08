import secrets
import time

from django.contrib.auth.hashers import make_password
from django.db import models
from django.utils.translation import gettext_lazy as _

from no_sql_client import NoSQLClient


class Facilitator(models.Model):
    no_sql_user = models.CharField(max_length=150, unique=True)
    no_sql_pass = models.CharField(max_length=128)
    no_sql_db_name = models.CharField(max_length=150, unique=True)
    username = models.CharField(max_length=150, unique=True, verbose_name=_('username'))
    password = models.CharField(max_length=128, verbose_name=_('password'))
    code = models.CharField(max_length=6, unique=True, verbose_name=_('code'))
    active = models.BooleanField(default=False, verbose_name=_('active'))

    __current_password = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__current_password = self.password

    def __str__(self):
        return self.username

    def save(self, *args, **kwargs):
        if not self.id:
            now = time.time()
            self.no_sql_user = str(int(now))
            no_sql_password_length = 13
            self.no_sql_password = secrets.token_urlsafe(no_sql_password_length)
            self.no_sql_db_name = f'facilitator_{self.no_sql_user}'
            if not self.code:
                self.code = self.get_code(self.no_sql_user)
            password = f'ChangeItNow{self.code}'
            self.password = make_password(password, salt=None, hasher='default')
            nsc = NoSQLClient()
            nsc.create_user(self.no_sql_user, self.no_sql_pass)
            facilitator_db = nsc.create_db(self.no_sql_db_name)
            nsc.replicate_design_db(facilitator_db)
            nsc.add_member_to_database(facilitator_db, self.no_sql_user)

        if self.password and self.password != self.__current_password:
            self.password = make_password(self.password, salt=None, hasher='default')

        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        NoSQLClient().delete_user(self.no_sql_user)

        super().delete(*args, **kwargs)

    @staticmethod
    def get_code(seed):
        import zlib
        return str(zlib.adler32(str(seed).encode('utf-8')))[:6]

    class Meta:
        verbose_name = _('Facilitator')
        verbose_name_plural = _('Facilitators')
