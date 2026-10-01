"""Initialise le trajet des localités (`LocalityHistory`), une seule fois après le déploiement :

  1. affectations passées des facilitateurs, reconstituées depuis le SIG
     (`AssignAdministrativeLevelToFacilitator`) : arrivée à la date de création de la ligne, départ
     (ligne désactivée) à la date de sa dernière modification, marquée approximative (≈) ;
  2. état actuel constaté : villages de stabilisation et additionnels des facilitateurs, localités
     d'intervention des utilisateurs, et villages d'affectation quand ils diffèrent de ceux reconstitués
     depuis le SIG.

Une personne/section qui a déjà un historique est laissée telle quelle (commande relançable).
Sans `--apply` : affiche seulement ce qui serait créé.

    python manage.py init_localities_history            # aperçu
    python manage.py init_localities_history --apply
"""
from collections import Counter, defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from assignments.models import AssignAdministrativeLevelToFacilitator
from authentication.models import Facilitator, LocalityHistory, UserLocalities
from cdd.call_objects_from_other_db import mis_objects_call
from dashboard.facilitators.localities import administrative_choices
from dashboard.facilitators.localities_history import facilitator_state, record_localities_change, user_state


class Command(BaseCommand):
    help = "Initialise l'historique des localités (affectations du SIG + état actuel constaté)."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help="Enregistrer (sinon aperçu).")

    def handle(self, *args, **options):
        now = timezone.now()
        self.counts = Counter()
        with transaction.atomic():
            self.facilitators(now)
            self.users(now)
            if not options['apply']:
                transaction.set_rollback(True)

        for key, value in sorted(self.counts.items()):
            self.stdout.write(f"  {key}: {value}")
        self.stdout.write(self.style.SUCCESS("Enregistré." if options['apply'] else "Aperçu seulement (--apply pour enregistrer)."))

    def record(self, *args, **kwargs):
        event = record_localities_change(*args, **kwargs)
        if event:
            self.counts[f"{event.get_section_display()} / {event.get_source_display()}"] += 1
        return event

    def facilitators(self, now):
        facilitators = {f.id: f for f in Facilitator.objects.all()}
        with_history = set(LocalityHistory.objects.filter(facilitator__isnull=False).values_list('facilitator_id', 'section'))

        # Mouvements du SIG par facilitateur : (date, approximative, village, +1 arrivée / -1 départ)
        moves = defaultdict(list)
        for facilitator_id, village_id, activated, created, updated in mis_objects_call.filter_objects(
            AssignAdministrativeLevelToFacilitator
        ).values_list('facilitator_id', 'administrative_level_id', 'activated', 'created_date', 'updated_date'):
            if not str(facilitator_id).isdigit() or int(facilitator_id) not in facilitators or not created:
                self.counts["lignes SIG ignorées (facilitateur inconnu)"] += 1
                continue
            moves[int(facilitator_id)].append((created, False, int(village_id), 1))
            if not activated:
                moves[int(facilitator_id)].append((updated or created, True, int(village_id), -1))

        for facilitator in facilitators.values():
            state = facilitator_state(facilitator)

            if (facilitator.id, 'assignment') not in with_history:
                presence = Counter()  # un village peut être affecté dans plusieurs projets
                villages = []
                groups = defaultdict(list)
                for date, approximate, village_id, delta in moves.get(facilitator.id, []):
                    groups[(date.replace(second=0, microsecond=0), approximate)].append((village_id, delta))
                for (date, approximate), changes in sorted(groups.items()):
                    before = list(villages)
                    for village_id, delta in changes:
                        presence[village_id] += delta
                    villages = [v for v in before if presence[v] > 0] + sorted(
                        {v for v, _ in changes if presence[v] > 0 and v not in before}
                    )
                    self.record('assignment', 'mis_import', {'villages': villages}, {'villages': before},
                                facilitator=facilitator, changed_at=date, approximate_date=approximate, changed_by_label="SIG")

                current = administrative_choices(state['assignment']['villages'])
                if facilitator.id in moves:
                    if set(current) != set(villages):
                        # écart entre le SIG et CDD : état actuel constaté, date inconnue
                        self.record('assignment', 'initial_state', {'villages': current}, {'villages': villages},
                                    facilitator=facilitator, changed_at=now, approximate_date=True)
                else:
                    self.record('assignment', 'initial_state', {'villages': current}, None, facilitator=facilitator, changed_at=now)

            for section in ('stabilization', 'additional'):
                if (facilitator.id, section) not in with_history:
                    self.record(section, 'initial_state', state[section], None, facilitator=facilitator, changed_at=now)

    def users(self, now):
        with_history = set(LocalityHistory.objects.filter(user__isnull=False).values_list('user_id', 'section'))
        for record in UserLocalities.objects.select_related('user'):
            state = user_state(record)
            for section in ('intervention', 'intervention_additional'):
                if (record.user_id, section) not in with_history:
                    self.record(section, 'initial_state', state[section], None, user=record.user, changed_at=now)
