from django.db import migrations


def add_ticket_delete_page(apps, schema_editor):
    AppPage = apps.get_model('tickets', 'AppPage')
    RoleLevel = apps.get_model('tickets', 'RoleLevel')
    RolePagePermission = apps.get_model('tickets', 'RolePagePermission')

    page, _ = AppPage.objects.update_or_create(
        url_name='ticket_delete',
        defaults=dict(
            code='ticket_delete',
            name='Excluir OS',
            group='Operação',
            order=22,
            is_enabled=True,
        ),
    )

    # Mantém o comportamento atual como padrão:
    # somente admin e super_admin podem excluir, demais bloqueados.
    roles = list(RoleLevel.objects.filter(is_active=True))
    for role in roles:
        allowed = role.code in {'admin', 'super_admin'}
        RolePagePermission.objects.update_or_create(
            role=role,
            page=page,
            defaults={'allowed': allowed},
        )


def remove_ticket_delete_page(apps, schema_editor):
    AppPage = apps.get_model('tickets', 'AppPage')
    RolePagePermission = apps.get_model('tickets', 'RolePagePermission')
    page = AppPage.objects.filter(url_name='ticket_delete').first()
    if page:
        RolePagePermission.objects.filter(page=page).delete()
        page.delete()


class Migration(migrations.Migration):
    dependencies = [
        ('tickets', '0065_merge_20260602_1054'),
    ]

    operations = [
        migrations.RunPython(add_ticket_delete_page, remove_ticket_delete_page),
    ]

