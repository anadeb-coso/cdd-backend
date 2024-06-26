from django import forms
from django.forms import RadioSelect, Select

from cdd.call_objects_from_other_db import mis_objects_call
from administrativelevels.models import AdministrativeLevel
from django.utils.translation import gettext_lazy as _



class AttachmentFilterForm(forms.Form):
    TYPE_CHOICES = (
        ("Photo", _("Photo")),
        ("Document", _("Document")),
        (None, _("Both")),
    )
    type = forms.ChoiceField(choices=TYPE_CHOICES, widget=RadioSelect, label=_("Type"))
    phase = forms.ChoiceField(widget=Select(attrs={'empty-option': '---------'}), required=False, label=_("Phase"))
    activity = forms.ChoiceField(widget=Select(attrs={'empty-option': '---------'}), required=False, label=_("Activity"))
    task = forms.ChoiceField(widget=Select(attrs={'empty-option': '---------'}), required=False, label=_("Task"))
    administrative_level = forms.ModelChoiceField(
        queryset=mis_objects_call.filter_objects(AdministrativeLevel, type="Village"),
        widget=Select(attrs={'empty-option': '---------'}), required=False, label=_("Administrative level")
    )