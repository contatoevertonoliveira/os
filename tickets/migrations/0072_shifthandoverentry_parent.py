from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0071_userprofile_ticket_toast_state"),
    ]

    operations = [
        migrations.AddField(
            model_name="shifthandoverentry",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="replies",
                to="tickets.shifthandoverentry",
                verbose_name="Resposta para",
            ),
        ),
    ]

