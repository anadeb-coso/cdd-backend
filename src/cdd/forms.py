from django import forms
from django.utils.translation import gettext_lazy as _


#Delete
class DeleteConfirmForm(forms.Form):
    confirmation = forms.BooleanField(label=_('Please check this box and click the confirmation button for validation.'),
                                       widget=forms.CheckboxInput, required=True)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
#And Delete