from django import forms
from django.utils.translation import gettext_lazy as _


#Delete
class DeleteConfirmForm(forms.Form):
    confirmation = forms.BooleanField(label=_('Please check this box and click the confirmation button for validation.'),
                                       widget=forms.CheckboxInput, required=True)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
#And Delete


class CustomerSelectMultiple(forms.SelectMultiple):

    def __init__(self, *args, tooltips=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tooltips = tooltips or {}

    def create_option(
        self, name, value, label, selected, index,
        subindex=None, attrs=None
    ):
        option = super().create_option(
            name, value, label, selected, index, subindex, attrs
        )

        # ajouter tooltip spécifique
        if value in self.tooltips:
            option["attrs"]["title"] = self.tooltips[value]
            option["attrs"]["help"] = self.tooltips[value]

        return option