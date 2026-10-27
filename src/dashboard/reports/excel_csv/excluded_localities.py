"""Villages / CVD à ne pas prendre en compte dans les situations de /reports/facilitators-status.

Les tâches sont suivies par CVD (sur son village siège) : exclure un village revient donc à exclure son CVD entier.
Une exclusion est une clé `cvd:<id>` ou `village:<id>`, envoyée par la page dans le paramètre `excluded`
(liste séparée par des virgules) ; `excluded_headquarters_village_ids` la convertit en villages sièges.

Import par Excel : feuille unique, colonnes TYPE (Village | CVD), ID, NOM, CANTON. L'ID suffit ; sans ID, le nom
(accents et casse ignorés), précisé par le canton s'il est ambigu.
"""
import io

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.utils.translation import gettext as _
from django.views import View
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from administrativelevels.models import CVD, AdministrativeLevel
from cdd.call_objects_from_other_db import mis_objects_call
from dashboard.statistics.utils import normaliser_chaine

TEMPLATE_COLUMNS = ["TYPE", "ID", "NOM", "CANTON"]
TYPES = {"VILLAGE": "village", "CVD": "cvd"}
MAX_SEARCH_RESULTS = 30


def _village_label(village):
    canton = village.parent.name if village.parent_id and village.parent else ""
    cvd = f" — CVD {village.cvd.name}" if village.cvd_id and village.cvd else ""
    return f"Village {village.name}{f' ({canton})' if canton else ''}{cvd}"


def _cvd_label(cvd):
    hq = cvd.headquarters_village
    canton = hq.parent.name if hq and hq.parent_id and hq.parent else ""
    name = cvd.name if normaliser_chaine(cvd.name or "").startswith("CVD") else f"CVD {cvd.name}"
    return f"{name}{f' ({canton})' if canton else ''}"


def _villages():
    return mis_objects_call.filter_objects(AdministrativeLevel, type="Village").select_related("parent", "cvd")


def _cvds():
    return mis_objects_call.filter_objects(CVD).select_related("headquarters_village", "headquarters_village__parent")


def parse_excluded_keys(value):
    """`"cvd:1,village:2"` -> {('cvd', 1), ('village', 2)} (clés invalides ignorées)."""
    keys = set()
    for part in str(value or "").split(","):
        kind, _sep, raw_id = part.strip().partition(":")
        if kind in ("cvd", "village") and raw_id.isdigit():
            keys.add((kind, int(raw_id)))
    return keys


def excluded_headquarters_village_ids(value):
    """Villages sièges des CVD exclus (un village exclu emporte le CVD dont il fait partie)."""
    keys = parse_excluded_keys(value)
    cvd_ids = {i for kind, i in keys if kind == "cvd"}
    village_ids = {i for kind, i in keys if kind == "village"}
    if village_ids:
        cvd_ids |= set(
            mis_objects_call.filter_objects(AdministrativeLevel, id__in=village_ids, cvd__isnull=False)
            .values_list("cvd_id", flat=True)
        )
    hq_ids = set(
        mis_objects_call.filter_objects(CVD, id__in=cvd_ids, headquarters_village__isnull=False)
        .values_list("headquarters_village_id", flat=True)
    ) if cvd_ids else set()
    # Un village siège choisi directement mais sans CVD rattaché reste exclu tel quel
    return hq_ids | village_ids


class ExcludedLocalitiesSearchView(LoginRequiredMixin, View):
    """Recherche (select2) de villages et de CVD par nom."""

    def get(self, request):
        term = (request.GET.get("q") or "").strip()
        if len(term) < 2:
            return JsonResponse({"results": []})
        cvds = [
            {"id": f"cvd:{c.id}", "text": _cvd_label(c)}
            for c in _cvds().filter(name__icontains=term).order_by("name")[:MAX_SEARCH_RESULTS]
        ]
        villages = [
            {"id": f"village:{v.id}", "text": _village_label(v)}
            for v in _villages().filter(name__icontains=term).order_by("name")[:MAX_SEARCH_RESULTS]
        ]
        return JsonResponse({"results": cvds + villages})


class ExcludedLocalitiesLabelsView(LoginRequiredMixin, View):
    """Libellés des clés gardées par le navigateur (réaffichage de la liste au retour sur la page)."""

    def get(self, request):
        keys = parse_excluded_keys(request.GET.get("keys"))
        cvd_ids = [i for kind, i in keys if kind == "cvd"]
        village_ids = [i for kind, i in keys if kind == "village"]
        results = [{"id": f"cvd:{c.id}", "text": _cvd_label(c)} for c in _cvds().filter(id__in=cvd_ids)]
        results += [{"id": f"village:{v.id}", "text": _village_label(v)} for v in _villages().filter(id__in=village_ids)]
        return JsonResponse({"results": results})


class ExcludedLocalitiesTemplateView(LoginRequiredMixin, View):
    """Modèle Excel à remplir pour l'import."""

    def get(self, request):
        wb = Workbook()
        ws = wb.active
        ws.title = "Exclusions"
        ws.append(TEMPLATE_COLUMNS)
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="24C38B")
        ws.append(["CVD", "", "Nom du CVD", "Nom du canton (facultatif)"])
        ws.append(["Village", "", "Nom du village", "Nom du canton (facultatif)"])
        for column, width in zip("ABCD", (12, 12, 40, 30)):
            ws.column_dimensions[column].width = width
        validation = DataValidation(type="list", formula1='"Village,CVD"', allow_blank=False)
        ws.add_data_validation(validation)
        validation.add("A2:A5000")

        help_ws = wb.create_sheet("Instructions")
        for line in (
            ["Une ligne par village ou CVD à ne pas prendre en compte (remplacer les deux lignes d'exemple)."],
            ["TYPE : « Village » ou « CVD »."],
            ["ID : identifiant du village ou du CVD (s'il est connu, il suffit)."],
            ["NOM : nom du village ou du CVD (utilisé si l'ID est vide ; accents et majuscules ignorés)."],
            ["CANTON : à préciser si plusieurs villages / CVD portent le même nom."],
            ["Les tâches étant suivies par CVD, exclure un village exclut tout son CVD."],
        ):
            help_ws.append(line)
        help_ws.column_dimensions["A"].width = 100

        buffer = io.BytesIO()
        wb.save(buffer)
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="modele_exclusions_villages_cvd.xlsx"'
        return response


def _resolve_row(kind, raw_id, name, canton, index):
    """(résultat, erreur) pour une ligne du fichier."""
    queryset = _cvds() if kind == "cvd" else _villages()
    if raw_id:
        obj = queryset.filter(id=raw_id).first()
        if obj:
            return obj, None
        return None, _("ID %(id)s not found") % {"id": raw_id}
    if not name:
        return None, _("Name or ID is required")
    key = normaliser_chaine(name)
    canton_key = normaliser_chaine(canton) if canton else None
    candidates = index.get((kind, key), [])
    if canton_key:
        candidates = [c for c in candidates if c[1] == canton_key]
    if len(candidates) == 1:
        return queryset.filter(id=candidates[0][0]).first(), None
    if not candidates:
        return None, _("“%(name)s” not found") % {"name": name}
    return None, _("“%(name)s” is ambiguous: specify the canton or the ID") % {"name": name}


def _name_index():
    """{(type, nom normalisé): [(id, canton normalisé)]} pour la recherche par nom."""
    index = {}
    for vid, name, canton in _villages().values_list("id", "name", "parent__name"):
        index.setdefault(("village", normaliser_chaine(name or "")), []).append((vid, normaliser_chaine(canton or "")))
    for cid, name, canton in _cvds().values_list("id", "name", "headquarters_village__parent__name"):
        index.setdefault(("cvd", normaliser_chaine(name or "")), []).append((cid, normaliser_chaine(canton or "")))
    return index


class ExcludedLocalitiesImportView(LoginRequiredMixin, View):
    """Lit le fichier Excel envoyé et renvoie les villages / CVD reconnus et les lignes en erreur."""

    def post(self, request):
        upload = request.FILES.get("file")
        if not upload:
            return JsonResponse({"error": _("No file sent.")}, status=400)
        try:
            ws = load_workbook(upload, read_only=True, data_only=True).worksheets[0]
            rows = list(ws.iter_rows(values_only=True))
        except Exception:  # noqa: BLE001 - fichier illisible
            return JsonResponse({"error": _("The file could not be read: use the Excel template.")}, status=400)
        header = [normaliser_chaine(str(h or "")) for h in (rows[0] if rows else [])]
        if not rows or any(col not in header for col in ("TYPE", "NOM")):
            return JsonResponse({"error": _("Unexpected columns: use the Excel template (TYPE, ID, NOM, CANTON).")}, status=400)
        position = {col: header.index(col) for col in TEMPLATE_COLUMNS if col in header}

        def cell(row, col):
            i = position.get(col)
            value = row[i] if i is not None and i < len(row) else None
            return str(value).strip() if value not in (None, "") else ""

        index, results, errors, seen = None, [], [], set()
        for line, row in enumerate(rows[1:], start=2):
            if not any(v not in (None, "") for v in row):
                continue
            kind = TYPES.get(normaliser_chaine(cell(row, "TYPE")))
            raw_id = cell(row, "ID").split(".")[0]
            name, canton = cell(row, "NOM"), cell(row, "CANTON")
            if not kind:
                errors.append({"line": line, "error": _("TYPE must be “Village” or “CVD”")})
                continue
            if raw_id and not raw_id.isdigit():
                errors.append({"line": line, "error": _("Invalid ID")})
                continue
            if not raw_id and index is None:
                index = _name_index()
            obj, error = _resolve_row(kind, int(raw_id) if raw_id else None, name, canton, index or {})
            if error:
                errors.append({"line": line, "error": error})
                continue
            key = f"{kind}:{obj.id}"
            if key not in seen:
                seen.add(key)
                results.append({"id": key, "text": _cvd_label(obj) if kind == "cvd" else _village_label(obj)})
        return JsonResponse({"results": results, "errors": errors})
