from cdd.call_objects_from_other_db import mis_objects_call
from subprojects.models import Project as MisProject
from process_manager.models import Project

def order_dict(sql_id, key, values):
    d = values
    if sql_id == 16 and key == "personnes":
        d = {
          "chefVillage": None,
          "contactChefVillage": None,
          "presidentCVD": None,
          "contactPresidentCVD": None,
          "tresorierCVD": None,
          "contactTresorierCVD": None,
          "secretaireCVD": None,
          "contactSecretaireCVD": None,
          "responsableJeunes": None,
          "contactResponsableJeunes": None,
          "responsableFemmes": None,
          "contactResponsableFemmes": None,
          "asc": None,
          "contactasc": None,
          "infirmier": None,
          "contactInfirmier": None
        }
        for k, v in values.items():
            d[k] = v
        
    return d

# def administrative_levels_by_project_id(project_id):
#     projects = Project.objects.filter(id=project_id)
#     projects_mis = mis_objects_call.filter_objects(MisProject, name__in=[p.name for p in projects])

#     if projects_mis.exists():
#         _sql, _params = projects_mis.query.get_compiler('mis').as_sql()
        
#         final_queryset = projects_mis.raw(
#             f"""
#             SELECT DISTINCT sub_p.id FROM subprojects_project AS sub_p 
#             LEFT JOIN subprojects_subproject AS sub_infras ON sub_subp.id=sub_infras.link_to_subproject_id 
#             WHERE (((sub_subp.current_status_of_the_site IN {tuple(STRUCTURE_NOT_START_STATUS*2)} 
#                 AND sub_infras.current_status_of_the_site IN {tuple(STRUCTURE_COMPLETED_STATUS+STRUCTURE_IN_PROGRESS_STATUS)}) 
#                 OR (sub_subp.current_status_of_the_site IN {tuple(STRUCTURE_IN_PROGRESS_STATUS+STRUCTURE_COMPLETED_STATUS)} 
#                 AND (sub_infras.current_status_of_the_site IN {tuple(STRUCTURE_NOT_START_STATUS+STRUCTURE_IN_PROGRESS_STATUS)}))
#                 OR (sub_subp.current_status_of_the_site IN {tuple(STRUCTURE_IN_PROGRESS_STATUS*2)})) 
#                 AND sub_subp.id IN (
#                     SELECT sub.id FROM ({_sql}) AS sub 
#                 ))
#             """, _params
#         )