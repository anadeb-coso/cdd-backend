"""
Étape 6 — Adaptation du code (générateur d'artefacts).

Les deux applications restent distinctes (décision §9.1) et pointent vers la
même base PostgreSQL. Cette étape NE modifie PAS les dépôts en place : elle
génère sous `merge/artifacts/60_code/` les éléments à intégrer, revus à la main.

Produit :
  - routers/cdd_merge_router.py       allow_migrate : CDD ne migre pas les apps
                                      possédées par COSOMIS (subprojects,
                                      administrativelevels, assignments)
  - routers/cosomis_merge_router.py   COSOMIS ne migre QUE ses apps propres
  - settings_snippet_cdd.py           DATABASES (default+mis+grm) + ROUTERS
  - settings_snippet_cosomis.py       idem côté COSOMIS
  - mirror_removal.md                 déclarations miroir à neutraliser (managed=False)
  - dead_models.md                    modèles orphelins à retirer
  - rapport_codemod.md

Entrées : merge/fusion_plan.yml, merge/artifacts/10_inventory/schema_inventory.json

Usage : python merge/scripts/06_codemod.py
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
INV = REPO / "merge" / "artifacts" / "10_inventory"
OUT = REPO / "merge" / "artifacts" / "60_code"
PLAN = REPO / "merge" / "fusion_plan.yml"

# Décision Étape 6 : propriétaire de schéma PG par app homonyme.
COSOMIS_OWNED_APPS = ["subprojects", "administrativelevels", "assignments"]
# apps propres à COSOMIS (catégorie C côté mis) — COSOMIS les migre aussi
COSOMIS_ONLY_APPS = ["financial", "custom_file", "kobotoolbox", "unicorn"]
# apps homonymes contenant AUSSI des tables propres à COSOMIS (mis_only) :
# process_manager_periodwave*, usermanager_usertoken. Au chargement PG (Étape 5,
# syncdb), COSOMIS crée ces tables manquantes ; les tables homonymes déjà
# créées par CDD sont ignorées. Dans le système déployé, ces tables restent
# gérées par un routeur au niveau modèle, pas au niveau app.
COSOMIS_EXTRA_SYNCDB_APPS = ["process_manager", "usermanager"]
# tout le reste (dont auth, contenttypes, sessions, admin, authtoken,
# authentication, usermanager, reports, process_manager, planning, news,
# storeapp, supportmaterial) est migré par CDD.

CDD_ROUTER = '''\
"""Routeur de fusion CDD ↔ PostgreSQL unifié (Étape 6).

- Les apps possédées par COSOMIS ne sont jamais migrées par CDD.
- Toutes les lectures/écritures vont sur `default` (les alias `mis`/`cdd`
  pointent la même base PostgreSQL ; `.using('mis')` reste valide).
- `grm` reste une base MySQL externe distincte (hors périmètre §3).
"""

COSOMIS_OWNED = {__COSOMIS_OWNED__}
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
'''

COSOMIS_ROUTER = '''\
"""Routeur de fusion COSOMIS ↔ PostgreSQL unifié (Étape 6).

COSOMIS ne migre QUE les apps dont il possède physiquement le schéma :
{owned}. Le reste (auth, contenttypes, sessions, admin, authtoken,
authentication[Facilitator = miroir CDD], usermanager, process_manager,
planning, news, storeapp, supportmaterial, reports) est migré par CDD.
"""

COSOMIS_MIGRATES = {__MIGRATES__}


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
'''


def main() -> None:
    (OUT / "routers").mkdir(parents=True, exist_ok=True)
    plan = yaml.safe_load(PLAN.read_text("utf-8"))
    sinv = json.loads((INV / "schema_inventory.json").read_text("utf-8"))

    # --- routers ---
    (OUT / "routers" / "__init__.py").write_text("", "utf-8")
    (OUT / "routers" / "cdd_merge_router.py").write_text(
        CDD_ROUTER.replace("__COSOMIS_OWNED__",
                           ", ".join(f'"{a}"' for a in COSOMIS_OWNED_APPS)),
        "utf-8")
    migrates = COSOMIS_OWNED_APPS + COSOMIS_ONLY_APPS
    (OUT / "routers" / "cosomis_merge_router.py").write_text(
        COSOMIS_ROUTER.replace("__MIGRATES__",
                               ", ".join(f'"{a}"' for a in migrates))
        .replace("{owned}", ", ".join(COSOMIS_OWNED_APPS)),
        "utf-8")

    # --- settings snippets ---
    (OUT / "settings_snippet_cdd.py").write_text(
        '# À intégrer dans src/cdd/settings.py (Étape 6, base PG unifiée)\n'
        '# `default` et `mis` pointent la MÊME base PostgreSQL ; `grm` reste MySQL.\n'
        'import environ\n'
        'env = environ.Env()\n'
        'DATABASES = {\n'
        '    "default": env.db("DATABASE_URL"),          # postgres://…/cdd_cosomis_unified\n'
        '    "mis": env.db("DATABASE_URL"),              # même base\n'
        '    "grm": env.db("LEGACY_GRM_DATABASE_URL"),   # MySQL externe, inchangé\n'
        '}\n'
        'DATABASE_ROUTERS = ["cdd.merge_routers.CddMergeRouter"]\n',
        "utf-8")
    (OUT / "settings_snippet_cosomis.py").write_text(
        '# À intégrer dans cosomis/cosomis/settings.py (Étape 6)\n'
        'import environ\n'
        'env = environ.Env()\n'
        'DATABASES = {\n'
        '    "default": env.db("DATABASE_URL"),   # postgres://…/cdd_cosomis_unified\n'
        '    "cdd": env.db("DATABASE_URL"),       # même base ; .using("cdd") reste valide\n'
        '}\n'
        'DATABASE_ROUTERS = ["cosomis.merge_routers.CosomisMergeRouter"]\n',
        "utf-8")

    # --- mirror removal / managed=False ---
    b_tables = {t: e for t, e in plan["tables"].items()
                if e.get("strategy") == "mirror"}
    lines = ["# Déclarations miroir à neutraliser (Étape 6)\n",
             "Décision §9.2 : le modèle reste chez son propriétaire ; le projet "
             "non-propriétaire garde une déclaration de lecture mais **`managed "
             "= False`** et ne migre jamais la table (routeur ci-dessus).\n"]
    by_proj = defaultdict(list)
    for t, e in sorted(b_tables.items()):
        ca = e["code_action"]
        by_proj[ca["project"]].append((t, e["schema_owner"],
                                       ca["remove_mirror_declaration"],
                                       ca["modules"]))
    for proj, items in by_proj.items():
        lines.append(f"\n## Projet `{proj}` — {len(items)} tables\n")
        for t, owner, models, mods in items:
            lines.append(f"- `{t}` (propriétaire **{owner}**) : "
                         f"{', '.join(models)}  — modules : {', '.join(mods)}")
            lines.append(f"  - action : `class Meta: managed = False` ; "
                         f"ne pas supprimer la classe (le code {proj} l'utilise "
                         f"en lecture via l'ORM / `.using()`).")
    (OUT / "mirror_removal.md").write_text("\n".join(lines) + "\n", "utf-8")

    # --- dead models ---
    dead = ["# Modèles orphelins — aucune table physique (Étape 6)\n",
            "Déclarés dans le code COSOMIS, aucune table nulle part.\n",
            "⚠ Vérifié : `authentication.User` (`class User(AbstractUser)`, "
            "importé `as GrmUser`) et `authentication.GovernmentWorker` "
            "relèvent du **domaine GRM** (`grm_client`, `grm_objects_call`) — "
            "**hors périmètre §3, NE PAS y toucher**. Leur table vit dans la "
            "base `grm`, jamais fusionnée. Aucune action Étape 6.\n"]
    for t, e in plan["tables"].items():
        if e.get("category", "").startswith("orpheline"):
            mods = sorted({m["model_module"]
                           for m in sinv["projects"]["cosomis"]["models"]
                           if m["db_table"] == t})
            dead.append(f"- `{t}` — modules : {', '.join(mods) or '?'} — GRM, "
                        "laissé tel quel")
    (OUT / "dead_models.md").write_text("\n".join(dead) + "\n", "utf-8")

    # --- rapport ---
    rep = ["# Rapport — Étape 6 : Adaptation du code (artefacts générés)\n",
           f"- Généré : {datetime.now().isoformat(timespec='seconds')}",
           f"- Sortie : `merge/artifacts/60_code/`",
           "",
           "## À appliquer",
           "1. `routers/cdd_merge_router.py` → `src/cdd/merge_routers.py` ; "
           "`routers/cosomis_merge_router.py` → `cosomis/cosomis/merge_routers.py`.",
           "2. Fusionner les `settings_snippet_*.py` dans les `settings.py` "
           "respectifs (DATABASES + DATABASE_ROUTERS). `default` et l'alias "
           "croisé pointent la MÊME base PostgreSQL.",
           "3. `mirror_removal.md` : passer les modèles miroirs en "
           "`Meta.managed = False` (18 côté CDD, `authentication_facilitator` "
           "côté COSOMIS).",
           "4. `dead_models.md` : `authentication.User` / `.GovernmentWorker` "
           "= domaine GRM (§3) — laissés tels quels.",
           "5. Sensibilité à la casse : basculer `username` / `email` "
           "d'authentification en `__iexact` (périmètre minimal, décision).",
           "6. Ne PAS toucher `grm` / `grm_objects_call` (§3).",
           "",
           "## Migrations Postgres",
           "- CDD migre : auth, contenttypes, admin, sessions, authtoken, "
           "authentication, usermanager, reports, process_manager, planning, "
           "news, storeapp, supportmaterial, humanize.",
           f"- COSOMIS migre : {', '.join(COSOMIS_OWNED_APPS + COSOMIS_ONLY_APPS)}.",
           "- L'Étape 5 applique cet ordre via un overlay de settings "
           "(`merge/scripts/05_load_postgres.py`), sans modifier les dépôts.",
           ]
    (OUT / "rapport_codemod.md").write_text("\n".join(rep) + "\n", "utf-8")
    print("Artefacts Étape 6 →", OUT)
    for p in sorted(OUT.rglob("*")):
        if p.is_file():
            print("  ", p.relative_to(OUT))


if __name__ == "__main__":
    main()
