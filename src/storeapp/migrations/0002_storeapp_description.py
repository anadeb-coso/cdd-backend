# Generated by Django 4.0.4 on 2024-01-31 11:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('storeapp', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='storeapp',
            name='description',
            field=models.TextField(default=None, verbose_name='App Description'),
            preserve_default=False,
        ),
    ]
