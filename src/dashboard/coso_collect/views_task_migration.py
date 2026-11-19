"""Onglet « Import vers les tâches » d'un formulaire COSOCollect (superutilisateurs) : exécute
`migrate_cosocollect_to_tasks` pour CE formulaire avec les options choisies dans la page, en thread, avec suivi
de l'avancement (CollectTaskMigrationRun) — même principe que « Synchroniser cette tâche » du générateur de
formulaire de tâche.

Les règles de l'import sont celles de la commande (coso_collect/task_migration.py)."""
import io
import logging
import os
import tempfile
import threading

from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.db import connections, transaction
from django.db.models import Count, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _, gettext_lazy
from django.views import generic

from coso_collect import task_migration as tm
from coso_collect.models import CollectForm, CollectSubmission, CollectTaskMigrationRun
from process_manager.models import Cycle, Project, Task

from .views import CollectPageMixin, FormAdminMixin

logger = logging.getLogger(__name__)

ACTION_SIMULATE = 'simulate'
ACTION_MATCHES = 'matches'
ACTION_APPLY = 'apply'
ACTION_UNDO_SIMULATE = 'undo_simulate'
ACTION_UNDO_APPLY = 'undo_apply'
WRITING_ACTIONS = (ACTION_APPLY, ACTION_UNDO_APPLY)


def action_choices():
    return [
        (ACTION_SIMULATE, _('Simulation (nothing is written)')),
        (ACTION_MATCHES, _('Matches only (form -> task, field differences)')),
        (ACTION_APPLY, _('Import into the tasks (writes)')),
        (ACTION_UNDO_SIMULATE, _('Undo the last import — simulation')),
        (ACTION_UNDO_APPLY, _('Undo the last import (writes)')),
    ]


def account_choices():
    return [
        (tm.ACCOUNT_REAL_FC, _('Real CF')),
        (tm.ACCOUNT_REAL_FT, _('Real TF')),
        (tm.ACCOUNT_TRAINING, _('Training accounts')),
        (tm.ACCOUNT_DEVELOP, _('Development / demo accounts')),
        (tm.ACCOUNT_OTHERS, _('Other accounts (web accounts without facilitator)')),
    ]


def account_counts(form, statuses=None):
    """{catégorie: nombre d'enregistrements} du formulaire (aux statuts donnés, défaut : envoyés)."""
    classifier = tm.AccountClassifier()
    counts = {key: 0 for key in tm.ACCOUNT_CATEGORIES}
    for sub in tm.submitted_submissions(form, statuses):
        for cat in classifier.categories(sub):
            counts[cat] += 1
    return counts


def parse_ids(raw):
    """« 12, 34 56 » -> [12, 34, 56] ; ValueError si un élément n'est pas un entier."""
    return [int(x) for x in (raw or '').replace(',', ' ').replace(';', ' ').split()]


class TaskMigrationForm(forms.Form):
    """Options de la commande (sauf --form, toujours le formulaire de la page, et --report, toujours produit)."""
    action = forms.ChoiceField(choices=())
    project = forms.ModelChoiceField(queryset=Project.objects.all())
    cycle = forms.ModelChoiceField(queryset=Cycle.objects.all())
    task = forms.ModelChoiceField(queryset=Task.objects.all(), required=False)
    villages = forms.CharField(required=False)
    min_score = forms.FloatField(min_value=0, max_value=1, initial=tm.DEFAULT_MIN_SCORE)
    no_overwrite = forms.BooleanField(required=False)
    attachments_by = forms.ChoiceField(choices=[(tm.ATTACHMENTS_BY_NAME, 'name'), (tm.ATTACHMENTS_BY_ORDER, 'order')],
                                       initial=tm.ATTACHMENTS_BY_NAME)
    files = forms.ChoiceField(choices=[(tm.FILES_COPY, 'copy'), (tm.FILES_LINK, 'link')], initial=tm.FILES_COPY)
    force = forms.BooleanField(required=False)
    force_validated = forms.BooleanField(required=False)
    # Statuts des enregistrements recopiés (--status) ; au moins un.
    statuses = forms.MultipleChoiceField(choices=CollectSubmission.STATUSES)
    # Comptes auteurs des enregistrements recopiés (--accounts) ; au moins un (la page coche « vrais FC »).
    accounts = forms.MultipleChoiceField(choices=())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['action'].choices = action_choices()
        self.fields['statuses'].error_messages['required'] = _('Choose at least one record status.')
        self.fields['accounts'].choices = account_choices()
        self.fields['accounts'].error_messages['required'] = _('Choose at least one kind of account.')

    def clean_villages(self):
        try:
            return parse_ids(self.cleaned_data.get('villages'))
        except ValueError:
            raise forms.ValidationError(_('Village / canton identifiers: whole numbers separated by commas.'))

    def clean(self):
        data = super().clean()
        project, cycle, task = data.get('project'), data.get('cycle'), data.get('task')
        if project and cycle and cycle.project_id != project.id:
            self.add_error('cycle', _('This cycle does not belong to the project.'))
        if task and project and task.project_id != project.id:
            self.add_error('task', _('This task does not belong to the project.'))
        elif task and cycle and not task.cycles.filter(id=cycle.id).exists():
            self.add_error('task', _('This task is not in the cycle.'))
        return data

    def command_options(self, form_id):
        """Options de call_command (mêmes noms que la ligne de commande)."""
        d = self.cleaned_data
        action = d['action']
        opts = {
            'project': d['project'].id, 'cycle': d['cycle'].id, 'form': [form_id],
            'map': [f"{form_id}:{d['task'].id}"] if d.get('task') else [],
            'village': d['villages'], 'min_score': d['min_score'], 'no_overwrite': d['no_overwrite'],
            'attachments_by': d['attachments_by'], 'files': d['files'], 'force': d['force'],
            'force_validated': d['force_validated'],
            # ordre fixe (envoyé, rempli, démarré), quel que soit l'ordre des cases
            'status': [key for key, _label in reversed(CollectSubmission.STATUSES) if key in d['statuses']],
            # ordre fixe (celui de la page)
            'accounts': [key for key in tm.ACCOUNT_CATEGORIES if key in d['accounts']],
            'matches_only': action == ACTION_MATCHES,
            'undo': action in (ACTION_UNDO_SIMULATE, ACTION_UNDO_APPLY),
            'apply': action in WRITING_ACTIONS,
        }
        return opts

    def command_line(self, form_id):
        """La commande équivalente (affichée dans l'historique, rejouable en SSH)."""
        o = self.command_options(form_id)
        parts = ['python manage.py migrate_cosocollect_to_tasks', f"--project {o['project']}", f"--cycle {o['cycle']}",
                 f"--form {form_id}"]
        parts += [f'--map {m}' for m in o['map']] + [f'--village {v}' for v in o['village']]
        if o['status'] != list(tm.DEFAULT_STATUSES):
            parts += [f'--status {s}' for s in o['status']]
        if o['accounts'] != list(tm.DEFAULT_ACCOUNTS):
            parts += [f'--accounts {a}' for a in o['accounts']]
        if o['min_score'] != tm.DEFAULT_MIN_SCORE:
            parts.append(f"--min-score {o['min_score']}")
        if o['attachments_by'] != tm.ATTACHMENTS_BY_NAME:
            parts.append(f"--attachments-by {o['attachments_by']}")
        if o['files'] != tm.FILES_COPY:
            parts.append(f"--files {o['files']}")
        for key, flag in (('no_overwrite', '--no-overwrite'), ('force', '--force'), ('force_validated', '--force-validated'),
                          ('matches_only', '--matches-only'), ('undo', '--undo'), ('apply', '--apply')):
            if o[key]:
                parts.append(flag)
        return ' '.join(parts)


class SuperuserFormMixin(LoginRequiredMixin, FormAdminMixin):
    """Formulaire `pk`, réservé aux superutilisateurs (non connecté : page de connexion)."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_superuser:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


# --------------------------------------------------------------------------------------------------------------
# Exécution en thread et avancement
# --------------------------------------------------------------------------------------------------------------
class _LogStream(io.StringIO):
    """Sortie de la commande, recopiée dans la ligne de suivi au fil de l'eau (par _RunProgress)."""


class _RunProgress:
    """Rappel d'avancement passé à la commande : phase, étape, comptes par statut, journal (écrits au plus toutes
    les FLUSH_EVERY secondes, et à chaque changement de phase)."""
    FLUSH_EVERY = 1.0

    def __init__(self, run_id, stream):
        self.run_id = run_id
        self.stream = stream
        self.state = {'phase': '', 'total': 0, 'done': 0, 'current': '', 'counts': {}}
        self._last = 0.0

    def _flush(self, force=False):
        now = timezone.now().timestamp()
        if not force and now - self._last < self.FLUSH_EVERY:
            return
        self._last = now
        CollectTaskMigrationRun.objects.filter(pk=self.run_id).update(
            heartbeat=timezone.now(), log=self.stream.getvalue(), **self.state)

    def __call__(self, event, phase=None, total=None, current=None, status=None, **_info):
        if event == 'phase':
            self.state.update(phase=phase or '', total=total or 0, done=0, current='')
            self._flush(force=True)
        elif event == 'step':
            # current = base en cours de lecture (étape à venir) ; status = document traité (étape faite)
            if status is None:
                if self.state['phase'] in ('index', 'undo') and self.state['current']:
                    self.state['done'] += 1
            else:
                self.state['done'] += 1
                counts = self.state['counts']
                counts[status] = counts.get(status, 0) + 1
            self.state['current'] = (current or '')[:255]
            self._flush()
        elif event == 'result':
            # statut d'un document sans étape propre (annulation : étapes = bases)
            counts = self.state['counts']
            counts[status] = counts.get(status, 0) + 1
            self._flush()

    def finish(self, error=None, report=''):
        if self.state['phase'] in ('index', 'undo') and self.state['current']:
            self.state['done'] = self.state['total']
        self.state['current'] = ''
        CollectTaskMigrationRun.objects.filter(pk=self.run_id).update(
            heartbeat=timezone.now(), finished_at=timezone.now(), log=self.stream.getvalue(), report=report,
            status=CollectTaskMigrationRun.STATUS_FAILED if error else CollectTaskMigrationRun.STATUS_DONE,
            error=(error or '')[:4000], **self.state)


def run_migration(run_id, options):
    """Exécute la commande (dans le thread appelant) et tient la ligne de suivi à jour."""
    stream = _LogStream()
    progress = _RunProgress(run_id, stream)
    fd, report_path = tempfile.mkstemp(prefix='cosocollect_tasks_', suffix='.csv')
    os.close(fd)
    error, report = None, ''
    try:
        with_report = not options.get('matches_only') and not options.get('undo')
        call_command('migrate_cosocollect_to_tasks', stdout=stream, stderr=stream, no_color=True,
                     progress=progress, **dict(options, report=report_path if with_report else None))
        if with_report and os.path.exists(report_path):
            with open(report_path, encoding='utf-8-sig') as fh:
                report = fh.read()
    except BaseException as exc:  # noqa: BLE001 - CommandError compris : affiché dans la page
        logger.exception('migrate_cosocollect_to_tasks (page) a échoué : %s', options)
        error = f'{type(exc).__name__}: {exc}'
    finally:
        try:
            os.remove(report_path)
        except OSError:
            pass
    progress.finish(error=error, report=report)


def start_in_thread(run_id, options):
    def _worker():
        try:
            run_migration(run_id, options)
        except Exception:  # noqa: BLE001 - la ligne de suivi n'a pas pu être écrite
            logger.exception('CollectTaskMigrationRun %s : fin non enregistrée', run_id)
        finally:
            for conn in connections.all():
                conn.close()

    threading.Thread(target=_worker, name=f'cosocollect_tasks-{run_id}', daemon=True).start()


def run_json(run):
    now = timezone.now()
    state = 'interrupted' if run.is_stale() else run.status
    user = run.started_by
    return {
        'id': run.id,
        'status': state,
        'running': state == CollectTaskMigrationRun.STATUS_RUNNING,
        'action': run.action,
        'action_label': dict(action_choices()).get(run.action, run.action),
        'writes': run.action in WRITING_ACTIONS,
        'command': (run.params or {}).get('command', ''),
        'started_at': timezone.localtime(run.started_at).strftime('%d/%m/%Y %H:%M:%S'),
        'finished_at': timezone.localtime(run.finished_at).strftime('%d/%m/%Y %H:%M:%S') if run.finished_at else None,
        'elapsed': int(((run.finished_at or now) - run.started_at).total_seconds()),
        'silent_for': int((now - run.heartbeat).total_seconds()),
        'started_by': (user.get_full_name() or user.username) if user else '',
        'phase': run.phase, 'total': run.total, 'done': run.done, 'current': run.current,
        'counts': run.counts or {},
        'log': run.log,
        'error': run.error,
        'report_url': reverse('dashboard:coso_collect:task_migration_report', args=[run.form_id, run.id])
        if run.report else None,
    }


# --------------------------------------------------------------------------------------------------------------
# Vues
# --------------------------------------------------------------------------------------------------------------
class TaskMigrationView(SuperuserFormMixin, CollectPageMixin, generic.TemplateView):
    template_name = 'coso_collect/task_migration.html'

    def get_context_data(self, **kwargs):
        ctx = self.admin_context(super().get_context_data(**kwargs), 'task_migration')
        form = self.form_obj
        session = self.request.session
        projects = list(Project.objects.order_by('name'))
        # Projet par défaut : celui de la session s'il est permis au formulaire, sinon le 1er projet lié.
        linked = list(form.projects.values_list('id', flat=True)) \
            if form.project_scope == CollectForm.PROJECTS_SELECTED else []
        default_project = session.get('project_id')
        if linked and default_project not in linked:
            default_project = linked[0]
        cycles = list(Cycle.objects.select_related('project').order_by('project__name', 'order'))
        default_cycle = session.get('cycle_id') if default_project == session.get('project_id') else None
        if not default_cycle:
            default_cycle = next((c.id for c in cycles if c.project_id == default_project), None)
        status_counts = dict(form.submissions.order_by().values_list('status').annotate(n=Count('id')))
        sent_by_account = account_counts(form)
        ctx.update({
            'projects': projects, 'cycles': cycles, 'linked_projects': linked,
            'default_project': default_project, 'default_cycle': default_cycle,
            'actions': action_choices(), 'default_min_score': tm.DEFAULT_MIN_SCORE,
            # Statuts proposés (envoyé, rempli, démarré) avec le nombre d'enregistrements du formulaire
            'record_statuses': [
                {'key': key, 'label': label, 'count': status_counts.get(key, 0), 'default': key in tm.DEFAULT_STATUSES}
                for key, label in reversed(CollectSubmission.STATUSES)
            ],
            # Comptes auteurs (défaut : vrais FC), avec le nombre d'enregistrements ENVOYÉS de chacun
            'record_accounts': [
                {'key': key, 'label': label, 'count': sent_by_account.get(key, 0), 'default': key in tm.DEFAULT_ACCOUNTS}
                for key, label in account_choices()
            ],
            'migration_i18n': {
                'running': _('In progress'), 'done': _('Finished'), 'failed': _('Failed'),
                'interrupted': _('Interrupted (no news for more than 10 minutes)'),
                'phase_index': _('Reading the facilitators databases'),
                'phase_write': _('Writing into the task documents'),
                'phase_write_dry': _('Simulating the task documents'),
                'phase_undo': _('Undoing in the facilitators databases'),
                'started_by': _('started by'), 'elapsed': _('duration'), 'silent': _('last news'),
                'report': _('Download the report (CSV)'), 'log': _('Command output'),
                'no_run': _('No run yet for this form.'), 'history': _('Previous runs'),
                'confirm_write': _('This run WRITES into the task documents of the facilitators. Continue?'),
                'error': _('Error'), 'auto': _('Automatic (by title)'),
                'matched': _('Automatic match'), 'none': _('No task found automatically'),
                'other_activity': _('close task under ANOTHER activity: choose it below if intended'),
                'ambiguous': _('several possible tasks: choose one below'),
                'statuses': {
                    'dry_run': _('to write (simulation)'), 'written': _('written'), 'unchanged': _('already up to date'),
                    'skipped_filled': _('skipped (already filled)'), 'skipped_validated': _('skipped (validated)'),
                    'no_common_fields': _('not written (no common field)'), 'missing_doc': _('document not found'),
                    'error': _('errors'), 'undone': _('restored'), 'skipped_modified': _('skipped (modified since)'),
                    'no_backup': _('without backup'),
                },
            },
        })
        return ctx


class TaskMigrationTasksView(SuperuserFormMixin, generic.View):
    """GET ?project=&cycle= : tâches du cycle et correspondance automatique de ce formulaire."""

    def get(self, request, *args, **kwargs):
        cycle = Cycle.objects.filter(id=request.GET.get('cycle'), project_id=request.GET.get('project')).first()
        if not cycle:
            return JsonResponse({'tasks': [], 'match': None})
        tasks = list(Task.objects.filter(project_id=cycle.project_id, cycles=cycle)
                     .select_related('activity', 'phase').order_by('phase__order', 'activity__order', 'order', 'id'))
        match = tm.match_forms_to_tasks([self.form_obj], tasks)[0]
        return JsonResponse({
            'tasks': [{'id': t.id, 'text': f'#{t.id} {tm.task_label(t)}'} for t in tasks],
            'match': {
                'task_id': match.task.id if match.task else None,
                'task': f'#{match.task.id} {tm.task_label(match.task)}' if match.task else None,
                'method': match.method, 'score': round(match.score or 0, 2),
                'candidates': [f'#{t.id} {tm.task_label(t)} ({score:.2f})' for score, t in match.candidates[:3]],
            },
        })


class TaskMigrationLevelsSearchView(SuperuserFormMixin, generic.View):
    """GET ?q= : régions, préfectures, communes, cantons et villages par nom (filtre --village) :
    {results: [{id, text}]}, du plus grand niveau au plus petit."""

    def get(self, request, *args, **kwargs):
        from administrativelevels.models import AdministrativeLevel
        term = (request.GET.get('q') or '').strip()
        if len(term) < 2:
            return JsonResponse({'results': []})
        types = ['Region', 'Prefecture', 'Commune', 'Canton', 'Village']
        qs = AdministrativeLevel.objects.filter(type__in=types).filter(
            Q(name__icontains=term) | Q(id=int(term)) if term.isdigit() else Q(name__icontains=term)
        ).select_related('parent', 'parent__parent')
        rank = {t: i for i, t in enumerate(types)}
        qs = sorted(qs[:200], key=lambda a: (rank.get(a.type, 9), a.name or ''))[:40]
        results = []
        for adl in qs:
            path = ' / '.join(p.name for p in (adl.parent, getattr(adl.parent, 'parent', None)) if p)
            results.append({'id': adl.id, 'text': f'{adl.name} ({_(adl.type)}{" — " + path if path else ""}) #{adl.id}'})
        return JsonResponse({'results': results})


class TaskMigrationStartView(SuperuserFormMixin, generic.View):
    """POST : options de la page -> nouvelle exécution en thread. 409 si une exécution est déjà en cours."""

    def post(self, request, *args, **kwargs):
        form = self.form_obj
        options_form = TaskMigrationForm(request.POST)
        if not options_form.is_valid():
            errors = {k: [str(e) for e in v] for k, v in options_form.errors.items()}
            return JsonResponse({'ok': False, 'message': _('Invalid options.'), 'errors': errors}, status=400)
        options = options_form.command_options(form.id)
        with transaction.atomic():
            CollectForm.objects.select_for_update().filter(pk=form.pk).first()
            running = CollectTaskMigrationRun.objects.filter(form=form, status=CollectTaskMigrationRun.STATUS_RUNNING)
            for run in running:
                if not run.is_stale():
                    return JsonResponse({'ok': False, 'message': _('A run is already in progress for this form.'),
                                         'run': run_json(run)}, status=409)
                run.status, run.finished_at = CollectTaskMigrationRun.STATUS_FAILED, timezone.now()
                run.error = 'Interrompue (aucune nouvelle depuis plus de 10 minutes).'
                run.save(update_fields=['status', 'finished_at', 'error'])
            run = CollectTaskMigrationRun.objects.create(
                form=form, started_by=request.user, action=options_form.cleaned_data['action'],
                params=dict(options, command=options_form.command_line(form.id)),
            )
        transaction.on_commit(lambda: start_in_thread(run.id, options))
        return JsonResponse({'ok': True, 'run': run_json(run)})


class TaskMigrationStatusView(SuperuserFormMixin, generic.View):
    """GET : 5 dernières exécutions de ce formulaire (la plus récente en premier)."""

    def get(self, request, *args, **kwargs):
        runs = [run_json(r) for r in CollectTaskMigrationRun.objects.filter(form=self.form_obj)
                .select_related('started_by')[:5]]
        return JsonResponse({'runs': runs, 'running': any(r['running'] for r in runs)})


class TaskMigrationReportView(SuperuserFormMixin, generic.View):
    def get(self, request, *args, **kwargs):
        run = CollectTaskMigrationRun.objects.filter(form=self.form_obj, pk=kwargs['run_id']).first()
        if not run or not run.report:
            raise Http404
        response = HttpResponse('﻿' + run.report, content_type='text/csv; charset=utf-8')
        stamp = timezone.localtime(run.started_at).strftime('%Y%m%d_%H%M%S')
        response['Content-Disposition'] = f'attachment; filename="cosocollect_{self.form_obj.pk}_taches_{stamp}.csv"'
        return response
