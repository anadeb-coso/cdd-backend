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

PHASES_BEFORE_BEGINING_SUBPROJECT_EXECUTION = [
    "VISITES PREALABLES", "MOBILISATION COMMUNAUTAIRE", "PLANIFICATION"
]

VALIDATION_PROCESS_COLORS = [
    '#F2CD86', # Pending to validate : Yellow 0
    '#63D3AC', # Validated : Light Green 1
    '#F0788E', # Indalidated : Red 2
    '#397F6A', # Completed :  Dark Green 3
    '#E9B9C2', # Undo :  Light Red 4
    '#5D0B22', # Deadline passed :  Dark Red 5
    'black', # Vacation :  Black 6
]

VALIDATION_PROCESS_COLORS_DESCRIPTION = {
    '#F2CD86': _('Pending to validate'), # Yellow 0
    '#63D3AC': _('Validated') ,# : Light Green 1
    '#F0788E': _('Invalidated'), # Red 2
    '#397F6A': _('Completed'), #  Dark Green 3
    '#E9B9C2': _('Undo'), # Light Red 4
    '#5D0B22': _('Deadline passed'), #  Dark Red 5
    'black': _('Vacation validated'), # Black 6
}

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

INVALID_CHARS = r'[\\/*?:\[\]]'

HEADERS_TO_SKIP = [
    "form", "form_fields", "administrative_levels", "updated_history", "updated_after_invalidation", "actions_by",
    "users_involved_in_task", "completed_history", "updated_after_invalidation_history", "action_by", "action_complete_by",
]

HEADERS_FORM_FIELDS = [
    "form", "form_fields", "administrative_levels"
]

HEADERS_HISTORY = [
   "updated_history", "updated_after_invalidation", "actions_by", "users_involved_in_task", "completed_history", 
   "updated_after_invalidation_history", "action_by", "action_complete_by",
]

HEADERS_IDS_AND_ADL = [
    '_id', '_rev', 'activity_id', 'cycle_id', 'phase_id', 'project_id', 'support_attachments', 'order', 'type', 
    'activity_sql_id', 'phase_sql_id', 'cycles', 'cvd_sql_id', 'cvd_unit', 'cvd_village', 'cvd_villages'
]

HEADERS_FIRST_ORDER = [
    'canton_name', 'canton_sql_id', 'administrative_level_name', 'administrative_level_id', 'name', 'activity_name', 'phase_name', 'description'
]

DATAFRAME_CDD_DATAS_BY_ORDER = ['canton_name', 'administrative_level_name']

TASKS_STATUS = [
    'Not_started', 
    'In_progress', 
    'Invalidated_reset_in_progress', 
    'Completed_awaiting_validation',  
    'Invalidated_updated_after_invalidation',
    'Invalidated_not_returned_after_invalidation', 
    'Invalidated', 
    'Validated', 
]