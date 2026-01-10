from django.views import View
from django.http import JsonResponse
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
from .models import Ticket, Client, Equipment, UserProfile, User
import json
from datetime import datetime

class TokenAuthMixin:
    def dispatch(self, request, *args, **kwargs):
        # Tenta pegar o token do Header ou do Query Parameter
        token = request.GET.get('token') or request.headers.get('Authorization')
        
        if not token:
            return JsonResponse({'error': 'Token não fornecido. Use ?token=SEU_TOKEN ou Header Authorization: Bearer SEU_TOKEN'}, status=401)
            
        try:
            # Remove 'Bearer ' se vier no header
            if token.startswith('Bearer '):
                token = token.split(' ')[1]
                
            # Verifica se o token existe e pega o usuário
            self.user_profile = UserProfile.objects.get(token=token)
            
        except UserProfile.DoesNotExist:
            return JsonResponse({'error': 'Token inválido ou expirado.'}, status=401)
            
        return super().dispatch(request, *args, **kwargs)

class TicketAPIView(TokenAuthMixin, View):
    def get(self, request):
        tickets = Ticket.objects.all().select_related('client', 'technician')
        data = []
        for ticket in tickets:
            data.append({
                'id': ticket.id,
                'codigo': ticket.formatted_id,
                'cliente': ticket.client.name,
                'status': ticket.get_status_display(),
                'tecnico': ticket.technician.username if ticket.technician else 'Sem técnico',
                'criado_em': ticket.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'descricao': ticket.description,
                'tipo_chamado': ticket.get_call_type_display() if ticket.call_type else None,
                'prioridade': ticket.problem_type.name if ticket.problem_type else None
            })
            
        return JsonResponse({'count': len(data), 'results': data}, safe=False)

class ClientAPIView(TokenAuthMixin, View):
    def get(self, request):
        clients = Client.objects.all()
        data = []
        for client in clients:
            data.append({
                'id': client.id,
                'nome': client.name,
                'email': client.email,
                'telefone': client.phone,
                'endereco': client.address,
                'contato': client.contact1_name
            })
        return JsonResponse({'count': len(data), 'results': data}, safe=False)

class EquipmentAPIView(TokenAuthMixin, View):
    def get(self, request):
        equipments = Equipment.objects.all().select_related('equipment_type')
        data = []
        for eq in equipments:
            data.append({
                'id': eq.id,
                'nome': eq.name,
                'tipo': eq.equipment_type.name if eq.equipment_type else None,
                'descricao': eq.description
            })
        return JsonResponse({'count': len(data), 'results': data}, safe=False)
