"""
Étape 3 — Correspondance des ID.

Produit :
  - merge/id_map.csv        table, source, old_id, new_id, reason
                            reason ∈ {matched, new_allocation, conflict}
  - merge/conflicts.csv     table, source, ref, type, detail
  - merge/artifacts/30_idmap/rapport_idmap.md

Ne concerne QUE la catégorie A de `fusion_plan.yml` (§4.4/§4.5). Les catégories
B et C n'ont aucune entrée (ID transportés tels quels).

Règles :
  - ligne COSOMIS dont la clé naturelle existe côté CDD → new_id = id CDD, reason=matched
  - ligne COSOMIS seule → new_id = MAX(id CDD) + rang, reason=new_allocation
    (allocation déterministe : tri par old_id croissant)
  - tables de liaison (auth_user_groups…) : PK technique transportée ; après
    remap des FK, une ligne COSOMIS dont le couple existe déjà côté CDD est
    abandonnée (dédoublonnage, journalisée) ; sinon nouvelle PK allouée.
  - conflit de valeur sur ligne appariée : CDD gagne (défaut), COSOMIS comble
    les NULL ; toute divergence non nulle est journalisée dans conflicts.csv.

Idempotent, lecture seule des artefacts (00_raw + fusion_plan.yml).

Usage : python merge/scripts/03_build_id_map.py
"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
RAW = REPO / "merge" / "artifacts" / "00_raw"
OUT = REPO / "merge" / "artifacts" / "30_idmap"
PLAN = REPO / "merge" / "fusion_plan.yml"
ID_MAP = REPO / "merge" / "id_map.csv"
CONFLICTS = REPO / "merge" / "conflicts.csv"

csv.field_size_limit(1 << 24)
NULL = r"\N"


def rows(db: str, table: str):
    p = RAW / db / f"{table}.csv"
    with p.open(encoding="utf-8", newline="") as fh:
        r = csv.reader(fh)
        header = next(r)
        idx = {c: i for i, c in enumerate(header)}
        return idx, [tuple(x) for x in r]


def val(row, idx, col):
    v = row[idx[col]]
    return None if v == NULL else v


def natural_key_index(db, table, key, resolve):
    """{clé_tuple: id} pour une table donnée."""
    idx, rr = rows(db, table)
    maps = {}
    for logical, (fkcol, rtable, rcol) in (resolve or {}).items():
        ridx, rrr = rows(db, rtable)
        maps[logical] = (fkcol, {r[ridx["id"]]: r[ridx[rcol]] for r in rrr})
    out = {}
    for r in rr:
        parts = []
        for k in key:
            if k in maps:
                fkcol, m = maps[k]
                parts.append(m.get(r[idx[fkcol]], "<?>"))
            else:
                parts.append(r[idx[k]])
        out[tuple(parts)] = r[idx["id"]]
    return idx, rr, out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    plan = yaml.safe_load(PLAN.read_text(encoding="utf-8"))
    tables = plan["tables"]

    id_map_rows: list[tuple] = []          # (table, source, old_id, new_id, reason)
    conflict_rows: list[tuple] = []        # (table, source, ref, type, detail)
    summary: dict[str, dict] = {}

    NATKEY = {
        "auth_group": (["name"], None, ["name"]),
        "auth_user": (["username"], None, ["email"]),
        "process_manager_wave": (["number"], None, []),
        "process_manager_administrativelevelwave": (
            ["project_id", "wave.number", "administrative_level_id"],
            {"wave.number": ("wave_id", "process_manager_wave", "number")}, []),
    }
    LINK = {
        "auth_user_groups": ["user_id", "group_id"],
        "auth_group_permissions": ["group_id", "permission_id"],
        "auth_user_user_permissions": ["user_id", "permission_id"],
    }

    # ---- 0. concepts partagés inter-tables (Project, Cycle) — D'ABORD --
    #     pour que PROJ_MAP serve à résoudre project_id ailleurs.
    PROJ_MAP: dict[str, str] = {}
    for concept, spec in (plan.get("cross_concept") or {}).items():
        ct, dt = spec["cosomis_table"], spec["cdd_table"]
        ckey = spec["natural_key"]
        try:
            d_idx, d_rows = rows("cdd", dt)
            cc_idx, cc_rows = rows("mis", ct)
        except FileNotFoundError:
            continue

        def _kt(row, idx, is_cdd):
            parts = []
            for k in ckey:
                v = row[idx[k]]
                if k == "project_id" and not is_cdd:
                    v = PROJ_MAP.get(v, v)
                parts.append(v)
            return tuple(parts)

        d_index = {_kt(r, d_idx, True): r[d_idx["id"]] for r in d_rows}
        m0 = n0 = 0
        max_cdd = max((int(r[d_idx["id"]]) for r in d_rows), default=0)
        alloc = 0
        for r in sorted(cc_rows, key=lambda x: int(x[cc_idx["id"]])):
            old = r[cc_idx["id"]]
            k = _kt(r, cc_idx, False)
            if k in d_index:
                new = d_index[k]
                id_map_rows.append((dt, "cosomis", old, new, "matched"))
                m0 += 1
            else:
                alloc += 1
                new = str(max_cdd + alloc)
                id_map_rows.append((dt, "cosomis", old, new, "new_allocation"))
                n0 += 1
            if dt == "process_manager_project":
                PROJ_MAP[old] = new
        summary[f"{concept} ({ct}→{dt})"] = {
            "cdd": len(d_rows), "mis": len(cc_rows),
            "matched": m0, "new_allocation": n0}

    # ---- 1. tables A à clé naturelle ---------------------------------
    for table, (key, resolve, crosscheck) in NATKEY.items():
        c_idx, c_rows, c_index = natural_key_index("cdd", table, key, resolve)
        m_idx, m_rows, _ = natural_key_index("mis", table, key, resolve)
        maps = {}
        for logical, (fkcol, rtable, rcol) in (resolve or {}).items():
            ridx, rrr = rows("mis", rtable)
            maps[logical] = (fkcol, {r[ridx["id"]]: r[ridx[rcol]] for r in rrr})
        max_cdd = max((int(r[c_idx["id"]]) for r in c_rows), default=0)
        matched = new_alloc = 0
        alloc = 0
        for r in sorted(m_rows, key=lambda x: int(x[m_idx["id"]])):
            parts = []
            for k in key:
                if k in maps:
                    fkcol, mm = maps[k]
                    parts.append(mm.get(r[m_idx[fkcol]], "<?>"))
                elif k == "project_id":
                    parts.append(PROJ_MAP.get(r[m_idx[k]], r[m_idx[k]]))
                else:
                    parts.append(r[m_idx[k]])
            kt = tuple(parts)
            old = r[m_idx["id"]]
            if kt in c_index:
                new = c_index[kt]
                id_map_rows.append((table, "cosomis", old, new, "matched"))
                matched += 1
                # crosscheck + conflits de valeur
                crow = next(x for x in c_rows if x[c_idx["id"]] == new)
                for col in c_idx:
                    if col == "id" or col not in m_idx:
                        continue
                    cv, mv = val(crow, c_idx, col), val(r, m_idx, col)
                    if col in crosscheck and cv and mv and \
                            cv.casefold() != mv.casefold():
                        conflict_rows.append((table, "cosomis", f"id={old}->{new}",
                                              "crosscheck", f"{col}: cdd={cv!r} "
                                              f"mis={mv!r}"))
                    elif cv and mv and cv != mv:
                        conflict_rows.append((table, "cosomis", f"id={old}->{new}",
                                              "valeur", f"{col}: cdd={cv!r} "
                                              f"mis={mv!r} (CDD gagne)"))
            else:
                alloc += 1
                new = str(max_cdd + alloc)
                id_map_rows.append((table, "cosomis", old, new, "new_allocation"))
                new_alloc += 1
        summary[table] = {"cdd": len(c_rows), "mis": len(m_rows),
                          "matched": matched, "new_allocation": new_alloc}
        if table == "process_manager_administrativelevelwave":
            conflict_rows.append((table, "-", "-", "rapprochement",
                                  f"{matched} appariées / {new_alloc} nouvelles "
                                  "après résolution du concept Project "
                                  "(subprojects_project → process_manager_project "
                                  "par name)."))

    # ---- 2. tables de liaison A ------------------------------------
    # id_map des cibles déjà construit
    def target_map(tbl):
        d = {}
        for (t, s, o, n, reason) in id_map_rows:
            if t == tbl and s == "cosomis":
                d[o] = n
        return d
    umap = target_map("auth_user")
    gmap = target_map("auth_group")

    for table, linkcols in LINK.items():
        try:
            c_idx, c_rows = rows("cdd", table)
            m_idx, m_rows = rows("mis", table)
        except FileNotFoundError:
            continue
        if not m_rows:
            summary[table] = {"cdd": len(c_rows), "mis": 0, "matched": 0,
                              "new_allocation": 0}
            continue
        remap = {"user_id": umap, "group_id": gmap}
        cdd_pairs = {tuple(r[c_idx[c]] for c in linkcols) for r in c_rows}
        max_cdd = max((int(r[c_idx["id"]]) for r in c_rows), default=0)
        alloc = dup = 0
        for r in sorted(m_rows, key=lambda x: int(x[m_idx["id"]])):
            pair = tuple(remap.get(c, {}).get(r[m_idx[c]], r[m_idx[c]])
                         for c in linkcols)
            old = r[m_idx["id"]]
            if pair in cdd_pairs:
                dup += 1
                id_map_rows.append((table, "cosomis", old, "", "conflict"))
                conflict_rows.append((table, "cosomis", f"id={old}",
                                      "doublon_liaison",
                                      f"{linkcols}={pair} déjà présent côté CDD "
                                      "→ ligne abandonnée"))
            else:
                alloc += 1
                id_map_rows.append((table, "cosomis", old, str(max_cdd + alloc),
                                    "new_allocation"))
                cdd_pairs.add(pair)
        summary[table] = {"cdd": len(c_rows), "mis": len(m_rows),
                          "matched": 0, "new_allocation": alloc, "doublons": dup}

    # ---- écritures -------------------------------------------------
    with ID_MAP.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["table", "source", "old_id", "new_id", "reason"])
        w.writerows(id_map_rows)
    with CONFLICTS.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["table", "source", "ref", "type", "detail"])
        w.writerows(conflict_rows)

    rep = ["# Rapport — Étape 3 : Correspondance des ID\n"]
    rep.append(f"- Généré : {datetime.now().isoformat(timespec='seconds')}")
    rep.append(f"- `merge/id_map.csv` : {len(id_map_rows)} lignes")
    rep.append(f"- `merge/conflicts.csv` : {len(conflict_rows)} lignes")
    rep.append("")
    rep.append("| table | cdd | mis | matched | new_alloc | doublons |")
    rep.append("|---|--:|--:|--:|--:|--:|")
    for t, s in summary.items():
        rep.append(f"| `{t}` | {s['cdd']} | {s['mis']} | {s['matched']} | "
                   f"{s['new_allocation']} | {s.get('doublons', 0)} |")
    rep.append("")
    by_type: dict[str, int] = {}
    for (_, _, _, ty, _) in conflict_rows:
        by_type[ty] = by_type.get(ty, 0) + 1
    rep.append("## Conflits par type")
    for k, v in sorted(by_type.items()):
        rep.append(f"- {k} : {v}")
    rep.append("")
    rep.append("## Règle de valeur appliquée")
    rep.append("- CDD gagne ; COSOMIS comble les NULL ; divergences non nulles "
               "journalisées (aucun écrasement silencieux). Aucune exception "
               "« COSOMIS gagne » déclarée sur les tables A.")
    rep.append("")
    rep.append("## Suite")
    rep.append("Relire `conflicts.csv`, puis Étape 4 : "
               "`merge/scripts/04_build_unified.py`.")
    (OUT / "rapport_idmap.md").write_text("\n".join(rep) + "\n", encoding="utf-8")

    print("id_map.csv :", len(id_map_rows), "lignes ;",
          "conflicts.csv :", len(conflict_rows), "lignes")
    for t, s in summary.items():
        print(f"  {t}: matched={s['matched']} new={s['new_allocation']} "
              f"dup={s.get('doublons', 0)}")


if __name__ == "__main__":
    main()
