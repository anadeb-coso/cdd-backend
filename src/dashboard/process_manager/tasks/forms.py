from django import forms

from cdd import FORM_FIELDS_TO_EXCLUDE
from process_manager.models import Phase, Activity, Task, Project, Cycle



class ProcessTaskManagerBaseForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(ProcessTaskManagerBaseForm, self).__init__(*args, **kwargs)
        project_id = kwargs.get('initial', {}).get('project_id')
        if project_id:
            self.fields['project'].queryset = Project.objects.filter(id=project_id)
            self.fields['project'].initial = Project.objects.get(id=project_id)
            self.fields['cycles'].queryset = Cycle.objects.filter(project_id=project_id)
            self.fields['cycles'].initial = Cycle.objects.filter(project_id=project_id)

            if 'phase' in self.fields:
                self.fields['phase'].queryset = Phase.objects.filter(project_id=project_id).order_by('order')
                
            if 'activity' in self.fields:
                self.fields['activity'].queryset = Activity.objects.filter(project_id=project_id).order_by('phase__order', 'order')
        
        self.fields['couch_id'].widget.attrs['readonly'] = 'readonly' 

        if 'name_normalized' in self.fields:
            self.fields['name_normalized'].widget.attrs['readonly'] = 'readonly'


class PhaseForm(ProcessTaskManagerBaseForm):

    class Meta:
        """docstring for Meta"""
        model = Phase
        # fields = '__all__'
        exclude = FORM_FIELDS_TO_EXCLUDE

        
class ActivityForm(ProcessTaskManagerBaseForm):
                
    class Meta:
        """docstring for Meta"""
        model = Activity
        # fields = '__all__'
        exclude = FORM_FIELDS_TO_EXCLUDE

        
class TaskForm(ProcessTaskManagerBaseForm):
                
    class Meta:
        """docstring for Meta"""
        model = Task
        # fields = '__all__'
        exclude = FORM_FIELDS_TO_EXCLUDE

        