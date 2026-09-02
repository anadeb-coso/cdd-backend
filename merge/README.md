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
| 6 — Adaptation code | **artefacts générés** ; non appliqués aux dépôts | `artifacts/60_code/` — routeurs, snippets settings, `mirror_removal.md`, `dead_models.md` |
| 7 — Remap CouchDB | **dry-run fait** ; `--apply` en attente de feu vert + levée d'ambiguïté | `artifacts/70_checks/rapport_remap_couchdb.md` |
| Contrôles §6 | **1-5 automatisés : OK** ; 6-8 à faire | `artifacts/70_checks/report.md` |

### Reste à faire avant bascule

1. **Décision §6.3** — 59 FK `process_manager_administrativelevelwave.project_id`
   orphelines (COSOMIS `project_id` ∈ {1,3} sans table `process_manager_project`
   côté `mis`). Choisir : mettre `project_id` à NULL / remapper vers un projet
   CDD / exclure les 59 lignes COSOMIS. Cf. `merge/conflicts.csv` type
   `rapprochement`.
2. **Appliquer l'Étape 6** aux dépôts (`src/` et `cosomis/`) : routeurs,
   settings PG, `Meta.managed=False` sur les 19 miroirs CDD +
   `authentication_facilitator` COSOMIS, retrait des 4 modèles orphelins,
   `__iexact` sur `auth_user.username/email`.
3. **Contrôles §6.6-6.8** : `manage.py check` + `makemigrations --check` sur PG ;
   exports `fc_situation` / `views_docx` / tableau de bord financier avant
   (MySQL) et après (PG) ; jeu de tests casse.
4. **Étape 7 `--apply`** après confirmation que les bases `facilitator_*`
   scannées sont d'origine COSOMIS (sinon les `user_id` CDD seraient corrompus).
5. `dump_mysql_unifie.sql` : livrable d'archive ; versionner son empreinte
   SHA-256 (§7) — non chargé dans MySQL.
6. **Note d'env** : `psycopg2-binary` a été installé dans `venv_mis` pour
   l'Étape 5 (migrate PG). `pip uninstall psycopg2-binary` si non souhaité.

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
