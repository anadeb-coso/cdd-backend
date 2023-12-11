from assignments.models import AssignAdministrativeLevelToFacilitator
from cdd.call_objects_from_other_db import mis_objects_call


def get_assign_adl_by_facilitatr(facilitator_id, project_id, activated):
    return mis_objects_call.filter_objects(
                AssignAdministrativeLevelToFacilitator, 
                facilitator_id=facilitator_id, project_id=project_id, activated=activated
            )
