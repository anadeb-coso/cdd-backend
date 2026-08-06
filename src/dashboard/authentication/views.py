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

from dashboard.facilitators.repository.db_facilitator_repository import FacilitatorRepository
from dashboard.facilitators.repository.facilitator_criteria import FacilitatorCriteria
from authentication.models import Facilitator
from process_manager.models import Project
import grm_client
from dashboard.facilitators.functions import update_facilitators_stats
from cdd.call_objects_from_other_db import mis_objects_call
from subprojects.models import Project as MisProject


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

    def get_context_data(self, **kwargs):
        context = super(UsersListView, self).get_context_data(**kwargs)
        context['breadcrumb'] = False

        if not (
            self.request.user.groups.filter(name__in=["Evaluator", "Admin", "CDDSpecialist", "NationalCoordinator", "KnowledgeManager"]).exists()
            or 
            bool(self.request.user.is_superuser)
        ):
            context['users'] = User.objects.filter(projects__id=self.request.session.get('project_id'))
        
        context['total_users_dashboard'] = User.objects.filter(
            is_active=True,
            projects__in=[self.request.session.get('project_id')]
        ).count()
        context['global_total_users_dashboard'] = User.objects.filter(
            is_active=True
        ).count()

        return context


class UsersDiagnosticsView(LoginRequiredMixin, generic.ListView):
    template_name = 'authentication/components/stats.html'
    context_object_name = 'object'

    def get_queryset(self):
        project_mis = mis_objects_call.filter_objects(MisProject, name=self.request.session.get('project_name'))

        # Infos Generales

        community_facilitators = FacilitatorRepository().find_by_criteria(
            criteria=FacilitatorCriteria(
                facilitator_type='community_facilitator',
                develop_mode=False,
                training_mode=False,
                active=True,
                projects__id=[self.request.session.get('project_id')]
            )
        )
        community_facilitators_count = community_facilitators.count()
        technical_facilitators = FacilitatorRepository().find_by_criteria(
            criteria=FacilitatorCriteria(
                facilitator_type='technical_facilitator',
                develop_mode=False,
                training_mode=False,
                active=True,
                projects__id=[self.request.session.get('project_id')]
            )
        )
        technical_facilitators_count = technical_facilitators.count()
        supervisors = User.objects.filter(
            groups__name__in=['Supervisor'],
            is_active=True,
            projects__in=[self.request.session.get('project_id')]
        )
        supervisors_count = supervisors.count()
        CDDSpecialists = User.objects.filter(
            groups__name__in=['CDDSpecialist'],
            is_active=True,
            projects__in=[self.request.session.get('project_id')]
        )
        CDDSpecialists_count = CDDSpecialists.count()
        others_users = User.objects.filter(
            projects__in=[self.request.session.get('project_id')],
            is_active=True,
        ).exclude(
            groups__name__in=['Supervisor', 'CDDSpecialist']
        )
        others_users_count = others_users.count()
        
        total_users = community_facilitators_count + technical_facilitators_count + supervisors_count + CDDSpecialists_count + others_users_count
        

        global_community_facilitators = FacilitatorRepository().find_by_criteria(
            criteria=FacilitatorCriteria(
                facilitator_type='community_facilitator',
                develop_mode=False,
                training_mode=False,
                active=True
            )
        )
        global_community_facilitators_count = global_community_facilitators.count()
        global_technical_facilitators = FacilitatorRepository().find_by_criteria(
            criteria=FacilitatorCriteria(
                facilitator_type='technical_facilitator',
                develop_mode=False,
                training_mode=False,
                active=True
            )
        )
        global_technical_facilitators_count = global_technical_facilitators.count()
        global_supervisors = User.objects.filter(
            groups__name__in=['Supervisor'],
            is_active=True
        )
        global_supervisors_count = global_supervisors.count()
        global_CDDSpecialists = User.objects.filter(
            groups__name__in=['CDDSpecialist'],
            is_active=True
        )
        global_CDDSpecialists_count = global_CDDSpecialists.count()
        global_others_users = User.objects.filter(
            is_active=True,
        ).exclude(
            groups__name__in=['Supervisor', 'CDDSpecialist']
        )
        global_others_users_count = global_others_users.count()
        
        global_total_users = global_community_facilitators_count + global_technical_facilitators_count + global_supervisors_count + global_CDDSpecialists_count + global_others_users_count
        

        # facilitators = update_facilitators_stats(
        #     community_facilitators, 
        #     [],
        #     self.request.session.get('project_id'), 
        #     self.request.session.get('cycle_id'),
        #     self.request.session.get('project_couch_id'),
        #     project_mis
        # )
        facilitators = community_facilitators
        # global_facilitators = update_facilitators_stats(
        #     global_community_facilitators, 
        #     [],
        #     self.request.session.get('project_id'), 
        #     self.request.session.get('cycle_id'),
        #     self.request.session.get('project_couch_id'),
        #     project_mis
        # )
        global_facilitators = global_community_facilitators

        facilitators_stabilized_all_docs = dict([
            (doc.get('representative').get('email'), doc) for doc in grm_client.get_all_facilitators() \
                if (
                    type(doc) is dict and doc.get('type') == 'adl' and \
                    doc.get('representative') and doc.get('representative').get('email')
                )
        ])

        # # - CF
        # adls_emaails_community_facilitators = [
        #     obj.email for obj in community_facilitators
        # ]
        # facilitators_stabilized_dict = dict([
        #     (k, doc) for k, doc in facilitators_stabilized_all_docs.items() if k in adls_emaails_community_facilitators
        # ])

        # global_adls_emaails_community_facilitators = [
        #     obj.email for obj in global_community_facilitators
        # ]
        # global_facilitators_stabilized_dict = dict([
        #     (k, doc) for k, doc in facilitators_stabilized_all_docs.items() if k in global_adls_emaails_community_facilitators
        # ])

        # # # - TF
        adls_emaails = [
            obj.email for obj in technical_facilitators
        ]
        technical_facilitators_stabilized = [
            doc for k, doc in facilitators_stabilized_all_docs.items() if k in adls_emaails
        ]

        global_adls_emaails = [
            obj.email for obj in global_technical_facilitators
        ]
        global_technical_facilitators_stabilized = [
            doc for k, doc in facilitators_stabilized_all_docs.items() if k in global_adls_emaails
        ]
        
        # End Infos Generales

        return {
            "facilitators_stabilized_all_docs": facilitators_stabilized_all_docs,
            "community_facilitators": community_facilitators,
            "community_facilitators_count": community_facilitators_count,
            "technical_facilitators": technical_facilitators,
            "technical_facilitators_count": technical_facilitators_count,
            "supervisors": supervisors,
            "supervisors_count": supervisors_count,
            "CDDSpecialists": CDDSpecialists,
            "CDDSpecialists_count": CDDSpecialists_count,
            "others_users": others_users,
            "others_users_count": others_users_count,
            "total_users": total_users,
            "global_community_facilitators": global_community_facilitators,
            "global_community_facilitators_count": global_community_facilitators_count,
            "global_technical_facilitators": global_technical_facilitators,
            "global_technical_facilitators_count": global_technical_facilitators_count,
            "global_supervisors": global_supervisors,
            "global_supervisors_count": global_supervisors_count,
            "global_CDDSpecialists": global_CDDSpecialists,
            "global_CDDSpecialists_count": global_CDDSpecialists_count,
            "global_others_users": global_others_users,
            "global_others_users_count": global_others_users_count,
            "global_total_users": global_total_users,
            "facilitators": facilitators,
            "technical_facilitators_stabilized": technical_facilitators_stabilized,
            "global_facilitators": global_facilitators,
            "global_technical_facilitators_stabilized": global_technical_facilitators_stabilized
        }
    


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
        facilitator = None
        facilitator_email = None

        if self.id:
            user = User.objects.get(id=self.id)
            form = UpdateUserForm(request.POST, instance=user)
            facilitator_email = user.email
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
            # print(groups, user_permissions)
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
            
            if not self.id and hasattr(user, 'projects'):
                instance.projects.add(*(Project.objects.get(id=self.request.session.get('project_id')).build_the_tree_structure()))

            instance.save()
            user.save(using='mis')
            #End

    
            try:
                facilitator = Facilitator.objects.get(email=(facilitator_email if facilitator_email else _user.email))
                facilitator.password = _user.password
                facilitator.username = _user.username
                facilitator.name = f"{_user.last_name} {_user.first_name}"
                facilitator.active = _user.is_active
                facilitator.save()
            except:
                pass

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