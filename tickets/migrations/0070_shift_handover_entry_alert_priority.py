from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0069_shift_handover_entry_alerts'),
    ]

    operations = [
        migrations.AddField(
            model_name='shifthandoverentryalert',
            name='priority',
            field=models.CharField(choices=[('high', 'Alta'), ('medium', 'Média'), ('low', 'Baixa')], default='medium', max_length=10, verbose_name='Prioridade'),
        ),
    ]

