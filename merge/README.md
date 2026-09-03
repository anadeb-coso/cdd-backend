# Fusion `cdd` + `cosomis` → PostgreSQL

Chantier piloté par [`../src/CLAUDE.md`](../src/CLAUDE.md). Branche : `merge/cdd-cosomis`.
Opération unique, non récurrente. Lire `CLAUDE.md` en entier avant toute action.

## Décisions prises

| # | Question | Réponse |
|---|---|---|
| 9.1 | Base de code unique ou deux apps ? | **Deux apps Django distinctes**, une seule base PostgreSQL. Lève la contradiction ligne 352 ↔ §9.1 en faveur de la ligne 352. |
| 9.6 | Gel des écritures pendant l'extraction ? | **Pas de gel possible** en théorie — mais l'extraction se fait sur des **copies locales statiques** (voir ci-dessous), donc le delta de `PLAN_ETAPE_0.md` devient dormant : une passe unique suffit. |
| 9.7 | Volumétrie / mode de traitement ? | **Tout en mémoire.** |
| 9.2 | Miroirs dont COSOMIS possède le schéma : déplacer vers l'app CDD ? | **Non.** Le modèle reste chez son propriétaire ; on ne supprime que la déclaration miroir en double. |
| 9.3 | Clé naturelle de `Subproject` ? | Le couple **(`number`, `joint_subproject_number`)**. `number` seul n'est pas unique. ⚠ ne s'applique que si `Subproject` est confirmé catégorie A ; l'inventaire le donne miroir (schéma COSOMIS). |
| 9.4 | `Facilitator` à deux e-mails ? | **Non**, l'e-mail est le même partout → clé naturelle = `email`. |
| 9.5 | Compte en double, hachages différents ? | **Le hachage CDD gagne** (cohérent avec « CDD survit »). |
| 4.5 | Clés naturelles des autres modèles de catégorie A | **Validées en bloc** : `Project`=`name`, `Cycle`=(`project`,`order`), `CVD`=`unique_code`, `GeographicalUnit`=`unique_code` repli (`canton`,`attributed_number_in_canton`), `User`=`username` (contrôle croisé `email`). `AdministrativeLevel` : schéma **uniquement COSOMIS**, CDD n'a que le miroir → catégorie B, pas de rapprochement. L'Étape 2 échoue si l'unicité réelle n'est pas vérifiée. |
| 4.3 | Champs homonymes de types incompatibles | **« Plus permissif » automatique** + journal `field_conflicts` dans `fusion_plan.yml`, relu avant l'Étape 4. |
| 5.x | Sensibilité à la casse MySQL→PG | **Périmètre minimal** : seuls `username` / `email` d'authentification passent en insensible à la casse. Le reste adopte la casse Postgres. |
| 6.x | Ponts `mis_objects_call` / `.using('mis')` après fusion | **Alias conservés**, `default` / `mis` / `cdd` pointent tous vers la même base PostgreSQL. Diff minimal, code quasi inchangé. |
| 6.x | Propriété du schéma PG (qui applique `migrate`) | **Chacun migre ses apps propres, jamais les apps communes.** Routeurs des deux côtés ; les apps homonymes (`subprojects`, `administrativelevels`, `authentication`, `assignments`, `process_manager`…) sont migrées par **un seul** des deux projets — propriétaire à fixer app par app via `ownership.csv` complet. |
| 0 | Source de l'extraction | **Bases locales**, pas la prod RDS : `mysql://root:@127.0.0.1/cdd` et `mysql://root:@127.0.0.1/mis` (MariaDB 10.4.32). Extraction **immédiate**, sans fenêtre horaire. |
| 7 | CouchDB | **Instance locale** : `http://127.0.0.1:5984` (root/root). Remap `sql_id` / `administrative_level_id` en dry-run par défaut. |

### Encore ouvert

- **§6.7** — produire les exports lourds « avant » (fc_situation, views_docx, tableau de bord financier) sur la base `cdd` locale : à confirmer au moment des contrôles d'acceptation.

## Environnements

| Projet | Racine | venv | Django |
|---|---|---|---|
| CDD | `../src` | `D:\COSO\PROJECTS\CDD\backend\venv_cdd` | 4.0.4 |
| COSOMIS | `D:\COSO\PROJECTS\MIS\cosomis\cosomis` | `D:\COSO\PROJECTS\MIS\venv_mis` | 4.2.30 |

Bases **locales** (MariaDB 10.4.32) : `cdd` (57 tables), `mis` (72 tables).
`mysqldump` / `mysql` absents ; `MySQLdb` présent dans les deux venvs → extraction via connecteur Python.

## Avancement

| Étape | État | Sortie |
|---|---|---|
| 0 — Extraction | **faite** (bases locales, `--apply`) | `artifacts/00_raw/` — DDL + CSV + `_information_schema.json`, `cutpoint.json` |
| 1 — Inventaire | **faite** (catégories §4.1 fermes) | `artifacts/10_inventory/` — `ownership.csv`, `collisions.md`, `conflicts.csv` |
| 2 — Plan de fusion | **faite** | `merge/fusion_plan.yml`, `artifacts/20_plan/rapport_plan.md` |
| 3 — id_map | **faite** | `merge/id_map.csv` (255 l.), `merge/conflicts.csv` (185 l.), `artifacts/30_idmap/` |
| 4 — Jeu unifié | **faite** | `artifacts/40_unified/` — 105 CSV + `dump_mysql_unifie.sql` (non versionnés), `rapport_unifie.md` |
| 5 — PostgreSQL | **faite** — 105/105 tables, 199 599 lignes | base `cdd_cosomis_unified` (PG 18) ; `05_load_postgres.py`, `artifacts/50_postgres/rapport_postgres.md` |
| 6 — Adaptation code | **appliquée aux 2 dépôts** (branche `merge/cdd-cosomis` de chaque) | `src/cdd/merge_routers.py` ; `cosomis/cosomis/merge_routers.py` + settings + `Facilitator.managed=False` + `db_column` PG63 + migration 0072 |
| `.env` | **PostgreSQL intégré** dans `src/cdd/.env` et `cosomis/cosomis/.env` (`DATABASE_URL` + `LEGACY_DATABASE_URL` → `cdd_cosomis_unified`) ; anciens MySQL en commentaire. `*.env` non versionné. |
| 7 — Remap CouchDB | **dry-run fait** ; `--apply` refusé (décision « aucune écriture CouchDB ») | `artifacts/70_checks/rapport_remap_couchdb.md` |
| Contrôles §6 + tests | **§6.1-6.8 : ✅** ; 25 tests COSOMIS `financial` + `subprojects` : ✅ sur PG | `artifacts/70_checks/report.md` |

### Étape 6 — appliquée

**CDD** (`src/`, branche `merge/cdd-cosomis`) :
- `src/cdd/merge_routers.py` + `DATABASE_ROUTERS` dans `settings.py`.
- Aucun changement de modèle (miroirs déjà cohérents ; `makemigrations --check` propre MySQL et PG).
- `__iexact` sur les lookups de login (`authentication/api/auth/login.py`, `authentication/serializers.py`, `usermanager/authentication.py`).

**COSOMIS** (`D:\COSO\PROJECTS\MIS\cosomis`, branche `merge/cdd-cosomis`) :
- `cosomis/cosomis/merge_routers.py` + `DATABASE_ROUTERS`.
- `MIGRATION_MODULES` retire du graphe les apps homonymes possédées par CDD
  (sinon `InconsistentMigrationHistory` sur une base PG partagée).
- `authentication.Facilitator` → `Meta.managed = False` + `db_table` explicite.
- `authentication.User` / `.GovernmentWorker` : **domaine GRM (§3), non touchés**.
- `__iexact` sur `usermanager/api/auth/login.py`.
- Vérifié sur PG (code réel) : `check` 0 issue, `makemigrations --check` propre.

### Concept `Project` (§0/§4.5) — traité

`subprojects_project` (COSOMIS) et `process_manager_project` (CDD) = même
concept, noms de table différents → catégorie A **inter-tables**. Apparié par
`name` (1→4, 2→5, 3→6), survivant `process_manager_project` ;
`process_manager_administrativelevelwave.project_id` des lignes COSOMIS remappé
→ 35 appariées / 24 nouvelles, **0 FK orpheline** (§6.3). `Cycle` : clés
définies, aucune FK croisée → pas de remap. Voir `fusion_plan.yml` →
`cross_concept`.

### Contrôles d'acceptation

| § | Contrôle | Résultat |
|---|---|---|
| 6.1 | Comptage par catégorie | ✅ |
| 6.2 | Identité des ID (unifié ↔ PG) | ✅ |
| 6.3 | Intégrité référentielle (187 FK) | ✅ 0 orpheline |
| 6.4 | Séquences `last_value ≥ MAX(id)` | ✅ (103) |
| 6.5 | Échantillon 20 lignes / table homonyme | ✅ 0 divergence |
| 6.6 | `check` + `makemigrations --check` (CDD + COSOMIS, PG, code réel, config depuis `.env`) | ✅ |
| 6.7 | `fc_situation` avant (MySQL) vs après (PG, config `.env`) | ✅ 7 feuilles octet-identiques |
| 6.7b | COUNT + Σ de **toutes** les colonnes de mesure (matching tronqué 63 c.), **97 tables B+C**, source ↔ PG (dont `financial_*` KPI) | ✅ identiques |
| 6.8 | Login `__iexact` (CDD + COSOMIS) ; 0 username en collision | ✅ appliqué |
| Tests | 25 tests unitaires COSOMIS `financial` + `subprojects` sur base PG | ✅ (via settings de test `MIGRATION_MODULES=None` → syncdb) |

**Bug corrigé au passage** : `subprojects_subproject.amount_of_the_care_and_maintenance_fund_expected_to_be_mobilized`
(64 c.) dépasse la limite d'identifiant PostgreSQL (63) → l'Étape 5 chargeait
la table **sans cette colonne** (135 valeurs, Σ 40 723 250, silencieusement
perdues). Corrigé : `db_column` explicite côté modèle COSOMIS + migration 0072
+ mapping de troncature dans le chargeur + §6.7b détecte désormais toute
colonne absente côté PG.

### Idempotence

Pipeline complet rejoué de zéro (00→06→05→checks) : **résultat identique**
(105/105 tables, A=8, contrôles §6.1-6.8 verts). `_introspect_project.py` force
`MIGRATION_MODULES = {}` pour que la qualification §4.1 ne dépende pas du
`MIGRATION_MODULES` ajouté au settings COSOMIS par l'Étape 6.

`migrate --fake` des apps possédées par COSOMIS (`administrativelevels`,
`subprojects` — dont la migration 0072 —, `assignments`, `financial`,
`custom_file`) exécuté **localement** sur `cdd_cosomis_unified` →
`django_migrations` aligné, `makemigrations --check` propre.

### Reste avant bascule production (rien à faire en ligne / aucun déploiement AWS ici)

1. **Compléter §6.7** : comparaison avant/après du rendu HTTP de l'export DOCX
   sous-projets et du tableau de bord financier (dépend de S3/Kobo réseau ;
   l'assiette de données est déjà vérifiée identique par §6.7b).
2. **Étape 7** : reste en dry-run (décision « aucune écriture CouchDB »).
   102 628 `user_id` candidats ; `--apply` exigerait de confirmer l'origine
   COSOMIS des bases `facilitator_*`.
3. **Déploiement** (hors périmètre de ces travaux) : pointer `DATABASE_URL` +
   `LEGACY_DATABASE_URL` des deux `.env` sur la base PostgreSQL unifiée
   (routeurs et settings en place) ; sur une base fraîche, `migrate --fake` les
   apps COSOMIS comme fait ici en local.
4. **Note d'env** : `psycopg2-binary` installé dans `venv_mis` pour l'Étape 5
   (`pip uninstall psycopg2-binary` si non souhaité).
5. **Branches** : `merge/cdd-cosomis` dans les deux dépôts (`cdd-backend` et
   `MIS/cosomis`), non poussées.

### Étape 1 — résultats fermes

Extraction : `cdd` 57 tables / ~154 k lignes, `mis` 72 tables. Classification §4.1
croisant `information_schema` + comptages + migrations + accès code :

| Catégorie | N | Traitement |
|---|---|---|
| **A — vrais doublons** | 8 | `auth_group`, `auth_user`, `auth_user_groups` (+ `process_manager_administrativelevelwave`, `process_manager_wave`) + 3 tables vides des 2 côtés. **Seules tables à réconcilier via `id_map`.** |
| **B — miroirs** | 20 | tout `subprojects_*`, `administrativelevels_*`, `assignments_assign…`, `authentication_facilitator`. Table dans **une seule** base → transport tel quel, on supprime juste la déclaration en double dans l'autre projet. Aucun `id_map`. |
| **C — propre à un projet** | 77 | transport tel quel |
| reconstruite (§4.6) | 8 | Django régénère |
| **orpheline** | 4 | `authentication_user`, `authentication_user_groups`, `authentication_user_user_permissions`, `authentication_governmentworker` — déclarées côté COSOMIS, **aucune table nulle part**. Déclarations mortes, à nettoyer à l'Étape 6. Aucune donnée. |

**Fait majeur** : le `cdd` local n'a **aucune** table `subprojects_*` /
`administrativelevels_*` — CDD lit tout ça dans `mis`. Et les utilisateurs
COSOMIS sont dans `auth_user` (79 lignes), **pas** dans `authentication_user`
(sans table). → fusion des comptes sur `auth_user`, clé `username`.

Autres relevés dans `collisions.md` : `Facilitator.code` CharField 100 vs 6
(§4.3 → plus permissif) ; FK molles (`couch_id`, `no_sql_db_id`,
`administrative_level_id`…) ; champs JSON listes d'ID (`Facilitator.*_administrative_ids`,
`planning.Activity.administrative_level_ids`, `reports.VillageCommittee.villages_ids`,
`news.News.administrative_levels`/`projects`) ; couplage CDD→COSOMIS massif
(229 `mis_objects_call`), COSOMIS→CDD léger. `grm` hors périmètre (§3).

### Décisions Étape 2 / 6 (prises)

- **`Wave`** : clé naturelle = `number`.
- **`AdministrativeLevelWave`** : clé naturelle = (`project`, `wave__number`,
  `administrative_level_id`).
- **Comptes utilisateurs** : `auth_user` fait foi des deux côtés ; fusion sur
  `username`. `authentication.User` / `authentication_user` (COSOMIS) =
  déclaration morte à nettoyer à l'Étape 6.
- **Schéma PG des apps homonymes** : COSOMIS migre `subprojects`,
  `administrativelevels`, `assignments` (il possède déjà ces tables) ; CDD
  migre `process_manager`, `planning`, `news`, `storeapp`, `supportmaterial`,
  `authentication` (facilitator), `usermanager`, `reports`. Routeurs
  `allow_migrate` des deux côtés.

### Décisions Étape 3 / 7 / contrôles (prises)

- **Conflit de valeurs (Étape 3)** : règle CLAUDE.md telle quelle — CDD gagne,
  COSOMIS comble les NULL, divergences non nulles journalisées dans
  `conflicts.csv`. **Exception** : COSOMIS gagne sur une liste de champs à
  arrêter au début de l'Étape 3. ⚠ en pratique les seules tables de
  catégorie A sont `auth_*` et `process_manager_wave` /
  `_administrativelevelwave` — aucun champ financier ni statut de sous-projet
  n'y figure (ceux-ci sont en B/C, transportés tels quels). Si aucune
  exception n'est nommée sur ces tables A, la règle de base s'applique seule.
- **Remap CouchDB (Étape 7)** : **dry-run uniquement** pour l'instant ;
  `--apply` seulement sur feu vert explicite après relecture du rapport.
- **Exports de référence « avant » (§6.7)** : à produire **maintenant** sur les
  bases locales `cdd` + `mis` (`fc_situation`, `reports/subprojects/views_docx`,
  tableau de bord financier) → `artifacts/70_checks/avant/`.

## Scripts

| Script | Rôle |
|---|---|
| `scripts/_introspect_project.py` | introspection ORM d'un projet, à lancer dans son venv |
| `scripts/00_extract.py` | Étape 0 — extraction lecture seule `cdd` + `mis` (`--dry-run` défaut, `--apply`) |
| `scripts/01_inventory.py` | Étape 1 — inventaire + qualification §4.1 → `artifacts/10_inventory/` |
| `scripts/02_build_plan.py` | Étape 2 — `merge/fusion_plan.yml` (+ contrôle d'unicité des clés naturelles) |
| `scripts/03_build_id_map.py` | Étape 3 — `merge/id_map.csv` + `merge/conflicts.csv` |
| `scripts/04_build_unified.py` | Étape 4 — `artifacts/40_unified/*.csv` + `dump_mysql_unifie.sql` |
| `scripts/05_load_postgres.py` | Étape 5 — provision + migrate + COPY + setval sur PostgreSQL |
| `scripts/06_codemod.py` | Étape 6 — génère `artifacts/60_code/` (routeurs, settings, patches) |
| `scripts/07_remap_couchdb.py` | Étape 7 — remap CouchDB (`--dry-run` défaut) |
| `scripts/checks/run_checks.py` | Contrôles d'acceptation §6.1-6.5 → `artifacts/70_checks/report.md` |

Rejouer tout le pipeline (idempotent) :
```
venv_mis  … 00_extract.py --apply
venv_cdd  … 01_inventory.py
venv_cdd  … 02_build_plan.py
venv_cdd  … 03_build_id_map.py
venv_cdd  … 04_build_unified.py
venv_cdd  … 06_codemod.py
venv_cdd  … 05_load_postgres.py
venv_cdd  … 07_remap_couchdb.py
venv_cdd  … checks/run_checks.py
```
(`venv_cdd` = `D:\COSO\PROJECTS\CDD\backend\venv_cdd\Scripts\python.exe`,
`venv_mis` = `D:\COSO\PROJECTS\MIS\venv_mis\Scripts\python.exe` ; forcer
`PYTHONUTF8=1` sous PowerShell.)
