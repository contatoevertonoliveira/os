from django.db import migrations


def seed_contact_pages(apps, schema_editor):
    AppPage = apps.get_model('tickets', 'AppPage')
    pages = [
        ('contactclient_list', 'Contatos (Clientes)', 'contactclient_list', 'Cadastros', 58),
        ('contactjumper_list', 'Contatos (JumperFour)', 'contactjumper_list', 'Cadastros', 59),
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
        ('tickets', '0056_contactclient_contactjumper_ticket_contact_split'),
    ]

    operations = [
        migrations.RunPython(seed_contact_pages, migrations.RunPython.noop),
    ]
