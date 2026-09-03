"""Routeur de fusion CDD ↔ PostgreSQL unifié (Étape 6).

- Les apps possédées par COSOMIS ne sont jamais migrées par CDD.
- Toutes les lectures/écritures vont sur `default` (les alias `mis`/`cdd`
  pointent la même base PostgreSQL ; `.using('mis')` reste valide).
- `grm` reste une base MySQL externe distincte (hors périmètre §3).
"""

COSOMIS_OWNED = {"subprojects", "administrativelevels", "assignments"}
GRM_APPS = {"grm", "grm_client"}


class CddMergeRouter:
    def db_for_read(self, model, **hints):
        return None  # défaut

    def db_for_write(self, model, **hints):
        return None

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == "grm":
            return app_label in GRM_APPS
        if db != "default":
            return False
        if app_label in COSOMIS_OWNED:
            return False
        return True
