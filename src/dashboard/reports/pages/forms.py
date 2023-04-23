from django import forms
from django.utils.translation import gettext_lazy


class ReportsFacilitatorsStatusForm(forms.Form):
    
    # date_start = forms.DateTimeField(label=gettext_lazy("Start"))
    # date_end = forms.DateField(label=gettext_lazy("End"))
    facilitator = forms.ChoiceField(label=gettext_lazy("Facilitator"))


    def __init__(self, facilitators,*args, **kwargs):
        super().__init__(*args, **kwargs)

        _facilitators = [('', '')]
        [_facilitators.append((o.no_sql_db_name, o.name if o.name else o.username)) for o in facilitators.order_by("name", "username")]

        self.fields['facilitator'].widget.choices = _facilitators