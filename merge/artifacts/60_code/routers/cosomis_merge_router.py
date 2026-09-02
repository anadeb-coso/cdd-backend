"""Routeur de fusion COSOMIS ↔ PostgreSQL unifié (Étape 6).

COSOMIS ne migre QUE les apps dont il possède physiquement le schéma :
subprojects, administrativelevels, assignments. Le reste (auth, contenttypes, sessions, admin, authtoken,
authentication[Facilitator = miroir CDD], usermanager, process_manager,
planning, news, storeapp, supportmaterial, reports) est migré par CDD.
"""

COSOMIS_MIGRATES = {"subprojects", "administrativelevels", "assignments", "financial", "custom_file", "kobotoolbox", "unicorn"}


class CosomisMergeRouter:
    def db_for_read(self, model, **hints):
        return None

    def db_for_write(self, model, **hints):
        return None

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db != "default":
            return False
        return app_label in COSOMIS_MIGRATES
