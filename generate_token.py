from django.contrib.auth.models import User
from tickets.models import UserProfile
import uuid

# Substitua 'seu_usuario' pelo nome do seu superusuário
USERNAME = 'admin' 

try:
    user = User.objects.get(username=USERNAME)
    
    # Verifica se já tem perfil, se não, cria
    profile, created = UserProfile.objects.get_or_create(user=user)
    
    # Gera um novo token se não tiver ou atualiza se quiser forçar
    if not profile.token:
        profile.token = str(uuid.uuid4())
        profile.save()
        print(f"Token GERADO para {USERNAME}: {profile.token}")
    else:
        print(f"Token ATUAL para {USERNAME}: {profile.token}")
        
except User.DoesNotExist:
    print(f"ERRO: Usuário '{USERNAME}' não encontrado. Crie o superusuário primeiro com 'python manage.py createsuperuser'")
