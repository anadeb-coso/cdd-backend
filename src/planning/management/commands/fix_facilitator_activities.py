"""Rattache à leur facilitateur les activités de planification enregistrées depuis le mobile sur son compte web.

Depuis que chaque facilitateur a un compte web lié (`Facilitator.user`, même e-mail), l'enregistrement d'une
activité depuis le mobile (`planning/api/views.py::RestSaveActivity`) trouvait ce compte web avant le
facilitateur : l'activité était rattachée à `user` et `facilitator` restait vide. Le mobile, qui relit l'agenda
d'un facilitateur par `facilitator__username`, ne l'affichait plus (le web, lui, l'affichait).

Cette commande remet ces activités dans l'état d'avant : `facilitator` = le facilitateur lié au compte web,
`user` vidé. Seules sont touchées les activités sans facilitateur dont le compte web est lié à un facilitateur ;
rien d'autre n'est modifié (dates, validations, commentaires, fichiers inchangés).

Sans --apply : aperçu, rien n'est écrit.

    python manage.py fix_facilitator_activities
    python manage.py fix_facilitator_activities --apply
"""
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from authentication.models import Facilitator
from planning.models import Activity


class Command(BaseCommand):
    help = "Rattache à leur facilitateur les activités du mobile enregistrées sur son compte web lié."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help="Écrit les corrections (sans : aperçu seulement).")

    def handle(self, *args, **options):
        facilitator_of_user = {
            user_id: (facilitator_id, name, email)
            for user_id, facilitator_id, name, email in Facilitator.objects.filter(user__isnull=False)
            .values_list('user_id', 'id', 'name', 'email')
        }
        activities = Activity.objects.filter(facilitator__isnull=True, user_id__in=list(facilitator_of_user))
        by_facilitator = defaultdict(list)
        for activity_id, user_id, created in activities.values_list('id', 'user_id', 'created_date').order_by('created_date'):
            by_facilitator[facilitator_of_user[user_id]].append((activity_id, created))

        total = sum(len(rows) for rows in by_facilitator.values())
        self.stdout.write(f"Activités à rattacher à leur facilitateur : {total} ({len(by_facilitator)} facilitateur(s))")
        for (facilitator_id, name, email), rows in sorted(by_facilitator.items(), key=lambda item: item[0][1] or ''):
            first, last = rows[0][1], rows[-1][1]
            self.stdout.write(
                f"  - {name} <{email}> (facilitateur {facilitator_id}) : {len(rows)} activité(s), "
                f"du {first:%d/%m/%Y %H:%M} au {last:%d/%m/%Y %H:%M} ; ids {', '.join(str(i) for i, _ in rows)}"
            )

        if not options['apply']:
            self.stdout.write(self.style.WARNING("Aperçu seulement : relancer avec --apply pour écrire."))
            return

        with transaction.atomic():
            updated = 0
            for (facilitator_id, _, _), rows in by_facilitator.items():
                updated += Activity.objects.filter(id__in=[i for i, _ in rows], facilitator__isnull=True).update(
                    facilitator_id=facilitator_id, user=None,
                )
        self.stdout.write(self.style.SUCCESS(f"{updated} activité(s) rattachée(s) à leur facilitateur."))
