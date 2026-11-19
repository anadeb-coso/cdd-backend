"""Commandes proposées dans le menu « Commandes / sync » : description, champs (= options de la commande) et
conversion des champs de la page en options `call_command` + ligne de commande équivalente.

Les règles métier restent dans les commandes : ce module ne fait que décrire leurs options et les valider.

Types de champ : bool, int, float, text, project, cycle (dépend du champ `project`), tasks / collect_forms
(plusieurs identifiants), couch_dbs (plusieurs bases CouchDB) / couch_db (une base), cantons (plusieurs cantons).
Clés d'un champ :
    key        nom du champ dans la page
    dest       nom de l'option pour call_command (défaut : key) ; None = pas une option (update_funnel : réponses)
    flag       option de la ligne de commande (« --s3-uri ») ; pour un champ multiple sans `join`, répétée
    join       séparateur : la liste est passée en une seule chaîne (« --dbs a,b »)
    default    valeur initiale (et valeur sous laquelle l'option n'est pas écrite dans la ligne de commande)
    required, min, max, multiple, danger (case à risque, en rouge), show_if {champ: valeur}
    keep_empty texte : une valeur vide est passée telle quelle (« --label '' »)
"""
import re
import shlex

from django.core.exceptions import ValidationError

DB_NAME_RE = re.compile(r"^[a-z_][a-z0-9_$()+/-]*$")

S3_POSTGRES = "s3://elasticbeanstalk-us-west-1-371600284712/backupsdb/cdd_cosomis/"
S3_COUCHDB = "s3://elasticbeanstalk-us-west-1-371600284712/backupsdb/couchdb/"


def _s3_postgres_fields(with_zip):
    fields = [
        {"key": "s3_uri", "flag": "--s3-uri", "type": "text", "default": S3_POSTGRES, "required": True,
         "label": "Destination S3", "help": "Dossier S3 où le fichier est envoyé (aws s3 cp)."},
        {"key": "name", "flag": "--name", "type": "text", "default": "cdd_cosomis", "required": True,
         "label": "Préfixe du fichier", "help": "Fichier envoyé : <préfixe>_<AAAAMMJJHHMM> + extension."},
        {"key": "workdir", "flag": "--workdir", "type": "text", "default": "",
         "label": "Dossier temporaire du serveur", "help": "Vide : /var/tmp, sinon le dossier temporaire du système."},
        {"key": "min_free_mb", "flag": "--min-free-mb", "type": "int", "default": 500, "min": 0, "required": True,
         "label": "Espace libre minimum (Mo)", "help": "Refuse de démarrer si le dossier temporaire a moins d'espace libre."},
    ]
    if with_zip:
        fields.append({"key": "zip", "flag": "--zip", "type": "bool", "default": False,
                       "label": "Zipper le .sql (.sql.zip) au lieu du .sql.gz",
                       "help": "Exporte en .sql brut puis le zippe avant l'envoi (le .sql est supprimé dès que le zip existe)."})
    fields += [
        {"key": "dry_run", "flag": "--dry-run", "type": "bool", "default": False,
         "label": "Essai : exporter sans envoyer sur S3", "help": "Le fichier est quand même supprimé ensuite (sauf « conserver »)."},
        {"key": "keep", "flag": "--keep", "type": "bool", "default": False, "danger": True,
         "label": "Conserver le fichier sur le serveur (débogage)", "help": "Attention à l'espace disque du serveur web."},
    ]
    return fields


COMMANDS = [
    {
        "name": "update_funnel",
        "title": "Statistiques d'avancement des tâches (funnel)",
        "summary": "Recalcule les compteurs d'avancement des tâches (AggregatedStatus) d'un projet et d'un cycle à partir "
                   "des tâches des facilitateurs dans CouchDB, puis les niveaux supérieurs et les statistiques des "
                   "facilitateurs. Ce sont ces compteurs qu'affichent la page Diagnostics, le funnel et les exports "
                   "« Situation des FC (statuts agrégés) » / « Situations des FC ».",
        "details": [
            "Lit les tâches de la base de sauvegarde backup_db_facilitators_docs puis celles de chaque facilitateur du "
            "projet (ou des seules bases choisies).",
            "Seuls les villages du projet ET du cycle dans le SIG sont comptés ; la sortie signale les villages absents "
            "du cycle SIG ou sans CVD (à corriger dans le SIG).",
            "Écrit dans PostgreSQL (AggregatedStatus, AggregatedStatusFacilitator, statistiques des facilitateurs) ; "
            "ne modifie pas CouchDB.",
            "Long et gourmand en mémoire (il a déjà figé une instance de production lancé en SSH) : il tourne ici dans "
            "un processus séparé, à priorité basse, arrêté s'il dépasse le plafond mémoire.",
        ],
        "writes": "always",
        "duration": "de quelques minutes à plus d'une heure",
        # Commande interactive : les champs donnent les réponses aux questions posées (dans l'ordre de la commande).
        "interactive": True,
        "fields": [
            {"key": "project", "dest": None, "type": "project", "required": True, "label": "Projet"},
            {"key": "cycle", "dest": None, "type": "cycle", "required": True, "label": "Cycle"},
            {"key": "develop_mode", "dest": None, "type": "bool", "default": False,
             "label": "Comptes de développement (develop_mode)",
             "help": "Les deux cases décochées : les vrais facilitateurs. Cochée : SEULEMENT les comptes de ce type."},
            {"key": "training_mode", "dest": None, "type": "bool", "default": False,
             "label": "Comptes de formation (training_mode)",
             "help": "Cochée : SEULEMENT les comptes de formation."},
            {"key": "dbs", "dest": None, "type": "couch_dbs", "default": [],
             "label": "Bases de facilitateurs à traiter",
             "help": "Vide : tous les facilitateurs du projet (du type choisi ci-dessus)."},
            {"key": "sync_tasks", "dest": None, "type": "bool", "default": True,
             "label": "Recalculer depuis les tâches des facilitateurs (sync_celery_tasks_re)"},
            {"key": "delete_aggregated", "dest": None, "type": "bool", "default": False, "danger": True,
             "show_if": {"sync_tasks": True},
             "label": "Supprimer d'abord les compteurs du projet / cycle",
             "help": "Efface tous les AggregatedStatus et AggregatedStatusFacilitator du projet et du cycle avant le "
                     "recalcul : les pages restent vides ou partielles jusqu'à la fin."},
            {"key": "sync_adl", "dest": None, "type": "bool", "default": True,
             "label": "Calculer les niveaux administratifs (sync_aggregated_status_on_adl)"},
            {"key": "adl_village", "dest": None, "type": "bool", "default": True, "show_if": {"sync_adl": True},
             "label": "Villages"},
            {"key": "adl_bigger", "dest": None, "type": "bool", "default": False, "show_if": {"sync_adl": True},
             "label": "Cantons, communes, préfectures, régions",
             "help": "Nécessaire pour la page Diagnostics ; le plus long."},
        ],
    },
    {
        "name": "backup_couchdb",
        "title": "Sauvegarde CouchDB vers S3",
        "summary": "Exporte les bases CouchDB (facilitateurs, sauvegarde, système) dans un zip <AAAAMMJJHHMM>.zip envoyé "
                   "sur S3 (aws s3 cp), sans rien laisser sur le serveur.",
        "details": [
            "Par défaut, le zip est envoyé au fil de l'eau : rien n'est stocké sur le serveur ; une seule base à la fois "
            "transite par un fichier temporaire.",
            "Contenu : la liste des bases, <base>.json au format d'import (_bulk_docs) et, s'il y en a, la liste des bases "
            "en échec (une base en échec n'arrête pas les autres).",
            "Arrêt immédiat si l'espace libre du dossier temporaire passe sous le minimum : le disque du serveur web "
            "n'est jamais rempli.",
            "Lecture seule dans CouchDB.",
        ],
        "writes": "unless:dry_run",
        "duration": "de 10 à 40 minutes pour toutes les bases",
        "fields": [
            {"key": "s3_uri", "flag": "--s3-uri", "type": "text", "default": S3_COUCHDB, "required": True,
             "label": "Destination S3"},
            {"key": "dbs", "flag": "--dbs", "type": "couch_dbs", "join": ",", "default": [],
             "label": "Bases à exporter", "help": "Vide : toutes les bases."},
            {"key": "start_db", "flag": "--start-db", "type": "couch_db", "default": "",
             "label": "Reprendre à partir de cette base", "help": "Dans l'ordre de _all_dbs (reprise après un échec)."},
            {"key": "exclude_system", "flag": "--exclude-system", "type": "bool", "default": False,
             "label": "Ignorer les bases système (_users, _replicator, _global_changes)"},
            {"key": "add_original", "flag": "--add-original", "type": "bool", "default": False,
             "label": "Ajouter aussi la réponse brute de _all_docs (original/<base>.json)",
             "help": "Double à peu près la taille du zip."},
            {"key": "via_file", "flag": "--via-file", "type": "bool", "default": False,
             "label": "Construire le zip sur disque puis l'envoyer", "help": "Ancien fonctionnement : demande de l'espace disque."},
            {"key": "workdir", "flag": "--workdir", "type": "text", "default": "",
             "label": "Dossier temporaire du serveur", "help": "Vide : /var/tmp, sinon le dossier temporaire du système."},
            {"key": "min_free_mb", "flag": "--min-free-mb", "type": "int", "default": 500, "min": 0, "required": True,
             "label": "Espace libre minimum (Mo)"},
            {"key": "page_size", "flag": "--page-size", "type": "int", "default": 1000, "min": 1, "required": True,
             "label": "Documents lus par requête"},
            {"key": "timeout", "flag": "--timeout", "type": "int", "default": 120, "min": 1, "required": True,
             "label": "Délai d'une requête CouchDB (s)"},
            {"key": "pause", "flag": "--pause", "type": "float", "default": 0.2, "min": 0, "required": True,
             "label": "Pause entre deux bases (s)"},
            {"key": "dry_run", "flag": "--dry-run", "type": "bool", "default": False,
             "label": "Essai : écrire le zip sur disque sans l'envoyer sur S3", "help": "Supprimé ensuite (sauf « conserver »)."},
            {"key": "keep", "flag": "--keep", "type": "bool", "default": False, "danger": True,
             "label": "Conserver le zip sur le serveur (débogage)"},
        ],
    },
    {
        "name": "backup_postgres_db_sql",
        "title": "Sauvegarde PostgreSQL (.sql.gz) vers S3",
        "summary": "Exporte la base PostgreSQL du serveur (DATABASE_URL) en SQL compressé (.sql.gz, export_postgres_db_sql), "
                   "l'envoie sur S3 puis supprime le fichier du serveur.",
        "details": [
            "Réimport : télécharger le fichier, le décompresser si .sql.zip, puis import_postgres_db_sql (ou gunzip + psql -f).",
            "Lecture seule dans la base ; refuse de démarrer si le dossier temporaire n'a pas assez d'espace libre.",
        ],
        "writes": "unless:dry_run",
        "duration": "quelques minutes",
        "fields": _s3_postgres_fields(with_zip=True),
    },
    {
        "name": "backup_postgres_db",
        "title": "Sauvegarde PostgreSQL (.zip) vers S3",
        "summary": "Exporte la base PostgreSQL du serveur (DATABASE_URL) avec export_postgres_db (.zip), l'envoie sur S3 "
                   "puis supprime le fichier du serveur.",
        "details": [
            "Réimport : télécharger le zip puis import_postgres_db.",
            "Lecture seule dans la base ; refuse de démarrer si le dossier temporaire n'a pas assez d'espace libre.",
        ],
        "writes": "unless:dry_run",
        "duration": "quelques minutes",
        "fields": _s3_postgres_fields(with_zip=False),
    },
    {
        "name": "link_project_cantons",
        "title": "Lier des cantons à un projet",
        "summary": "Lie des cantons, avec leurs villages et leurs niveaux parents (commune, préfecture, région), à un "
                   "projet, comme le fait l'administration des projets ; les cycles COSOMIS du projet suivent.",
        "details": [
            "Sans « Écrire », la commande affiche seulement ce qui changerait (niveaux ajoutés / retirés).",
            "Par défaut, les cantons s'AJOUTENT aux niveaux déjà liés ; « Remplacer » retire ceux qui ne sont pas choisis.",
        ],
        "writes": "if:apply",
        "duration": "quelques secondes",
        "fields": [
            {"key": "project", "flag": "--project", "type": "project", "required": True, "label": "Projet"},
            {"key": "cantons", "flag": "--cantons", "type": "cantons", "join": ",", "required": True, "default": [],
             "label": "Cantons"},
            {"key": "replace", "flag": "--replace", "type": "bool", "default": False, "danger": True,
             "label": "Remplacer les niveaux déjà liés au projet",
             "help": "Les villages et cantons non choisis sont retirés du projet."},
            {"key": "apply", "flag": "--apply", "type": "bool", "default": False, "apply": True,
             "label": "Écrire les changements (sinon simple aperçu)"},
        ],
    },
    {
        "name": "rename_form_field",
        "title": "Renommer un champ de formulaire",
        "summary": "Renomme un champ de groupe de formulaire, à la fois dans les tâches et dans COSOCollect : formulaire, "
                   "réponses des facilitateurs, historiques et partages, sans perdre les valeurs.",
        "details": [
            "Tâches : formulaire en base, registre des partages et documents CouchDB de toutes les bases (process_design, "
            "copies des facilitateurs, sauvegardes).",
            "COSOCollect : formulaire (sa version augmente de 1 : les mobiles le rechargent), enregistrements, historiques "
            "et pièces jointes.",
            "Sans « Écrire » : simulation. En écriture, les originaux sont sauvegardés (JSON Lines) avant modification.",
            "Défaut : tâche 167 / COSOCollect 9, generalitiesSurVillage.totalParticipants -> populationTotal « Population totale ».",
        ],
        "writes": "if:apply",
        "duration": "quelques minutes (toutes les bases CouchDB sont parcourues)",
        "fields": [
            {"key": "task", "flag": "--task", "type": "tasks", "default": [167],
             "label": "Tâches", "help": "Vide : tâche 167."},
            {"key": "collect_form", "flag": "--collect-form", "type": "collect_forms", "default": [9],
             "label": "Formulaires COSOCollect", "help": "Vide : formulaire 9."},
            {"key": "no_tasks", "flag": "--no-tasks", "type": "bool", "default": False, "label": "Ne pas traiter les tâches"},
            {"key": "no_collect", "flag": "--no-collect", "type": "bool", "default": False, "label": "Ne pas traiter COSOCollect"},
            {"key": "group", "flag": "--group", "type": "text", "default": "generalitiesSurVillage", "required": True,
             "label": "Groupe du champ"},
            {"key": "old", "flag": "--old", "type": "text", "default": "totalParticipants", "required": True,
             "label": "Ancien nom"},
            {"key": "new", "flag": "--new", "type": "text", "default": "populationTotal", "required": True,
             "label": "Nouveau nom"},
            {"key": "label", "flag": "--label", "type": "text", "default": "Population totale", "keep_empty": True,
             "label": "Nouveau libellé", "help": "Vide : garder le libellé actuel."},
            {"key": "db", "flag": "--db", "type": "couch_dbs", "default": [],
             "label": "Limiter aux bases CouchDB", "help": "Vide : toutes les bases."},
            {"key": "backup", "flag": "--backup", "type": "text", "default": "",
             "label": "Fichier de sauvegarde des originaux",
             "help": "Vide : media/backups/rename_form_field_<date>.jsonl sur le serveur."},
            {"key": "apply", "flag": "--apply", "type": "bool", "default": False, "apply": True,
             "label": "Écrire (sinon simulation)"},
        ],
    },
    {
        "name": "setup_village_profile_task",
        "title": "Préparer la tâche « Profil du village »",
        "summary": "Active la génération du profil de village (Word/PDF) sur les tâches concernées et ajoute à leur "
                   "formulaire les questions manquantes.",
        "details": [
            "Par défaut : les tâches « Établissement du profil du village » qui ont ce formulaire.",
            "Sans « Écrire » : simple aperçu des questions ajoutées.",
            "Après écriture : synchroniser ces tâches vers les facilitateurs (générateur de formulaire > « Synchroniser "
            "cette tâche »).",
        ],
        "writes": "if:apply",
        "duration": "quelques secondes",
        "fields": [
            {"key": "task", "flag": "--task", "type": "tasks", "default": [],
             "label": "Tâches", "help": "Vide : les tâches « profil du village » détectées automatiquement."},
            {"key": "apply", "flag": "--apply", "type": "bool", "default": False, "apply": True,
             "label": "Écrire les changements (sinon simple aperçu)"},
        ],
    },
    {
        "name": "sync_comities_members",
        "title": "Membres des comités villageois",
        "summary": "Lit dans les bases de tous les facilitateurs les tâches de mise en place / restructuration du CVD et "
                   "recopie les membres des comités (B/CVD, CS, CTMO, CCT, CES, CVGP, représentants des jeunes, CIRDI) "
                   "dans les comités villageois (rapports).",
        "details": [
            "Tâches lues : mise en place du CVD (COSO 29, PURS 78, FA-COSO 114), date de la 2e réunion (27, 76, 112) et "
            "vérification de l'existence du CVD (19, 68, 104).",
            "Crée ou met à jour un comité par (comité, CVD, projet) : membres, présence de femmes, méthode de choix, "
            "existence du CVD, effectif complet, date de réunion.",
            "Écrit dans PostgreSQL (VillageCommittee) ; lecture seule dans CouchDB. Aucune option.",
        ],
        "writes": "always",
        "duration": "quelques minutes",
        "fields": [],
    },
]

BY_NAME = {c["name"]: c for c in COMMANDS}


def public_commands():
    """Description envoyée à la page (sans les fonctions)."""
    return [{k: v for k, v in c.items()} for c in COMMANDS]


# ----------------------------------------------------------------------------------------------------------------
# Validation des champs envoyés par la page
# ----------------------------------------------------------------------------------------------------------------
def _ints(values, label):
    out = []
    for raw in values:
        for part in str(raw).replace(";", ",").replace(" ", ",").split(","):
            if part.strip():
                if not part.strip().isdigit():
                    raise ValidationError(f"{label} : « {part} » n'est pas un identifiant.")
                out.append(int(part))
    return list(dict.fromkeys(out))


def _visible(field, raw_values):
    for other, wanted in (field.get("show_if") or {}).items():
        if raw_values.get(other) != wanted:
            return False
    return True


def clean(command, data):
    """`data` : QueryDict de la page. -> {clé: valeur}. Lève ValidationError({clé: message})."""
    from administrativelevels.models import AdministrativeLevel
    from coso_collect.models import CollectForm
    from process_manager.models import Cycle, Project, Task

    values, errors = {}, {}
    for field in command["fields"]:
        key, kind, label = field["key"], field["type"], field["label"]
        try:
            if kind == "bool":
                value = data.get(key) in ("1", "true", "on", "True")
            elif kind in ("int", "float"):
                raw = (data.get(key) or "").strip().replace(",", ".") if kind == "float" else (data.get(key) or "").strip()
                if raw == "":
                    value = None
                else:
                    try:
                        value = int(raw) if kind == "int" else float(raw)
                    except ValueError:
                        raise ValidationError("nombre attendu.")
                    if field.get("min") is not None and value < field["min"]:
                        raise ValidationError(f"au moins {field['min']}.")
                    if field.get("max") is not None and value > field["max"]:
                        raise ValidationError(f"au plus {field['max']}.")
            elif kind == "text":
                value = (data.get(key) or "").strip()
                if len(value) > 500:
                    raise ValidationError("500 caractères au plus.")
                if any(c in value for c in "\r\n\x00"):
                    raise ValidationError("une seule ligne.")
            elif kind == "project":
                ids = _ints([data.get(key) or ""], label)
                value = Project.objects.filter(id=ids[0]).first() if ids else None
                if ids and value is None:
                    raise ValidationError("projet introuvable.")
            elif kind == "cycle":
                ids = _ints([data.get(key) or ""], label)
                value = Cycle.objects.filter(id=ids[0]).first() if ids else None
                if ids and value is None:
                    raise ValidationError("cycle introuvable.")
            elif kind in ("tasks", "collect_forms", "cantons"):
                ids = _ints(data.getlist(key), label)
                if kind == "tasks":
                    found = set(Task.objects.filter(id__in=ids).values_list("id", flat=True))
                elif kind == "collect_forms":
                    found = set(CollectForm.objects.filter(id__in=ids).values_list("id", flat=True))
                else:
                    found = set(AdministrativeLevel.objects.filter(id__in=ids, type="Canton").values_list("id", flat=True))
                missing = [i for i in ids if i not in found]
                if missing:
                    raise ValidationError(f"introuvable(s) : {', '.join(map(str, missing))}.")
                value = ids
            elif kind in ("couch_dbs", "couch_db"):
                names = [n.strip() for raw in data.getlist(key) for n in raw.split(",") if n.strip()]
                bad = [n for n in names if not DB_NAME_RE.match(n)]
                if bad:
                    raise ValidationError(f"nom de base invalide : {', '.join(bad)}.")
                names = list(dict.fromkeys(names))
                if kind == "couch_db":
                    if len(names) > 1:
                        raise ValidationError("une seule base.")
                    value = names[0] if names else ""
                else:
                    value = names
            else:  # pragma: no cover - registre incohérent
                raise ValidationError(f"type de champ inconnu : {kind}")
        except ValidationError as exc:
            errors[key] = f"{label} : {' '.join(exc.messages)}"
            continue
        values[key] = value

    for field in command["fields"]:
        key = field["key"]
        if key in errors or not field.get("required") or not _visible(field, values):
            continue
        value = values.get(key)
        if value is None or value == "" or value == []:
            errors[key] = f"{field['label']} : obligatoire."

    if not errors and command["name"] == "update_funnel":
        if values["cycle"].project_id != values["project"].id:
            errors["cycle"] = "Cycle : il n'appartient pas au projet."
        if not values["sync_tasks"] and not values["sync_adl"]:
            errors["sync_tasks"] = "Choisir au moins un calcul."
    if not errors and command["name"] == "rename_form_field":
        if values["no_tasks"] and values["no_collect"]:
            errors["no_tasks"] = "Rien à traiter : les tâches et COSOCollect sont tous deux exclus."
        if values["old"] == values["new"]:
            errors["new"] = "Nouveau nom : identique à l'ancien."
    if errors:
        raise ValidationError(errors)
    return values


# ----------------------------------------------------------------------------------------------------------------
# Options call_command, réponses (commande interactive), ligne de commande
# ----------------------------------------------------------------------------------------------------------------
def _option_value(field, value):
    if field["type"] in ("project", "cycle"):
        return value.id if value is not None else None
    if field.get("join") and isinstance(value, list):
        return field["join"].join(str(v) for v in value)
    return value


def build(command, values):
    """-> (options call_command, réponses aux questions, ligne de commande, écrit ?)."""
    options, parts = {}, ["python", "manage.py", command["name"]]
    for field in command["fields"]:
        if field.get("dest", field["key"]) is None:
            continue
        dest = field.get("dest") or field["key"]
        value = values.get(field["key"])
        kind = field["type"]
        if kind == "bool":
            if value:
                options[dest] = True
                parts.append(field["flag"])
            continue
        if value is None or value == [] or (value == "" and not field.get("keep_empty")):
            continue
        option = _option_value(field, value)
        options[dest] = option
        if isinstance(option, list):
            if option != field.get("default"):
                for item in option:
                    parts += [field["flag"], str(item)]
        elif option != field.get("default") or field.get("required") and field.get("default") is None:
            parts += [field["flag"], str(option)]

    answers = []
    if command["name"] == "update_funnel":
        yes = lambda flag: "1" if values[flag] else "0"  # noqa: E731
        answers = [str(values["project"].id), str(values["cycle"].id), yes("develop_mode"), yes("training_mode"),
                   ",".join(values["dbs"]), "0",  # 0 = pas d'autre projet
                   "1",  # confirmation
                   yes("sync_tasks")]
        if values["sync_tasks"]:
            answers.append(yes("delete_aggregated"))
        answers.append(yes("sync_adl"))
        if values["sync_adl"]:
            answers += [yes("adl_village"), yes("adl_bigger")]

    writes = command["writes"]
    if writes.startswith("if:"):
        writes = bool(values.get(writes[3:]))
    elif writes.startswith("unless:"):
        writes = not values.get(writes[7:])
    else:
        writes = writes == "always"

    line = " ".join(shlex.quote(p) for p in parts)
    if answers:
        line += "   # réponses aux questions : " + " | ".join(a or "(vide)" for a in answers)
    return options, answers, line, writes
