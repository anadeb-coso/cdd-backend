"""Galerie « Ouvrages » (menu Galerie) : fichiers (photos, documents) des sous-projets dont l'infrastructure n'est
pas abandonnée (`infrastructure_deleted` différent de vrai), filtrables par projet, secteur, type, désignation,
type de travaux, étape, localité et type de fichier.

Même présentation que la galerie « Cycle d'investissement » (/administrative-levels/documents/) : la page étend son
gabarit (grille, défilement infini, visionneuse, cascade Région > ... > Village).

Lecture en SQL direct : le modèle `subprojects.Subproject` du CDD ne déclare que quelques colonnes de la table du SIG
(base commune). Secteur, type, désignation et type de travaux sont des libellés (colonnes texte)."""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db import connection
from django.urls import reverse
from django.utils.translation import gettext_lazy
from django.views import generic

from dashboard.mixins import PageMixin
from process_manager.project_access import visible_projects
from .views_doc import (GALLERY_PAGE_SIZE, GEO_KEYS, GEO_LABELS, GEO_LEVELS, _adm_queryset, _int_or_none,
                        attachment_extension, attachment_kind)

NOT_DELETED = "s.infrastructure_deleted IS NOT TRUE"

# filtres « libellé » : paramètre GET -> (colonne, titre)
TEXT_FILTERS = [
    ("sector", "s.subproject_sector", gettext_lazy("Sector")),
    ("subproject_type", "s.type_of_subproject", gettext_lazy("Type of subproject")),
    ("designation", "s.subproject_type_designation", gettext_lazy("Designation")),
    ("works_type", "s.works_type", gettext_lazy("Works type")),
]


def _rows(sql, params=()):
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        columns = [c[0] for c in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _descendant_ids(adm_id):
    """Le niveau et tous ses descendants (village -> lui-même)."""
    ids, frontier = {adm_id}, [adm_id]
    while frontier:
        frontier = list(_adm_queryset().filter(parent_id__in=frontier).values_list('id', flat=True))
        frontier = [i for i in frontier if i not in ids]
        ids.update(frontier)
    return ids


class WorksGalleryView(PageMixin, LoginRequiredMixin, generic.TemplateView):
    template_name = "administrative_levels/works/works.html"
    grid_template_name = "administrative_levels/documents/_grid.html"
    title = gettext_lazy("Works")
    active_level1 = 'gallery'
    active_level2 = 'works'

    # -- filtres -------------------------------------------------------------------------------------------------
    def geo_scope(self):
        """Niveau géographique le plus fin choisi (village, sinon canton, ...)."""
        for key in reversed(GEO_KEYS):
            adm_id = _int_or_none(self.request.GET.get(key))
            if adm_id:
                adm = _adm_queryset().filter(id=adm_id).first()
                if adm:
                    return adm
        return None

    def where(self):
        params = self.request.GET
        clauses, values = [NOT_DELETED, "COALESCE(f.url, '') <> ''", "f.url NOT LIKE 'file:%%'"], []
        project_id = _int_or_none(params.get("project"))
        if project_id:
            clauses.append("EXISTS (SELECT 1 FROM subprojects_subproject_projects sp "
                           "WHERE sp.subproject_id = s.id AND sp.project_id = %s)")
            values.append(project_id)
        for key, column, _label in TEXT_FILTERS:
            if params.get(key):
                clauses.append(f"{column} = %s")
                values.append(params[key])
        if params.get("step"):
            clauses.append("st.wording = %s")
            values.append(params["step"])
        kind = params.get("type")
        if kind == "Photo":
            clauses.append("(f.file_type ILIKE 'image%%')")
        elif kind == "Document":
            clauses.append("(f.file_type IS NULL OR f.file_type NOT ILIKE 'image%%')")
        search = (params.get("q") or "").strip()
        if search:
            clauses.append("(s.full_title_of_approved_subproject ILIKE %s OR CAST(s.number AS TEXT) ILIKE %s "
                           "OR f.name ILIKE %s)")
            values += [f"%{search}%"] * 3
        scope = self.geo_scope()
        if scope:
            ids = list(_descendant_ids(scope.id))
            clauses.append("(s.location_subproject_realized_id = ANY(%s) OR s.canton_id = ANY(%s) OR EXISTS ("
                           "SELECT 1 FROM subprojects_subproject_list_of_beneficiary_villages bv "
                           "WHERE bv.subproject_id = s.id AND bv.administrativelevel_id = ANY(%s)))")
            values += [ids, ids, ids]
        return " AND ".join(clauses), values

    FROM = ("FROM subprojects_subprojectfile f "
            "JOIN subprojects_subproject s ON s.id = f.subproject_id "
            "LEFT JOIN subprojects_subprojectstep st ON st.id = f.subproject_step_id ")

    # -- page --------------------------------------------------------------------------------------------------------
    def get_template_names(self):
        if self.request.headers.get("HX-Request") == "true":
            return [self.grid_template_name]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        where, values = self.where()
        total = _rows(f"SELECT COUNT(*) AS n {self.FROM} WHERE {where}", values)[0]["n"]
        page_number = max(_int_or_none(self.request.GET.get("page")) or 1, 1)
        paginator = Paginator(range(total), GALLERY_PAGE_SIZE)
        is_htmx = self.request.headers.get("HX-Request") == "true"
        items = []
        if not (page_number > paginator.num_pages and is_htmx):
            page = paginator.get_page(min(page_number, paginator.num_pages))
            offset = (page.number - 1) * GALLERY_PAGE_SIZE
            items = _rows(
                f"SELECT f.id, f.name, f.url, f.file_type, f.date_taken, s.id AS subproject_id, s.number, "
                f"s.full_title_of_approved_subproject AS title, s.subproject_sector AS sector, "
                f"s.location_subproject_realized_id AS village_id, s.canton_id, st.wording AS step "
                f"{self.FROM} WHERE {where} ORDER BY f.date_taken DESC NULLS LAST, f.id DESC "
                f"LIMIT %s OFFSET %s", values + [GALLERY_PAGE_SIZE, offset])
            if page.has_next():
                query = self.request.GET.copy()
                query["page"] = page.number + 1
                context["next_page_url"] = f"{self.request.path}?{query.urlencode()}"
        self.add_display_fields(items)

        query_strings_raw = self.request.GET.copy()
        query_strings_raw.pop("page", None)
        context.update({
            "attachments": items,
            "total_count": total,
            "no_results": total == 0,
            "query_strings_raw": query_strings_raw,
            "type_links": self.type_links(),
            "active_filter_chips": self.chips(),
            "geo_selects": self.geo_selects(),
            "works_selects": self.works_selects(),
            "search": self.request.GET.get("q") or "",
        })
        return context

    def add_display_fields(self, items):
        adm_ids = {i["village_id"] for i in items if i["village_id"]} | {i["canton_id"] for i in items if i["canton_id"]}
        names = dict(_adm_queryset().filter(id__in=adm_ids).values_list("id", "name"))
        for item in items:
            uri = str(item["url"])
            village, canton = names.get(item["village_id"]), names.get(item["canton_id"])
            item.update({
                "raw_url": uri.split("?")[0],
                "kind": "image" if str(item["file_type"] or "").startswith("image") else attachment_kind(uri),
                "ext": attachment_extension(uri).upper(),
                "attachment": {"uri": uri},
                "name": item["step"] or item["name"] or "",
                "headquarters_village": village or canton or "",
                "canton": canton or "",
                "location_label": " · ".join(x for x in [
                    f"{GEO_LABELS['village']} : {village}" if village else (f"{GEO_LABELS['canton']} : {canton}" if canton else ""),
                ] if x),
                "task_name": " - ".join(str(x) for x in [item["number"], item["title"]] if x),
                "adm_url": "",
            })

    # -- éléments de la page -------------------------------------------------------------------------------------
    def _url_without(self, *keys, **extra):
        query = self.request.GET.copy()
        for key in ("page",) + keys:
            query.pop(key, None)
        for key, value in extra.items():
            query[key] = value
        return f"{self.request.path}?{query.urlencode()}" if query else self.request.path

    def type_links(self):
        active = self.request.GET.get("type") or "all"
        return {
            "active": active,
            "all": self._url_without("type"),
            "Photo": self._url_without("type", type="Photo"),
            "Document": self._url_without("type", type="Document"),
        }

    def works_selects(self):
        """Listes de filtres : projets visibles par l'utilisateur, libellés présents parmi les ouvrages."""
        params = self.request.GET
        selects = [{
            "key": "project", "label": gettext_lazy("Project"), "selected": params.get("project") or "",
            "options": [(str(p.pk), p.name) for p in visible_projects(self.request.user)],
        }]
        for key, column, label in TEXT_FILTERS:
            options = _rows(f"SELECT DISTINCT {column} AS v FROM subprojects_subproject s "
                            f"WHERE {NOT_DELETED} AND COALESCE({column}, '') <> '' ORDER BY 1")
            selects.append({"key": key, "label": label, "selected": params.get(key) or "",
                            "options": [(o["v"], o["v"]) for o in options]})
        steps = _rows("SELECT DISTINCT st.wording AS v FROM subprojects_subprojectfile f "
                      "JOIN subprojects_subprojectstep st ON st.id = f.subproject_step_id "
                      "WHERE COALESCE(st.wording, '') <> '' ORDER BY 1")
        selects.append({"key": "step", "label": gettext_lazy("Step"), "selected": params.get("step") or "",
                        "options": [(o["v"], o["v"]) for o in steps]})
        return selects

    def geo_selects(self):
        chain, adm = {}, self.geo_scope()
        while adm is not None:
            key = dict((t, k) for k, t in GEO_LEVELS).get(adm.type)
            if key:
                chain[key] = adm
            adm = adm.parent
        selects, parent = [], None
        for key, adm_type in GEO_LEVELS:
            if key == "region":
                options = _adm_queryset().filter(type=adm_type)
            elif parent is not None:
                options = _adm_queryset().filter(parent_id=parent.id, type=adm_type)
            else:
                options = _adm_queryset().none()
            selected = chain.get(key)
            selects.append({"key": key, "label": GEO_LABELS[key], "selected": selected.id if selected else None,
                            "options": list(options.order_by("name").values_list("id", "name")),
                            "disabled": key != "region" and parent is None})
            parent = selected
        return selects

    def chips(self):
        params, chips = self.request.GET, []
        project_id = _int_or_none(params.get("project"))
        if project_id:
            project = visible_projects(self.request.user).filter(pk=project_id).first()
            chips.append({"label": project.name if project else project_id, "remove_url": self._url_without("project")})
        for key, _column, label in TEXT_FILTERS + [("step", None, gettext_lazy("Step"))]:
            if params.get(key):
                chips.append({"label": f"{label} : {params[key]}", "remove_url": self._url_without(key)})
        scope = self.geo_scope()
        if scope:
            chips.append({"label": scope.name, "remove_url": self._url_without(*GEO_KEYS)})
        if params.get("q"):
            chips.append({"label": f"« {params['q']} »", "remove_url": self._url_without("q")})
        return chips
