"""Recopie les enregistrements COSOCollect envoyés dans les tâches du cycle d'investissement.

Par défaut : simulation (rien n'est écrit). Ajouter --apply pour écrire dans CouchDB (et copier les fichiers).

Exemples :
    python manage.py migrate_cosocollect_to_tasks --project 4 --cycle 1 --matches-only
    python manage.py migrate_cosocollect_to_tasks --project 4 --cycle 1 --report rapport.csv
    python manage.py migrate_cosocollect_to_tasks --project 4 --cycle 1 --map 61:205 --apply
    python manage.py migrate_cosocollect_to_tasks --project 4 --cycle 1 --no-overwrite --attachments-by order --apply
    python manage.py migrate_cosocollect_to_tasks --project 4 --cycle 1 --force-validated --apply   # tâches validées aussi
    python manage.py migrate_cosocollect_to_tasks --project 4 --cycle 1 --status submitted --status completed  # + remplis non envoyés
    python manage.py migrate_cosocollect_to_tasks --project 4 --cycle 1 --accounts real_fc --accounts real_ft  # vrais FC + FT

Voir coso_collect/task_migration.py pour les règles.
"""
import argparse
import csv
from collections import Counter

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from coso_collect import task_migration as tm
from coso_collect.models import CollectForm, CollectSubmission
from process_manager.models import Cycle, Project, Task

ACCOUNT_LABELS = {
    tm.ACCOUNT_REAL_FC: 'vrais FC', tm.ACCOUNT_REAL_FT: 'vrais FT', tm.ACCOUNT_TRAINING: 'comptes de formation',
    tm.ACCOUNT_DEVELOP: 'comptes de démonstration', tm.ACCOUNT_OTHERS: 'autres comptes',
}


class Command(BaseCommand):
    help = "Recopie les enregistrements COSOCollect envoyés dans les tâches du cycle (simulation sans --apply)."

    def add_arguments(self, parser):
        parser.add_argument('--project', type=int, required=True, help='Id du projet (process_manager.Project).')
        parser.add_argument('--cycle', type=int, help='Id du cycle (défaut : le seul cycle du projet).')
        parser.add_argument('--form', type=int, action='append', default=[],
                            help='Limiter à ce formulaire COSOCollect (répétable). Défaut : tous.')
        parser.add_argument('--map', action='append', default=[], metavar='FORM_ID:TASK_ID',
                            help='Correspondance forcée formulaire -> tâche (répétable).')
        parser.add_argument('--min-score', type=float, default=tm.DEFAULT_MIN_SCORE,
                            help='Seuil du rapprochement approché des titres (0-1, défaut %(default)s).')
        parser.add_argument('--task', type=int, action='append', default=[],
                            help='Limiter à cette tâche (id, répétable) — import comme annulation.')
        parser.add_argument('--village', type=int, action='append', default=[],
                            help="Limiter à ce village / canton / commune / préfecture / région (id, répétable). Un niveau "
                                 "supérieur au village vaut pour tous ses villages (enregistrements de ses cantons ET "
                                 "de leurs villages ; --undo : tâches de ses villages).")
        parser.add_argument('--no-overwrite', action='store_true',
                            help='Ne pas écraser une tâche déjà remplie (défaut : écraser).')
        parser.add_argument('--attachments-by', choices=[tm.ATTACHMENTS_BY_NAME, tm.ATTACHMENTS_BY_ORDER],
                            default=tm.ATTACHMENTS_BY_NAME,
                            help='Rapprochement des photos/fichiers avec les pièces jointes de la tâche (défaut : name).')
        parser.add_argument('--files', choices=[tm.FILES_COPY, tm.FILES_LINK], default=tm.FILES_COPY,
                            help="copy : copie du fichier pour la tâche (défaut) ; link : lien vers le fichier COSOCollect.")
        parser.add_argument('--force', action='store_true',
                            help='Réécrire même un document déjà à jour de cet enregistrement (jamais une tâche validée).')
        parser.add_argument('--force-validated', action='store_true',
                            help='Remplacer aussi les données des tâches déjà VALIDÉES (la validation est conservée). '
                                 'Sans cette option, une tâche validée n\'est jamais modifiée.')
        parser.add_argument('--matches-only', action='store_true',
                            help='Afficher seulement les correspondances formulaire -> tâche et les écarts de champs.')
        parser.add_argument('--report', help='Fichier CSV du détail par tâche et village.')
        parser.add_argument('--status', action='append', default=[],
                            choices=[key for key, _label in CollectSubmission.STATUSES],
                            help="Statut des enregistrements à recopier (répétable) : submitted (envoyé), completed "
                                 "(rempli, non envoyé), draft (démarré). Défaut : submitted.")
        parser.add_argument('--accounts', action='append', default=[], choices=list(tm.ACCOUNT_CATEGORIES),
                            help="Comptes dont les enregistrements sont importés (répétable) : real_fc (vrais FC), "
                                 "real_ft (vrais FT), training (formation), develop (démonstration), others (comptes "
                                 "web sans facilitateur). Défaut : real_fc.")
        parser.add_argument('--apply', action='store_true', help='Écrire réellement (sinon simulation).')
        parser.add_argument('--undo', action='store_true',
                            help="Annuler le DERNIER import COSOCollect des tâches (état d'avant restauré ; une tâche "
                                 "modifiée depuis : --force ; validée : --force-validated). Limiter avec --form / "
                                 "--village. Simulation sans --apply.")
        # Page « Import vers les tâches » (call_command) : rappel d'avancement, absent de la ligne de commande.
        parser.add_argument('--progress-callback', dest='progress', default=None, help=argparse.SUPPRESS)

    # ------------------------------------------------------------------------------------------------------
    def handle(self, *args, **opts):
        project = Project.objects.filter(id=opts['project']).first()
        if not project:
            raise CommandError(f"Projet {opts['project']} introuvable.")
        cycles = Cycle.objects.filter(project=project)
        if opts.get('cycle'):
            cycle = cycles.filter(id=opts['cycle']).first()
        else:
            cycle = cycles.first() if cycles.count() == 1 else None
        if not cycle:
            raise CommandError('Cycle introuvable : préciser --cycle (%s).'
                               % ', '.join(f'{c.id}={c}' for c in cycles))

        forms = CollectForm.objects.exclude(status=CollectForm.STATUS_DRAFT)
        if opts['form']:
            forms = CollectForm.objects.filter(id__in=opts['form'])
        forms = list(forms.order_by('id'))

        forced = {}
        for raw in opts['map']:
            try:
                form_id, task_id = (int(x) for x in raw.split(':', 1))
            except ValueError:
                raise CommandError(f'--map invalide : {raw} (attendu FORM_ID:TASK_ID)')
            task = Task.objects.filter(id=task_id, project=project).select_related('activity').first()
            if not task:
                raise CommandError(f'--map {raw} : tâche {task_id} absente du projet.')
            if not task.cycles.filter(id=cycle.id).exists():
                raise CommandError(f'--map {raw} : tâche {task_id} absente du cycle {cycle} '
                                   f'(cycles de la tâche : {", ".join(str(c) for c in task.cycles.all()) or "aucun"}).')
            forced[form_id] = task
            # sans --form : un formulaire forcé est traité même s'il est en brouillon ; avec --form, --map ne fait que
            # déclarer la correspondance (seuls les formulaires de --form sont traités)
            if not opts['form'] and form_id not in {f.id for f in forms}:
                form = CollectForm.objects.filter(id=form_id).first()
                if not form:
                    raise CommandError(f'--map {raw} : formulaire {form_id} introuvable.')
                forms.append(form)

        # Formulaires réservés à d'AUTRES projets (« Projets liés » = projets choisis, sans celui-ci) : écartés —
        # des projets différents ont des tâches de même nom. Gardés seulement si demandés (--form / --map).
        explicit = set(opts['form']) | set(forced)
        other_project, kept_anyway = [], []
        for f in list(forms):
            if f.project_scope == CollectForm.PROJECTS_SELECTED and \
                    not f.projects.filter(id=project.id).exists():
                if f.id in explicit:
                    kept_anyway.append(f)
                else:
                    other_project.append(f)
                    forms.remove(f)

        dry_run = not opts['apply']
        w = self.stdout.write
        w(f"Projet : {project.name} (#{project.id}) — cycle : {cycle} (#{cycle.id})")
        w(f"CouchDB : {settings.NO_SQL_URL} — base : {settings.DATABASES['default'].get('HOST') or 'local'}"
          f"/{settings.DATABASES['default'].get('NAME')}")
        w(self.style.WARNING('SIMULATION (aucune écriture) — ajouter --apply pour écrire.') if dry_run
          else self.style.ERROR('ÉCRITURE RÉELLE dans les bases CouchDB des facilitateurs.'))
        w(f"Écraser les tâches déjà remplies : {'non' if opts['no_overwrite'] else 'oui'} — tâches validées : "
          f"{'REMPLACÉES (--force-validated)' if opts['force_validated'] else 'jamais modifiées'} — pièces jointes par "
          f"{opts['attachments_by']} — fichiers : {opts['files']}")
        statuses = list(dict.fromkeys(opts['status'])) or list(tm.DEFAULT_STATUSES)
        labels = dict(CollectSubmission.STATUSES)
        w(f"Enregistrements recopiés : {', '.join(f'{labels[s]} ({s})' for s in statuses)}")
        accounts = list(dict.fromkeys(opts.get('accounts') or [])) or list(tm.DEFAULT_ACCOUNTS)
        w(f"Comptes retenus (auteurs des enregistrements) : {', '.join(ACCOUNT_LABELS[a] + f' ({a})' for a in accounts)}\n")
        for f in other_project:
            w(self.style.WARNING(f"Écarté (réservé à d'autres projets) : [{f.id}] {f.title}"))
        for f in kept_anyway:
            w(self.style.WARNING(f"Réservé à d'autres projets mais demandé explicitement : [{f.id}] {f.title}"))
        if other_project or kept_anyway:
            w('')

        if opts['undo']:
            self._undo(project, cycle, forms if opts['form'] else None, dry_run, opts)
            return

        if opts['matches_only']:
            tasks = list(Task.objects.filter(project=project, cycles=cycle).select_related('activity'))
            matches = tm.match_forms_to_tasks(forms, tasks, forced, opts['min_score'])
            self._print_matches(matches, opts['attachments_by'])
            return

        result = tm.run(
            project, cycle, forms, forced=forced, min_score=opts['min_score'],
            overwrite=not opts['no_overwrite'], force=opts['force'], attachments_by=opts['attachments_by'],
            files_mode=opts['files'], dry_run=dry_run, only_adl_ids=set(opts['village']) or None,
            force_validated=opts['force_validated'], only_task_ids=set(opts['task']) or None,
            progress=opts.get('progress'), statuses=statuses, accounts=accounts,
        )
        self._print_matches(result['matches'], opts['attachments_by'])
        self._print_summary(result, dry_run)
        if opts.get('report'):
            self._write_report(opts['report'], result)
            w(f"\nRapport : {opts['report']}")

    # ------------------------------------------------------------------------------------------------------
    def _undo(self, project, cycle, forms, dry_run, opts):
        w = self.stdout.write
        w(self.style.MIGRATE_HEADING('Annulation du dernier import COSOCollect'))
        if forms is not None:
            w('  formulaires : ' + ', '.join(f'[{f.id}] {f.title}' for f in forms))
        result = tm.undo(project, cycle, forms, dry_run=dry_run, force=opts['force'],
                         force_validated=opts['force_validated'], only_adl_ids=set(opts['village']) or None,
                         only_task_ids=set(opts['task']) or None, progress=opts.get('progress'))
        for facilitator, err in result['errors']:
            w(self.style.WARNING(f"Base inaccessible : {facilitator.no_sql_db_name} ({err})"))
        labels = {
            'undone': 'restaurés', 'dry_run': 'à restaurer (simulation)',
            'skipped_modified': "ignorés (modifiés depuis l'import ; --force pour restaurer quand même)",
            'skipped_validated': 'ignorés (validés ; --force-validated)',
            'no_backup': "sans sauvegarde (importés avant l'ajout de --undo)", 'error': 'erreurs',
        }
        counts = Counter(o.status for o in result['outcomes'])
        if not counts:
            w('  aucun document importé à annuler')
        for status, n in counts.items():
            style = self.style.ERROR if status == 'error' else self.style.SUCCESS
            w(style(f"  {labels.get(status, status)} : {n}"))
        for o in result['outcomes']:
            if o.status == 'error':
                w(self.style.ERROR(f"  ! tâche #{o.task_id} village {o.adl_id} {o.ref.db_name} : {o.detail}"))

    def _print_matches(self, matches, attachments_by):
        w = self.stdout.write
        w(self.style.MIGRATE_HEADING('Formulaires -> tâches'))
        for m in matches:
            head = f"  [{m.form.id}] {m.form.title}"
            if m.task:
                style = self.style.SUCCESS if m.method in ('exact', 'forced') else self.style.WARNING
                w(style(f"{head}\n      -> tâche #{m.task.id} {tm.task_label(m.task)} ({m.method}, {m.score:.2f})"))
                diff = tm.compare_fields(m.form.form, m.task.form, m.task.attachments, attachments_by)
                w(f"      champs recopiés : {len(diff['copied'])}")
                for label, key in (('absents de COSOCollect', 'task_missing'),
                                   ('COSOCollect non utilisés', 'collect_unused'),
                                   ('types différents', 'type_diff'),
                                   ('choix absents de la tâche', 'enum_diff'),
                                   ('fichiers sans pièce jointe', 'attachments_unmatched')):
                    if diff[key]:
                        w(self.style.WARNING(f"      {label} : {', '.join(diff[key])}"))
                for src, dst in diff['attachments']:
                    w(f"      fichier « {src} » -> pièce jointe « {dst} »")
            else:
                why = {'other_activity': ' — tâche proche mais sous une AUTRE activité : --map FORM:TASK si voulu',
                       'ambiguous': ' — plusieurs tâches possibles : --map FORM:TASK'}.get(m.method, '')
                w(self.style.ERROR(f"{head}\n      -> aucune tâche ({m.method}, meilleur {m.score:.2f}){why}"))
                for score, t in m.candidates[:3]:
                    w(f"         ? #{t.id} {tm.task_label(t)} ({score:.2f})")
        w('')

    def _print_summary(self, result, dry_run):
        w = self.stdout.write
        index = result['index']
        for facilitator, err in index.errors:
            w(self.style.WARNING(f"Base inaccessible : {facilitator.no_sql_db_name} ({err})"))
        items = result['items']
        w(self.style.MIGRATE_HEADING('Résultat'))
        w(f"  tâches x villages à remplir : {len(items)}")
        multi = [i for i in items if len(i.refs) > 1]
        if multi:
            w(self.style.WARNING(f"  dont {len(multi)} présents chez plusieurs facilitateurs (tous écrits)"))
        competing = sum(i.competing for i in items)
        if competing:
            w(f"  enregistrements plus anciens écartés (le plus récent gardé) : {competing}")
        counts = Counter(o.status for o in result['outcomes'])
        labels = {
            'dry_run': 'à écrire (simulation)', 'written': 'écrits', 'unchanged': 'déjà à jour',
            'skipped_filled': 'ignorés (tâche déjà remplie, --no-overwrite)',
            'skipped_validated': 'ignorés (tâche déjà validée ; --force-validated pour remplacer)',
            'no_common_fields': 'NON écrits : aucun champ commun avec la tâche (rapprochement à vérifier)',
            'missing_doc': 'document introuvable',
            'error': 'erreurs',
        }
        for status, n in counts.items():
            style = self.style.ERROR if status in ('error', 'missing_doc', 'no_common_fields') else self.style.SUCCESS
            w(style(f"  {labels.get(status, status)} : {n}"))
        if dry_run:
            flags = Counter(f for o in result['outcomes'] if o.status == 'dry_run' for f in o.detail.split(',') if f)
            if flags['filled']:
                w(self.style.WARNING(f"  dont déjà remplis (seraient écrasés) : {flags['filled']}"))
            if flags['validated']:  # seulement avec --force-validated (sinon : skipped_validated)
                w(self.style.WARNING(f"  dont déjà VALIDÉS (données remplacées, validation conservée) : "
                                     f"{flags['validated']}"))
        reasons = Counter(p.reason.split(':')[0] for p in result['pending'])
        if reasons:
            w(self.style.WARNING('  en attente (à relancer plus tard) :'))
            names = {'no_task_doc': 'village sans tâche distribuée (pas de facilitateur affecté ?)',
                     'no_location': 'enregistrement sans village ni canton',
                     'village_unresolved': 'village introuvable (ni identifiant ni nom connu dans le canton)',
                     'canton_unresolved': 'canton introuvable (nom inconnu ou porté par plusieurs cantons)',
                     'account_excluded': 'auteur hors des comptes retenus (--accounts)'}
            for reason, n in reasons.items():
                w(self.style.WARNING(f"    {names.get(reason, reason)} : {n}"))
        warned = [o for o in result['outcomes'] if o.warnings]
        if warned:
            w(self.style.WARNING(f"  avec avertissements (voir le rapport --report) : {len(warned)}"))
            for o in warned[:10]:
                w(self.style.WARNING(f"    tâche #{o.item.task.id} village {o.item.adl_id} : {' ; '.join(o.warnings[:3])}"))
        for o in result['outcomes']:
            if o.status in ('error', 'missing_doc'):
                w(self.style.ERROR(f"  ! tâche #{o.item.task.id} village {o.item.adl_id} {o.ref.db_name} : {o.detail}"))

    def _write_report(self, path, result):
        geo = result['geo']
        with open(path, 'w', newline='', encoding='utf-8-sig') as fh:
            out = csv.writer(fh, delimiter=';')
            out.writerow(['statut', 'formulaire', 'tache_id', 'tache', 'village_id', 'village', 'niveau_source',
                          'source_id', 'source', 'enregistrement', 'envoye_le', 'facilitateur', 'base',
                          'document', 'champs', 'pieces_jointes', 'detail', 'avertissements'])
            for o in result['outcomes']:
                i = o.item
                out.writerow([
                    o.status, i.form.title, i.task.id, tm.task_label(i.task), i.adl_id, geo.name(i.adl_id),
                    i.level, i.source_id, geo.name(i.source_id) if i.source_id else '', i.submission.uuid,
                    i.submission.submitted_at, o.ref.facilitator.name or o.ref.facilitator.username, o.ref.db_name,
                    o.ref.doc_id, len(o.fields), ', '.join(o.attachments), o.detail, ' ; '.join(o.warnings),
                ])
            for p in result['pending']:
                out.writerow([
                    'en_attente', p.form.title, p.task.id, tm.task_label(p.task), '', '', p.level, p.source_id or '',
                    geo.name(p.source_id) if p.source_id else '', p.submission.uuid, p.submission.submitted_at,
                    '', '', '', '', '', p.reason, '',
                ])
