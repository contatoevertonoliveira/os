from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0021_alter_tickettype_options_clienthub_contact_name_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='leankeep_id',
            field=models.CharField(max_length=50, verbose_name='Nº Ocorrência Leankeep', blank=True, null=True),
        ),
    ]

