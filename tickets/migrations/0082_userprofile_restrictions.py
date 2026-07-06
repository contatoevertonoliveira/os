# Migration to add functionality restrictions to UserProfile

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0081_userprofile_ai_chat_enabled'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='can_view_tickets',
            field=models.BooleanField(default=True, verbose_name='Visualizar Ordens de Serviço'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='can_create_tickets',
            field=models.BooleanField(default=True, verbose_name='Criar Ordens de Serviço'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='can_edit_tickets',
            field=models.BooleanField(default=True, verbose_name='Editar Ordens de Serviço'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='can_delete_tickets',
            field=models.BooleanField(default=True, verbose_name='Deletar Ordens de Serviço'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='can_view_checklists',
            field=models.BooleanField(default=True, verbose_name='Visualizar Checklists'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='can_create_checklists',
            field=models.BooleanField(default=True, verbose_name='Criar Checklists'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='can_view_reports',
            field=models.BooleanField(default=True, verbose_name='Visualizar Relatórios'),
        ),
    ]
