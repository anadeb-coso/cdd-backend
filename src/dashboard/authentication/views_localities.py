import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy
from django.views import generic

import grm_client
from authentication.models import Facilitator, LocalityHistory, UserLocalities
from dashboard.facilitators.localities import (
    TOGO_ID, AdministrativeTree, UserLocalitiesChange, can_assign_localities_of, describe_user_zone,
    flag_sessions_for_zone_change, is_supervisor, supervisor_canton_ids, user_display_name,
)
from dashboard.facilitators.localities_history import event_rows, record_user_changes, user_state
from dashboard.mixins import PageMixin

SECTIONS = ('intervention', 'additional')


class UserLocalitiesView(PageMixin, LoginRequiredMixin, generic.TemplateView):
    """Localités d'intervention d'un utilisateur (superviseurs surtout) : 1er choix = niveau principal,
    TOGO = tout le pays. Aperçu comparé à l'état actuel, puis confirmation ; copie ensuite vers le compte
    GRM de même email. Un facilitateur est renvoyé vers la page « Localités » des facilitateurs."""
    template_name = 'authentication/localities.html'
    title = gettext_lazy('Intervention localities')
    active_level1 = 'users'
    breadcrumb = [
        {'url': reverse_lazy('dashboard:authentication:users'), 'title': gettext_lazy('Users')},
        {'url': '', 'title': gettext_lazy('Intervention localities')},
    ]

    account = None

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.account = get_object_or_404(User, pk=kwargs['id'])
            # un superviseur ne modifie que les localités des facilitateurs, et jamais sa propre zone
            if not can_assign_localities_of(request.user, self.account):
                raise Http404
            facilitator_filter = Q(user=self.account)
            if self.account.email:
                facilitator_filter |= Q(email__iexact=self.account.email)
            facilitator = Facilitator.objects.filter(facilitator_filter).first()
            if facilitator:
                return redirect('dashboard:facilitators:localities', pk=facilitator.pk)
        return super().dispatch(request, *args, **kwargs)

    @property
    def tree(self):
        if not hasattr(self, '_tree'):
            self._tree = AdministrativeTree()
        return self._tree

    def _record(self):
        return UserLocalities.objects.filter(user=self.account).select_related('updated_by').first()

    def _submitted(self):
        submitted = []
        for section in SECTIONS:
            raw = self.request.POST.get(f'{section}_ids')
            try:
                submitted.append(json.loads(raw) if raw is not None else None)
            except ValueError:
                submitted.append(None)
        return submitted

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        record = self._record()
        change = kwargs.get('change') or UserLocalitiesChange(self.tree, self.account, record)
        options = self.tree.options()
        context.update({
            'account': self.account,
            'account_name': user_display_name(self.account),
            'account_groups': sorted(group.name for group in self.account.groups.all()),
            'supervisor': is_supervisor(self.account),
            'record': record,
            'zone': describe_user_zone(self.tree, self.account, record),
            'intervention_options': [(int(TOGO_ID), self.tree.label_of(TOGO_ID))] + options,
            'localities_options': options,
            'sections': [
                ('intervention', gettext_lazy('Intervention localities')),
                ('intervention_additional', gettext_lazy('Additional intervention localities')),
            ],
            'selected': json.dumps({'intervention': change.old_choices, 'additional': change.old_additional_choices}),
            'current': {
                'intervention': change.diff(change.old_villages, change.old_villages),
                'additional': change.diff(change.old_additional, change.old_additional),
                'main': self.tree.label_of(change.old_main) if record else gettext_lazy("Not defined"),
            },
            'history': event_rows(self.tree, LocalityHistory.objects.filter(user=self.account).select_related('changed_by')),
        })
        return context

    def post(self, request, *args, **kwargs):
        submitted = self._submitted()
        record = self._record()
        change = UserLocalitiesChange(self.tree, self.account, record, *submitted)
        if 'confirm' not in request.POST or change.errors:
            context = self.get_context_data(change=UserLocalitiesChange(self.tree, self.account, record))
            current = json.loads(context['selected'])
            context.update({
                'preview': change.summary(), 'errors': change.errors, 'warnings': change.warnings,
                'submitted': {section: json.dumps(value) if value is not None else None for section, value in zip(SECTIONS, submitted)},
                'selected': json.dumps({section: value if value is not None else current[section] for section, value in zip(SECTIONS, submitted)}),
            })
            return self.render_to_response(context)

        if change.changed:
            self._apply(change, record)
        else:
            messages.info(request, gettext_lazy("No change to save."))
        return redirect('dashboard:authentication:user_localities', id=self.account.pk)

    def _apply(self, change, record):
        before = user_state(record)
        supervisor = is_supervisor(self.account)
        zone_before = supervisor_canton_ids(self.account) if supervisor else None
        if record is None:
            record = UserLocalities(user=self.account)
        record.administrative_id = change.new_main
        record.administrative_choices = change.new_choices
        record.village_ids = change.new_villages
        record.additional_administrative_choices = change.new_additional_choices
        record.additional_village_ids = change.new_additional
        record.updated_by = self.request.user
        record.save()
        record_user_changes(self.account, before, record, 'user_localities_page', changed_by=self.request.user)

        zone_after = supervisor_canton_ids(self.account) if supervisor else None
        if supervisor and (zone_before is None or set(zone_before) != set(zone_after or [])):
            # Zone changée : ses sessions ouvertes sont déconnectées à leur requête suivante (un superviseur ne
            # modifie jamais sa propre zone, cf. dispatch).
            flagged = flag_sessions_for_zone_change(self.account)
            if flagged:
                messages.info(self.request, gettext_lazy(
                    "%(n)s open session(s) of this supervisor will be logged out: the new zone applies at the next login."
                ) % {'n': flagged})

        if not self.account.email:
            messages.warning(self.request, gettext_lazy("Localities saved in CDD but not sent to the GRM (%s).") % gettext_lazy("no email"))
            return
        ok, detail = grm_client.update_localities_on_grm(
            self.account.email, change.new_main, change.new_choices, change.new_additional_choices,
        )
        if ok:
            messages.success(self.request, gettext_lazy("Localities saved and sent to the GRM."))
        else:
            messages.warning(self.request, gettext_lazy("Localities saved in CDD but not sent to the GRM (%s).") % detail)
