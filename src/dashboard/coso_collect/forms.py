from django import forms
from django.contrib.auth.models import Group, User
from django.utils.translation import gettext_lazy as _

from authentication.models import Facilitator
from coso_collect.models import CollectForm


class CollectFormCreateForm(forms.ModelForm):
    class Meta:
        model = CollectForm
        fields = ('title', 'description')
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class _UserChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        name = obj.get_full_name()
        return f'{name} ({obj.username})' if name else obj.username


class _FacilitatorChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return f'{obj.name or obj.username} ({obj.username})'


class CollectFormSettingsForm(forms.ModelForm):
    allowed_users = _UserChoiceField(
        queryset=User.objects.filter(is_active=True).order_by('first_name', 'last_name', 'username'),
        required=False, label=_('Allowed users'),
        widget=forms.SelectMultiple(attrs={'class': 'form-control'}),
    )
    allowed_groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.order_by('name'), required=False, label=_('Allowed groups'),
        widget=forms.SelectMultiple(attrs={'class': 'form-control'}),
    )
    allowed_facilitators = _FacilitatorChoiceField(
        queryset=Facilitator.objects.filter(active=True).order_by('name', 'username'),
        required=False, label=_('Allowed facilitators'),
        widget=forms.SelectMultiple(attrs={'class': 'form-control'}),
    )
    class Meta:
        model = CollectForm
        fields = ('title', 'description', 'access_scope', 'allowed_users', 'allowed_groups',
                  'allowed_facilitators', 'single_submission', 'close_message')
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'access_scope': forms.RadioSelect(attrs={'class': 'custom-control-input'}),
            'single_submission': forms.CheckboxInput(attrs={'class': 'custom-control-input'}),
            'close_message': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 2,
                'placeholder': _('This form is closed: no more data can be sent.'),
            }),
        }
        help_texts = {
            'close_message': _('Shown to users who try to send data after the form is closed.'),
            'single_submission': _('Unticked (default): each person can send as many records as they want. '
                                   'Ticked: each person has only one record (their web and facilitator accounts '
                                   'count as one person); once started, they continue it instead of creating '
                                   'another. Records already received are kept.'),
        }


class _SingleUserChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        name = obj.get_full_name()
        return f'{name} ({obj.username})' if name else obj.username


class AddFormAdminForm(forms.Form):
    """Nouvel administrateur d'un formulaire : compte web actif, ni le créateur ni un administrateur déjà
    désigné. Il reçoit d'abord la seule lecture des données ; le créateur coche ensuite ses autres droits."""
    user = _SingleUserChoiceField(
        queryset=User.objects.none(), label=_('Add an administrator'), empty_label=_('Choose a user…'),
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
    )

    def __init__(self, collect_form, *args, **kwargs):
        super().__init__(*args, **kwargs)
        excluded = set(collect_form.admin_rights.values_list('user_id', flat=True))
        if collect_form.created_by_id:
            excluded.add(collect_form.created_by_id)
        # Les superutilisateurs ont déjà tous les droits sur tous les formulaires.
        self.fields['user'].queryset = (User.objects.filter(is_active=True, is_superuser=False)
                                        .exclude(pk__in=excluded).order_by('first_name', 'last_name', 'username'))


class ImportFormFileForm(forms.Form):
    file = forms.FileField(label=_('Form file (.xlsx XLSForm or .json)'))
