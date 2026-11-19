import json
import logging
import threading

from django.shortcuts import render, redirect
from rest_framework import status
from django.utils.translation import gettext_lazy
from django.views import generic
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from dashboard.mixins import PageMixin
from authentication.permissions import FullStackPermissionRequiredMixin
from django.contrib import messages
from django.db import connections, transaction
from django.db.models import F
from django.utils import timezone
from django.http import Http404, JsonResponse, HttpResponse

from process_manager.models import Phase, Activity, Task, TaskSyncRun
from dashboard.process_manager.tasks.forms import *
from dashboard.process_manager.tasks.form_design import (
    validate_form_design,
    validate_visibility_condition,
    validate_attachments,
    attachment_file_type,
    form_design_to_xlsform,
    xlsform_to_form_design,
    choices_to_xlsx,
    xlsx_to_choices,
    list_datasources,
    query_datasource,
    read_sheet_table,
    ADMIN_LEVEL_TYPES,
    DATASOURCE_OPS,
)
from dashboard.utils import sync_tasks
from dashboard.process_manager.tasks.sync_scope import SyncScope

logger = logging.getLogger(__name__)


def _names_for_search(objects):
    """Noms joints, posés en data-attribut des lignes pour la recherche côté navigateur des listes."""
    return ' | '.join(o.name for o in objects if o.name)


def _ids_for_filter(objects):
    """Identifiants séparés par des espaces (data-attribut des lignes pour les filtres à choix multiples)."""
    return ' '.join(str(o.pk) for o in objects)


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
        return Phase.objects.filter(project_id=self.request.session.get('project_id')).select_related(
            'project').prefetch_related('activity_set', 'task_set').order_by('order')
    
    def get_context_data(self, **kwargs):
        ctx = super(PhaseListView, self).get_context_data(**kwargs)
        ctx['class_object'] = 'Phase'
        # Recherche par activité / tâche (côté navigateur) : noms des activités et tâches de chaque phase.
        objects = list(ctx['objects'])
        for obj in objects:
            obj.search_activities = _names_for_search(obj.activity_set.all())
            obj.search_tasks = _names_for_search(obj.task_set.all())
            obj.filter_activity_ids = _ids_for_filter(obj.activity_set.all())
            obj.filter_task_ids = _ids_for_filter(obj.task_set.all())
        ctx['objects'] = objects
        project_id = self.request.session.get('project_id')
        ctx['filter_activities'] = Activity.objects.filter(project_id=project_id).select_related(
            'phase').order_by('phase__order', 'order')
        ctx['filter_tasks'] = Task.objects.filter(project_id=project_id).select_related(
            'activity').order_by('phase__order', 'activity__order', 'order')
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
        return Activity.objects.filter(project_id=self.request.session.get('project_id')).select_related(
            'phase', 'project').prefetch_related('task_set').order_by('phase__order', 'order')
    
    def get_context_data(self, **kwargs):
        ctx = super(ActivityListView, self).get_context_data(**kwargs)
        ctx['class_object'] = 'Activity'
        # Filtre par phase + recherche par tâche (côté navigateur).
        objects = list(ctx['objects'])
        for obj in objects:
            obj.search_tasks = _names_for_search(obj.task_set.all())
            obj.filter_task_ids = _ids_for_filter(obj.task_set.all())
        ctx['objects'] = objects
        ctx['filter_phases'] = Phase.objects.filter(
            project_id=self.request.session.get('project_id')).order_by('order')
        ctx['filter_tasks'] = Task.objects.filter(
            project_id=self.request.session.get('project_id')).select_related(
            'activity').order_by('phase__order', 'activity__order', 'order')
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
        return Task.objects.filter(project_id=self.request.session.get('project_id')).select_related(
            'phase', 'activity', 'project').order_by('phase__order', 'activity__order', 'order')
    
    def get_context_data(self, **kwargs):
        ctx = super(TaskListView, self).get_context_data(**kwargs)
        ctx['class_object'] = 'Task'
        # Filtres par phase et par activité (côté navigateur).
        project_id = self.request.session.get('project_id')
        ctx['filter_phases'] = Phase.objects.filter(project_id=project_id).order_by('order')
        ctx['filter_activities'] = Activity.objects.filter(project_id=project_id).order_by('phase__order', 'order')
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

        # Phase de chaque activité proposée : le formulaire ne montre que les activités de la phase choisie.
        ctx['activity_phases'] = {
            str(a_id): ph_id for a_id, ph_id in ctx['form'].fields['activity'].queryset.values_list('id', 'phase_id')
        }
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


# Task form builder

class _TaskScopedMixin(LoginRequiredMixin, FullStackPermissionRequiredMixin):
    """Récupère la Task du projet courant ou lève Http404."""

    def get_task(self, request, task_id):
        try:
            return Task.objects.get(
                id=task_id,
                project_id=request.session.get('project_id'),
            )
        except Task.DoesNotExist:
            raise Http404

    def get_cycle_id(self, request, task):
        """Cycle courant (session) s'il appartient à la tâche, sinon 1er cycle
        de la tâche."""
        cycle_id = request.session.get('cycle_id')
        if cycle_id and task.cycles.filter(id=cycle_id).exists():
            return cycle_id
        first = task.cycles.first()
        return first.id if first else None


class TaskFormBuilderView(PageMixin, _TaskScopedMixin, generic.TemplateView):
    """Interface visuelle de création du formulaire d'une tâche (attribut
    ``Task.form``). Le compilateur arbre -> format stocké vit dans le JS ;
    cette vue ne fait que fournir le JSON courant et rendre la page."""

    template_name = 'process_manager/tasks/form_builder.html'
    title = gettext_lazy('Form builder')
    active_level1 = 'process_manager_tasks'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        task = self.get_task(self.request, kwargs['id'])
        ctx['class_object'] = 'Task'
        ctx['task'] = task
        ctx['task_form'] = task.form or []
        # Pièces jointes avec leur type de fichier effectif (déduit du nom pour
        # les slots créés avant le choix explicite du type).
        ctx['task_attachments'] = [
            dict(slot, file_type=attachment_file_type(slot)) if isinstance(slot, dict) else slot
            for slot in (task.attachments or [])
        ]
        ctx['title'] = gettext_lazy('Form builder')
        # Modale sync_tasks : superutilisateurs uniquement.
        if self.request.user.is_superuser:
            cycle_id = self.get_cycle_id(self.request, task)
            ctx['sync_cycle_id'] = cycle_id
            ctx['sync_cycle_name'] = self.request.session.get('cycle_name')
            # Listes de la fenêtre lues dans CouchDB à son ouverture (TaskFormSyncScopeView) : la page reste rapide.
            ctx['sync_geo_levels'] = [
                {'key': 'region', 'label': gettext_lazy('Regions')},
                {'key': 'prefecture', 'label': gettext_lazy('Prefectures')},
                {'key': 'commune', 'label': gettext_lazy('Communes')},
                {'key': 'canton', 'label': gettext_lazy('Cantons')},
            ]
            # Libellés du suivi de synchronisation (json_script : apostrophes sans risque dans le JS).
            ctx['sync_i18n'] = {key: str(text) for key, text in {
                'running': gettext_lazy('Sync in progress'),
                'done': gettext_lazy('Sync finished'),
                'failed': gettext_lazy('Sync failed'),
                'interrupted': gettext_lazy('Sync interrupted'),
                'since': gettext_lazy('for'),
                'in': gettext_lazy('in'),
                'after': gettext_lazy('after'),
                'on': gettext_lazy('on'),
                'by': gettext_lazy('started by'),
                'dbs': gettext_lazy('databases walked through'),
                'current': gettext_lazy('current'),
                'villages': gettext_lazy('headquarters villages processed'),
                'created': gettext_lazy('created'),
                'updated': gettext_lazy('updated'),
                'expected': gettext_lazy('expected'),
                'differs': gettext_lazy('Fewer villages processed than expected: check the facilitators concerned.'),
                'silent': gettext_lazy('No news from the server for'),
                'rerun': gettext_lazy('You can run it again: already synchronised villages are updated, not duplicated.'),
                'badge_running': gettext_lazy('sync in progress'),
                'badge_done': gettext_lazy('sync finished'),
                'badge_failed': gettext_lazy('sync failed'),
                'last': gettext_lazy('Last sync'),
                'none': gettext_lazy('No sync of this task launched from this window yet.'),
            }.items()}
        ctx['breadcrumb'] = [
            {
                'url': reverse_lazy('dashboard:process_manager:tasks:task_list'),
                'title': gettext_lazy('Tasks'),
            },
            {'url': '', 'title': task.name},
            {'url': '', 'title': ctx['title']},
        ]
        return ctx


def _prune_invalid_cross_task_refs(form, project_id, visibility_condition=None, attachments=None):
    """``choicesFrom`` et ``crossTaskVisibility`` (page-level) référencent une
    tâche source (``sourceTaskId``) dans une AUTRE tâche ; ``visibility_condition``
    (task-level, optionnel) et ``Task.attachments[i]["conditions"]`` (task-level,
    optionnel) font de même — ``form_design.py`` reste délibérément découplé de
    l'ORM (cf. commentaire en tête de ce module) et ne peut donc pas vérifier
    que ces tâches existent encore (même projet) ; fait ici, après validation,
    EN UNE SEULE requête pour les 4 mécanismes, sur le même principe
    "réparation silencieuse" que le reste de cette vue. Renvoie
    ``(visibility_condition, attachments)`` nettoyés (``visibility_condition``
    devient ``None`` si sa tâche source n'existe plus ; les conditions
    d'attachment dont la tâche source n'existe plus sont retirées sans
    supprimer le slot lui-même)."""
    task_ids = set()
    for page in form or []:
        if not isinstance(page, dict):
            continue
        for key in ('choicesFrom', 'crossTaskVisibility'):
            for entry in page.get(key) or []:
                if isinstance(entry, dict) and entry.get('sourceTaskId') is not None:
                    task_ids.add(entry['sourceTaskId'])
    if isinstance(visibility_condition, dict) and visibility_condition.get('sourceTaskId') is not None:
        task_ids.add(visibility_condition['sourceTaskId'])
    for slot in attachments or []:
        if not isinstance(slot, dict):
            continue
        for cond in slot.get('conditions') or []:
            if isinstance(cond, dict) and cond.get('sourceTaskId') is not None:
                task_ids.add(cond['sourceTaskId'])

    if not task_ids:
        return visibility_condition, attachments

    valid_ids = set(
        Task.objects.filter(id__in=task_ids, project_id=project_id).values_list('id', flat=True)
    )

    def _still_valid(entry):
        return not (
            isinstance(entry, dict) and entry.get('sourceTaskId') is not None
            and entry['sourceTaskId'] not in valid_ids
        )

    for page in form or []:
        if not isinstance(page, dict):
            continue
        for key in ('choicesFrom', 'crossTaskVisibility'):
            entries = page.get(key)
            if entries:
                page[key] = [entry for entry in entries if _still_valid(entry)]

    if isinstance(visibility_condition, dict) and not _still_valid(visibility_condition):
        visibility_condition = None

    for slot in attachments or []:
        if isinstance(slot, dict) and slot.get('conditions'):
            slot['conditions'] = [cond for cond in slot['conditions'] if _still_valid(cond)]

    return visibility_condition, attachments


class TaskFormBuilderSaveView(_TaskScopedMixin, generic.View):
    """Reçoit le formulaire final (JSON), le valide et l'enregistre dans
    ``Task.form`` (la synchro CouchDB ``process_design`` est faite par
    ``Task.save()``)."""

    def post(self, request, *args, **kwargs):
        task = self.get_task(request, kwargs['id'])
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            return JsonResponse({'ok': False, 'errors': ['JSON invalide.']}, status=400)

        form = payload.get('form', payload)
        clean, errors = validate_form_design(form)
        if errors:
            return JsonResponse({'ok': False, 'errors': errors}, status=422)

        share_mode = payload.get('share_mode') or Task.SHARE_MODE_NONE
        if share_mode not in dict(Task.SHARE_MODE_CHOICES):
            share_mode = Task.SHARE_MODE_NONE

        # Visibilité conditionnelle de la tâche entière (hors `form`, mirroir
        # task-level de `crossTaskVisibility` — cf. form_design.py).
        visibility_condition = validate_visibility_condition(payload.get('visibility_condition'))

        # Pièces jointes attendues (hors `form` — onglet "Pièces jointes").
        # Clé absente du payload (ancien client / autre écran de sauvegarde) =
        # ne pas toucher `task.attachments` du tout, pour ne jamais effacer
        # silencieusement des slots existants (ex. saisis en admin Django).
        attachments_provided = 'attachments' in payload
        attachments, attach_errors = validate_attachments(payload.get('attachments'))
        if attach_errors:
            return JsonResponse({'ok': False, 'errors': attach_errors}, status=422)

        visibility_condition, attachments = _prune_invalid_cross_task_refs(
            clean, task.project_id, visibility_condition,
            attachments if attachments_provided else None,
        )
        task.form = clean
        task.share_mode = share_mode
        # Document Word / PDF générable : modifié seulement s'il est envoyé (anciens clients inchangés)
        if 'generated_document' in payload:
            generated_document = payload.get('generated_document') or ''
            if generated_document in dict(Task.GENERATED_DOCUMENT_CHOICES):
                task.generated_document = generated_document
        task.visibility_condition = visibility_condition
        if attachments_provided:
            task.attachments = attachments
        task.save()
        return JsonResponse({
            'ok': True, 'form': task.form, 'share_mode': task.share_mode,
            'visibility_condition': task.visibility_condition,
            'attachments': task.attachments,
        })


class TaskFormXlsExportView(_TaskScopedMixin, generic.View):
    """Exporte ``Task.form`` en classeur XLSForm (.xlsx)."""

    def get(self, request, *args, **kwargs):
        task = self.get_task(request, kwargs['id'])
        content = form_design_to_xlsform(task.form or [], form_title=task.name)
        response = HttpResponse(
            content,
            content_type=(
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            ),
        )
        filename = f'form_task_{task.id}.xlsx'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class TaskFormXlsImportView(_TaskScopedMixin, generic.View):
    """Convertit un .xlsx XLSForm en design de formulaire et le renvoie au
    builder (sans enregistrer : l'utilisateur relit puis sauvegarde)."""

    def post(self, request, *args, **kwargs):
        self.get_task(request, kwargs['id'])
        uploaded = request.FILES.get('file')
        if not uploaded:
            return JsonResponse({'ok': False, 'errors': ['Aucun fichier.']}, status=400)
        try:
            form = xlsform_to_form_design(uploaded)
        except Exception as exc:  # noqa: BLE001 - message utilisateur
            return JsonResponse(
                {'ok': False, 'errors': [f'Import impossible : {exc}']}, status=422,
            )
        clean, errors = validate_form_design(form)
        return JsonResponse({'ok': not errors, 'form': form, 'errors': errors})


class TaskFormChoicesExportView(_TaskScopedMixin, generic.View):
    """Exporte en .xlsx la liste de choix (``select_one`` / ``select_multiple``)
    envoyée par le builder. Le fichier produit illustre aussi le format attendu
    à l'import (colonnes ``valeur`` / ``libelle``)."""

    def post(self, request, *args, **kwargs):
        self.get_task(request, kwargs['id'])
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            payload = {}
        content = choices_to_xlsx(payload.get('choices') or [])
        response = HttpResponse(
            content,
            content_type=(
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            ),
        )
        response['Content-Disposition'] = 'attachment; filename="choix.xlsx"'
        return response


class TaskFormChoicesImportView(_TaskScopedMixin, generic.View):
    """Lit un .xlsx et renvoie au builder la liste des valeurs de choix (sans
    rien enregistrer : l'utilisateur relit puis sauvegarde le formulaire)."""

    def post(self, request, *args, **kwargs):
        self.get_task(request, kwargs['id'])
        uploaded = request.FILES.get('file')
        if not uploaded:
            return JsonResponse({'ok': False, 'errors': ['Aucun fichier.']}, status=400)
        try:
            choices = xlsx_to_choices(uploaded)
        except Exception as exc:  # noqa: BLE001 - message utilisateur
            return JsonResponse(
                {'ok': False, 'errors': [f'Import impossible : {exc}']}, status=422,
            )
        return JsonResponse({'ok': True, 'choices': choices})


class TaskFormDataSourcesView(_TaskScopedMixin, generic.View):
    """Métadonnées des sources dynamiques pour les sélecteurs du builder :
    tables de référence autorisées + colonnes, niveaux administratifs,
    opérateurs de filtre."""

    def get(self, request, *args, **kwargs):
        self.get_task(request, kwargs['id'])
        return JsonResponse({
            'ok': True,
            'tables': list_datasources(),
            'admin_levels': ADMIN_LEVEL_TYPES,
            'ops': list(DATASOURCE_OPS.keys()),
        })


class TaskFormOtherTasksView(_TaskScopedMixin, generic.View):
    """Liste des AUTRES tâches du même projet (id, nom, phase, activité) —
    alimente le picker « tâche source » de ``choicesFrom`` (options d'un
    select construites depuis la réponse d'un select d'une autre tâche)."""

    def get(self, request, *args, **kwargs):
        task = self.get_task(request, kwargs['id'])
        others = Task.objects.filter(
            project_id=request.session.get('project_id'),
        ).exclude(id=task.id).select_related('phase', 'activity').order_by(
            'phase__order', 'activity__order', 'order',
        )
        return JsonResponse({
            'ok': True,
            'tasks': [
                {
                    'id': t.id, 'name': t.name,
                    'phase_name': t.phase.name if t.phase_id else '',
                    'activity_name': t.activity.name if t.activity_id else '',
                }
                for t in others
            ],
        })


def _select_field_paths(properties, fields, prefix=""):
    """``[(chemin, libellé), ...]`` des feuilles select_one/select_multiple
    (_check) de ``properties`` — descend récursivement dans les
    groupes/répétables en lisant ``fields`` (``page.options.fields``) EN
    PARALLÈLE pour retrouver le libellé à n'importe quelle profondeur, même
    logique de double-traversée que ``_clean_options_fields`` (groupe :
    ``opts["fields"]`` ; répétable : ``opts["item"]["fields"]``)."""
    from dashboard.process_manager.tasks.form_design import _is_select_prop, _sub_properties

    out = []
    for name, prop in (properties or {}).items():
        if not isinstance(prop, dict):
            continue
        path = f"{prefix}.{name}" if prefix else name
        opts = (fields or {}).get(name) or {}
        sub_props = _sub_properties(prop)
        if sub_props is not None:
            sub_fields = opts.get("fields") or (opts.get("item") or {}).get("fields") or {}
            out.extend(_select_field_paths(sub_props, sub_fields, path))
        elif _is_select_prop(prop):
            out.append((path, opts.get("label") or name))
    return out


def _all_field_paths(properties, fields, prefix=""):
    """Comme ``_select_field_paths`` mais renvoie TOUTE feuille (pas
    seulement select_one/select_multiple) — alimente le picker « champ
    source » de ``crossTaskVisibility`` (visibilité conditionnelle inter-
    tâches), qui peut cibler/sourcer n'importe quel type de champ, contrairement
    à ``choicesFrom`` qui ne concerne que des select. Les champs "note"
    (purement informatifs, jamais de valeur) sont exclus — inutiles comme
    source d'une condition."""
    from dashboard.process_manager.tasks.form_design import _sub_properties

    out = []
    for name, prop in (properties or {}).items():
        if not isinstance(prop, dict):
            continue
        path = f"{prefix}.{name}" if prefix else name
        opts = (fields or {}).get(name) or {}
        sub_props = _sub_properties(prop)
        if sub_props is not None:
            sub_fields = opts.get("fields") or (opts.get("item") or {}).get("fields") or {}
            out.extend(_all_field_paths(sub_props, sub_fields, path))
        elif not prop.get("_note"):
            out.append((path, opts.get("label") or name))
    return out


class TaskFormTaskFieldsView(_TaskScopedMixin, generic.View):
    """Chemins pointés (``"$<index>.<chemin>"``, même convention que
    ``rules``/``when.field``) des champs d'une AUTRE tâche du même projet —
    alimente le picker « champ source » de ``choicesFrom`` (par défaut,
    select_one/select_multiple uniquement) ET de ``crossTaskVisibility``
    (``?all=1``, tout type de champ — visibilité conditionnelle inter-tâches,
    peut dépendre/cibler n'importe quel type de réponse)."""

    def get(self, request, *args, **kwargs):
        self.get_task(request, kwargs['id'])
        other_task = Task.objects.filter(
            id=kwargs['other_id'], project_id=request.session.get('project_id'),
        ).first()
        if not other_task:
            return JsonResponse({'ok': False, 'fields': []}, status=404)

        path_fn = _all_field_paths if request.GET.get('all') else _select_field_paths
        result = []
        for idx, page in enumerate(other_task.form or []):
            if not isinstance(page, dict):
                continue
            properties = (page.get('page') or {}).get('properties') or {}
            page_fields = (page.get('options') or {}).get('fields') or {}
            for path, label in path_fn(properties, page_fields):
                result.append({'path': f'${idx}.{path}', 'label': f'P{idx + 1} · {label}'})
        return JsonResponse({'ok': True, 'fields': result})


class TaskFormDataSourcePreviewView(_TaskScopedMixin, generic.View):
    """Exécute une source (PostgreSQL liste blanche / niveaux administratifs) et
    renvoie les lignes {v,l,p} à figer dans le champ (snapshot). N'enregistre
    rien : le builder stocke le dataset puis l'utilisateur sauvegarde."""

    def post(self, request, *args, **kwargs):
        self.get_task(request, kwargs['id'])
        try:
            spec = json.loads(request.body.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            return JsonResponse({'ok': False, 'errors': ['JSON invalide.']}, status=400)
        try:
            rows, truncated = query_datasource(spec)
        except Exception as exc:  # noqa: BLE001 - message utilisateur
            return JsonResponse({'ok': False, 'errors': [str(exc)]}, status=422)
        return JsonResponse({
            'ok': True, 'rows': rows, 'count': len(rows), 'truncated': truncated,
        })


class TaskFormDatasetSheetView(_TaskScopedMixin, generic.View):
    """Lit un .xlsx et renvoie {columns, rows} pour que le builder mappe les
    colonnes valeur / libellé / parent d'une source « fichier »."""

    def post(self, request, *args, **kwargs):
        self.get_task(request, kwargs['id'])
        uploaded = request.FILES.get('file')
        if not uploaded:
            return JsonResponse({'ok': False, 'errors': ['Aucun fichier.']}, status=400)
        try:
            # Remplissage automatique : nombre maximal de lignes choisi dans le générateur
            from dashboard.process_manager.tasks.form_design import autofill_max_rows
            limit = autofill_max_rows({'maxRows': request.POST.get('limit')}) if request.POST.get('limit') else None
            columns, rows = read_sheet_table(uploaded, limit) if limit else read_sheet_table(uploaded)
        except Exception as exc:  # noqa: BLE001 - message utilisateur
            return JsonResponse(
                {'ok': False, 'errors': [f'Lecture impossible : {exc}']}, status=422,
            )
        return JsonResponse({
            'ok': True, 'columns': columns, 'rows': rows, 'count': len(rows),
        })


class _SyncRunProgress:
    """Rappel d'avancement passé à ``sync_tasks`` : met à jour la ligne TaskSyncRun (et son « signe de vie »)."""

    def __init__(self, run_id):
        self.run_id = run_id

    def _update(self, **fields):
        TaskSyncRun.objects.filter(pk=self.run_id).update(heartbeat=timezone.now(), **fields)

    def __call__(self, event, db=None, total=None, created=None):
        if event == 'start':
            self._update(dbs_total=F('dbs_total') + (total or 0))
        elif event == 'facilitator':
            self._update(current_db=(db or '')[:255])
        elif event == 'village':
            field = 'created_docs' if created else 'updated_docs'
            self._update(pairs_done=F('pairs_done') + 1, **{field: F(field) + 1})
        elif event == 'facilitator_done':
            self._update(dbs_done=F('dbs_done') + 1)

    def finish(self, error=None):
        fields = {'finished_at': timezone.now(),
                  'status': TaskSyncRun.STATUS_FAILED if error else TaskSyncRun.STATUS_DONE}
        if error:
            fields['error'] = error[:2000]
        else:
            fields['current_db'] = ''
        self._update(**fields)


def _run_sync_tasks_in_thread(run_id=None, **kwargs):
    """Lance ``sync_tasks`` dans un thread démon : l'action peut être longue
    (parcours des bases CouchDB des facilitateurs) et ne doit ni bloquer la
    réponse HTTP ni les requêtes des autres utilisateurs. Avec ``run_id``,
    l'avancement et la fin (ou l'échec) sont tenus dans TaskSyncRun."""
    progress = _SyncRunProgress(run_id) if run_id else None

    def _worker():
        try:
            sync_tasks(progress=progress, **kwargs)
            if progress:
                progress.finish()
        except Exception as exc:  # noqa: BLE001 - on loggue, le thread ne doit pas planter en silence
            logger.exception('sync_tasks (form builder) a échoué : %s', kwargs)
            if progress:
                try:
                    progress.finish(error=f'{type(exc).__name__}: {exc}')
                except Exception:  # noqa: BLE001
                    logger.exception('TaskSyncRun %s : échec non enregistré', run_id)
        finally:
            # Chaque thread a ses propres connexions DB : on les ferme.
            for conn in connections.all():
                conn.close()

    thread = threading.Thread(
        target=_worker,
        name=f"sync_tasks-{kwargs.get('tasks_ids')}",
        daemon=True,
    )
    thread.start()


def _sync_run_json(run):
    """Avancement d'une synchronisation pour la fenêtre (durées calculées côté serveur : pas d'écart d'horloge)."""
    now = timezone.now()
    state = 'interrupted' if run.is_stale() else run.status
    user = run.started_by
    return {
        'id': run.id,
        'status': state,
        'running': state == TaskSyncRun.STATUS_RUNNING,
        'started_at': timezone.localtime(run.started_at).strftime('%d/%m/%Y %H:%M:%S'),
        'finished_at': timezone.localtime(run.finished_at).strftime('%d/%m/%Y %H:%M:%S') if run.finished_at else None,
        'elapsed': int(((run.finished_at or now) - run.started_at).total_seconds()),
        'silent_for': int((now - run.heartbeat).total_seconds()),
        'started_by': (user.get_full_name() or user.username) if user else '',
        'expected_villages': run.expected_villages,
        'expected_facilitators': run.expected_facilitators,
        'expected_pairs': run.expected_pairs,
        'dbs_total': run.dbs_total,
        'dbs_done': run.dbs_done,
        'current_db': run.current_db,
        'pairs_done': run.pairs_done,
        'created_docs': run.created_docs,
        'updated_docs': run.updated_docs,
        'error': run.error,
    }


class TaskFormSyncStatusView(_TaskScopedMixin, generic.View):
    """Avancement des dernières synchronisations de la tâche (JSON), interrogé par la fenêtre. Superutilisateurs."""

    def test_func(self):
        return bool(self.request.user.is_authenticated and self.request.user.is_superuser)

    def get(self, request, *args, **kwargs):
        task = self.get_task(request, kwargs['id'])
        runs = [_sync_run_json(r) for r in TaskSyncRun.objects.filter(task=task).select_related('started_by')[:5]]
        return JsonResponse({'runs': runs, 'running': any(r['running'] for r in runs)})


def _scope_reads_couch(source):
    """Source des villages sièges de la fenêtre : 'postgres' (défaut, copie en base `Facilitator.administrative_levels`,
    instantané) ou 'couch' (documents facilitateur CouchDB, ceux que lit sync_tasks ; bouton de la fenêtre)."""
    return source == 'couch'


class TaskFormSyncScopeView(_TaskScopedMixin, generic.View):
    """Listes de la fenêtre « Synchroniser cette tâche » (JSON) : villages sièges du projet et du cycle (copie en
    base, ou CouchDB avec ?source=couch), leurs régions … cantons, et les bases. Superutilisateurs seulement."""

    def test_func(self):
        return bool(self.request.user.is_authenticated and self.request.user.is_superuser)

    def get(self, request, *args, **kwargs):
        task = self.get_task(request, kwargs['id'])
        cycle_id = self.get_cycle_id(request, task)
        source = 'couch' if _scope_reads_couch(request.GET.get('source')) else 'postgres'
        scope = SyncScope(request.session.get('project_id'), cycle_id, read_couch=source == 'couch')
        return JsonResponse(dict(scope.as_json(), source=source))


class TaskFormSyncView(_TaskScopedMixin, generic.View):
    """Déclenche ``dashboard.utils.sync_tasks`` pour LA tâche courante, en
    arrière-plan (thread). Paramètres choisis dans la modale du form builder.

    Réservé aux **superutilisateurs** (l'action touche toutes les bases
    CouchDB des facilitateurs)."""

    def test_func(self):
        return bool(
            self.request.user.is_authenticated and self.request.user.is_superuser
        )

    def post(self, request, *args, **kwargs):
        task = self.get_task(request, kwargs['id'])
        project_id = request.session.get('project_id')
        cycle_id = self.get_cycle_id(request, task)
        if not cycle_id:
            return JsonResponse(
                {'ok': False, 'errors': ["Aucun cycle associé à cette tâche."]},
                status=422,
            )

        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except (ValueError, UnicodeDecodeError):
            return JsonResponse({'ok': False, 'errors': ['JSON invalide.']}, status=400)

        develop_mode = bool(payload.get('develop_mode', False))
        training_mode = bool(payload.get('training_mode', False))
        no_sql_dbs = [str(x) for x in (payload.get('no_sql_dbs') or []) if str(x).strip()]
        raw_ids = payload.get('administrativelevel_ids') or []
        geo = payload.get('geo') or {}
        if not isinstance(raw_ids, list) or not isinstance(geo, dict):
            return JsonResponse({'ok': False, 'errors': ['Paramètres invalides.']}, status=400)

        # Zone (régions … cantons), villages sièges, bases, develop_mode et training_mode se combinent.
        # Les identifiants sont passés en TEXTE : sync_tasks compare `str(id) in administrativelevel_ids`.
        # Même source que les listes affichées dans la fenêtre (copie en base par défaut, CouchDB si relu).
        source = 'couch' if _scope_reads_couch(payload.get('source')) else 'postgres'
        scope = SyncScope(project_id, cycle_id, read_couch=source == 'couch')
        administrativelevel_ids, facilitators, villages = scope.resolve(
            develop_mode, training_mode, no_sql_dbs, raw_ids, geo,
        )
        restricted = bool(raw_ids) or any(geo.get(key) for key in ('region', 'prefecture', 'commune', 'canton'))
        if restricted and not administrativelevel_ids:
            return JsonResponse({'ok': False, 'errors': [gettext_lazy(
                'No headquarters village matches the chosen area and villages.').__str__()]}, status=422)
        if not facilitators:
            return JsonResponse({'ok': False, 'errors': [gettext_lazy(
                'No facilitator matches these choices (databases, villages, develop_mode, training_mode).'
            ).__str__()]}, status=422)

        targeted = set(villages)
        expected_pairs = sum(len(f['villages'] & targeted) for f in facilitators)
        with transaction.atomic():
            # Une seule synchronisation à la fois par tâche (verrou sur la ligne de la tâche pendant la vérification).
            Task.objects.select_for_update().filter(pk=task.pk).first()
            running = TaskSyncRun.objects.filter(
                task=task, status=TaskSyncRun.STATUS_RUNNING,
                heartbeat__gte=timezone.now() - TaskSyncRun.STALE_AFTER,
            ).first()
            if running:
                return JsonResponse({'ok': False, 'errors': [gettext_lazy(
                    'A sync of this task is already running; wait for it to finish.').__str__()],
                    'run': _sync_run_json(running)}, status=409)
            # Synchronisations restées « en cours » sans nouvelle : serveur redémarré, thread perdu.
            TaskSyncRun.objects.filter(task=task, status=TaskSyncRun.STATUS_RUNNING).update(
                status=TaskSyncRun.STATUS_FAILED, finished_at=timezone.now(),
                error=gettext_lazy('Interrupted: no news from the server for 10 minutes (restart?).').__str__())
            run = TaskSyncRun.objects.create(
                task=task, project_id=project_id, cycle_id=cycle_id, started_by=request.user,
                params={'source': source, 'develop_mode': develop_mode, 'training_mode': training_mode, 'no_sql_dbs': no_sql_dbs,
                        'administrativelevel_ids': [str(x) for x in raw_ids], 'geo': geo},
                expected_villages=len(villages), expected_facilitators=len(facilitators),
                expected_pairs=expected_pairs,
            )
        try:
            _run_sync_tasks_in_thread(
                run_id=run.id,
                project_id=project_id,
                cycle_id=cycle_id,
                develop_mode=develop_mode,
                training_mode=training_mode,
                no_sql_dbs=no_sql_dbs or False,
                administrativelevel_ids=administrativelevel_ids,
                tasks_ids=[task.id],
            )
        except Exception as exc:  # noqa: BLE001 - thread non démarré : la ligne ne doit pas rester « en cours »
            _SyncRunProgress(run.id).finish(error=f'{type(exc).__name__}: {exc}')
            raise
        return JsonResponse({
            'ok': True,
            'run': _sync_run_json(TaskSyncRun.objects.get(pk=run.pk)),
            'message': gettext_lazy(
                'Synchronisation lancée en arrière-plan. Elle peut prendre '
                'plusieurs minutes selon le nombre de facilitateurs.'
            ).__str__() + ' ' + gettext_lazy(
                'Expected: %(villages)s headquarters village(s), %(facilitators)s facilitator(s).'
            ).__str__() % {'villages': len(villages), 'facilitators': len(facilitators)},
            'villages': len(villages),
            'facilitators': len(facilitators),
        })

# End Task form builder