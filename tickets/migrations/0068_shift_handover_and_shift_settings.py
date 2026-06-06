from django.db import migrations, models
import datetime
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0067_ticket_delete_request_workflow'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsettings',
            name='day_shift_start',
            field=models.TimeField(default=datetime.time(8, 0), verbose_name='Início do turno diurno'),
        ),
        migrations.AddField(
            model_name='systemsettings',
            name='day_shift_end',
            field=models.TimeField(default=datetime.time(20, 0), verbose_name='Fim do turno diurno'),
        ),
        migrations.AddField(
            model_name='systemsettings',
            name='enable_night_shift',
            field=models.BooleanField(default=False, verbose_name='Ativar turno noturno'),
        ),
        migrations.AddField(
            model_name='systemsettings',
            name='night_shift_start',
            field=models.TimeField(default=datetime.time(20, 0), verbose_name='Início do turno noturno'),
        ),
        migrations.AddField(
            model_name='systemsettings',
            name='night_shift_end',
            field=models.TimeField(default=datetime.time(8, 0), verbose_name='Fim do turno noturno'),
        ),
        migrations.CreateModel(
            name='ShiftHandover',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('shift_date', models.DateField(verbose_name='Data do turno')),
                ('shift_type', models.CharField(choices=[('day', 'Diurno'), ('night', 'Noturno')], default='day', max_length=10, verbose_name='Tipo de turno')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Passagem de Turno',
                'verbose_name_plural': 'Passagens de Turno',
                'ordering': ['-shift_date', '-id'],
                'unique_together': {('shift_date', 'shift_type')},
            },
        ),
        migrations.CreateModel(
            name='ShiftHandoverEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField(verbose_name='Texto')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Criado por')),
                ('handover', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='entries', to='tickets.shifthandover', verbose_name='Turno')),
            ],
            options={
                'verbose_name': 'Anotação do Turno',
                'verbose_name_plural': 'Anotações do Turno',
                'ordering': ['-created_at', '-id'],
            },
        ),
    ]

