"""Mise au format du canevas « Statistiques » des documents de tâche de chaque projet.

L'export `get_global_statistic_under_file_excel_or_csv` (onglet Statistiques de
/reports/facilitators-status) a été écrit pour les formulaires COSO : il reconnaît les
tâches par leur id COSO ou leur nom COSO, et lit les effectifs sur la 1re page du formulaire.
Les autres projets n'ont pas toujours ce format :

- FA2-COSO renomme ses tâches (« Etablir le profil du village » au lieu de « Etablissement du
  profil du village »…) et deux de ses tâches portent le même nom (« Présenter les activités
  de la journée » en AV3 et en AV4) : la correspondance se fait donc par nom de tâche ET
  activité ;
- certains formulaires placent les effectifs sur une autre page que la 1re (AV1 FA2) ;
- certains enregistrent les nombres en texte (« 100 », « 00 ») : l'export les additionnait
  en les concaténant.

Cette normalisation travaille sur une COPIE du document (rien n'est réécrit dans CouchDB).
"""

import copy
import re

from .utils import normaliser_chaine


# Tâches du canevas (ids et noms COSO, tels que lus par l'export).
CANEVAS_TASKS = {
    "visite_canton": (13, "Introduction et présentation de l'AC par l'AADB lors de la première réunion cantonale"),
    "visite_village": (17, "Présentation et clarification de votre mission"),
    "profil_village": (20, "Etablissement du profil du village"),
    "reunion_1": (22, "Brève introduction de la réunion et de l'ANADEB"),
    "reunion_2": (27, "Ouverture de la deuxième réunion et vérification du quorum des participants"),
    "formation_module_1": (37, "Animer la session de formation sur le Module 1 : rôles et responsabilités des membres des organes de CVD"),
    "reunion_3": (41, "Présenter les activités de la journée"),
    "reunion_4_pav": (45, "Elaboration du plan d'action villageois (PAV)"),
    "ccd": (46, "Mise en place et/ou restructuration du comité cantonal de développement (CCD)  et du comité cantonal de gestion des plaintes (CCGP)"),
    "arbitrage_ccd": (47, "Appui au CCD dans  l'analyse des PAV des villages, l'arbitrage, la sélection des sous - projets à financer et l'affection des ressources par sous - projet"),
    "reunion_5_restitution": (48, "Appui à l'organisation et à la facilitation de rencontre  communautaire de restitution des résultats de la reunion cantonale d'arbitrage"),
}

# Projet -> [(nom de la tâche, nom de l'activité ou None, tâche du canevas)].
# L'activité n'est exigée que lorsque le nom seul est ambigu.
PROJECT_TASK_ALIASES = {
    "FA2-COSO": [
        ("Introduction et présentation des facilitateurs par le spécialiste DCC/SZ", None, "visite_canton"),
        ("Présenter et clarifier votre mission", None, "visite_village"),
        ("Etablir le profil du village", None, "profil_village"),
        ("Vérifier le quorum des participants", None, "reunion_1"),  # AV1 - Orientation du village
        ("Ouvrir la deuxième assemblée villageois (AV2) et vérifier le quorum des participants", None, "reunion_2"),
        ("Animer la session de formation sur les thèmes : rôles et responsabilités des membres des organes de CVD et mécanisme de gestion des plaintes", None, "formation_module_1"),
        ("Présenter les activités de la journée", "AV3 - Diagnostic des besoins", "reunion_3"),
        ("Présenter les activités de la journée", "AV4 - Elaboration de PAV", "reunion_4_pav"),
        ("Mettre en place et/ou restructurer le comité cantonal de développement (CCD)  et le comité cantonal de gestion des plaintes (CCGP)", None, "ccd"),
        ("Appuyer le CCD dans  l'analyse des PAV des villages, l'arbitrage, la sélection des sous - projets à financer et l'affectation des ressources", None, "arbitrage_ccd"),
        ("Appuyer le CVD dans l'organisation et la facilitation de la rencontre communautaire de restitution des résultats de la reunion cantonale d'arbitrage", None, "reunion_5_restitution"),
    ],
}

# Préfixes des champs numériques lus par le canevas (effectifs, ménages, ethnies…).
_NUMERIC_KEY = re.compile(r"^(total|population|nombre|nbr)", re.IGNORECASE)
_NUMBER = re.compile(r"^\s*-?\d+(?:[.,]\d+)?\s*$")
# Champs lus sur la 1re page : repris d'une autre page s'ils n'y sont pas.
_FIRST_PAGE_KEY = re.compile(r"^(total|nombre|date)", re.IGNORECASE)

_CATEGORIES = ("Refugie", "DeplaceInterne", "CommunauteAcceuil")


def alias_task_names(project_name):
    """Noms des tâches du projet qui alimentent le canevas sous un autre nom."""
    return list({name for name, _activity, _key in PROJECT_TASK_ALIASES.get(project_name, [])})


def _empty(value):
    return value is None or (isinstance(value, str) and not value.strip())


def population_or_computed_total(population, form_response, old_form_response=None):
    """« Eff. Population » du profil du village : la population saisie (populationTotaleDuVillage, sinon
    populationVillage) ; vide, le total calculé du formulaire FA2-COSO (`generalitiesSurVillage.populationTotal` =
    réfugiés + déplacés internes + communauté d'accueil, ex-`totalParticipants`), réponse courante puis ancienne version.
    Les autres projets n'ont pas ce champ : leur valeur est inchangée."""
    if not _empty(population):
        return population
    for response in (form_response, old_form_response):
        for page in response or []:
            gen = page.get("generalitiesSurVillage") if isinstance(page, dict) else None
            if isinstance(gen, dict) and not _empty(gen.get("populationTotal")):
                return _to_number(gen["populationTotal"])
    return population


def _canevas_key(doc, project_name):
    aliases = PROJECT_TASK_ALIASES.get(project_name or doc.get("project_name"), [])
    if not aliases:
        return None
    name = normaliser_chaine(doc.get("name") or "")
    activity = normaliser_chaine(doc.get("activity_name") or "")
    for alias_name, alias_activity, key in aliases:
        if normaliser_chaine(alias_name) != name:
            continue
        if alias_activity is None or normaliser_chaine(alias_activity) == activity:
            return key
    return None


def _to_number(value):
    """Effectif saisi en texte -> nombre. « O » tapé pour zéro est lu 0 ; un autre texte non
    numérique est laissé vide (il faisait échouer les additions de l'export)."""
    if not isinstance(value, str):
        return value
    value = value.strip()
    if not value:
        return None
    if re.fullmatch(r"[0-9oO]+", value):
        value = value.replace("o", "0").replace("O", "0")
    if re.fullmatch(r"\d{1,3}(?:[   .]\d{3})+", value):  # séparateurs de milliers
        value = re.sub(r"[   .]", "", value)
    if _NUMBER.match(value):
        value = value.replace(",", ".")
        return float(value) if "." in value else int(value)
    return None


def _numbers_in(page):
    if not isinstance(page, dict):
        return page
    out = {}
    for k, v in page.items():
        if isinstance(v, dict):
            out[k] = {sk: (_to_number(sv) if _NUMERIC_KEY.match(sk) else sv) for sk, sv in v.items()}
        else:
            out[k] = _to_number(v) if _NUMERIC_KEY.match(k) else v
    return out


def _sum(values):
    values = [v for v in values if isinstance(v, (int, float))]
    return sum(values) if values else None


def _complete_profile(form_response):
    """Effectifs hommes / femmes du profil, à partir des catégories s'ils ne sont pas saisis."""
    for page in form_response:
        if not isinstance(page, dict) or not isinstance(page.get("generalitiesSurVillage"), dict):
            continue
        # Une valeur n'est posée que si elle a pu être calculée : une clé absente laisse
        # l'export retomber sur l'ancienne version du formulaire (old_forms).
        gen = page["generalitiesSurVillage"]
        for sexe in ("Hommes", "Femmes"):
            for age in ("Moins35", "Plus35"):
                key = f"total{sexe}{age}"
                value = _sum(gen.get(f"total{sexe}{age}{c}") for c in _CATEGORIES)
                if gen.get(key) in (None, "") and value is not None:
                    gen[key] = value
        # Groupe « population » existant (COSO : sur une autre page) complété en place ; sinon
        # créé sur cette page. Jamais un second groupe : l'export lit le premier rencontré.
        holder = next((p for p in form_response if isinstance(p, dict) and isinstance(p.get("population"), dict)), None)
        population = holder["population"] if holder else {}
        for sexe in ("Hommes", "Femmes"):
            key = f"populationNombreDe{sexe}"
            value = _sum([gen.get(f"total{sexe}Moins35"), gen.get(f"total{sexe}Plus35")])
            if population.get(key) in (None, "") and value is not None:
                population[key] = value
        if population and holder is None:
            page["population"] = population
        return


def _normalize_form_response(form_response, canevas_key):
    if not isinstance(form_response, list) or not form_response:
        return form_response
    pages = [_numbers_in(p) for p in form_response]
    first = pages[0] if isinstance(pages[0], dict) else {}
    for page in pages[1:]:
        if not isinstance(page, dict):
            continue
        for k, v in page.items():
            if _FIRST_PAGE_KEY.match(k) and not isinstance(v, (dict, list)) and first.get(k) is None and v is not None:
                first[k] = v
    pages[0] = first
    if canevas_key == "profil_village":
        _complete_profile(pages)
    return pages


def normalize_task_doc(doc, project_name=None):
    """Copie du document de tâche au format attendu par le canevas (voir l'en-tête du module)."""
    if not isinstance(doc, dict) or doc.get("type") != "task":
        return doc
    key = _canevas_key(doc, project_name)
    if key is None and not doc.get("form_response"):
        return doc
    doc = copy.deepcopy(doc)
    if key:
        # La reconstitution du profil (hommes / femmes) ne vaut que pour ces projets : COSO et
        # FA-COSO gardent leur lecture (dont le repli sur l'ancienne version, old_forms).
        doc["sql_id"], doc["name"] = CANEVAS_TASKS[key]
    doc["form_response"] = _normalize_form_response(doc.get("form_response"), key)
    for old in doc.get("old_forms") or []:
        if isinstance(old, dict):
            old["form_response"] = _normalize_form_response(old.get("form_response"), key)
    return doc
