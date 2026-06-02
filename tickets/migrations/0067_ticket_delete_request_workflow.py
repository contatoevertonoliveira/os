from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('tickets', '0066_add_ticket_delete_permission'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='delete_status',
            field=models.CharField(
                choices=[('none', 'Nenhuma'), ('pending', 'Solicitada'), ('rejected', 'Rejeitada')],
                default='none',
                max_length=20,
                verbose_name='Status de Exclusão',
            ),
        ),
        migrations.AddField(
            model_name='ticket',
            name='delete_requested_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='ticket_delete_requests',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Exclusão solicitada por',
            ),
        ),
        migrations.AddField(
            model_name='ticket',
            name='delete_requested_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Exclusão solicitada em'),
        ),
        migrations.AddField(
            model_name='ticket',
            name='delete_request_reason',
            field=models.CharField(blank=True, default='', max_length=250, verbose_name='Motivo da solicitação (opcional)'),
        ),
        migrations.AddField(
            model_name='ticket',
            name='delete_decided_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='ticket_delete_decisions',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Solicitação decidida por',
            ),
        ),
        migrations.AddField(
            model_name='ticket',
            name='delete_decided_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Solicitação decidida em'),
        ),
        migrations.AddField(
            model_name='ticket',
            name='delete_decision_note',
            field=models.CharField(blank=True, default='', max_length=250, verbose_name='Observação da decisão (opcional)'),
        ),
    ]

