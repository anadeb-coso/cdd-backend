# Generated by Django 4.0.4 on 2022-11-01 19:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0002_facilitator_test_mode'),
    ]

    operations = [
        migrations.RenameField(
            model_name='facilitator',
            old_name='test_mode',
            new_name='develop_mode',
        ),
        migrations.AddField(
            model_name='facilitator',
            name='training_mode',
            field=models.BooleanField(default=False, verbose_name='test mode'),
        ),
    ]