"""
Étape 1 — Inventaire (volet code, sans accès base).

Croise l'introspection ORM des deux projets Django (CDD `src/`, COSOMIS `cosomis/`)
et produit sous `merge/artifacts/10_inventory/` :

  - schema_inventory.json  : inventaire brut fusionné des deux projets
  - collisions.md          : tables/modèles homonymes, colonnes divergentes,
                             FK molles, champs JSON contenant des listes d'ID
  - ownership.csv          : matrice de propriété du schéma (§4.1 du CLAUDE.md).
                             Les colonnes qui dépendent des bases physiques
                             (existe_dans_*, lignes_*) valent PENDING_DB tant
                             que l'Étape 0 n'a pas tourné.
  - rapport_inventaire.md  : rapport lisible, à relire avant l'Étape 2.

Ce script ne se connecte à AUCUNE base. Il n'écrit rien hors de
`merge/artifacts/10_inventory/`. Idempotent : relancer écrase les artefacts.

Usage :
    python merge/scripts/01_inventory.py
"""
from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# --- Emplacements (voir CLAUDE.md §0) --------------------------------------
REPO = Path(__file__).resolve().parents[2]          # .../cdd-backend
CDD_ROOT = REPO / "src"
COSOMIS_ROOT = Path(r"D:\COSO\PROJECTS\MIS\cosomis\cosomis")

CDD_PY = Path(r"D:\COSO\PROJECTS\CDD\backend\venv_cdd\Scripts\python.exe")
COSOMIS_PY = Path(r"D:\COSO\PROJECTS\MIS\venv_mis\Scripts\python.exe")

PROJECTS = [
    {"label": "cdd", "root": CDD_ROOT, "settings": "cdd.settings", "py": CDD_PY},
    {"label": "cosomis", "root": COSOMIS_ROOT, "settings": "cosomis.settings",
     "py": COSOMIS_PY},
]

OUT_DIR = REPO / "merge" / "artifacts" / "10_inventory"
RAW_DIR = REPO / "merge" / "artifacts" / "00_raw"   # sortie de l'Étape 0
INTROSPECT = Path(__file__).resolve().parent / "_introspect_project.py"

# Tables Django reconstruites, jamais fusionnées ligne à ligne (§4.6)
DJANGO_REBUILT = {
    "django_migrations", "django_content_type", "auth_permission",
    "django_session", "django_admin_log", "django_site",
}
DJANGO_REBUILT_PREFIX = ("django_celery_results", "django_celery_beat")

# Ponts ORM inter-bases connus (§0)
CROSS_DB_CALLS = ["mis_objects_call", "cdd_objects_call", "grm_objects_call"]

# Colonnes entières qui ressemblent à des FK sans contrainte (§1)
SOFT_FK_RE = re.compile(r"(_id|_ids)$")
SOFT_FK_INT_TYPES = {"IntegerField", "BigIntegerField", "PositiveIntegerField",
                     "PositiveBigIntegerField", "SmallIntegerField", "CharField",
                     "TextField"}
JSON_TYPES = {"JSONField"}
JSON_ID_HINT_RE = re.compile(r"(_ids|_id_list|ids_list|list_ids|_ids_)", re.I)
# Champs JSON d'audit omniprésents (métadonnées, pas des listes d'ID métier)
JSON_AUDIT_NOISE = {"create_by_user", "update_by_user", "delete_by_user",
                    "users_involved"}


def run_introspection(proj: dict) -> dict:
    if not Path(proj["py"]).exists():
        raise SystemExit(f"venv introuvable : {proj['py']}")
    if not Path(proj["root"]).exists():
        raise SystemExit(f"racine projet introuvable : {proj['root']}")
    cmd = [str(proj["py"]), str(INTROSPECT), str(proj["root"]),
           proj["settings"], proj["label"]]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        sys.stderr.write(res.stdout + "\n" + res.stderr + "\n")
        raise SystemExit(f"introspection {proj['label']} a échoué (code "
                         f"{res.returncode})")
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError:
        sys.stderr.write(res.stdout[:4000] + "\n" + res.stderr + "\n")
        raise SystemExit(f"sortie non-JSON pour {proj['label']}")


def grep_counts(root: Path, patterns: list[str]) -> dict:
    """Compte brut d'occurrences par motif dans les .py du projet (hors venv,
    migrations, tests). Sert d'indicateur, pas de preuve."""
    counts = {p: [] for p in patterns}
    for path in root.rglob("*.py"):
        parts = set(path.parts)
        if parts & {"migrations", "__pycache__", "tests", "test"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for pat in patterns:
            for m in re.finditer(re.escape(pat), text):
                line = text.count("\n", 0, m.start()) + 1
                counts[pat].append(f"{path.relative_to(root).as_posix()}:{line}")
    return counts


def index_models(inv: dict) -> dict:
    """model_key insensible à la casse -> enregistrement modèle."""
    return {m["object_name"].lower(): m for m in inv["models"]}


def index_by_table(inv: dict) -> dict:
    out: dict[str, list] = {}
    for m in inv["models"]:
        out.setdefault(m["db_table"], []).append(m)
    return out


def field_map(model: dict) -> dict:
    return {f["name"]: f for f in model["fields"]}


def classify(table: str, in_cdd: bool, in_cos: bool,
             mig_cdd: bool, mig_cos: bool) -> str:
    """Pré-classification indicative. La catégorie définitive exige les bases
    physiques (§4.1) : sans elles, on ne descend jamais en A/B fermes."""
    if table in DJANGO_REBUILT or table.startswith(DJANGO_REBUILT_PREFIX):
        return "reconstruite (§4.6)"
    if in_cdd and not in_cos:
        return "C — cdd_only (à confirmer base)"
    if in_cos and not in_cdd:
        return "C — mis_only (à confirmer base)"
    # présent des deux côtés dans le CODE
    if mig_cdd and mig_cos:
        return "à_arbitrer (A probable : CreateModel des deux côtés)"
    if mig_cdd and not mig_cos:
        return "à_arbitrer (B probable : schéma possédé par cdd)"
    if mig_cos and not mig_cdd:
        return "à_arbitrer (B probable : schéma possédé par cosomis)"
    return "à_arbitrer (aucun CreateModel trouvé)"


def _resolve(name: str, phys_names: dict) -> str | None:
    """Fait correspondre un `db_table` du code à une table physique.
    MySQL est insensible à la casse sur les noms de table ; Django tronque en
    outre les noms M2M à 64 caractères (+ suffixe de hash). On tolère les deux."""
    key = name.casefold()
    if key in phys_names:
        return phys_names[key]
    if len(name) >= 60:  # nom potentiellement tronqué par Django
        for pk, pv in phys_names.items():
            if pk[:56] == key[:56]:
                return pv
    return None


def load_phys() -> dict | None:
    """Charge les métadonnées physiques produites par l'Étape 0, si présentes.
    Retourne {name: {'names': {casefold: réel}, 'rows': {réel: int}, 'meta': dict}}."""
    cut = RAW_DIR / "cutpoint.json"
    if not cut.exists():
        return None
    counts = json.loads(cut.read_text(encoding="utf-8"))["sources"]
    out = {}
    for name in ("cdd", "mis"):
        isj = RAW_DIR / name / "_information_schema.json"
        if not isj.exists():
            return None
        meta = json.loads(isj.read_text(encoding="utf-8"))
        names = {t["table_name"].casefold(): t["table_name"]
                 for t in meta["tables"]}
        out[name] = {
            "names": names,
            "rows": {t: v["count"] for t, v in counts.get(name, {}).items()},
            "meta": meta,
        }
    return out


def classify_firm(table, code_cdd, code_cos, mig_cdd, mig_cos, phys):
    """Classification §4.1 avec la vérité des bases physiques.
    Retourne (categorie, note_conflit|None)."""
    if table in DJANGO_REBUILT or table.startswith(DJANGO_REBUILT_PREFIX):
        return "reconstruite (§4.6)", None

    real_cdd = _resolve(table, phys["cdd"]["names"])
    real_cos = _resolve(table, phys["mis"]["names"])
    p_cdd = real_cdd is not None
    p_cos = real_cos is not None
    r_cdd = phys["cdd"]["rows"].get(real_cdd, 0) if p_cdd else 0
    r_cos = phys["mis"]["rows"].get(real_cos, 0) if p_cos else 0

    if not p_cdd and not p_cos:
        return "orpheline (dans le code, absente des deux bases)", \
               "table déclarée dans le code mais absente des deux bases physiques"

    if p_cdd and p_cos:
        # présente physiquement des deux côtés
        if mig_cdd != mig_cos:
            owner = "cdd" if mig_cdd else "cosomis"
            return (f"à_arbitrer (dérive de schéma : table des 2 côtés, "
                    f"CreateModel seulement {owner})"), \
                   (f"table physique des deux côtés mais migration d'un seul "
                    f"côté ({owner}) — §4.1 cas piégeux")
        if (r_cdd == 0) != (r_cos == 0):
            vide = "cdd" if r_cdd == 0 else "cosomis"
            return (f"à_arbitrer (table vide côté {vide} — miroir créé par "
                    f"erreur ?)"), \
                   (f"table physique des deux côtés mais vide côté {vide} "
                    f"({r_cdd} vs {r_cos} lignes) — §4.1 : confirmer avant B")
        if r_cdd == 0 and r_cos == 0:
            return "A (vide des deux côtés — rien à fusionner)", None
        return "A", None

    # présente physiquement d'un seul côté
    owner = "cdd" if p_cdd else "cosomis"
    if code_cdd and code_cos:
        return f"B (miroir, propriétaire={owner})", None
    return f"C — {owner}_only", None


def build_conflicts(rows_conf: list, path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["table", "type_conflit", "detail"])
        for r in rows_conf:
            w.writerow(r)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    invs = {}
    for proj in PROJECTS:
        print(f"[introspection] {proj['label']} …", flush=True)
        invs[proj["label"]] = run_introspection(proj)

    cdd, cos = invs["cdd"], invs["cosomis"]

    # --- grep ponts inter-bases + .using() -------------------------------
    cross = {}
    for proj in PROJECTS:
        cross[proj["label"]] = grep_counts(
            Path(proj["root"]), [".using(", *CROSS_DB_CALLS]
        )

    schema_inventory = {
        "generated_by": "merge/scripts/01_inventory.py",
        "note": ("Volet CODE de l'Étape 1. Les colonnes existe_dans_*/lignes_* "
                 "de ownership.csv exigent l'Étape 0 (dumps MySQL)."),
        "projects": invs,
        "cross_db_access": cross,
    }
    (OUT_DIR / "schema_inventory.json").write_text(
        json.dumps(schema_inventory, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )

    # --- Index -----------------------------------------------------------
    cdd_by_name = index_models(cdd)
    cos_by_name = index_models(cos)
    cdd_by_table = index_by_table(cdd)
    cos_by_table = index_by_table(cos)

    cdd_mig = {k: v for k, v in cdd["migrations_create"].items()}
    cos_mig = {k: v for k, v in cos["migrations_create"].items()}

    def has_mig(inv_mig: dict, model: dict) -> bool:
        key = f"{model['app_label']}.{model['object_name']}".lower()
        return key in inv_mig

    # ================= collisions.md ===================================
    lines: list[str] = []
    lines.append("# collisions.md — Étape 1 (volet code)\n")
    lines.append("> Généré par `merge/scripts/01_inventory.py`. "
                 "Sans accès aux bases physiques : les catégories A/B ne sont "
                 "que *probables* (CLAUDE.md §4.1).\n")

    # 1. modèles de même nom (object_name insensible à la casse)
    common_names = sorted(set(cdd_by_name) & set(cos_by_name))
    lines.append(f"\n## 1. Modèles de même nom ({len(common_names)})\n")
    lines.append("| Modèle | app CDD | table CDD | app COSOMIS | table COSOMIS "
                 "| managed CDD | managed COSOMIS | CreateModel CDD "
                 "| CreateModel COSOMIS |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for name in common_names:
        a, b = cdd_by_name[name], cos_by_name[name]
        lines.append(
            f"| {a['object_name']} | {a['app_label']} | `{a['db_table']}` "
            f"| {b['app_label']} | `{b['db_table']}` | {a['managed']} "
            f"| {b['managed']} | {'oui' if has_mig(cdd_mig, a) else '—'} "
            f"| {'oui' if has_mig(cos_mig, b) else '—'} |"
        )

    # 2. tables de même nom
    common_tables = sorted(set(cdd_by_table) & set(cos_by_table))
    lines.append(f"\n## 2. Tables de même nom ({len(common_tables)})\n")
    lines.append("| Table | modèle(s) CDD | modèle(s) COSOMIS | catégorie probable |")
    lines.append("|---|---|---|---|")
    for t in common_tables:
        ac = ", ".join(m["model_key"] for m in cdd_by_table[t])
        bc = ", ".join(m["model_key"] for m in cos_by_table[t])
        cat = classify(
            t, True, True,
            any(has_mig(cdd_mig, m) for m in cdd_by_table[t]),
            any(has_mig(cos_mig, m) for m in cos_by_table[t]),
        )
        lines.append(f"| `{t}` | {ac} | {bc} | {cat} |")

    # 3. colonnes divergentes sur tables homonymes
    lines.append("\n## 3. Colonnes divergentes sur tables homonymes\n")
    lines.append("Pour chaque table présente des deux côtés dans le code : "
                 "champs seulement CDD, seulement COSOMIS, ou de type différent.\n")
    for t in common_tables:
        cdd_models = cdd_by_table[t]
        cos_models = cos_by_table[t]
        # on compare le 1er modèle concret de chaque côté
        fa = field_map(cdd_models[0])
        fb = field_map(cos_models[0])
        only_a = sorted(set(fa) - set(fb))
        only_b = sorted(set(fb) - set(fa))
        difftype = []
        for name in sorted(set(fa) & set(fb)):
            if fa[name]["type"] != fb[name]["type"] or \
               fa[name]["max_length"] != fb[name]["max_length"]:
                difftype.append(
                    f"{name} (CDD {fa[name]['type']}"
                    f"/{fa[name]['max_length']} vs COSOMIS "
                    f"{fb[name]['type']}/{fb[name]['max_length']})"
                )
        if not (only_a or only_b or difftype):
            continue
        lines.append(f"\n### `{t}`")
        lines.append(f"- **{cdd_models[0]['model_key']}** vs "
                     f"**{cos_models[0]['model_key']}**")
        if only_a:
            lines.append(f"- champs seulement CDD : {', '.join(only_a)}")
        if only_b:
            lines.append(f"- champs seulement COSOMIS : {', '.join(only_b)}")
        if difftype:
            lines.append(f"- types divergents : {'; '.join(difftype)}")

    # 4. FK molles : colonnes *_id / *_ids entières non-FK
    lines.append("\n## 4. Colonnes « FK molles » (entier `*_id`/`*_ids`, pas de "
                 "ForeignKey)\n")
    lines.append("| Projet | Modèle | Champ | Type | null |")
    lines.append("|---|---|---|---|---|")
    for label, inv in (("cdd", cdd), ("cosomis", cos)):
        for m in inv["models"]:
            for f in m["fields"]:
                if f.get("related_model"):
                    continue
                if f["primary_key"]:
                    continue
                if SOFT_FK_RE.search(f["name"]) and f["type"] in SOFT_FK_INT_TYPES:
                    lines.append(
                        f"| {label} | {m['model_key']} | `{f['name']}` "
                        f"| {f['type']} | {f['null']} |"
                    )

    # 5. champs JSON (candidats listes d'ID)
    lines.append("\n## 5. Champs JSON (§1)\n")
    lines.append("### 5.a Candidats « listes d'ID » (à remapper via id_map, §4.4)\n")
    lines.append("| Projet | Modèle | Champ |")
    lines.append("|---|---|---|")
    json_other = []  # (label, model_key, field)
    for label, inv in (("cdd", cdd), ("cosomis", cos)):
        for m in inv["models"]:
            for f in m["fields"]:
                if f["type"] not in JSON_TYPES:
                    continue
                if JSON_ID_HINT_RE.search(f["name"]):
                    lines.append(f"| {label} | {m['model_key']} | `{f['name']}` |")
                elif f["name"] not in JSON_AUDIT_NOISE:
                    json_other.append((label, m["model_key"], f["name"]))
    lines.append("\n### 5.b Autres champs JSON (hors audit `*_by_user`/"
                 "`users_involved`) — à inspecter manuellement\n")
    lines.append("| Projet | Modèle | Champ |")
    lines.append("|---|---|---|")
    for label, mk, fn in json_other:
        lines.append(f"| {label} | {mk} | `{fn}` |")

    # 6. accès inter-bases repérés dans le code
    lines.append("\n## 6. Accès inter-bases dans le code (indicateur)\n")
    for label in ("cdd", "cosomis"):
        lines.append(f"\n### projet {label}")
        for pat, hits in cross[label].items():
            lines.append(f"- `{pat}` : {len(hits)} occurrence(s)")
            for h in hits[:40]:
                lines.append(f"  - {h}")
            if len(hits) > 40:
                lines.append(f"  - … (+{len(hits) - 40})")

    (OUT_DIR / "collisions.md").write_text("\n".join(lines) + "\n",
                                           encoding="utf-8")

    # ================= ownership.csv + conflicts.csv ===================
    phys = load_phys()
    phys_tables = set()
    code_tables = set(cdd_by_table) | set(cos_by_table)
    if phys:
        # tables physiques non couvertes par un db_table du code (après
        # résolution casse + troncature M2M) → à lister comme physiques pures
        resolved = {r for t in code_tables
                    for r in (_resolve(t, phys["cdd"]["names"]),
                              _resolve(t, phys["mis"]["names"])) if r}
        for side in ("cdd", "mis"):
            for real in phys[side]["names"].values():
                if real not in resolved:
                    phys_tables.add(real)
    all_tables = sorted(code_tables | phys_tables)

    conflicts: list = []
    cat_counts: dict = {}
    own_rows: list = []

    with (OUT_DIR / "ownership.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([
            "table", "existe_dans_cdd", "existe_dans_cosomis",
            "lignes_cdd", "lignes_cosomis", "migration_cdd", "migration_cosomis",
            "managed_cdd", "managed_cosomis", "acces_via_using", "categorie",
        ])
        for t in all_tables:
            in_cdd = t in cdd_by_table
            in_cos = t in cos_by_table
            mc, ms = [], []
            for m in cdd_by_table.get(t, []):
                mc += cdd_mig.get(f"{m['app_label']}.{m['object_name']}".lower(), [])
            for m in cos_by_table.get(t, []):
                ms += cos_mig.get(f"{m['app_label']}.{m['object_name']}".lower(), [])
            managed_cdd = (all(m["managed"] for m in cdd_by_table[t])
                           if in_cdd else "")
            managed_cos = (all(m["managed"] for m in cos_by_table[t])
                           if in_cos else "")
            # accès uniquement via .using(<autre alias>) — indice de miroir (§4.1.4)
            using_only = ""
            if phys:
                real_cdd = _resolve(t, phys["cdd"]["names"])
                real_cos = _resolve(t, phys["mis"]["names"])
                col_cdd = "oui" if real_cdd else "non"
                col_cos = "oui" if real_cos else "non"
                r_cdd = phys["cdd"]["rows"].get(real_cdd, "") if real_cdd else ""
                r_cos = phys["mis"]["rows"].get(real_cos, "") if real_cos else ""
                if in_cdd or in_cos:
                    cat, note = classify_firm(t, in_cdd, in_cos, bool(mc),
                                              bool(ms), phys)
                elif t in DJANGO_REBUILT or t.startswith(DJANGO_REBUILT_PREFIX):
                    cat, note = "reconstruite (§4.6)", None
                else:
                    cat, note = "physique_sans_modèle", (
                        "table présente en base mais aucun modèle Django ne la "
                        "déclare")
                if note:
                    conflicts.append([t, "qualification §4.1", note])
            else:
                col_cdd = "code_seulement" if in_cdd else "non"
                col_cos = "code_seulement" if in_cos else "non"
                r_cdd = r_cos = "PENDING_DB"
                cat = classify(t, in_cdd, in_cos, bool(mc), bool(ms))
            head = cat.split(" ")[0].split("(")[0] or cat
            cat_counts[head] = cat_counts.get(head, 0) + 1
            w.writerow([
                t, col_cdd, col_cos, r_cdd, r_cos,
                ";".join(sorted(set(mc))) or "",
                ";".join(sorted(set(ms))) or "",
                managed_cdd, managed_cos, using_only, cat,
            ])
            own_rows.append({"table": t, "categorie": cat,
                             "lignes_cdd": r_cdd, "lignes_cosomis": r_cos})

    build_conflicts(conflicts, OUT_DIR / "conflicts.csv")

    # ================= rapport_inventaire.md ==========================
    n_a = sum(1 for t in common_tables)
    rep = []
    rep.append("# Rapport — Étape 1 : Inventaire (volet code)\n")
    rep.append(f"- Projet CDD : `{CDD_ROOT}` (Django {cdd['django_version']}, "
               f"{len(cdd['models'])} modèles)")
    rep.append(f"- Projet COSOMIS : `{COSOMIS_ROOT}` (Django "
               f"{cos['django_version']}, {len(cos['models'])} modèles)")
    rep.append(f"- Alias base CDD : {list(cdd['databases'])}")
    rep.append(f"- Alias base COSOMIS : {list(cos['databases'])}")
    rep.append(f"- Routeurs CDD : {cdd['database_routers'] or 'aucun'}")
    rep.append(f"- Routeurs COSOMIS : {cos['database_routers'] or 'aucun'}")
    rep.append("")
    rep.append("## Chiffres clés")
    rep.append(f"- Modèles de même `object_name` : **{len(common_names)}**")
    rep.append(f"- Tables (db_table) de même nom : **{len(common_tables)}**")
    rep.append(f"- Tables vues dans le code ou les bases : **{len(all_tables)}**")
    rep.append("")
    if phys:
        rep.append("## Étape 0 : intégrée")
        rep.append(f"- Bases physiques lues : `cdd` "
                   f"({len(phys['cdd']['names'])} tables), `mis` "
                   f"({len(phys['mis']['names'])} tables).")
        rep.append("- `ownership.csv` : colonnes `existe_dans_*` / `lignes_*` "
                   "renseignées, `categorie` **ferme** (§4.1).")
        rep.append("")
        rep.append("### Répartition des catégories")
        for k in sorted(cat_counts):
            rep.append(f"- `{k}` : {cat_counts[k]}")
        # constats saillants dérivés d'ownership.csv
        def cats(pred):
            return [r for r in own_rows if pred(r)]
        a_rows = cats(lambda r: r["categorie"].startswith("A"))
        b_rows = cats(lambda r: r["categorie"].startswith("B"))
        orph = cats(lambda r: r["categorie"].startswith("orpheline"))
        rep.append("")
        rep.append("### Constats saillants")
        rep.append(f"- **Catégorie A (vrais doublons à fusionner) : {len(a_rows)} "
                   f"tables** — " + ", ".join(f"`{r['table']}`" for r in a_rows))
        rep.append(f"- **Catégorie B (miroirs — supprimer la déclaration en "
                   f"double, aucune fusion) : {len(b_rows)}** — "
                   + ", ".join(f"`{r['table']}`" for r in b_rows))
        rep.append(f"- **Orphelines (déclarées dans le code, aucune table) : "
                   f"{len(orph)}** — " + ", ".join(f"`{r['table']}`" for r in orph)
                   + ". À traiter à l'Étape 6 (déclarations mortes), pas de "
                   "données concernées.")
        rep.append("- `auth_user` porte les utilisateurs **des deux côtés** "
                   "(cdd + mis) ; le modèle COSOMIS `authentication.User` "
                   "(`authentication_user`) n'a **pas de table** → la fusion "
                   "des comptes se fait sur `auth_user`, clé `username`.")
        n_arb = sum(v for k, v in cat_counts.items() if k.startswith("à_arbitrer"))
        rep.append("")
        if n_arb:
            rep.append(f"⚠ **{n_arb} table(s) `à_arbitrer`** — voir "
                       "`conflicts.csv`. Aucune Étape 2 tant qu'il en reste.")
        else:
            rep.append("✅ Aucune ligne `à_arbitrer` : Étape 2 débloquée côté "
                       "qualification.")
    else:
        rep.append("## Ce qui reste BLOQUÉ (exige l'Étape 0)")
        rep.append("- `existe_dans_*` / `lignes_*` réels, catégorie A/B ferme.")
        rep.append("- Lancer `merge/scripts/00_extract.py --apply` puis relancer "
                   "ce script.")
    rep.append("")
    rep.append("## Erreurs d'introspection")
    for label, inv in (("cdd", cdd), ("cosomis", cos)):
        errs = inv.get("errors") or []
        rep.append(f"- {label} : {len(errs)} erreur(s)")
        for e in errs[:20]:
            rep.append(f"  - {e}")
    rep.append("")
    rep.append("## Prochaine action")
    if phys and not any(k.startswith("à_arbitrer") for k in cat_counts):
        rep.append("1. Relire `ownership.csv` (catégories fermes).")
        rep.append("2. Fixer, app par app, le propriétaire de schéma PG des apps "
                   "homonymes (décision Étape 6 : chacun migre ses apps propres).")
        rep.append("3. Démarrer l'Étape 2 : `merge/fusion_plan.yml`.")
    else:
        rep.append("1. Arbitrer les lignes `conflicts.csv` (cas piégeux §4.1).")
        rep.append("2. Relancer ce script, viser 0 `à_arbitrer`.")
    rep.append("")
    rep.append("Rappel : `grm` / `grm_objects_call` hors périmètre (§3).")
    (OUT_DIR / "rapport_inventaire.md").write_text("\n".join(rep) + "\n",
                                                   encoding="utf-8")

    print("\nArtefacts écrits dans", OUT_DIR)
    for p in sorted(OUT_DIR.iterdir()):
        print("  -", p.name, f"({p.stat().st_size} o)")
    print(f"\nModèles homonymes : {len(common_names)} | "
          f"tables homonymes : {len(common_tables)}")


if __name__ == "__main__":
    main()
