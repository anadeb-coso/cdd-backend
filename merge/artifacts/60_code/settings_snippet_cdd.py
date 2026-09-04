# Appliqué dans src/cdd/settings.py — base PG unifiée.
# `default` ET l'alias `mis` dérivent de DATABASE_URL (plus de
# LEGACY_DATABASE_URL) ; `grm` reste externe (§3).
DATABASES = {
    "default": env.db(),                        # postgres://…/cdd_cosomis_unified
    EXTERNAL_DATABASE_NAME: env.db(),           # alias `mis` = même base
    EXTERNAL_GRM_DATABASE_NAME: env.db("LEGACY_GRM_DATABASE_URL"),
}
DATABASE_ROUTERS = ["cdd.merge_routers.CddMergeRouter"]
