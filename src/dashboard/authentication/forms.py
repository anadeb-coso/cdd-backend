from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django import forms

from django.contrib.auth.models import User

from authentication.accounts import email_in_use, username_candidates


class EmailAuthenticationForm(AuthenticationForm):
    def __init__(self, request=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = _('Email')

    def clean(self):
        email = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        user = User.objects.filter(email__iexact=email).first()

        if not user:
            raise self.get_invalid_login_error()
        if email and password:
            self.user_cache = authenticate(self.request, username=user.username, password=password)
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            else:
                self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


class CreateUserForm(forms.ModelForm):
    """Création d'un utilisateur web : le nom d'utilisateur (prénom.nom) et le mot de passe initial sont générés
    puis envoyés par e-mail ; le mot de passe est à changer à la première connexion (authentication/accounts.py)."""

    class Meta:
        """docstring for Meta"""
        model = User
        fields = (
            'last_name', 'first_name', 'email',
            'is_superuser', 'is_staff', 'is_active', 'groups', 'user_permissions'
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('last_name', 'first_name', 'email'):
            self.fields[name].required = True

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip()
        if email_in_use(email):
            raise forms.ValidationError(_('An account (user or facilitator) already uses this e-mail address.'), code='email_in_use')
        return email

    def clean(self):
        cleaned_data = super().clean()
        if not username_candidates(cleaned_data.get('first_name'), cleaned_data.get('last_name')):
            self.add_error('last_name', _('The last name and the first name(s) must contain letters.'))
        return cleaned_data

class UpdateUserForm(forms.ModelForm):
                
    class Meta:
        """docstring for Meta"""
        model = User
        fields = (
            'username', 'last_name', 'first_name', 'email', 
            'is_superuser', 'is_staff', 'is_active', 'groups', 'user_permissions'
        )


class FirstLoginPasswordForm(forms.Form):
    """Changement du mot de passe initial à la première connexion (cf. authentication/accounts.py)."""
    current_password = forms.CharField(label=gettext_lazy("Current password"), strip=False,
                                       widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))
    new_password = forms.CharField(label=gettext_lazy("New password"), strip=False, max_length=16,
                                   widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
                                   help_text=gettext_lazy("8 to 16 letters and digits, with at least one letter and one digit."))
    new_password_confirm = forms.CharField(label=gettext_lazy("New password confirmation"), strip=False, max_length=16,
                                           widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

