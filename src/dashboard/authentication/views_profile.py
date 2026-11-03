"""Profil d'un utilisateur (page de consultation pour les administrateurs) et réinitialisation de son mot de passe
(nouveau mot de passe généré, envoyé par e-mail, à changer à la connexion suivante)."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy
from django.views import generic

from authentication.accounts import (
    generate_password, password_change_required, person_accounts, require_password_change, send_account_credentials,
    set_person_password,
)
from authentication.mgp_accounts import create_account_on_mgp, linked_facilitator, mgp_account_exists
from authentication.models import LocalityHistory, PasswordChangeRequirement, UserLocalities
from authentication.permissions import AdminPermissionRequiredMixin
from dashboard.facilitators.localities import AdministrativeTree, describe_user_zone, is_supervisor, user_display_name
from dashboard.mixins import PageMixin


def can_manage_account(request_user, account):
    """Un administrateur ne gère pas un superutilisateur (sauf s'il l'est lui-même) ; jamais son propre compte ici
    (page Profil personnelle pour cela : la réinitialisation le déconnecterait)."""
    if account.pk == request_user.pk:
        return False
    return request_user.is_superuser or not account.is_superuser


class UserProfileView(PageMixin, LoginRequiredMixin, AdminPermissionRequiredMixin, generic.TemplateView):
    template_name = 'authentication/user_profile.html'
    title = gettext_lazy('User profile')
    active_level1 = 'users'
    breadcrumb = [
        {'url': reverse_lazy('dashboard:authentication:users'), 'title': gettext_lazy('Users')},
        {'url': '', 'title': gettext_lazy('User profile')},
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        account = get_object_or_404(User, pk=self.kwargs['id'])
        facilitator = linked_facilitator(account)
        record = UserLocalities.objects.filter(user=account).select_related('updated_by').first()
        person = person_accounts(account=account)
        last_requirement = PasswordChangeRequirement.objects.filter(user=account).order_by('-id').first()
        context.update({
            'account': account,
            'account_name': user_display_name(account),
            'groups': sorted(account.groups.values_list('name', flat=True)),
            'projects': list(account.projects.all()),
            'facilitator': facilitator,
            'supervisor': is_supervisor(account),
            'zone': None if facilitator else describe_user_zone(AdministrativeTree(), account, record),
            'localities_record': record,
            'mgp_account': mgp_account_exists(account.email),
            'password_change_pending': password_change_required(person=person) if person.exists else False,
            'last_requirement': last_requirement,
            'localities_events': LocalityHistory.objects.filter(user=account).count(),
            'can_manage': can_manage_account(self.request.user, account),
        })
        return context


class UserAccountActionView(LoginRequiredMixin, AdminPermissionRequiredMixin, generic.View):
    """Actions du profil (POST) : `reset_password` ou `create_mgp`."""

    def post(self, request, *args, **kwargs):
        account = get_object_or_404(User, pk=kwargs['id'])
        if not can_manage_account(request.user, account):
            raise Http404
        action = request.POST.get('action')
        if action == 'reset_password':
            self._reset_password(account)
        elif action == 'create_mgp':
            status, detail = create_account_on_mgp(account)
            if status == 'created':
                messages.success(request, gettext_lazy("MGP account created"))
            elif status == 'exists':
                messages.info(request, gettext_lazy("An MGP account already existed with this e-mail address: left unchanged"))
            elif status == 'error':
                messages.warning(request, gettext_lazy("MGP account not created (%(detail)s)") % {'detail': detail})
            else:
                messages.warning(request, gettext_lazy("No e-mail address: no MGP account can be created."))
        return redirect('dashboard:authentication:user_profile', id=account.pk)

    def _reset_password(self, account):
        request = self.request
        if not (account.email or '').strip():
            messages.error(request, gettext_lazy("This user has no e-mail address: the new password cannot be sent."))
            return
        password = generate_password()
        person = person_accounts(account=account)
        if not person.exists:  # compte inactif : seul ce compte
            from authentication.accounts import Person
            person = Person([account], [])
        # Même mot de passe sur tous les comptes de la personne (DCC web/SIG, facilitateur, MGP)...
        result = set_person_password(person, password, 'password_reset')
        # ... et à changer à la connexion suivante, comme un mot de passe initial.
        require_password_change(email=account.email, user=account, facilitator=linked_facilitator(account), created_by=request.user)

        mgp_note = None
        if result['mgp'] is None and mgp_account_exists(account.email) is False:
            status, _detail = create_account_on_mgp(account)  # compte MGP absent : créé avec la nouvelle empreinte
            mgp_note = gettext_lazy("MGP account created") if status == 'created' else None
        elif result['mgp'] is False:
            messages.warning(request, gettext_lazy("The MGP password could not be updated."))

        sent = send_account_credentials(
            user_display_name(account), account.email, account.username, password,
            facilitator=linked_facilitator(account) is not None, reset=True,
        )
        if sent:
            messages.success(request, gettext_lazy("Password reset: the new password has been sent to %(email)s.") % {'email': account.email})
        else:
            # Mail non parti : le mot de passe est montré une seule fois à l'administrateur pour le transmettre.
            messages.warning(request, gettext_lazy(
                "Password reset, but the e-mail could not be sent. New password (shown once): %(password)s"
            ) % {'password': password})
        if mgp_note:
            messages.info(request, mgp_note)
