import json
import os
import time

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy
from django.views import generic
from storages.backends.s3boto3 import S3Boto3Storage

from dashboard.mixins import PageMixin
from dashboard.facilitators.views import FacilitatorMixin
from no_sql_client import NoSQLClient
from process_manager.models import Task

from dashboard.administrative_levels.views_adl import _derive_planning_task_status

from .functions import list_cvds_with_overview, resolve_task_doc, save_task_form


class TaskCycleHomeView(PageMixin, LoginRequiredMixin, generic.View):
    """Point d'entree du menu (URL sans id) : redirige vers la liste des CVD
    du facilitateur lie a l'utilisateur connecte (Facilitator.user, cf.
    ensure_facilitator_user). Pas de compte facilitateur lie -> etat vide."""
    active_level1 = 'task_cycle'

    def get(self, request, *args, **kwargs):
        facilitator = getattr(request.user, 'facilitator', None)
        if not facilitator or not facilitator.no_sql_db_name:
            return render(request, 'task_cycle/empty.html', {
                'title': gettext_lazy('Tasks (DCC cycle)'),
                'active_level1': self.active_level1,
            })
        return redirect('dashboard:task_cycle:cvd_list', id=facilitator.no_sql_db_name)


class TaskCycleCVDListView(FacilitatorMixin, PageMixin, LoginRequiredMixin, generic.TemplateView):
    """Liste des CVD (propres + stabilisation) avec diagnostic, pour le
    facilitateur `id` (no_sql_db_name) - meme mixin/plomberie que
    AdministrativeLevelDetailView (self.facilitator_db/self.cvds deja
    construits par FacilitatorMixin.dispatch)."""
    template_name = 'task_cycle/cvd_list.html'
    active_level1 = 'task_cycle'
    title = gettext_lazy('Tasks (DCC cycle)')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cvds = list_cvds_with_overview(
            self.request, self.facilitator_db, self.facilitator_db_name,
            self.cvds, self.no_sql_dbs_names_with_village_ids,
        )
        context['cvds'] = cvds
        # Affichage en 2 rangées horizontales scrollables (propres / stabilisation)
        # plutôt qu'une grille qui s'enroule -- évite qu'une longue liste ne
        # pousse le détail phases/activités/tâches trop bas sur la page.
        context['cvds_own'] = [e for e in cvds if not e['cvd'].get('stabilized')]
        context['cvds_stabilized'] = [e for e in cvds if e['cvd'].get('stabilized')]
        context['facilitator_db_name'] = self.facilitator_db_name
        return context


class TaskFormFetchView(LoginRequiredMixin, generic.View):
    """AJAX : schéma (Task.form) + réponses déjà saisies d'une tâche, pour
    initialiser le modal de remplissage (E1/E2 : task_cycle_fill_form.js).
    `id` = no_sql_db_name de la CVD actuellement sélectionnée sur la page
    (résolu par le client, cf. cvd_list.html) — pas forcément le facilitateur
    propriétaire réel si CVD de stabilisation, d'où le repli dans
    resolve_task_doc."""

    def get(self, request, *args, **kwargs):
        no_sql_db_name = kwargs['id']
        adl_id = request.GET.get('administrative_level')
        sql_id = request.GET.get('task')
        if not adl_id or not sql_id:
            return JsonResponse({'ok': False, 'message': 'missing params'}, status=400)
        try:
            task = Task.objects.get(id=int(sql_id))
        except (Task.DoesNotExist, ValueError, TypeError):
            return JsonResponse({'ok': False, 'message': 'task not found'}, status=404)

        nsc = NoSQLClient()
        db, doc, found_db_name = resolve_task_doc(nsc, request, no_sql_db_name, adl_id, sql_id)

        return JsonResponse({
            'ok': True,
            'form': task.form or [],
            'form_response': (doc or {}).get('form_response') or [],
            'attachments': task.attachments or [],
            'existing_attachments': (doc or {}).get('attachments') or [],
            'validated': (doc or {}).get('validated'),
            'task_name': task.name,
            'task_description': task.description or '',
            'task_completed': bool((doc or {}).get('completed')),
            'task_status': _derive_planning_task_status(doc),
            'cvd_name': (doc or {}).get('administrative_level_name') or '',
            'doc_id': (doc or {}).get('_id'),
            'found_db_name': found_db_name,
            'doc_found': doc is not None,
        })


class TaskFormSaveView(LoginRequiredMixin, generic.View):
    """AJAX (POST JSON) : sauvegarde du formulaire rempli, cf.
    dashboard.task_cycle.functions.save_task_form (E7)."""

    def post(self, request, *args, **kwargs):
        no_sql_db_name = kwargs['id']
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            return JsonResponse({'ok': False, 'message': 'invalid payload'}, status=400)

        adl_id = payload.get('administrative_level')
        sql_id = payload.get('task')
        values = payload.get('values')
        attachments = payload.get('attachments')
        if not adl_id or not sql_id or not isinstance(values, list):
            return JsonResponse({'ok': False, 'message': 'missing params'}, status=400)

        nsc = NoSQLClient()
        db, doc, found_db_name = resolve_task_doc(nsc, request, no_sql_db_name, adl_id, sql_id)
        if doc is None:
            return JsonResponse({'ok': False, 'message': 'no data found for this task/village yet'}, status=404)

        result = save_task_form(request, doc, db, found_db_name, values, attachments)
        return JsonResponse(result, status=200 if result['ok'] else 409)


class TaskAttachmentUploadView(LoginRequiredMixin, generic.View):
    """Upload d'une pièce jointe (E5) vers S3 — même schéma 2 lignes que
    attachments/views.py UploadIssueAttachmentAPIView (mobile), mais protégé
    par la session web (LoginRequiredMixin) plutôt qu'ouvert, et sous son
    propre préfixe S3 dédié (`task_form_attachments/<no_sql_db_name>/...`)."""

    def post(self, request, *args, **kwargs):
        f = request.FILES.get('file')
        if not f:
            return JsonResponse({'ok': False, 'message': 'no file'}, status=400)
        if f.size > settings.MAX_UPLOAD_SIZE:
            return JsonResponse({'ok': False, 'message': 'file too large'}, status=400)

        no_sql_db_name = kwargs['id']
        file_name = f"{int(time.time() * 1000)}-{f.name}"
        file_path = os.path.join('task_form_attachments', no_sql_db_name, file_name)

        storage = S3Boto3Storage()
        storage.save(file_path, f)
        url = storage.url(file_path)
        return JsonResponse({'ok': True, 'url': url, 'name': f.name})
