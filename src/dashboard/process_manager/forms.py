from django import forms
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from administrativelevels.models import AdministrativeLevel
from authentication.models import Facilitator
from process_manager.models import Project
from subprojects.models import Financier

from .projects import expand_administrative_levels, mis_project, save_cosomis_fields

# Statuts d'un projet : mêmes valeurs que dans COSOMIS (subprojects.models.Project.Status).
PROJECT_STATUS_CHOICES = (
    ('ACTIVE', _('Active')),
    ('SUSPENDED', _('Suspended')),
    ('ABANDONED', _('Abandoned')),
    ('CLOSED', _('Closed')),
)


class FacilitatorChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        name = obj.name or obj.username
        return f"{name} ({obj.email})" if obj.email else name


class UserChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        name = obj.get_full_name() or obj.username
        return f"{name} ({obj.email})" if obj.email else name


class AdministrativeLevelChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.name} ({obj.parent.name})" if obj.parent_id else obj.name


def descendant_project_ids(project):
    """Le projet et tous ses sous-projets (un projet ne peut pas devenir le parent de l'un d'eux)."""
    ids, frontier = {project.pk}, [project.pk]
    while frontier:
        frontier = list(Project.objects.filter(parent_id__in=frontier).exclude(pk__in=ids).values_list('pk', flat=True))
        ids.update(frontier)
    return ids


class ProjectFullForm(forms.ModelForm):
    """Projet complet (création et modification), page « Projets » du Web DCC et admin : champs du projet,
    facilitateurs et utilisateurs liés (DCC), financeurs et niveaux administratifs (COSOMIS) — mêmes champs et mêmes
    règles que le formulaire de projet de COSOMIS (cosomis/subprojects/forms_project.py)."""
    status = forms.ChoiceField(choices=PROJECT_STATUS_CHOICES, initial='ACTIVE', label=_("Status"))
    financiers = forms.ModelMultipleChoiceField(queryset=Financier.objects.none(), required=False, label=_("Financiers"))
    administrative_levels = AdministrativeLevelChoiceField(
        queryset=AdministrativeLevel.objects.none(), required=False, label=_("Administrative Levels"),
        help_text=_("The villages of the chosen cantons and the parents of the chosen levels are added automatically; "
                    "the cycles of the project follow these levels."))
    facilitators = FacilitatorChoiceField(
        queryset=Facilitator.objects.none(), required=False, label=_("Facilitators"),
        help_text=_("Facilitators working on this project (they see it in the DCC mobile app)."))
    users = UserChoiceField(
        queryset=User.objects.none(), required=False, label=_("Users"),
        help_text=_("Users who can select this project in the DCC and COSOMIS."))
    inherit_from_parent = forms.BooleanField(
        required=False, label=_("Also link the facilitators and users of the parent project"))

    class Meta:
        model = Project
        fields = ['name', 'description', 'parent', 'status', 'financiers', 'administrative_levels',
                  'facilitators', 'users', 'inherit_from_parent']
        labels = {'name': _("Name"), 'description': _("Description"), 'parent': _("Parent project")}

    def __init__(self, *args, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        instance = self.instance
        parents = Project.objects.all().order_by('name')
        if instance.pk:
            parents = parents.exclude(pk__in=descendant_project_ids(instance))
        self.fields['parent'].queryset = parents
        self.fields['financiers'].queryset = Financier.objects.all().order_by('name')
        self.fields['administrative_levels'].queryset = AdministrativeLevel.objects.select_related('parent').order_by('name')

        facilitator_ids = list(instance.facilitators.values_list('pk', flat=True)) if instance.pk else []
        user_ids = list(instance.users.values_list('pk', flat=True)) if instance.pk else []
        # comptes réels actifs, plus ceux déjà liés (même inactifs : ne pas les retirer sans le vouloir)
        self.fields['facilitators'].queryset = Facilitator.objects.filter(
            Q(active=True, develop_mode=False, training_mode=False) | Q(pk__in=facilitator_ids)).order_by('name', 'username')
        self.fields['users'].queryset = User.objects.filter(Q(is_active=True) | Q(pk__in=user_ids)).order_by(
            'first_name', 'last_name', 'username')
        if instance.pk:
            mirror = mis_project(instance)
            self.initial.setdefault('financiers', list(mirror.financiers.values_list('pk', flat=True)))
            self.initial.setdefault('administrative_levels', list(mirror.administrative_levels.values_list('pk', flat=True)))
            self.initial['status'] = instance.status or 'ACTIVE'
        else:
            self.initial.setdefault('inherit_from_parent', True)
            if current_user is not None:
                # la personne qui crée le projet peut le sélectionner ensuite
                self.initial.setdefault('users', [current_user.pk])
        self.inherited = {'facilitators': 0, 'users': 0}

    def clean_administrative_levels(self):
        levels = self.cleaned_data['administrative_levels']
        if levels:
            levels = AdministrativeLevel.objects.filter(id__in=expand_administrative_levels([o.id for o in levels]))
        return levels

    def clean(self):
        cleaned = super().clean()
        parent = cleaned.get('parent')
        if parent and cleaned.get('inherit_from_parent'):
            for kind in ('facilitators', 'users'):
                chosen = list(cleaned.get(kind) or [])
                chosen_ids = {o.pk for o in chosen}
                extra = [o for o in getattr(parent, kind).all() if o.pk not in chosen_ids]
                if extra:
                    cleaned[kind] = chosen + extra
                    self.inherited[kind] = len(extra)
        return cleaned

    def save_links(self, project):
        """Après l'enregistrement du projet : facilitateurs et utilisateurs (DCC), financeurs, niveaux et cycles
        (COSOMIS)."""
        project.facilitators.set(self.cleaned_data.get('facilitators') or [])
        project.users.set(self.cleaned_data.get('users') or [])
        save_cosomis_fields(project, self.cleaned_data.get('financiers') or [],
                            self.cleaned_data.get('administrative_levels') or [])
