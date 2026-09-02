# Rapport — Étape 3 : Correspondance des ID

- Généré : 2026-09-02T17:45:30
- `merge/id_map.csv` : 255 lignes
- `merge/conflicts.csv` : 185 lignes

| table | cdd | mis | matched | new_alloc | doublons |
|---|--:|--:|--:|--:|--:|
| `auth_group` | 31 | 31 | 31 | 0 | 0 |
| `auth_user` | 82 | 79 | 78 | 1 | 0 |
| `process_manager_wave` | 5 | 6 | 5 | 1 | 0 |
| `process_manager_administrativelevelwave` | 35 | 59 | 0 | 59 | 0 |
| `auth_user_groups` | 89 | 80 | 0 | 2 | 78 |
| `auth_group_permissions` | 0 | 0 | 0 | 0 | 0 |
| `auth_user_user_permissions` | 0 | 0 | 0 | 0 | 0 |

## Conflits par type
- doublon_liaison : 78
- rapprochement : 1
- valeur : 106

## Règle de valeur appliquée
- CDD gagne ; COSOMIS comble les NULL ; divergences non nulles journalisées (aucun écrasement silencieux). Aucune exception « COSOMIS gagne » déclarée sur les tables A.

## Suite
Relire `conflicts.csv`, puis Étape 4 : `merge/scripts/04_build_unified.py`.
