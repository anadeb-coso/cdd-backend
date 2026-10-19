from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('coso_collect', '0003_collectformadmin_rights'),
    ]

    operations = [
        migrations.AddField(
            model_name='collectform',
            name='single_submission',
            field=models.BooleanField(default=False, verbose_name='Only one record per person'),
        ),
    ]
