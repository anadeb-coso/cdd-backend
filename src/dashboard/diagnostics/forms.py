from django import forms
from django.utils.translation import gettext_lazy

from authentication.models import Facilitator
from dashboard.utils import get_administrative_levels_by_type, get_documents_by_type, get_choices
from no_sql_client import NoSQLClient
from dashboard.facilitators.functions import get_cvds
from process_manager.models import Task, Phase, Activity
from administrativelevels.models import AdministrativeLevel


class DiagnosticsForm(forms.Form):
    
    phase = forms.ChoiceField(label=gettext_lazy("Phase"))
    activity = forms.ChoiceField(label=gettext_lazy("Activity"))
    task = forms.ChoiceField(label=gettext_lazy("Task"))

    region = forms.ChoiceField(label=gettext_lazy("Region"))
    prefecture = forms.ChoiceField(label=gettext_lazy("Prefecture"))
    commune = forms.ChoiceField(label=gettext_lazy("Commune"))
    canton = forms.ChoiceField(label=gettext_lazy("Canton"))
    village = forms.ChoiceField(label=gettext_lazy("Village"))


    def __init__(self, *args, **kwargs):
        initial = kwargs.get('initial', {})
        project_id = initial.get('project_id')
        cycle_id = initial.get('cycle_id')
        super().__init__(*args, **kwargs)

        # nsc = NoSQLClient()
        # administrative_levels_db = nsc.get_db('administrative_levels')
        # process_design = nsc.get_db('process_design')

        
        # for label in ["phase", "activity", "task"]:
        #     try:
        #         elements = get_choices(get_documents_by_type(process_design, label), 'sql_id', "name", True)
        #         self.fields[label].widget.choices = elements
        #         self.fields[label].choices = elements
        #         self.fields[label].widget.attrs['class'] = label
        #     except Exception as exc:
        #         pass
        if project_id:
            self.fields['phase'].widget.choices = [('', '')] + [(o.id, o.name) for o in Phase.objects.get_objects_by_general_filtre(request=None, attrs={'project_id': project_id, 'cycle_id': cycle_id}).order_by("order")]
            self.fields['activity'].widget.choices = [('', '')] + [(o.id, o.name) for o in Activity.objects.get_objects_by_general_filtre(request=None, attrs={'project_id': project_id, 'cycle_id': cycle_id}).order_by("phase__order", "order")]
            self.fields['task'].widget.choices = [('', '')] + [(o.id, o.name) for o in Task.objects.get_objects_by_general_filtre(request=None, attrs={'project_id': project_id, 'cycle_id': cycle_id}).order_by("phase__order", "activity__order", "order")]
        else:
            self.fields['phase'].widget.choices = [('', '')] + [(o.id, o.name) for o in Phase.objects.all().order_by("order")]
            self.fields['activity'].widget.choices = [('', '')] + [(o.id, o.name) for o in Activity.objects.all().order_by("phase__order", "order")]
            self.fields['task'].widget.choices = [('', '')] + [(o.id, o.name) for o in Task.objects.all().order_by("phase__order", "activity__order", "order")]

        # for label in ["region", "prefecture", "commune", "canton", "village"]:
        #     try:
        #         administrative_level_choices = get_choices(
        #             get_administrative_levels_by_type(administrative_levels_db, label.title()), 
        #             'administrative_id', "name", True)
        #         self.fields[label].widget.choices = administrative_level_choices
        #         self.fields[label].choices = administrative_level_choices
        #         self.fields[label].widget.attrs['class'] = label
        #     except Exception as exc:
        #         pass
        self.fields['region'].widget.choices = [('', '')] + [(o.id, o.name) for o in AdministrativeLevel.objects.using('mis').filter(type="Region").order_by("name")]
        self.fields['prefecture'].widget.choices = [('', '')] + [(o.id, o.name) for o in AdministrativeLevel.objects.using('mis').filter(type="Prefecture").order_by("name")]
        self.fields['commune'].widget.choices = [('', '')] + [(o.id, o.name) for o in AdministrativeLevel.objects.using('mis').filter(type="Commune").order_by("name")]
        self.fields['canton'].widget.choices = [('', '')] + [(o.id, o.name) for o in AdministrativeLevel.objects.using('mis').filter(type="Canton").order_by("name")]
        self.fields['village'].widget.choices = [('', '')] + [(o.id, o.name) for o in AdministrativeLevel.objects.using('mis').filter(type="Village").order_by("name")]
        

