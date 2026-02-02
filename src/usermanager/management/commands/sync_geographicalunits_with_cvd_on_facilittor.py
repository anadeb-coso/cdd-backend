from django.core.management.base import BaseCommand, CommandError
from dashboard.utils import sync_tasks, add_facilitator_design, sync_geographicalunits_with_cvd_on_facilittor
from process_manager.models import Project, Cycle

class Command(BaseCommand):
    help = 'This command allow to update facilitators cvd informations'

    def handle(self, *args, **options):
        # Your command logic here

        project_id = int(input(f"project_id [Ex.: 3] ({[{p.id: p.name} for p in Project.objects.all()]}) : "))
        develop_mode = bool(int(input("develop_mode [0=False, 1=True] : ") or 0))
        training_mode = bool(int(input("training_mode [0=False, 1=True] : ") or 0))
        no_sql_db = input("facilitator db [Ex. : facilitator_1233456] : ").strip().lower() or None
        
        
        sync_geographicalunits_with_cvd_on_facilittor(project_id, develop_mode, training_mode, no_sql_db)

        self.stdout.write(self.style.SUCCESS('Successfully executed mycommand!'))



