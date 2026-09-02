# À intégrer dans cosomis/cosomis/settings.py (Étape 6)
import environ
env = environ.Env()
DATABASES = {
    "default": env.db("DATABASE_URL"),   # postgres://…/cdd_cosomis_unified
    "cdd": env.db("DATABASE_URL"),       # même base ; .using("cdd") reste valide
}
DATABASE_ROUTERS = ["cosomis.merge_routers.CosomisMergeRouter"]
