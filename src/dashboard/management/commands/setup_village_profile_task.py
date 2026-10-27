"""Prépare les tâches « Établissement du profil du village » pour la génération du profil de village
(Word / PDF, ``dashboard/documents/village_profile.py``) :

- active ``Task.generated_document = "village_profile"`` ;
- ajoute au formulaire les questions du canevas qui manquaient : en tête de la page 1, un groupe
  « Identification du village et collecte » (numéro du passage, coordonnées GPS, chef de village :
  nom / adresse / téléphone, date de la collecte) ; dans la section 2, « Pharmacie ou dépôt de
  médicaments » (clé ``existencePharmacieOuDepotMedicaments``, déjà attendue par le groupe).

Les nouvelles questions sont facultatives et AJOUTÉES (aucune page insérée, aucune clé renommée) : les
réponses déjà saisies restent valables. Relançable sans effet si tout est déjà en place.

    python manage.py setup_village_profile_task            # aperçu, rien n'est écrit
    python manage.py setup_village_profile_task --apply    # écrit (Task.form + document CouchDB du processus)
    python manage.py setup_village_profile_task --task 69 --task 105 --apply

Ensuite : synchroniser la tâche vers les facilitateurs (bouton « Synchroniser cette tâche » du générateur
de formulaire) pour que les téléphones reçoivent les nouvelles questions et le bouton de génération.
"""
import copy

from django.core.management.base import BaseCommand, CommandError

from dashboard.process_manager.tasks.form_design import validate_form_design
from process_manager.models import Task

IDENTIFICATION_KEY = "identificationVillage"
PHARMACY_KEY = "existencePharmacieOuDepotMedicaments"
I18N = {"optional": "", "required": "*"}
YES_NO = {"type": "string", "enum": ["Oui", "Non"]}

IDENTIFICATION_FIELDS = [
    ("numeroPassage", {"type": "string"}, {"label": "Numéro du passage"}),
    ("coordonneesGps", {"type": "geopoint"},
     {"label": "Coordonnées GPS du village/quartier", "mode": "geopoint", "accuracyThreshold": 20}),
    ("chefVillageNom", {"type": "string"}, {"label": "Chef de village / quartier : prénom et nom"}),
    ("chefVillageAdresse", {"type": "string"}, {"label": "Adresse du chef (indication de la maison du chef)"}),
    ("chefVillageTelephone", {"type": "string"}, {"label": "Numéro de téléphone du chef"}),
    ("dateCollecte", {"type": "string", "format": "date"}, {"label": "Date de la collecte", "mode": "date", "help": "DD/MM/YYYY"}),
]


def is_village_profile_form(form):
    keys = str(form or "")
    return "populationVillage" in keys and "equipementEtInfrastructures" in keys


def add_missing_fields(form):
    """(nouveau formulaire, liste des ajouts). Ne modifie pas ``form``."""
    form = copy.deepcopy(form)
    added = []

    # 1) groupe d'identification en tête de la 1re page
    page = form[0]
    props = page["page"].setdefault("properties", {})
    options = page.setdefault("options", {})
    fields = options.setdefault("fields", {})
    if IDENTIFICATION_KEY not in props:
        props[IDENTIFICATION_KEY] = {
            "type": "object",
            "properties": {key: dict(schema) for key, schema, _opts in IDENTIFICATION_FIELDS},
            "required": [],
        }
        fields[IDENTIFICATION_KEY] = {
            "label": "Identification du village et collecte", "i18n": dict(I18N),
            "fields": {key: dict(opts, help=opts.get("help", ""), i18n=dict(I18N)) for key, _schema, opts in IDENTIFICATION_FIELDS},
            "order": [key for key, _schema, _opts in IDENTIFICATION_FIELDS],
        }
        order = options.get("order") or [k for k in props if k != IDENTIFICATION_KEY]
        options["order"] = [IDENTIFICATION_KEY] + [k for k in order if k != IDENTIFICATION_KEY]
        added.append("page 1 : groupe « Identification du village et collecte » (6 questions)")
    else:
        group = props[IDENTIFICATION_KEY].setdefault("properties", {})
        group_opts = fields.setdefault(IDENTIFICATION_KEY, {}).setdefault("fields", {})
        for key, schema, opts in IDENTIFICATION_FIELDS:
            if key not in group:
                group[key] = dict(schema)
                group_opts[key] = dict(opts, help=opts.get("help", ""), i18n=dict(I18N))
                added.append(f"page 1 : question {key}")

    # 2) pharmacie dans la section 2 (groupe des équipements)
    for page in form:
        section = (page["page"].get("properties") or {}).get("existenceEtAccessibilitAuxServicesSociaux")
        if not section:
            continue
        equipments = (section.get("properties") or {}).get("equipementEtInfrastructures")
        if not equipments:
            continue
        if PHARMACY_KEY not in equipments.setdefault("properties", {}):
            equipments["properties"][PHARMACY_KEY] = dict(YES_NO)
            (page.setdefault("options", {}).setdefault("fields", {})
             .setdefault("existenceEtAccessibilitAuxServicesSociaux", {}).setdefault("fields", {})
             .setdefault("equipementEtInfrastructures", {}).setdefault("fields", {}))[PHARMACY_KEY] = {
                "label": "Pharmacie ou dépôt de médicaments", "help": "", "i18n": dict(I18N)}
            added.append("section 2 : question « Pharmacie ou dépôt de médicaments »")
        break
    return form, added


class Command(BaseCommand):
    help = "Active le profil de village (Word/PDF) et ajoute les questions manquantes aux tâches concernées."

    def add_arguments(self, parser):
        parser.add_argument("--task", action="append", type=int, help="Identifiant de tâche (répétable). "
                            "Par défaut : les tâches « Établissement du profil du village » ayant ce formulaire.")
        parser.add_argument("--apply", action="store_true", help="Écrire les changements (sinon simple aperçu).")

    def handle(self, *args, **options):
        if options["task"]:
            tasks = list(Task.objects.filter(id__in=options["task"]).select_related("project"))
            missing = set(options["task"]) - {t.id for t in tasks}
            if missing:
                raise CommandError(f"Tâche(s) introuvable(s) : {sorted(missing)}")
        else:
            tasks = [t for t in Task.objects.filter(name__icontains="profil du village").select_related("project")
                     if is_village_profile_form(t.form)]
        if not tasks:
            self.stdout.write("Aucune tâche concernée.")
            return

        for task in tasks:
            label = f"Tâche {task.id} ({task.project.name}) « {task.name} »"
            if not is_village_profile_form(task.form):
                self.stdout.write(self.style.WARNING(f"{label} : formulaire du profil de village absent, ignorée."))
                continue
            new_form, added = add_missing_fields(task.form)
            clean, errors = validate_form_design(new_form)
            if errors:
                raise CommandError(f"{label} : formulaire invalide après ajout : {errors}")
            enable = task.generated_document != Task.GENERATED_DOCUMENT_VILLAGE_PROFILE
            if not added and not enable:
                self.stdout.write(f"{label} : déjà prête.")
                continue
            self.stdout.write(label + " :")
            if enable:
                self.stdout.write("  - génération Word/PDF du profil de village activée")
            for line in added:
                self.stdout.write("  - " + line)
            if options["apply"]:
                task.form = clean
                task.generated_document = Task.GENERATED_DOCUMENT_VILLAGE_PROFILE
                task.save()
                self.stdout.write(self.style.SUCCESS("  enregistrée."))
        if not options["apply"]:
            self.stdout.write(self.style.WARNING("Aperçu seulement : relancer avec --apply pour écrire."))
        else:
            self.stdout.write("Penser à synchroniser ces tâches vers les facilitateurs (générateur de formulaire > "
                              "« Synchroniser cette tâche »).")
