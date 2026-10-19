"""COSOCollect : formulaires de collecte créés sur le Web DCC (même format de champs que les
formulaires de tâche du « Cycle d'investissement », cf. dashboard/process_manager/tasks/form_design.py),
remplis sur le mobile (hors connexion, WatermelonDB) ou sur le web.

- `CollectForm` : le formulaire (pages au format `Task.form`) + son titre combiné (`title_template`).
- `CollectSubmission` : un objet de données (une saisie). `uuid` est généré par le client (mobile ou
  web) pour que la synchronisation soit idempotente.
- `CollectAttachment` : photo / document joint à une saisie (champ de type `photo` ou `file`).
"""
import os
import time
import uuid

from django.contrib.auth.models import Group, User
from django.db import models
from django.utils.translation import gettext_lazy as _

from authentication.models import Facilitator


class CollectForm(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_CLOSED = 'closed'
    STATUSES = [
        (STATUS_DRAFT, _('Draft')),
        (STATUS_PUBLISHED, _('Published')),
        (STATUS_CLOSED, _('Closed')),
    ]

    ACCESS_ALL = 'all'
    ACCESS_RESTRICTED = 'restricted'
    ACCESS_SCOPES = [
        (ACCESS_ALL, _('All connected users')),
        (ACCESS_RESTRICTED, _('Only the users, groups and facilitators selected')),
    ]

    uid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    title = models.CharField(max_length=255, verbose_name=_('Title'))
    description = models.TextField(blank=True, default='', verbose_name=_('Description'))
    # Pages au format stocké de Task.form ({options, page, rules?, calculate?, messages?, choicesFrom?}).
    form = models.JSONField(default=list, blank=True)
    # Titre combiné d'une saisie : {"parts": [{"type": "field"|"meta"|"text", ...}], "separator": "_",
    # "slugify": true}. Cf. coso_collect/titles.py.
    title_template = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUSES, default=STATUS_DRAFT, db_index=True,
                              verbose_name=_('Status'))
    # Incrémentée à chaque modification de `form` / `title_template` : le mobile recharge le formulaire
    # quand la version locale est dépassée.
    version = models.PositiveIntegerField(default=1)
    close_message = models.TextField(blank=True, default='', verbose_name=_('Message shown once closed'))
    # Un seul enregistrement par personne (comptes web + facilitateur de la même personne confondus) : une
    # fois le sien démarré, on le reprend au lieu d'en créer un autre. Par défaut : plusieurs.
    single_submission = models.BooleanField(default=False, verbose_name=_('Only one record per person'))

    access_scope = models.CharField(max_length=20, choices=ACCESS_SCOPES, default=ACCESS_ALL,
                                    verbose_name=_('Who can fill in this form'))
    allowed_users = models.ManyToManyField(User, blank=True, related_name='collect_forms_allowed',
                                           verbose_name=_('Allowed users'))
    allowed_groups = models.ManyToManyField(Group, blank=True, related_name='collect_forms_allowed',
                                            verbose_name=_('Allowed groups'))
    allowed_facilitators = models.ManyToManyField(Facilitator, blank=True, related_name='collect_forms_allowed',
                                                  verbose_name=_('Allowed facilitators'))
    # Administrateurs du formulaire (en plus de son créateur et des superutilisateurs), chacun avec les
    # droits que le créateur lui accorde (cf. CollectFormAdmin).
    admins = models.ManyToManyField(User, blank=True, through='CollectFormAdmin', related_name='collect_forms_administered',
                                    verbose_name=_('Administrators'))

    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='collect_forms_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = _('COSOCollect form')
        verbose_name_plural = _('COSOCollect forms')

    def __str__(self):
        return self.title

    @property
    def is_open(self):
        return self.status == self.STATUS_PUBLISHED


class CollectFormAdmin(models.Model):
    """Administrateur d'un formulaire et droits accordés par le créateur. Le créateur et les
    superutilisateurs ont tous les droits ; seuls eux gèrent la liste des administrateurs."""

    # (code, libellé) — `can_<code>` est le champ booléen correspondant.
    RIGHTS = [
        ('view_data', _('Read all the data')),
        ('export', _('Export the data')),
        ('edit_form', _('Modify the form')),
        ('publish', _('Publish the form')),
        ('close', _('Close the form')),
        ('reopen_form', _('Reopen the collection')),
        ('reopen_records', _('Reopen sent records')),
        ('edit_data', _('Modify the records (data objects)')),
        ('delete_records', _('Delete records')),
        ('delete_form', _('Delete the form')),
    ]

    form = models.ForeignKey(CollectForm, on_delete=models.CASCADE, related_name='admin_rights')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='collect_form_rights')
    can_view_data = models.BooleanField(default=True, verbose_name=_('Read all the data'))
    can_export = models.BooleanField(default=False, verbose_name=_('Export the data'))
    can_edit_form = models.BooleanField(default=False, verbose_name=_('Modify the form'))
    can_publish = models.BooleanField(default=False, verbose_name=_('Publish the form'))
    can_close = models.BooleanField(default=False, verbose_name=_('Close the form'))
    can_reopen_form = models.BooleanField(default=False, verbose_name=_('Reopen the collection'))
    can_reopen_records = models.BooleanField(default=False, verbose_name=_('Reopen sent records'))
    can_edit_data = models.BooleanField(default=False, verbose_name=_('Modify the records (data objects)'))
    can_delete_records = models.BooleanField(default=False, verbose_name=_('Delete records'))
    can_delete_form = models.BooleanField(default=False, verbose_name=_('Delete the form'))
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('form', 'user')]
        ordering = ['added_at']

    def __str__(self):
        return f'{self.user} — {self.form}'

    def has(self, code):
        return bool(getattr(self, f'can_{code}', False))

    def granted(self):
        return [code for code, _label in self.RIGHTS if self.has(code)]


class CollectSubmission(models.Model):
    STATUS_DRAFT = 'draft'          # démarré
    STATUS_COMPLETED = 'completed'  # rempli jusqu'au bout, pas encore envoyé
    STATUS_SUBMITTED = 'submitted'  # envoyé : verrouillé tant qu'un administrateur ne le rouvre pas
    STATUSES = [
        (STATUS_DRAFT, _('Started')),
        (STATUS_COMPLETED, _('Filled in')),
        (STATUS_SUBMITTED, _('Sent')),
    ]

    SOURCE_WEB = 'web'
    SOURCE_MOBILE = 'mobile'
    SOURCES = [(SOURCE_WEB, 'Web'), (SOURCE_MOBILE, 'Mobile')]

    form = models.ForeignKey(CollectForm, on_delete=models.CASCADE, related_name='submissions')
    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    form_version = models.PositiveIntegerField(default=1)
    # Réponses par page (même forme que `form_response` d'une tâche).
    data = models.JSONField(default=list, blank=True)
    title = models.CharField(max_length=500, blank=True, default='', db_index=True)
    status = models.CharField(max_length=20, choices=STATUSES, default=STATUS_DRAFT, db_index=True)
    # Saisie envoyée rouverte à la modification par un administrateur ; repasse à False au renvoi.
    editable = models.BooleanField(default=False)
    source = models.CharField(max_length=10, choices=SOURCES, default=SOURCE_MOBILE)

    # Auteur : compte web OU compte facilitateur (cf. authentication/identity.py, règle « même personne »).
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name='collect_submissions')
    facilitator = models.ForeignKey(Facilitator, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='collect_submissions')

    started_at = models.DateTimeField(null=True, blank=True)       # création sur l'appareil
    # Date d'enregistrement telle que saisie sur l'appareil (avec son fuseau), base du titre combiné.
    started_at_local = models.CharField(max_length=40, blank=True, default='')
    submitted_at = models.DateTimeField(null=True, blank=True)
    client_updated_at = models.DateTimeField(null=True, blank=True)
    reopened_at = models.DateTimeField(null=True, blank=True)
    reopened_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    history = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['form', 'status']),
            models.Index(fields=['form', 'created_at']),
        ]

    def __str__(self):
        return self.title or str(self.uuid)

    @property
    def is_locked(self):
        return self.status == self.STATUS_SUBMITTED and not self.editable

    @property
    def author_name(self):
        if self.facilitator_id and self.facilitator:
            if self.facilitator.user_id and self.facilitator.user:
                return f"{self.facilitator.user.last_name} {self.facilitator.user.first_name}" or self.facilitator.user.username
            return self.facilitator.name or self.facilitator.username
        if self.user_id and self.user:
            return f"{self.user.last_name} {self.user.first_name}" or self.user.username
        return ''


def attachment_upload_to(instance, filename):
    base, ext = os.path.splitext(os.path.basename(filename or 'fichier'))
    return 'coso_collect/{}/{}/{}-{}{}'.format(
        instance.form.uid, instance.submission_uuid, int(time.time() * 1000), base[:80], ext[:12],
    )


class CollectAttachment(models.Model):
    form = models.ForeignKey(CollectForm, on_delete=models.CASCADE, related_name='attachments')
    # Rattachée dès que la saisie arrive au serveur (le fichier peut être envoyé avant elle).
    submission = models.ForeignKey(CollectSubmission, null=True, blank=True, on_delete=models.CASCADE,
                                   related_name='attachments')
    submission_uuid = models.UUIDField(db_index=True)
    field_path = models.CharField(max_length=500, blank=True, default='')
    file = models.FileField(upload_to=attachment_upload_to, max_length=500)
    name = models.CharField(max_length=255, blank=True, default='')
    mime_type = models.CharField(max_length=150, blank=True, default='')
    size = models.PositiveBigIntegerField(default=0)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    facilitator = models.ForeignKey(Facilitator, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return self.name

    @property
    def is_image(self):
        return (self.mime_type or '').startswith('image/')
