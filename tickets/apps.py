from django.apps import AppConfig
from django.db.models.signals import post_migrate

class TicketsConfig(AppConfig):
    name = 'tickets'

    def ready(self):
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
            # Se o usuário existe mas não tem profile ou token errado, ajustamos
            if hasattr(user, 'profile'):
                user.profile.token = '2026'
                user.profile.role = 'super_admin'
                user.profile.save()
            else:
                UserProfile.objects.create(user=user, token='2026', role='super_admin')
        else:
            # Cria usuário e profile do zero
            user = User.objects.create_user('admin', 'admin@example.com', 'admin')
            UserProfile.objects.create(user=user, token='2026', role='super_admin')
            
        print("Usuário SuperAdmin padrão criado com sucesso!")
