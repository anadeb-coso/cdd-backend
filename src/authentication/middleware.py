from django.shortcuts import render
from django.urls import reverse

# Restriction serveur pour les Facilitator connectés au Web DCC (voir
# authentication.functions.ensure_facilitator_user, dashboard/templates/layouts/sidebar.html) :
# la sidebar cache déjà les menus non autorisés, mais ça n'empêche pas d'atteindre une page en
# tapant son URL directement — cette middleware est le vrai gardien, côté serveur.
#
# N'agit QUE sur ce qui est sous le namespace `dashboard` (resolver_match.namespaces[0] ==
# "dashboard") : les API REST (/api/, /authentication/ racine, /process_manager/ racine,
# /attachments/, utilisées par le mobile et divers JS), l'admin Django (déjà protégé nativement par
# `is_staff`, laissé `False` par `ensure_facilitator_user`) et les routes utilitaires (health/,
# i18n/, static/, media/, profile/ non namespacé) ne sont volontairement PAS touchés — ce ne sont
# pas des "menus" du dashboard, les toucher risquerait de casser le mobile/des intégrations sans
# aucun bénéfice pour cette demande.
FACILITATOR_GROUP_NAMES = ["CommunityFacilitator", "TechnicalFacilitator"]

# Namespaces AUTORISÉS EN BLOC (tout ce qui est dessous) — un menu = un namespace complet,
# cf. plan pour la correspondance avec les 8 menus demandés. `statistics` sert de backend d'export
# à Rapports (appelé depuis les templates reports/pages/*), pas un menu en soi.
ALLOWED_NAMESPACE_PREFIXES = [
    ("dashboard", "reports"),
    ("dashboard", "administrative_levels"),  # inclut "Documents", même app
    ("dashboard", "planning"),
    ("dashboard", "funnel"),
    ("dashboard", "storeapp"),
    ("dashboard", "news"),
    ("dashboard", "statistics"),
    ("dashboard", "task_cycle"),  # menu "Tâches (cycle DCC)", gated par groups_collectors
]

# Vues PRÉCISES autorisées dans des namespaces par ailleurs bloqués (dépendances cross-namespace
# réelles des pages ci-dessus, trouvées en cherchant tous les {% url %}/ajax de leurs templates —
# cf. plan). Le reste de ces namespaces (ex. `facilitators:list`/`create`, `process_manager:tasks:*`
# = "Investment cycle", `authentication:users`) reste bloqué.
ALLOWED_VIEW_NAMES = {
    "dashboard:authentication:login",
    "dashboard:authentication:logout",
    # Sélection de projet : PageMixin.dispatch (dashboard/mixins.py) y redirige TOUT utilisateur
    # authentifié sans projet en session, Facilitator inclus — la bloquer créerait une boucle.
    "dashboard:process_manager:list",
    "dashboard:process_manager:validate_invalidate_task",
    "dashboard:process_manager:complete_uncomplete_task",
    "dashboard:process_manager:get_choices_for_next_phases_activities_tasks",
    "dashboard:process_manager:get_choices_for_next_phases_activities_tasks_by_id",
    "dashboard:facilitators:task_list",
    "dashboard:facilitators:task_comments",
    "dashboard:facilitators:task_detail_modal",
    "dashboard:facilitators:facilitator_percent",
    "dashboard:facilitators:facilitators_percent",
    "dashboard:facilitators:export_fc_to_excel",
}

# Endpoint générique de suppression d'objet par nom de modèle (cdd/urls.py, DeleteObjectFormView) —
# hors du namespace `dashboard` (chemin racine sans namespace), donc jamais concerné par les règles
# ci-dessus ; bloqué ici explicitement par prudence (aucun des 8 menus ne s'appuie dessus).
ALWAYS_BLOCKED_VIEW_NAMES = {"object_deletion_form"}


def _is_facilitator_only(user):
    if not user or not user.is_authenticated or user.is_superuser or user.is_staff:
        return False
    return user.groups.filter(name__in=FACILITATOR_GROUP_NAMES).exists()


class FacilitatorMenuAccessMiddleware:
    """Restreint un utilisateur Facilitator (groupe CommunityFacilitator/TechnicalFacilitator,
    ni superuser ni staff) aux 8 menus autorisés du dashboard — cf. commentaire de module."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not _is_facilitator_only(getattr(request, "user", None)):
            return None

        match = request.resolver_match
        if match is None:
            return None

        if match.view_name in ALWAYS_BLOCKED_VIEW_NAMES:
            return self._deny(request)
        if match.view_name in ALLOWED_VIEW_NAMES:
            return None

        namespaces = tuple(match.namespaces)
        if any(namespaces[: len(prefix)] == prefix for prefix in ALLOWED_NAMESPACE_PREFIXES):
            return None
        if namespaces[:1] != ("dashboard",):
            return None  # hors du dashboard -> hors périmètre de cette middleware

        return self._deny(request)

    def _deny(self, request):
        return render(request, "common/facilitator_access_denied.html", status=404, context={
            "home_url": reverse("dashboard:reports:reports:index"),
        })
