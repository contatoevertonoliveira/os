from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_created_by(apps, schema_editor):
    Ticket = apps.get_model("tickets", "Ticket")
    # Melhor esforço: para OS antigas, assume que "requester" era quem abriu a OS.
    Ticket.objects.filter(created_by__isnull=True, requester__isnull=False).update(
        created_by=models.F("requester")
    )


def noop_reverse(apps, schema_editor):
    # Não desfaz backfill
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("tickets", "0063_activesession"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticket",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_tickets",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Criado por",
            ),
        ),
        migrations.RunPython(backfill_created_by, noop_reverse),
    ]

