"""Menu « COSOCollect » du Web DCC : création / publication des formulaires (web uniquement), saisie web,
et, pour les administrateurs d'un formulaire, résumé, données, galerie, carte et exports."""
import json
import re
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Max, Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _, gettext_lazy
from django.views import generic

from coso_collect import access, exports, stats
from coso_collect.api_views import attachment_payload, serve_attachment
from coso_collect.display import build_tree, cell_value, table_columns
from coso_collect.fields import geopoint_values, leaf_fields
from coso_collect.form_files import export_json, export_xlsform, import_form_file
from coso_collect.models import CollectAttachment, CollectForm, CollectFormAdmin, CollectSubmission
from coso_collect.services import (
    CollectError, admin_update_submission, bump_version, discard_stored_file, has_own_submission,
    save_submission, set_submission_editable, store_attachment, submission_payload,
)
from coso_collect.titles import normalize_template, parse_iso
from dashboard.mixins import PageMixin
from dashboard.process_manager.tasks.form_design import (
    ADMIN_LEVEL_TYPES, DATASOURCE_OPS, choices_to_xlsx, list_datasources, query_datasource,
    read_sheet_table, validate_form_design, xlsx_to_choices,
)

from .forms import AddFormAdminForm, CollectFormCreateForm, CollectFormSettingsForm, ImportFormFileForm

XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def attachment_url(attachment_id):
    return reverse('dashboard:coso_collect:attachment', args=[attachment_id])


def _json_body(request):
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except (ValueError, UnicodeDecodeError):
        return None


def _filename(text, ext):
    base = re.sub(r'[^A-Za-z0-9_-]+', '_', text or 'formulaire').strip('_')[:60] or 'formulaire'
    return f'{base}.{ext}'


def _download(content, filename, content_type):
    response = HttpResponse(content, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _has_fields(pages):
    return bool(leaf_fields(pages, include_notes=True))


def generic_path(field_path):
    """Chemin concret d'une valeur ("$0.membres.2.photo") -> chemin du champ ("$0.membres.photo")."""
    return re.sub(r'\.\d+(?=\.)', '', field_path or '')


def _field_path_regex(path):
    """Expression régulière des chemins concrets d'un champ (index de ligne des répétables admis)."""
    head, _, rest = (path or '').partition('.')
    pattern = '^' + re.escape(head)
    for segment in rest.split('.') if rest else []:
        pattern += r'\.' + re.escape(segment) + r'(\.\d+)?'
    return pattern + '$'


# ---------------------------------------------------------------------------------------------- mixins
class CollectPageMixin(PageMixin, LoginRequiredMixin):
    active_level1 = 'coso_collect'
    title = gettext_lazy('COSOCollect')


def admin_home_url(form, rights):
    """Page d'arrivée d'un administrateur sur un formulaire, selon ses droits."""
    return reverse(f'dashboard:coso_collect:{rights.first_tab()}', args=[form.pk])


class FormAdminMixin:
    """Formulaire `pk`, réservé à ses administrateurs ; `required_right` : droit exigé en plus
    (cf. CollectFormAdmin.RIGHTS), None = tout administrateur du formulaire."""
    required_right = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        self.form_obj = get_object_or_404(CollectForm, pk=kwargs['pk'])
        self.rights = access.form_rights(request.user, self.form_obj)
        if not self.rights.is_admin or not self.has_required_right():
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def has_required_right(self):
        return self.required_right is None or self.rights.has(self.required_right)

    def admin_context(self, ctx, tab):
        form = self.form_obj
        ctx.update({
            'collect_form': form,
            'rights': self.rights,
            'tab': tab,
            'title': _('COSOCollect'),
            'submissions_count': form.submissions.count(),
            'has_own_record': form.single_submission and has_own_submission(self.request.user, form),
            'breadcrumb': [
                {'url': reverse('dashboard:coso_collect:list'), 'title': _('COSOCollect')},
                {'url': '', 'title': form.title},
            ],
        })
        return ctx

    def submissions(self):
        return self.form_obj.submissions.all()


class FormAccessMixin:
    """Formulaire `pk` que l'utilisateur peut remplir / consulter (publié ou clôturé)."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        self.form_obj = get_object_or_404(CollectForm, pk=kwargs['pk'])
        if not access.can_access_form(request.user, self.form_obj):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


# ------------------------------------------------------------------------------------------ liste / création
class FormListView(CollectPageMixin, generic.TemplateView):
    template_name = 'coso_collect/list.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        fillable = list(access.fillable_forms(user).order_by('-published_at', '-updated_at'))
        counts = {}
        for row in (access.own_submissions(user).filter(form__in=fillable)
                    .values('form_id', 'status').annotate(n=Count('pk'))):
            counts.setdefault(row['form_id'], {})[row['status']] = row['n']
        for form in fillable:
            form.my_counts = counts.get(form.pk, {})
            form.my_total = sum(form.my_counts.values())
        administered = list(
            access.administered_forms(user)
            .annotate(n_submissions=Count('submissions', distinct=True),
                      last_submission=Max('submissions__updated_at'))
            .select_related('created_by').order_by('-updated_at')
        )
        rights = access.rights_by_form(user, administered)
        for form in administered:
            form.rights = rights[form.pk]
            form.admin_url = admin_home_url(form, form.rights)
        ctx.update({
            'breadcrumb': [{'url': '', 'title': _('COSOCollect')}],
            'fillable_forms': fillable,
            'administered_forms': administered,
            'can_create': access.can_create_forms(user),
            'create_form': CollectFormCreateForm(),
            'import_form': ImportFormFileForm(),
        })
        return ctx


class FormCreateView(LoginRequiredMixin, generic.View):
    def post(self, request, *args, **kwargs):
        if not access.can_create_forms(request.user):
            raise PermissionDenied
        form = CollectFormCreateForm(request.POST)
        if not form.is_valid():
            messages.error(request, _('The title is required.'))
            return redirect('dashboard:coso_collect:list')
        obj = form.save(commit=False)
        obj.created_by = request.user
        obj.form = []
        obj.save()
        return redirect('dashboard:coso_collect:builder', pk=obj.pk)


class FormImportCreateView(LoginRequiredMixin, generic.View):
    """Nouveau formulaire depuis un fichier (.xlsx XLSForm ou .json COSOCollect)."""

    def post(self, request, *args, **kwargs):
        if not access.can_create_forms(request.user):
            raise PermissionDenied
        uploaded = request.FILES.get('file')
        if not uploaded:
            messages.error(request, _('No file.'))
            return redirect('dashboard:coso_collect:list')
        result = import_form_file(uploaded)
        if not result.get('form') and result.get('errors'):
            messages.error(request, ' '.join(result['errors']))
            return redirect('dashboard:coso_collect:list')
        title = result.get('title') or re.sub(r'\.(xlsx|json)$', '', uploaded.name, flags=re.I)
        obj = CollectForm.objects.create(
            title=title[:255], description=result.get('description') or '', form=result.get('form') or [],
            title_template=result.get('title_template') or {}, created_by=request.user,
            single_submission=bool(result.get('single_submission')),
        )
        if result.get('errors'):
            messages.warning(request, _('Partial import: ') + ' '.join(result['errors']))
        else:
            messages.success(request, _('Form imported. Review it, then publish it.'))
        return redirect('dashboard:coso_collect:builder', pk=obj.pk)


# ----------------------------------------------------------------------------------------------- builder
class BuilderView(CollectPageMixin, FormAdminMixin, generic.TemplateView):
    template_name = 'coso_collect/builder.html'
    required_right = 'edit_form'

    def get_context_data(self, **kwargs):
        ctx = self.admin_context(super().get_context_data(**kwargs), 'builder')
        ctx['form_json'] = self.form_obj.form or []
        ctx['title_template_json'] = normalize_template(self.form_obj.title_template)
        return ctx


class BuilderSaveView(LoginRequiredMixin, FormAdminMixin, generic.View):
    """Enregistre la structure (`form`) et le titre combiné (`title_template`) envoyés par le builder."""
    required_right = 'edit_form'

    def post(self, request, *args, **kwargs):
        form = self.form_obj
        payload = _json_body(request)
        if payload is None:
            return JsonResponse({'ok': False, 'errors': [_('Invalid JSON.')]}, status=400)
        pages = payload.get('form', [])
        clean, errors = validate_form_design(pages)
        if errors:
            return JsonResponse({'ok': False, 'errors': errors}, status=422)
        clean = clean or []
        if form.status != CollectForm.STATUS_DRAFT and not _has_fields(clean):
            return JsonResponse({'ok': False, 'errors': [_('A published form must keep at least one field.')]},
                                status=422)
        template = normalize_template(payload.get('title_template'), clean)
        changed = clean != (form.form or []) or template != normalize_template(form.title_template)
        form.form = clean
        form.title_template = template
        if changed:
            bump_version(form)
        form.save()
        return JsonResponse({'ok': True, 'version': form.version, 'title_template': template,
                             'status': form.status})


class BuilderImportView(LoginRequiredMixin, FormAdminMixin, generic.View):
    """Fichier .xlsx / .json -> structure renvoyée au builder (rien n'est enregistré)."""
    required_right = 'edit_form'

    def post(self, request, *args, **kwargs):
        uploaded = request.FILES.get('file')
        if not uploaded:
            return JsonResponse({'ok': False, 'errors': [_('No file.')]}, status=400)
        result = import_form_file(uploaded)
        return JsonResponse({
            'ok': not result.get('errors'), 'form': result.get('form'),
            'title_template': result.get('title_template'), 'errors': result.get('errors') or [],
        })


class FormFileExportView(LoginRequiredMixin, FormAdminMixin, generic.View):
    """Fichier du formulaire (structure, sans données) : qui le modifie ou qui exporte."""

    def has_required_right(self):
        return self.rights.has('edit_form') or self.rights.has('export')

    def get(self, request, *args, **kwargs):
        form = self.form_obj
        if kwargs['fmt'] == 'json':
            return _download(export_json(form), _filename(form.title, 'json'), 'application/json')
        return _download(export_xlsform(form), _filename(form.title, 'xlsx'), XLSX_MIME)


class BuilderChoicesExportView(LoginRequiredMixin, FormAdminMixin, generic.View):
    required_right = 'edit_form'

    def post(self, request, *args, **kwargs):
        payload = _json_body(request) or {}
        return _download(choices_to_xlsx(payload.get('choices') or []), 'choix.xlsx', XLSX_MIME)


class BuilderChoicesImportView(LoginRequiredMixin, FormAdminMixin, generic.View):
    required_right = 'edit_form'

    def post(self, request, *args, **kwargs):
        uploaded = request.FILES.get('file')
        if not uploaded:
            return JsonResponse({'ok': False, 'errors': [_('No file.')]}, status=400)
        try:
            choices = xlsx_to_choices(uploaded)
        except Exception as exc:  # noqa: BLE001 - message utilisateur
            return JsonResponse({'ok': False, 'errors': [str(exc)]}, status=422)
        return JsonResponse({'ok': True, 'choices': choices})


class BuilderDataSourcesView(LoginRequiredMixin, FormAdminMixin, generic.View):
    required_right = 'edit_form'

    def get(self, request, *args, **kwargs):
        return JsonResponse({'ok': True, 'tables': list_datasources(), 'admin_levels': ADMIN_LEVEL_TYPES,
                             'ops': list(DATASOURCE_OPS.keys())})


class BuilderDataSourcePreviewView(LoginRequiredMixin, FormAdminMixin, generic.View):
    required_right = 'edit_form'

    def post(self, request, *args, **kwargs):
        spec = _json_body(request)
        if spec is None:
            return JsonResponse({'ok': False, 'errors': [_('Invalid JSON.')]}, status=400)
        try:
            rows, truncated = query_datasource(spec)
        except Exception as exc:  # noqa: BLE001 - message utilisateur
            return JsonResponse({'ok': False, 'errors': [str(exc)]}, status=422)
        return JsonResponse({'ok': True, 'rows': rows, 'count': len(rows), 'truncated': truncated})


class BuilderDatasetSheetView(LoginRequiredMixin, FormAdminMixin, generic.View):
    required_right = 'edit_form'

    def post(self, request, *args, **kwargs):
        uploaded = request.FILES.get('file')
        if not uploaded:
            return JsonResponse({'ok': False, 'errors': [_('No file.')]}, status=400)
        try:
            columns, rows = read_sheet_table(uploaded)
        except Exception as exc:  # noqa: BLE001 - message utilisateur
            return JsonResponse({'ok': False, 'errors': [str(exc)]}, status=422)
        return JsonResponse({'ok': True, 'columns': columns, 'rows': rows, 'count': len(rows)})


# ------------------------------------------------------------------------------------ paramètres / statut
class SettingsView(CollectPageMixin, FormAdminMixin, generic.FormView):
    template_name = 'coso_collect/settings.html'
    form_class = CollectFormSettingsForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.form_obj
        return kwargs

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if not self.rights.has('edit_form'):  # page ouverte à tout administrateur : lecture seule
            for field in form.fields.values():
                field.disabled = True
        return form

    def post(self, request, *args, **kwargs):
        if not self.rights.has('edit_form'):
            raise PermissionDenied
        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = self.admin_context(super().get_context_data(**kwargs), 'settings')
        ctx['right_choices'] = CollectFormAdmin.RIGHTS
        ctx['my_rights'] = [label for code, label in CollectFormAdmin.RIGHTS if self.rights.has(code)]
        if self.rights.manage_admins:
            rows = list(self.form_obj.admin_rights.select_related('user'))
            for row in rows:
                row.cells = [{'code': code, 'label': label, 'on': row.has(code)}
                             for code, label in CollectFormAdmin.RIGHTS]
            ctx['admin_rows'] = rows
            ctx['add_admin_form'] = AddFormAdminForm(self.form_obj)
            ctx['right_requires'] = access.RIGHT_REQUIRES
        return ctx

    def form_valid(self, form):
        form.save()
        messages.success(self.request, _('Settings saved.'))
        return redirect('dashboard:coso_collect:settings', pk=self.form_obj.pk)


def _next_url(request, default):
    url = request.POST.get('next') or ''
    if url and url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()},
                                               require_https=request.is_secure()):
        return url
    return default


class StatusView(LoginRequiredMixin, FormAdminMixin, generic.View):
    """Publier / clôturer / rouvrir la collecte / repasser en brouillon, chacun selon son droit."""
    # action -> (statuts de départ admis, droit exigé)
    ACTIONS = {
        'publish': ((CollectForm.STATUS_DRAFT,), 'publish'),
        'unpublish': ((CollectForm.STATUS_PUBLISHED,), 'publish'),
        'close': ((CollectForm.STATUS_PUBLISHED,), 'close'),
        'reopen': ((CollectForm.STATUS_CLOSED,), 'reopen_form'),
    }

    def post(self, request, *args, **kwargs):
        form = self.form_obj
        back = _next_url(request, reverse('dashboard:coso_collect:settings', args=[form.pk]))
        action = request.POST.get('action')
        if action == 'publish' and form.status == CollectForm.STATUS_CLOSED:
            action = 'reopen'  # ancien libellé du bouton « Rouvrir la collecte »
        statuses, right = self.ACTIONS.get(action, ((), None))
        if form.status not in statuses or (action == 'unpublish' and form.submissions.exists()):
            messages.error(request, _('Action not allowed.'))
            return redirect(back)
        if not self.rights.has(right):
            messages.error(request, _('You do not have this right on this form.'))
            return redirect(back)
        now = timezone.now()
        if action in ('publish', 'reopen'):
            clean, errors = validate_form_design(form.form or [])
            if errors or not _has_fields(clean or []):
                messages.error(request, _('The form must contain at least one valid field before being published.'))
                return redirect('dashboard:coso_collect:builder' if self.rights.has('edit_form')
                                else 'dashboard:coso_collect:settings', pk=form.pk)
            form.status = CollectForm.STATUS_PUBLISHED
            form.published_at = form.published_at or now
            form.closed_at = None
            messages.success(request, _('Form published: users can now load and fill it in.') if action == 'publish'
                             else _('Collection reopened: users can send data again.'))
        elif action == 'close':
            form.status = CollectForm.STATUS_CLOSED
            form.closed_at = now
            messages.success(request, _('Form closed: users can no longer send data.'))
        else:
            form.status = CollectForm.STATUS_DRAFT
            messages.success(request, _('Form back to draft.'))
        form.save()
        return redirect(back)


class FormAdminsView(LoginRequiredMixin, FormAdminMixin, generic.View):
    """Créateur / superutilisateur : ajouter ou retirer un administrateur, enregistrer les droits de chacun."""

    def has_required_right(self):
        return self.rights.manage_admins

    def post(self, request, *args, **kwargs):
        form = self.form_obj
        back = reverse('dashboard:coso_collect:settings', args=[form.pk]) + '#cc-admins'
        action = request.POST.get('action')
        if action == 'add':
            add_form = AddFormAdminForm(form, request.POST)
            if not add_form.is_valid():
                messages.error(request, _('Choose a user who is not yet an administrator of this form.'))
                return redirect(back)
            user = add_form.cleaned_data['user']
            CollectFormAdmin.objects.create(form=form, user=user)  # lecture des données seule, par défaut
            messages.success(request, _('%(name)s is now an administrator of this form: tick the rights to grant.')
                             % {'name': user.get_full_name() or user.username})
        elif action == 'remove':
            try:
                user_id = int(request.POST.get('user') or 0)
            except ValueError:
                user_id = 0
            if form.admin_rights.filter(user_id=user_id).delete()[0]:
                messages.success(request, _('Administrator removed.'))
        elif action == 'rights':
            # Seules les lignes affichées sont mises à jour (un administrateur ajouté entre-temps garde ses droits).
            shown = {int(v) for v in request.POST.getlist('admins') if v.isdigit()}
            for row in form.admin_rights.filter(user_id__in=shown):
                codes = access.normalize_rights(request.POST.getlist(f'rights_{row.user_id}'))
                for code in access.RIGHT_CODES:
                    setattr(row, f'can_{code}', code in codes)
                row.save()
            messages.success(request, _('Rights saved.'))
        else:
            messages.error(request, _('Action not allowed.'))
        return redirect(back)


class FormDeleteView(LoginRequiredMixin, FormAdminMixin, generic.View):
    required_right = 'delete_form'

    def post(self, request, *args, **kwargs):
        form = self.form_obj
        if request.POST.get('confirm_title', '').strip() != form.title.strip():
            messages.error(request, _('Type the exact title of the form to confirm the deletion.'))
            return redirect('dashboard:coso_collect:settings', pk=form.pk)
        for attachment in form.attachments.all():
            discard_stored_file(attachment.file)
        form.delete()
        messages.success(request, _('Form deleted.'))
        return redirect('dashboard:coso_collect:list')


# ------------------------------------------------------------------------------------------ saisie web
class MySubmissionsView(CollectPageMixin, FormAccessMixin, generic.TemplateView):
    template_name = 'coso_collect/my_submissions.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        form = self.form_obj
        qs = access.own_submissions(self.request.user, form).select_related('user', 'facilitator')
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(title__icontains=q)
        status = self.request.GET.get('status')
        if status in dict(CollectSubmission.STATUSES):
            qs = qs.filter(status=status)
        page = Paginator(qs.order_by('-created_at'), 25).get_page(self.request.GET.get('page'))
        params = self.request.GET.copy()
        params.pop('page', None)
        rights = access.form_rights(self.request.user, form)
        ctx.update({
            'collect_form': form, 'page_obj': page, 'q': q, 'status': status, 'query_string': params.urlencode(),
            'statuses': CollectSubmission.STATUSES, 'title': form.title,
            'admin_url': admin_home_url(form, rights) if rights.is_admin else '',
            'has_own_record': form.single_submission and has_own_submission(self.request.user, form),
            'breadcrumb': [
                {'url': reverse('dashboard:coso_collect:list'), 'title': _('COSOCollect')},
                {'url': '', 'title': form.title},
                {'url': '', 'title': _('My records')},
            ],
        })
        return ctx


def _fill_context(request, form, submission=None, admin_edit=False):
    """Contexte de fill.html. `admin_edit` : un administrateur (droit `edit_data`) corrige la saisie d'un
    autre — enregistrement et envois de fichiers par les routes « admin- », statut et auteur conservés."""
    initial = submission.data if submission else []
    sub_uuid = str(submission.uuid if submission else uuid.uuid4())
    if admin_edit:
        parent = {'url': reverse('dashboard:coso_collect:data', args=[form.pk]), 'title': form.title}
        save_url = reverse('dashboard:coso_collect:admin_save', args=[sub_uuid])
        edit_url = reverse('dashboard:coso_collect:admin_edit', args=[sub_uuid])
        upload_url = reverse('dashboard:coso_collect:admin_upload', args=[sub_uuid])
    else:
        parent = {'url': reverse('dashboard:coso_collect:my_submissions', args=[form.pk]), 'title': form.title}
        save_url = reverse('dashboard:coso_collect:save', args=[sub_uuid])
        edit_url = reverse('dashboard:coso_collect:edit', args=[sub_uuid])
        upload_url = reverse('dashboard:coso_collect:upload', args=[form.pk])
    return {
        'collect_form': form,
        'submission': submission,
        'submission_uuid': sub_uuid,
        'admin_edit': admin_edit,
        'save_url': save_url,
        'edit_url': edit_url,
        'upload_url': upload_url,
        'form_json': form.form or [],
        'initial_json': initial,
        'created_at': submission.started_at_local if submission else '',
        'title': form.title,
        'breadcrumb': [
            {'url': reverse('dashboard:coso_collect:list'), 'title': _('COSOCollect')},
            parent,
            {'url': '', 'title': submission.title if submission else _('New record')},
        ],
    }


class FillView(CollectPageMixin, FormAccessMixin, generic.TemplateView):
    """Nouvelle saisie web — ou, pour un formulaire à un seul enregistrement par personne, celui qu'on a déjà."""
    template_name = 'coso_collect/fill.html'

    def get(self, request, *args, **kwargs):
        form = self.form_obj
        if form.status != CollectForm.STATUS_PUBLISHED:
            messages.warning(request, form.close_message or _('This form is closed: no more data can be sent.'))
            return redirect('dashboard:coso_collect:my_submissions', pk=form.pk)
        if form.single_submission:
            existing = access.own_submissions(request.user, form).order_by('-created_at').first()
            if existing:
                messages.info(request, _('This form accepts only one record per person: here is yours.'))
                if existing.is_locked:
                    return redirect('dashboard:coso_collect:submission', uuid=existing.uuid)
                return redirect('dashboard:coso_collect:edit', uuid=existing.uuid)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_fill_context(self.request, self.form_obj))
        return ctx


class EditSubmissionView(CollectPageMixin, generic.TemplateView):
    template_name = 'coso_collect/fill.html'

    def get(self, request, *args, **kwargs):
        self.submission = get_object_or_404(CollectSubmission.objects.select_related('form'), uuid=kwargs['uuid'])
        form = self.submission.form
        if not access.owns_submission(request.user, self.submission):
            raise PermissionDenied
        if form.status != CollectForm.STATUS_PUBLISHED:
            messages.warning(request, form.close_message or _('This form is closed: no more data can be sent.'))
            return redirect('dashboard:coso_collect:submission', uuid=self.submission.uuid)
        if self.submission.is_locked:
            messages.warning(request, _('This record has already been sent and can no longer be modified.'))
            return redirect('dashboard:coso_collect:submission', uuid=self.submission.uuid)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_fill_context(self.request, self.submission.form, self.submission))
        return ctx


class SubmissionSaveView(LoginRequiredMixin, generic.View):
    """POST JSON {form_id, status, data, created_at} : crée / met à jour la saisie `uuid`."""

    def post(self, request, *args, **kwargs):
        payload = _json_body(request)
        if payload is None:
            return JsonResponse({'ok': False, 'message': _('Invalid JSON.')}, status=400)
        form = get_object_or_404(CollectForm, pk=payload.get('form_id') or 0)
        payload['uuid'] = str(kwargs['uuid'])
        try:
            submission = save_submission(form, request.user, payload, CollectSubmission.SOURCE_WEB)
        except CollectError as exc:
            return JsonResponse({'ok': False, 'code': exc.code, 'message': exc.message}, status=409)
        return JsonResponse({
            'ok': True, 'submission': submission_payload(submission),
            'redirect': reverse('dashboard:coso_collect:submission', args=[submission.uuid]),
        })


class UploadView(LoginRequiredMixin, generic.View):
    def post(self, request, *args, **kwargs):
        form = get_object_or_404(CollectForm, pk=kwargs['pk'])
        uploaded = request.FILES.get('file')
        if not uploaded:
            return JsonResponse({'ok': False, 'message': _('No file.')}, status=400)
        if uploaded.size > settings.MAX_UPLOAD_SIZE:
            return JsonResponse({'ok': False, 'message': _('File too large.')}, status=400)
        try:
            attachment = store_attachment(form, request.user, uploaded, request.POST.get('submission_uuid'),
                                          request.POST.get('field_path'))
        except CollectError as exc:
            return JsonResponse({'ok': False, 'code': exc.code, 'message': exc.message}, status=409)
        payload = attachment_payload(attachment)
        payload['url'] = attachment_url(attachment.pk)
        return JsonResponse({'ok': True, 'attachment': payload})


class SubmissionDataAdminMixin:
    """Saisie `uuid` d'un formulaire dont l'utilisateur a le droit `edit_data`."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        self.submission = get_object_or_404(CollectSubmission.objects.select_related('form'), uuid=kwargs['uuid'])
        if not access.has_right(request.user, self.submission.form, 'edit_data'):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class AdminEditSubmissionView(CollectPageMixin, SubmissionDataAdminMixin, generic.TemplateView):
    """Administrateur : corriger les données d'une saisie (même envoyée, verrouillée ou formulaire clôturé)."""
    template_name = 'coso_collect/fill.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_fill_context(self.request, self.submission.form, self.submission, admin_edit=True))
        return ctx


class AdminSaveSubmissionView(LoginRequiredMixin, SubmissionDataAdminMixin, generic.View):
    """POST JSON {data} : nouvelles données de la saisie ; auteur, statut et dates d'envoi inchangés."""

    def post(self, request, *args, **kwargs):
        payload = _json_body(request)
        if payload is None:
            return JsonResponse({'ok': False, 'message': _('Invalid JSON.')}, status=400)
        try:
            submission = admin_update_submission(self.submission, request.user, payload.get('data'))
        except CollectError as exc:
            return JsonResponse({'ok': False, 'code': exc.code, 'message': exc.message}, status=409)
        return JsonResponse({
            'ok': True, 'submission': submission_payload(submission),
            'redirect': reverse('dashboard:coso_collect:submission', args=[submission.uuid]),
        })


class AdminUploadView(LoginRequiredMixin, SubmissionDataAdminMixin, generic.View):
    def post(self, request, *args, **kwargs):
        uploaded = request.FILES.get('file')
        if not uploaded:
            return JsonResponse({'ok': False, 'message': _('No file.')}, status=400)
        if uploaded.size > settings.MAX_UPLOAD_SIZE:
            return JsonResponse({'ok': False, 'message': _('File too large.')}, status=400)
        try:
            attachment = store_attachment(self.submission.form, request.user, uploaded, self.submission.uuid,
                                          request.POST.get('field_path'), as_admin=True)
        except CollectError as exc:
            return JsonResponse({'ok': False, 'code': exc.code, 'message': exc.message}, status=409)
        payload = attachment_payload(attachment)
        payload['url'] = attachment_url(attachment.pk)
        return JsonResponse({'ok': True, 'attachment': payload})


class AttachmentView(LoginRequiredMixin, generic.View):
    def get(self, request, *args, **kwargs):
        attachment = get_object_or_404(CollectAttachment.objects.select_related('form', 'submission'), pk=kwargs['aid'])
        if not access.can_view_attachment(request.user, attachment):
            raise PermissionDenied
        response = serve_attachment(attachment)
        if request.GET.get('download') and isinstance(response, FileResponse):
            response['Content-Disposition'] = 'attachment; filename="{}"'.format(attachment.name.replace('"', ''))
        return response


HISTORY_LABELS = {
    'created': gettext_lazy('Created'),
    'updated': gettext_lazy('Modified'),
    'submitted': gettext_lazy('Sent'),
    'reopened': gettext_lazy('Reopened for modification'),
    'locked': gettext_lazy('Locked again'),
    'edited_by_admin': gettext_lazy('Data corrected by an administrator'),
}


def _history_display(history):
    out = []
    for entry in reversed(history or []):
        if not isinstance(entry, dict):
            continue
        at = parse_iso(entry.get('at'))
        out.append(dict(entry, label=HISTORY_LABELS.get(entry.get('action'), entry.get('action')),
                        at_display=timezone.localtime(at).strftime('%d/%m/%Y %H:%M') if at else ''))
    return out


class SubmissionDetailView(CollectPageMixin, generic.TemplateView):
    template_name = 'coso_collect/submission_detail.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        submission = get_object_or_404(
            CollectSubmission.objects.select_related('form', 'user', 'facilitator', 'reopened_by'),
            uuid=kwargs['uuid'],
        )
        if not access.can_view_submission(self.request.user, submission):
            raise PermissionDenied
        form = submission.form
        rights = access.form_rights(self.request.user, form)
        is_owner = access.owns_submission(self.request.user, submission)
        back = (reverse('dashboard:coso_collect:data', args=[form.pk]) if rights.has('view_data') and not is_owner
                else reverse('dashboard:coso_collect:my_submissions', args=[form.pk]))
        ctx.update({
            'submission': submission,
            'collect_form': form,
            'pages': build_tree(form.form, submission.data, attachment_url),
            'rights': rights,
            'is_owner': is_owner,
            'can_edit': is_owner and not submission.is_locked and form.status == CollectForm.STATUS_PUBLISHED,
            'title': _('COSOCollect'),
            'history': _history_display(submission.history),
            'breadcrumb': [
                {'url': reverse('dashboard:coso_collect:list'), 'title': _('COSOCollect')},
                {'url': back, 'title': form.title},
                {'url': '', 'title': submission.title},
            ],
        })
        return ctx


class SubmissionEditableView(LoginRequiredMixin, generic.View):
    """Administrateur : rouvrir la modification d'une saisie envoyée (ou la reverrouiller)."""

    def post(self, request, *args, **kwargs):
        submission = get_object_or_404(CollectSubmission.objects.select_related('form'), uuid=kwargs['uuid'])
        if not access.has_right(request.user, submission.form, 'reopen_records'):
            raise PermissionDenied
        editable = request.POST.get('editable') == '1'
        set_submission_editable(submission, request.user, editable)
        messages.success(request, _('Modification reopened for the author.') if editable else _('Record locked.'))
        return redirect(_next_url(request, reverse('dashboard:coso_collect:submission', args=[submission.uuid])))


class SubmissionDeleteView(LoginRequiredMixin, generic.View):
    def post(self, request, *args, **kwargs):
        submission = get_object_or_404(CollectSubmission.objects.select_related('form'), uuid=kwargs['uuid'])
        form = submission.form
        if not access.has_right(request.user, form, 'delete_records'):
            raise PermissionDenied
        for attachment in submission.attachments.all():
            discard_stored_file(attachment.file)
        submission.delete()
        messages.success(request, _('Record deleted.'))
        return redirect(_next_url(request, reverse('dashboard:coso_collect:data', args=[form.pk])))


# ------------------------------------------------------------------------------- administration : données
def filtered_submissions(form, params):
    qs = form.submissions.select_related('user', 'facilitator')
    q = (params.get('q') or '').strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(facilitator__name__icontains=q) | Q(facilitator__username__icontains=q)
                       | Q(user__username__icontains=q) | Q(user__first_name__icontains=q)
                       | Q(user__last_name__icontains=q))
    statuses = [s for s in (params.getlist('status') if hasattr(params, 'getlist') else params.get('status') or [])
                if s in dict(CollectSubmission.STATUSES)]
    if statuses:
        qs = qs.filter(status__in=statuses)
    source = params.get('source')
    if source in dict(CollectSubmission.SOURCES):
        qs = qs.filter(source=source)
    date_from, date_to = params.get('date_from'), params.get('date_to')
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    if params.get('editable') == '1':
        qs = qs.filter(editable=True)
    return qs


class DataView(CollectPageMixin, FormAdminMixin, generic.TemplateView):
    template_name = 'coso_collect/data.html'
    required_right = 'view_data'

    def get_context_data(self, **kwargs):
        ctx = self.admin_context(super().get_context_data(**kwargs), 'data')
        form = self.form_obj
        qs = filtered_submissions(form, self.request.GET)
        sort = self.request.GET.get('sort') or '-created_at'
        if sort.lstrip('-') not in ('created_at', 'submitted_at', 'title', 'status', 'updated_at'):
            sort = '-created_at'
        try:
            per_page = min(max(int(self.request.GET.get('per_page') or 25), 10), 200)
        except ValueError:
            per_page = 25
        page = Paginator(qs.order_by(sort, '-pk'), per_page).get_page(self.request.GET.get('page'))
        columns = table_columns(form.form)
        rows = [{'submission': s, 'cells': [cell_value(c, s.data) for c in columns]} for s in page.object_list]
        params = self.request.GET.copy()
        params.pop('page', None)
        sort_params = params.copy()
        sort_params.pop('sort', None)
        ctx.update({
            'page_obj': page, 'rows': rows, 'columns': columns, 'sort': sort, 'per_page': per_page,
            'sort_query': sort_params.urlencode(),
            'statuses': CollectSubmission.STATUSES, 'sources': CollectSubmission.SOURCES,
            'selected_statuses': self.request.GET.getlist('status'), 'filters': self.request.GET,
            'query_string': params.urlencode(), 'filtered_count': page.paginator.count,
        })
        return ctx


class SummaryView(CollectPageMixin, FormAdminMixin, generic.TemplateView):
    template_name = 'coso_collect/summary.html'
    required_right = 'view_data'

    def get_context_data(self, **kwargs):
        ctx = self.admin_context(super().get_context_data(**kwargs), 'summary')
        form = self.form_obj
        days = stats.pick_range(self.request.GET.get('days'))
        scope = self.request.GET.get('scope') or 'all'
        qs = self.submissions()
        report_qs = qs.filter(status=CollectSubmission.STATUS_SUBMITTED) if scope == 'submitted' else qs
        ctx.update({
            'overview': stats.overview(form, qs),
            'days': days, 'ranges': stats.RANGES, 'scope': scope,
            'charts': {
                'timeline': stats.timeline(qs, days),
                'by_author': stats.by_author(qs),
                'by_source': stats.by_source(qs),
                'by_status': {
                    'labels': [str(label) for _k, label in CollectSubmission.STATUSES],
                    'values': [qs.filter(status=k).count() for k, _l in CollectSubmission.STATUSES],
                },
                'questions': stats.question_reports(form, report_qs),
            },
        })
        return ctx


class GalleryView(CollectPageMixin, FormAdminMixin, generic.TemplateView):
    template_name = 'coso_collect/gallery.html'
    required_right = 'view_data'

    def attachments(self):
        qs = (self.form_obj.attachments.filter(submission__isnull=False)
              .select_related('submission').order_by('-created_at'))
        field = self.request.GET.get('field')
        if field:
            qs = qs.filter(field_path__regex=_field_path_regex(field))
        kind = self.request.GET.get('kind')
        if kind == 'images':
            qs = qs.filter(mime_type__startswith='image/')
        elif kind == 'documents':
            qs = qs.exclude(mime_type__startswith='image/')
        q = (self.request.GET.get('q') or '').strip()
        if q:
            qs = qs.filter(Q(submission__title__icontains=q) | Q(name__icontains=q))
        return qs

    def get(self, request, *args, **kwargs):
        if request.GET.get('download') == 'zip':
            if not self.rights.has('export'):
                raise PermissionDenied
            archive = exports.zip_attachments(self.attachments())
            return FileResponse(archive, as_attachment=True, filename=_filename(self.form_obj.title + '_fichiers', 'zip'))
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = self.admin_context(super().get_context_data(**kwargs), 'gallery')
        media_fields = [f for f in leaf_fields(self.form_obj.form) if f['type'] in ('photo', 'file')]
        page = Paginator(self.attachments(), 48).get_page(self.request.GET.get('page'))
        labels = {f['path']: f['label'] for f in media_fields}
        for attachment in page.object_list:
            attachment.field_label = labels.get(generic_path(attachment.field_path), attachment.field_path)
            attachment.url = attachment_url(attachment.pk)
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx.update({'page_obj': page, 'media_fields': media_fields, 'filters': self.request.GET,
                    'query_string': params.urlencode()})
        return ctx


class MapView(CollectPageMixin, FormAdminMixin, generic.TemplateView):
    template_name = 'coso_collect/map.html'
    required_right = 'view_data'

    def get_context_data(self, **kwargs):
        ctx = self.admin_context(super().get_context_data(**kwargs), 'map')
        form = self.form_obj
        geo_fields = [f for f in leaf_fields(form.form) if f['type'] == 'geopoint']
        statuses = self.request.GET.getlist('status')
        qs = filtered_submissions(form, self.request.GET)
        points = []
        for submission in qs:
            for path, field, value in geopoint_values(submission.data, form.form):
                points.append({
                    'lat': value['latitude'], 'lng': value['longitude'], 'title': submission.title,
                    'status': submission.status, 'author': submission.author_name, 'field': field['label'],
                    'field_path': field['path'], 'accuracy': value.get('accuracy'),
                    'date': timezone.localtime(submission.created_at).strftime('%d/%m/%Y %H:%M'),
                    'url': reverse('dashboard:coso_collect:submission', args=[submission.uuid]),
                })
        ctx.update({
            'geo_fields': geo_fields, 'points': points, 'statuses': CollectSubmission.STATUSES,
            'selected_statuses': statuses, 'filters': self.request.GET,
            'mapbox_token': settings.MAPBOX_ACCESS_TOKEN,
            'map_center': {'lat': settings.DIAGNOSTIC_MAP_LATITUDE, 'lng': settings.DIAGNOSTIC_MAP_LONGITUDE,
                           'zoom': settings.DIAGNOSTIC_MAP_ZOOM},
        })
        return ctx


class ExportView(CollectPageMixin, FormAdminMixin, generic.TemplateView):
    template_name = 'coso_collect/export.html'
    required_right = 'export'

    def get(self, request, *args, **kwargs):
        fmt = request.GET.get('download')
        if fmt:
            return self.download(fmt)
        return super().get(request, *args, **kwargs)

    def download(self, fmt):
        form = self.form_obj
        params = self.request.GET
        qs = filtered_submissions(form, params).order_by('created_at')
        options = exports.normalize_options(params)
        absolute = lambda aid: self.request.build_absolute_uri(attachment_url(aid))  # noqa: E731
        stamp = timezone.localtime().strftime('%Y%m%d_%H%M%S')
        name = f'{form.title}_{stamp}'
        if fmt == 'xlsx':
            return _download(exports.to_xlsx(form, qs, options, absolute), _filename(name, 'xlsx'), XLSX_MIME)
        if fmt == 'csv':
            return _download(exports.to_csv(form, qs, options, absolute), _filename(name, 'csv'),
                             'text/csv; charset=utf-8')
        if fmt == 'geojson':
            rows = ((s, path, field, value) for s in qs for path, field, value in geopoint_values(s.data, form.form))
            return _download(exports.to_geojson(form, qs, rows), _filename(name, 'geojson'), 'application/geo+json')
        if fmt == 'zip':
            attachments = CollectAttachment.objects.filter(submission__in=qs).select_related('submission')
            return FileResponse(exports.zip_attachments(attachments), as_attachment=True,
                                filename=_filename(name + '_fichiers', 'zip'))
        raise Http404

    def get_context_data(self, **kwargs):
        ctx = self.admin_context(super().get_context_data(**kwargs), 'export')
        ctx.update({'statuses': CollectSubmission.STATUSES, 'sources': CollectSubmission.SOURCES,
                    'has_geopoint': any(f['type'] == 'geopoint' for f in leaf_fields(self.form_obj.form)),
                    'has_media': any(f['type'] in ('photo', 'file') for f in leaf_fields(self.form_obj.form))})
        return ctx
