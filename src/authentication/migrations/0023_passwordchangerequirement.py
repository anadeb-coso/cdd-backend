from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0022_user_localities_history'),
    ]

    operations = [
        migrations.CreateModel(
            name='PasswordChangeRequirement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.CharField(blank=True, db_index=True, max_length=254, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('changed_at', models.DateTimeField(blank=True, null=True)),
                ('changed_on', models.CharField(blank=True, max_length=30, null=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('facilitator', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='authentication.facilitator')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Password change requirement',
                'verbose_name_plural': 'Password change requirements',
                'db_table': 'authentication_passwordchangerequirement',
            },
        ),
        migrations.AlterField(
            model_name='localityhistory',
            name='source',
            field=models.CharField(choices=[('localities_page', 'Localities page'), ('facilitator_form', 'Facilitator form'), ('facilitator_creation', 'Facilitator creation'), ('user_localities_page', 'User localities page'), ('grm', 'GRM'), ('mis_import', 'Imported from the MIS assignments'), ('initial_state', 'Initial state'), ('couchdb_rebuild', 'Rebuilt from CouchDB'), ('excel_import', 'Excel import')], max_length=30),
        ),
    ]
