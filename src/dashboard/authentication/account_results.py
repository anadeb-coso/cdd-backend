"""Retour d'une création de compte(s) (utilisateur, facilitateur, import Excel de facilitateurs)."""
from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.cache import add_never_cache_headers
from django.utils.translation import gettext as _


def mgp_label(row):
    status = row.get('mgp_status')
    if status == 'created':
        return _("MGP account created")
    if status == 'exists':
        return _("An MGP account already existed with this e-mail address: left unchanged")
    if status == 'error':
        return _("MGP account not created (%(detail)s)") % {'detail': row.get('mgp_detail') or '-'}
    return ''


def accounts_created_response(request, rows, back_url, title, errors=None, extra=None, always_render=False):
    """Mail des identifiants parti pour chaque compte (et rien d'autre à montrer) : messages puis retour à
    `back_url`. Sinon page récapitulative, qui affiche une seule fois les identifiants non envoyés (jamais mise
    en cache)."""
    if rows and not errors and not always_render and all(row['mail_sent'] for row in rows):
        for row in rows:
            messages.success(request, _("Account of %(name)s created: login details sent to %(email)s.") % row)
            label = mgp_label(row)
            if row.get('mgp_status') == 'error':
                messages.warning(request, label)
            elif label:
                messages.info(request, label)
        return redirect(back_url)

    for row in rows:
        row['mgp_label'] = mgp_label(row)
    context = {
        'title': title,
        'breadcrumb': [{'url': back_url, 'title': title}],
        'rows': rows,
        'errors': errors or [],
        'back_url': back_url,
        'passwords_shown': any(row.get('password') for row in rows),
    }
    context.update(extra or {})
    response = render(request, 'authentication/accounts_created.html', context)
    add_never_cache_headers(response)
    return response
