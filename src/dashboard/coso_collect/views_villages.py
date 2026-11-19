"""Onglet « Villages » de l'administration d'un formulaire COSOCollect : saisies dont le village n'existe plus
(identifiant absent de la base, nom changé, nom saisi au lieu d'un identifiant), villages proposés, et
correction de la valeur (cf. coso_collect/village_check.py).

Lecture : droit « Lire toutes les données » ; correction : droit « Modifier les saisies »."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _, ngettext
from django.views import generic

from coso_collect import village_check
from coso_collect.models import CollectSubmission

from .views import CollectPageMixin, FormAdminMixin

PAGE_SIZE = 50


def problem_labels():
    return {
        'unknown_id': _('Identifier no longer in the database'),
        'renamed': _('Name changed in the database'),
        'text': _('Name entered instead of an identifier'),
    }


class VillagesCheckView(CollectPageMixin, FormAdminMixin, generic.TemplateView):
    template_name = 'coso_collect/villages.html'
    required_right = 'view_data'

    def get_context_data(self, **kwargs):
        ctx = self.admin_context(super().get_context_data(**kwargs), 'villages')
        form, params = self.form_obj, self.request.GET
        geo = village_check.geo_fields(form.form or [])
        ctx['village_field'] = geo.get('village')
        if 'village' not in geo:
            return ctx
        qs = form.submissions.select_related('user', 'facilitator').order_by('-created_at')
        statuses = [s for s in params.getlist('status') if s in dict(CollectSubmission.STATUSES)]
        if statuses:
            qs = qs.filter(status__in=statuses)
        q = (params.get('q') or '').strip()
        if q:
            qs = qs.filter(title__icontains=q)
        issues = village_check.analyze(form, qs)
        labels = problem_labels()
        counts = {key: sum(1 for i in issues if i['problem'] == key) for key in labels}
        problem = params.get('problem') if params.get('problem') in labels else ''
        if problem:
            issues = [i for i in issues if i['problem'] == problem]
        for issue in issues:
            issue['problem_label'] = labels[issue['problem']]
        page = Paginator(issues, PAGE_SIZE).get_page(params.get('page'))
        query = params.copy()
        query.pop('page', None)
        ctx.update({
            'issues_page': page, 'issues_total': sum(counts.values()), 'problem_counts': counts,
            'problem_labels': labels, 'selected_problem': problem, 'statuses': CollectSubmission.STATUSES,
            'selected_statuses': statuses, 'q': q, 'query_string': query.urlencode(),
            'sure_count': sum(1 for i in issues if i['sure']),
            'other_geo_fields': [geo[k]['label'] for k in ('region', 'prefecture', 'commune', 'canton') if k in geo],
        })
        return ctx


class VillagesRelinkView(LoginRequiredMixin, FormAdminMixin, generic.View):
    """POST : lignes `row` (index) avec `uuid-<i>`, `value-<i>`, `village-<i>` ; `only` = une seule ligne ;
    `update_parents` = 1 pour réaligner région ... canton."""
    required_right = 'edit_data'

    def post(self, request, *args, **kwargs):
        form = self.form_obj
        post = request.POST
        only = post.get('only', '').strip()
        rows = [only] if only else post.getlist('pick')
        update_parents = post.get('update_parents') == '1'
        geography = village_check.Geography()
        done, errors = 0, []
        for idx in rows:
            line = int(idx) + 1 if str(idx).isdigit() else idx
            uuid, old_value = post.get(f'uuid-{idx}', ''), post.get(f'value-{idx}', '')
            village_id = village_check._as_id(post.get(f'village-{idx}'))
            if not village_id:
                errors.append(_('Line %(n)s: no village chosen.') % {'n': line})
                continue
            submission = CollectSubmission.objects.filter(form=form, uuid=uuid).first() if uuid else None
            if submission is None:
                errors.append(_('Line %(n)s: record not found.') % {'n': line})
                continue
            try:
                village_check.relink(submission, request.user, old_value, village_id, update_parents, geography)
                done += 1
            except village_check.RelinkError as exc:
                reason = {
                    'changed': _('the value was modified in the meantime, reload the page'),
                    'unknown_village': _('unknown village'),
                }.get(str(exc), str(exc))
                errors.append(_('Line %(n)s (%(title)s): %(reason)s.') % {
                    'n': line, 'title': submission.title or submission.uuid, 'reason': reason})
        if done:
            messages.success(request, ngettext('%(count)d record updated.', '%(count)d records updated.', done)
                             % {'count': done})
        for error in errors:
            messages.error(request, error)
        if not done and not errors:
            messages.warning(request, _('No line selected.'))
        default = reverse('dashboard:coso_collect:villages', args=[form.pk])
        next_url = post.get('next') or default
        if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            next_url = default
        return redirect(next_url)


class VillagesSearchView(LoginRequiredMixin, FormAdminMixin, generic.View):
    """Recherche d'un village par nom (liste de choix de la correction) : {results: [{id, text}]}."""
    required_right = 'edit_data'

    def get(self, request, *args, **kwargs):
        term = (request.GET.get('q') or '').strip()
        if len(village_check.norm(term)) < 2:
            return JsonResponse({'results': []})
        geography = village_check.Geography()
        ref = village_check.norm(term)
        scored = []
        for vid, name in geography.norm_names.items():
            if ref in name:
                score = 2.0 if name == ref else (1.5 if name.startswith(ref) else 1.0)
            else:
                score = village_check.similarity(term, name)
                if score < 0.75:
                    continue
            scored.append((-score, name, vid))
        scored.sort()
        results = [{'id': vid, 'text': f"{geography.levels[vid]['name']} — {geography.path_label(vid)}"}
                   for _score, _name, vid in scored[:30]]
        return JsonResponse({'results': results})

