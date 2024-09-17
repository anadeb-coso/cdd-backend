from django.http import Http404, JsonResponse
from django.contrib.auth import logout as auth_logout
from django.shortcuts import redirect
from django.http import HttpResponseRedirect


class PageMixin(object):
    title = None
    active_level1 = None
    active_level2 = None
    breadcrumb = None

    def get_context_data(self, **kwargs):
        ctx = super(PageMixin, self).get_context_data(**kwargs)
        
        
        ctx.setdefault('title', self.title)
        ctx.setdefault('active_level1', self.active_level1)
        ctx.setdefault('active_level2', self.active_level2)
        ctx.setdefault('breadcrumb', self.breadcrumb)
        return ctx
    
    def dispatch(self, request, *args, **kwargs):
        
        if "/process-manager/" not in self.request.get_full_path() and self.request.user.is_authenticated and not self.request.session.get('project_id'): # If the user is authenticated and no project selected
            # auth_logout(self.request) #log out user
            return redirect('dashboard:process_manager:list')
        return super().dispatch(request, *args, **kwargs)


class ModalFormMixin(object):
    template_name = 'common/modal_form.html'
    id_form = 'form'
    title = None
    subtitle = None
    picture = None
    picture_class = None
    submit_button = None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault('id_form', self.id_form)
        ctx.setdefault('title', self.title)
        ctx.setdefault('subtitle', self.subtitle)
        ctx.setdefault('picture', self.picture)
        ctx.setdefault('picture_class', self.picture_class)
        ctx.setdefault('submit_button', self.submit_button)
        return ctx


class AJAXRequestMixin:
    def dispatch(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') != 'XMLHttpRequest':
            raise Http404
        return super().dispatch(request, *args, **kwargs)


class JSONResponseMixin:
    def render_to_json_response(self, context, **response_kwargs):
        return JsonResponse(self.get_data(context), **response_kwargs)

    def get_data(self, context):
        return context
