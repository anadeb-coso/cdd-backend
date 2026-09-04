# Appliqué dans cosomis/cosomis/settings.py.
# `default` ET l'alias `cdd` dérivent de DATABASE_URL (plus de
# LEGACY_DATABASE_URL).
DATABASES = {
    "default": env.db(),                 # postgres://…/cdd_cosomis_unified
    EXTERNAL_DATABASE_NAME: env.db(),    # alias `cdd` = même base
}
DATABASE_ROUTERS = ["cosomis.merge_routers.CosomisMergeRouter"]
