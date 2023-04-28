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
        super().__init__(*args, **kwargs)

        # nsc = NoSQLClient()
        # administrative_levels_db = nsc.get_db('administrative_levels')
        # process_design = nsc.get_db('process_design')

        query_result_phases = [('', '')]
        query_result_activities = [('', '')]
        query_result_tasks = [('', '')]

        query_result_regions = [('', '')]
        query_result_prefectures = [('', '')]
        query_result_communes = [('', '')]
        query_result_cantons = [('', '')]
        query_result_villages = [('', '')]


        [query_result_phases.append((o.id, o.name)) for o in Phase.objects.all().order_by("order")]
        [query_result_activities.append((o.id, o.name)) for o in Activity.objects.all().order_by("phase__order", "order")]
        [query_result_tasks.append((o.id, o.name)) for o in Task.objects.all().order_by("phase__order", "activity__order", "order")]

        [query_result_regions.append((o.id, o.name)) for o in AdministrativeLevel.objects.using('mis').filter(type="Region").order_by("name")]
        [query_result_prefectures.append((o.id, o.name)) for o in AdministrativeLevel.objects.using('mis').filter(type="Prefecture").order_by("name")]
        [query_result_communes.append((o.id, o.name)) for o in AdministrativeLevel.objects.using('mis').filter(type="Commune").order_by("name")]
        [query_result_cantons.append((o.id, o.name)) for o in AdministrativeLevel.objects.using('mis').filter(type="Canton").order_by("name")]
        [query_result_villages.append((o.id, o.name)) for o in AdministrativeLevel.objects.using('mis').filter(type="Village").order_by("name")]
        # for label in ["phase", "activity", "task"]:
        #     try:
        #         elements = get_choices(get_documents_by_type(process_design, label), 'sql_id', "name", True)
        #         self.fields[label].widget.choices = elements
        #         self.fields[label].choices = elements
        #         self.fields[label].widget.attrs['class'] = label
        #     except Exception as exc:
        #         pass
        self.fields['phase'].widget.choices = query_result_phases
        self.fields['activity'].widget.choices = query_result_activities
        self.fields['task'].widget.choices = query_result_tasks

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
        self.fields['region'].widget.choices = query_result_regions
        self.fields['prefecture'].widget.choices = query_result_prefectures
        self.fields['commune'].widget.choices = query_result_communes
        self.fields['canton'].widget.choices = query_result_cantons
        self.fields['village'].widget.choices = query_result_villages
        

