from django.apps import AppConfig
from django.db.models.signals import post_migrate

class TicketsConfig(AppConfig):
    name = 'tickets'

    def ready(self):
        import tickets.signals
        post_migrate.connect(create_default_user, sender=self)

def create_default_user(sender, **kwargs):
    from django.contrib.auth.models import User
    from .models import UserProfile

    # Verifica se já existe um perfil com o token 2026
    if not UserProfile.objects.filter(token='2026').exists():
        print("Criando usuário SuperAdmin padrão (Token: 2026)...")

        # Verifica se o usuário 'admin' já existe para não dar erro de duplicate key
        if User.objects.filter(username='admin').exists():
            user = User.objects.get(username='admin')
        else:
            user = User.objects.create_user('admin', 'admin@example.com', 'admin')

        # get_or_create não sobrescreve o token/role se o profile já existir
        # (ex: criado pelo signal post_save em User), então atualizamos explicitamente.
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.token = '2026'
        profile.role = 'super_admin'
        profile.save()

        print("Usuário SuperAdmin padrão criado com sucesso!")
