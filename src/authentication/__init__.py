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

PROFESSIONAL_GROUPS = [
    'Minister', 'Advisor', 'GeneralManager', 'NationalCoordinator', 'RegionalCoordinator', 'Director', 
    'Evaluator', 'Financial', 'ProcurementSpecialist', 'KnowledgeManager', 'CDDSpecialist', 'Accountant', 'Infra', 'YouthProgramSpecialist', 'LocalEconomicDevelopmentSpecialist', 'CommunicationSpecialist', 'FullStack',
    'Supervisor',
    'CommunityFacilitator', 'TechnicalFacilitator'
]