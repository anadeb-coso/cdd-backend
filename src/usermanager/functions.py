from datetime import datetime
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.urls import reverse
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User
from django.db import connections
import logging

from cdd.my_librairies.mail.send_mail import send_email
from dashboard.templatetags.custom_tags import get_group_high
import locale
import random
import zlib
from rest_framework import status

from authentication.models import Facilitator
from cdd.call_objects_from_other_db import mis_objects_call, grm_objects_call, cdd_objects_call


def generate_random_code(longueur=6):
    return ''.join(random.choices('0123456789', k=longueur))

def generate_random_code_by_element(seed, longueur=6):
    return str(zlib.adler32(str(seed).encode('utf-8')))[:longueur]

def generate_random_code_combine(seed, longueur=6):
    return str(
        int(generate_random_code(longueur)) + int(generate_random_code_by_element(seed, longueur))
    )[:longueur]

def encoder_email(email):
    partie_nom, domaine = email.split("@")
    
    partie_masquee = partie_nom[:2] + "*" * (len(partie_nom) - 2)
    
    email_encode = partie_masquee + "@" + domaine
    return email_encode

import re

def validate_password(password):
    # Vérifier si le mot de passe contient uniquement des lettres et des chiffres
    if not re.fullmatch("[A-Za-z0-9]+", password):
        return _("The password must contain only letters and numbers.")
    
    # Vérifier la longueur (au moins 8 caractères)
    if len(password) < 8:
        return _("The password must contain at least 8 characters.")
    
    # Vérifier si le mot de passe contient au moins une lettre
    if not re.search("[A-Za-z]", password):
        return _("The password must contain at least one letter.")
    
    # Vérifier si le mot de passe contient au moins un chiffre
    if not re.search("[0-9]", password):
        return _("The password must contain at least one digit.")
    
    return True


def user_manager_email_notification(user, mail_type, motif, deadline):
    locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
    data = {
        'user_name': user['first_name'] if user.get('first_name') else (user['name'].split(' ')[0] if user.get('name') else (user['email'].split('@')[0] if user.get('email') else user['username'].split('@')[0])),
        'current_year': datetime.now().year,
    }
    if mail_type == "code_change_password":
        template_name = 'mail/notification'
        title = _('Password change confirmation code')
        subject = _(f"[COSO Apps : {datetime.now().strftime('%Y-%m-%d')}]") + " " + title

        data['description'] = _('This code is only valid for %(deadline)s')
        data['description'] = data['description'] % {'deadline': deadline}

        data['motif'] = _('Code : %(code)s')
        data['motif'] = data['motif'] % {'code': motif}
    elif mail_type == "code_forget_password":
        template_name = 'mail/notification'
        title = _('Password reset confirmation code')
        subject = _(f"[COSO Apps : {datetime.now().strftime('%Y-%m-%d')}]") + " " + title

        data['description'] = _('This code is only valid for %(deadline)s')
        data['description'] = data['description'] % {'deadline': deadline}

        data['motif'] = _('Code : %(code)s')
        data['motif'] = data['motif'] % {'code': motif}
    else:
        return
    
    data['subject'] = subject
    data['title'] = title
    
    try:
        msg = send_email(
            subject,
            template_name,
            data,
            [user['email']], 
            [user['email']]
        )
        if msg == 'error':
            return _("An error occurred while sending the email")
        else:
            return _("Mail sent successfully")
    except Exception as exc:
        return _("An error occurred while sending the email")
        


def get_user_by_email(email):
    if email:
        cdd_user = cdd_objects_call.filter_objects(User, email=email, is_active=True).first()
        mis_user = mis_objects_call.filter_objects(User, email=email, is_active=True).first()
        cdd_facilitator = cdd_objects_call.filter_objects(Facilitator, email=email, active=True).first()

        grm_user = {}
        with connections['grm'].cursor() as cursor:
            try:
                cursor.execute(
                    """
                    SELECT id, username, first_name, last_name, email, password, phone_number
                    FROM authentication_user
                    WHERE email = %s AND is_active = TRUE
                    """,
                    [email],
                )
                
                count = 0
                for row in cursor.fetchall():
                    grm_user['id'] = row[0]
                    grm_user['username'] = row[1]
                    grm_user['first_name'] = row[2]
                    grm_user['last_name'] = row[3]
                    grm_user['email'] = row[4]
                    grm_user['password'] = row[5]
                    grm_user['phone_number'] = row[6]
                    count += 1
                    
            except Exception as exc:
                logging.exception(exc)

        return (
            cdd_user if cdd_user else (mis_user if mis_user else (grm_user if grm_user else cdd_facilitator)), 
            {'cdd_user': cdd_user, 'mis_user': mis_user, 'grm_user': grm_user, 'cdd_facilitator': cdd_facilitator}
        )
    return None, None