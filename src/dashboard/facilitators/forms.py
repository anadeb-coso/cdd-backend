from django import forms
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from authentication.models import Facilitator
from dashboard.utils import get_choices
from no_sql_client import NoSQLClient


class FilterTaskForm(forms.Form):
    administrative_level = forms.ChoiceField()
    phase = forms.ChoiceField()
    activity = forms.ChoiceField()

    def __init__(self, *args, **kwargs):
        initial = kwargs.get('initial')
        facilitator_db_name = initial.get('facilitator_db_name')
        super().__init__(*args, **kwargs)

        nsc = NoSQLClient()
        facilitator_db = nsc.get_db(facilitator_db_name)

        query_result = facilitator_db.get_query_result({"type": 'task'})
        self.fields['administrative_level'].widget.choices = get_choices(
            query_result, "administrative_level_id", "administrative_level_name")
        self.fields['phase'].widget.choices = get_choices(query_result, "phase_id", "phase_name")
        self.fields['activity'].widget.choices = get_choices(query_result, "activity_id", "activity_name")


class FacilitatorForm(forms.Form):
    error_messages = {
        "password_mismatch": _("The two password fields didn’t match."),
        'duplicated_username': _('A facilitator with that username is already registered.'),
    }
    name = forms.CharField()
    email = forms.EmailField(required=False)
    phone = forms.CharField(required=False)
    username = forms.CharField()
    password1 = forms.CharField(
        label=_("Password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text=password_validation.password_validators_help_text_html(),
    )
    password2 = forms.CharField(
        label=_("Password confirmation"),
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        strip=False,
        help_text=_("Enter the same password as before, for verification."),
    )

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError(
                self.error_messages["password_mismatch"],
                code="password_mismatch",
            )
        return password2

    def _post_clean(self):
        super()._post_clean()
        # Validate the password after self.instance is updated with form data
        # by super().
        password = self.cleaned_data.get("password2")
        if password:
            try:
                password_validation.validate_password(password)
            except ValidationError as error:
                self.add_error("password2", error)

    def clean_username(self):
        username = self.cleaned_data['username']
        if Facilitator.objects.filter(username=username):
            self.add_error('username', self.error_messages["duplicated_username"])
        return username
