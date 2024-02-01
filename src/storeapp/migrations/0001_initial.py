# Generated by Django 4.0.4 on 2024-01-31 11:12

from django.db import migrations, models
import django.db.models.deletion
import storeapp.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='StoreProject',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='Project Name')),
                ('package', models.CharField(blank=True, max_length=100, null=True, unique=True, verbose_name='Project Name')),
                ('description', models.TextField(verbose_name='Project Description')),
            ],
        ),
        migrations.CreateModel(
            name='StoreApp',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version_code', models.IntegerField(unique=True, verbose_name='Version Code')),
                ('app_version', models.CharField(max_length=45, verbose_name='Version')),
                ('apk', models.ImageField(upload_to=storeapp.models.app_path, verbose_name='APK')),
                ('app_code', models.IntegerField(unique=True, verbose_name='App Code')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='storeapp.storeproject', verbose_name='Project')),
            ],
        ),
    ]