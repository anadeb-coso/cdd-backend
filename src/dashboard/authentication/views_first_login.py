from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.shortcuts import redirect, resolve_url
from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext_lazy
from django.views import generic

from authentication.accounts import change_initial_password, password_change_required
from authentication.middleware import FACILITATOR_GROUP_NAMES, PASSWORD_CHANGE_CHECKED_SESSION_KEY
from dashboard.authentication.forms import FirstLoginPasswordForm


def after_login_url(user):
    """Page d'arrivée après connexion (Rapports pour un facilitateur, cf. FacilitatorAwareLoginView)."""
    if user.groups.filter(name__in=FACILITATOR_GROUP_NAMES).exists():
        return reverse("dashboard:reports:reports:index")
    return resolve_url(settings.LOGIN_REDIRECT_URL)


class FirstLoginPasswordView(LoginRequiredMixin, generic.FormView):
    """Changement obligatoire du mot de passe initial à la première connexion (PasswordChangeRequiredMiddleware y
    renvoie toute page du dashboard tant qu'il n'est pas fait). Le nouveau mot de passe vaut pour toutes les
    plateformes (DCC, SIG, MGP) ; la session courante reste ouverte."""
    template_name = 'authentication/first_login_password.html'
    form_class = FirstLoginPasswordForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not password_change_required(account=request.user):
            request.session[PASSWORD_CHANGE_CHECKED_SESSION_KEY] = True
            return redirect(after_login_url(request.user))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        data = form.cleaned_data
        ok, errors, _person = change_initial_password(
            None, data['current_password'], data['new_password'], data['new_password_confirm'], 'dcc_web',
            account=self.request.user,
        )
        if not ok:
            for error in errors:
                form.add_error(None, error)
            return self.form_invalid(form)
        # Le hash du mot de passe a changé : la session courante est gardée.
        update_session_auth_hash(self.request, User.objects.get(pk=self.request.user.pk))
        self.request.session[PASSWORD_CHANGE_CHECKED_SESSION_KEY] = True
        messages.success(self.request, gettext_lazy("Your password has been changed. It is now valid on all the platforms (DCC, MGP and SIG)."))
        return redirect(after_login_url(self.request.user))
