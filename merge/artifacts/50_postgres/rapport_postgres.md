# Rapport — Étape 5 : Chargement PostgreSQL

- Base : `cdd_cosomis_unified` (PostgreSQL 18)
- Généré : 2026-09-23T23:49:42
- migrate CDD : True ; migrate COSOMIS : True
- COPY : **106 tables OK**, 0 en échec
- Séquences recalées : 104
- migrate --fake COSOMIS + --check : True

## Chargées (106 tables, 201755 lignes)

## Suite
Étape 7 (`07_remap_couchdb.py`, dry-run) puis contrôles d'acceptation (`merge/scripts/checks/`).
