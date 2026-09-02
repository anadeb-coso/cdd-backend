# Rapport — Étape 4 : Jeu de données unifié

- Généré : 2026-09-02T17:49:16
- Tables écrites : 105 (`merge/artifacts/40_unified/`)
- Dump archive : `dump_mysql_unifie.sql` (105416 Kio)
- ⚠ 3 table(s) dans un cycle de FK (administrativelevels_administrativelevel, administrativelevels_cvd, administrativelevels_geographicalunit) — arêtes retour cassées pour l'ordre ([('administrativelevels_cvd', 'administrativelevels_administrativelevel'), ('administrativelevels_geographicalunit', 'administrativelevels_administrativelevel')]). Le dump SQL est encadré par SET FOREIGN_KEY_CHECKS=0 ; l'Étape 5 charge avec contraintes différées.

## Catégorie A
- `auth_group` : CDD 31 + COSOMIS fusionnées 31 + nouvelles 0 → **31**
- `auth_group_permissions` : CDD 0 + COSOMIS fusionnées 0 + nouvelles 0 → **0**
- `auth_user` : CDD 82 + COSOMIS fusionnées 78 + nouvelles 1 → **83**
- `auth_user_groups` : CDD 89 + COSOMIS fusionnées 0 + nouvelles 2 → **91**
- `auth_user_user_permissions` : CDD 0 + COSOMIS fusionnées 0 + nouvelles 0 → **0**
- `authtoken_token` : CDD 0 + COSOMIS fusionnées 0 + nouvelles 0 → **0**
- `process_manager_administrativelevelwave` : CDD 35 + COSOMIS fusionnées 0 + nouvelles 59 → **94**
- `process_manager_wave` : CDD 5 + COSOMIS fusionnées 5 + nouvelles 1 → **6**

## Contrôle de comptage (§6.1)
- `auth_group` : cdd+mis-appariées = 31 ; unifiée = 31 → OK
- `auth_group_permissions` : cdd+mis-appariées = 0 ; unifiée = 0 → OK
- `auth_user` : cdd+mis-appariées = 83 ; unifiée = 83 → OK
- `auth_user_groups` : cdd+mis-appariées = 91 ; unifiée = 91 → OK
- `auth_user_user_permissions` : cdd+mis-appariées = 0 ; unifiée = 0 → OK
- `authtoken_token` : cdd+mis-appariées = 0 ; unifiée = 0 → OK
- `process_manager_administrativelevelwave` : cdd+mis-appariées = 94 ; unifiée = 94 → OK
- `process_manager_wave` : cdd+mis-appariées = 6 ; unifiée = 6 → OK

## Suite
Étape 5 : `merge/scripts/05_load_postgres.py` (charge les CSV de `40_unified/` dans PostgreSQL via COPY, colonne `id` explicite).
