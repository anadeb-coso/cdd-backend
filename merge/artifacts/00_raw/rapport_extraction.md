# Rapport — Étape 0 : Extraction

- Mode : APPLY (données écrites)
- Généré : 2026-09-22T17:40:13
- Convention CSV : séparateur `,`, fin de ligne `\n`, NULL = `\N`, encodage UTF-8. L'Étape 5 (COPY) devra utiliser `NULL E'\\N'`.

## cdd — `cdd` (MySQL/MariaDB 10.4.32-MariaDB)
- 59 tables, 154671 lignes au total

| table | lignes | max(id) |
|---|---:|---:|
| `auth_group` | 31 | 31 |
| `auth_group_permissions` | 0 |  |
| `auth_permission` | 248 | 248 |
| `auth_user` | 82 | 84 |
| `auth_user_groups` | 89 | 181 |
| `auth_user_user_permissions` | 0 |  |
| `authentication_facilitator` | 241 | 712 |
| `authtoken_token` | 0 |  |
| `django_admin_log` | 1110 | 1110 |
| `django_celery_results_chordcounter` | 0 |  |
| `django_celery_results_groupresult` | 0 |  |
| `django_celery_results_taskresult` | 0 |  |
| `django_content_type` | 62 | 62 |
| `django_migrations` | 165 | 165 |
| `django_session` | 1235 |  |
| `news_category` | 10 | 10 |
| `news_news` | 107 | 167 |
| `news_news_tags` | 228 | 305 |
| `news_newsfile` | 398 | 528 |
| `news_subscription` | 158 | 429 |
| `news_tag` | 28 | 28 |
| `planning_activity` | 15196 | 16622 |
| `planning_activitycomment` | 42 | 47 |
| `planning_activitydeadline` | 0 |  |
| `planning_activitydeadline_activities_deadline_groups` | 0 |  |
| `planning_activityfile` | 7273 | 7429 |
| `planning_activitygeolocation` | 3341 | 3361 |
| `planning_activityvalidate` | 12339 | 12339 |
| `planning_validationgroupsprocess` | 4 | 4 |
| `planning_validationgroupsprocess_planners_groups` | 16 | 20 |
| `planning_validationgroupsprocess_validators_groups` | 8 | 21 |
| `process_manager_activity` | 48 | 50 |
| `process_manager_activity_cycles` | 48 | 48 |
| `process_manager_administrativelevelwave` | 35 | 35 |
| `process_manager_aggregatedstatus` | 99812 | 486774 |
| `process_manager_aggregatedstatusfacilitator` | 298 | 1400 |
| `process_manager_cycle` | 3 | 3 |
| `process_manager_deployment` | 5 | 5 |
| `process_manager_emailaddresseswhichsendemails` | 3 | 3 |
| `process_manager_facilitatordeployment` | 0 |  |
| `process_manager_facilitatorwave` | 50 | 50 |
| `process_manager_phase` | 17 | 19 |
| `process_manager_phase_cycles` | 17 | 17 |
| `process_manager_processaddorremoveadl` | 533 | 533 |
| `process_manager_project` | 3 | 6 |
| `process_manager_project_facilitators` | 388 | 1417 |
| `process_manager_project_users` | 160 | 165 |
| `process_manager_task` | 137 | 154 |
| `process_manager_task_cycles` | 137 | 137 |
| `process_manager_task_groups_collectors` | 0 |  |
| `process_manager_tasksharerecord` | 0 |  |
| `process_manager_wave` | 5 | 5 |
| `reports_villagecommittee` | 9676 | 9676 |
| `storeapp_storeapp` | 33 | 38 |
| `storeapp_storeproject` | 2 | 2 |
| `supportmaterial_lesson` | 11 | 13 |
| `supportmaterial_subject` | 5 | 6 |
| `supportmaterial_supportingmaterial` | 13 | 15 |
| `usermanager_validationcode` | 821 | 821 |

## mis — `mis` (MySQL/MariaDB 10.4.32-MariaDB)
- 72 tables, 51497 lignes au total

| table | lignes | max(id) |
|---|---:|---:|
| `administrativelevels_administrativelevel` | 2199 | 6832 |
| `administrativelevels_cvd` | 1740 | 1822 |
| `administrativelevels_geographicalunit` | 1669 | 1745 |
| `assignments_assignadministrativeleveltofacilitator` | 2159 | 2611 |
| `auth_group` | 31 | 31 |
| `auth_group_permissions` | 0 |  |
| `auth_permission` | 232 | 232 |
| `auth_user` | 79 | 81 |
| `auth_user_groups` | 80 | 135 |
| `auth_user_user_permissions` | 0 |  |
| `authtoken_token` | 0 |  |
| `custom_file_customerfile` | 0 |  |
| `django_admin_log` | 663 | 663 |
| `django_celery_results_chordcounter` | 0 |  |
| `django_celery_results_groupresult` | 0 |  |
| `django_celery_results_taskresult` | 0 |  |
| `django_content_type` | 57 | 57 |
| `django_migrations` | 181 | 181 |
| `django_session` | 359 |  |
| `financial_account` | 154 | 154 |
| `financial_activity` | 0 |  |
| `financial_activity_funding` | 0 |  |
| `financial_activity_structures_impliquees` | 0 |  |
| `financial_activity_structures_responsables` | 0 |  |
| `financial_administrativelevel_allocation` | 214 | 305 |
| `financial_annual_work_plan` | 0 |  |
| `financial_bank` | 1 | 1 |
| `financial_bank_transfer` | 153 | 235 |
| `financial_bank_transfer_disbursements` | 0 |  |
| `financial_bank_transfer_supporting_documents` | 0 |  |
| `financial_disbursement` | 0 |  |
| `financial_disbursement_request` | 0 |  |
| `financial_disbursement_request_validation` | 0 |  |
| `financial_funding` | 0 |  |
| `financial_supporting_document` | 0 |  |
| `financial_supporting_document_activity` | 0 |  |
| `financial_supporting_document_activity_file` | 0 |  |
| `financial_tag` | 0 |  |
| `process_manager_administrativelevelwave` | 59 | 94 |
| `process_manager_periodwave` | 10 | 10 |
| `process_manager_periodwave_administrative_levels` | 70 | 70 |
| `process_manager_project` | 3 | 3 |
| `process_manager_project_administrative_levels` | 2625 | 5403 |
| `process_manager_project_financiers` | 2 | 2 |
| `process_manager_wave` | 6 | 6 |
| `subprojects_category_ida` | 0 |  |
| `subprojects_component` | 20 | 30 |
| `subprojects_component_fundings` | 0 |  |
| `subprojects_cycle` | 3 | 3 |
| `subprojects_cycle_administrative_levels` | 2624 | 5616 |
| `subprojects_filecomment` | 16 | 30 |
| `subprojects_financier` | 1 | 1 |
| `subprojects_level` | 1121 | 1497 |
| `subprojects_step` | 20 | 20 |
| `subprojects_step_next_steps` | 44 | 44 |
| `subprojects_subproject` | 1541 | 2129 |
| `subprojects_subproject_financiers` | 2 | 4 |
| `subprojects_subproject_list_of_beneficiary_villages` | 11054 | 21156 |
| `subprojects_subproject_list_of_villages_crossed_by_the_trackfee7` | 16 | 25 |
| `subprojects_subproject_priorities` | 0 |  |
| `subprojects_subproject_projects` | 1541 | 6417 |
| `subprojects_subprojectfile` | 7828 | 8516 |
| `subprojects_subprojectsector` | 0 |  |
| `subprojects_subprojectstep` | 12842 | 20869 |
| `subprojects_subprojecttype` | 0 |  |
| `subprojects_typemain` | 0 |  |
| `subprojects_villagegoal` | 0 |  |
| `subprojects_villagemeeting` | 0 |  |
| `subprojects_villageobstacle` | 0 |  |
| `subprojects_villagepriority` | 0 |  |
| `subprojects_vulnerablegroup` | 0 |  |
| `usermanager_usertoken` | 78 | 78 |

