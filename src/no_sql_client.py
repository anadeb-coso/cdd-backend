from django.conf import settings


class NoSQLClient:

    def __init__(self, username=settings.NO_SQL_USER, password=settings.NO_SQL_PASS, url=settings.NO_SQL_URL):
        self.username = username
        self.password = password
        self.url = url
        self.client = self.get_client()

    def get_client(self):
        from cloudant.client import CouchDB
        return CouchDB(self.username, self.password, url=self.url, connect=True, auto_renew=True)

    def get_dbs(self):
        return self.client.all_dbs()

    def get_db(self, db_name):
        return self.client[db_name]

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
            for k, v in doc_new.items():
                if v:
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

                _p.field_set(_p, k, v)
                
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
