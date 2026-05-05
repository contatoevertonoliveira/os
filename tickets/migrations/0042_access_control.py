from django.db import migrations, models
import django.db.models.deletion


def seed_access_control(apps, schema_editor):
    RoleLevel = apps.get_model('tickets', 'RoleLevel')
    AppPage = apps.get_model('tickets', 'AppPage')

    roles = [
        ('super_admin', 'Super Admin'),
        ('admin', 'Administrador'),
        ('technician', 'Técnico'),
        ('operator', 'Operador'),
        ('standard', 'Padrão'),
    ]

    for code, name in roles:
        RoleLevel.objects.update_or_create(
            code=code,
            defaults={
                'name': name,
                'is_system': True,
                'is_active': True,
            },
        )

    pages = [
        ('home', 'Bem-vindo', 'home', 'Público', 1),
        ('services_hub', 'Hub de Serviços', 'services_hub', 'Público', 2),
        ('login', 'Login', 'login', 'Público', 3),
        ('dashboard', 'Dashboard', 'dashboard', 'Geral', 10),
        ('hub_dashboard', 'Hubs Dashboard', 'hub_dashboard', 'Geral', 11),
        ('local', 'Local', 'local', 'Geral', 12),
        ('task_list', 'Lista de Tasks', 'task_list', 'Operação', 20),
        ('ticket_list', 'Ordens de Serviço', 'ticket_list', 'Operação', 21),
        ('checklist_daily', 'Checklist Diário', 'checklist_daily', 'Operação', 22),
        ('notification_list', 'Notificações', 'notification_list', 'Operação', 23),
        ('profile', 'Meu Perfil', 'profile', 'Conta', 30),
        ('settings', 'Configurações', 'settings', 'Admin', 40),
        ('user_list', 'Gerenciar Usuários', 'user_list', 'Admin', 41),
        ('technician_list', 'Técnicos (Cadastro)', 'technician_list', 'Cadastros', 50),
        ('client_list', 'Clientes', 'client_list', 'Cadastros', 51),
        ('equipment_list', 'Equipamentos', 'equipment_list', 'Cadastros', 52),
        ('system_list', 'Sistemas', 'system_list', 'Cadastros', 53),
        ('travel_list', 'Viagens', 'travel_list', 'Cadastros', 54),
        ('permissions', 'Permissões', 'permissions', 'Admin', 45),
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


def unseed_access_control(apps, schema_editor):
    RoleLevel = apps.get_model('tickets', 'RoleLevel')
    AppPage = apps.get_model('tickets', 'AppPage')
    RoleLevel.objects.filter(is_system=True).delete()
    AppPage.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0041_systemsettings_allow_checklist_pdf_debug'),
    ]

    operations = [
        migrations.CreateModel(
            name='RoleLevel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.SlugField(max_length=50, unique=True, verbose_name='Código do Nível')),
                ('name', models.CharField(max_length=100, verbose_name='Nome do Nível')),
                ('is_system', models.BooleanField(default=False, verbose_name='Nível do Sistema')),
                ('is_active', models.BooleanField(default=True, verbose_name='Ativo')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Nível de Usuário',
                'verbose_name_plural': 'Níveis de Usuário',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='AppPage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.SlugField(max_length=80, unique=True, verbose_name='Código da Página')),
                ('name', models.CharField(max_length=120, verbose_name='Nome da Página')),
                ('url_name', models.CharField(max_length=120, unique=True, verbose_name='URL Name (Django)')),
                ('group', models.CharField(blank=True, max_length=80, null=True, verbose_name='Grupo')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='Ordem')),
                ('is_enabled', models.BooleanField(default=True, verbose_name='Habilitada')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Página',
                'verbose_name_plural': 'Páginas',
                'ordering': ['group', 'order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='RolePagePermission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('allowed', models.BooleanField(default=True, verbose_name='Permitida')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('page', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='role_permissions', to='tickets.apppage', verbose_name='Página')),
                ('role', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='page_permissions', to='tickets.rolelevel', verbose_name='Nível')),
            ],
            options={
                'verbose_name': 'Permissão por Página',
                'verbose_name_plural': 'Permissões por Página',
                'unique_together': {('role', 'page')},
            },
        ),
        migrations.RunPython(seed_access_control, unseed_access_control),
    ]

