from django.db import migrations


def seed_missing_cadastro_pages(apps, schema_editor):
    AppPage = apps.get_model('tickets', 'AppPage')

    pages = [
        ('ordertype_list', 'Tipos de Chamados', 'ordertype_list', 'Cadastros', 55),
        ('problemtype_list', 'Tipos de Problema', 'problemtype_list', 'Cadastros', 56),
        ('responsible_list', 'Responsáveis', 'responsible_list', 'Cadastros', 57),
    ]

    for code, name, url_name, group, order in pages:
        AppPage.objects.update_or_create(
            url_name=url_name,
            defaults={
                'code': code,
                'name': name,
                'group': group,
                'order': order,
                'is_enabled': True,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0051_pdf_report_permissions'),
    ]

    operations = [
        migrations.RunPython(seed_missing_cadastro_pages, migrations.RunPython.noop),
    ]
