from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0070_shift_handover_entry_alert_priority"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="ticket_toast_state_date",
            field=models.DateField(blank=True, null=True, verbose_name="Data do estado de toast (OS)"),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="ticket_toast_morning_shown",
            field=models.BooleanField(default=False, verbose_name="Toast (OS) mostrado - primeiro acesso do dia"),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="ticket_toast_end_shown",
            field=models.BooleanField(default=False, verbose_name="Toast (OS) mostrado - fim do turno"),
        ),
    ]

