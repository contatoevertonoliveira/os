from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0068_shift_handover_and_shift_settings'),
    ]

    operations = [
        migrations.CreateModel(
            name='ShiftHandoverEntryAlert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('acknowledged_at', models.DateTimeField(blank=True, null=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='handover_alerts_created', to=settings.AUTH_USER_MODEL, verbose_name='Criado por')),
                ('entry', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='alerts', to='tickets.shifthandoverentry', verbose_name='Anotação')),
                ('target_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='handover_alerts', to=settings.AUTH_USER_MODEL, verbose_name='Usuário alvo')),
            ],
            options={
                'verbose_name': 'Alerta de Anotação (Turno)',
                'verbose_name_plural': 'Alertas de Anotação (Turno)',
                'ordering': ['-created_at', '-id'],
                'unique_together': {('entry', 'target_user')},
            },
        ),
    ]

