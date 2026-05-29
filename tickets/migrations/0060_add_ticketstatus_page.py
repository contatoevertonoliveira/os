from django.db import migrations

def add_ticketstatus_page(apps, schema_editor):
    AppPage = apps.get_model('tickets', 'AppPage')
    AppPage.objects.get_or_create(
        code='ticketstatus_list',
        defaults=dict(
            name='Status de OS',
            url_name='ticketstatus_list',
            group='Cadastros',
            order=53.5,
            is_enabled=True,
        )
    )

def remove_ticketstatus_page(apps, schema_editor):
    AppPage = apps.get_model('tickets', 'AppPage')
    AppPage.objects.filter(code='ticketstatus_list').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0059_ticketstatus'),
    ]

    operations = [
        migrations.RunPython(add_ticketstatus_page, remove_ticketstatus_page),
    ]
