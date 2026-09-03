# Rapport — Étape 1 : Inventaire (volet code)

- Projet CDD : `D:\COSO\PROJECTS\CDD\backend\deploy\cdd-backend\src` (Django 4.0.4, 76 modèles)
- Projet COSOMIS : `D:\COSO\PROJECTS\MIS\cosomis\cosomis` (Django 4.2.30, 77 modèles)
- Alias base CDD : ['default', 'mis', 'grm']
- Alias base COSOMIS : ['default', 'cdd']
- Routeurs CDD : ["'cdd.merge_routers.CddMergeRouter'"]
- Routeurs COSOMIS : ["'cosomis.merge_routers.CosomisMergeRouter'"]

## Chiffres clés
- Modèles de même `object_name` : **38**
- Tables (db_table) de même nom : **35**
- Tables vues dans le code ou les bases : **117**

## Étape 0 : intégrée
- Bases physiques lues : `cdd` (57 tables), `mis` (72 tables).
- `ownership.csv` : colonnes `existe_dans_*` / `lignes_*` renseignées, `categorie` **ferme** (§4.1).

### Répartition des catégories
- `A` : 8
- `B` : 20
- `C` : 77
- `orpheline` : 4
- `reconstruite` : 8

### Constats saillants
- **Catégorie A (vrais doublons à fusionner) : 8 tables** — `auth_group`, `auth_group_permissions`, `auth_user`, `auth_user_groups`, `auth_user_user_permissions`, `authtoken_token`, `process_manager_administrativelevelwave`, `process_manager_wave`
- **Catégorie B (miroirs — supprimer la déclaration en double, aucune fusion) : 20** — `administrativelevels_administrativelevel`, `administrativelevels_cvd`, `administrativelevels_geographicalunit`, `assignments_assignadministrativeleveltofacilitator`, `authentication_facilitator`, `subprojects_component`, `subprojects_cycle`, `subprojects_cycle_administrative_levels`, `subprojects_financier`, `subprojects_project`, `subprojects_project_administrative_levels`, `subprojects_project_financiers`, `subprojects_subproject`, `subprojects_subproject_projects`, `subprojects_typemain`, `subprojects_villagegoal`, `subprojects_villagemeeting`, `subprojects_villageobstacle`, `subprojects_villagepriority`, `subprojects_vulnerablegroup`
- **Orphelines (déclarées dans le code, aucune table) : 4** — `authentication_governmentworker`, `authentication_user`, `authentication_user_groups`, `authentication_user_user_permissions`. À traiter à l'Étape 6 (déclarations mortes), pas de données concernées.
- `auth_user` porte les utilisateurs **des deux côtés** (cdd + mis) ; le modèle COSOMIS `authentication.User` (`authentication_user`) n'a **pas de table** → la fusion des comptes se fait sur `auth_user`, clé `username`.

✅ Aucune ligne `à_arbitrer` : Étape 2 débloquée côté qualification.

## Erreurs d'introspection
- cdd : 0 erreur(s)
- cosomis : 0 erreur(s)

## Prochaine action
1. Relire `ownership.csv` (catégories fermes).
2. Fixer, app par app, le propriétaire de schéma PG des apps homonymes (décision Étape 6 : chacun migre ses apps propres).
3. Démarrer l'Étape 2 : `merge/fusion_plan.yml`.

Rappel : `grm` / `grm_objects_call` hors périmètre (§3).
