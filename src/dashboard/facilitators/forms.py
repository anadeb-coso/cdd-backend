from django import forms
from django.utils.translation import gettext_lazy as _

from authentication import ADL, MAJOR
from client import get_db
from dashboard.forms.forms import FileForm


class PasswordConfirmForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput())


class FacilitatorProfileForm(FileForm):
    name = forms.CharField(max_length=250, label=_("Name"))
    phone = forms.CharField(required=False, max_length=50, label=_('Tel'))
    email = forms.EmailField()
    doc_id = ""

    def __init__(self, *args, **kwargs):
        initial = kwargs.get('initial')
        self.doc_id = initial.get('doc_id')
        super().__init__(*args, **kwargs)
        self.fields['file'].required = False
        self.fields['file'].widget.attrs["class"] = "hidden"

        document = get_db()[self.doc_id]
        self.fields['name'].initial = document['representative']['name']
        self.fields['phone'].initial = document['representative']['phone']
        self.fields['email'].initial = document['representative']['email']

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        selector = {
            "$and": [
                {
                    "representative.email": email
                },
                {
                    "type": {
                        "$in": [ADL, MAJOR]
                    }
                }
            ]
        }
        eadl_db = get_db()

        docs = eadl_db.get_query_result(selector)
        doc = docs[0][0] if docs[0] else None
        if doc and doc['_id'] != self.doc_id:
            self.add_error('email', _("This email is already registered."))
        return email
