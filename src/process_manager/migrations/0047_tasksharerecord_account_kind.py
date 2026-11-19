# Partage entre villages sièges : le registre distingue le type de compte (vrai FC / formation / démonstration),
# le partage ne se faisant qu'entre comptes du même type (14/11/2026).

from django.db import migrations, models


def fill_account_kind(apps, schema_editor):
    """Type de compte des lignes existantes = celui du facilitateur qui les tient (aucun facilitateur : vrai FC)."""
    TaskShareRecord = apps.get_model('process_manager', 'TaskShareRecord')
    for record in TaskShareRecord.objects.exclude(facilitator=None).select_related('facilitator'):
        fac = record.facilitator
        training, develop = bool(fac.training_mode), bool(fac.develop_mode)
        if (training, develop) != (False, False):
            TaskShareRecord.objects.filter(pk=record.pk).update(training_mode=training, develop_mode=develop)


class Migration(migrations.Migration):

    dependencies = [
        ('process_manager', '0046_tasksyncrun'),
    ]

    operations = [
        migrations.AddField(
            model_name='tasksharerecord',
            name='training_mode',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='tasksharerecord',
            name='develop_mode',
            field=models.BooleanField(default=False),
        ),
        # Contrainte d'abord, données ensuite (pas d'ALTER après des UPDATE dans la même transaction :
        # piège PostgreSQL « pending trigger events »).
        migrations.AlterUniqueTogether(
            name='tasksharerecord',
            unique_together={('task', 'project', 'cycle', 'administrative_level_id', 'training_mode', 'develop_mode')},
        ),
        migrations.RunPython(fill_account_kind, migrations.RunPython.noop),
    ]
