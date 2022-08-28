from django import forms

from no_sql_client import NoSQLClient
from dashboard.utils import get_choices


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
