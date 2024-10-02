from django.http import HttpResponseRedirect
from django.conf import settings
from django.utils.translation import get_language

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views import generic
from django.http import Http404
from django.apps import apps

from dashboard.mixins import AJAXRequestMixin, JSONResponseMixin, ModalFormMixin
from cdd.forms import DeleteConfirmForm


def set_language(request):
    response = HttpResponseRedirect('/')
    if request.method == 'POST':
        try:
            language = request.POST.get('language')
            next = request.POST.get('next')
            next_url_generate = False
            language_code = get_language()
            
            if next and language_code and next.startswith("/"+language_code+"/") :
                next = next[(len(language_code)+2):]
                next_url_generate = True
                
            if language:
                if language != settings.LANGUAGE_CODE and [lang for lang in settings.LANGUAGES if lang[0] == language]:
                    redirect_path = f'/{language}/{next}' if next_url_generate else f'/{language}/'
                elif language == settings.LANGUAGE_CODE:
                    redirect_path = f'/{next}' if next_url_generate else '/'
                else:
                    return response
                from django.utils import translation
                translation.activate(language)
                response = HttpResponseRedirect(redirect_path)
                response.set_cookie(settings.LANGUAGE_COOKIE_NAME, language)
        except Exception as exc:
            pass
    return response



#Delete
class DeleteObjectFormView(AJAXRequestMixin, ModalFormMixin, LoginRequiredMixin, JSONResponseMixin,
                                      generic.FormView):
    form_class = DeleteConfirmForm
    id_form = "cdd_deletion_object_form"
    title = _('Confirm deletion')
    submit_button = _('Confirm')
    form_class_color = 'danger'

    def post(self, request, *args, **kwargs):
        form = None
        if self.kwargs.get('object_id') and self.kwargs.get('type'):
            ClassModals = []
            ClassModal = None
            for app_conf in apps.get_app_configs():
                try:
                    ClassModal = app_conf.get_model(self.kwargs.get('type').lower())
                    # break # stop as soon as it is found
                    ClassModals.append(ClassModal)
                except LookupError:
                    # no such model in this application
                    pass
            
            # if ClassModal:
            for cls in ClassModals:
                obj = cls.objects.get(id=self.kwargs.get('object_id'))
                if hasattr(obj, self.kwargs.get('attr')):
                    form = DeleteConfirmForm(request.POST)

                    if form and form.is_valid():
                        return self._delete_object(obj)
        
        msg = _("An error has occurred...")
        messages.add_message(self.request, messages.ERROR, msg, extra_tags='error')

        context = {'msg': render(self.request, 'common/messages.html').content.decode("utf-8")}
        return self.render_to_json_response(context, safe=False)
    
    def _delete_object(self, obj):
        _class = obj.__class__
        
        obj.delete()
        
        msg = _("The object was successfully removed.")
        messages.add_message(self.request, messages.SUCCESS, msg, extra_tags='success')

        context = {'msg': render(self.request, 'common/messages.html').content.decode("utf-8")}
        return self.render_to_json_response(context, safe=False)
#And Delete