from django.conf import settings


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
                            for elt_attach in attachments: #Go through the attachments
                                if elt_attach.get("name") and elt_attach.get("name") == elt.get("name"):
                                    elt = attachments[i]

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