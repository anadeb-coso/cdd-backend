from django import forms
from django.utils.translation import gettext_lazy

from dashboard.administrative_levels.functions import get_cascade_administrative_levels_by_administrative_level_id
from dashboard.process_manager.functions import get_cascade_phase_activity_task_by_their_id
from process_manager.models import Task, Phase, Activity
from administrativelevels.models import AdministrativeLevel


class CascadeForm(forms.Form):
    
    phase = forms.ChoiceField(label=gettext_lazy("Phase"))
    activity = forms.ChoiceField(label=gettext_lazy("Activity"))
    task = forms.ChoiceField(label=gettext_lazy("Task"))

    region = forms.ChoiceField(label=gettext_lazy("Region"))
    prefecture = forms.ChoiceField(label=gettext_lazy("Prefecture"))
    commune = forms.ChoiceField(label=gettext_lazy("Commune"))
    canton = forms.ChoiceField(label=gettext_lazy("Canton"))
    village = forms.ChoiceField(label=gettext_lazy("Village"))


    def __init__(self, ad_id, phase_id, activity_id, task_id, *args, **kwargs):
        super().__init__(*args, **kwargs)

        query_result_phases = [('', '')]
        query_result_activities = [('', '')]
        query_result_tasks = [('', '')]

        query_result_regions = [('', '')]
        query_result_prefectures = [('', '')]
        query_result_communes = [('', '')]
        query_result_cantons = [('', '')]
        query_result_villages = [('', '')]

        ad = None
        if ad_id:
            ad = AdministrativeLevel.objects.using('mis').filter(id=int(ad_id))
        for k, v in get_cascade_administrative_levels_by_administrative_level_id(ad_id).items():
            if k == "prefectures":
                [query_result_prefectures.append((o.get('administrative_id'), o.get('name'))) for o in v]
            if k == "communes":
                [query_result_communes.append((o.get('administrative_id'), o.get('name'))) for o in v]
            if k == "cantons":
                [query_result_cantons.append((o.get('administrative_id'), o.get('name'))) for o in v]
            if k == "villages":
                if ad and ad[0].type == "Village":
                    [query_result_villages.append((o.id, o.name)) for o in ad[0].parent.administrativelevel_set.get_queryset()]
                else:
                    [query_result_villages.append((o.get('administrative_id'), o.get('name'))) for o in v]
                    
        for k, v in get_cascade_phase_activity_task_by_their_id(phase_id, activity_id, task_id).items():
            if k == "activities":
                [query_result_activities.append(o) for o in v]
            if k == "tasks":
                [query_result_tasks.append(o) for o in v]


        [query_result_phases.append((o.id, o.name)) for o in Phase.objects.all().order_by("order")]

        [query_result_regions.append((o.id, o.name)) for o in AdministrativeLevel.objects.using('mis').filter(type="Region").order_by("name")]
        
        
       
        self.fields['phase'].widget.choices = query_result_phases
        self.fields['activity'].widget.choices = query_result_activities
        self.fields['task'].widget.choices = query_result_tasks
        
        self.fields['region'].widget.choices = query_result_regions
        self.fields['prefecture'].widget.choices = query_result_prefectures
        self.fields['commune'].widget.choices = query_result_communes
        self.fields['canton'].widget.choices = query_result_cantons
        self.fields['village'].widget.choices = query_result_villages
        
        #Default
        if task_id:
            self.fields['task'].initial = self.get_item_by_id(query_result_tasks, task_id)
            _t = Task.objects.filter(id=int(task_id))
            if _t:
                self.fields['activity'].initial = (_t[0].activity_id, _t[0].activity.name)
                self.fields['phase'].initial = (_t[0].phase_id, _t[0].phase.name)
        elif activity_id:
            self.fields['activity'].initial = self.get_item_by_id(query_result_activities, activity_id)
            _a = Activity.objects.filter(id=int(activity_id))
            if _a:
                self.fields['phase'].initial = (_a[0].phase_id, _a[0].phase.name)
        elif phase_id:
            self.fields['phase'].initial = self.get_item_by_id(query_result_phases, phase_id)

        if ad_id:
            if ad:
                if ad[0].type == "Village":
                    self.fields['village'].initial = self.get_item_by_id(query_result_villages, ad_id)
                    self.fields['canton'].initial = (ad[0].parent.id, ad[0].parent.name)
                    self.fields['commune'].initial = (ad[0].parent.parent.id, ad[0].parent.parent.name)
                    self.fields['prefecture'].initial = (ad[0].parent.parent.parent.id, ad[0].parent.parent.parent.name)
                    self.fields['region'].initial = (ad[0].parent.parent.parent.parent.id, ad[0].parent.parent.parent.parent.name)
                elif ad[0].type == "Canton":
                    self.fields['canton'].initial = self.get_item_by_id(query_result_cantons, ad_id)
                    self.fields['commune'].initial = (ad[0].parent.id, ad[0].parent.name)
                    self.fields['prefecture'].initial = (ad[0].parent.parent.id, ad[0].parent.parent.name)
                    self.fields['region'].initial = (ad[0].parent.parent.parent.id, ad[0].parent.parent.parent.name)
                elif ad[0].type == "Commune":
                    self.fields['commune'].initial = self.get_item_by_id(query_result_communes, ad_id)
                    self.fields['prefecture'].initial = (ad[0].parent.id, ad[0].parent.name)
                    self.fields['region'].initial = (ad[0].parent.parent.id, ad[0].parent.parent.name)
                elif ad[0].type == "Prefecture":
                    self.fields['prefecture'].initial = self.get_item_by_id(query_result_prefectures, ad_id)
                    self.fields['region'].initial = (ad[0].parent.id, ad[0].parent.name)
                elif ad[0].type == "Region":
                    self.fields['region'].initial = self.get_item_by_id(query_result_regions, ad_id)

    def get_item_by_id(self, liste, _id):
        for elt in liste:
            if str(elt[0]) == str(_id):
                return elt
        return ('', '')