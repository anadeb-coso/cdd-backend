"""Projets proposés dans les listes de choix : seulement ceux où l'utilisateur connecté intervient
(Project.users), tous pour un super-administrateur."""
from process_manager.models import Project


def visible_projects(user):
    if user is not None and getattr(user, 'is_superuser', False):
        return Project.objects.order_by('name')
    if user is None or not getattr(user, 'is_authenticated', False):
        return Project.objects.none()
    return Project.objects.filter(users=user).distinct().order_by('name')


def restrict_projects_field(form, user, field_name='projects'):
    """Limite le champ de choix `field_name` du formulaire aux projets visibles par `user`."""
    field = form.fields.get(field_name)
    if field is not None:
        field.queryset = visible_projects(user)
    return form


def keep_hidden_projects(user, current, chosen):
    """Projets à enregistrer : les choix faits + les projets déjà liés que `user` ne voit pas dans la liste
    (sinon un administrateur limité retirerait sans le savoir les projets des autres)."""
    chosen_ids = {p.pk if hasattr(p, 'pk') else int(p) for p in chosen or []}
    if user is not None and getattr(user, 'is_superuser', False):
        return chosen_ids
    visible_ids = set(visible_projects(user).values_list('pk', flat=True))
    current_ids = {p.pk if hasattr(p, 'pk') else int(p) for p in current or []}
    return chosen_ids | (current_ids - visible_ids)
