from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('process_manager', '0044_aggregatedstatus_indexes'),
        ('coso_collect', '0005_collectform_rank'),
    ]

    operations = [
        migrations.AddField(
            model_name='collectform',
            name='project_scope',
            field=models.CharField(choices=[('none', 'No project: open to people linked to no project too'), ('all', 'All the projects: only people linked to at least one project'), ('selected', 'Only the projects selected')], default='none', max_length=20, verbose_name='Linked projects'),
        ),
        migrations.AddField(
            model_name='collectform',
            name='projects',
            field=models.ManyToManyField(blank=True, related_name='collect_forms', to='process_manager.Project', verbose_name='Projects'),
        ),
    ]
