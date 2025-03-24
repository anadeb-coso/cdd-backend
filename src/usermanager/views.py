from django.http import HttpResponseRedirect
from django.conf import settings
from django.utils.translation import get_language
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.utils.translation import gettext_lazy as _
from django.views import generic
from django.http import Http404
from django.apps import apps
from django.contrib.auth.models import User
from django.db import connections
import logging
from django.utils import translation

from cdd.call_objects_from_other_db import mis_objects_call, grm_objects_call, cdd_objects_call
from cdd.functions import get_validation_code
from usermanager.functions import encoder_email

from django.views.decorators.csrf import csrf_exempt
from authentication.models import Facilitator

# @csrf_exempt
def user_manager(request):
    data = {}
    if request.method == 'POST':

        language = request.POST.get('language', None)
        translation.activate(language)
        # request.set_cookie(settings.LANGUAGE_COOKIE_NAME, language)

        email = request.POST.get('email', None)
        
        if email:
            data['email'] = email

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
            
            data['user'] = {'exists': {}, 'objects': {}, 'object': None}
            data['user']['exists']['cdd'] = cdd_user is not None
            data['user']['exists']['cdd_facilitator'] = cdd_facilitator is not None
            data['user']['exists']['mis'] = mis_user is not None
            data['user']['exists']['grm'] = grm_user not in ({}, None)

            data['user']['objects']['cdd'] = cdd_user
            data['user']['objects']['cdd_facilitator'] = cdd_facilitator
            data['user']['objects']['mis'] = mis_user
            data['user']['objects']['grm'] = grm_user


            data['user']['object'] = cdd_user if cdd_user else (mis_user if mis_user else (grm_user if grm_user else cdd_facilitator))
            data['encoder_email'] = encoder_email(email)

            request.session['redirection_url_origin_after_user_manage'] = request.POST.get('redirection_url', None)
            data['redirection_url_origin_after_user_manage'] = request.POST.get('redirection_url', None)
            
            data['previous_url'] = request.POST.get('previous_url', f"{request.scheme}://{request.get_host()}")

            return render(request, 'profile.html', {'data': data})
        
    elif request.method == "GET" and request.session.get('redirection_url_origin_after_user_manage'):
        redirection_url = request.session.get('redirection_url_origin_after_user_manage')
        
        return redirect(redirection_url)
    
    raise Http404