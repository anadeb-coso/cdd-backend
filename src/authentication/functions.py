from django.utils.translation import gettext_lazy
from django.contrib.auth.models import Group

from assignments.models import AssignAdministrativeLevelToFacilitator
from cdd.call_objects_from_other_db import mis_objects_call
from authentication import PROFESSIONAL_GROUPS


def get_assign_adl_by_facilitatr(facilitator_id, project_id, activated):
    return mis_objects_call.filter_objects(
                AssignAdministrativeLevelToFacilitator, 
                facilitator_id=facilitator_id, project_id=project_id, activated=activated
            )

def get_assigns_adl_by_facilitatrs(facilitator_ids, project_id, activated):
    return mis_objects_call.filter_objects(
                AssignAdministrativeLevelToFacilitator, 
                facilitator_id__in=facilitator_ids, project_id=project_id, activated=activated
            )


def get_group_high(group: Group):
    if group.name in PROFESSIONAL_GROUPS:

        if group.name == "Minister":
            return gettext_lazy("Minister").__str__()
        if group.name == "Advisor":
            return gettext_lazy("Advisor").__str__()
        if group.name == "GeneralManager":
            return gettext_lazy("General Manager").__str__()
        if group.name == "NationalCoordinator":
            return gettext_lazy("National Coordinator").__str__()
        if group.name == "RegionalCoordinator":
            return gettext_lazy("Regional Coordinator").__str__()
        if group.name == "Director":
            return gettext_lazy("Director").__str__()
        
        if group.name == "Evaluator":
            return gettext_lazy("Evaluator").__str__()
        if group.name == "Financial":
            return gettext_lazy("Financial ").__str__()
        if group.name == "ProcurementSpecialist":
            return gettext_lazy("Procurement Specialist").__str__()
        if group.name == "KnowledgeManager":
            return gettext_lazy("Knowledge manager").__str__()
        if group.name == "CDDSpecialist":
            return gettext_lazy("CDD Specialist").__str__()
        if group.name == "Accountant":
            return gettext_lazy("Accountant").__str__()
        if group.name == "Infra":
            return gettext_lazy("Infra").__str__()
        if group.name == "YouthProgramSpecialist":
            return gettext_lazy("Youth Program Specialist").__str__()
        if group.name == "LocalEconomicDevelopmentSpecialist":
            return gettext_lazy("Local Economic Development Specialist").__str__()
        if group.name == "CommunicationSpecialist":
            return gettext_lazy("Communication Specialist").__str__()
        if group.name == "FullStack":
            return gettext_lazy("FullStack").__str__()
        
        if group.name == "Supervisor":
            return gettext_lazy("Supervisor").__str__()
        
        if group.name == "CommunityFacilitator":
            return gettext_lazy("Community Facilitator").__str__()
        if group.name == "TechnicalFacilitator":
            return gettext_lazy("Technical Facilitator").__str__()
                

    return gettext_lazy("User").__str__()