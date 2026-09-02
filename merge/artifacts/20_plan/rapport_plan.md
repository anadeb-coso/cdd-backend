# Rapport — Étape 2 : Plan de fusion

- Généré : 2026-09-02T17:43:27
- Statut : **OK**
- Plan : `merge/fusion_plan.yml` (117 tables)

## Répartition
- A : 8
- B : 20
- C : 77
- orpheline : 4
- reconstruite : 8

## Catégorie A — réconciliation

### `auth_group`
- clé naturelle : ['name']
- unicité : {'cdd': 'unique', 'mis': 'unique'}
- FK entrantes à remapper (côté mis) : auth_group_permissions.group_id, auth_user_groups.group_id

### `auth_group_permissions`
- clé naturelle : None
- conflit type `id` : CDD bigint(20) / COSOMIS int(11) → retenu bigint(20)

### `auth_user`
- clé naturelle : ['username']
- unicité : {'cdd': 'unique', 'mis': 'unique'}
- FK entrantes à remapper (côté mis) : auth_user_groups.user_id, auth_user_user_permissions.user_id, authtoken_token.user_id, django_admin_log.user_id, subprojects_filecomment.user_id, subprojects_subprojectfile.user_id, usermanager_usertoken.user_id

### `auth_user_groups`
- clé naturelle : None
- conflit type `id` : CDD bigint(20) / COSOMIS int(11) → retenu bigint(20)

### `auth_user_user_permissions`
- clé naturelle : None
- conflit type `id` : CDD bigint(20) / COSOMIS int(11) → retenu bigint(20)

### `authtoken_token`
- clé naturelle : None

### `process_manager_administrativelevelwave`
- clé naturelle : ['project_id', 'wave.number', 'administrative_level_id']
- unicité : {'cdd': 'unique', 'mis': 'unique'}
- champs ajoutés de COSOMIS (null=True) : delete_by_user
- conflit type `administrative_level_id` : CDD int(11) / COSOMIS bigint(20) → retenu bigint(20)
- champs CDD seuls conservés : cycle_id
- FK entrantes à remapper (côté mis) : process_manager_periodwave_administrative_levels.administrativelevelwave_id

### `process_manager_wave`
- clé naturelle : ['number']
- unicité : {'cdd': 'unique', 'mis': 'unique'}
- champs ajoutés de COSOMIS (null=True) : delete_by_user
- FK entrantes à remapper (côté mis) : process_manager_administrativelevelwave.wave_id, process_manager_periodwave.wave_id

## Catégorie B — miroirs (déclaration en double à retirer)
- `administrativelevels_administrativelevel` — propriétaire **cosomis** ; retirer dans **cdd** : administrativelevels.AdministrativeLevel
- `administrativelevels_cvd` — propriétaire **cosomis** ; retirer dans **cdd** : administrativelevels.CVD
- `administrativelevels_geographicalunit` — propriétaire **cosomis** ; retirer dans **cdd** : administrativelevels.GeographicalUnit
- `assignments_assignadministrativeleveltofacilitator` — propriétaire **cosomis** ; retirer dans **cdd** : assignments.AssignAdministrativeLevelToFacilitator
- `authentication_facilitator` — propriétaire **cdd** ; retirer dans **cosomis** : authentication.Facilitator
- `subprojects_component` — propriétaire **cosomis** ; retirer dans **cdd** : subprojects.Component
- `subprojects_cycle` — propriétaire **cosomis** ; retirer dans **cdd** : subprojects.Cycle
- `subprojects_cycle_administrative_levels` — propriétaire **cosomis** ; retirer dans **cdd** : subprojects.Cycle_administrative_levels
- `subprojects_financier` — propriétaire **cosomis** ; retirer dans **cdd** : subprojects.Financier
- `subprojects_project` — propriétaire **cosomis** ; retirer dans **cdd** : subprojects.Project
- `subprojects_project_administrative_levels` — propriétaire **cosomis** ; retirer dans **cdd** : subprojects.Project_administrative_levels
- `subprojects_project_financiers` — propriétaire **cosomis** ; retirer dans **cdd** : subprojects.Project_financiers
- `subprojects_subproject` — propriétaire **cosomis** ; retirer dans **cdd** : subprojects.Subproject
- `subprojects_subproject_projects` — propriétaire **cosomis** ; retirer dans **cdd** : subprojects.Subproject_projects
- `subprojects_typemain` — propriétaire **cosomis** ; retirer dans **cdd** : subprojects.TypeMain
- `subprojects_villagegoal` — propriétaire **cosomis** ; retirer dans **cdd** : subprojects.VillageGoal
- `subprojects_villagemeeting` — propriétaire **cosomis** ; retirer dans **cdd** : subprojects.VillageMeeting
- `subprojects_villageobstacle` — propriétaire **cosomis** ; retirer dans **cdd** : subprojects.VillageObstacle
- `subprojects_villagepriority` — propriétaire **cosomis** ; retirer dans **cdd** : subprojects.VillagePriority
- `subprojects_vulnerablegroup` — propriétaire **cosomis** ; retirer dans **cdd** : subprojects.VulnerableGroup

## FK molles / JSON (§1) — côté mis uniquement
- **86** colonne(s) `create_by_user`/`update_by_user` (snapshot user) → remapper la clé JSON `.id` via id_map(auth_user).
- 46 colonne(s) sans remap : `users_involved` (audit libre) et les listes d'ID adl (catégorie B, ID inchangés).
- Détail complet dans `fusion_plan.yml` → `soft_remap`.


## Suite
Plan **OK** → Étape 3 : `merge/scripts/03_build_id_map.py`.
