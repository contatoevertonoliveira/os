from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0058_remove_duplicate_claro_hub_clients'),
    ]

    operations = [
        migrations.CreateModel(
            name='TicketStatus',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.SlugField(max_length=50, unique=True, verbose_name='Código')),
                ('name', models.CharField(max_length=100, verbose_name='Nome do Status')),
                ('color', models.CharField(default='secondary', help_text='Ex: primary, warning, success, danger, info', max_length=20, verbose_name='Cor (Bootstrap)')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='Ordem')),
                ('is_active', models.BooleanField(default=True, verbose_name='Ativo')),
            ],
            options={
                'verbose_name': 'Status de OS',
                'verbose_name_plural': 'Status de OS',
                'ordering': ['order', 'name'],
            },
        ),
        migrations.RunSQL(
            sql="""
                INSERT INTO tickets_ticketstatus (code, name, color, "order", is_active)
                VALUES
                    ('open', 'Em Aberto', 'primary', 1, TRUE),
                    ('in_progress', 'Em Andamento', 'warning', 2, TRUE),
                    ('pending', 'Aguardando Aprovação', 'info', 3, TRUE),
                    ('finished', 'Finalizado', 'success', 4, TRUE),
                    ('canceled', 'Cancelado', 'danger', 5, TRUE)
                ON CONFLICT (code) DO NOTHING;
            """,
            reverse_sql="DELETE FROM tickets_ticketstatus WHERE code IN ('open','in_progress','pending','finished','canceled');"
        ),
    ]
