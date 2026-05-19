from django.db import migrations, models


def seed_pdf_pages(apps, schema_editor):
    AppPage = apps.get_model('tickets', 'AppPage')

    pages = [
        ('tickets_daily_report_view', 'Relatório Diário de Chamados (Visualizador)', 'tickets_daily_report_view', 'Relatórios', 10),
        ('tickets_daily_pdf', 'Relatório Diário de Chamados (PDF)', 'tickets_daily_pdf', 'Relatórios', 11),
        ('ticket_pdf_view', 'Relatório Detalhado do Chamado (Visualizador)', 'ticket_pdf_view', 'Relatórios', 20),
        ('ticket_pdf', 'Relatório Detalhado do Chamado (PDF)', 'ticket_pdf', 'Relatórios', 21),
        ('checklist_pdf', 'Checklist Diário (PDF)', 'checklist_pdf', 'Relatórios', 30),
    ]

    for code, name, url_name, group, order in pages:
        AppPage.objects.update_or_create(
            url_name=url_name,
            defaults={
                'code': code,
                'name': name,
                'group': group,
                'order': order,
                'is_enabled': True,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0050_userprofile_block_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='allow_pdf_reports',
            field=models.BooleanField(default=True, verbose_name='Permitir relatórios PDF'),
        ),
        migrations.RunPython(seed_pdf_pages, migrations.RunPython.noop),
    ]

