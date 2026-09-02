# À intégrer dans src/cdd/settings.py (Étape 6, base PG unifiée)
# `default` et `mis` pointent la MÊME base PostgreSQL ; `grm` reste MySQL.
import environ
env = environ.Env()
DATABASES = {
    "default": env.db("DATABASE_URL"),          # postgres://…/cdd_cosomis_unified
    "mis": env.db("DATABASE_URL"),              # même base
    "grm": env.db("LEGACY_GRM_DATABASE_URL"),   # MySQL externe, inchangé
}
DATABASE_ROUTERS = ["cdd.merge_routers.CddMergeRouter"]
