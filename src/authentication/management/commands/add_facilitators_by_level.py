import time

from django.core.management.base import BaseCommand, CommandError

from authentication.models import Facilitator
from no_sql_client import NoSQLClient


class Command(BaseCommand):
    help = 'Loads administrative levels from csv file to CouchDB'
    error_messages = {
        "more_than_one": "There is more than one document type facilitator in the design database.",
        "only_one": "Make sure there is only one document of type facilitator in the design database.",
        "no_facilitator": "There is no document type facilitator in the design database.",
        "no_administrative_level": "There is no document of type administrative_level with the given name.",
        "no_database": "There is no database with the given name.",
    }

    def add_arguments(self, parser):
        parser.add_argument('database', type=str, help='Name of the database with documents type administrative_level')
        parser.add_argument('administrative_level', type=str, help='Administrative level name')

    def handle(self, *args, **kwargs):
        database = kwargs['database']
        administrative_level = kwargs['administrative_level']

        # for f in Facilitator.objects.exclude(username='test'):
        #     facilitator_db_name = f.no_sql_db_name
        #     f.delete(no_sql_db=facilitator_db_name)
        #     print(f'deleted {facilitator_db_name}')

        nsc = NoSQLClient()
        try:
            administrative_level_db = nsc.get_db(database)
        except Exception as e:
            raise CommandError(f'{self.error_messages["no_database"]} {e}')

        regions = administrative_level_db.get_query_result(
            {
                "type": 'administrative_level',
                "administrative_level": administrative_level,
            }
        )
        if len(regions[:]) == 0:
            raise CommandError(f'{self.error_messages["no_administrative_level"]}')

        added = 0
        for doc in regions:
            facilitator, created = Facilitator.objects.get_or_create(
                username=f'{doc["name"].replace(" ", "_")}_{doc["administrative_id"]}')
            if created:
                added += 1
            else:
                continue
            facilitator_db_name = facilitator.no_sql_db_name
            facilitator_db = nsc.get_db(facilitator_db_name)
            query_result = facilitator_db.get_query_result({"type": 'facilitator'})[:]
            start = time.time()
            while len(query_result) == 0:
                query_result = facilitator_db.get_query_result({"type": 'facilitator'})[:]
                print(f'esperando documento para facilitator {facilitator.no_sql_user}')
                end = time.time()
                if (end - start) > 10:
                    facilitator.delete(no_sql_db=facilitator_db_name)
                    raise CommandError(f'{self.error_messages["no_facilitator"]}')

            if len(query_result) > 1:
                facilitator.delete(no_sql_db=facilitator_db_name)
                raise CommandError(f'{self.error_messages["more_than_one"]} {self.error_messages["only_one"]}')

            facilitator_doc = facilitator_db[query_result[0]['_id']]
            facilitator_doc["administrative_levels"] = [
                {
                    "name": doc["name"],
                    "id": doc["administrative_id"],
                }
            ]
            facilitator_doc.save()

        self.stdout.write(self.style.SUCCESS(f'Successfully added {added} facilitators'))
