"""Page « Comptes de formation » (superutilisateurs) : liste des comptes training_mode du projet de la session,
avec accès à leur profil et à leurs localités, et création de nouveaux comptes (cf. training.py).

Ces comptes n'apparaissent pas dans la liste des FC, qui ne montre que les facilitateurs ayant une affectation
active dans le SIG — réservée aux vrais FC."""
from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from django.utils.translation import gettext as _, gettext_lazy
from django.views import generic

from authentication.models import Facilitator
from dashboard.mixins import PageMixin
from process_manager.models import Cycle, Project

from . import training


class TrainingAccountsForm(forms.Form):
    count = forms.IntegerField(min_value=1, max_value=training.MAX_ACCOUNTS, initial=1)
    start = forms.IntegerField(min_value=1)
    password = forms.CharField(min_length=4, max_length=128, initial=training.DEFAULT_PASSWORD)
    headquarters = forms.TypedMultipleChoiceField(coerce=int, choices=())
    sync_tasks = forms.BooleanField(required=False, initial=True)

    def __init__(self, *args, headquarters_choices=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['headquarters'].choices = headquarters_choices
        self.fields['headquarters'].error_messages['required'] = _('Choose at least one CVD headquarters village.')

    def clean(self):
        data = super().clean()
        if data.get('start') and data.get('count'):
            taken = list(Facilitator.objects.filter(username__in=training.usernames(data['start'], data['count']))
                         .values_list('username', flat=True))
            if taken:
                self.add_error('start', _('These usernames already exist: %(names)s') % {'names': ', '.join(sorted(taken))})
        return data


class TrainingAccountsView(PageMixin, LoginRequiredMixin, UserPassesTestMixin, generic.TemplateView):
    template_name = 'facilitators/training_accounts.html'
    title = gettext_lazy('Training accounts')
    active_level1 = 'facilitators'
    active_level2 = 'training_accounts'

    def test_func(self):
        return self.request.user.is_superuser

    def project_cycle(self):
        project = Project.objects.filter(id=self.request.session.get('project_id')).first()
        cycle = Cycle.objects.filter(id=self.request.session.get('cycle_id'), project=project).first() if project else None
        return project, cycle

    def get_context_data(self, form=None, **kwargs):
        ctx = super().get_context_data(**kwargs)
        project, cycle = self.project_cycle()
        choices = training.headquarters_choices(project) if project else []
        if form is None:
            default_hq = [hq for hq, _label in choices if hq == 3805][:1]   # SANFATOUTE CENTRE, comme la fonction
            form = TrainingAccountsForm(headquarters_choices=choices, initial={
                'start': training.next_number(), 'headquarters': default_hq})
        accounts = list(Facilitator.objects.filter(training_mode=True, projects=project).order_by('id')) if project else []
        sig = training.sig_assignments_count(accounts)
        for f in accounts:
            f.hq_names = [x.get('name') for x in (f.administrative_levels or [])
                          if isinstance(x, dict) and x.get('is_headquarters_village') and x.get('project_id') == project.couch_id]
            f.village_count = len({str(x.get('id')) for x in (f.administrative_levels or [])
                                   if isinstance(x, dict) and x.get('project_id') == project.couch_id})
            f.sig_rows = sig.get(f.id, 0)
        ctx.update({
            'form': form, 'project': project, 'cycle': cycle, 'accounts': accounts,
            'sig_violations': sum(1 for f in accounts if f.sig_rows),
            'max_accounts': training.MAX_ACCOUNTS,
            'breadcrumb': [{'url': '', 'title': _('Training accounts')}],
        })
        return ctx

    def post(self, request, *args, **kwargs):
        project, cycle = self.project_cycle()
        if not project or not cycle:
            messages.error(request, _('Select a project and a cycle first.'))
            return redirect('dashboard:facilitators:training_accounts')
        form = TrainingAccountsForm(request.POST, headquarters_choices=training.headquarters_choices(project))
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        d = form.cleaned_data
        try:
            created = training.create_training_accounts(project, cycle, d['start'], d['count'], d['password'],
                                                        d['headquarters'])
        except Exception as exc:  # noqa: BLE001 - les comptes déjà créés sont gardés, le message le dit
            messages.error(request, _('Creation stopped: %(error)s') % {'error': exc})
            return redirect('dashboard:facilitators:training_accounts')
        names = ', '.join(f.username for f in created)
        messages.success(request, _('%(n)s training account(s) created: %(names)s — password: %(password)s') % {
            'n': len(created), 'names': names, 'password': d['password']})
        if d['sync_tasks'] and created:
            from dashboard.process_manager.tasks.views import _run_sync_tasks_in_thread
            _run_sync_tasks_in_thread(project_id=project.id, cycle_id=cycle.id, develop_mode=False, training_mode=True,
                                      no_sql_dbs=[f.no_sql_db_name for f in created])
            messages.info(request, _('The tasks of the cycle are being created in these accounts (in the background, '
                                     'a few minutes).'))
        return redirect('dashboard:facilitators:training_accounts')
