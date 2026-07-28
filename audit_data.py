#!/usr/bin/env python
"""
Script de Auditoria de Dados - JumperFour
Conta registros em cada tabela e identifica dados importantes para migração
"""
import os
import django
from django.db.models import Count, Q
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jumperfour.settings')
django.setup()

from tickets.models import (
    User, UserProfile, RoleLevel, Client, ClientHub, ContactPerson,
    ContactClient, ContactJumper, Equipment, EquipmentType, OrderType,
    ProblemType, System, TicketType, Ticket, TicketStatus, TicketImage,
    TicketUpdate, TicketUpdateImage, TicketFavorite, TicketListOrder,
    TechnicianTravel, TravelSegment, AIChatSession, AIChatMessage,
    AIUserMemory, AITicketBatchDraft, PrivateChatThread, PrivateChatMessage,
    PrivateChatReadState, ChecklistTemplate, ChecklistTemplateItem,
    ChecklistTemplateItemOption, DailyChecklist, DailyChecklistItem,
    DailyChecklistItemImage, DailyChecklistItemDetail, SystemSettings,
    AIProviderConfig, SearchProviderConfig, VoiceProviderConfig,
    ShiftHandover, ShiftHandoverEntry, ShiftHandoverEntryAlert,
    Notification, ActiveSession, MicrosoftGraphToken, ClientSyncState
)

class DataAudit:
    """Auditoria de dados do JumperFour"""

    def __init__(self):
        self.results = {}
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def count_model(self, model_class, name=None):
        """Conta registros de um modelo"""
        if name is None:
            name = model_class.__name__

        count = model_class.objects.count()
        self.results[name] = count
        return count

    def run_audit(self):
        """Executa auditoria completa"""
        print("=" * 80)
        print("🔍 AUDITORIA DE DADOS - JumperFour")
        print("=" * 80)
        print(f"Data: {self.timestamp}\n")

        # Autenticação
        print("\n📋 AUTENTICAÇÃO & USUÁRIOS")
        print("-" * 80)
        user_count = self.count_model(User, "User (Django)")
        print(f"  • Usuários Django: {user_count}")

        profile_count = self.count_model(UserProfile, "UserProfile")
        print(f"  • Perfis de Usuário: {profile_count}")

        role_count = self.count_model(RoleLevel, "RoleLevel")
        print(f"  • Níveis de Role: {role_count}")

        # Clientes
        print("\n👥 CLIENTES & CONTATOS")
        print("-" * 80)
        client_count = self.count_model(Client, "Client")
        print(f"  • Clientes: {client_count}")

        hub_count = self.count_model(ClientHub, "ClientHub")
        print(f"  • Hubs/Unidades de Cliente: {hub_count}")

        contact_client_count = self.count_model(ContactClient, "ContactClient")
        print(f"  • Contatos de Cliente: {contact_client_count}")

        contact_jumper_count = self.count_model(ContactJumper, "ContactJumper")
        print(f"  • Contatos Internos (JumperFour): {contact_jumper_count}")

        # Equipamentos & Categorias
        print("\n🔧 EQUIPAMENTOS & CATEGORIAS")
        print("-" * 80)
        equipment_count = self.count_model(Equipment, "Equipment")
        print(f"  • Equipamentos: {equipment_count}")

        equipment_type_count = self.count_model(EquipmentType, "EquipmentType")
        print(f"  • Tipos de Equipamento: {equipment_type_count}")

        order_type_count = self.count_model(OrderType, "OrderType")
        print(f"  • Tipos de Ordem: {order_type_count}")

        problem_type_count = self.count_model(ProblemType, "ProblemType")
        print(f"  • Tipos de Problema: {problem_type_count}")

        system_count = self.count_model(System, "System")
        print(f"  • Sistemas Gerenciados: {system_count}")

        ticket_type_count = self.count_model(TicketType, "TicketType")
        print(f"  • Tipos de Ticket: {ticket_type_count}")

        # Ordens de Serviço
        print("\n📋 ORDENS DE SERVIÇO (TICKETS)")
        print("-" * 80)
        ticket_count = self.count_model(Ticket, "Ticket")
        print(f"  • Total de Ordens de Serviço: {ticket_count}")

        # Status de tickets
        ticket_status_count = self.count_model(TicketStatus, "TicketStatus")
        print(f"  • Status Customizáveis: {ticket_status_count}")

        # Dados relacionados a tickets
        ticket_image_count = self.count_model(TicketImage, "TicketImage")
        print(f"  • Imagens de Ticket: {ticket_image_count}")

        ticket_update_count = self.count_model(TicketUpdate, "TicketUpdate")
        print(f"  • Updates de Ticket: {ticket_update_count}")

        ticket_fav_count = self.count_model(TicketFavorite, "TicketFavorite")
        print(f"  • Tickets Favoritos: {ticket_fav_count}")

        # Viagens
        print("\n✈️  VIAGENS TÉCNICAS")
        print("-" * 80)
        travel_count = self.count_model(TechnicianTravel, "TechnicianTravel")
        print(f"  • Viagens de Técnico: {travel_count}")

        segment_count = self.count_model(TravelSegment, "TravelSegment")
        print(f"  • Segmentos de Viagem: {segment_count}")

        # Chat IA
        print("\n🤖 CHAT COM IA (JOTA4)")
        print("-" * 80)
        ai_session_count = self.count_model(AIChatSession, "AIChatSession")
        print(f"  • Sessões de Chat IA: {ai_session_count}")

        ai_message_count = self.count_model(AIChatMessage, "AIChatMessage")
        print(f"  • Mensagens IA: {ai_message_count}")

        ai_memory_count = self.count_model(AIUserMemory, "AIUserMemory")
        print(f"  • Memórias de Usuário (IA): {ai_memory_count}")

        # Chat Privado
        print("\n💬 CHAT PRIVADO (1:1)")
        print("-" * 80)
        private_thread_count = self.count_model(PrivateChatThread, "PrivateChatThread")
        print(f"  • Threads de Chat Privado: {private_thread_count}")

        private_msg_count = self.count_model(PrivateChatMessage, "PrivateChatMessage")
        print(f"  • Mensagens Privadas: {private_msg_count}")

        # Checklists
        print("\n✅ CHECKLISTS")
        print("-" * 80)
        checklist_template_count = self.count_model(ChecklistTemplate, "ChecklistTemplate")
        print(f"  • Templates de Checklist: {checklist_template_count}")

        daily_checklist_count = self.count_model(DailyChecklist, "DailyChecklist")
        print(f"  • Checklists Diários: {daily_checklist_count}")

        # Passagem de Turno
        print("\n🔄 PASSAGEM DE TURNO")
        print("-" * 80)
        handover_count = self.count_model(ShiftHandover, "ShiftHandover")
        print(f"  • Passagens de Turno: {handover_count}")

        handover_entry_count = self.count_model(ShiftHandoverEntry, "ShiftHandoverEntry")
        print(f"  • Entradas de Passagem: {handover_entry_count}")

        # Notificações
        print("\n🔔 NOTIFICAÇÕES")
        print("-" * 80)
        notification_count = self.count_model(Notification, "Notification")
        print(f"  • Notificações: {notification_count}")

        # Configurações
        print("\n⚙️  CONFIGURAÇÕES DO SISTEMA")
        print("-" * 80)
        settings_count = self.count_model(SystemSettings, "SystemSettings")
        print(f"  • Configurações de Sistema: {settings_count}")

        ai_config_count = self.count_model(AIProviderConfig, "AIProviderConfig")
        print(f"  • Configurações de Provedor IA: {ai_config_count}")

        # Resumo
        print("\n" + "=" * 80)
        print("📊 RESUMO TOTAL")
        print("=" * 80)

        total_records = sum(self.results.values())
        total_models = len(self.results)

        print(f"Total de Registros: {total_records:,}")
        print(f"Total de Modelos com Dados: {total_models}")

        # Identifica modelos críticos (com mais dados)
        print("\n🔝 Top 5 Tabelas (por quantidade de registros):")
        sorted_models = sorted(self.results.items(), key=lambda x: x[1], reverse=True)
        for i, (model, count) in enumerate(sorted_models[:5], 1):
            print(f"  {i}. {model}: {count:,}")

        # Modelos vazios
        empty_models = [m for m, c in self.results.items() if c == 0]
        if empty_models:
            print(f"\n⚠️  Modelos Vazios ({len(empty_models)}):")
            for model in empty_models[:10]:
                print(f"  • {model}")

        return self.results

    def generate_report(self):
        """Gera relatório em markdown"""
        content = f"""# 📊 Auditoria de Dados - JumperFour

**Data:** {self.timestamp}

## Resumo Executivo

- **Total de Registros:** {sum(self.results.values()):,}
- **Modelos com Dados:** {len([c for c in self.results.values() if c > 0])}
- **Modelos Vazios:** {len([c for c in self.results.values() if c == 0])}

## Detalhamento

"""

        categories = {
            'Autenticação & Usuários': [
                'User (Django)', 'UserProfile', 'RoleLevel'
            ],
            'Clientes & Contatos': [
                'Client', 'ClientHub', 'ContactClient', 'ContactJumper'
            ],
            'Equipamentos & Categorias': [
                'Equipment', 'EquipmentType', 'OrderType', 'ProblemType', 'System', 'TicketType'
            ],
            'Ordens de Serviço': [
                'Ticket', 'TicketStatus', 'TicketImage', 'TicketUpdate', 'TicketFavorite'
            ],
            'Viagens Técnicas': [
                'TechnicianTravel', 'TravelSegment'
            ],
            'Chat IA (Jota4)': [
                'AIChatSession', 'AIChatMessage', 'AIUserMemory'
            ],
            'Chat Privado': [
                'PrivateChatThread', 'PrivateChatMessage'
            ],
            'Checklists': [
                'ChecklistTemplate', 'DailyChecklist'
            ],
            'Passagem de Turno': [
                'ShiftHandover', 'ShiftHandoverEntry'
            ],
            'Outros': [
                'Notification', 'SystemSettings', 'AIProviderConfig'
            ]
        }

        for category, models in categories.items():
            content += f"\n### {category}\n\n"
            for model in models:
                if model in self.results:
                    count = self.results[model]
                    status = "✅" if count > 0 else "⚠️"
                    content += f"- {status} {model}: {count:,}\n"

        return content

if __name__ == '__main__':
    audit = DataAudit()
    audit.run_audit()

    print("\n\n✅ Auditoria concluída!")
