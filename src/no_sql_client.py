import json

from django.conf import settings


# Réglages d'une pièce jointe de tâche (Task.attachments) recopiés sur les
# tâches déjà distribuées, le fichier saisi restant inchangé.
ATTACHMENT_CONFIG_KEYS = ("optional", "conditions", "file_type", "share")

# Documents de conception (vues CouchDB) attendus dans chaque base facilitateur. La version de
# référence est celle de la base `process_design`. L'application mobile en dépend :
# - `_design/task_stats` (vue `status_count_full`) : statistiques des tâches par village. Sans elle,
#   la liste des CVD du « Cycle d'investissement » reste vide (fetchTaskStatsFull) ;
# - `_design/tasks_number` : nombres de tâches / dernières activités (tableaux de bord web) ;
# - `_design/views_docs` : tâches planifiées triées par date (planning).
DESIGN_SOURCE_DB = "process_design"
FACILITATOR_DESIGN_DOC_IDS = ("_design/task_stats", "_design/tasks_number", "_design/views_docs")


def _comparable_design(doc):
    """Contenu d'un document de conception sans les métadonnées CouchDB, pour comparer deux versions.
    Ignore ce que cloudant (DesignDocument) ajoute sans effet : `options: {partitioned: false}` et les
    sections vides (`lists: {}`, `indexes: {}`, `shows: {}`...)."""
    doc = {k: v for k, v in (doc or {}).items() if k not in ("_id", "_rev") and v not in ({}, None)}
    if doc.get("options") == {"partitioned": False}:
        doc.pop("options")
    return doc


class NoSQLClient:

    def __init__(self, username=settings.NO_SQL_USER, password=settings.NO_SQL_PASS, url=settings.NO_SQL_URL, timeout=None):
        self.username = username
        self.password = password
        self.url = url
        # None (défaut) = comportement historique inchangé (aucun timeout, requêtes potentiellement
        # bloquantes indéfiniment). À renseigner explicitement pour tout code qui interroge de
        # nombreuses bases CouchDB en parallèle (ex. `dashboard/reports/excel_csv/fc_situation.py`) :
        # sans borne, une seule base injoignable/lente suffit à bloquer tout le lot.
        self.timeout = timeout
        self.client = self.get_client()

    def get_client(self):
        from cloudant.client import CouchDB
        return CouchDB(
            self.username, self.password, url=self.url, connect=True, auto_renew=True,
            timeout=self.timeout,
        )

    def get_dbs(self):
        return self.client.all_dbs()

    def get_db(self, db_name):
        return self.client[db_name]

    def find_all(self, db, selector, fields=None, page_size=1000):
        """Tous les documents correspondant à `selector` (`_find`), paginés par bookmark.

        À préférer à `all_docs(include_docs=True)` quand on ne lit que quelques champs : avec
        `fields`, CouchDB ne renvoie que ces champs au lieu des documents entiers (historiques,
        formulaires… — une base facilitateur de 28 Mo de JSON occupe ~200 Mo de RAM une fois
        parsée). Ne pas utiliser `db.get_query_result(...)[:]` pour tout récupérer : cloudant
        n'envoie alors pas de `limit` et CouchDB tronque silencieusement à 25 documents.
        """
        docs = []
        bookmark = None
        while True:
            kwargs = {'limit': page_size}
            if bookmark:
                kwargs['bookmark'] = bookmark
            result = db.get_query_result(selector, fields=fields, raw_result=True, **kwargs)
            page = result.get('docs', [])
            docs.extend(page)
            bookmark = result.get('bookmark')
            if len(page) < page_size or not bookmark:
                return docs

    def create_db(self, db_name, **kwargs):
        return self.client.create_database(db_name, **kwargs)

    def delete_db(self, db_name):
        try:
            self.client.delete_database(db_name)
        except Exception as e:
            print(e)

    def create_document(self, db, data, **kwargs):
        new_document = db.create_document(data, **kwargs)
        return new_document
    
    def update_doc(self, db, id, doc_new: dict):
        try:
            doc = db.get(id)
            if not doc:
                doc = db.get_design_document(id)
            for k, v in doc_new.items():
                if v:
                    doc[k] = v
            db[id] = doc
            db[id].save()
        except Exception as exc:
            print(exc)
            return {}
        return doc
    
    def update_doc_uncontrolled(self, db, id, doc_new: dict):
        try:
            doc = db.get(id)
            if not doc:
                doc = db.get_design_document(id)
            for k, v in doc_new.items():
                doc[k] = v
            db[id] = doc
            db[id].save()
        except Exception as exc:
            print(exc)
            return {}
        return doc

    def update_cloudant_document(self, db, doc_id, doc_new: dict, dict_of_list_values: dict = {}, attachments=[]):
        """
        dict_of_list_values: dict : content as key the attribut of the document who have as value as list and the values of 
        this key are the attributes than we'll modify their values
        """
        _p = {}
        try:
            from cloudant.document import Document
            _p = Document(db, doc_id)
            
            for k, v in doc_new.items():
                if k in list(dict_of_list_values.keys()): #if we have the attributes list to modify
                    attr = []
                    for i in range(len(v)): #Range the interval of the list of the attribut
                        elt = v[i].copy()
                        new_elt = v[i].copy()

                        if k == "attachments" and attachments: #if we have the attachments to modify
                            # Slot déjà présent (même nom) : on garde le fichier saisi
                            # et on reprend la configuration du Générateur de formulaire.
                            existing = next((e for e in attachments if isinstance(e, dict)
                                             and e.get("name") and e.get("name") == elt.get("name")), None)
                            if existing is not None:
                                elt = dict(existing)
                                for config_key in ATTACHMENT_CONFIG_KEYS:
                                    if config_key in new_elt:
                                        elt[config_key] = new_elt[config_key]
                                    else:
                                        elt.pop(config_key, None)

                        for _v in dict_of_list_values[k]: # Go through the attributs list of the doc attr than we going modify
                            if elt.get(_v):
                                elt[_v] = new_elt.get(_v)
                        attr.append(elt)

                    _p.field_set(_p, k, attr)
                    continue
                
                try:
                    _p.field_set(_p, k, v)
                except:
                    pass
                
            _p.save()
        except Exception as exc:
            print(exc)
            return {}
        return _p

    def create_user(self, username, password):
        db = self.get_db('_users')
        return db.create_document({
            '_id': f'org.couchdb.user:{username}',
            "name": username,
            "type": "user",
            "roles": [],
            "password": password
        })

    def delete_document(self, db, document_id):
        try:
            db[document_id].delete()
        except Exception as e:
            print(e)

    def delete_user(self, username, no_sql_db=None):
        db = self.get_db('_users')
        self.delete_document(db, f'org.couchdb.user:{username}')
        if no_sql_db:
            self.delete_db(no_sql_db)

    def create_replication(self, source_db, target_db, **kwargs):
        from cloudant.replicator import Replicator
        return Replicator(self.client).create_replication(source_db, target_db, **kwargs)

    def replicate_design_db(self, target_db, **kwargs):
        source_db = self.get_db('design')
        return self.create_replication(source_db, target_db, **kwargs)

    def _raw_get(self, db, doc_id):
        """Document brut (dict) ou None s'il n'existe pas. Passe par HTTP plutôt que par les objets
        Document/DesignDocument de cloudant, qui gardent un cache et ajoutent des champs par défaut."""
        resp = self.client.r_session.get(f"{db.database_url}/{doc_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def ensure_design_docs(self, target_db, ddoc_ids=FACILITATOR_DESIGN_DOC_IDS, source_db_name=DESIGN_SOURCE_DB,
                           update=False, dry_run=False, source_docs=None):
        """Copie dans `target_db` les documents de conception `ddoc_ids` de la base `source_db_name`.

        Un document absent est créé. Un document présent n'est réécrit qu'avec `update=True` et seulement
        s'il diffère de la source. `dry_run=True` n'écrit rien. `source_docs` ({id: doc}) évite de relire
        la source pour chaque base quand on en traite beaucoup (cf. `load_design_docs`).

        Renvoie {ddoc_id: statut} avec statut parmi : created, updated, unchanged, outdated (diffère, non
        réécrit), missing_in_source, conflict, error: <message>.
        """
        if source_docs is None:
            source_docs = self.load_design_docs(ddoc_ids, source_db_name)
        result = {}
        for ddoc_id in ddoc_ids:
            source = source_docs.get(ddoc_id)
            if not source:
                result[ddoc_id] = "missing_in_source"
                continue
            try:
                current = self._raw_get(target_db, ddoc_id)
                body = {k: v for k, v in source.items() if k not in ("_id", "_rev")}
                if current is None:
                    status = "created"
                elif _comparable_design(current) == _comparable_design(source):
                    result[ddoc_id] = "unchanged"
                    continue
                elif not update:
                    result[ddoc_id] = "outdated"
                    continue
                else:
                    status = "updated"
                    body["_rev"] = current["_rev"]

                if not dry_run:
                    resp = self.client.r_session.put(
                        f"{target_db.database_url}/{ddoc_id}", data=json.dumps(body),
                        headers={"Content-Type": "application/json"},
                    )
                    if resp.status_code == 409:
                        result[ddoc_id] = "conflict"
                        continue
                    resp.raise_for_status()
                result[ddoc_id] = status
            except Exception as exc:  # noqa: BLE001 - une base en erreur ne doit pas arrêter les autres
                result[ddoc_id] = f"error: {exc}"
        return result

    def load_design_docs(self, ddoc_ids=FACILITATOR_DESIGN_DOC_IDS, source_db_name=DESIGN_SOURCE_DB):
        """{ddoc_id: document} des documents de conception de référence (absents ignorés)."""
        source_db = self.get_db(source_db_name)
        docs = {}
        for ddoc_id in ddoc_ids:
            doc = self._raw_get(source_db, ddoc_id)
            if doc:
                docs[ddoc_id] = doc
        return docs

    def add_member_to_database(self, db, username, roles=None):
        security_doc = db.get_security_document()
        members = security_doc['members']
        if 'name' in members:
            members['name'].append(username)
        else:
            members["names"] = [username]

        if roles:
            members['roles'] = roles
        security_doc.save()

    def list_all_databases(self, filter_str=None):
        """
        Lists all databases. If filter_str is provided, only databases containing the given string are returned.

        :param filter_str: (Optional) A string to filter the database names.
        :return: List of database names.
        """
        all_dbs = self.client.all_dbs()
        if filter_str:
            return [db for db in all_dbs if filter_str in db]
        return all_dbs