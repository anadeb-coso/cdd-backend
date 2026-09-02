# Déclarations miroir à neutraliser (Étape 6)

Décision §9.2 : le modèle reste chez son propriétaire ; le projet non-propriétaire garde une déclaration de lecture mais **`managed = False`** et ne migre jamais la table (routeur ci-dessus).


## Projet `cdd` — 19 tables

- `administrativelevels_administrativelevel` (propriétaire **cosomis**) : administrativelevels.AdministrativeLevel  — modules : administrativelevels.models
  - action : `class Meta: managed = False` ; ne pas supprimer la classe (le code cdd l'utilise en lecture via l'ORM / `.using()`).
- `administrativelevels_cvd` (propriétaire **cosomis**) : administrativelevels.CVD  — modules : administrativelevels.models
  - action : `class Meta: managed = False` ; ne pas supprimer la classe (le code cdd l'utilise en lecture via l'ORM / `.using()`).
- `administrativelevels_geographicalunit` (propriétaire **cosomis**) : administrativelevels.GeographicalUnit  — modules : administrativelevels.models
  - action : `class Meta: managed = False` ; ne pas supprimer la classe (le code cdd l'utilise en lecture via l'ORM / `.using()`).
- `assignments_assignadministrativeleveltofacilitator` (propriétaire **cosomis**) : assignments.AssignAdministrativeLevelToFacilitator  — modules : assignments.models
  - action : `class Meta: managed = False` ; ne pas supprimer la classe (le code cdd l'utilise en lecture via l'ORM / `.using()`).
- `subprojects_component` (propriétaire **cosomis**) : subprojects.Component  — modules : subprojects.models
  - action : `class Meta: managed = False` ; ne pas supprimer la classe (le code cdd l'utilise en lecture via l'ORM / `.using()`).
- `subprojects_cycle` (propriétaire **cosomis**) : subprojects.Cycle  — modules : subprojects.models
  - action : `class Meta: managed = False` ; ne pas supprimer la classe (le code cdd l'utilise en lecture via l'ORM / `.using()`).
- `subprojects_cycle_administrative_levels` (propriétaire **cosomis**) : subprojects.Cycle_administrative_levels  — modules : subprojects.models
  - action : `class Meta: managed = False` ; ne pas supprimer la classe (le code cdd l'utilise en lecture via l'ORM / `.using()`).
- `subprojects_financier` (propriétaire **cosomis**) : subprojects.Financier  — modules : subprojects.models
  - action : `class Meta: managed = False` ; ne pas supprimer la classe (le code cdd l'utilise en lecture via l'ORM / `.using()`).
- `subprojects_project` (propriétaire **cosomis**) : subprojects.Project  — modules : subprojects.models
  - action : `class Meta: managed = False` ; ne pas supprimer la classe (le code cdd l'utilise en lecture via l'ORM / `.using()`).
- `subprojects_project_administrative_levels` (propriétaire **cosomis**) : subprojects.Project_administrative_levels  — modules : subprojects.models
  - action : `class Meta: managed = False` ; ne pas supprimer la classe (le code cdd l'utilise en lecture via l'ORM / `.using()`).
- `subprojects_project_financiers` (propriétaire **cosomis**) : subprojects.Project_financiers  — modules : subprojects.models
  - action : `class Meta: managed = False` ; ne pas supprimer la classe (le code cdd l'utilise en lecture via l'ORM / `.using()`).
- `subprojects_subproject` (propriétaire **cosomis**) : subprojects.Subproject  — modules : subprojects.models
  - action : `class Meta: managed = False` ; ne pas supprimer la classe (le code cdd l'utilise en lecture via l'ORM / `.using()`).
- `subprojects_subproject_projects` (propriétaire **cosomis**) : subprojects.Subproject_projects  — modules : subprojects.models
  - action : `class Meta: managed = False` ; ne pas supprimer la classe (le code cdd l'utilise en lecture via l'ORM / `.using()`).
- `subprojects_typemain` (propriétaire **cosomis**) : subprojects.TypeMain  — modules : subprojects.models
  - action : `class Meta: managed = False` ; ne pas supprimer la classe (le code cdd l'utilise en lecture via l'ORM / `.using()`).
- `subprojects_villagegoal` (propriétaire **cosomis**) : subprojects.VillageGoal  — modules : subprojects.models
  - action : `class Meta: managed = False` ; ne pas supprimer la classe (le code cdd l'utilise en lecture via l'ORM / `.using()`).
- `subprojects_villagemeeting` (propriétaire **cosomis**) : subprojects.VillageMeeting  — modules : subprojects.models
  - action : `class Meta: managed = False` ; ne pas supprimer la classe (le code cdd l'utilise en lecture via l'ORM / `.using()`).
- `subprojects_villageobstacle` (propriétaire **cosomis**) : subprojects.VillageObstacle  — modules : subprojects.models
  - action : `class Meta: managed = False` ; ne pas supprimer la classe (le code cdd l'utilise en lecture via l'ORM / `.using()`).
- `subprojects_villagepriority` (propriétaire **cosomis**) : subprojects.VillagePriority  — modules : subprojects.models
  - action : `class Meta: managed = False` ; ne pas supprimer la classe (le code cdd l'utilise en lecture via l'ORM / `.using()`).
- `subprojects_vulnerablegroup` (propriétaire **cosomis**) : subprojects.VulnerableGroup  — modules : subprojects.models
  - action : `class Meta: managed = False` ; ne pas supprimer la classe (le code cdd l'utilise en lecture via l'ORM / `.using()`).

## Projet `cosomis` — 1 tables

- `authentication_facilitator` (propriétaire **cdd**) : authentication.Facilitator  — modules : authentication.models
  - action : `class Meta: managed = False` ; ne pas supprimer la classe (le code cosomis l'utilise en lecture via l'ORM / `.using()`).
