from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0044_checklist_item_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='requesters',
            field=models.ManyToManyField(blank=True, related_name='requested_tickets_multi', to=settings.AUTH_USER_MODEL, verbose_name='Solicitantes'),
        ),
    ]

