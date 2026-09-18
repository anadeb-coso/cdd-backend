from django.utils.translation import gettext_lazy as _

FACILITATORS_TYPES = [
    ('community_facilitator', _('Community facilitator')),
    ('technical_facilitator', _('Technical facilitator'))
]

FACILITATORS_TYPES_PLURAL = [
    ('community_facilitator', _('Community facilitators')),
    ('technical_facilitator', _('Technical facilitators'))
]

FACILITATORS_TYPES_WITH_GROUP_NAME = {
    'CommunityFacilitator': 'community_facilitator',
    'TechnicalFacilitator': 'technical_facilitator'
}

# Sens inverse (facilitator_type -> nom du Group Django), utilisé pour
# attribuer le groupe web d'un Facilitator selon son type
# (cf. authentication.functions.ensure_facilitator_user).
FACILITATOR_TYPE_TO_GROUP_NAME = {v: k for k, v in FACILITATORS_TYPES_WITH_GROUP_NAME.items()}

PROFESSIONAL_GROUPS = [
    'Minister', 'Advisor', 'GeneralManager', 'NationalCoordinator', 'RegionalCoordinator', 'Director', 
    'Evaluator', 'Financial', 'ProcurementSpecialist', 'KnowledgeManager', 'CDDSpecialist', 'Accountant', 'Infra', 'YouthProgramSpecialist', 'LocalEconomicDevelopmentSpecialist', 'CommunicationSpecialist', 'FullStack',
    'Supervisor',
    'CommunityFacilitator', 'TechnicalFacilitator'
]