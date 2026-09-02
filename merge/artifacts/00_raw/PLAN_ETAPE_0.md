# Étape 0 — Extraction : plan

Statut : **EXÉCUTÉE le 2026-09-02 sur les bases locales** via
`merge/scripts/00_extract.py --apply`. Voir `rapport_extraction.md`,
`cutpoint.json`, et `cdd/` + `mis/` (DDL + CSV + `_information_schema.json`).

Décision de source : bases **locales** `mysql://root:@127.0.0.1/cdd` et
`.../mis` (MariaDB 10.4.32), pas la prod RDS. Comme ce sont des copies
statiques, la mécanique de delta décrite plus bas (T0 / passe 2) **reste
dormante** : une passe unique a suffi. `cutpoint.json` est produit quand même
comme point d'audit et pour l'idempotence.

Le texte ci-dessous documente la procédure telle qu'elle s'appliquerait à une
extraction depuis la prod, si le besoin réapparaît.

---


## Contraintes qui pèsent sur cette étape

| Source | Contrainte |
|---|---|
| CLAUDE.md §2 | bases sources en **lecture seule**, aucun verrou long sur la prod sans validation explicite |
| CLAUDE.md §2 | **aucune perte silencieuse** : toute ligne non reprise doit finir dans un rapport |
| Décision §9.6 (prise) | **pas de gel des écritures possible** → les deux apps écrivent pendant l'extraction |
| Décision §9.7 (prise) | traitement **tout en mémoire** |
| État machine | `mysqldump`/`mysql` **absents**. `MySQLdb` présent dans `venv_cdd` et `venv_mis` → extraction via connecteur Python |

Bases (depuis `deploy/.env`, à ne jamais committer) :

- CDD : `DATABASE_URL` → `cddapp.<...>.us-west-1.rds.amazonaws.com/ebdb`
- COSOMIS : `LEGACY_DATABASE_URL` → `cosomis.<...>.us-west-1.rds.amazonaws.com/ebdb`

## Conséquence de « pas de gel » : extraction en deux passes + delta

Un `id_map` construit sur un instantané devient faux dès qu'une ligne est créée
après l'instantané. Sans gel, on encadre le problème plutôt que de l'éliminer :

1. **T0 — marqueur de coupure.** Relever, par base :
   - `SELECT MAX(id)` de chaque table à `AUTO_INCREMENT`,
   - `SELECT NOW()` serveur + `MAX(updated_date)` / `MAX(updated_at)` là où la
     colonne existe (les modèles CDD ont `created_date`/`updated_date`, les
     modèles COSOMIS `created_at`/`updated_at` — à confirmer table par table
     depuis `schema_inventory.json`).
   Écrire le tout dans `merge/artifacts/00_raw/cutpoint.json`.

2. **Passe 1 — extraction pleine (lecture seule, sans verrou).**
   - Connexion en `REPEATABLE READ`, `SET SESSION TRANSACTION READ ONLY`,
     `innodb_lock_wait_timeout` court. **Pas** de `FLUSH TABLES WITH READ LOCK`,
     **pas** de `--single-transaction` sur un moteur non-InnoDB sans accord.
   - Extraction par `SELECT` paginé (clé primaire croissante), une table par
     fichier : `merge/artifacts/00_raw/<base>/<table>.csv` + le DDL
     (`SHOW CREATE TABLE`) dans `<base>/<table>.ddl.sql`.
   - Journaliser : version serveur (`SELECT VERSION()`), `@@character_set_*`,
     `@@collation_*`, `information_schema.TABLES` (moteur, lignes estimées,
     `TABLE_COLLATION`), `information_schema.COLUMNS`,
     `information_schema.KEY_COLUMN_USAGE` (FK réelles),
     `information_schema.STATISTICS` (index).
     → `merge/artifacts/00_raw/<base>/_information_schema.json`.
     Ce fichier alimente enfin les colonnes `existe_dans_*` / `lignes_*` de
     `ownership.csv` (Étape 1).

3. **Passe 2 — delta, juste avant de figer `id_map` (Étape 3).**
   - Re-extraire uniquement : `id > MAX(id)@T0` **ou**
     `updated_* > NOW()@T0` (marge de sécurité : recouvrir 1 h avant T0 pour
     absorber la dérive d'horloge et les transactions longues).
   - Produire `merge/artifacts/00_raw/<base>/_delta/<table>.csv` +
     `delta_report.md` (lignes ajoutées, lignes modifiées, tables sans colonne
     d'horodatage donc non couvrables par le delta → **liste d'alerte**).
   - Les tables sans PK auto ni horodatage (tables M2M surtout) sont ré-extraites
     **en entier** en passe 2 et diffées ligne à ligne.

4. **Fenêtre courte recommandée.** Même sans gel total, planifier passe 1 et
   passe 2 sur une plage de faible activité (nuit UTC) réduit la taille du delta
   et le risque de FK pendante transitoire.

## Sorties de l'étape

```
merge/artifacts/00_raw/
  cutpoint.json
  cdd/<table>.csv        cdd/<table>.ddl.sql        cdd/_information_schema.json
  cosomis/<table>.csv    cosomis/<table>.ddl.sql    cosomis/_information_schema.json
  cdd/_delta/*.csv       cosomis/_delta/*.csv       delta_report.md
  rapport_extraction.md
```

Les CSV volumineux ne sont pas versionnés : versionner leur SHA-256 et la
commande de génération (CLAUDE.md §7).

## Ce qu'il faut pour lancer

1. **Feu vert explicite** pour lire les deux bases RDS de production (§2).
2. Confirmer les colonnes d'horodatage fiables par table (sinon le delta est
   aveugle sur ces tables — à traiter comme risque documenté).
3. Confirmer la plage horaire d'extraction.
4. Script `merge/scripts/00_extract.py` (à écrire) : `--dry-run` par défaut,
   `--apply` pour extraire réellement, `--pass=1|2`.
