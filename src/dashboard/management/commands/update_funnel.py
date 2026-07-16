from django.core.management.base import BaseCommand
import os
from dashboard.facilitators.repository.db_facilitator_repository import FacilitatorRepository
from dashboard.facilitators.repository.facilitator_criteria import FacilitatorCriteria
from dashboard.tasks import sync_celery_tasks_re, sync_aggregated_status_on_adl
from process_manager.models import Project, Cycle, AggregatedStatusFacilitator
from cdd.call_objects_from_other_db import mis_objects_call
from subprojects.models import Project as MisProject
from dashboard.facilitators.functions import update_facilitators_stats

class Command(BaseCommand):
    help = 'Update the AggregatedStatus objects for the funnel'

    def manage_prompt(self, type_value, prompt_message, options=None, default=''):
        if options:
            prompt_message += f" ({options})"
        prompt_message += " : "
        while True:
            try:
                value = input(prompt_message) or default
                if type_value == bool:
                    return bool(int(value))
                elif type_value == int:
                    return int(value)
                elif type_value == list:
                    return [elt.strip().lower() for elt in value.split(",") if elt.strip().lower()]
                else:
                    return value
            except ValueError:
                self.stdout.write(self.style.ERROR(f"Invalid input. Please enter a valid {type_value.__name__} value."))

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('\n\n\t\t**************************** Welcome to synchronize command processes! ****************************'))
        self.stdout.write(self.style.WARNING('You must provide the project_id, cycle_id, develop_mode, training_mode, no_sql_dbs to synchronize the tasks on facilitators db and update the aggregated status on adl!'))
        self.stdout.write(self.style.WARNING('After providing db names, you will be asked if you want to continue the process or not, you can add as many projects as you want before starting the synchronization process!'))

        projects_queue_list = []
        count = 1
        while True:
            self.stdout.write(self.style.WARNING(f'\n\n\t\t**************************** Project {count} ****************************'))
            project_id = self.manage_prompt(int, f"\nproject_id [Ex.: 3] ({[{p.id: p.name} for p in Project.objects.all()]})")
            cycle_id = self.manage_prompt(int, f"cycle_id [Ex.: 3] ({[{c.id: c.__str__()} for c in Cycle.objects.filter(project_id=project_id)]})")
            develop_mode = self.manage_prompt(bool, "develop_mode [0=False, 1=True] (default is False)", default='0')
            training_mode = self.manage_prompt(bool, "training_mode [0=False, 1=True] (default is False)", default='0')
            no_sql_dbs = self.manage_prompt(list, "facilitators db [Ex. : facilitator_1233456,facilitator_12889556, facilitator_1277855]")

            projects_queue_list.append((project_id, cycle_id, develop_mode, training_mode, no_sql_dbs))

            continue_process = self.manage_prompt(bool, "\ncontinue adding process [0=False, 1=True] (default is False)", default='0')
            if not continue_process:
                break
            count += 1

        self.stdout.write(self.style.WARNING('\n\n\t\tYou want to synchronize the following projects with their respective cycles and no_sql_dbs?'))
        for project_id, cycle_id, develop_mode, training_mode, no_sql_dbs in projects_queue_list:
            self.stdout.write(self.style.WARNING(f"\t- Project ID: {project_id}, Cycle ID: {cycle_id}, Develop Mode: {develop_mode}, Training Mode: {training_mode}, No SQL DBs: {no_sql_dbs}"))
        
        confirm = self.manage_prompt(bool, "\nconfirm [0=False, 1=True] (default is True)", default='1')
        if not confirm:
            self.stdout.write(self.style.ERROR('\nProcess cancelled by the user.'))
            return
        
        execute_sync_celery_tasks_re_function = self.manage_prompt(bool, "\nDid you want to execute sync_celery_tasks_re function [0=False, 1=True] (default is True)", default='1')
        execute_sync_aggregated_status_on_adl_function = self.manage_prompt(bool, "\nDid you want to execute sync_aggregated_status_on_adl function [0=False, 1=True] (default is True)", default='1')
        if execute_sync_aggregated_status_on_adl_function:
            execute_adl_village = self.manage_prompt(bool, "\nDid you want to execute adl village [0=False, 1=True] (default is True)", default='1')
            execute_adl_bigger_than_village = self.manage_prompt(bool, "\nDid you want to execute adl bigger than village (canton, commune, prefecture, region) [0=False, 1=True] (default is False)", default='0')

        project_id, cycle_id, develop_mode, training_mode, no_sql_dbs = None, None, None, None, None
        for project_id, cycle_id, develop_mode, training_mode, no_sql_dbs in projects_queue_list:
            self.stdout.write(self.style.WARNING("\n\n====================================================\n"))
            self.stdout.write(self.style.WARNING(f'\tStarting synchronization for Project ID: {project_id}, Cycle ID: {cycle_id}...'))
            
            if execute_sync_celery_tasks_re_function:
                if no_sql_dbs:
                    for no_sql_db in no_sql_dbs:
                        sync_celery_tasks_re(project_id, cycle_id, develop_mode, training_mode, no_sql_db)
                else:
                    sync_celery_tasks_re(project_id, cycle_id, develop_mode, training_mode)
            if execute_sync_aggregated_status_on_adl_function:
                sync_aggregated_status_on_adl(project_id, cycle_id, execute_adl_village, execute_adl_bigger_than_village)
            
            if execute_sync_celery_tasks_re_function or execute_sync_aggregated_status_on_adl_function:
                AggregatedStatusFacilitator.objects.filter(project_id=project_id, cycle_id=cycle_id).update(new_update_exists=True)
            
                #Sync facilitators stats
                print("Sync facilitators stats")
                _project = Project.objects.get(id=project_id)
                facilitators = update_facilitators_stats(
                    FacilitatorRepository().find_by_criteria(
                        criteria=FacilitatorCriteria(
                            facilitator_type='community_facilitator',
                            develop_mode=False,
                            training_mode=False,
                            active=True,
                            projects__id=[project_id]
                        )
                    ), 
                    [],
                    project_id, 
                    cycle_id,
                    _project.couch_id,
                    mis_objects_call.get_object(MisProject, name=_project.name)
                )
                print("End Sync facilitators stats", len(facilitators))

        self.stdout.write(self.style.SUCCESS('Successfully executed update_funnel command!'))

