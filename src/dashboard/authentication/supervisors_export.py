"""Export Excel de /supervisors/ : superviseurs de zone (SZ) et cantons couverts.

Feuille « Superviseurs » : un SZ par ligne (nom et prénom, téléphone, e-mail, projets) avec ses cantons couverts.
Feuille « Cantons » : un canton par ligne, précédé de sa région, préfecture et commune, avec le nom et prénom,
le téléphone et l'e-mail de son SZ (une ligne par SZ si plusieurs le couvrent ; vide si aucun).

Mêmes superviseurs que le tableau de la page (filtres « Projets » et niveau géographique, cf.
views_supervisors.selected_supervisor_docs). Cantons couverts = cantons des villages de la zone du SZ (villages
d'intervention + villages additionnels), comme la colonne « Cantons » de la page."""
from collections import defaultdict
from io import BytesIO

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.db import connections
from django.http import HttpResponse
from django.utils import timezone
from django.views import generic
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from administrativelevels.models import AdministrativeLevel
from cdd.call_objects_from_other_db import mis_objects_call
from dashboard.administrative_levels.functions import get_cascade_villages_by_administrative_level_id

SUPERVISOR_COLUMNS = ["Nom et prénom", "Téléphone", "E-mail", "Projets", "Nombre de cantons couverts",
                      "Cantons couverts"]
CANTON_COLUMNS = ["Région", "Préfecture", "Commune", "Canton", "Nom et prénom du SZ", "Téléphone du SZ",
                  "E-mail du SZ"]
HEADER_FILL = PatternFill("solid", fgColor="DDEBF7")
NO_SUPERVISOR_FILL = PatternFill("solid", fgColor="FCE4D6")


def supervisors_phones(users):
    """{user_id: téléphone} : celui du compte MGP de même e-mail (`representative.phone` de l'API du MGP, profil du
    superviseur), sinon celui de sa fiche facilitateur (même personne). CDD ne garde pas le téléphone des comptes
    web (auth.User)."""
    from authentication.identity import facilitator_of_user

    by_email = {}
    emails = sorted({(u.email or "").strip().lower() for u in users if (u.email or "").strip()})
    if emails:
        try:
            with connections["grm"].cursor() as cursor:
                cursor.execute(
                    "SELECT lower(email), phone_number FROM authentication_user WHERE lower(email) = ANY(%s)", [emails])
                for email, phone in cursor.fetchall():
                    if phone and not by_email.get(email):
                        by_email[email] = phone
        except Exception:  # noqa: BLE001 - MGP injoignable : repli sur les fiches facilitateurs
            by_email = {}
    phones = {}
    for user in users:
        phone = by_email.get((user.email or "").strip().lower())
        if not phone:
            facilitator = facilitator_of_user(user)
            phone = getattr(facilitator, "phone", None)
        phones[user.id] = phone or ""
    return phones


def _cantons_of_villages(village_ids):
    """{village_id: canton_id} (parent des villages)."""
    ids = {int(v) for v in village_ids if str(v).isdigit()}
    if not ids:
        return {}
    return dict(mis_objects_call.filter_objects(AdministrativeLevel, id__in=ids, type="Village")
                .values_list("id", "parent_id"))


def _canton_paths(canton_ids):
    """{canton_id: (région, préfecture, commune, canton)}."""
    rows = mis_objects_call.filter_objects(AdministrativeLevel, id__in=canton_ids, type="Canton").values_list(
        "id", "name", "parent__name", "parent__parent__name", "parent__parent__parent__name")
    return {cid: (region or "", prefecture or "", commune or "", name or "")
            for cid, name, commune, prefecture, region in rows}


def _area_canton_ids(request):
    """Cantons du niveau géographique filtré sur la page (None : pas de filtre)."""
    from dashboard.authentication.views_supervisors import geo_filter_id
    level_id = geo_filter_id(request)
    if level_id is None:
        return None
    village_ids = [v["administrative_id"] for v in get_cascade_villages_by_administrative_level_id(level_id)]
    return {c for c in _cantons_of_villages(village_ids).values() if c}


def _projects_canton_ids(projects):
    from subprojects.models import Project as MisProject
    mis_ids = list(mis_objects_call.filter_objects(MisProject, name__in=[p.name for p in projects])
                   .values_list("id", flat=True))
    if not mis_ids:
        return set()
    return set(mis_objects_call.filter_objects(
        AdministrativeLevel, administrative_levels_projects__in=mis_ids, type="Canton",
    ).values_list("id", flat=True))


def build_workbook(request):
    from dashboard.authentication.views_supervisors import selected_supervisor_docs
    from process_manager.models import Project

    projects, listed_projects, accounts, docs = selected_supervisor_docs(request)
    users = {u.id: u for u in User.objects.filter(id__in=[a[0] for a in accounts.values()])}

    # Cantons couverts par superviseur
    village_ids = {v for doc in docs for v in doc["smallest_administrative_level_ids"]
                   + doc["additional_smallest_administrative_level_ids"]}
    canton_of = _cantons_of_villages(village_ids)
    supervisors = []
    for doc in docs:
        user = users[accounts[doc["representative"]["email"]][0]]
        cantons = {canton_of.get(int(v)) for v in doc["smallest_administrative_level_ids"]
                   + doc["additional_smallest_administrative_level_ids"] if str(v).isdigit()}
        supervisors.append({"user": user, "cantons": {c for c in cantons if c}})

    project_names = defaultdict(list)
    for user_id, name in Project.users.through.objects.filter(
        user_id__in=list(users), project_id__in=[p.id for p in projects],
    ).values_list("user_id", "project__name").order_by("project__name"):
        project_names[user_id].append(name)

    phones = supervisors_phones(list(users.values()))
    area = _area_canton_ids(request)
    all_cantons = _projects_canton_ids(listed_projects) | {c for s in supervisors for c in s["cantons"]}
    if area is not None:
        all_cantons &= area
    paths = _canton_paths(all_cantons | {c for s in supervisors for c in s["cantons"]})

    def full_name(user):
        return f"{user.last_name} {user.first_name}".strip() or user.username

    def sort_path(canton_id):
        return tuple(x.upper() for x in paths.get(canton_id, ("", "", "", str(canton_id))))

    wb = Workbook()
    ws = wb.active
    ws.title = "Superviseurs"
    ws.append(SUPERVISOR_COLUMNS)
    for s in sorted(supervisors, key=lambda s: full_name(s["user"]).upper()):
        user = s["user"]
        cantons = sorted(s["cantons"], key=sort_path)
        ws.append([
            full_name(user), phones.get(user.id, ""), user.email or "", ", ".join(project_names.get(user.id, [])),
            len(cantons),
            ", ".join(f"{paths[c][3]} ({paths[c][2]})" if paths.get(c) else str(c) for c in cantons),
        ])

    ws2 = wb.create_sheet("Cantons")
    ws2.append(CANTON_COLUMNS)
    supervisors_of = defaultdict(list)
    for s in supervisors:
        for canton_id in s["cantons"]:
            supervisors_of[canton_id].append(s["user"])
    for canton_id in sorted(all_cantons, key=sort_path):
        path = list(paths.get(canton_id, ("", "", "", str(canton_id))))
        users_of = sorted(supervisors_of.get(canton_id, []), key=lambda u: full_name(u).upper())
        if not users_of:
            ws2.append(path + ["", "", ""])
            for cell in ws2[ws2.max_row]:
                cell.fill = NO_SUPERVISOR_FILL
        for user in users_of:
            ws2.append(path + [full_name(user), phones.get(user.id, ""), user.email or ""])

    for sheet, widths in ((ws, [32, 18, 34, 22, 14, 90]), (ws2, [18, 20, 22, 26, 32, 18, 34])):
        for col, width in enumerate(widths, 1):
            sheet.column_dimensions[get_column_letter(col)].width = width
        for cell in sheet[1]:
            cell.font = Font(bold=True)
            cell.fill = HEADER_FILL
            cell.alignment = Alignment(wrap_text=True, vertical="center")
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
    for row in ws.iter_rows(min_row=2, min_col=6, max_col=6):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    return wb


class SupervisorsExportView(LoginRequiredMixin, generic.View):
    """GET (mêmes paramètres que supervisors-list/) -> classeur Excel."""

    def get(self, request, *args, **kwargs):
        wb = build_workbook(request)
        buffer = BytesIO()
        wb.save(buffer)
        response = HttpResponse(buffer.getvalue(),
                                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        stamp = timezone.localtime().strftime("%Y%m%d_%H%M")
        response["Content-Disposition"] = f'attachment; filename="superviseurs_de_zone_{stamp}.xlsx"'
        return response
