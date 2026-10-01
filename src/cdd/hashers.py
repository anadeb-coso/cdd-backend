"""Hachage des mots de passe COMMUN à CDD (Web DCC) et au SIG (COSOMIS), qui partagent la table `auth_user`
(base unifiée).

Chaque version de Django a son propre nombre d'itérations PBKDF2 par défaut (Django 4.0, CDD : 320 000 ;
Django 4.1, SIG : 390 000 ; Django 4.2 : 600 000) et réécrit le hash à la connexion dès qu'il diffère du sien.
Or Django vérifie à chaque requête un condensat du hash stocké dans la session : le hash réécrit par l'une des
applications invalidait les sessions ouvertes sur l'autre — se connecter sur le Web DCC déconnectait du SIG, et
inversement.

Les deux applications utilisent donc ce même hasher : un hash d'au moins `min_iterations` itérations n'est jamais
réécrit à la connexion ; les nouveaux mots de passe sont hachés avec `iterations`.
À garder IDENTIQUE dans les deux projets (cdd/hashers.py et cosomis/hashers.py), y compris après une mise à jour
de Django.
"""
from django.contrib.auth.hashers import PBKDF2PasswordHasher, must_update_salt


class SharedPBKDF2PasswordHasher(PBKDF2PasswordHasher):
    algorithm = "pbkdf2_sha256"   # mêmes hash que le hasher par défaut de Django
    iterations = 390000           # nouveaux mots de passe
    min_iterations = 320000       # en dessous seulement, le hash est renforcé à la connexion

    def must_update(self, encoded):
        decoded = self.decode(encoded)
        return decoded["iterations"] < self.min_iterations or must_update_salt(decoded["salt"], self.salt_entropy)

