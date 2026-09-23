# Modèles orphelins — aucune table physique (Étape 6)

Déclarés dans le code COSOMIS, aucune table nulle part.

⚠ Vérifié : `authentication.User` (`class User(AbstractUser)`, importé `as GrmUser`) et `authentication.GovernmentWorker` relèvent du **domaine GRM** (`grm_client`, `grm_objects_call`) — **hors périmètre §3, NE PAS y toucher**. Leur table vit dans la base `grm`, jamais fusionnée. Aucune action Étape 6.

- `authentication_governmentworker` — modules : authentication.models — GRM, laissé tel quel
- `authentication_user` — modules : authentication.models — GRM, laissé tel quel
- `authentication_user_groups` — modules : authentication.models — GRM, laissé tel quel
- `authentication_user_user_permissions` — modules : authentication.models — GRM, laissé tel quel
