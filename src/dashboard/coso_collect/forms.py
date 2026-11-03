from django import forms
from django.contrib.auth.models import Group, User
from django.db.models import Q
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
        fields = ('title', 'description', 'rank', 'access_scope', 'allowed_users', 'allowed_groups',
                  'allowed_facilitators', 'single_submission', 'close_message')
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'rank': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'style': 'max-width:160px;',
                                             'placeholder': _('Optional')}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'access_scope': forms.RadioSelect(attrs={'class': 'custom-control-input'}),
            'single_submission': forms.CheckboxInput(attrs={'class': 'custom-control-input'}),
            'close_message': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 2,
                'placeholder': _('This form is closed: no more data can be sent.'),
            }),
        }
        help_texts = {
            'rank': _('Optional. Forms are listed on the web and on the mobile from the smallest ranking to the '
                      'largest; forms without a ranking come after them.'),
            'close_message': _('Shown to users who try to send data after the form is closed.'),
            'single_submission': _('Unticked (default): each person can send as many records as they want. '
                                   'Ticked: each person has only one record (their web and facilitator accounts '
                                   'count as one person); once started, they continue it instead of creating '
                                   'another. Records already received are kept.'),
        }


class AddFormAdminForm(forms.Form):
    """Nouveaux administrateurs d'un formulaire, en une fois : plusieurs utilisateurs et/ou tous les membres de
    groupes d'utilisateurs. Seuls les comptes web actifs qui ne sont ni le créateur, ni des superutilisateurs
    (déjà tous les droits), ni déjà administrateurs sont ajoutés. Chacun reçoit d'abord la seule lecture des
    données ; le créateur coche ensuite ses autres droits."""
    users = _UserChoiceField(
        queryset=User.objects.none(), required=False, label=_('Users'),
        widget=forms.SelectMultiple(attrs={'class': 'form-control form-control-sm', 'style': 'width:100%'}),
    )
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.order_by('name'), required=False, label=_('User groups'),
        widget=forms.SelectMultiple(attrs={'class': 'form-control form-control-sm', 'style': 'width:100%'}),
    )

    def __init__(self, collect_form, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.collect_form = collect_form
        self.fields['users'].queryset = self.candidates()

    def candidates(self):
        excluded = set(self.collect_form.admin_rights.values_list('user_id', flat=True))
        if self.collect_form.created_by_id:
            excluded.add(self.collect_form.created_by_id)
        return (User.objects.filter(is_active=True, is_superuser=False)
                .exclude(pk__in=excluded).order_by('first_name', 'last_name', 'username'))

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('users') and not cleaned.get('groups'):
            raise forms.ValidationError(_('Choose at least one user or one group.'))
        return cleaned

    def new_admins(self):
        """Utilisateurs à ajouter (choisis + membres des groupes choisis), sans doublon."""
        users = self.cleaned_data.get('users') or User.objects.none()
        groups = self.cleaned_data.get('groups') or []
        return list(self.candidates().filter(Q(pk__in=users) | Q(groups__in=groups)).distinct())


class ImportFormFileForm(forms.Form):
    file = forms.FileField(label=_('Form file (.xlsx XLSForm or .json)'))
