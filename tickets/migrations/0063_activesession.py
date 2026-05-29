from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0062_alter_ticketstatus_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='ActiveSession',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_key', models.CharField(max_length=40, unique=True, verbose_name='Chave da Sessão')),
                ('ip_address', models.CharField(max_length=45, verbose_name='Endereço IP')),
                ('user_agent', models.TextField(blank=True, null=True, verbose_name='User Agent')),
                ('last_activity', models.DateTimeField(auto_now=True, verbose_name='Última Atividade')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='active_sessions', to='auth.user', verbose_name='Usuário')),
            ],
            options={
                'verbose_name': 'Sessão Ativa',
                'verbose_name_plural': 'Sessões Ativas',
                'ordering': ['-last_activity'],
            },
        ),
    ]
