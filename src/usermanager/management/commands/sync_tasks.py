from django.core.management.base import BaseCommand, CommandError
from dashboard.utils import sync_tasks, add_facilitator_design, sync_geographicalunits_with_cvd_on_facilittor
from process_manager.models import Project, Cycle

class Command(BaseCommand):
    help = 'This command allow to add sync tasks on facilitators db'

    def handle(self, *args, **options):
        # Your command logic here
        project_id = int(input(f"project_id [Ex.: 3] ({[{p.id: p.name} for p in Project.objects.all()]}) : "))
        cycle_id = int(input(f"cycle_id [Ex.: 3] ({[{c.id: c.__str__()} for c in Cycle.objects.filter(project_id=project_id)]}) : "))
        develop_mode = bool(int(input("develop_mode [0=False, 1=True] : ") or 0))
        training_mode = bool(int(input("training_mode [0=False, 1=True] : ") or 0))
        no_sql_dbs = [elt.strip().lower() for elt in input("facilitators db [Ex. : facilitator_1233456,facilitator_12889556, facilitator_1277855] : ").split(",") if elt.strip().lower()]
        administrativelevel_ids = [elt.strip().lower() for elt in input("administrativelevel_ids db [Ex. : 4,1025, 4044] : ").split(",") if elt.strip().lower()]
        tasks_ids = [int(elt.strip().lower()) for elt in input("tasks_ids db [Ex. : 4,1025, 4044] : ").split(",") if elt.strip().lower()]
        
        attachmentsPresented = input("attachmentsPresented [0=False, 1=True, default=None] : ")
        if attachmentsPresented == "":
            attachmentsPresented = None
        else:
            attachmentsPresented = bool(int(attachmentsPresented))
        
        
        run_add_facilitator_design = bool(int(input("run add_facilitator_design [0=False, 1=True] : ") or 0))
        run_sync_geographicalunits_with_cvd_on_facilittor = bool(int(input("run sync_geographicalunits_with_cvd_on_facilittor [0=False, 1=True] : ") or 0))

        sync_tasks(
            project_id, cycle_id, develop_mode, training_mode, no_sql_dbs, administrativelevel_ids, tasks_ids, attachmentsPresented=None
        )

        if run_add_facilitator_design:
            print("\n===================================================add_facilitator_design========================================================")
            add_facilitator_design(develop_mode, training_mode, no_sql_dbs=no_sql_dbs, project_id=project_id)

        if run_sync_geographicalunits_with_cvd_on_facilittor:
            print("\n=============================================sync_geographicalunits_with_cvd_on_facilittor=======================================")
            sync_geographicalunits_with_cvd_on_facilittor(project_id, develop_mode, training_mode)

        self.stdout.write(self.style.SUCCESS('Successfully executed mycommand!'))



