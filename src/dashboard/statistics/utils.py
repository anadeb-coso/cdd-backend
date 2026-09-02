import unicodedata
import re


def safe_get(lst, index, default={}):
    try:
        return {k: v for k, v in lst[index].items() if v is not None}
    except IndexError:
        return default
    


def normaliser_chaine(chaine):
    chaine = chaine.upper() # Mettre en majuscule
    
    chaine = ''.join(
        c for c in unicodedata.normalize('NFD', chaine)
        if unicodedata.category(c) != 'Mn'
    ) # Suppression des accents
    
    chaine = re.sub(r'[^A-Z0-9]', '', chaine) # Suppression de tous les caractères sauf les lettres et chiffres
    
    return chaine

def comparer_chaines(str1, *str2):
    normalized_str1 = normaliser_chaine(str1)
    for s in str2:
        if normalized_str1 == normaliser_chaine(s):
            return True
    return False


def resolve_project_context(request):
    """Contexte projet pour les exports.

    Renvoie un dict {project_id, project_name, project_couch_id, project_mis_id,
    cycle_id, cycle_couch_id}. Par défaut les valeurs de session ; si la requête porte
    ``?project=<nom>`` (ou ``?project_name=``), on les résout pour ce projet CDD afin de
    permettre un export "par projet" sans changer le projet de session.
    """
    session = request.session
    ctx = {
        'project_id': session.get('project_id'),
        'project_name': session.get('project_name'),
        'project_couch_id': session.get('project_couch_id'),
        'project_mis_id': session.get('project_mis_id'),
        'cycle_id': session.get('cycle_id'),
        'cycle_couch_id': session.get('cycle_couch_id'),
    }

    override = request.GET.get('project') or request.GET.get('project_name')
    if not override or override == ctx['project_name']:
        return ctx

    from process_manager.models import Cycle, Project
    from subprojects.models import Project as MisProject
    from cdd.call_objects_from_other_db import mis_objects_call

    cdd_project = Project.objects.filter(name=override).first()
    if not cdd_project:
        return ctx

    cycle = Cycle.objects.filter(project=cdd_project).order_by('order').first()
    mis_project = mis_objects_call.filter_objects(MisProject, name=cdd_project.name).first()

    ctx.update({
        'project_id': cdd_project.id,
        'project_name': cdd_project.name,
        'project_couch_id': cdd_project.couch_id,
        'project_mis_id': mis_project.id if mis_project else ctx['project_mis_id'],
        'cycle_id': cycle.id if cycle else ctx['cycle_id'],
        'cycle_couch_id': cycle.couch_id if cycle else ctx['cycle_couch_id'],
    })
    return ctx


def cdd_projects_for_request(request):
    """Projets CDD proposés aux exports "par projet".

    Priorité à l'arborescence du projet de session (ex. COSO -> COSO, FA-COSO), sinon les
    projets auxquels l'utilisateur est rattaché, sinon tous.
    """
    from process_manager.models import Project

    tree_names = request.session.get('tree_structure_projects_names')
    if tree_names:
        projects = Project.objects.filter(name__in=tree_names)
    else:
        projects = Project.objects.filter(users=request.user)
        if not projects.exists():
            projects = Project.objects.all()
    return projects.order_by('name')