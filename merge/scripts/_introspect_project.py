"""
Introspection d'un projet Django — à exécuter DANS le venv du projet.

Sortie : un JSON sur stdout décrivant apps, modèles, champs, tables, migrations.
Aucune connexion à la base : seul `django.setup()` + l'API `_meta` est utilisé.

Usage :
    python _introspect_project.py <racine_projet> <module.settings> <label_projet>

Les variables d'environnement de base (SECRET_KEY, *_DATABASE_URL) sont
renseignées avec des valeurs factices : l'introspection ORM ne se connecte pas.
"""
import os
import sys
import json
import traceback


def main():
    proj_root, settings_mod, project_label = sys.argv[1], sys.argv[2], sys.argv[3]

    os.environ.setdefault("SECRET_KEY", "introspection-only")
    for key in ("DATABASE_URL", "LEGACY_DATABASE_URL", "LEGACY_GRM_DATABASE_URL",
                "GRM_DATABASE_URL"):
        os.environ.setdefault(key, "sqlite:////tmp/introspection-none.db")

    sys.path.insert(0, proj_root)
    os.environ["DJANGO_SETTINGS_MODULE"] = settings_mod

    import django
    from django.apps import apps
    from django.conf import settings

    django.setup()

    # L'inventaire doit voir TOUTES les migrations sur disque, indépendamment
    # d'un éventuel MIGRATION_MODULES ajouté au settings pour le déploiement
    # unifié (Étape 6) — sinon la qualification §4.1 devient non idempotente.
    settings.MIGRATION_MODULES = {}

    out = {
        "project": project_label,
        "project_root": proj_root,
        "settings_module": settings_mod,
        "django_version": django.get_version(),
        "databases": {
            alias: {
                "ENGINE": cfg.get("ENGINE"),
                "NAME": cfg.get("NAME"),
                "HOST": cfg.get("HOST"),
            }
            for alias, cfg in settings.DATABASES.items()
        },
        "database_routers": [repr(r) for r in getattr(settings, "DATABASE_ROUTERS", [])],
        "installed_apps": list(settings.INSTALLED_APPS),
        "models": [],
        "migrations_create": {},
        "errors": [],
    }

    # ---- Modèles ---------------------------------------------------------
    for model in apps.get_models(include_auto_created=True):
        meta = model._meta
        try:
            rec = {
                "app_label": meta.app_label,
                "object_name": meta.object_name,
                "model_key": f"{meta.app_label}.{meta.object_name}",
                "db_table": meta.db_table,
                "managed": bool(meta.managed),
                "proxy": bool(meta.proxy),
                "abstract": bool(meta.abstract),
                "auto_created": bool(meta.auto_created),
                "pk": meta.pk.name if meta.pk is not None else None,
                "pk_column": meta.pk.column if meta.pk is not None else None,
                "unique_together": [list(t) for t in meta.unique_together],
                "app_module": getattr(
                    getattr(meta, "app_config", None), "name", None
                ),
                "model_module": model.__module__,
                "fields": [],
                "m2m": [],
            }
            for f in meta.get_fields():
                if f.many_to_many and not f.auto_created:
                    through = getattr(f.remote_field, "through", None)
                    rec["m2m"].append({
                        "name": f.name,
                        "related_model": (
                            f.related_model._meta.label
                            if f.related_model is not None else None
                        ),
                        "through": (
                            through._meta.db_table if through is not None else None
                        ),
                        "through_auto": (
                            bool(through._meta.auto_created) if through is not None
                            else None
                        ),
                    })
                    continue
                if not hasattr(f, "get_internal_type"):
                    continue  # reverse relation objects
                if f.auto_created and not f.concrete:
                    continue
                item = {
                    "name": f.name,
                    "attname": getattr(f, "attname", f.name),
                    "column": getattr(f, "column", None),
                    "type": f.get_internal_type(),
                    "null": bool(getattr(f, "null", False)),
                    "blank": bool(getattr(f, "blank", False)),
                    "unique": bool(getattr(f, "unique", False)),
                    "primary_key": bool(getattr(f, "primary_key", False)),
                    "max_length": getattr(f, "max_length", None),
                }
                if getattr(f, "is_relation", False) and f.related_model is not None:
                    item["related_model"] = f.related_model._meta.label
                    item["on_delete"] = getattr(
                        getattr(f.remote_field, "on_delete", None), "__name__", None
                    )
                rec["fields"].append(item)
            out["models"].append(rec)
        except Exception as exc:  # pragma: no cover - diagnostic
            out["errors"].append(
                f"model {meta.app_label}.{meta.object_name}: {exc!r}"
            )

    # ---- Migrations : qui possède le CreateModel de chaque table --------
    try:
        from django.db.migrations.loader import MigrationLoader
        from django.db.migrations.operations.models import CreateModel

        loader = MigrationLoader(None, ignore_no_migrations=True)
        for (app_label, mig_name), migration in loader.disk_migrations.items():
            for op in migration.operations:
                if isinstance(op, CreateModel):
                    key = f"{app_label}.{op.name}".lower()
                    out["migrations_create"].setdefault(key, [])
                    out["migrations_create"][key].append(f"{app_label}/{mig_name}")
    except Exception as exc:  # pragma: no cover
        out["errors"].append(f"migrations: {exc!r}")
        out["errors"].append(traceback.format_exc())

    sys.stdout.write(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
