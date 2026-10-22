"""Pages d'import Excel des facilitateurs et de leurs localités (cf. imports.py) : téléversement, aperçu, puis
confirmation."""
from io import BytesIO

from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext, gettext_lazy
from django.views import generic

from authentication.models import Facilitator
from authentication.permissions import AdminPermissionRequiredMixin
from cdd.call_objects_from_other_db import mis_objects_call
from dashboard.authentication.account_results import accounts_created_response
from dashboard.mixins import PageMixin
from no_sql_client import NoSQLClient
from process_manager.models import Cycle, Project
from subprojects.models import Project as MisProject

from . import imports
from .creation import create_facilitator
from .localities import AdministrativeTree, LocalitiesChange, can_edit_localities
from .localities_apply import apply_facilitator_localities
from .localities_notify import notify_localities_change

XLSX_CONTENT_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


class FacilitatorsFileForm(forms.Form):
    file = forms.FileField(label=gettext_lazy("Excel file (.xlsx)"))
    projects = forms.ModelMultipleChoiceField(
        label=gettext_lazy("Projects"), queryset=Project.objects.all(), widget=forms.CheckboxSelectMultiple, required=True,
    )


class AssignmentsFileForm(forms.Form):
    file = forms.FileField(label=gettext_lazy("Excel file (.xlsx)"))
    mode = forms.ChoiceField(label=gettext_lazy("Type of localities"), widget=forms.RadioSelect, choices=(
        (imports.MODE_INITIAL, gettext_lazy("Initial localities (assignment villages of the current project and cycle)")),
        (imports.MODE_STABILIZATION, gettext_lazy("Stabilization localities")),
    ))
    replace = forms.BooleanField(label=gettext_lazy(
        "Replace the current localities of each facilitator of the file (otherwise the villages of the file are added)"),
        required=False)


class ImportTemplateView(LoginRequiredMixin, generic.View):
    """Canevas Excel vide de l'import demandé."""

    def get(self, request, kind, *args, **kwargs):
        if kind == 'facilitators':
            workbook = imports.template_workbook(imports.FACILITATOR_COLUMNS)
            name = 'ac_list_canevas.xlsx'
        elif kind == 'assignments':
            workbook = imports.template_workbook(imports.ASSIGNMENT_COLUMNS)
            name = 'ac_affectation_villages.xlsx'
        else:
            raise Http404
        content = BytesIO()
        workbook.save(content)
        response = HttpResponse(content.getvalue(), content_type=XLSX_CONTENT_TYPE)
        response['Content-Disposition'] = f'attachment; filename="{name}"'
        return response


class FacilitatorsImportView(PageMixin, LoginRequiredMixin, AdminPermissionRequiredMixin, generic.TemplateView):
    """Création de comptes de facilitateurs depuis un fichier Excel : chaque ligne valide est créée comme par le
    formulaire « Créer un facilitateur » (identifiants générés et envoyés, compte MGP, mot de passe à changer)."""
    template_name = 'facilitators/import_facilitators.html'
    title = gettext_lazy('Import facilitators')
    active_level1 = 'facilitators'
    breadcrumb = [
        {'url': reverse_lazy('dashboard:facilitators:list'), 'title': gettext_lazy('Facilitators')},
        {'url': '', 'title': gettext_lazy('Import facilitators')},
    ]

    def default_projects(self):
        project_id = self.request.session.get('project_id')
        return Project.objects.filter(Q(id=project_id) | Q(parent_id=project_id), users__in=[self.request.user.id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault('form', FacilitatorsFileForm(initial={'projects': self.default_projects()}))
        context['template_url'] = reverse('dashboard:facilitators:import_template', args=['facilitators'])
        return context

    def post(self, request, *args, **kwargs):
        if 'payload' in request.POST:
            return self.confirm(request)
        form = FacilitatorsFileForm(request.POST, request.FILES)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        try:
            lines = imports.read_sheet(form.cleaned_data['file'], imports.FACILITATOR_COLUMNS, imports.MAX_FACILITATOR_ROWS)
        except imports.ImportFileError as exc:
            form.add_error('file', str(exc))
            return self.render_to_response(self.get_context_data(form=form))
        rows = imports.check_facilitator_rows(lines)
        valid = [row for row in rows if not row['errors']]
        projects = list(form.cleaned_data['projects'])
        return self.render_to_response(self.get_context_data(
            form=form, preview=rows, valid_count=len(valid), projects=projects,
            payload=imports.sign({'lines': lines, 'projects': [p.pk for p in projects]}) if valid else None,
        ))

    def confirm(self, request):
        payload = imports.unsign(request.POST.get('payload'))
        if payload is None:
            return self.render_to_response(self.get_context_data(
                expired=gettext("The preview has expired or has been modified: please upload the file again.")))
        session = request.session
        projects = list(Project.objects.filter(pk__in=payload['projects']))
        tree = AdministrativeTree()
        created, errors, reserved = [], [], set()
        # Tout est recontrôlé : un compte a pu être créé depuis l'aperçu.
        for row in imports.check_facilitator_rows([tuple(line) for line in payload['lines']]):
            if row['errors']:
                errors.append(gettext("Row %(line)s (%(name)s): %(errors)s") % {
                    'line': row['line'], 'name': f"{row['last_name']} {row['first_name']}".strip() or '-',
                    'errors': " ".join(row['errors'])})
                continue
            try:
                creation = create_facilitator(
                    last_name=row['last_name'], first_names=row['first_name'], email=row['email'], phone=row['phone'],
                    sex=row['sex'], facilitator_type=row['facilitator_type'], projects=projects, created_by=request.user,
                    project_id=session.get('project_id'), cycle_id=session.get('cycle_id'),
                    project_couch_id=session.get('project_couch_id'), project_name=session.get('project_name'),
                    tree=tree, reserved_usernames=reserved,
                )
            except Exception as exc:
                errors.append(gettext("Row %(line)s (%(name)s): %(errors)s") % {
                    'line': row['line'], 'name': f"{row['last_name']} {row['first_name']}", 'errors': exc})
                continue
            reserved.add(creation.username)
            created.append(creation.as_row())
        return accounts_created_response(
            request, created, reverse('dashboard:facilitators:list'), gettext('Import facilitators'),
            errors=errors, always_render=True,
            extra={'summary': gettext("%(n)s account(s) created.") % {'n': len(created)}},
        )


class AssignmentsImportView(PageMixin, LoginRequiredMixin, generic.TemplateView):
    """Localités initiales (villages d'affectation du projet et du cycle courants) ou de stabilisation de
    facilitateurs existants, depuis un fichier Excel : même calcul et mêmes droits que la page « Localités » de
    chaque facilitateur (réplication des initiales en stabilisation si elle est vide, envoi au MGP, mail)."""
    template_name = 'facilitators/import_assignments.html'
    title = gettext_lazy('Import localities')
    active_level1 = 'facilitators'
    breadcrumb = [
        {'url': reverse_lazy('dashboard:facilitators:list'), 'title': gettext_lazy('Facilitators')},
        {'url': '', 'title': gettext_lazy('Import localities')},
    ]

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_edit_localities(request.user):
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault('form', AssignmentsFileForm(initial={'mode': imports.MODE_INITIAL}))
        context['template_url'] = reverse('dashboard:facilitators:import_template', args=['assignments'])
        session = self.request.session
        context['project_name'] = session.get('project_name')
        cycle = Cycle.objects.filter(id=session.get('cycle_id')).first()
        context['cycle_name'] = cycle.name if cycle else None
        return context

    # -- calcul ----------------------------------------------------------------------------------

    def _context_objects(self):
        session = self.request.session
        return (
            Project.objects.get(id=session.get('project_id')), Cycle.objects.get(id=session.get('cycle_id')),
            mis_objects_call.filter_objects(MisProject, name=session.get('project_name')).first(),
        )

    @staticmethod
    def _doc(facilitator):
        try:
            facilitator_db = NoSQLClient().get_db(facilitator.no_sql_db_name)
            query_result = facilitator_db.get_query_result({"type": "facilitator"})[:]
            return facilitator_db, (facilitator_db[query_result[0]['_id']] if query_result else None)
        except Exception:
            return None, None

    def _change(self, tree, facilitator, villages, mode, replace, objects):
        """(LocalitiesChange, base CouchDB, document, erreurs) pour les villages du fichier de ce facilitateur."""
        facilitator_db, doc = self._doc(facilitator)
        project_cdd, cycle_cdd, project_mis = objects
        current = LocalitiesChange(tree, facilitator, doc, self.request.user, project_cdd, cycle_cdd, project_mis, None, None, None)
        submitted = imports.submitted_localities(mode, replace, villages, current)
        errors = []
        if mode == imports.MODE_INITIAL:
            change = LocalitiesChange(tree, facilitator, doc, self.request.user, project_cdd, cycle_cdd, project_mis, submitted, None, None)
            if not change.can_edit_assignment:
                errors.append(gettext("Assignment villages already filled in: only an administrator can modify them."))
        else:
            change = LocalitiesChange(tree, facilitator, doc, self.request.user, project_cdd, cycle_cdd, project_mis, None, submitted, None)
        return change, facilitator_db, doc, errors + change.errors

    @staticmethod
    def _section_summary(change, mode):
        summary = change.summary()
        return summary['assignment'] if mode == imports.MODE_INITIAL else summary['stabilization']

    def post(self, request, *args, **kwargs):
        if 'payload' in request.POST:
            return self.confirm(request)
        form = AssignmentsFileForm(request.POST, request.FILES)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        try:
            lines = imports.read_sheet(form.cleaned_data['file'], imports.ASSIGNMENT_COLUMNS, imports.MAX_ASSIGNMENT_ROWS)
        except imports.ImportFileError as exc:
            form.add_error('file', str(exc))
            return self.render_to_response(self.get_context_data(form=form))

        mode, replace = form.cleaned_data['mode'], form.cleaned_data['replace']
        tree = AdministrativeTree()
        by_facilitator, line_errors, line_warnings = imports.group_assignment_rows(
            lines, imports.LocalityIndex(tree), imports.FacilitatorIndex())
        objects = self._context_objects()
        preview, items = [], []
        for facilitator_id, entry in by_facilitator.items():
            facilitator = Facilitator.objects.get(pk=facilitator_id)
            change, _db, _doc, errors = self._change(tree, facilitator, entry['villages'], mode, replace, objects)
            summary = change.summary()
            preview.append({
                'facilitator': facilitator, 'roles': ", ".join(sorted(entry['roles'])), 'file_villages': len(entry['villages']),
                'lines': entry['lines'], 'section': self._section_summary(change, mode), 'summary': summary,
                'replicated': mode == imports.MODE_INITIAL and summary['copied_from_assignment'] and change.stabilization_changed,
                'warnings': change.warnings, 'errors': errors, 'changed': summary['changed'] and not errors,
            })
            if summary['changed'] and not errors:
                items.append({'facilitator': facilitator_id, 'villages': entry['villages']})
        return self.render_to_response(self.get_context_data(
            form=form, preview=preview, mode=mode, replace=replace, line_errors=line_errors, line_warnings=line_warnings,
            changed_count=len(items),
            payload=imports.sign({'mode': mode, 'replace': replace, 'items': items}) if items else None,
        ))

    def confirm(self, request):
        payload = imports.unsign(request.POST.get('payload'))
        if payload is None:
            return self.render_to_response(self.get_context_data(
                expired=gettext("The preview has expired or has been modified: please upload the file again.")))
        mode, replace = payload['mode'], payload['replace']
        session = request.session
        tree = AdministrativeTree()
        objects = self._context_objects()
        results = []
        for item in payload['items']:
            facilitator = Facilitator.objects.filter(pk=item['facilitator']).first()
            if facilitator is None:
                continue
            row = {'facilitator': facilitator, 'errors': [], 'grm': None, 'mail_sent': False, 'section': None}
            results.append(row)
            change, facilitator_db, doc, errors = self._change(tree, facilitator, item['villages'], mode, replace, objects)
            row['section'] = self._section_summary(change, mode)
            if errors:
                row['errors'] = errors
                continue
            if not change.summary()['changed']:
                row['unchanged'] = True
                continue
            history = dict(changed_by=request.user, project_id=session.get('project_id'))
            try:
                result = apply_facilitator_localities(
                    change, facilitator, facilitator_db, doc, session.get('project_id'), session.get('project_name'),
                    history, 'excel_import',
                )
            except Exception as exc:
                row['errors'] = [str(exc)]
                continue
            row['grm'] = result['grm']
            row['databases_error'] = result['databases_error']
            row['mail_sent'] = notify_localities_change(facilitator, result['events'], tree=tree)
        return self.render_to_response(self.get_context_data(results=results, mode=mode, replace=replace))
