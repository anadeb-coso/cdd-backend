# collisions.md — Étape 1 (volet code)

> Généré par `merge/scripts/01_inventory.py`. Sans accès aux bases physiques : les catégories A/B ne sont que *probables* (CLAUDE.md §4.1).


## 1. Modèles de même nom (38)

| Modèle | app CDD | table CDD | app COSOMIS | table COSOMIS | managed CDD | managed COSOMIS | CreateModel CDD | CreateModel COSOMIS |
|---|---|---|---|---|---|---|---|---|
| Activity | planning | `planning_activity` | financial | `financial_activity` | True | True | oui | oui |
| AdministrativeLevel | administrativelevels | `administrativelevels_administrativelevel` | administrativelevels | `administrativelevels_administrativelevel` | True | True | — | oui |
| AdministrativeLevelWave | process_manager | `process_manager_administrativelevelwave` | process_manager | `process_manager_administrativelevelwave` | True | True | oui | oui |
| AssignAdministrativeLevelToFacilitator | assignments | `assignments_assignadministrativeleveltofacilitator` | assignments | `assignments_assignadministrativeleveltofacilitator` | True | True | — | oui |
| ChordCounter | django_celery_results | `django_celery_results_chordcounter` | django_celery_results | `django_celery_results_chordcounter` | True | True | oui | oui |
| Component | subprojects | `subprojects_component` | subprojects | `subprojects_component` | True | True | — | oui |
| ContentType | contenttypes | `django_content_type` | contenttypes | `django_content_type` | True | True | oui | oui |
| CVD | administrativelevels | `administrativelevels_cvd` | administrativelevels | `administrativelevels_cvd` | True | True | — | oui |
| Cycle | subprojects | `subprojects_cycle` | subprojects | `subprojects_cycle` | True | True | — | oui |
| Cycle_administrative_levels | subprojects | `subprojects_cycle_administrative_levels` | subprojects | `subprojects_cycle_administrative_levels` | True | True | — | — |
| Facilitator | authentication | `authentication_facilitator` | authentication | `authentication_facilitator` | True | False | oui | — |
| Financier | subprojects | `subprojects_financier` | subprojects | `subprojects_financier` | True | True | — | oui |
| GeographicalUnit | administrativelevels | `administrativelevels_geographicalunit` | administrativelevels | `administrativelevels_geographicalunit` | True | True | — | — |
| Group | auth | `auth_group` | auth | `auth_group` | True | True | oui | oui |
| Group_permissions | auth | `auth_group_permissions` | auth | `auth_group_permissions` | True | True | — | — |
| GroupResult | django_celery_results | `django_celery_results_groupresult` | django_celery_results | `django_celery_results_groupresult` | True | True | oui | oui |
| LogEntry | admin | `django_admin_log` | admin | `django_admin_log` | True | True | oui | oui |
| Permission | auth | `auth_permission` | auth | `auth_permission` | True | True | oui | oui |
| Project | subprojects | `subprojects_project` | subprojects | `subprojects_project` | True | True | — | oui |
| Project_administrative_levels | subprojects | `subprojects_project_administrative_levels` | subprojects | `subprojects_project_administrative_levels` | True | True | — | — |
| Project_financiers | subprojects | `subprojects_project_financiers` | subprojects | `subprojects_project_financiers` | True | True | — | — |
| Session | sessions | `django_session` | sessions | `django_session` | True | True | oui | oui |
| Subproject | subprojects | `subprojects_subproject` | subprojects | `subprojects_subproject` | True | True | — | oui |
| Subproject_projects | subprojects | `subprojects_subproject_projects` | subprojects | `subprojects_subproject_projects` | True | True | — | — |
| Tag | news | `news_tag` | financial | `financial_tag` | True | True | oui | oui |
| TaskResult | django_celery_results | `django_celery_results_taskresult` | django_celery_results | `django_celery_results_taskresult` | True | True | oui | oui |
| Token | authtoken | `authtoken_token` | authtoken | `authtoken_token` | True | True | oui | oui |
| TokenProxy | authtoken | `authtoken_token` | authtoken | `authtoken_token` | True | True | oui | oui |
| TypeMain | subprojects | `subprojects_typemain` | subprojects | `subprojects_typemain` | True | True | — | oui |
| User | auth | `auth_user` | authentication | `authentication_user` | True | True | oui | — |
| User_groups | auth | `auth_user_groups` | authentication | `authentication_user_groups` | True | True | — | — |
| User_user_permissions | auth | `auth_user_user_permissions` | authentication | `authentication_user_user_permissions` | True | True | — | — |
| VillageGoal | subprojects | `subprojects_villagegoal` | subprojects | `subprojects_villagegoal` | True | True | — | oui |
| VillageMeeting | subprojects | `subprojects_villagemeeting` | subprojects | `subprojects_villagemeeting` | True | True | — | oui |
| VillageObstacle | subprojects | `subprojects_villageobstacle` | subprojects | `subprojects_villageobstacle` | True | True | — | oui |
| VillagePriority | subprojects | `subprojects_villagepriority` | subprojects | `subprojects_villagepriority` | True | True | — | oui |
| VulnerableGroup | subprojects | `subprojects_vulnerablegroup` | subprojects | `subprojects_vulnerablegroup` | True | True | — | oui |
| Wave | process_manager | `process_manager_wave` | process_manager | `process_manager_wave` | True | True | oui | oui |

## 2. Tables de même nom (35)

| Table | modèle(s) CDD | modèle(s) COSOMIS | catégorie probable |
|---|---|---|---|
| `administrativelevels_administrativelevel` | administrativelevels.AdministrativeLevel | administrativelevels.AdministrativeLevel | à_arbitrer (B probable : schéma possédé par cosomis) |
| `administrativelevels_cvd` | administrativelevels.CVD | administrativelevels.CVD | à_arbitrer (B probable : schéma possédé par cosomis) |
| `administrativelevels_geographicalunit` | administrativelevels.GeographicalUnit | administrativelevels.GeographicalUnit | à_arbitrer (aucun CreateModel trouvé) |
| `assignments_assignadministrativeleveltofacilitator` | assignments.AssignAdministrativeLevelToFacilitator | assignments.AssignAdministrativeLevelToFacilitator | à_arbitrer (B probable : schéma possédé par cosomis) |
| `auth_group` | auth.Group | auth.Group | à_arbitrer (A probable : CreateModel des deux côtés) |
| `auth_group_permissions` | auth.Group_permissions | auth.Group_permissions | à_arbitrer (aucun CreateModel trouvé) |
| `auth_permission` | auth.Permission | auth.Permission | reconstruite (§4.6) |
| `auth_user` | auth.User | auth.User | à_arbitrer (A probable : CreateModel des deux côtés) |
| `auth_user_groups` | auth.User_groups | auth.User_groups | à_arbitrer (aucun CreateModel trouvé) |
| `auth_user_user_permissions` | auth.User_user_permissions | auth.User_user_permissions | à_arbitrer (aucun CreateModel trouvé) |
| `authentication_facilitator` | authentication.Facilitator | authentication.Facilitator | à_arbitrer (B probable : schéma possédé par cdd) |
| `authtoken_token` | authtoken.Token, authtoken.TokenProxy | authtoken.Token, authtoken.TokenProxy | à_arbitrer (A probable : CreateModel des deux côtés) |
| `django_admin_log` | admin.LogEntry | admin.LogEntry | reconstruite (§4.6) |
| `django_celery_results_chordcounter` | django_celery_results.ChordCounter | django_celery_results.ChordCounter | reconstruite (§4.6) |
| `django_celery_results_groupresult` | django_celery_results.GroupResult | django_celery_results.GroupResult | reconstruite (§4.6) |
| `django_celery_results_taskresult` | django_celery_results.TaskResult | django_celery_results.TaskResult | reconstruite (§4.6) |
| `django_content_type` | contenttypes.ContentType | contenttypes.ContentType | reconstruite (§4.6) |
| `django_session` | sessions.Session | sessions.Session | reconstruite (§4.6) |
| `process_manager_administrativelevelwave` | process_manager.AdministrativeLevelWave | process_manager.AdministrativeLevelWave | à_arbitrer (A probable : CreateModel des deux côtés) |
| `process_manager_wave` | process_manager.Wave | process_manager.Wave | à_arbitrer (A probable : CreateModel des deux côtés) |
| `subprojects_component` | subprojects.Component | subprojects.Component | à_arbitrer (B probable : schéma possédé par cosomis) |
| `subprojects_cycle` | subprojects.Cycle | subprojects.Cycle | à_arbitrer (B probable : schéma possédé par cosomis) |
| `subprojects_cycle_administrative_levels` | subprojects.Cycle_administrative_levels | subprojects.Cycle_administrative_levels | à_arbitrer (aucun CreateModel trouvé) |
| `subprojects_financier` | subprojects.Financier | subprojects.Financier | à_arbitrer (B probable : schéma possédé par cosomis) |
| `subprojects_project` | subprojects.Project | subprojects.Project | à_arbitrer (B probable : schéma possédé par cosomis) |
| `subprojects_project_administrative_levels` | subprojects.Project_administrative_levels | subprojects.Project_administrative_levels | à_arbitrer (aucun CreateModel trouvé) |
| `subprojects_project_financiers` | subprojects.Project_financiers | subprojects.Project_financiers | à_arbitrer (aucun CreateModel trouvé) |
| `subprojects_subproject` | subprojects.Subproject | subprojects.Subproject | à_arbitrer (B probable : schéma possédé par cosomis) |
| `subprojects_subproject_projects` | subprojects.Subproject_projects | subprojects.Subproject_projects | à_arbitrer (aucun CreateModel trouvé) |
| `subprojects_typemain` | subprojects.TypeMain | subprojects.TypeMain | à_arbitrer (B probable : schéma possédé par cosomis) |
| `subprojects_villagegoal` | subprojects.VillageGoal | subprojects.VillageGoal | à_arbitrer (B probable : schéma possédé par cosomis) |
| `subprojects_villagemeeting` | subprojects.VillageMeeting | subprojects.VillageMeeting | à_arbitrer (B probable : schéma possédé par cosomis) |
| `subprojects_villageobstacle` | subprojects.VillageObstacle | subprojects.VillageObstacle | à_arbitrer (B probable : schéma possédé par cosomis) |
| `subprojects_villagepriority` | subprojects.VillagePriority | subprojects.VillagePriority | à_arbitrer (B probable : schéma possédé par cosomis) |
| `subprojects_vulnerablegroup` | subprojects.VulnerableGroup | subprojects.VulnerableGroup | à_arbitrer (B probable : schéma possédé par cosomis) |

## 3. Colonnes divergentes sur tables homonymes

Pour chaque table présente des deux côtés dans le code : champs seulement CDD, seulement COSOMIS, ou de type différent.


### `administrativelevels_administrativelevel`
- **administrativelevels.AdministrativeLevel** vs **administrativelevels.AdministrativeLevel**
- champs seulement COSOMIS : area_status, delete_by_user
- types divergents : latitude (CDD FloatField/None vs COSOMIS DecimalField/None); longitude (CDD FloatField/None vs COSOMIS DecimalField/None)

### `administrativelevels_cvd`
- **administrativelevels.CVD** vs **administrativelevels.CVD**
- champs seulement COSOMIS : account_number, bank, bank_code, delete_by_user, guichet_code, rib
- types divergents : president_phone_of_the_cvd (CDD CharField/15 vs COSOMIS CharField/100); secretary_phone_of_the_cvd (CDD CharField/15 vs COSOMIS CharField/100); treasurer_phone_of_the_cvd (CDD CharField/15 vs COSOMIS CharField/100)

### `administrativelevels_geographicalunit`
- **administrativelevels.GeographicalUnit** vs **administrativelevels.GeographicalUnit**
- champs seulement COSOMIS : delete_by_user

### `assignments_assignadministrativeleveltofacilitator`
- **assignments.AssignAdministrativeLevelToFacilitator** vs **assignments.AssignAdministrativeLevelToFacilitator**
- champs seulement CDD : administrative_level_id, project_id
- champs seulement COSOMIS : administrative_level, delete_by_user, project
- types divergents : facilitator_id (CDD IntegerField/None vs COSOMIS CharField/255)

### `authentication_facilitator`
- **authentication.Facilitator** vs **authentication.Facilitator**
- champs seulement CDD : create_by_user, created_date, no_sql_dbs_names, update_by_user, updated_date, users_involved
- types divergents : code (CDD CharField/100 vs COSOMIS CharField/6)

### `process_manager_administrativelevelwave`
- **process_manager.AdministrativeLevelWave** vs **process_manager.AdministrativeLevelWave**
- champs seulement CDD : administrative_level_id, cycle
- champs seulement COSOMIS : administrative_level, delete_by_user

### `process_manager_wave`
- **process_manager.Wave** vs **process_manager.Wave**
- champs seulement COSOMIS : delete_by_user

### `subprojects_component`
- **subprojects.Component** vs **subprojects.Component**
- champs seulement COSOMIS : amount, category, delete_by_user, external_id, project, target

### `subprojects_cycle`
- **subprojects.Cycle** vs **subprojects.Cycle**
- champs seulement CDD : project_id
- champs seulement COSOMIS : delete_by_user, project

### `subprojects_financier`
- **subprojects.Financier** vs **subprojects.Financier**
- champs seulement COSOMIS : delete_by_user

### `subprojects_project`
- **subprojects.Project** vs **subprojects.Project**
- champs seulement COSOMIS : delete_by_user, external_id, parent, status

### `subprojects_subproject`
- **subprojects.Subproject** vs **subprojects.Subproject**
- champs seulement COSOMIS : amount_of_the_care_and_maintenance_fund_expected_to_be_mobilized, amount_of_the_contract_for_construction_supervisors, amount_of_the_controllers_contract_in_SES, amount_of_the_facilitator_contract, amount_spent_on_completing_the_infrastructure, amount_spent_on_infrastructure_up_to_provisional_acceptance, approval_date_cora, breeders_farmers_group, canton, care_and_maintenance_amount_on_village_account, comments, component, contract_amount_work_companies, contract_companies_amount_for_efme, contract_number_of_work_companies, convention, current_level_of_physical_realization_of_the_work, current_level_of_physical_realization_of_the_work_percent, current_level_of_physical_realization_of_the_work_wording, current_status_of_the_site, date_of_final_acceptance_of_the_work, date_of_organization_of_the_social_audit, date_of_provisional_acceptance_of_work_contracts, date_of_signature_of_contract_for_construction_supervisors, date_of_technical_acceptance_of_work_contracts, date_signature_contract_controllers_in_SES, date_signature_contract_efme, date_signature_contract_facilitator, date_signature_contract_work_companies, delete_by_user, depth_of_drilling, direct_beneficiaries_men, direct_beneficiaries_women, distance_covered_by_streetlights, drilling_flow_rate, estimated_cost, estimated_number_of_beneficiaries, ethnic_minority_group, exact_amount_spent, existence_of_maintenance_and_upkeep_plan_developed_by_community, expected_duration_of_the_work, expected_end_date_of_the_contract, extension_length, facilitator_name, full_title_of_approved_subproject, has_fence, has_latrine_blocs, indirect_beneficiaries_men, indirect_beneficiaries_women, infrastructure_changed, intervention_unit, joint_subproject_number, latitude, launch_date_of_the_construction_site_in_the_village, length_of_the_track, level_of_achievement_donation_certificate, link_to_subproject, longitude, lot, market_name, name_of_company_awarded_efme, name_of_the_awarded_company_works_companies, number, number_of_classrooms, number_of_drinking_fountains, number_of_infrastructures, number_of_latrine_blocks, number_of_participants_m_in_the_social_audit, number_of_participants_t_in_the_social_audit, number_of_participants_w_in_the_social_audit, number_of_sections_of_track_developed, number_of_streetlights, official_handover_date_of_the_microproject_to_the_community, official_handover_date_of_the_microproject_to_the_sector, population, priority, provisional_acceptance_date_for_efme_contracts, refugee_and_internally_displaced_persons_group, storage_capacity, subproject_sector, subproject_type_designation, target_female_beneficiaries, target_male_beneficiaries, target_youth_beneficiaries, technical_acceptance_date_for_efme_contracts, total_contract_amount_paid, type_of_subproject, wave, women_s_group, work_completion_date, works_type, youth_group

### `subprojects_typemain`
- **subprojects.TypeMain** vs **subprojects.TypeMain**
- champs seulement COSOMIS : delete_by_user

### `subprojects_villagegoal`
- **subprojects.VillageGoal** vs **subprojects.VillageGoal**
- champs seulement COSOMIS : delete_by_user

### `subprojects_villagemeeting`
- **subprojects.VillageMeeting** vs **subprojects.VillageMeeting**
- champs seulement COSOMIS : delete_by_user

### `subprojects_villageobstacle`
- **subprojects.VillageObstacle** vs **subprojects.VillageObstacle**
- champs seulement COSOMIS : delete_by_user

### `subprojects_villagepriority`
- **subprojects.VillagePriority** vs **subprojects.VillagePriority**
- champs seulement COSOMIS : delete_by_user

### `subprojects_vulnerablegroup`
- **subprojects.VulnerableGroup** vs **subprojects.VulnerableGroup**
- champs seulement COSOMIS : delete_by_user

## 4. Colonnes « FK molles » (entier `*_id`/`*_ids`, pas de ForeignKey)

| Projet | Modèle | Champ | Type | null |
|---|---|---|---|---|
| cdd | admin.LogEntry | `object_id` | TextField | True |
| cdd | process_manager.Project | `couch_id` | CharField | False |
| cdd | process_manager.Cycle | `couch_id` | CharField | False |
| cdd | process_manager.Phase | `couch_id` | CharField | False |
| cdd | process_manager.Activity | `couch_id` | CharField | False |
| cdd | process_manager.Task | `couch_id` | CharField | False |
| cdd | process_manager.AggregatedStatus | `administrative_level_id` | IntegerField | True |
| cdd | process_manager.AdministrativeLevelWave | `administrative_level_id` | IntegerField | False |
| cdd | administrativelevels.AdministrativeLevel | `no_sql_db_id` | CharField | True |
| cdd | assignments.AssignAdministrativeLevelToFacilitator | `administrative_level_id` | IntegerField | False |
| cdd | assignments.AssignAdministrativeLevelToFacilitator | `facilitator_id` | IntegerField | False |
| cdd | assignments.AssignAdministrativeLevelToFacilitator | `project_id` | IntegerField | False |
| cdd | subprojects.Cycle | `project_id` | IntegerField | False |
| cdd | reports.VillageCommittee | `cvd_id` | IntegerField | False |
| cdd | reports.VillageCommittee | `village_headquarters_id` | IntegerField | False |
| cdd | django_celery_results.TaskResult | `task_id` | CharField | False |
| cdd | django_celery_results.ChordCounter | `group_id` | CharField | False |
| cdd | django_celery_results.GroupResult | `group_id` | CharField | False |
| cosomis | admin.LogEntry | `object_id` | TextField | True |
| cosomis | subprojects.CategoryIDA | `external_id` | CharField | True |
| cosomis | subprojects.Component | `external_id` | CharField | True |
| cosomis | subprojects.SubprojectFile | `facilitator_id` | IntegerField | True |
| cosomis | subprojects.Project | `external_id` | CharField | True |
| cosomis | administrativelevels.AdministrativeLevel | `no_sql_db_id` | CharField | True |
| cosomis | authentication.GovernmentWorker | `administrative_id` | CharField | True |
| cosomis | assignments.AssignAdministrativeLevelToFacilitator | `facilitator_id` | CharField | False |
| cosomis | financial.Account | `external_id` | CharField | True |
| cosomis | financial.Funding | `external_id` | CharField | True |
| cosomis | financial.AnnualWorkPlan | `external_id` | CharField | True |
| cosomis | financial.Activity | `external_id` | CharField | True |
| cosomis | financial.ActivityFunding | `external_id` | CharField | True |
| cosomis | financial.SupportingDocument | `external_id` | CharField | True |
| cosomis | financial.SupportingDocumentActivity | `external_id` | CharField | True |
| cosomis | financial.SupportingDocumentActivityFile | `external_id` | CharField | True |
| cosomis | financial.BankTransfer | `external_id` | CharField | True |
| cosomis | financial.DisbursementRequest | `external_id` | CharField | True |
| cosomis | financial.DisbursementRequestValidation | `external_id` | CharField | True |
| cosomis | financial.Disbursement | `external_id` | CharField | True |
| cosomis | custom_file.CustomerFile | `object_id` | IntegerField | False |
| cosomis | django_celery_results.TaskResult | `task_id` | CharField | False |
| cosomis | django_celery_results.ChordCounter | `group_id` | CharField | False |
| cosomis | django_celery_results.GroupResult | `group_id` | CharField | False |

## 5. Champs JSON (§1)

### 5.a Candidats « listes d'ID » (à remapper via id_map, §4.4)

| Projet | Modèle | Champ |
|---|---|---|
| cdd | authentication.Facilitator | `administrative_levels_ids` |
| cdd | authentication.Facilitator | `stabilization_administrative_ids` |
| cdd | authentication.Facilitator | `additional_administrative_ids` |
| cdd | planning.Activity | `administrative_level_ids` |
| cdd | reports.VillageCommittee | `villages_ids` |
| cosomis | authentication.Facilitator | `administrative_levels_ids` |
| cosomis | authentication.Facilitator | `stabilization_administrative_ids` |
| cosomis | authentication.Facilitator | `additional_administrative_ids` |
| cosomis | authentication.GovernmentWorker | `administrative_ids` |

### 5.b Autres champs JSON (hors audit `*_by_user`/`users_involved`) — à inspecter manuellement

| Projet | Modèle | Champ |
|---|---|---|
| cdd | authentication.Facilitator | `no_sql_dbs_names` |
| cdd | authentication.Facilitator | `administrative_levels` |
| cdd | process_manager.Cycle | `capacity_attachments` |
| cdd | process_manager.Phase | `capacity_attachments` |
| cdd | process_manager.Activity | `capacity_attachments` |
| cdd | process_manager.Task | `form` |
| cdd | process_manager.Task | `attachments` |
| cdd | process_manager.Task | `capacity_attachments` |
| cdd | process_manager.AggregatedStatusFacilitator | `administrative_level_headquarters_villages_infos` |
| cdd | process_manager.EmailAddressesWhichSendEmails | `email_addresses` |
| cdd | process_manager.ProcessAddOrRemoveADL | `administrative_levels` |
| cdd | news.News | `administrative_levels` |
| cdd | news.News | `projects` |
| cdd | planning.Activity | `administrative_levels` |
| cdd | planning.Activity | `another_detail` |
| cdd | planning.ActivityGeolocation | `geolocation_start` |
| cdd | planning.ActivityGeolocation | `geolocation_end` |
| cdd | reports.VillageCommittee | `villages_names` |
| cdd | reports.VillageCommittee | `members` |
| cosomis | subprojects.Subproject | `priority` |
| cosomis | authentication.Facilitator | `administrative_levels` |

## 6. Accès inter-bases dans le code (indicateur)


### projet cdd
- `.using(` : 191 occurrence(s)
  - grm_client.py:145
  - grm_client.py:174
  - grm_client.py:178
  - administrativelevels/functions.py:6
  - administrativelevels/functions.py:14
  - administrativelevels/functions.py:15
  - administrativelevels/functions.py:16
  - administrativelevels/functions.py:19
  - administrativelevels/functions.py:20
  - administrativelevels/functions.py:23
  - administrativelevels/functions.py:25
  - administrativelevels/functions.py:28
  - administrativelevels/functions.py:29
  - administrativelevels/functions.py:31
  - administrativelevels/functions.py:32
  - administrativelevels/functions.py:34
  - administrativelevels/functions.py:35
  - administrativelevels/views.py:22
  - authentication/models.py:508
  - authentication/models.py:523
  - authentication/models.py:531
  - authentication/models.py:544
  - cdd/call_objects_from_other_db.py:11
  - cdd/call_objects_from_other_db.py:14
  - cdd/call_objects_from_other_db.py:17
  - cdd/call_objects_from_other_db.py:20
  - cdd/merge_routers.py:5
  - cdd/utils.py:17
  - dashboard/tasks.py:132
  - dashboard/utils.py:147
  - dashboard/utils.py:151
  - dashboard/utils.py:358
  - dashboard/utils.py:1088
  - dashboard/utils.py:1202
  - dashboard/utils.py:1472
  - dashboard/utils.py:2389
  - dashboard/utils.py:2460
  - dashboard/utils.py:2675
  - dashboard/utils.py:2692
  - dashboard/utils.py:2871
  - … (+151)
- `mis_objects_call` : 229 occurrence(s)
  - authentication/functions.py:5
  - authentication/functions.py:10
  - authentication/functions.py:16
  - authentication/models.py:442
  - authentication/api/facilitators/update_adl.py:16
  - authentication/api/facilitators/update_adl.py:42
  - authentication/api/facilitators/update_adl.py:47
  - authentication/api/facilitators/update_adl.py:52
  - cdd/call_objects_from_other_db.py:30
  - dashboard/context_processors.py:6
  - dashboard/functions.py:1
  - dashboard/functions.py:33
  - dashboard/tasks.py:17
  - dashboard/tasks.py:214
  - dashboard/tasks.py:216
  - dashboard/tasks.py:224
  - dashboard/tasks.py:286
  - dashboard/tasks.py:472
  - dashboard/tasks.py:474
  - dashboard/tasks.py:490
  - dashboard/tasks.py:491
  - dashboard/tasks.py:632
  - dashboard/utils.py:20
  - dashboard/utils.py:120
  - dashboard/utils.py:120
  - dashboard/utils.py:122
  - dashboard/utils.py:136
  - dashboard/utils.py:191
  - dashboard/utils.py:191
  - dashboard/utils.py:195
  - dashboard/utils.py:195
  - dashboard/utils.py:1795
  - dashboard/utils.py:1798
  - dashboard/utils.py:2440
  - dashboard/utils.py:2501
  - dashboard/utils.py:2528
  - dashboard/utils.py:2648
  - dashboard/utils.py:2843
  - dashboard/utils.py:3009
  - dashboard/utils.py:3515
  - … (+189)
- `cdd_objects_call` : 18 occurrence(s)
  - cdd/call_objects_from_other_db.py:32
  - usermanager/functions.py:19
  - usermanager/functions.py:114
  - usermanager/functions.py:116
  - usermanager/views.py:17
  - usermanager/views.py:38
  - usermanager/views.py:40
  - usermanager/views_change_password.py:24
  - usermanager/views_change_password.py:107
  - usermanager/views_change_password.py:109
  - usermanager/views_forget_password.py:25
  - usermanager/views_forget_password.py:39
  - usermanager/views_forget_password.py:41
  - usermanager/views_forget_password.py:152
  - usermanager/views_forget_password.py:154
  - usermanager/api/views_change_password.py:24
  - usermanager/api/views_change_password.py:121
  - usermanager/api/views_change_password.py:123
- `grm_objects_call` : 6 occurrence(s)
  - cdd/call_objects_from_other_db.py:31
  - usermanager/functions.py:19
  - usermanager/views.py:17
  - usermanager/views_change_password.py:24
  - usermanager/views_forget_password.py:25
  - usermanager/api/views_change_password.py:24

### projet cosomis
- `.using(` : 18 occurrence(s)
  - administrativelevels/models.py:135
  - administrativelevels/models.py:141
  - administrativelevels/views_components.py:104
  - assignments/functions.py:26
  - assignments/functions.py:32
  - assignments/functions.py:40
  - assignments/models.py:28
  - authentication/models.py:40
  - cosomis/call_objects_from_other_db.py:11
  - cosomis/call_objects_from_other_db.py:14
  - cosomis/call_objects_from_other_db.py:17
  - cosomis/utils.py:26
  - cosomis/utils.py:28
  - cosomis/utils.py:107
  - cosomis/utils.py:109
  - subprojects/export/views.py:259
  - usermanager/api/auth/login.py:40
  - usermanager/api/auth/login.py:63
- `mis_objects_call` : 0 occurrence(s)
- `cdd_objects_call` : 4 occurrence(s)
  - cosomis/call_objects_from_other_db.py:27
  - process_manager/utils.py:1
  - process_manager/utils.py:7
  - process_manager/utils.py:8
- `grm_objects_call` : 3 occurrence(s)
  - assignments/functions.py:5
  - assignments/functions.py:72
  - cosomis/call_objects_from_other_db.py:28
