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
        db.create_document(data, **kwargs)

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

    def delete_user(self, username):
        db = self.get_db('_users')
        self.delete_document(db, f'org.couchdb.user:{username}')

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
