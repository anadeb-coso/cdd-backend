"""Profil de village : remplit le canevas « Questionnaire communautaire — Profil de village »
(``templates_docx/questionnaire_profil_village.docx``) avec les réponses de la tâche
« Établissement du profil du village » (formulaire des projets FA-COSO / PURS).

Les réponses sont repérées par CLÉ de champ, quelle que soit la page ; les options du canevas par
LIBELLÉ (accents, casse et ponctuation ignorés) et leurs codes sont lus dans le canevas lui-même.
Une case cochée devient ☒ ; les réponses écrites sont en gras bleu foncé. Ce qui n'a pas de place
dans le canevas est ajouté sous « Observations » (« Informations complémentaires »).

Point d'entrée : ``build_village_profile_docx(form_response, meta) -> bytes``.
"""
import io
import re
import unicodedata
from pathlib import Path

from docx import Document
from docx.shared import RGBColor

TEMPLATE = Path(__file__).resolve().parent / "templates_docx" / "questionnaire_profil_village.docx"
BOX, BOX_CHECKED = "☐", "☒"
ANSWER_COLOR = RGBColor(0x1F, 0x38, 0x64)

# Clés des champs du formulaire (tâches 69 / 105) — y compris les champs d'identification ajoutés.
YES = "oui"


def norm(text):
    """Texte comparable : sans accents ni casse, seulement lettres et chiffres."""
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _tokens(text):
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().lower()
    return [t for t in re.split(r"[^a-z0-9]+", text) if t]


def _token_match(a, b):
    """Même mot, ou mêmes 4 premières lettres (Peuls / Peulh, Christianime / Christianisme)."""
    return a == b or (len(a) >= 4 and len(b) >= 4 and a[:4] == b[:4])


def flatten(form_response):
    """Réponses de toutes les pages -> {clé de champ: valeur} (groupes aplatis, coordonnées gardées entières)."""
    out = {}

    def walk(node):
        if not isinstance(node, dict):
            return
        for key, value in node.items():
            if isinstance(value, dict) and "latitude" not in value:
                walk(value)
            else:
                out.setdefault(key, value)

    for page in form_response or []:
        walk(page)
    return out


def _is_yes(value):
    return norm(value) in ("oui", "yes", "true", "1")


def _is_no(value):
    return norm(value) in ("non", "no", "false", "0")


def _fmt_number(value):
    if value in (None, ""):
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return str(int(number)) if number == int(number) else str(number).replace(".", ",")


# --------------------------------------------------------------------------- écriture dans le document
def _styled_run(paragraph, text):
    run = paragraph.add_run(str(text))
    run.bold = True
    run.font.color.rgb = ANSWER_COLOR
    return run


def write_in_cell(cell, text):
    """Écrit la réponse sous le libellé de la cellule (paragraphe vide suivant, sinon nouveau paragraphe)."""
    if text in (None, ""):
        return
    paragraphs = cell.paragraphs
    target = next((p for p in paragraphs[1:] if not p.text.strip()), None)
    if target is None and len(paragraphs) == 1 and not paragraphs[0].text.strip():
        target = paragraphs[0]
    if target is None:
        target = cell.add_paragraph()
    _styled_run(target, text)


def _check_paragraph(paragraph):
    for run in paragraph.runs:
        if BOX in run.text:
            run.text = run.text.replace(BOX, BOX_CHECKED, 1)
            return True
    return False


def check_cell(cell):
    for paragraph in cell.paragraphs:
        if _check_paragraph(paragraph):
            return True
    return False


def _fill_dots(cell, text):
    """Remplace les pointillés « …… » d'une option « Autre » par le texte saisi."""
    if not text:
        return
    for paragraph in cell.paragraphs:
        for run in paragraph.runs:
            if "…" in run.text:
                run.text = re.sub(r"…+", "", run.text)
                _styled_run(paragraph, text)
                return
    write_in_cell(cell, text)


def _unique_cells(row):
    seen, out = set(), []
    for cell in row.cells:
        if id(cell._tc) not in seen:
            seen.add(id(cell._tc))
            out.append(cell)
    return out


OPTION_RE = re.compile(r"^\s*" + BOX + r"\s*(\d+)\s*(.*)$")


def options_of(table):
    """Options « ☐ <code> <libellé> » d'un tableau -> [(code, libellé, cellule)]."""
    out = []
    for row in table.rows:
        for cell in _unique_cells(row):
            match = OPTION_RE.match(cell.text.replace("\n", " "))
            if match:
                out.append((match.group(1), match.group(2).strip(), cell))
    return out


def _find_option(options, value):
    """Option correspondant à ``value`` : libellé identique, sinon mot en commun ; None sinon."""
    target = norm(value)
    if not target:
        return None
    for option in options:
        if norm(option[1]) == target or norm(option[1]).startswith(target) or (len(norm(option[1])) > 8 and target.startswith(norm(option[1]))):
            return option
    value_tokens = _tokens(value)
    for option in options:
        if norm(option[1]).startswith("autre") or "etrang" in norm(option[1]):
            continue  # options génériques : seulement par libellé exact ou par repli
        label_tokens = _tokens(option[1])
        if any(_token_match(a, b) for a in value_tokens for b in label_tokens if len(a) > 2 and len(b) > 2):
            return option
    return None


def _other_option(options, foreign=False):
    for option in options:
        label = norm(option[1])
        if foreign and "etrang" in label:
            return option
        if not foreign and label.startswith("autre"):
            return option
    for option in options:  # option libre « ☐ 5 …………… »
        if "…" in option[1] or not option[1].strip():
            return option
    return None


def choose(options, value, other_text=""):
    """Coche l'option de ``value`` et renvoie le texte « code – libellé » à reporter dans la case de code."""
    if not value:
        return ""
    is_other = norm(value).startswith("autre") or "etrang" in norm(value)
    option = None if is_other else _find_option(options, value)
    label = None
    if option is None:
        option = _other_option(options, foreign="etrang" in norm(value))
        label = (other_text or "").strip() or (None if is_other else str(value))
    if option is None:
        return str(value)
    check_cell(option[2])
    if label and ("…" in option[1] or not option[1].strip()):
        _fill_dots(option[2], label)
    shown = label or option[1]
    return f"{option[0]} – {shown}"


def check_yes_no_cells(row_cells, yes_index, no_index, value):
    if _is_yes(value):
        check_cell(row_cells[yes_index])
    elif _is_no(value):
        check_cell(row_cells[no_index])


def yes_no_table(table, mapping, data, label_index=1, others=None):
    """Tableau « Code | Libellé | Oui | Non » (1 ou 2 blocs côte à côte) : coche Oui/Non par libellé.
    ``mapping`` = {libellé normalisé: clé du champ}. ``others`` = {libellé normalisé: texte « Autre »}."""
    for row in table.rows[1:]:
        cells = [c for c in row.cells]
        width = len(cells)
        for start in range(0, width, 4):
            block = cells[start:start + 4]
            if len(block) < 4:
                continue
            key_label = norm(block[label_index].text)
            for label, key in mapping.items():
                if key_label.startswith(label):
                    check_yes_no_cells(block, 2, 3, data.get(key))
                    if others and label in others and others[label]:
                        _fill_dots(block[label_index], others[label])
                        check_cell(block[2])
                    break


def check_simple_yes_no(table, value):
    options = options_of(table)
    for code, label, cell in options:
        if (_is_yes(value) and norm(label).startswith("oui")) or (_is_no(value) and norm(label).startswith("non")):
            check_cell(cell)


# --------------------------------------------------------------------------- correspondances
ASSOCIATIONS = {
    "chefferie": "existenceChefferie", "comitededeveloppement": "existenceComiteDev",
    "comitedecole": "existenceComiteEcole", "comitedesante": "existenceComiteSante",
    "cooperativeagricole": "existenceCooperativeAgricole", "agentdencadrement": "existenceAgentEncaAgricole",
    "ong": "existenceONG", "agentmunicipal": "existenceAgentMunicipal",
    "fonctionnaire": "existenceFonctionnaireRegion", "groupementfeminin": "existenceGroupeFeminin",
    "comitedegestion": "existenceComiteEau", "associationprofessionnelle": "existenceAssociationPro",
    "cooperativeassociationpastorale": "existenceCoopPastorale", "associationdejeunes": "existenceGroupeJeunes",
}
SHOCKS = {
    "secheresse": "pbSecheresse", "inondations": "pbInondations", "incendies": "pbIncendies",
    "tauxelevedemaladiesdescultures": "pbMaladiesCultures", "tauxelevedemaladiesdesanimaux": "pbMaladiesAnimaux",
    "baisseimportante": "pbBaissePrixAgricoles", "prixelevesdesintrants": "pbHaussePrixIntrantsAgri",
    "prixelevesdesproduitsalimentaires": "pbHassePrixAlimentaires", "attaquesacridiennes": "pbRavageRecolte",
    "glissementdeterrain": "pbGlissementTerrain", "ventsviolents": "pbVentsViolents",
    "bouffeesdechaleur": "pbBouffeesChaleur", "epidemies": "pbEpidemies",
}
INFRASTRUCTURES = {
    "etablissementmaternel": "existenceEtablissementMaternel", "ecoleprimaire": "existenceEcolePrimaire",
    "college": "existenceCollege", "lycee": "existenceLycee", "hopitalpublic": "existenceHopitalPublicOuPrive",
    "autrecentredesante": "existenceAutreCentreSantPublic", "cabinetmedical": "existenceCabinetMedicalCliniquePrive",
    "pharmacie": "existencePharmacieOuDepotMedicaments", "bureaudeposte": "existencePoste", "centredetatcivil": "existenceCentreCivil",
    "postedepolice": "existencePolice", "banqueinstitution": "existenceBanque", "marchepermanent": "existenceMarchePermanent",
    "marcheperiodique": "existenceMarchePeriodique", "gareroutiere": "existenceGareRoutiere",
    "routebitumee": "existenceRouteBitumee", "routeenlaterite": "existenceRouteLaterite",
    "centredencadrement": "existenceCentreAgricole", "banquecerealiere": "existenceBanqueCereale",
    "couloirsdecirculation": "existenceCouloirsTranshumance", "zonesdestationnement": "existenceStationBetail",
    "banqueaaliments": "existenceBanqueAlimentBetail", "pointdapprovisionnement": "existencePointEauBoisson",
    "pointsdeaudebetail": "existencePointEauBetail", "foragequipermet": "existenceForage",
    "boucherie": "existenceBoucherie", "mosquee": "existenceMosquee", "eglise": "existenceEglise",
    "complexesportif": "existenceComplexeSportif", "salledespectacle": "existenceSalleSpectacle",
    "centredalphabetisation": "existenceAlphabetisation", "centredeformation": "existenceCentreFormationPro",
    "centresocial": "existenceCentreSocial",
}
TRANSPORTS = {"moto": "TcMotoTricycle", "taxi": "TcTaxiVoiture", "train": "TcTrain", "pirogue": "TcPirogue"}
NETWORKS = {"yas": "couvertureReseauTogocom", "moov": "couvertureReseauMoov", "reseaudunpays": "couvertureReseauPaysVoisin"}
# Sources d'eau : l'ordre des choix du formulaire suit exactement les codes 1 à 17 du canevas.
WATER_SOURCES = [
    "Eau du robinet dans le logement", "Eau du robinet dans la cour/concession", "Robinet du voisin",
    "Borne fontaine/Robinet public", "Puits ouvert dans la cour/Concession", "Puits ouvert ailleurs",
    "Puits couvert dans la cour/Concession", "Puits couvert ailleurs", "Forage dans la concession",
    "Forage ailleurs", "Source aménagée", "Source non aménagée", "Fleuve/Rivière/Lac/Barrage",
    "Eau en bouteille", "Eau de pluie", "Eau en sachet", "Vendeur ambulant",
]
# Réponses écrites « Réponse : ____ » : question du canevas -> clé du champ.
WRITTEN_ANSWERS = {"1.01a": "totalHouseHolds", "1.06": "distanceAgglomeration", "1.18": "totalNouveauxMenages",
                   "1.19": "nbrNouveauxMenagesRaisonConflits"}
# Champs sans place dans le canevas : reportés sous « Observations ».
EXTRA_INFO = [
    ("populationVillage", "Population totale déclarée"),
    ("nombreEthniques", "Nombre de groupes ethniques"),
    ("existenceGroupeRefugie", "Association des réfugiés"),
    ("totalNouveauxMenagesCetteAnnee", "Nouveaux ménages installés cette année"),
    ("nbrMenagesExpratries", "Ménages partis vers l'extérieur du pays"),
]


def _water_text(value):
    if not value:
        return ""
    target = norm(value)
    for index, label in enumerate(WATER_SOURCES, start=1):
        if norm(label) == target:
            return f"{index} – {label}"
    return f"18 – {value}"


def _sum(data, keys):
    values = [data.get(k) for k in keys if data.get(k) not in (None, "")]
    if not values:
        return ""
    try:
        return _fmt_number(sum(float(v) for v in values))
    except (TypeError, ValueError):
        return ""


def _population_by_age(data, men, young):
    sex = "Hommes" if men else "Femmes"
    age = "Moins35" if young else "Plus35"
    return _sum(data, [f"total{sex}{age}{cat}" for cat in ("Refugie", "DeplaceInterne", "CommunauteAcceuil")])


def _gps(data, meta):
    point = data.get("coordonneesGps")
    if isinstance(point, dict) and point.get("latitude") is not None:
        return f"{float(point['latitude']):.6f}", f"{float(point['longitude']):.6f}"
    lat, lon = meta.get("latitude"), meta.get("longitude")
    if lat is not None and lon is not None and (float(lat), float(lon)) != (0.0, 0.0):  # 0,0 = non renseigné
        return f"{float(meta['latitude']):.6f}", f"{float(meta['longitude']):.6f}"
    return "", ""


def _date(value):
    if not value:
        return ""
    text = str(value)
    match = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    return f"{int(match.group(3)):02d}/{int(match.group(2)):02d}/{match.group(1)}" if match else text


# --------------------------------------------------------------------------- remplissage
def _fill_header(tables, data, meta):
    latitude, longitude = _gps(data, meta)
    values = {
        "numerodupassage": data.get("numeroPassage") or meta.get("passage"),
        "region": meta.get("region"), "commune": meta.get("commune"), "canton": meta.get("canton"),
        "villagequartier": meta.get("village"), "latituden": latitude, "longitudee": longitude,
        "prenometnom": data.get("chefVillageNom"), "adresse": data.get("chefVillageAdresse"),
        "numerodetelephone": data.get("chefVillageTelephone"),
        "datedelacollecte": _date(data.get("dateCollecte") or meta.get("date")),
        "nomdelenqueteur": meta.get("facilitator"),
    }
    for table in tables[:7]:
        for row in table.rows:
            for cell in _unique_cells(row):
                label = norm(cell.paragraphs[0].text) if cell.paragraphs else ""
                for key, value in values.items():
                    if label.startswith(key):
                        write_in_cell(cell, value)
                        break


def _fill_code_cells(table, texts):
    cells = _unique_cells(table.rows[0])
    for cell, text in zip(cells, texts):
        write_in_cell(cell, text)


def _replace_blank(paragraph, value):
    """Remplace le premier « ____ » du paragraphe par la valeur (le texte qui suit, ex. « km », est gardé)."""
    runs = list(paragraph.runs)
    for index, run in enumerate(runs):
        match = re.search(r"_+", run.text)
        if not match:
            continue
        # la ligne « ____ » peut être coupée en plusieurs morceaux : retirer aussi ceux qui suivent
        for other in runs[index + 1:]:
            if re.fullmatch(r"_+", other.text):
                other.text = ""
            elif other.text.startswith("_"):
                other.text = other.text.lstrip("_")
                break
            else:
                break
        before, after = run.text[:match.start()], run.text[match.end():]
        run.text = before
        value_run = _styled_run(paragraph, value)
        run._r.addnext(value_run._r)
        if after:
            tail = paragraph.add_run(after)
            tail.bold = run.bold
            value_run._r.addnext(tail._r)
        return


def _fill_written_answers(document, data):
    current = None
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        match = re.match(r"^\(?(\d\.\d{2}a?)\)?\s", text)
        if match:
            current = match.group(1)
            continue
        if text.startswith("Réponse") and current in WRITTEN_ANSWERS:
            value = _fmt_number(data.get(WRITTEN_ANSWERS[current]))
            if value:
                _replace_blank(paragraph, value)
            current = None


def build_village_profile_docx(form_response, meta=None):
    """Canevas rempli (octets .docx). ``meta`` : region, commune, canton, village, facilitator, date,
    latitude, longitude (repli si la tâche n'a pas de coordonnées)."""
    meta = meta or {}
    data = flatten(form_response)
    document = Document(str(TEMPLATE))
    t = document.tables

    _fill_header(t, data, meta)

    # 1.01 population par âge et sexe
    for row in t[7].rows[1:]:
        cells = _unique_cells(row)
        young = norm(cells[0].text).startswith("moins")
        write_in_cell(cells[1], _population_by_age(data, True, young))
        write_in_cell(cells[2], _population_by_age(data, False, young))

    # 1.02 à 1.05 : listes codées (cases + codes reportés)
    for options_table, code_table, keys, count in (
        (t[8], t[9], ("principaleLangueParlee", "autrePrincipaleLangueParlee"), 3),
        (t[10], t[11], ("principaleEthnie", "autrePrincipaleEthnie"), 3),
        (t[12], t[13], ("principaleReligion", "autrePrincipaleReligion"), 3),
        (t[14], t[15], ("principaleActivite", "autrePrincipaleActivite"), 2),
    ):
        options = options_of(options_table)
        _fill_code_cells(code_table, [
            choose(options, data.get(f"{keys[0]}{i}"), data.get(f"{keys[1]}{i}")) for i in range(1, count + 1)
        ])

    choose(options_of(t[16]), data.get("voiePrincipaleDacces"), data.get("AutreVoiePrincipaleDacces"))  # 1.07
    check_simple_yes_no(t[17], data.get("existenceMoyenTransportCommun"))                               # 1.08
    yes_no_table(t[18], TRANSPORTS, data)                                                               # 1.09
    choose(options_of(t[19]), data.get("principalMoyenTransport"))                                     # 1.10
    check_simple_yes_no(t[20], data.get("principalMoyenTransportAccessibleFemmes"))                    # 1.11
    choose(options_of(t[21]), data.get("frequencePrincipalMoyenTransport"),
           data.get("autreFrequencePrincipalMoyenTransport"))                                          # 1.12
    check_simple_yes_no(t[22], data.get("existenceReseauElectrique"))                                  # 1.13
    yes_no_table(t[23], NETWORKS, data)                                                                 # 1.14
    _fill_code_cells(t[25], [                                                                           # 1.15
        ", ".join(x for x in (_water_text(data.get("sourceEauSaisonSeche1")), _water_text(data.get("sourceEauSaisonSeche2"))) if x),
        ", ".join(x for x in (_water_text(data.get("sourceEauSaisonPluie1")), _water_text(data.get("sourceEauSaisonPluie2"))) if x),
    ])
    yes_no_table(t[26], ASSOCIATIONS, data)                                                             # 1.16
    check_simple_yes_no(t[27], data.get("venueNouveauxMenages"))                                       # 1.17
    choose(options_of(t[28]), data.get("statusMenages"))                                               # 1.20
    others = {"autre": data.get("autreAPreciser")}
    yes_no_table(t[29], dict(SHOCKS, autre="__autre__"), data, others=others)                          # 1.21
    yes_no_table(t[30], INFRASTRUCTURES, data)                                                          # 2.01
    _fill_written_answers(document, data)                                                               # 1.01a, 1.06, 1.18, 1.19

    # Observations + informations sans place dans le canevas
    lines = [line for line in str(data.get("observations") or "").splitlines() if line.strip()]
    extra = []
    for key, label in EXTRA_INFO:
        value = data.get(key)
        if value not in (None, ""):
            extra.append(f"{label} : {_fmt_number(value) if not isinstance(value, str) else value}")
    if extra:
        lines += ["Informations complémentaires :"] + extra
    rows = t[31].rows
    for index, line in enumerate(lines):
        if index < len(rows):
            write_in_cell(rows[index].cells[0], line)
        else:
            write_in_cell(rows[-1].cells[0], line)

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def build_meta(administrative_level_id, facilitator_name="", date=""):
    """Région / commune / canton / village (+ coordonnées) du village de la tâche, lus dans le SIG."""
    from administrativelevels.models import AdministrativeLevel
    from cdd.call_objects_from_other_db import mis_objects_call

    meta = {"facilitator": facilitator_name or "", "date": date or ""}
    try:
        village = mis_objects_call.filter_objects(AdministrativeLevel, id=int(administrative_level_id)).first()
    except (TypeError, ValueError):
        village = None
    if village is None:
        return meta
    meta.update(village=village.name, latitude=village.latitude, longitude=village.longitude)
    level = village.parent
    for _ in range(5):
        if level is None:
            break
        kind = (level.type or "").lower()
        if kind in ("canton", "commune", "region") and kind not in meta:
            meta[kind] = level.name
        level = level.parent
    return meta


def file_name(meta, extension):
    village = re.sub(r"[^A-Za-z0-9]+", "_", unicodedata.normalize("NFKD", meta.get("village") or "village")
                     .encode("ascii", "ignore").decode()).strip("_") or "village"
    return f"Profil_village_{village}.{extension}"
