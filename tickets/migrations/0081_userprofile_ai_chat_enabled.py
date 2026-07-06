# Generated migration for adding ai_chat_enabled field to UserProfile

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0080_ai_chat_and_settings'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='ai_chat_enabled',
            field=models.BooleanField(default=True, verbose_name='Ativar Chat IA'),
        ),
    ]
