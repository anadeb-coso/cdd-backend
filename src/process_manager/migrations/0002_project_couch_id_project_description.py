# Generated by Django 4.0.4 on 2022-10-13 13:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('process_manager', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='couch_id',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='project',
            name='description',
            field=models.TextField(default=''),
            preserve_default=False,
        ),
    ]
