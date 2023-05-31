from django.shortcuts import render, redirect
from rest_framework import status
from django.utils.translation import gettext_lazy
from django.views import generic
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from dashboard.mixins import PageMixin
from authentication.permissions import AdminPermissionRequiredMixin
from dashboard.authentication.forms import CreateUserForm, UpdateUserForm
from django.contrib.auth.models import User, Group, Permission
from django.forms.models import model_to_dict
from django.contrib import messages
from django.http import Http404


def handler400(request, exception):
    return render(
        request,
        template_name='common/400.html',
        status=status.HTTP_400_BAD_REQUEST,
        content_type='text/html'
    )


def handler403(request, exception):
    return render(
        request,
        template_name='common/403.html',
        status=status.HTTP_403_FORBIDDEN,
        content_type='text/html'
    )


def handler404(request, exception):
    return render(
        request,
        template_name='common/404.html',
        status=status.HTTP_404_NOT_FOUND,
        content_type='text/html'
    )


def handler500(request):
    return render(
        request,
        template_name='common/500.html',
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content_type='text/html'
    )




class UsersListView(PageMixin, LoginRequiredMixin, generic.ListView):
    """Display user list"""

    model = User
    template_name = 'authentication/users.html'
    context_object_name = 'users'
    title = gettext_lazy('Users')
    active_level1 = 'users'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    


class CreateUpdateUserFormView(PageMixin, LoginRequiredMixin, AdminPermissionRequiredMixin, generic.FormView):
    template_name = 'authentication/create.html'
    title = gettext_lazy('Create User')
    active_level1 = 'users'
    form_class = CreateUserForm
    success_url = reverse_lazy('dashboard:authentication:users')
    breadcrumb = [
        {
            'url': reverse_lazy('dashboard:authentication:users'),
            'title': gettext_lazy('Users')
        },
        {
            'url': '',
            'title': title
        }
    ]
    id = 0
    def dispatch(self, request, *args, **kwargs):
        try:
            self.id = kwargs['id']
        except Exception:
            pass
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        ctx = super(CreateUpdateUserFormView, self).get_context_data(**kwargs)
        if self.id:
            form = UpdateUserForm(instance=User.objects.get(id=self.id))
            ctx['form'] = form

            ctx['title'] = gettext_lazy('Update User')
            ctx['breadcrumb'] = [
                {
                    'url': reverse_lazy('dashboard:authentication:users'),
                    'title': gettext_lazy('Users')
                },
                {
                    'url': '',
                    'title': ctx['title']
                }
            ]

        return ctx

    def post(self, request, *args, **kwargs):
        if self.id:
            form = UpdateUserForm(request.POST, instance=User.objects.get(id=self.id))
        else:
            form = CreateUserForm(request.POST)
        if form.is_valid():
            
            groups = form.cleaned_data['groups']
            user_permissions = form.cleaned_data['user_permissions']
            try:
                for g in groups:
                    Group.objects.using('mis').get(name=g.name)
                for u_p in user_permissions:
                    Permission.objects.using('mis').get(name=u_p.name)
            except Exception as exc:
                messages.info(request, gettext_lazy(exc.__str__()))
                return super(CreateUpdateUserFormView, self).get(request, *args, **kwargs)

            instance = form.save()

            # Save on MIS DB
            a_dict = model_to_dict(instance)
            
            del a_dict['id']
            del a_dict['groups']
            del a_dict['user_permissions']
            user = None
            if self.id:
                try:
                    _user = User.objects.get(id=self.id)
                    # user_id = User.objects.using('mis').get(username=_user.username).id
                    # a_dict['id'] = user_id
                    # User.objects.using('mis').update(**a_dict)
                    user = User.objects.using('mis').get(username=_user.username)
                    for k, v in a_dict.items():
                        setattr(user, k, v)
                except Exception as exc:
                    messages.info(request, gettext_lazy(exc.__str__()))
                    return redirect('dashboard:authentication:users')
            else:
                User.objects.using('mis').create(**a_dict)
                user = User.objects.using('mis').get(username=instance.username)
            print(groups, user_permissions)
            instance.groups.set([])
            user.groups.set([])
            instance.user_permissions.set([])
            user.user_permissions.set([])
            for g in groups:
                instance.groups.add(g)
                user.groups.add(Group.objects.using('mis').get(name=g.name))
            for u_p in user_permissions:
                instance.user_permissions.add(u_p)
                user.user_permissions.add(Permission.objects.using('mis').get(name=u_p.name))
                
            instance.save()
            user.save(using='mis')
            #End

            return redirect('dashboard:authentication:users')
        return super(CreateUpdateUserFormView, self).get(request, *args, **kwargs)


class DeleteUserFormView(PageMixin, LoginRequiredMixin, AdminPermissionRequiredMixin, generic.TemplateView):
    template_name = 'authentication/delete.html'
    title = gettext_lazy('Delete User')
    active_level1 = 'users'
    success_url = reverse_lazy('dashboard:authentication:users')
    breadcrumb = [
        {
            'url': reverse_lazy('dashboard:authentication:users'),
            'title': gettext_lazy('Users')
        },
        {
            'url': '',
            'title': title
        }
    ]

    id = 0
    def dispatch(self, request, *args, **kwargs):
        try:
            self.id = kwargs['id']
        except Exception:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super(DeleteUserFormView, self).get_context_data(**kwargs)
        try:
            if self.id:
                ctx['object'] = User.objects.get(id=self.id)
            return ctx
        except Exception as exc:
            messages.info(self.request, gettext_lazy(exc.__str__()))
            return redirect('dashboard:authentication:users')

    def post(self, request, *args, **kwargs):
        try:
            user = User.objects.get(id=self.id)
            user.delete()
            return redirect('dashboard:authentication:users')
        except Exception as exc:
            messages.info(request, gettext_lazy(exc.__str__()))
        
        return super(DeleteUserFormView, self).get(request, *args, **kwargs)