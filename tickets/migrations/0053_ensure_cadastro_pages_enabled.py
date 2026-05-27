from django.db import migrations


def ensure_all_cadastro_pages_enabled(apps, schema_editor):
    AppPage = apps.get_model('tickets', 'AppPage')

    # Enable all cadastro pages
    cadastro_url_names = [
        'client_list',
        'equipment_list',
        'ordertype_list',
        'problemtype_list',
        'technician_list',
        'responsible_list',
        'travel_list',
        'system_list',
        'user_list',
    ]

    AppPage.objects.filter(url_name__in=cadastro_url_names).update(is_enabled=True)


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0052_add_missing_cadastro_pages'),
    ]

    operations = [
        migrations.RunPython(ensure_all_cadastro_pages_enabled, migrations.RunPython.noop),
    ]
