from django import forms

from authentication.models import Facilitator
from dashboard.utils import get_administrative_levels_by_type, get_documents_by_type, get_choices
from no_sql_client import NoSQLClient


class DiagnosticsForm(forms.Form):
    
    phase = forms.ChoiceField(label='')
    activity = forms.ChoiceField(label='')
    task = forms.ChoiceField(label='')

    region = forms.ChoiceField(label='')
    prefecture = forms.ChoiceField(label='')
    commune = forms.ChoiceField(label='')
    canton = forms.ChoiceField(label='')
    village = forms.ChoiceField(label='')


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        nsc = NoSQLClient()
        administrative_levels_db = nsc.get_db('administrative_levels')
        process_design = nsc.get_db('process_design')
        
        for label in ["phase", "activity", "task"]:
            try:
                elements = get_choices(get_documents_by_type(process_design, label), 'sql_id', "name", True)
                self.fields[label].widget.choices = elements
                self.fields[label].choices = elements
                self.fields[label].widget.attrs['class'] = label
            except Exception as exc:
                pass

        for label in ["region", "prefecture", "commune", "canton", "village"]:
            try:
                administrative_level_choices = get_choices(
                    get_administrative_levels_by_type(administrative_levels_db, label.title()), 
                    'administrative_id', "name", True)
                self.fields[label].widget.choices = administrative_level_choices
                self.fields[label].choices = administrative_level_choices
                self.fields[label].widget.attrs['class'] = label
            except Exception as exc:
                pass
        

