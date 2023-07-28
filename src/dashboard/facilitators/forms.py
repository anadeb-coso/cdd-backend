from django import forms
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from authentication.models import Facilitator
from dashboard.utils import get_administrative_level_choices, get_administrative_levels_by_level, get_choices
from no_sql_client import NoSQLClient
from .functions import get_cvds
from process_manager.models import Task, Phase, Activity


class FilterTaskForm(forms.Form):
    administrative_level = forms.ChoiceField()
    phase = forms.ChoiceField()
    activity = forms.ChoiceField()
    task = forms.ChoiceField()
    is_validated = forms.ChoiceField()

    def __init__(self, *args, **kwargs):
        initial = kwargs.get('initial')
        facilitator_db_name = initial.get('facilitator_db_name')
        super().__init__(*args, **kwargs)

        nsc = NoSQLClient()
        facilitator_db = nsc.get_db(facilitator_db_name)

        facilitator_docs = facilitator_db.all_docs(include_docs=True)['rows']

        query_result_phases = [('', '')]
        query_result_activities = [('', '')]
        query_result_tasks = [('', '')]
        # query_result_administrativelevels = []
        facilitator_doc = {}
        for doc in facilitator_docs:
            doc = doc.get('doc')
            if doc.get('type') == "facilitator":
                # query_result_administrativelevels = doc.get("administrative_levels")
                facilitator_doc = doc
                break
            # elif doc.get('type') == "phase" and not self.check_name(query_result_phases, doc):
            #     query_result_phases.append(doc)
            # elif doc.get('type') == "activity" and not self.check_name(query_result_activities, doc):
            #     doc["phase_order"] = 0
            #     for phase_obj in query_result_phases:
            #         if phase_obj['_id'] == doc["phase_id"]:
            #             doc["phase_order"] = phase_obj['order']
            #             break
            #     query_result_activities.append(doc)
            # elif doc.get('type') == "task" and not self.check_name(query_result_tasks, doc):
            #     doc["phase_order"] = 0
            #     doc["activity_order"] = 0
            #     for phase_obj in query_result_phases:
            #         if phase_obj['name'] == doc["phase_name"]:
            #             doc["phase_order"] = phase_obj['order']
            #             break
            #     for activity_obj in query_result_activities:
            #         if activity_obj['name'] == doc["activity_name"]:
            #             doc["activity_order"] = activity_obj['order']
            #             break
            #     query_result_tasks.append(doc)
        
        # query_result_phases = sorted(query_result_phases, key=lambda obj: obj['order'])
        # query_result_activities = sorted(query_result_activities, key=lambda obj: (str(obj["phase_order"])+str(obj["order"])))
        # query_result_tasks = sorted(query_result_tasks, key=lambda obj: (str(obj["phase_order"])+str(obj["activity_order"])+str(obj["order"])))
        # query_result_administrativelevels = sorted(query_result_administrativelevels, key=lambda obj: obj.get('name'))
        [query_result_phases.append((o.name, o.name)) for o in Phase.objects.all().order_by("order")]
        [query_result_activities.append((o.name, o.name)) for o in Activity.objects.all().order_by("phase__order", "order")]
        [query_result_tasks.append((o.name, o.name)) for o in Task.objects.all().order_by("phase__order", "activity__order", "order")]
        cvds = sorted(get_cvds(facilitator_doc), key=lambda obj: obj.get('name'))

        # self.fields['administrative_level'].widget.choices = get_choices(
        #     query_result_administrativelevels, "id", "name")
        self.fields['administrative_level'].widget.choices = get_choices(cvds, "village_id", "name")
        # self.fields['phase'].widget.choices = get_choices(query_result_phases, "name", "name")
        # self.fields['activity'].widget.choices = get_choices(query_result_activities, "name", "name")
        # self.fields['task'].widget.choices = get_choices(query_result_tasks, "name", "name")
        self.fields['phase'].widget.choices = query_result_phases
        self.fields['activity'].widget.choices = query_result_activities
        self.fields['task'].widget.choices = query_result_tasks
        self.fields['is_validated'].widget.choices = [
            ('', ''), ('Validated', _('Validated')), ('Invalidated',  _('Invalidated')),
            ('Completed', _('Completed')), ('Pending',  _('Uncompleted')), ('Untouched',  _('Unsee'))
        ]
    
    def check_name(self, liste, obj):
        for elt in liste:
            if elt.get('name') == obj.get("name"):
                return True
        return False

class FacilitatorForm(forms.Form):
    error_messages = {
        "password_mismatch": _("The two password fields didn’t match."),
        'duplicated_username': _('A facilitator with that username is already registered.'),
        'administrative_level_required': _('At least one administrative level is required.'),
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
    administrative_level = forms.ChoiceField()
    administrative_levels = forms.JSONField(label='', required=False)
    sex = forms.ChoiceField(choices=(("M.", "M."), ("Mme", "Mme")))

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
        if Facilitator.objects.filter(username=username).exists():
            self.add_error('username', self.error_messages["duplicated_username"])
        return username

    def clean(self):
        administrative_levels = self.cleaned_data['administrative_levels']
        if not administrative_levels:
            raise forms.ValidationError(self.error_messages['administrative_level_required'])
        return super().clean()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        nsc = NoSQLClient()
        administrative_levels_db = nsc.get_db('administrative_levels')
        label = get_administrative_levels_by_level(administrative_levels_db)[0]['administrative_level'].upper()
        self.fields['administrative_level'].label = label

        administrative_level_choices = get_administrative_level_choices(administrative_levels_db)
        self.fields['administrative_level'].widget.choices = administrative_level_choices
        self.fields['administrative_level'].choices = administrative_level_choices
        self.fields['administrative_level'].widget.attrs['class'] = "region"
        self.fields['administrative_levels'].widget.attrs['class'] = "hidden"




class UpdateFacilitatorForm(forms.ModelForm):
    error_messages = {
        'duplicated_username': _('A facilitator with that username is already registered.'),
        'administrative_level_required': _('At least one administrative level is required.'),
    }
    
    email = forms.EmailField(required=False)
    phone = forms.CharField(required=False)
    name = forms.CharField(required=False)
    administrative_level = forms.ChoiceField(required=False)
    administrative_levels = forms.JSONField(label='', required=False)
    sex = forms.ChoiceField(choices=(("M.", "M."), ("Mme", "Mme")))

    def clean(self):
        administrative_levels = self.cleaned_data['administrative_levels']
        if not administrative_levels:
            raise forms.ValidationError(self.error_messages['administrative_level_required'])
        return super().clean()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        nsc = NoSQLClient()
        administrative_levels_db = nsc.get_db('administrative_levels')
        label = get_administrative_levels_by_level(administrative_levels_db)[0]['administrative_level'].upper()
        self.fields['administrative_level'].label = label

        administrative_level_choices = get_administrative_level_choices(administrative_levels_db)
        self.fields['administrative_level'].widget.choices = administrative_level_choices
        self.fields['administrative_level'].choices = administrative_level_choices
        self.fields['administrative_level'].widget.attrs['class'] = "region"
        self.fields['administrative_levels'].widget.attrs['class'] = "hidden"


    class Meta:
        model = Facilitator
        fields = [] # specify the fields to be displayed


class FilterFacilitatorForm(forms.Form):
    region = forms.ChoiceField()
    prefecture = forms.ChoiceField()
    commune = forms.ChoiceField()
    canton = forms.ChoiceField()
    village = forms.ChoiceField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        nsc = NoSQLClient()
        db = nsc.get_db("administrative_levels")

        administrativelevels_docs = db.all_docs(include_docs=True)['rows']

        query_result_regions = []
        query_result_prefectures = []
        query_result_communes = []
        query_result_cantons = []
        query_result_villages = []
        for doc in administrativelevels_docs:
            doc = doc.get('doc')
            if doc.get('type') == 'administrative_level':
                if doc.get('administrative_level') == "Region":
                    query_result_regions.append(doc)
                elif doc.get('administrative_level') == "Prefecture":
                    query_result_prefectures.append(doc)
                elif doc.get('administrative_level') == "Commune":
                    query_result_communes.append(doc)
                elif doc.get('administrative_level') == "Canton":
                    query_result_cantons.append(doc)
                elif doc.get('administrative_level') == "Village":
                    query_result_villages.append(doc)
        
        self.fields['region'].widget.choices = get_choices(query_result_regions, "administrative_id", "name")
        self.fields['prefecture'].widget.choices = get_choices(query_result_prefectures, "administrative_id", "name")
        self.fields['commune'].widget.choices = get_choices(query_result_communes, "administrative_id", "name")
        self.fields['canton'].widget.choices = get_choices(query_result_cantons, "administrative_id", "name")
        self.fields['village'].widget.choices = get_choices(query_result_villages, "administrative_id", "name")
    
