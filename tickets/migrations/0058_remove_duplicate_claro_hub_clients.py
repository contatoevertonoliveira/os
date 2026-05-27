from django.db import migrations


def remove_duplicate_hub_clients(apps, schema_editor):
    """Remove client records that are duplicates of Claro hubs."""
    Client = apps.get_model('tickets', 'Client')
    Ticket = apps.get_model('tickets', 'Ticket')
    TechnicianTravel = apps.get_model('tickets', 'TechnicianTravel')
    ChecklistTemplate = apps.get_model('tickets', 'ChecklistTemplate')

    duplicate_names = ['SMJAB50', 'SMLAP14', 'SMMOO62', 'SMMRB50', 'SPO0VG', 'SPO4JA']

    for name in duplicate_names:
        try:
            client = Client.objects.get(name=name)
            # Safety check: ensure no tickets, travels, or templates reference this client
            has_tickets = Ticket.objects.filter(client=client).exists()
            has_travels = TechnicianTravel.objects.filter(client=client).exists()
            has_templates = ChecklistTemplate.objects.filter(client=client).exists()

            if not has_tickets and not has_travels and not has_templates:
                client.delete()
                print(f"Removed duplicate client: {name}")
            else:
                print(f"SKIPPED {name}: still has references (tickets={has_tickets}, travels={has_travels}, templates={has_templates})")
        except Client.DoesNotExist:
            print(f"Client {name} not found, skipping")


def reverse_func(apps, schema_editor):
    """Reverse is a no-op - we can't restore deleted clients automatically."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0057_add_contact_pages'),
    ]

    operations = [
        migrations.RunPython(remove_duplicate_hub_clients, reverse_func),
    ]
