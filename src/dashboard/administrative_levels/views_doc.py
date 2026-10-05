from django.contrib.auth.hashers import make_password
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.shortcuts import get_object_or_404
from urllib.parse import urlencode
from django.urls import reverse
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy
from django.utils import translation
from django.views import generic
from rest_framework import response, generics as rest_generics
from datetime import datetime
from django.core.paginator import Paginator
from django.db.models import Q, QuerySet
import re as re_module
from functools import reduce
import io
import os
import zipfile
import requests
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from django.http import JsonResponse
from django.urls import NoReverseMatch

from cdd.my_librairies.download_file import display_filename_with_suffix
from dashboard.templatetags.custom_tags import attachment_location_label

from process_manager.models import Phase, Activity, Task, Project
from authentication.models import Facilitator
from dashboard.facilitators.forms import FacilitatorForm, FilterTaskForm, UpdateFacilitatorForm, FilterFacilitatorForm
from dashboard.mixins import AJAXRequestMixin, PageMixin, JSONResponseMixin
from no_sql_client import NoSQLClient
from dashboard.utils import (
    sync_geographicalunits_with_cvd_on_facilittor, sync_tasks
)
from authentication.permissions import (
    CDDSpecialistPermissionRequiredMixin, SuperAdminPermissionRequiredMixin,
    AdminPermissionRequiredMixin
    )
from dashboard.facilitators.functions import (
    get_cvds, get_cvd_name_by_village_id, is_village_principal, single_task_by_cvd,
    clear_facilitator_docs_by_administrativelevels_and_save_to_backup_db, 
    get_headquarters_village_id
)
from administrativelevels import models as administrativelevels_models
from assignments.models import AssignAdministrativeLevelToFacilitator
from dashboard.administrative_levels.functions import get_administrative_levels_under_json, get_cascade_villages_by_administrative_level_id
from cdd.functions import datetime_complet_str, exists_id_in_a_dict
from cdd.call_objects_from_other_db import mis_objects_call
from authentication.functions import get_assign_adl_by_facilitatr
from dashboard.tasks import sync_celery_tasks_re
from dashboard.facilitators.views import FacilitatorMixin
from dashboard.administrative_levels.forms import AttachmentFilterForm
from cdd.my_librairies.functions import strip_accents, get_datas_dict
from dashboard.reports.constants import IGNORES, PEULS
from subprojects.models import Project as MisProject




# --- Galerie /administrative-levels/documents/ -------------------------------
#
# Par défaut (aucun paramètre `type`, aucun filtre de processus) : les PAV
# (plans d'actions villageois) et le PAC (plan d'actions cantonal) d'un canton —
# comportement historique de la page. Les boutons « Tout / Photos / Documents »
# (paramètre `type`) et les filtres Région > Préfecture > Commune > Canton >
# Village et Phase > Activité > Tâche donnent accès à TOUTES les pièces jointes
# des tâches (mêmes principes d'affichage que la galerie du PDL,
# `/administrative-levels/attachments/` : grille, pastilles de filtres actifs,
# modal de filtres, mode sélection, visionneuse, défilement infini).
#
# Les pièces jointes vivent dans les documents `task` des bases CouchDB des
# facilitateurs (champ `attachments`, une entrée = `{name, type, attachment:
# {uri}}`) : pas de modèle SQL, pas d'id stable — une pièce jointe est
# identifiée par son URL S3.

# Tâches (sql_id) portant le document du plan d'actions (PAV/PAC), pour les 3
# projets : COSO (45, 47), FA-COSO (130, 132), PURS (94, 96).
PAV_PAC_TASK_SQL_IDS = [45, 47, 130, 132, 94, 96]
PAV_PAC_ATTACHMENT_NAME_PART = "document du plan d'actions"
PAC_ATTACHMENT_NAME = "Télecharger le document du plan d'actions cantonales finalisé".lower()

# Canton affiché quand aucun filtre géographique n'est choisi (historique).
DEFAULT_CANTON_ID = 1973

# Taille d'une page de la grille (chargement suivant au défilement, htmx).
GALLERY_PAGE_SIZE = 36

# Valeurs du paramètre `type`. Absent -> PAV/PAC (défaut historique).
TYPE_PAV_PAC = "pav_pac"
TYPE_ALL = "all"
TYPE_PHOTO = "Photo"
TYPE_DOCUMENT = "Document"

# Niveaux géographiques, du plus large au plus fin : (paramètre GET, type en base).
GEO_LEVELS = [
    ("region", "Region"),
    ("prefecture", "Prefecture"),
    ("commune", "Commune"),
    ("canton", "Canton"),
    ("village", "Village"),
]
GEO_KEYS = [key for key, _ in GEO_LEVELS]
GEO_LABELS = {
    "region": gettext_lazy("Region"),
    "prefecture": gettext_lazy("Prefecture"),
    "commune": gettext_lazy("Commune"),
    "canton": gettext_lazy("Canton"),
    "village": gettext_lazy("Village"),
}
# Ancien paramètre de la page (id du canton) : toujours accepté (liens existants).
LEGACY_CANTON_PARAM = "administrative_level"

# Filtres de processus, du plus large au plus fin (ids SQL).
PROCESS_KEYS = ["phase", "activity", "task"]
# Filtre sur le libellé de la pièce jointe (champ `name`), cf. attachment_label_key.
LABEL_PARAM = "label"
PROCESS_LABELS = {
    "phase": gettext_lazy("Phase"),
    "activity": gettext_lazy("Activity"),
    "task": gettext_lazy("Task"),
}

IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "heic", "heif"}
WORD_EXTENSIONS = {"doc", "docx"}
# Autres formats Office : affichables par la visionneuse Office Web, pas de conversion.
OFFICE_EXTENSIONS = {"xls", "xlsx", "ppt", "pptx"}

# Lecture des bases CouchDB des facilitateurs : une requête par base, en
# parallèle (lecture seule, I/O réseau) et bornée dans le temps — même principe
# que dashboard/reports/excel_csv/fc_situation.py (une base lente ou injoignable
# ne doit pas bloquer toute la page).
_COUCHDB_TIMEOUT = 30
_SCAN_MAX_WORKERS = 16
# Seuls les champs utiles à la galerie (les docs `task` portent aussi
# formulaires/réponses/historiques, inutiles ici et volumineux).
_TASK_DOC_FIELDS = [
    "_id", "sql_id", "name", "administrative_level_id", "administrative_level_name",
    "phase_name", "activity_name", "attachments",
]


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def attachment_extension(uri):
    """Extension (minuscules, sans le point) du fichier d'une URL, "" si aucune."""
    filename = str(uri or "").split("?")[0].rsplit("/", 1)[-1]
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def attachment_kind(uri):
    """Nature d'une pièce jointe d'après l'extension de son URL : "image", "pdf",
    "word", "office" ou "other". Le champ `type` (MIME) des pièces jointes n'est
    pas fiable (ex. "image/jpeg" déclaré pour le document Word du PAV)."""
    ext = attachment_extension(uri)
    if ext == "pdf":
        return "pdf"
    if ext in WORD_EXTENSIONS:
        return "word"
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in OFFICE_EXTENSIONS:
        return "office"
    return "other"


def attachment_label_key(name):
    """Clé de comparaison d'un libellé de pièce jointe : sans accents, casse ni
    espaces superflus — les mêmes libellés existent avec des variantes de saisie
    selon les tâches/projets (« Télecharger » / « Télécharger »)."""
    return " ".join(strip_accents(str(name or "")).split()).casefold()


def _adm_queryset():
    return administrativelevels_models.AdministrativeLevel.objects.using('mis')


def _get_adm(value, adm_type=None):
    adm_id = _int_or_none(value)
    if adm_id is None:
        return None
    qs = _adm_queryset().filter(id=adm_id)
    if adm_type:
        qs = qs.filter(type=adm_type)
    return qs.first()


def _geo_key_for_type(adm_type):
    for key, _type in GEO_LEVELS:
        if _type == adm_type:
            return key
    return None


def _scope_villages(adm):
    """Villages couverts par un niveau administratif (lui-même si c'est un
    village) : {id: {"name", "canton_id", "canton_name", "cvd_id"}}.
    Un aller-retour SQL par niveau descendu (au plus 4)."""
    fields = ("id", "type", "name", "parent_id", "parent__name", "cvd_id")
    if adm.type == "Village":
        rows = list(_adm_queryset().filter(id=adm.id).values(*fields))
    else:
        rows, frontier, depth = [], [adm.id], 0
        while frontier and depth < len(GEO_LEVELS):
            children = list(_adm_queryset().filter(parent_id__in=frontier).values(*fields))
            rows += [c for c in children if c["type"] == "Village"]
            frontier = [c["id"] for c in children if c["type"] != "Village"]
            depth += 1
    return {
        r["id"]: {
            "name": r["name"],
            "canton_id": r["parent_id"],
            "canton_name": r["parent__name"],
            "cvd_id": r["cvd_id"],
        }
        for r in rows
    }


def _fetch_task_docs(db_name, selector):
    """Exécuté dans un thread du pool : sa propre connexion CouchDB (le client
    `cloudant` n'est pas garanti thread-safe)."""
    try:
        nsc = NoSQLClient(timeout=_COUCHDB_TIMEOUT)
        return nsc.find_all(nsc.get_db(db_name), selector, fields=_TASK_DOC_FIELDS)
    except Exception as exc:  # noqa: BLE001 — une base KO ne doit pas faire échouer la page
        print(f"[documents] base {db_name} ignorée : {exc}")
        return []


class AttachmentListView(PageMixin, LoginRequiredMixin, generic.TemplateView):
    template_name = "administrative_levels/documents/attachments.html"
    grid_template_name = "administrative_levels/documents/_grid.html"
    context_object_name = "attachments"
    title = gettext_lazy("Gallery")
    active_level1 = 'documents'
    paginate_by = GALLERY_PAGE_SIZE
    no_sql_db_name = None
    administrative_level = None
    canton = None

    def post(self, request, *args, **kwargs):
        url = reverse("dashboard:administrative_levels:documents")
        final_querystring = request.GET.copy()

        for key, value in request.GET.items():
            if (
                key in request.POST
                and value != request.POST[key]
                and request.POST[key] != ""
            ):
                final_querystring.pop(key)

        post_dict = request.POST.copy()
        post_dict.update(final_querystring)
        post_dict.pop("csrfmiddlewaretoken")
        if "reset-hidden" in post_dict and post_dict["reset-hidden"] == "true":
            return redirect(url)

        for key, value in request.POST.items():
            if value == "":
                post_dict.pop(key)
        final_querystring.update(post_dict)
        if final_querystring:
            url = "{}?{}".format(url, urlencode(final_querystring))
        return redirect(url)

    # -- Lecture des filtres ---------------------------------------------------

    def _params(self):
        return self.request.GET

    def get_gallery_mode(self):
        params = self._params()
        requested = params.get("type") or ""
        if requested in (TYPE_ALL, TYPE_PHOTO, TYPE_DOCUMENT):
            return requested
        # Un filtre phase/activité/tâche/libellé n'a de sens que sur toutes les
        # pièces jointes : le choisir depuis la vue PAV/PAC bascule sur « Tout ».
        if any(params.get(key) for key in PROCESS_KEYS + [LABEL_PARAM]):
            return TYPE_ALL
        return TYPE_PAV_PAC

    def get_geo_scope(self):
        """(niveau administratif couvert, True si c'est le canton par défaut)."""
        if not hasattr(self, "_geo_scope"):
            params = self._params()
            scope = None
            for key, adm_type in reversed(GEO_LEVELS):
                if params.get(key):
                    scope = _get_adm(params.get(key), adm_type)
                    if scope is not None:
                        break
            if scope is None and params.get(LEGACY_CANTON_PARAM):
                # Ancien paramètre : n'importe quel niveau, comme historiquement.
                scope = _get_adm(params.get(LEGACY_CANTON_PARAM))
            is_default = scope is None
            if is_default:
                scope = (
                    _get_adm(DEFAULT_CANTON_ID)
                    or _adm_queryset().filter(type="Canton").order_by("id").first()
                )
            self._geo_scope = (scope, is_default)
        return self._geo_scope

    def get_task_sql_ids(self):
        """Ids des tâches du filtre phase/activité/tâche le plus fin, None sans filtre."""
        params = self._params()
        task_id = _int_or_none(params.get("task"))
        if task_id is not None:
            return list(Task.objects.filter(id=task_id).values_list("id", flat=True))
        activity_id = _int_or_none(params.get("activity"))
        if activity_id is not None:
            return list(Task.objects.filter(activity_id=activity_id).values_list("id", flat=True))
        phase_id = _int_or_none(params.get("phase"))
        if phase_id is not None:
            return list(Task.objects.filter(phase_id=phase_id).values_list("id", flat=True))
        return None

    # -- Données -----------------------------------------------------------------

    def _scan_attachments(self, task_sql_ids):
        """Pièces jointes synchronisées des docs `task` du périmètre géographique
        (et des tâches `task_sql_ids`, None = toutes), dans l'ordre de lecture des
        bases, SANS autre filtre ni dédoublonnage : liste de dicts (l'entrée
        `attachments` du doc CouchDB, enrichie du village, du canton, de la tâche…)."""
        session = self.request.session
        scope, _is_default = self.get_geo_scope()
        if scope is None or (task_sql_ids is not None and not task_sql_ids):
            return []

        villages = _scope_villages(scope)
        if not villages:
            return []

        project_mis = mis_objects_call.filter_objects(MisProject, name=session.get('project_name'))
        project_mis_id = project_mis.first().id if project_mis.count() >= 1 else 1

        # Bases CouchDB des facilitateurs affectés à ces villages (toutes les
        # affectations du projet, comme historiquement) ; la dernière affectation
        # d'un village donne la base de son lien « Voir le village ».
        assignments = list(
            mis_objects_call.filter_objects(
                AssignAdministrativeLevelToFacilitator,
                administrative_level_id__in=list(villages.keys()),
                project_id=project_mis_id,
            ).order_by("id").values_list("administrative_level_id", "facilitator_id")
        )
        # Ordre des bases = celui de la requête historique (pas de tri) : c'est
        # lui qui décide quelle copie du PAC est gardée quand plusieurs villages
        # du canton la portent.
        facilitator_db_names = list(
            Facilitator.objects.filter(id__in={f for _, f in assignments})
            .exclude(no_sql_db_name__isnull=True).exclude(no_sql_db_name="")
            .values_list("id", "no_sql_db_name")
        )
        db_name_by_facilitator = dict(facilitator_db_names)
        db_name_by_village = {}
        for village_id, facilitator_id in assignments:
            if facilitator_id in db_name_by_facilitator:
                db_name_by_village[village_id] = db_name_by_facilitator[facilitator_id]
        db_names = list(dict.fromkeys(name for _, name in facilitator_db_names))
        if not db_names:
            return []

        village_ids = list(villages.keys())
        selector = {
            "type": "task",
            "project_id": session.get('project_couch_id'),
            "cycle_id": session.get('cycle_couch_id'),
            # `administrative_level_id` est une chaîne dans les docs ; l'entier
            # est accepté aussi par sécurité.
            "administrative_level_id": {"$in": [str(v) for v in village_ids] + village_ids},
            "attachments": {"$elemMatch": {"attachment.uri": {"$exists": True}}},
        }
        if task_sql_ids is not None:
            selector["sql_id"] = {"$in": list(task_sql_ids)}

        # `map` conserve l'ordre des bases (déterministe : qui garde quel PAC).
        with ThreadPoolExecutor(max_workers=min(_SCAN_MAX_WORKERS, len(db_names))) as executor:
            results = list(executor.map(lambda name: _fetch_task_docs(name, selector), db_names))

        entries = []
        for db_name, docs in zip(db_names, results):
            for doc in docs:
                village_id = _int_or_none(doc.get("administrative_level_id"))
                village = villages.get(village_id)
                if village is None:
                    continue
                for attachment in doc.get("attachments") or []:
                    if not isinstance(attachment, dict) or not isinstance(attachment.get("attachment"), dict):
                        continue
                    uri = attachment["attachment"].get("uri")
                    # file:/// = fichier resté sur le téléphone (non synchronisé), non affichable.
                    if not uri or str(uri).startswith("file:"):
                        continue
                    entry = dict(attachment)
                    entry.update({
                        "raw_url": str(uri).split("?")[0],
                        "kind": attachment_kind(uri),
                        "ext": attachment_extension(uri).upper(),
                        "headquarters_village": doc.get("administrative_level_name") or village["name"],
                        "headquarters_village_id": village_id,
                        "village_cvd_id": village["cvd_id"],
                        "canton": village["canton_name"] or "",
                        "canton_id": village["canton_id"],
                        "no_sql_db_name": db_name_by_village.get(village_id) or db_name,
                        "task_sql_id": doc.get("sql_id"),
                        "task_name": doc.get("name") or "",
                        "phase_name": doc.get("phase_name") or "",
                        "activity_name": doc.get("activity_name") or "",
                    })
                    entries.append(entry)
        return entries

    @staticmethod
    def _matches_kind(entry, mode):
        if mode == TYPE_PHOTO:
            return entry["kind"] == "image"
        if mode == TYPE_DOCUMENT:
            return entry["kind"] != "image"
        return True

    @staticmethod
    def _unique_files(entries):
        """Un même fichier peut figurer dans plusieurs bases (village réaffecté,
        tâche partagée entre villages) : gardé une fois (première occurrence)."""
        seen_urls, unique = set(), []
        for entry in entries:
            if entry["raw_url"] not in seen_urls:
                seen_urls.add(entry["raw_url"])
                unique.append(entry)
        return unique

    def get_queryset(self):
        """Toutes les pièces jointes correspondant aux filtres (cf.
        `_scan_attachments`), triées. Réutilisé tel quel par
        DownloadAttachmentsZipView (« Télécharger tout » / « la sélection »)."""
        if hasattr(self, "_items"):
            return self._items

        mode = self.get_gallery_mode()
        scope, _is_default = self.get_geo_scope()
        self.canton = scope
        self.administrative_level_id = scope.id if scope else None

        if mode == TYPE_PAV_PAC:
            entries, cantons_with_pac = [], set()
            for entry in self._scan_attachments(PAV_PAC_TASK_SQL_IDS):
                name = str(entry.get("name") or "").lower()
                if PAV_PAC_ATTACHMENT_NAME_PART not in name:
                    continue
                # Le PAC est le même document pour tous les villages du canton :
                # un seul par canton.
                if name == PAC_ATTACHMENT_NAME:
                    if entry["canton_id"] in cantons_with_pac:
                        continue
                    cantons_with_pac.add(entry["canton_id"])
                entries.append(entry)
        else:
            label_key = attachment_label_key(self._params().get("label"))
            entries = [
                entry for entry in self._scan_attachments(self.get_task_sql_ids())
                if self._matches_kind(entry, mode)
                and (not label_key or attachment_label_key(entry.get("name")) == label_key)
            ]
        items = self._unique_files(entries)

        self._add_villages_names(items)
        if mode == TYPE_PAV_PAC:
            items.sort(key=lambda obj: str(obj["name"]) + str(obj["headquarters_village"]))
        else:
            # Par village, puis dans l'ordre du processus (phase > activité > tâche).
            orders = {
                t_id: (p_order or 0, a_order or 0, t_order or 0)
                for t_id, p_order, a_order, t_order in Task.objects.filter(
                    id__in={i["task_sql_id"] for i in items if i["task_sql_id"]}
                ).values_list("id", "phase__order", "activity__order", "order")
            }
            items.sort(key=lambda obj: (
                str(obj["headquarters_village"]).lower(),
                orders.get(obj["task_sql_id"], (999999, 999999, 999999)),
                str(obj["task_name"]),
                _int_or_none(obj.get("order")) or 0,
                str(obj["name"]),
            ))
        self._items = items
        return items

    def get_label_choices(self):
        """Libellés des pièces jointes du périmètre (géographie, phase/activité/
        tâche, Photos/Documents) — TOUTES les pièces jointes, même en vue PAV/PAC,
        et sans tenir compte du libellé déjà choisi : [{"name", "count"}] triés,
        `count` = nombre de fichiers. Libellés regroupés sans tenir compte des
        accents, de la casse ni des espaces (« Télecharger » = « Télécharger ») ;
        nom affiché = la variante la plus fréquente."""
        mode = self.get_gallery_mode()
        entries = [
            entry for entry in self._scan_attachments(self.get_task_sql_ids())
            if self._matches_kind(entry, mode)
        ]
        counts, variants = defaultdict(int), defaultdict(lambda: defaultdict(int))
        for entry in self._unique_files(entries):
            name = " ".join(str(entry.get("name") or "").split())
            key = attachment_label_key(name)
            if not key:
                continue
            counts[key] += 1
            variants[key][name] += 1
        return [
            {"name": max(variants[key].items(), key=lambda kv: kv[1])[0], "count": counts[key]}
            for key in sorted(counts)
        ]

    @staticmethod
    def _add_villages_names(items):
        """`villages_names` : villages du CVD du village siège, s'il en compte
        plusieurs (« A/B/C »), comme historiquement — en une requête."""
        cvd_ids = {i["village_cvd_id"] for i in items if i["village_cvd_id"]}
        names_by_cvd = defaultdict(list)
        if cvd_ids:
            for cvd_id, name in _adm_queryset().filter(cvd_id__in=cvd_ids).order_by("id").values_list("cvd_id", "name"):
                names_by_cvd[cvd_id].append(name)
        for item in items:
            names = names_by_cvd.get(item["village_cvd_id"], [])
            item["villages_names"] = "/".join(names) if len(names) > 1 else ""

    @staticmethod
    def _add_display_fields(items):
        """Localité affichée (canton si l'intitulé évoque un canton, sinon village
        siège et villages de son CVD — même règle que le nom de fichier au
        téléchargement, cf. attachment_location_label) et lien « Voir le village »
        de la carte et de la visionneuse. Uniquement pour la page affichée."""
        for item in items:
            if "canton" in str(item.get("name") or "").lower():
                item["location_label"] = "{} : {}".format(GEO_LABELS["canton"], item.get("canton") or "")
            else:
                item["location_label"] = "{} : {}{}".format(
                    GEO_LABELS["village"], item.get("headquarters_village") or "",
                    " ({})".format(item["villages_names"]) if item.get("villages_names") else "",
                )
            item["adm_url"] = ""
            if item.get("no_sql_db_name") and item.get("headquarters_village_id"):
                try:
                    item["adm_url"] = "{}?administrative_level={}".format(
                        reverse("dashboard:administrative_levels:detail", args=[item["no_sql_db_name"]]),
                        item["headquarters_village_id"],
                    )
                except NoReverseMatch:
                    pass

    # -- Contexte ----------------------------------------------------------------

    def get_context_data(self, **kwargs):
        context = super(AttachmentListView, self).get_context_data(**kwargs)
        params = self._params()

        items = self.get_queryset()
        mode = self.get_gallery_mode()
        scope, scope_is_default = self.get_geo_scope()

        paginator = Paginator(items, GALLERY_PAGE_SIZE)
        # ?page= invalide ou hors limites : jamais d'erreur. Page complète ->
        # page valide la plus proche ; requête htmx du défilement infini au-delà
        # de la dernière page -> fragment vide (arrête la boucle).
        page_number = max(_int_or_none(params.get("page")) or 1, 1)
        if page_number > paginator.num_pages and self.is_htmx():
            page_obj, attachments = None, []
        else:
            page_obj = paginator.get_page(min(page_number, paginator.num_pages))
            attachments = list(page_obj.object_list)
        self._add_display_fields(attachments)

        query_strings_raw = params.copy()
        query_strings_raw.pop("page", None)

        context["attachments"] = attachments
        context["page_obj"] = page_obj
        context["total_count"] = paginator.count
        context["no_results"] = paginator.count == 0
        if page_obj is not None and page_obj.has_next():
            next_query = query_strings_raw.copy()
            next_query["page"] = page_obj.next_page_number()
            context["next_page_url"] = "{}?{}".format(self.request.path, next_query.urlencode())

        context["query_strings_raw"] = query_strings_raw
        context["gallery_mode"] = mode
        context["type_links"] = self._build_type_links(params, mode)
        context["active_filter_chips"] = self._build_active_chips(params, mode, scope, scope_is_default)
        context["geo_selects"] = self._build_geo_selects(scope)
        context["process_selects"] = self._build_process_selects(params)
        context["selected_label"] = " ".join(str(params.get(LABEL_PARAM) or "").split())
        context["max_zip_files"] = MAX_ZIP_FILES
        context["scope"] = scope
        context["scope_label"] = "{} : {}".format(GEO_LABELS.get(_geo_key_for_type(scope.type), scope.type), scope.name) if scope else ""
        context['administrative_level_id'] = self.administrative_level_id
        context['canton'] = self.canton
        return context

    def is_htmx(self):
        return self.request.headers.get("HX-Request") == "true"

    def get_template_names(self, *args, **kwargs):
        # Défilement infini (htmx) : uniquement le fragment de la page suivante,
        # jamais la page complète (dont les <script> seraient réexécutés).
        if self.is_htmx():
            return [self.grid_template_name]
        return [self.template_name]

    @staticmethod
    def _querystring_without(params, *keys_to_drop):
        clean = params.copy()
        for key in ("page",) + tuple(keys_to_drop):
            clean.pop(key, None)
        for key in list(clean.keys()):
            if clean.get(key) in ("", None):
                clean.pop(key, None)
        encoded = clean.urlencode()
        return "?" + encoded if encoded else "?"

    def _build_type_links(self, params, mode):
        base = self._querystring_without(params, "type")
        separator = "" if base == "?" else "&"
        return {
            # PAV/PAC : les filtres de processus et de libellé n'y ont pas de sens
            # (tâches et pièces jointes fixes).
            TYPE_PAV_PAC: self._querystring_without(params, "type", LABEL_PARAM, *PROCESS_KEYS),
            TYPE_ALL: f"{base}{separator}type={TYPE_ALL}",
            TYPE_PHOTO: f"{base}{separator}type={TYPE_PHOTO}",
            TYPE_DOCUMENT: f"{base}{separator}type={TYPE_DOCUMENT}",
            "active": mode,
        }

    def _build_active_chips(self, params, mode, scope, scope_is_default):
        chips = []
        if mode in (TYPE_PHOTO, TYPE_DOCUMENT):
            label_map = {TYPE_PHOTO: gettext_lazy("Photos"), TYPE_DOCUMENT: gettext_lazy("Documents")}
            chips.append({
                "label": "{} : {}".format(gettext_lazy("Type"), label_map[mode]),
                "remove_url": self._querystring_without(params, "type"),
            })

        if scope_is_default:
            if scope is not None:
                chips.append({
                    "label": "{} : {} ({})".format(GEO_LABELS["canton"], scope.name, gettext_lazy("default")),
                    "remove_url": None,
                })
        else:
            geo_chips = []
            for index, (key, adm_type) in enumerate(GEO_LEVELS):
                adm = _get_adm(params.get(key), adm_type) if params.get(key) else None
                if adm is None:
                    continue
                # Retirer un niveau retire aussi les niveaux plus fins (ses enfants).
                geo_chips.append({
                    "label": "{} : {}".format(GEO_LABELS[key], adm.name),
                    "remove_url": self._querystring_without(params, LEGACY_CANTON_PARAM, *GEO_KEYS[index:]),
                })
            if not geo_chips and scope is not None:
                # Niveau venu de l'ancien paramètre `administrative_level`.
                geo_chips.append({
                    "label": "{} : {}".format(GEO_LABELS.get(_geo_key_for_type(scope.type), scope.type), scope.name),
                    "remove_url": self._querystring_without(params, LEGACY_CANTON_PARAM),
                })
            chips += geo_chips

        if mode != TYPE_PAV_PAC:
            for index, (key, model) in enumerate((("phase", Phase), ("activity", Activity), ("task", Task))):
                obj_id = _int_or_none(params.get(key))
                obj = model.objects.filter(id=obj_id).first() if obj_id is not None else None
                if obj is None:
                    continue
                chips.append({
                    "label": "{} : {}".format(PROCESS_LABELS[key], obj.name),
                    "remove_url": self._querystring_without(params, *PROCESS_KEYS[index:]),
                })
            label = " ".join(str(params.get(LABEL_PARAM) or "").split())
            if label:
                chips.append({
                    "label": "{} : {}".format(gettext_lazy("Label"), label),
                    "remove_url": self._querystring_without(params, LABEL_PARAM),
                })
        return chips

    def _build_geo_selects(self, scope):
        """Listes Région > ... > Village du modal de filtres, pré-remplies côté
        serveur avec la chaîne du niveau affiché (ses ancêtres sélectionnés,
        leurs enfants en options) : pas de cascade AJAX au chargement."""
        chain = {}
        adm = scope
        while adm is not None:
            key = _geo_key_for_type(adm.type)
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
            selects.append({
                "key": key,
                "label": GEO_LABELS[key],
                "options": list(options.order_by("name").values_list("id", "name")),
                "selected": selected.id if selected else None,
                "disabled": key != "region" and parent is None,
            })
            parent = selected
        return selects

    def _build_process_selects(self, params):
        phase_id = _int_or_none(params.get("phase"))
        activity_id = _int_or_none(params.get("activity"))
        task_id = _int_or_none(params.get("task"))
        # Remonte la chaîne quand seul un niveau fin est fourni (ex. ?task=).
        if task_id is not None and (activity_id is None or phase_id is None):
            task = Task.objects.filter(id=task_id).first()
            if task:
                activity_id, phase_id = task.activity_id, task.phase_id
        if activity_id is not None and phase_id is None:
            activity = Activity.objects.filter(id=activity_id).first()
            if activity:
                phase_id = activity.phase_id

        phases = Phase.objects.get_objects_by_general_filtre(request=self.request, attrs=None).order_by("order")
        activities = (
            Activity.objects.filter(phase_id=phase_id).get_objects_by_general_filtre(request=self.request, attrs=None).order_by("order")
            if phase_id is not None else Activity.objects.none()
        )
        tasks = (
            Task.objects.filter(activity_id=activity_id).get_objects_by_general_filtre(request=self.request, attrs=None).order_by("order")
            if activity_id is not None else Task.objects.none()
        )
        return [
            {"key": "phase", "label": PROCESS_LABELS["phase"], "options": list(phases.values_list("id", "name")),
             "selected": phase_id, "disabled": False},
            {"key": "activity", "label": PROCESS_LABELS["activity"], "options": list(activities.values_list("id", "name")),
             "selected": activity_id, "disabled": phase_id is None},
            {"key": "task", "label": PROCESS_LABELS["task"], "options": list(tasks.values_list("id", "name")),
             "selected": task_id, "disabled": activity_id is None},
        ]


class DocumentsFilterChoicesView(LoginRequiredMixin, generic.View):
    """Cascade des listes du modal de filtres de la galerie : enfants du niveau
    choisi (`?type=region&value=<id>` -> préfectures, ..., `canton` -> villages,
    `phase` -> activités, `activity` -> tâches du projet/cycle actif)."""

    def get(self, request, *args, **kwargs):
        select_type = request.GET.get("type")
        value = _int_or_none(request.GET.get("value"))
        values = []
        if value is not None:
            if select_type in GEO_KEYS[:-1]:
                child_type = GEO_LEVELS[GEO_KEYS.index(select_type) + 1][1]
                values = list(
                    _adm_queryset().filter(parent_id=value, type=child_type).order_by("name").values("id", "name")
                )
            elif select_type == "phase":
                values = list(
                    Activity.objects.filter(phase_id=value)
                    .get_objects_by_general_filtre(request=request, attrs=None)
                    .order_by("order").values("id", "name")
                )
            elif select_type == "activity":
                values = list(
                    Task.objects.filter(activity_id=value)
                    .get_objects_by_general_filtre(request=request, attrs=None)
                    .order_by("order").values("id", "name")
                )
        return JsonResponse({"values": values})


class DocumentsLabelChoicesView(PageMixin, LoginRequiredMixin, generic.View):
    """Liste « Libellé » du modal de filtres de la galerie : libellés des pièces
    jointes du périmètre décrit par la query string (mêmes paramètres que la
    page : région…village, phase/activité/tâche, type), chacun avec son nombre de
    fichiers (AttachmentListView.get_label_choices). Chargée à la demande
    (ouverture du modal, changement d'un filtre) plutôt qu'à chaque affichage de
    la page : elle impose de lire toutes les pièces jointes du périmètre, même en
    vue PAV/PAC."""

    def get(self, request, *args, **kwargs):
        lister = AttachmentListView()
        lister.request = request
        return JsonResponse({"values": lister.get_label_choices()})


# Nombre max de fichiers zippés en une seule requête (synchrone, pas de job
# d'arrière-plan fiable disponible dans ce projet — cf. mémoire des sessions
# précédentes) : évite une requête HTTP qui traîne indéfiniment sur une trop
# grosse sélection.
MAX_ZIP_FILES = 200


class DownloadAttachmentsZipView(PageMixin, LoginRequiredMixin, generic.View):
    """« Télécharger tout » (GET, ré-exécute EXACTEMENT le même filtrage que
    la page — AttachmentListView.get_queryset — pour garantir un zip complet
    et cohérent avec les filtres actifs, canton compris, plutôt que de
    dépendre d'une énumération côté client potentiellement incomplète) et
    « Télécharger la sélection » (POST, uniquement les fichiers cochés,
    identifiés par leur URL S3 — ces pièces jointes n'ont pas d'id stable,
    cf. AttachmentListView.get_queryset)."""

    def get(self, request, *args, **kwargs):
        lister = AttachmentListView()
        lister.request = request
        attachments = lister.get_queryset()
        items = [
            (a["attachment"]["uri"], self._desired_name(a, a["attachment"]["uri"]))
            for a in attachments
            if a.get("attachment", {}).get("uri") and "file:///data" not in a["attachment"]["uri"]
        ]
        return self._build_zip_response(items)

    def post(self, request, *args, **kwargs):
        urls = [u for u in request.POST.getlist('urls') if u]
        # Renommage "<intitulé> (<village/canton>)" (même règle que le
        # téléchargement individuel, cf. _attachment_card_content.html) :
        # les pièces jointes n'ont pas d'id/nom stable transmis par la case à
        # cocher (juste l'URL), donc on ré-exécute le même filtrage que la
        # page pour retrouver le nom + village/canton de chaque fichier
        # sélectionné — même source de vérité que « Télécharger tout ».
        lister = AttachmentListView()
        lister.request = request
        attachments = lister.get_queryset()
        by_url = {
            a["attachment"]["uri"]: a for a in attachments
            if a.get("attachment", {}).get("uri")
        }
        items = [(u, self._desired_name(by_url.get(u), u)) for u in urls]
        return self._build_zip_response(items)

    @staticmethod
    def _desired_name(attachment, url):
        if not attachment:
            return None
        name = attachment.get("name")
        if not name:
            return None
        location = attachment_location_label(attachment)
        return display_filename_with_suffix(name, location, url)

    def _build_zip_response(self, items):
        # Déduplique par URL en préservant l'ordre (une même pièce jointe
        # peut apparaître plusieurs fois si le filtre couvre plusieurs
        # villages partageant le même document, ex. plan d'actions cantonal).
        seen = {}
        for url, desired_name in items:
            if url and url not in seen:
                seen[url] = desired_name
        if not seen:
            return HttpResponseBadRequest("Aucun fichier à télécharger.")
        items = list(seen.items())[:MAX_ZIP_FILES]

        buffer = io.BytesIO()
        used_names = set()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for url, desired_name in items:
                try:
                    resp = requests.get(url.split("?")[0], stream=True, timeout=30)
                    if resp.status_code != 200:
                        continue
                except Exception:
                    continue
                name = desired_name or (url.split("/")[-1].split("?")[0] or "fichier")
                base, ext = os.path.splitext(name)
                candidate, n = name, 1
                while candidate in used_names:
                    candidate = f"{base}_{n}{ext}"
                    n += 1
                used_names.add(candidate)
                zf.writestr(candidate, resp.content)

        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type="application/zip")
        response['Content-Disposition'] = 'attachment; filename="documents.zip"'
        return response