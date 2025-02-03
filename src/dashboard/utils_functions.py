
from assignments.models import AssignAdministrativeLevelToFacilitator
from dashboard.facilitators.repository.db_facilitator_repository import FacilitatorRepository
from dashboard.facilitators.repository.facilitator_criteria import FacilitatorCriteria
from subprojects.models import Project as MisProject
from cdd.call_objects_from_other_db import mis_objects_call
from dashboard.administrative_levels.functions import get_cascade_villages_by_administrative_level_id
from authentication.models import Facilitator

def get_facilitators_on_adlor_dbs_name(project_name, project_id, ids_administrative_level, facilitators_dbs_name=[]):
    
    liste_villages = get_cascade_villages_by_administrative_level_id(ids_administrative_level)

    if facilitators_dbs_name:
        fs = Facilitator.objects.filter(develop_mode=False, training_mode=False, no_sql_db_name__in=facilitators_dbs_name)
    else:
        project_mis = mis_objects_call.filter_objects(MisProject, name=project_name)
        project_mis_id = project_mis.first().id if project_mis.count() >= 1 else 1

        if ids_administrative_level:
            assign_facilitators = AssignAdministrativeLevelToFacilitator.objects.using('mis').filter(
                administrative_level_id__in=[int(v['administrative_id']) for v in liste_villages],
                project_id=project_mis_id,
                activated=True
            )
            criteria = FacilitatorCriteria(
                id__in=list(set([int(f.facilitator_id) for f in assign_facilitators])),
                develop_mode=False,
                training_mode=False,
                projects__id=[project_id]
            )
        else:
            criteria = FacilitatorCriteria(
                develop_mode=False,
                training_mode=False,
                projects__id=[project_id]
            )
        fs = FacilitatorRepository().find_by_criteria(criteria=criteria)

    return fs, liste_villages