"""Page « Projets » du Web DCC (superutilisateurs) : création et modification d'un projet avec tous ses champs
(facilitateurs, utilisateurs, financeurs, niveaux administratifs…), comme dans COSOMIS.

Accessible depuis la sélection de projet, donc sans projet en session : pas de PageMixin (qui y renvoie)."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy
from django.views import generic

from process_manager.models import Project

from .forms import ProjectFullForm


def save_project_form(request, form):
    """Projet (et son document CouchDB, cf. Project.save), puis tous ses liens, dans une transaction."""
    with transaction.atomic():
        project = form.save(commit=False)
        project.status = form.cleaned_data['status']
        project.save()
        form.save_links(project)
    if form.inherited['facilitators'] or form.inherited['users']:
        messages.info(request, gettext_lazy("%(facilitators)s facilitator(s) and %(users)s user(s) of the parent project "
                                            "were also linked.") % form.inherited)
    messages.success(request, gettext_lazy("The project %(name)s has been saved.") % {'name': project.name})
    return project


class ProjectFormView(LoginRequiredMixin, UserPassesTestMixin, generic.View):
    template_name = 'process_manager/project_form.html'

    def test_func(self):
        return self.request.user.is_superuser

    def get_project(self):
        return get_object_or_404(Project, pk=self.kwargs['pk']) if 'pk' in self.kwargs else None

    def render_form(self, form, project):
        return render(self.request, self.template_name, {
            'form': form, 'project': project,
            'title': gettext_lazy('Update the project') if project else gettext_lazy('Create a project'),
            'projects': Project.objects.order_by('name'),
        })

    def get(self, request, *args, **kwargs):
        project = self.get_project()
        return self.render_form(ProjectFullForm(instance=project, current_user=request.user), project)

    def post(self, request, *args, **kwargs):
        project = self.get_project()
        form = ProjectFullForm(request.POST, instance=project, current_user=request.user)
        if not form.is_valid():
            return self.render_form(form, project)
        project = save_project_form(request, form)
        return redirect('dashboard:process_manager:project_update', pk=project.pk)
