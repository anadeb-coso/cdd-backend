from django import forms
from django.utils.translation import gettext_lazy as _



class TaskPlanCommentForm(forms.Form):
    message = forms.CharField(label='', max_length=255, widget=forms.Textarea(attrs={'rows': '3'}))

    def __init__(self, *args, **kwargs):
        # initial = kwargs.get('initial')
        # super().__init__(*args, **kwargs)
        pass
