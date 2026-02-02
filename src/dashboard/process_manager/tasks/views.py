from django.shortcuts import render, redirect
from rest_framework import status
from django.utils.translation import gettext_lazy
from django.views import generic
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from dashboard.mixins import PageMixin
from authentication.permissions import FullStackPermissionRequiredMixin
from django.contrib import messages
from django.http import Http404

from process_manager.models import Phase, Activity, Task
from dashboard.process_manager.tasks.forms import *

# Phase

class PhaseListView(PageMixin, FullStackPermissionRequiredMixin, generic.ListView):
    """Display phase list"""

    model = Phase
    template_name = 'process_manager/tasks/list.html'
    context_object_name = 'objects'
    title = gettext_lazy('Phases')
    active_level1 = 'process_manager_tasks'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def get_queryset(self):
        return Phase.objects.filter(project_id=self.request.session.get('project_id')).order_by('order')
    
    def get_context_data(self, **kwargs):
        ctx = super(PhaseListView, self).get_context_data(**kwargs)
        ctx['class_object'] = 'Phase'
        return ctx


class CreateUpdatePhaseFormView(PageMixin, FullStackPermissionRequiredMixin, generic.FormView):
    template_name = 'process_manager/tasks/create.html'
    title = gettext_lazy('Create Phase')
    active_level1 = 'process_manager_tasks'
    form_class = PhaseForm
    success_url = reverse_lazy('dashboard:process_manager:tasks:phase_list')
    breadcrumb = [
        {
            'url': reverse_lazy('dashboard:process_manager:tasks:phase_list'),
            'title': gettext_lazy('Phases')
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
        ctx = super(CreateUpdatePhaseFormView, self).get_context_data(**kwargs)
        ctx['class_object'] = 'Phase'
        if self.id:
            ctx['form'] = PhaseForm(
                instance=Phase.objects.get(id=self.id, project_id=self.request.session.get('project_id')),
                initial={
                    'project_id': self.request.session.get('project_id')
                }
            )

            ctx['title'] = gettext_lazy('Update Phase')
            ctx['breadcrumb'] = [
                {
                    'url': reverse_lazy('dashboard:process_manager:tasks:phase_list'),
                    'title': gettext_lazy('Phases')
                },
                {
                    'url': '',
                    'title': ctx['title']
                }
            ]
        else:
            ctx['form'] = PhaseForm(
                initial={
                    'project_id': self.request.session.get('project_id')
                }
            )

        return ctx

    def post(self, request, *args, **kwargs):

        if self.id:
            phase = Phase.objects.get(id=self.id, project_id=self.request.session.get('project_id'))
            form = PhaseForm(
                request.POST,
                instance=phase,
                initial={
                    'project_id': self.request.session.get('project_id')
                }
            )
        else:
            form = PhaseForm(
                request.POST,
                initial={
                    'project_id': self.request.session.get('project_id')
                }
            )

        if form.is_valid():

            instance = form.save()

            return redirect('dashboard:process_manager:tasks:phase_list')
        
        return super(CreateUpdatePhaseFormView, self).get(request, *args, **kwargs)


class DeletePhaseFormView(PageMixin, FullStackPermissionRequiredMixin, generic.TemplateView):
    template_name = 'process_manager/tasks/delete.html'
    title = gettext_lazy('Delete Phase')
    active_level1 = 'process_manager_tasks'
    success_url = reverse_lazy('dashboard:process_manager:tasks:phase_list')
    breadcrumb = [
        {
            'url': reverse_lazy('dashboard:process_manager:tasks:phase_list'),
            'title': gettext_lazy('Phases')
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
        ctx = super(DeletePhaseFormView, self).get_context_data(**kwargs)
        ctx['class_object'] = 'Phase'
        try:
            if self.id:
                ctx['object'] = Phase.objects.get(id=self.id, project_id=self.request.session.get('project_id'))
            return ctx
        except Exception as exc:
            messages.info(self.request, gettext_lazy(exc.__str__()))
            return redirect('dashboard:process_manager:tasks:phase_list')

    def post(self, request, *args, **kwargs):
        try:
            phase = Phase.objects.get(id=self.id, project_id=self.request.session.get('project_id'))
            phase.delete()
            return redirect('dashboard:process_manager:tasks:phase_list')
        except Exception as exc:
            messages.info(request, gettext_lazy(exc.__str__()))
        
        return super(DeletePhaseFormView, self).get(request, *args, **kwargs)
    
# End Phase


# Activity

class ActivityListView(PageMixin, FullStackPermissionRequiredMixin, generic.ListView):
    """Display Activity list"""

    model = Activity
    template_name = 'process_manager/tasks/list.html'
    context_object_name = 'objects'
    title = gettext_lazy('Activities')
    active_level1 = 'process_manager_tasks'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def get_queryset(self):
        return Activity.objects.filter(project_id=self.request.session.get('project_id')).order_by('phase__order', 'order')
    
    def get_context_data(self, **kwargs):
        ctx = super(ActivityListView, self).get_context_data(**kwargs)
        ctx['class_object'] = 'Activity'
        return ctx


class CreateUpdateActivityFormView(PageMixin, FullStackPermissionRequiredMixin, generic.FormView):
    template_name = 'process_manager/tasks/create.html'
    title = gettext_lazy('Create Activity')
    active_level1 = 'process_manager_tasks'
    form_class = ActivityForm
    success_url = reverse_lazy('dashboard:process_manager:tasks:activity_list')
    breadcrumb = [
        {
            'url': reverse_lazy('dashboard:process_manager:tasks:activity_list'),
            'title': gettext_lazy('Activities')
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
        ctx = super(CreateUpdateActivityFormView, self).get_context_data(**kwargs)
        ctx['class_object'] = 'Activity'
        if self.id:
            ctx['form'] = ActivityForm(
                instance=Activity.objects.get(id=self.id, project_id=self.request.session.get('project_id')),
                initial={
                    'project_id': self.request.session.get('project_id')
                }
            )

            ctx['title'] = gettext_lazy('Update Activity')
            ctx['breadcrumb'] = [
                {
                    'url': reverse_lazy('dashboard:process_manager:tasks:activity_list'),
                    'title': gettext_lazy('Activities')
                },
                {
                    'url': '',
                    'title': ctx['title']
                }
            ]
        else:
            ctx['form'] = ActivityForm(
                initial={
                    'project_id': self.request.session.get('project_id')
                }
            )

        return ctx

    def post(self, request, *args, **kwargs):

        if self.id:
            activity = Activity.objects.get(id=self.id, project_id=self.request.session.get('project_id'))
            form = ActivityForm(
                request.POST,
                instance=activity,
                initial={
                    'project_id': self.request.session.get('project_id')
                }
            )
        else:
            form = ActivityForm(
                request.POST,
                initial={
                    'project_id': self.request.session.get('project_id')
                }
            )

        if form.is_valid():

            form.save()

            return redirect('dashboard:process_manager:tasks:activity_list')
        
        return super(CreateUpdateActivityFormView, self).get(request, *args, **kwargs)


class DeleteActivityFormView(PageMixin, FullStackPermissionRequiredMixin, generic.TemplateView):
    template_name = 'process_manager/tasks/delete.html'
    title = gettext_lazy('Delete Activity')
    active_level1 = 'process_manager_tasks'
    success_url = reverse_lazy('dashboard:process_manager:tasks:activity_list')
    breadcrumb = [
        {
            'url': reverse_lazy('dashboard:process_manager:tasks:activity_list'),
            'title': gettext_lazy('Activities')
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
        ctx = super(DeleteActivityFormView, self).get_context_data(**kwargs)
        ctx['class_object'] = 'Activity'
        try:
            if self.id:
                ctx['object'] = Activity.objects.get(id=self.id, project_id=self.request.session.get('project_id'))
            return ctx
        except Exception as exc:
            messages.info(self.request, gettext_lazy(exc.__str__()))
            return redirect('dashboard:process_manager:tasks:activity_list')

    def post(self, request, *args, **kwargs):
        try:
            activity = Activity.objects.get(id=self.id, project_id=self.request.session.get('project_id'))
            activity.delete()
            return redirect('dashboard:process_manager:tasks:activity_list')
        except Exception as exc:
            messages.info(request, gettext_lazy(exc.__str__()))
        
        return super(DeleteActivityFormView, self).get(request, *args, **kwargs)
    
# End Activity


# Task

class TaskListView(PageMixin, FullStackPermissionRequiredMixin, generic.ListView):
    """Display Task list"""

    model = Task
    template_name = 'process_manager/tasks/list.html'
    context_object_name = 'objects'
    title = gettext_lazy('Tasks')
    active_level1 = 'process_manager_tasks'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def get_queryset(self):
        return Task.objects.filter(project_id=self.request.session.get('project_id')).order_by('phase__order', 'activity__order', 'order')
    
    def get_context_data(self, **kwargs):
        ctx = super(TaskListView, self).get_context_data(**kwargs)
        ctx['class_object'] = 'Task'
        return ctx


class CreateUpdateTaskFormView(PageMixin, FullStackPermissionRequiredMixin, generic.FormView):
    template_name = 'process_manager/tasks/create.html'
    title = gettext_lazy('Create Task')
    active_level1 = 'process_manager_tasks'
    form_class = TaskForm
    success_url = reverse_lazy('dashboard:process_manager:tasks:task_list')
    breadcrumb = [
        {
            'url': reverse_lazy('dashboard:process_manager:tasks:task_list'),
            'title': gettext_lazy('Tasks')
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
        ctx = super(CreateUpdateTaskFormView, self).get_context_data(**kwargs)
        ctx['class_object'] = 'Task'
        if self.id:
            ctx['form'] = TaskForm(
                instance=Task.objects.get(id=self.id, project_id=self.request.session.get('project_id')),
                initial={
                    'project_id': self.request.session.get('project_id')
                }
            )

            ctx['title'] = gettext_lazy('Update Task')
            ctx['breadcrumb'] = [
                {
                    'url': reverse_lazy('dashboard:process_manager:tasks:task_list'),
                    'title': gettext_lazy('Tasks')
                },
                {
                    'url': '',
                    'title': ctx['title']
                }
            ]
        else:
            
            ctx['form'] = TaskForm(
                initial={
                    'project_id': self.request.session.get('project_id')
                }
            )

        return ctx

    def post(self, request, *args, **kwargs):

        if self.id:
            task = Task.objects.get(id=self.id, project_id=self.request.session.get('project_id'))
            form = TaskForm(
                request.POST, 
                instance=task,
                initial={
                    'project_id': self.request.session.get('project_id')
                }
            )
        else:
            form = TaskForm(
                request.POST,
                initial={
                    'project_id': self.request.session.get('project_id')
                }
            )

        if form.is_valid():

            form.save()

            return redirect('dashboard:process_manager:tasks:task_list')
        
        return super(CreateUpdateTaskFormView, self).get(request, *args, **kwargs)


class DeleteTaskFormView(PageMixin, FullStackPermissionRequiredMixin, generic.TemplateView):
    template_name = 'process_manager/tasks/delete.html'
    title = gettext_lazy('Delete Task')
    active_level1 = 'process_manager_tasks'
    success_url = reverse_lazy('dashboard:process_manager:tasks:task_list')
    breadcrumb = [
        {
            'url': reverse_lazy('dashboard:process_manager:tasks:task_list'),
            'title': gettext_lazy('Tasks')
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
        ctx = super(DeleteTaskFormView, self).get_context_data(**kwargs)
        ctx['class_object'] = 'Task'
        try:
            if self.id:
                ctx['object'] = Task.objects.get(id=self.id, project_id=self.request.session.get('project_id'))
            return ctx
        except Exception as exc:
            messages.info(self.request, gettext_lazy(exc.__str__()))
            return redirect('dashboard:process_manager:tasks:task_list')

    def post(self, request, *args, **kwargs):
        try:
            task = Task.objects.get(id=self.id, project_id=self.request.session.get('project_id'))
            task.delete()
            return redirect('dashboard:process_manager:tasks:task_list')
        except Exception as exc:
            messages.info(request, gettext_lazy(exc.__str__()))
        
        return super(DeleteTaskFormView, self).get(request, *args, **kwargs)
    
# End Task