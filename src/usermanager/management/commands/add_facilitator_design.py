from django.core.management.base import BaseCommand, CommandError
from dashboard.utils import add_facilitator_design
from process_manager.models import Project

class Command(BaseCommand):
    help = 'This command allow to add desgin documents to facilitators db'

    def handle(self, *args, **options):
        # Your command logic here
        develop_mode = bool(int(input("develop_mode [0=False, 1=True] : ") or 0))
        training_mode = bool(int(input("training_mode [0=False, 1=True] : ") or 0))
        no_sql_dbs = [elt.strip().lower() for elt in input("facilitators db [Ex. : facilitator_1233456,facilitator_12889556, facilitator_1277855] : ").split(",") if elt.strip().lower()]
        project_id = int(input(f"project_id [Ex.: 3] ({[{p.id: p.name} for p in Project.objects.all()]}) : "))

        add_facilitator_design(
            develop_mode, training_mode, no_sql_dbs=no_sql_dbs, project_id=project_id
        )

        self.stdout.write(self.style.SUCCESS('Successfully executed mycommand!'))



