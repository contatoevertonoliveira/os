from django.db import migrations

def add_permissions(apps, schema_editor):
    AppPage = apps.get_model('tickets', 'AppPage')
    RoleLevel = apps.get_model('tickets', 'RoleLevel')
    RolePagePermission = apps.get_model('tickets', 'RolePagePermission')

    try:
        page = AppPage.objects.get(code='ticketstatus_list')
    except AppPage.DoesNotExist:
        return

    roles = RoleLevel.objects.filter(is_active=True)
    for role in roles:
        RolePagePermission.objects.get_or_create(
            role=role,
            page=page,
            defaults={'allowed': True}
        )

def remove_permissions(apps, schema_editor):
    RolePagePermission = apps.get_model('tickets', 'RolePagePermission')
    RolePagePermission.objects.filter(page__code='ticketstatus_list').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0060_add_ticketstatus_page'),
    ]

    operations = [
        migrations.RunPython(add_permissions, remove_permissions),
    ]
