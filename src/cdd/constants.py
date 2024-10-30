from django.utils.translation import gettext_lazy as _


PHASES_COLORS = [
    '#D9D9D9', # 0
    '#63D3AC', # 1
    '#F0788E', # 2
    '#F2CD86', # 3
    '#9095FF', # 4
    '#44967D', # 5
    '#BA79B7', # 6
    '#E9B9C2', # 7
]

PHASES_WITH_THEIR_NUMBERS = {
    "VISITES PREALABLES": 1,
    "MOBILISATION COMMUNAUTAIRE": 2,
    "PLANIFICATION": 3,
    "PRÉPARATION SOUS-PROJET": 4,
    "CONSULTATION  ET EXAMEN SOUS-PROJET": 5,
    "CONSULTATION ET EXAMEN SOUS-PROJET": 5,
    "MISE EN ŒUVRE DU SOUS-PROJET": 6,
    "CLOTURE ET REPLANIFICATION DU SOUS-PROJET": 7,
}

VALIDATION_PROCESS_COLORS = [
    '#F2CD86', # Pending to validate : Yellow 0
    '#63D3AC', # Validated : Light Green 1
    '#F0788E', # Indalidated : Red 2
    '#397F6A', # Completed :  Dark Green 3
    '#E9B9C2', # Undo :  Light Red 4
    '#5D0B22', # Deadline passed :  Dark Red 5
    'black', # Vacation :  Black 6
]

TYPES_VACATION = {
    "Congé annuel": _("Annual vacation"), 
    "Maternité/Paternité": _("Maternity/Paternity"), 
    "Maladie": _("Disease"), 
    "Permission exceptionnelle : décés": _("Exceptional permission: death"),
    "Permission exceptionnelle : mariage": _("Exceptional permission: wedding"), 
    "Permission exceptionnelle : naissance": _("Exceptional permission: birth"),
    "Autre": _("Other")
}

COMPONENTS = {
    "COMPOSANTE 1.1": _("COMPONENT 1.1"), 
    "COMPOSANTE 1.2": _("COMPONENT 1.2"), 
    "COMPOSANTE 1.2a": _("COMPONENT 1.2a"), 
    "COMPOSANTE 1.2b": _("COMPONENT 1.2b"),
    "COMPOSANTE 1.3": _("COMPONENT 1.3"), 
    "COMPOSANTE 2": _("COMPONENT 2"),
    "COMPOSANTE 3": _("COMPONENT 3"),
    "COMPOSANTE 4": _("COMPONENT 4"),
    "COMPOSANTE 5": _("COMPONENT 5"),
    "Autre": _("Other")
}