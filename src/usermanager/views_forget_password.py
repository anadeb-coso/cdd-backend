from django.http import HttpResponseRedirect
from django.conf import settings
from django.utils.translation import get_language
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import timedelta
from django.db import connections
from django.contrib.auth.hashers import check_password, make_password
import logging
from django.http import Http404

from rest_framework.response import Response
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from django.contrib.auth.models import User
from django.db import connections
import logging

from usermanager.functions import user_manager_email_notification, generate_random_code_combine, validate_password
from usermanager.models import ValidationCode
from cdd.call_objects_from_other_db import mis_objects_call, grm_objects_call, cdd_objects_call
from usermanager.functions import encoder_email
import grm_client
from authentication.models import Facilitator


def reset_password_ask_email(request):
    
    if request.method == 'GET':
        request.session['redirection_url_origin_after_user_manage'] = request.GET.get('redirection_url', f"{request.scheme}://{request.get_host()}")
        return render(request, 'reset_password_ask_email.html', {'redirection_url': request.session['redirection_url_origin_after_user_manage']})
    elif request.method == 'POST' and request.POST.get('email', None):
        email = request.POST.get('email', None)

        cdd_user = cdd_objects_call.filter_objects(User, email=email, is_active=True).first()
        mis_user = mis_objects_call.filter_objects(User, email=email, is_active=True).first()
        cdd_facilitator = cdd_objects_call.filter_objects(Facilitator, email=email, active=True).first()

        grm_user = {}
        with connections['grm'].cursor() as cursor:
            try:
                cursor.execute(f"""SELECT id, username, first_name, last_name, email, password, phone_number 
                            FROM authentication_user 
                            WHERE email='{email}' AND is_active=1
                """)
                
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
    
        if not cdd_user and not mis_user and not grm_user and not cdd_facilitator:
            msg = _("This e-mail address does not exist in our database. If you have any questions, please contact the administration.")
            messages.info(request, msg)
            return render(request, 'reset_password_ask_email.html', {
                'redirection_url': request.session.get('redirection_url_origin_after_user_manage', request.GET.get('redirection_url', request.POST.get('redirection_url', f"{request.scheme}://{request.get_host()}"))),
                'msg': msg
                })

        msg = _("We are encountering a few errors when sending you e-mails.")

        code = generate_random_code_combine(email)

        now=timezone.now()
        minutes_to_add = 15
        new_time = now + timedelta(minutes=minutes_to_add)

        ValidationCode.objects.filter(email=email).update(already_use=True)
        
        validation_code = ValidationCode(
            code=code,
            email=email,
            asking_datetime=now,
            validation_code_ending_datetime=new_time,
            motif="Code de confirmation pour accéder au changement de mot de passe"
        )

        validation_code.save()

        msg = user_manager_email_notification(
            {'email': email},
            mail_type= "code_forget_password",
            motif=code,
            deadline=f"{minutes_to_add} minitues"
        )

        messages.info(request, msg)

        return render(
            request, 
            'reset_password.html', 
            {
                'data': {
                    'email': email, 'encoder_email': encoder_email(email),
                    'redirection_url': request.POST.get('redirection_url', request.GET.get('redirection_url', f"{request.scheme}://{request.get_host()}"))
                }
            }
        )

    raise Http404



class RestResetPassword(APIView):
    def post(self, request, *args, **kwargs):

        # data = {}
        if request.method == 'POST':
            ok = False
            confirm_code = request.POST.get('confirm_code', None)
            email = request.POST.get('email', None)
            password_new = request.POST.get('password_new', None)
            password_new_confirm = request.POST.get('password_new_confirm', None)

            msg = _("An error has occurred...")

            is_validate_password = validate_password(password_new)
            validation_code = ValidationCode.objects.filter(code=confirm_code)

            if not email:
                msg = _("The e-mail address is required")
            elif not password_new:
                msg = _("The password address is required")
            elif password_new != password_new_confirm:
                msg = _("The password must be the same as the previous one.")
            elif not validation_code:
                msg = _("Code invalide")
            elif not validation_code.filter(validation_code_ending_datetime__gt=timezone.now()).exists():
                msg = _("Code expired")
            elif not validation_code.filter(validation_code_ending_datetime__gt=timezone.now(), already_use=False).exists():
                msg = _("Code already used")
            elif not is_validate_password:
                msg = is_validate_password
            else:
                cdd_user = cdd_objects_call.filter_objects(User, email=email, is_active=True).first()
                mis_user = mis_objects_call.filter_objects(User, email=email, is_active=True).first()
                cdd_facilitator = cdd_objects_call.filter_objects(Facilitator, email=email, active=True).first()
                
                password_new_hashed = make_password(password_new)

                if cdd_user:
                    cdd_user.password = password_new_hashed
                    cdd_user.save()
                if mis_user:
                    mis_user.password = password_new_hashed
                    mis_user.save(using='mis')
                if cdd_facilitator:
                    cdd_facilitator.password = password_new_hashed
                    cdd_facilitator.simple_save()

                try:
                    # Synchronise le mot de passe côté GRM (compte auth.User + Adl.representative)
                    # via l'API inter-services (remplace l'ancienne double écriture directe dans
                    # MySQL legacy `grm` et CouchDB `eadls`). Best-effort : ne doit jamais faire
                    # échouer la réinitialisation locale CDD si GRM est injoignable.
                    grm_client.set_grm_user_password(email, password_new)
                except:
                    pass

                msg = _('The password has been successfully reset.')
                ok = True
                validation_code.update(already_use=True)

            # messages.add_message(request, messages.INFO, msg, extra_tags='info')

            context = {
                # 'done_page': render(
                #     request, 
                #     'reset_password_done.html', 
                #     {
                #         'redirection_url': request.session.get('redirection_url_origin_after_user_manage')
                #     }
                # ).content.decode("utf-8"),
                'msg_text': msg,
                'ok': ok
            }
            return Response(
                context, status.HTTP_200_OK
            )
        raise Http404
    

def reset_password_done(request):
    
    if request.method == 'GET':
        return render(
            request, 
            'reset_password_done.html', 
            {
                'redirection_url': request.session.get('redirection_url_origin_after_user_manage', request.GET.get('redirection_url', f"{request.scheme}://{request.get_host()}"))
            }
        )
    
    raise Http404