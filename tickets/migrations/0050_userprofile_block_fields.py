from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0049_microsoft_graph_token_client_sync_state'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='blocked_reason',
            field=models.CharField(blank=True, max_length=200, null=True, verbose_name='Motivo do Bloqueio'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='blocked_until',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Bloqueado até'),
        ),
    ]

