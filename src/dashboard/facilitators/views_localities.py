import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy
from django.views import generic

import grm_client
from authentication.models import Facilitator
from cdd.call_objects_from_other_db import mis_objects_call
from dashboard.mixins import PageMixin
from dashboard.utils import search_facilitators_db_with_villages_stabilized, sync_geographicalunits_with_cvd_on_facilittor
from no_sql_client import NoSQLClient
from process_manager.models import Cycle, Project
from subprojects.models import Project as MisProject

from authentication.models import LocalityHistory
from .localities import (
    AdministrativeTree, LocalitiesChange, apply_administrative_levels, can_assign_user_localities, can_edit_assignment,
    can_edit_localities, can_view_localities_history, schedule_administrative_levels_documents_moves,
)
from .localities_history import event_rows, facilitator_state, presence_periods, record_facilitator_changes

SECTIONS = ('assignment', 'stabilization', 'additional')


class FacilitatorLocalitiesView(PageMixin, LoginRequiredMixin, generic.TemplateView):
    """Villages d'affectation, de stabilisation (niveau principal = 1er choisi) et localités additionnelles
    d'un facilitateur. Enregistrement en deux temps : aperçu comparé à l'état actuel, puis confirmation.
    Les localités de stabilisation/additionnelles sont ensuite transmises au GRM."""
    template_name = 'facilitators/localities.html'
    title = gettext_lazy('Localities')
    active_level1 = 'facilitators'
    breadcrumb = [
        {'url': reverse_lazy('dashboard:facilitators:list'), 'title': gettext_lazy('Facilitators')},
        {'url': '', 'title': gettext_lazy('Localities')},
    ]

    facilitator = None
    facilitator_db = None
    doc = None

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            if not can_edit_localities(request.user):
                raise Http404
            self.facilitator = get_object_or_404(Facilitator, pk=kwargs['pk'])
            try:
                nsc = NoSQLClient()
                self.facilitator_db = nsc.get_db(self.facilitator.no_sql_db_name)
                query_result = self.facilitator_db.get_query_result({"type": "facilitator"})[:]
                self.doc = self.facilitator_db[query_result[0]['_id']] if query_result else None
            except Exception:
                self.facilitator_db, self.doc = None, None
        return super().dispatch(request, *args, **kwargs)

    # -- calcul ----------------------------------------------------------------------------------

    def _change(self, submitted=(None, None, None)):
        session = self.request.session
        return LocalitiesChange(
            self.tree, self.facilitator, self.doc, self.request.user,
            Project.objects.get(id=session.get('project_id')), Cycle.objects.get(id=session.get('cycle_id')),
            mis_objects_call.filter_objects(MisProject, name=session.get('project_name')).first(),
            *submitted,
        )

    @property
    def tree(self):
        if not hasattr(self, '_tree'):
            self._tree = AdministrativeTree()
        return self._tree

    def _submitted(self):
        """Listes ordonnées envoyées par le formulaire (None = section non modifiable ou non envoyée)."""
        submitted = []
        for section in SECTIONS:
            raw = self.request.POST.get(f'{section}_ids')
            try:
                submitted.append(json.loads(raw) if raw is not None else None)
            except ValueError:
                submitted.append(None)
        if not can_edit_assignment(self.request.user, self.facilitator, self.doc):
            submitted[0] = None
        return submitted

    # -- affichage -------------------------------------------------------------------------------

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        change = kwargs.get('change') or self._change()
        context.update({
            'sections': [
                ('assignment', gettext_lazy('Assignment villages')),
                ('stabilization', gettext_lazy('Stabilization villages')),
                ('additional', gettext_lazy('Additional villages')),
            ],
            'facilitator': self.facilitator,
            'can_edit_assignment': can_edit_assignment(self.request.user, self.facilitator, self.doc),
            'assignment_filled': bool(self.facilitator.administrative_levels or (self.doc and self.doc.get('administrative_levels'))),
            'assignment_options': self.tree.options(self.tree.ancestors_and_self(change.project_villages)),
            'localities_options': self.tree.options(),
            'selected': json.dumps({
                'assignment': change.old_assignment,
                'stabilization': change.old_stabilization_choices,
                'additional': change.old_additional_choices,
            }),
            'history': event_rows(self.tree, LocalityHistory.objects.filter(facilitator=self.facilitator).select_related('changed_by')),
            'current': {
                'assignment': change.diff(change.old_assignment, change.old_assignment),
                'stabilization': change.diff(change.old_stabilization, change.old_stabilization),
                'additional': change.diff(change.old_additional, change.old_additional),
                'main': self.tree.label_of(change.old_main),
            },
        })
        return context

    # -- enregistrement --------------------------------------------------------------------------

    def post(self, request, *args, **kwargs):
        submitted = self._submitted()
        change = self._change(submitted)
        if 'confirm' not in request.POST or change.errors:
            # 1er temps (ou erreur) : aperçu comparé à l'état actuel, rien n'est enregistré.
            context = self.get_context_data(change=self._change())
            current = json.loads(context['selected'])
            context.update({
                'preview': change.summary(), 'errors': change.errors, 'warnings': change.warnings,
                'submitted': {section: json.dumps(value) if value is not None else None for section, value in zip(SECTIONS, submitted)},
                # le formulaire reste pré-rempli avec la saisie, pour l'ajuster avant de confirmer
                'selected': json.dumps({section: value if value is not None else current[section] for section, value in zip(SECTIONS, submitted)}),
            })
            return self.render_to_response(context)

        if change.summary()['changed']:
            self._apply(change)
        else:
            messages.info(request, gettext_lazy("No change to save."))
        return redirect('dashboard:facilitators:localities', pk=self.facilitator.pk)

    def _apply(self, change):
        facilitator = self.facilitator
        session = self.request.session
        before = facilitator_state(facilitator)
        history = dict(changed_by=self.request.user, project_id=session.get('project_id'))

        if change.assignment_changed:
            _administrative_levels, administrative_levels_new, administrative_levels_remove = apply_administrative_levels(
                facilitator, change.old_levels, change.new_administrative_levels_elements(),
                change.project_cdd, change.cycle_cdd, change.project_mis.id if change.project_mis else 1,
                session.get('project_name'),
            )
            facilitator.administrative_levels = _administrative_levels
            facilitator.administrative_levels_ids = [int(_adl['id']) for _adl in _administrative_levels]
            facilitator.simple_save()
            if self.doc:
                # `update_doc_uncontrolled` : une liste vidée doit aussi l'être dans CouchDB.
                NoSQLClient().update_doc_uncontrolled(self.facilitator_db, self.doc['_id'], {"administrative_levels": _administrative_levels})
            schedule_administrative_levels_documents_moves(facilitator.no_sql_db_name, administrative_levels_new, administrative_levels_remove,
                                                           kept_administrative_levels=_administrative_levels)
            sync_geographicalunits_with_cvd_on_facilittor(
                session.get('project_id'), facilitator.develop_mode, facilitator.training_mode, facilitator.no_sql_db_name
            )
            record_facilitator_changes(facilitator, before, 'localities_page', sections=['assignment'], **history)

        if change.stabilization_changed:
            facilitator.main_administrative_id = change.new_main
            facilitator.stabilization_administrative_choices = change.new_stabilization_choices
            facilitator.stabilization_administrative_ids = change.new_stabilization
            facilitator.additional_administrative_choices = change.new_additional_choices
            facilitator.additional_administrative_ids = change.new_additional
            facilitator.simple_save()
            record_facilitator_changes(facilitator, before, 'localities_page', sections=['stabilization', 'additional'], **history)
            try:
                # Bases CouchDB des facilitateurs affectés à ces villages (même traitement que l'envoi du GRM).
                search_facilitators_db_with_villages_stabilized(session.get('project_name'), no_sql_db=facilitator.no_sql_db_name)
            except Exception as exc:
                messages.warning(self.request, gettext_lazy("Access to other facilitators' databases not updated: %s") % exc)

            ok, detail = grm_client.update_localities_on_grm(
                facilitator.email, change.new_main, change.new_stabilization_choices, change.new_additional_choices,
            )
            if ok:
                messages.success(self.request, gettext_lazy("Localities saved and sent to the GRM."))
            else:
                messages.warning(self.request, gettext_lazy("Localities saved in CDD but not sent to the GRM (%s).") % detail)
        else:
            messages.success(self.request, gettext_lazy("Localities saved."))


class LocalitiesHistoryView(PageMixin, LoginRequiredMixin, generic.TemplateView):
    """Trajets : changements de localités des facilitateurs (et des utilisateurs pour qui peut attribuer
    leurs localités d'intervention), filtrables par personne, section, localité et période. Avec une
    localité : périodes de présence de chacun dans cette localité (arrivée, départ)."""
    template_name = 'facilitators/localities_history.html'
    title = gettext_lazy('Localities history')
    active_level1 = 'facilitators'
    active_level2 = 'localities_history'
    breadcrumb = [{'url': '', 'title': gettext_lazy('Localities history')}]
    max_rows = 500

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_view_localities_history(request.user):
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tree = AdministrativeTree()
        params = self.request.GET
        q = (params.get('q') or '').strip()
        kind = params.get('kind') or ''
        section = params.get('section') or ''
        locality = params.get('locality') or ''
        date_from, date_to = params.get('date_from') or '', params.get('date_to') or ''
        can_see_users = can_assign_user_localities(self.request.user)

        events = LocalityHistory.objects.select_related('changed_by')
        if not can_see_users or kind == 'facilitator':
            events = events.filter(facilitator__isnull=False)
        elif kind == 'user':
            events = events.filter(facilitator__isnull=True)
        if q:
            events = events.filter(Q(name__icontains=q) | Q(email__icontains=q))
        if section:
            events = events.filter(section=section)

        periods, locality_label = None, None
        if locality.isdigit() and int(locality) in tree.levels:
            village_ids = set(tree.villages([int(locality)]))
            locality_label = tree.label(int(locality))
            # présences : toute la chronologie des personnes filtrées (sans la période)
            periods = presence_periods(list(events), village_ids)
            events = [
                e for e in events
                if village_ids & (set(e.added or []) | set(e.removed or []))
                or (e.villages_before is None and village_ids & set(e.villages_after or []))
            ]
        else:
            events = list(events)
        if date_from:
            events = [e for e in events if e.changed_at.date().isoformat() >= date_from]
        if date_to:
            events = [e for e in events if e.changed_at.date().isoformat() <= date_to]

        context.update({
            'filters': {'q': q, 'kind': kind, 'section': section, 'locality': locality, 'date_from': date_from, 'date_to': date_to},
            'can_see_users': can_see_users,
            'can_edit_localities': can_edit_localities(self.request.user),
            'sections': LocalityHistory.SECTIONS if can_see_users else LocalityHistory.SECTIONS[:3],
            'localities_options': tree.options(),
            'locality_label': locality_label,
            'periods': periods,
            'total': len(events),
            'history': event_rows(tree, events[:self.max_rows]),
            'max_rows': self.max_rows,
        })
        return context
