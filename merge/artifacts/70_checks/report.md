# Rapport — Contrôles d'acceptation (§6)

- Généré : 2026-09-03T17:30:53
- Base : cdd_cosomis_unified (PostgreSQL 18)
- Contrôles 1-5 automatisés : ✅ tous passés
- Contrôles §6.6 (code), §6.7 (non-régression), §6.8 (casse) : **non exécutés** — nécessitent les dépôts adaptés (Étape 6) sur PG.
- La bascule production reste **non prononcée** tant que les contrôles §6.6-6.8 ne sont pas levés.

## 1. Comptage (§6.1) — ✅
- ✅ `administrativelevels_administrativelevel` [mirror] attendu 2199, PG 2199
- ✅ `administrativelevels_cvd` [mirror] attendu 1740, PG 1740
- ✅ `administrativelevels_geographicalunit` [mirror] attendu 1669, PG 1669
- ✅ `assignments_assignadministrativeleveltofacilitator` [mirror] attendu 2159, PG 2159
- ✅ `auth_group` [merge] attendu 31, PG 31
- ✅ `auth_group_permissions` [merge] attendu 0, PG 0
- ✅ `auth_user` [merge] attendu 83, PG 83
- ✅ `auth_user_groups` [merge] attendu 91, PG 91
- ✅ `auth_user_user_permissions` [merge] attendu 0, PG 0
- ✅ `authentication_facilitator` [mirror] attendu 241, PG 241
- ✅ `authtoken_token` [merge] attendu 0, PG 0
- ✅ `custom_file_customerfile` [mis_only] attendu 0, PG 0
- ✅ `financial_account` [mis_only] attendu 154, PG 154
- ✅ `financial_activity` [mis_only] attendu 0, PG 0
- ✅ `financial_activity_funding` [mis_only] attendu 0, PG 0
- ✅ `financial_activity_structures_impliquees` [mis_only] attendu 0, PG 0
- ✅ `financial_activity_structures_responsables` [mis_only] attendu 0, PG 0
- ✅ `financial_administrativeLevel_allocation` [mis_only] attendu 214, PG 214
- ✅ `financial_annual_work_plan` [mis_only] attendu 0, PG 0
- ✅ `financial_bank` [mis_only] attendu 1, PG 1
- ✅ `financial_bank_transfer` [mis_only] attendu 153, PG 153
- ✅ `financial_bank_transfer_disbursements` [mis_only] attendu 0, PG 0
- ✅ `financial_bank_transfer_supporting_documents` [mis_only] attendu 0, PG 0
- ✅ `financial_disbursement` [mis_only] attendu 0, PG 0
- ✅ `financial_disbursement_request` [mis_only] attendu 0, PG 0
- ✅ `financial_disbursement_request_validation` [mis_only] attendu 0, PG 0
- ✅ `financial_funding` [mis_only] attendu 0, PG 0
- ✅ `financial_supporting_document` [mis_only] attendu 0, PG 0
- ✅ `financial_supporting_document_activity` [mis_only] attendu 0, PG 0
- ✅ `financial_supporting_document_activity_file` [mis_only] attendu 0, PG 0
- ✅ `financial_tag` [mis_only] attendu 0, PG 0
- ✅ `news_category` [cdd_only] attendu 10, PG 10
- ✅ `news_news` [cdd_only] attendu 107, PG 107
- ✅ `news_news_tags` [cdd_only] attendu 228, PG 228
- ✅ `news_newsfile` [cdd_only] attendu 398, PG 398
- ✅ `news_subscription` [cdd_only] attendu 158, PG 158
- ✅ `news_tag` [cdd_only] attendu 28, PG 28
- ✅ `planning_activity` [cdd_only] attendu 14890, PG 14890
- ✅ `planning_activitycomment` [cdd_only] attendu 42, PG 42
- ✅ `planning_activitydeadline` [cdd_only] attendu 0, PG 0
- ✅ `planning_activitydeadline_activities_deadline_groups` [cdd_only] attendu 0, PG 0
- ✅ `planning_activityfile` [cdd_only] attendu 7239, PG 7239
- ✅ `planning_activitygeolocation` [cdd_only] attendu 3336, PG 3336
- ✅ `planning_activityvalidate` [cdd_only] attendu 12214, PG 12214
- ✅ `planning_validationgroupsprocess` [cdd_only] attendu 4, PG 4
- ✅ `planning_validationgroupsprocess_planners_groups` [cdd_only] attendu 16, PG 16
- ✅ `planning_validationgroupsprocess_validators_groups` [cdd_only] attendu 8, PG 8
- ✅ `process_manager_activity` [cdd_only] attendu 48, PG 48
- ✅ `process_manager_activity_cycles` [cdd_only] attendu 48, PG 48
- ✅ `process_manager_administrativelevelwave` [merge] attendu 59, PG 59
- ✅ `process_manager_aggregatedstatus` [cdd_only] attendu 99812, PG 99812
- ✅ `process_manager_aggregatedstatusfacilitator` [cdd_only] attendu 298, PG 298
- ✅ `process_manager_cycle` [cdd_only] attendu 3, PG 3
- ✅ `process_manager_deployment` [cdd_only] attendu 5, PG 5
- ✅ `process_manager_emailaddresseswhichsendemails` [cdd_only] attendu 3, PG 3
- ✅ `process_manager_facilitatordeployment` [cdd_only] attendu 0, PG 0
- ✅ `process_manager_facilitatorwave` [cdd_only] attendu 50, PG 50
- ✅ `process_manager_periodwave` [mis_only] attendu 10, PG 10
- ✅ `process_manager_periodwave_administrative_levels` [mis_only] attendu 70, PG 70
- ✅ `process_manager_phase` [cdd_only] attendu 17, PG 17
- … (+45 lignes)

## 2. Identité des ID (§6.2) — ✅
- ✅ ensembles d'`id` identiques (unifié ↔ PG) sur 104 tables

## 3. Intégrité référentielle (§6.3) — ✅
- ✅ 0 FK orpheline sur 187 contraintes

## 4. Séquences (§6.4) — ✅
- ✅ 55 séquences : last_value ≥ MAX(id)

## 5. Échantillon (§6.5) — ✅
- ✅ `administrativelevels_administrativelevel` : 0/20 lignes divergentes (colonnes ['id', 'name', 'type', 'latitude']…)
- ✅ `administrativelevels_cvd` : 0/20 lignes divergentes (colonnes ['id', 'attributed_number_in_canton', 'unique_code', 'president_name_of_the_cvd']…)
- ✅ `administrativelevels_geographicalunit` : 0/20 lignes divergentes (colonnes ['id', 'attributed_number_in_canton', 'unique_code', 'description']…)
- ✅ `assignments_assignadministrativeleveltofacilitator` : 0/20 lignes divergentes (colonnes ['id', 'created_date', 'updated_date', 'facilitator_id']…)
- ✅ `auth_group` : 0/20 lignes divergentes (colonnes ['id', 'name']…)
- ✅ `auth_user` : 0/20 lignes divergentes (colonnes ['id', 'password', 'last_login', 'is_superuser']…)
- ✅ `auth_user_groups` : 0/20 lignes divergentes (colonnes ['id', 'user_id', 'group_id']…)
- ✅ `authentication_facilitator` : 0/20 lignes divergentes (colonnes ['id', 'no_sql_user', 'no_sql_pass', 'no_sql_db_name']…)
- ✅ `process_manager_administrativelevelwave` : 0/20 lignes divergentes (colonnes ['id', 'created_date', 'updated_date', 'administrative_level_id']…)
- ✅ `process_manager_wave` : 0/6 lignes divergentes (colonnes ['id', 'created_date', 'updated_date', 'number']…)
- ✅ `subprojects_component` : 0/10 lignes divergentes (colonnes ['id', 'created_date', 'updated_date', 'name']…)
- ✅ `subprojects_cycle` : 0/3 lignes divergentes (colonnes ['id', 'created_date', 'updated_date', 'create_by_user']…)
- ✅ `subprojects_cycle_administrative_levels` : 0/20 lignes divergentes (colonnes ['id', 'cycle_id', 'administrativelevel_id']…)
- ✅ `subprojects_financier` : 0/1 lignes divergentes (colonnes ['id', 'created_date', 'updated_date', 'name']…)
- ✅ `subprojects_project` : 0/3 lignes divergentes (colonnes ['id', 'created_date', 'updated_date', 'name']…)
- ✅ `subprojects_project_administrative_levels` : 0/20 lignes divergentes (colonnes ['id', 'project_id', 'administrativelevel_id']…)
- ✅ `subprojects_project_financiers` : 0/2 lignes divergentes (colonnes ['id', 'project_id', 'financier_id']…)
- ✅ `subprojects_subproject` : 0/20 lignes divergentes (colonnes ['id', 'created_date', 'updated_date', 'target_female_beneficiaries']…)
- ✅ `subprojects_subproject_projects` : 0/20 lignes divergentes (colonnes ['id', 'subproject_id', 'project_id']…)

## 6-8. Contrôles nécessitant les codebases adaptées — à faire
- **§6.6 Code** : appliquer `merge/artifacts/60_code/` aux dépôts puis `manage.py check` + `makemigrations --check --dry-run` (CDD et COSOMIS) sur PG.
- **§6.7 Non-régression** : produire fc_situation / views_docx / tableau de bord financier avant (MySQL) et après (PG), comparer.
- **§6.8 Casse** : jeu de tests `get(username=…)` / `get(name=…)` avec casse différente, vérifier `__iexact`.
