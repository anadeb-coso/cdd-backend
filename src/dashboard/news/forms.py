from django import forms
from django.utils.translation import gettext_lazy as _

from administrativelevels.models import AdministrativeLevel
from news.models import Category, Tag

    
class FilterNewsFormMultiChoices(forms.Form):
    categories = forms.MultipleChoiceField()
    tags = forms.MultipleChoiceField()
    cantons = forms.MultipleChoiceField()
    villages = forms.MultipleChoiceField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


        self.fields['categories'].widget.choices = [('', '')] + [(str(o.id), o.name) for o in Category.objects.all().order_by("name")]
        self.fields['tags'].widget.choices = [('', '')] + [(str(o.id), o.name) for o in Tag.objects.all().order_by("name")]
        self.fields['cantons'].widget.choices = [('', '')] + [(str(o.id), o.name) for o in AdministrativeLevel.objects.using('mis').filter(type="Canton").order_by("name")]
        self.fields['villages'].widget.choices = [('', '')] + [(str(o.id), o.name) for o in AdministrativeLevel.objects.using('mis').filter(type="Village").order_by("name")]

    
