from django import forms
from django.utils.translation import gettext_lazy as _

from reports.models import VillageCommittee
from cdd.forms import CustomerSelectMultiple

COMMITTEE = "BCVD"

class FilterTypeCommittesForm(forms.Form):

    committees = forms.MultipleChoiceField(
        choices=[],
        required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        committees = (
            VillageCommittee.objects
            .values("name", "description")
            .distinct()
            .order_by("name")
        )

        choices = []
        tooltips = {}
        
        for c in committees:
            choices.append((c["name"], c["name"]))
            tooltips[c["name"]] = c["description"] or c["name"]

        self.fields["committees"].choices = choices
        self.fields["committees"].initial = COMMITTEE if choices else None

        # injecter widget avec tooltips
        self.fields["committees"].widget = CustomerSelectMultiple(
            choices=self.fields["committees"].choices,
            tooltips=tooltips
        )