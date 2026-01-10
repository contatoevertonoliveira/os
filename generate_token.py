import os
import django
from django.conf import settings

# Configura o Django manualmente para scripts soltos
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jumperfour.settings')
django.setup()

from django.contrib.auth.models import User
from tickets.models import UserProfile
import uuid

USERNAME = 'admin'

print("--- INICIANDO GERADOR DE TOKEN ---")

try:
    print(f"Buscando usuário '{USERNAME}'...")
    user = User.objects.get(username=USERNAME)
    print(f"Usuário encontrado: {user.email}")
    
    print("Verificando perfil...")
    profile, created = UserProfile.objects.get_or_create(user=user)
    
    if created:
        print("Perfil criado agora.")
    else:
        print("Perfil já existia.")
    
    if not profile.token:
        print("Token vazio. Gerando novo...")
        profile.token = str(uuid.uuid4())
        profile.save()
        print(f"NOVO Token gerado: {profile.token}")
    else:
        print(f"Token EXISTENTE: {profile.token}")

except User.DoesNotExist:
    print(f"ERRO CRÍTICO: Usuário '{USERNAME}' não existe no banco de dados.")
    print("Rode 'python manage.py createsuperuser' primeiro!")
except Exception as e:
    print(f"ERRO INESPERADO: {e}")

print("--- FIM ---")
