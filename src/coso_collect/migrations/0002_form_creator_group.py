from django.db import migrations

# Groupe autorisé à créer des formulaires COSOCollect (avec les superutilisateurs et le groupe Admin,
# cf. coso_collect/access.py) ; attribuable depuis la page Utilisateurs du dashboard.
FORM_CREATOR_GROUP = 'FormCreator'


def create_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.get_or_create(name=FORM_CREATOR_GROUP)


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('coso_collect', '0001_initial'),
    ]

    # Retour arrière : le groupe est conservé (il peut déjà avoir des membres).
    operations = [
        migrations.RunPython(create_group, migrations.RunPython.noop),
    ]
