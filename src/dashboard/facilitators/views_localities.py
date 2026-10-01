import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from datetime import date

from django.db.models import F, Func, IntegerField, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.html import escape, format_html
from django.utils.translation import gettext, gettext_lazy
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
from .localities_history import (
    change_datetime, event_rows, facilitator_state, last_change_at, min_change_date, parse_change_date, presence_periods,
    record_facilitator_changes,
)

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
            # date du changement sur le terrain : aujourd'hui par défaut, pas avant le dernier changement enregistré
            'today': timezone.localdate().isoformat(),
            'change_date': timezone.localdate().isoformat(),
            'min_change_date': min_change_date(last_change_at(facilitator=self.facilitator)),
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
        last_changed_at = last_change_at(facilitator=self.facilitator)
        change_date, date_error = parse_change_date(request.POST.get('change_date'), last_changed_at)
        if date_error:
            change.errors.append(date_error)
        if 'confirm' not in request.POST or change.errors:
            # 1er temps (ou erreur) : aperçu comparé à l'état actuel, rien n'est enregistré.
            context = self.get_context_data(change=self._change())
            current = json.loads(context['selected'])
            context.update({
                'preview': change.summary(), 'errors': change.errors, 'warnings': change.warnings,
                'submitted': {section: json.dumps(value) if value is not None else None for section, value in zip(SECTIONS, submitted)},
                # le formulaire reste pré-rempli avec la saisie, pour l'ajuster avant de confirmer
                'selected': json.dumps({section: value if value is not None else current[section] for section, value in zip(SECTIONS, submitted)}),
                'change_date': change_date.isoformat() if change_date else request.POST.get('change_date', ''),
                'change_date_display': change_date.strftime('%d/%m/%Y') if change_date else None,
            })
            return self.render_to_response(context)

        if change.summary()['changed']:
            self._apply(change, change_datetime(change_date, last_changed_at))
        else:
            messages.info(request, gettext_lazy("No change to save."))
        return redirect('dashboard:facilitators:localities', pk=self.facilitator.pk)

    def _apply(self, change, changed_at):
        facilitator = self.facilitator
        session = self.request.session
        before = facilitator_state(facilitator)
        history = dict(changed_by=self.request.user, project_id=session.get('project_id'), changed_at=changed_at)

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


class LocalitiesHistoryMixin:
    """Filtres communs à la page « Trajets » et à ses données paginées : plusieurs choix possibles par filtre
    (personnes, types, sections, localités) et une période."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_view_localities_history(request.user):
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    @property
    def tree(self):
        if not hasattr(self, '_tree'):
            self._tree = AdministrativeTree()
        return self._tree

    def filters(self):
        params = self.request.GET

        def iso_date(value):
            try:
                return date.fromisoformat(value).isoformat() if value else ''
            except ValueError:
                return ''

        return {
            'persons': [v for v in params.getlist('person') if v[:2] in ('f-', 'u-') and v[2:].isdigit()],
            'kinds': [v for v in params.getlist('kind') if v in ('facilitator', 'user')],
            'sections': [v for v in params.getlist('section') if v in dict(LocalityHistory.SECTIONS)],
            'localities': [int(v) for v in params.getlist('locality') if str(v).isdigit() and int(v) in self.tree.levels],
            'date_from': iso_date(params.get('date_from')),
            'date_to': iso_date(params.get('date_to')),
        }

    def visible_events(self):
        events = LocalityHistory.objects.all()
        if not can_assign_user_localities(self.request.user):
            events = events.filter(facilitator__isnull=False)  # superviseurs : les facilitateurs seulement
        return events

    def person_filtered(self, filters):
        """Filtres personnes, types et sections (ni la période, ni la localité)."""
        events = self.visible_events()
        if filters['persons']:
            events = events.filter(
                Q(facilitator_id__in=[int(v[2:]) for v in filters['persons'] if v.startswith('f-')])
                | Q(user_id__in=[int(v[2:]) for v in filters['persons'] if v.startswith('u-')])
            )
        if len(filters['kinds']) == 1:
            events = events.filter(facilitator__isnull=filters['kinds'] == ['user'])
        if filters['sections']:
            events = events.filter(section__in=filters['sections'])
        return events

    def locality_villages(self, filters):
        return sorted({v for locality in filters['localities'] for v in self.tree.villages([locality])})

    @staticmethod
    def _contains_any(column):
        """Condition SQL : la liste JSON `column` contient l'un des villages passés en paramètre (PostgreSQL)."""
        table = LocalityHistory._meta.db_table
        return (f'EXISTS (SELECT 1 FROM jsonb_array_elements_text(COALESCE("{table}"."{column}", \'[]\'::jsonb)) AS e(v) '
                f'WHERE e.v = ANY(%s))')

    def filtered_events(self, filters):
        """Lignes du tableau : changements qui font arriver ou partir un village des localités choisies."""
        events = self.person_filtered(filters)
        if filters['date_from']:
            events = events.filter(changed_at__date__gte=filters['date_from'])
        if filters['date_to']:
            events = events.filter(changed_at__date__lte=filters['date_to'])
        if filters['localities']:
            villages = [str(v) for v in self.locality_villages(filters)]
            if not villages:
                return events.none()
            table = LocalityHistory._meta.db_table
            events = events.extra(
                where=[f'({self._contains_any("added")} OR {self._contains_any("removed")} '
                       f'OR ("{table}"."villages_before" IS NULL AND {self._contains_any("villages_after")}))'],
                params=[villages, villages, villages],
            )
        return events

    def presence_events(self, filters):
        """Chronologie utile aux périodes de présence : changements dont l'état avant ou après touche les localités."""
        villages = [str(v) for v in self.locality_villages(filters)]
        if not villages:
            return []
        return list(self.person_filtered(filters).extra(
            where=[f'({self._contains_any("villages_before")} OR {self._contains_any("villages_after")})'],
            params=[villages, villages],
        ))


class LocalitiesHistoryView(LocalitiesHistoryMixin, PageMixin, LoginRequiredMixin, generic.TemplateView):
    """Trajets : changements de localités des facilitateurs (et des utilisateurs pour qui peut attribuer
    leurs localités d'intervention), filtrables par personnes, types, sections, localités et période. Avec des
    localités : périodes de présence de chacun (arrivée, départ). Le tableau des changements est chargé page par
    page (LocalitiesHistoryDataView)."""
    template_name = 'facilitators/localities_history.html'
    title = gettext_lazy('Localities history')
    active_level1 = 'facilitators'
    active_level2 = 'localities_history'
    breadcrumb = [{'url': '', 'title': gettext_lazy('Localities history')}]

    def get_context_data(self, **kwargs):
        from django.contrib.auth.models import User

        context = super().get_context_data(**kwargs)
        filters = self.filters()
        can_see_users = can_assign_user_localities(self.request.user)

        persons = [(f"f-{pk}", f"{name or email} — {email}" if email else (name or str(pk)))
                   for pk, name, email in Facilitator.objects.filter(localities_history__isnull=False).distinct()
                   .values_list('id', 'name', 'email')]
        if can_see_users:
            persons += [(f"u-{pk}", f"{(last + ' ' + first).strip() or username} — {email}" if email else (last + ' ' + first).strip() or username)
                        for pk, last, first, username, email in User.objects.filter(localities_history__isnull=False).distinct()
                        .values_list('id', 'last_name', 'first_name', 'username', 'email')]

        periods = None
        if filters['localities']:
            periods = presence_periods(self.presence_events(filters), set(self.locality_villages(filters)))

        context.update({
            'filters': filters,
            'can_see_users': can_see_users,
            'persons_options': sorted(persons, key=lambda p: p[1].lower()),
            'sections': LocalityHistory.SECTIONS if can_see_users else LocalityHistory.SECTIONS[:3],
            'localities_options': self.tree.options(),
            'locality_label': ", ".join(self.tree.label(l) for l in filters['localities']),
            'periods': periods,
            'data_url': f"{reverse('dashboard:facilitators:localities_history_data')}?{self.request.GET.urlencode()}",
            'page_sizes': HISTORY_PAGE_SIZES,
        })
        return context


HISTORY_PAGE_SIZES = [10, 20, 50, 100, 500, 1000]


class LocalitiesHistoryDataView(LocalitiesHistoryMixin, LoginRequiredMixin, generic.View):
    """Données du tableau des changements de la page « Trajets », au format DataTables côté serveur : page
    demandée (`start`, `length`, -1 = tout), tri sur une colonne (par défaut la date, la plus récente d'abord)."""
    ORDER_FIELDS = ['changed_at', 'name', 'section', 'main_after', 'added_count', 'removed_count', 'changed_by_label']

    def get(self, request, *args, **kwargs):
        def number(name, default):
            try:
                return int(request.GET.get(name, default))
            except (TypeError, ValueError):
                return default

        filters = self.filters()
        events = self.filtered_events(filters)
        column = number('order[0][column]', 0)
        field = self.ORDER_FIELDS[column] if 0 <= column < len(self.ORDER_FIELDS) else 'changed_at'
        prefix = '' if request.GET.get('order[0][dir]') == 'asc' else '-'
        events = events.annotate(
            added_count=Func(F('added'), function='jsonb_array_length', output_field=IntegerField()),
            removed_count=Func(F('removed'), function='jsonb_array_length', output_field=IntegerField()),
        ).order_by(f'{prefix}{field}', f'{prefix}id').select_related('changed_by')

        start, length = max(number('start', 0), 0), number('length', HISTORY_PAGE_SIZES[1])
        page = events[start:] if length == -1 else events[start:start + max(length, 1)]
        can_edit = can_edit_localities(request.user)
        can_see_users = can_assign_user_localities(request.user)
        data = [history_cells(row, can_edit, can_see_users) for row in event_rows(self.tree, list(page))]
        return JsonResponse({
            'draw': number('draw', 0),
            'recordsTotal': self.visible_events().count(),
            'recordsFiltered': events.count(),
            'data': data,
        })


def history_cells(row, can_edit, can_see_users):
    """Cellules HTML d'une ligne du tableau des changements (mêmes informations que le trajet d'une personne)."""
    event = row['event']
    changed_at, created_at = timezone.localtime(event.changed_at), timezone.localtime(event.created_at)
    note = lambda text: format_html('<br><span class="localities-note">{}</span>', text)

    date_cell = format_html('{}{}', '≈ ' if event.approximate_date else '', changed_at.strftime('%d/%m/%Y'))
    if changed_at.date() == created_at.date():
        date_cell = format_html('{} {}', date_cell, changed_at.strftime('%H:%M'))
    else:
        date_cell = format_html('{}{}', date_cell, note(f"{gettext('recorded on')} {created_at.strftime('%d/%m/%Y %H:%M')}"))

    name = event.name or event.email or '-'
    if event.facilitator_id and can_edit:
        person = format_html('<a href="{}#localities-history" target="_blank">{}</a>',
                             reverse('dashboard:facilitators:localities', args=[event.facilitator_id]), name)
    elif event.user_id and can_see_users:
        person = format_html('<a href="{}#localities-history" target="_blank">{}</a>',
                             reverse('dashboard:authentication:user_localities', args=[event.user_id]), name)
    else:
        person = escape(name)
    person = format_html('{}{}', person, note(gettext('CDD facilitator') if event.facilitator_id else gettext('Dashboard user')))

    section = format_html('{}{}', event.get_section_display(), note(f"{row['after_count']} {gettext('village(s)')}"))
    main = format_html('{} → <b>{}</b>', row['main_before'], row['main_after']) if row['main_changed'] else escape(row['main_after'])

    added = format_html('<span class="badge badge-light border">{}</span> ', gettext('Initial state')) if row['first_definition'] else ''
    if row['whole_country']:
        added = format_html('{}{}', added, gettext('Whole country (TOGO)'))
    elif row['added_count']:
        added = format_html('{}+{} : {}', added, row['added_count'], row['added'])
    else:
        added = format_html('{}-', added)
    added = format_html('<span class="preview-added">{}</span>', added)
    removed = format_html('<span class="preview-removed">-{} : {}</span>', row['removed_count'], row['removed']) if row['removed_count'] else '-'
    by = format_html('{}{}', event.changed_by_label or '-', note(event.get_source_display()))
    return [str(date_cell), str(person), str(section), str(main), str(added), str(removed), str(by)]
