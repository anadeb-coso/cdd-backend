"""
Django management command to migrate data from CouchDB to MySQL.

This command migrates:
1. TaskSubmission records (from task documents)
2. TaskSubmissionHistory records (from updated_history arrays)
3. TaskUserInvolvement records (from users_involved_in_task arrays)
4. GeolocationCapture records (from geolocation documents)

Usage:
    python manage.py migrate_couchdb_to_mysql [--facilitator-id ID] [--dry-run]
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware, is_aware

from authentication.models import Facilitator
from no_sql_client import NoSQLClient
from process_manager.models import (
    Task, Project, Cycle,
    TaskSubmission, TaskSubmissionHistory,
    TaskUserInvolvement, GeolocationCapture
)

User = get_user_model()

# Configure logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Migrate data from CouchDB to MySQL (TaskSubmission, History, Geolocations)'

    def __init__(self):
        super().__init__()
        self.nsc = None
        self.stats = {
            'task_submissions_processed': 0,
            'task_submissions_created': 0,
            'task_submissions_failed': 0,
            'histories_created': 0,
            'involvements_created': 0,
            'geolocations_processed': 0,
            'geolocations_created': 0,
            'geolocations_failed': 0,
            'users_created': 0,
            'users_skipped': 0,
            'users_failed': 0,
        }
        self.sample_shown = False
        self.show_sample = False

    def add_arguments(self, parser):
        parser.add_argument(
            '--facilitator-id',
            type=int,
            help='Process only this facilitator ID (optional)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without writing to database'
        )
        parser.add_argument(
            '--show-sample',
            action='store_true',
            help='Show a sample task document structure on first error'
        )

    def migrate_facilitator_users(self, facilitators, dry_run: bool):
        """
        Create a Django User for each Facilitator that doesn't have one.
        Uses facilitator.username and facilitator.password (from the old model).
        """
        for facilitator in facilitators:
            try:
                # Skip if User already linked
                if facilitator.user_id:
                    self.stats['users_skipped'] += 1
                    self.stdout.write(
                        f'  ⏭️  Skipping {facilitator.username} — User already exists'
                    )
                    continue

                if dry_run:
                    self.stdout.write(
                        f'  [DRY RUN] Would create User for: {facilitator.username}'
                    )
                    continue

                with transaction.atomic():
                    # Create User — password is already hashed in facilitator.password
                    user, user_created = User.objects.get_or_create(
                        username=facilitator.username,
                        defaults={
                            'first_name': facilitator.name,
                            'email': facilitator.email or '',
                            'is_active': facilitator.active,
                        }
                    )

                    if user_created:
                        # Set the hashed password directly (no re-hashing)
                        user.password = facilitator.password
                        user.save(update_fields=['password'])

                    # Link User to Facilitator
                    facilitator.user = user
                    facilitator.save(update_fields=['user'])

                    self.stats['users_created'] += 1
                    self.stdout.write(
                        f'  ✅ Created User for: {facilitator.username}'
                    )

            except Exception as e:
                self.stats['users_failed'] += 1
                logger.error(
                    f'Failed to create User for facilitator {facilitator.id} '
                    f'({facilitator.username}): {e}'
                )
                self.stdout.write(
                    self.style.ERROR(
                        f'  ❌ Failed: {facilitator.username} — {e}'
                    )
                )

    def handle(self, *args, **options):
        facilitator_id = options.get('facilitator_id')
        dry_run = options.get('dry_run', False)
        self.show_sample = options.get('show_sample', False)

        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 DRY RUN MODE - No data will be written'))

        # Initialize CouchDB client
        self.nsc = NoSQLClient()

        try:
            # Get facilitators to process
            if facilitator_id:
                facilitators = Facilitator.objects.filter(id=facilitator_id)
                if not facilitators.exists():
                    raise CommandError(f'Facilitator with ID {facilitator_id} not found')
            else:
                facilitators = Facilitator.objects.all()

            self.stdout.write(f'Processing {facilitators.count()} facilitator(s)...\n')

            # Create Users for each Facilitator (required for TokenAuthentication)
            self.stdout.write(f'\n👤 Creating User accounts for facilitators...')
            self.migrate_facilitator_users(facilitators, dry_run)

            # Migrate TaskSubmissions from facilitator databases
            for facilitator in facilitators:
                self.stdout.write(f'\n📦 Processing facilitator: {facilitator.name} (ID: {facilitator.id})')
                self.migrate_facilitator_geographical_units(facilitator, dry_run)
                self.migrate_facilitator_tasks(facilitator, dry_run)

            # Migrate geolocations
            self.stdout.write(f'\n🌍 Processing geolocations...')
            self.migrate_geolocations(facilitators, dry_run)

            # Print summary
            self.print_summary()

        except Exception as e:
            logger.exception("Migration failed")
            raise CommandError(f'Migration failed: {str(e)}')
        finally:
            if self.nsc and self.nsc.client:
                self.nsc.client.disconnect()

    def migrate_facilitator_geographical_units(self, facilitator: Facilitator, dry_run: bool):
        """
        Migrate geographical_units field from CouchDB facilitator document to MySQL.
        """
        facilitator_db_name = f"facilitator_{facilitator.no_sql_user}"

        try:
            facilitator_db = self.nsc.get_db(facilitator_db_name)
        except Exception as e:
            return

        # Query facilitator document
        try:
            facilitator_docs = facilitator_db.get_query_result({'type': 'facilitator'})
            if not facilitator_docs:
                return

            facilitator_doc = list(facilitator_docs)[0] if facilitator_docs else None
            if not facilitator_doc:
                return

            geographical_units = facilitator_doc.get('geographical_units', [])

            if geographical_units and not dry_run:
                # Update the facilitator's geographical_units field
                Facilitator.objects.filter(id=facilitator.id).update(
                    geographical_units=geographical_units
                )
                self.stdout.write(f'  ✅ Updated geographical_units ({len(geographical_units)} units)')
            elif dry_run and geographical_units:
                self.stdout.write(f'  [DRY RUN] Would update geographical_units ({len(geographical_units)} units)')

        except Exception as e:
            logger.error(f'Failed to migrate geographical_units for facilitator {facilitator.id}: {e}')

    def migrate_facilitator_tasks(self, facilitator: Facilitator, dry_run: bool):
        """
        Migrate task documents from a facilitator's CouchDB database.
        """
        # Get facilitator database name
        facilitator_db_name = f"facilitator_{facilitator.no_sql_user}"

        try:
            facilitator_db = self.nsc.get_db(facilitator_db_name)
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'  ⚠️  Database {facilitator_db_name} not found: {e}')
            )
            return

        # Query all task documents
        try:
            task_docs = facilitator_db.get_query_result({'type': 'task'})
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'  ❌ Error querying tasks: {e}')
            )
            return

        task_count = 0
        for task_doc in task_docs:
            task_count += 1
            self.stats['task_submissions_processed'] += 1

            try:
                if dry_run:
                    self.stdout.write(f'  [DRY RUN] Would migrate task: {task_doc.get("_id")}')
                else:
                    self.migrate_single_task(task_doc, facilitator)
                    self.stats['task_submissions_created'] += 1
            except Exception as e:
                self.stats['task_submissions_failed'] += 1
                logger.error(f'Failed to migrate task {task_doc.get("_id")}: {e}')
                self.stdout.write(
                    self.style.ERROR(f'  ❌ Failed task {task_doc.get("_id")}: {e}')
                )

        self.stdout.write(f'  ✅ Processed {task_count} task document(s)')

    def migrate_single_task(self, task_doc: Dict, facilitator: Facilitator):
        """
        Migrate a single task document to TaskSubmission with related records.
        """
        # Extract data from CouchDB document
        task_sql_id = task_doc.get('sql_id')
        project_couch_id = task_doc.get('project_id')
        cycle_couch_id = task_doc.get('cycle_id')
        administrative_level_id = task_doc.get('administrative_level_id')

        # Debug: log which fields are missing
        missing_fields = []
        if not task_sql_id:
            missing_fields.append('sql_id')
        if not project_couch_id:
            missing_fields.append('project_id')
        if not cycle_couch_id:
            missing_fields.append('cycle_id')
        if not administrative_level_id:
            missing_fields.append('administrative_level_id')

        if missing_fields:
            logger.warning(
                f'Task {task_doc.get("_id")} missing fields: {", ".join(missing_fields)}. '
                f'Available keys: {list(task_doc.keys())}'
            )

            # Show sample document on first error if requested
            if self.show_sample and not self.sample_shown:
                self.sample_shown = True
                import json
                self.stdout.write(self.style.WARNING('\n📄 Sample task document structure:'))
                self.stdout.write(json.dumps(task_doc, indent=2, default=str))
                self.stdout.write('\n')

            raise ValueError(
                f'Missing required fields ({", ".join(missing_fields)}) in task document {task_doc.get("_id")}'
            )

        # Look up related objects
        try:
            task = Task.objects.get(id=task_sql_id)
        except Task.DoesNotExist:
            raise ValueError(f'Task with SQL ID {task_sql_id} not found')

        # Synchronize support_attachments from CouchDB to Task model
        # If the CouchDB document says it supports attachments, we update the SQL master task
        couch_support_attachments = task_doc.get('support_attachments', False)
        if couch_support_attachments is True and task.support_attachments is False:
            task.support_attachments = True
            task.save(update_fields=['support_attachments'])
            logger.info(f'Updated Task {task.id} support_attachments to True based on CouchDB doc')

        try:
            project = Project.objects.get(couch_id=project_couch_id)
        except Project.DoesNotExist:
            raise ValueError(f'Project with couch_id {project_couch_id} not found')

        try:
            cycle = Cycle.objects.get(couch_id=cycle_couch_id)
        except Cycle.DoesNotExist:
            raise ValueError(f'Cycle with couch_id {cycle_couch_id} not found')

        # Parse dates
        completed_date = None
        if task_doc.get('completed_date') and task_doc['completed_date'] != '0000-00-00 00:00:00':
            completed_date = self.parse_date_string(task_doc['completed_date'])

        last_updated = None
        if task_doc.get('last_updated_moment'):
            last_updated = self.make_datetime_aware(parse_datetime(task_doc['last_updated_moment']))

        # Create or update TaskSubmission
        with transaction.atomic():
            submission, created = TaskSubmission.objects.update_or_create(
                task=task,
                facilitator=facilitator,
                administrative_level_id=int(administrative_level_id),
                project=project,
                cycle=cycle,
                defaults={
                    'completed': task_doc.get('completed', False),
                    'completed_date': completed_date,
                    'form_response': task_doc.get('form_response', []),
                    'validated': task_doc.get('validated'),
                    'updated_after_invalidation': task_doc.get('updated_after_invalidation', False),
                    'processed_attachments': task_doc.get('attachments', []),
                    'couch_rev': task_doc.get('_rev', ''),
                    'synced_to_couch': True,
                }
            )

            if last_updated:
                # Update last_updated manually (since it's auto_now)
                TaskSubmission.objects.filter(id=submission.id).update(last_updated=last_updated)

            # Migrate history
            if 'updated_history' in task_doc and task_doc['updated_history']:
                self.migrate_task_history(submission, task_doc['updated_history'])

            # Migrate user involvements
            if 'users_involved_in_task' in task_doc and task_doc['users_involved_in_task']:
                self.migrate_user_involvements(submission, task_doc['users_involved_in_task'])

    def migrate_task_history(self, submission: TaskSubmission, history_array: List[Dict]):
        """
        Migrate updated_history array to TaskSubmissionHistory records.
        """
        for history_entry in history_array:
            try:
                # Get facilitator
                facilitator_data = history_entry.get('facilitator', {})
                facilitator_sql_id = facilitator_data.get('sql_id')

                # Parse date first (required field)
                created_at = self.make_datetime_aware(parse_datetime(history_entry.get('date')))
                if not created_at:
                    continue

                # Determine intervention type
                intervention_type = self.determine_intervention_type(history_entry)

                # Try to get facilitator
                facilitator = None
                missing_facilitator_data = {}

                if facilitator_sql_id:
                    try:
                        facilitator = Facilitator.objects.get(id=facilitator_sql_id)
                    except Facilitator.DoesNotExist:
                        logger.warning(f'Facilitator {facilitator_sql_id} not found for history entry')
                        # Store the full facilitator data for later investigation
                        missing_facilitator_data = facilitator_data

                # Create history record (with or without facilitator)
                TaskSubmissionHistory.objects.create(
                    submission=submission,
                    facilitator=facilitator,
                    missing_facilitator=missing_facilitator_data,
                    form_response_snapshot=history_entry.get('form_response', {}),
                    form_fields_snapshot=history_entry.get('form_fields', {}),
                    fields_updated=history_entry.get('fields_updated', []),
                    attachments_updated=history_entry.get('attachments_updated', []),
                    attachments_snapshot=history_entry.get('attachments', []),
                    page=history_entry.get('page', 0),
                    intervention_type=intervention_type,
                    created_at=created_at
                )
                self.stats['histories_created'] += 1

            except Exception as e:
                logger.error(f'Failed to migrate history entry: {e}')

    def migrate_user_involvements(self, submission: TaskSubmission, involvements_array: List[Dict]):
        """
        Migrate users_involved_in_task array to TaskUserInvolvement records.
        """
        for involvement in involvements_array:
            try:
                facilitator_sql_id = involvement.get('sql_id')

                # Parse dates first (required fields)
                first_date = self.make_datetime_aware(parse_datetime(involvement.get('first_intervention_date')))
                last_date = self.make_datetime_aware(parse_datetime(involvement.get('last_intervention_date')))

                if not first_date or not last_date:
                    continue

                # Try to get facilitator
                facilitator = None
                missing_facilitator_data = {}

                if facilitator_sql_id:
                    try:
                        facilitator = Facilitator.objects.get(id=facilitator_sql_id)
                    except Facilitator.DoesNotExist:
                        logger.warning(f'Facilitator {facilitator_sql_id} not found for involvement')
                        # Store the full involvement data for later investigation
                        missing_facilitator_data = involvement

                # Create involvement record (with or without facilitator)
                # Note: We can't use unique_together if facilitator can be null,
                # so we check manually
                if facilitator:
                    TaskUserInvolvement.objects.update_or_create(
                        submission=submission,
                        facilitator=facilitator,
                        defaults={
                            'first_intervention_date': first_date,
                            'last_intervention_date': last_date,
                        }
                    )
                else:
                    # Create without facilitator (for missing facilitators)
                    TaskUserInvolvement.objects.create(
                        submission=submission,
                        facilitator=None,
                        missing_facilitator=missing_facilitator_data,
                        first_intervention_date=first_date,
                        last_intervention_date=last_date,
                    )

                self.stats['involvements_created'] += 1

            except Exception as e:
                logger.error(f'Failed to migrate involvement: {e}')

    def migrate_geolocations(self, facilitators, dry_run: bool):
        """
        Migrate geolocation documents from facilitator databases.
        """
        for facilitator in facilitators:
            facilitator_db_name = f"facilitator_{facilitator.no_sql_user}"

            try:
                facilitator_db = self.nsc.get_db(facilitator_db_name)
            except Exception as e:
                continue

            # Query geolocation documents
            try:
                geo_docs = facilitator_db.get_query_result({'type': 'geolocation'})
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'  ⚠️  Error querying geolocations: {e}')
                )
                continue

            for geo_doc in geo_docs:
                self.stats['geolocations_processed'] += 1

                try:
                    if dry_run:
                        self.stdout.write(
                            f'  [DRY RUN] Would migrate geolocation: {geo_doc.get("_id")}'
                        )
                    else:
                        created_count = self.migrate_single_geolocation(geo_doc, facilitator)
                        self.stats['geolocations_created'] += created_count
                except Exception as e:
                    self.stats['geolocations_failed'] += 1
                    logger.error(f'Failed to migrate geolocation {geo_doc.get("_id")}: {e}')

    def migrate_single_geolocation(self, geo_doc: Dict, facilitator: Facilitator) -> int:
        """
        Migrate a single geolocation document.
        Returns the number of GeolocationCapture objects created.
        """
        from django.utils import timezone
        created_count = 0

        # Migrate administrative levels
        for admin_level in geo_doc.get('administrativelevels', []):
            coords_created = self.make_datetime_aware(parse_datetime(admin_level.get('coords_created')))
            coords_updated = self.make_datetime_aware(parse_datetime(admin_level.get('coords_updated')))

            if not coords_created:
                continue

            obj, created = GeolocationCapture.objects.update_or_create(
                facilitator=facilitator,
                administrative_level_id=int(admin_level.get('id')),
                defaults={
                    'administrative_level_name': admin_level.get('name', ''),
                    'latitude': admin_level.get('latitude'),
                    'longitude': admin_level.get('longitude'),
                    'coords_created': coords_created,
                    'synced': geo_doc.get('synced', False),
                }
            )
            if created:
                created_count += 1

            # Update coords_updated manually
            if coords_updated:
                GeolocationCapture.objects.filter(
                    facilitator=facilitator,
                    administrative_level_id=int(admin_level.get('id'))
                ).update(coords_updated=coords_updated)

        # Migrate custom points of interest (others)
        for poi in geo_doc.get('others', []):
            GeolocationCapture.objects.create(
                facilitator=facilitator,
                poi_name=poi.get('name', ''),
                latitude=poi.get('latitude'),
                longitude=poi.get('longitude'),
                coords_created=timezone.now(),
                synced=geo_doc.get('synced', False),
            )
            created_count += 1

        return created_count

    def make_datetime_aware(self, dt: Optional[datetime]) -> Optional[datetime]:
        """
        Ensure datetime is timezone-aware.
        """
        if dt and not is_aware(dt):
            return make_aware(dt)
        return dt

    def determine_intervention_type(self, history_entry: Dict) -> str:
        """
        Determine the intervention type from history entry.
        """
        # This is a heuristic - adjust based on actual data patterns
        if history_entry.get('fields_updated'):
            return 'update'
        return 'create'

    def parse_date_string(self, date_str: str) -> Optional[datetime]:
        """
        Parse various date string formats from CouchDB and return timezone-aware datetime.
        """
        if not date_str or date_str == '0000-00-00 00:00:00':
            return None

        # Try ISO format first
        parsed = parse_datetime(date_str)
        if parsed:
            # Make timezone-aware if needed
            if not is_aware(parsed):
                parsed = make_aware(parsed)
            return parsed

        # Try other common formats
        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y/%m/%d %H:%M:%S',
            '%d-%m-%Y %H:%M:%S',
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(date_str, fmt)
                # Make timezone-aware
                if not is_aware(parsed):
                    parsed = make_aware(parsed)
                return parsed
            except ValueError:
                continue

        logger.warning(f'Could not parse date: {date_str}')
        return None

    def print_summary(self):
        """
        Print migration summary statistics.
        """
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('MIGRATION SUMMARY'))
        self.stdout.write('=' * 60)

        self.stdout.write(f'\n👤 User Accounts:')
        self.stdout.write(f'  • Created: {self.stats["users_created"]}')
        self.stdout.write(f'  • Skipped (already existed): {self.stats["users_skipped"]}')
        self.stdout.write(f'  • Failed: {self.stats["users_failed"]}')

        self.stdout.write(f'\n📋 Task Submissions:')
        self.stdout.write(f'  • Processed: {self.stats["task_submissions_processed"]}')
        self.stdout.write(f'  • Created: {self.stats["task_submissions_created"]}')
        self.stdout.write(f'  • Failed: {self.stats["task_submissions_failed"]}')

        self.stdout.write(f'\n📜 History Records Created: {self.stats["histories_created"]}')
        self.stdout.write(f'👥 User Involvements Created: {self.stats["involvements_created"]}')

        self.stdout.write(f'\n🌍 Geolocations:')
        self.stdout.write(f'  • Processed: {self.stats["geolocations_processed"]}')
        self.stdout.write(f'  • Created: {self.stats["geolocations_created"]}')
        self.stdout.write(f'  • Failed: {self.stats["geolocations_failed"]}')

        self.stdout.write('\n' + '=' * 60 + '\n')

        if self.stats['task_submissions_failed'] > 0 or self.stats['geolocations_failed'] > 0:
            self.stdout.write(
                self.style.WARNING('⚠️  Some records failed. Check logs for details.')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('✅ Migration completed successfully!')
            )
