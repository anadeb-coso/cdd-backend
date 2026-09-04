# Rapport — Étape 6 : Adaptation du code (artefacts générés)

- Généré : 2026-09-04T06:07:41
- Sortie : `merge/artifacts/60_code/`

## À appliquer
1. `routers/cdd_merge_router.py` → `src/cdd/merge_routers.py` ; `routers/cosomis_merge_router.py` → `cosomis/cosomis/merge_routers.py`.
2. Fusionner les `settings_snippet_*.py` dans les `settings.py` respectifs (DATABASES + DATABASE_ROUTERS). `default` et l'alias croisé pointent la MÊME base PostgreSQL.
3. `mirror_removal.md` : passer les modèles miroirs en `Meta.managed = False` (18 côté CDD, `authentication_facilitator` côté COSOMIS).
4. `dead_models.md` : `authentication.User` / `.GovernmentWorker` = domaine GRM (§3) — laissés tels quels.
5. Sensibilité à la casse : basculer `username` / `email` d'authentification en `__iexact` (périmètre minimal, décision).
6. Ne PAS toucher `grm` / `grm_objects_call` (§3).

## Migrations Postgres
- CDD migre : auth, contenttypes, admin, sessions, authtoken, authentication, usermanager, reports, process_manager, planning, news, storeapp, supportmaterial, humanize.
- COSOMIS migre : subprojects, administrativelevels, assignments, financial, custom_file, kobotoolbox, unicorn.
- L'Étape 5 applique cet ordre via un overlay de settings (`merge/scripts/05_load_postgres.py`), sans modifier les dépôts.
