"""Droits par administrateur d'un formulaire : la relation `CollectForm.admins` passe par le modèle
`CollectFormAdmin` (un booléen par droit). Les administrateurs déjà désignés reçoivent tous les droits,
pour ne rien leur retirer de ce qu'ils pouvaient faire jusqu'ici."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

RIGHT_FIELDS = (
    'can_view_data', 'can_export', 'can_edit_form', 'can_publish', 'can_close', 'can_reopen_form',
    'can_reopen_records', 'can_edit_data', 'can_delete_records', 'can_delete_form',
)


def copy_existing_admins(apps, schema_editor):
    CollectForm = apps.get_model('coso_collect', 'CollectForm')
    CollectFormAdmin = apps.get_model('coso_collect', 'CollectFormAdmin')
    rows = CollectForm.admins.through.objects.all()
    CollectFormAdmin.objects.bulk_create([
        CollectFormAdmin(form_id=row.collectform_id, user_id=row.user_id, **{f: True for f in RIGHT_FIELDS})
        for row in rows
    ])


def restore_admins(apps, schema_editor):
    CollectForm = apps.get_model('coso_collect', 'CollectForm')
    CollectFormAdmin = apps.get_model('coso_collect', 'CollectFormAdmin')
    through = CollectForm.admins.through
    through.objects.bulk_create([
        through(collectform_id=row.form_id, user_id=row.user_id) for row in CollectFormAdmin.objects.all()
    ])


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('coso_collect', '0002_form_creator_group'),
    ]

    operations = [
        migrations.CreateModel(
            name='CollectFormAdmin',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('can_view_data', models.BooleanField(default=True, verbose_name='Read all the data')),
                ('can_export', models.BooleanField(default=False, verbose_name='Export the data')),
                ('can_edit_form', models.BooleanField(default=False, verbose_name='Modify the form')),
                ('can_publish', models.BooleanField(default=False, verbose_name='Publish the form')),
                ('can_close', models.BooleanField(default=False, verbose_name='Close the form')),
                ('can_reopen_form', models.BooleanField(default=False, verbose_name='Reopen the collection')),
                ('can_reopen_records', models.BooleanField(default=False, verbose_name='Reopen sent records')),
                ('can_edit_data', models.BooleanField(default=False, verbose_name='Modify the records (data objects)')),
                ('can_delete_records', models.BooleanField(default=False, verbose_name='Delete records')),
                ('can_delete_form', models.BooleanField(default=False, verbose_name='Delete the form')),
                ('added_at', models.DateTimeField(auto_now_add=True)),
                ('form', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='admin_rights',
                                           to='coso_collect.collectform')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                           related_name='collect_form_rights', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['added_at'],
                'unique_together': {('form', 'user')},
            },
        ),
        migrations.RunPython(copy_existing_admins, restore_admins),
        migrations.RemoveField(model_name='collectform', name='admins'),
        migrations.AddField(
            model_name='collectform',
            name='admins',
            field=models.ManyToManyField(blank=True, related_name='collect_forms_administered',
                                         through='coso_collect.CollectFormAdmin', to=settings.AUTH_USER_MODEL,
                                         verbose_name='Administrators'),
        ),
    ]
