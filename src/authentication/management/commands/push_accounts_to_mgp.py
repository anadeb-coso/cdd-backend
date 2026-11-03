"""Crée sur le MGP les comptes du DCC qui n'y ont pas encore de compte de même e-mail (facilitateurs, puis
utilisateurs web qui ne sont pas des facilitateurs), avec la même empreinte de mot de passe.

Sans --apply : liste seulement les comptes manquants. Les comptes MGP existants ne sont jamais modifiés."""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db.models import Q

from authentication.accounts import grm_account
from authentication.mgp_accounts import create_account_on_mgp, linked_facilitator


class Command(BaseCommand):
    help = "Create on the MGP the DCC accounts (facilitators and web users) that have no MGP account with the same e-mail."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help="Create the missing accounts (preview otherwise).")
        parser.add_argument('--include-inactive', action='store_true', help="Also inactive DCC accounts.")

    def handle(self, *args, **options):
        from authentication.models import Facilitator

        apply, seen = options['apply'], set()
        missing = []

        facilitators = Facilitator.objects.exclude(Q(email__isnull=True) | Q(email='')).exclude(training_mode=True)
        if not options['include_inactive']:
            facilitators = facilitators.filter(active=True)
        for facilitator in facilitators.order_by('id'):
            key = facilitator.email.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            if grm_account(key) is None:
                missing.append(('facilitator', facilitator))

        users = User.objects.exclude(Q(email__isnull=True) | Q(email=''))
        if not options['include_inactive']:
            users = users.filter(is_active=True)
        for user in users.order_by('id'):
            key = user.email.strip().lower()
            if key in seen or linked_facilitator(user) is not None:
                continue
            seen.add(key)
            if grm_account(key) is None:
                missing.append(('user', user))

        counts = {}
        for kind, account in missing:
            label = getattr(account, 'name', None) or account.get_full_name() or account.username
            if apply:
                status, detail = create_account_on_mgp(account)
                counts[status] = counts.get(status, 0) + 1
                self.stdout.write(f"{kind:11} {account.pk:>6} {account.email:<45} {label} -> {status}{' (' + str(detail) + ')' if detail else ''}")
            else:
                self.stdout.write(f"{kind:11} {account.pk:>6} {account.email:<45} {label}")

        self.stdout.write(self.style.SUCCESS(
            f"{len(missing)} account(s) without MGP account"
            + (f" — result: {counts}" if apply else " (preview: run again with --apply to create them)")
        ))
