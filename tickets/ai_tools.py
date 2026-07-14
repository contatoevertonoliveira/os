"""
Ferramentas (tools) disponíveis para o agente de IA.
Cada tool verifica permissões do usuário antes de executar operações no banco.
"""
import json
import logging
import time
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


def _parse_dt(value):
    """
    Converte string de data/hora em datetime timezone-aware.
    Aceita vários formatos. Se a string não tiver hora, usa a hora atual.
    Sempre retorna um datetime aware (com timezone do Django settings).
    """
    from django.utils.dateparse import parse_datetime, parse_date
    import datetime

    if not value:
        return None

    value = str(value).strip()

    # Tenta parse completo (YYYY-MM-DDTHH:MM ou YYYY-MM-DD HH:MM)
    dt = parse_datetime(value.replace(" ", "T"))
    if not dt:
        # Tenta só data (YYYY-MM-DD ou DD/MM/YYYY)
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                d = datetime.datetime.strptime(value[:10], fmt)
                # Sem hora — usa hora atual
                now = timezone.localtime(timezone.now())
                dt = datetime.datetime(d.year, d.month, d.day, now.hour, now.minute, 0)
                break
            except ValueError:
                continue

    if dt is None:
        return None

    # Garante timezone-aware
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())

    return dt


def _generate_username(seed):
    """Gera um login único a partir de um nome (slug + sufixo numérico se necessário)."""
    import unicodedata
    import re
    from django.contrib.auth.models import User as DjangoUser

    normalized = unicodedata.normalize('NFKD', seed or '')
    normalized = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.lower()
    normalized = re.sub(r'[^a-z0-9]+', '.', normalized).strip('.')
    base = normalized or 'user'

    username = base
    counter = 1
    while DjangoUser.objects.filter(username=username).exists():
        username = f"{base}{counter}"
        counter += 1
    return username


# ---------------------------------------------------------------------------
# Definições das tools (enviadas para o modelo de IA)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "name": "search_client",
        "description": "Busca clientes cadastrados pelo nome (busca parcial). Use para verificar se um cliente existe antes de criar uma OS.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nome ou parte do nome do cliente"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "search_web",
        "description": (
            "Busca informações reais na internet via Google. Uso geral — não é só para cadastro de "
            "empresas: use sempre que o usuário pedir para pesquisar/buscar/procurar algo online, por "
            "exemplo: nome oficial e razão social de empresas, endereço de clientes/lojas, telefones, "
            "contatos, e-mails, ou qualquer marca/modelo/especificação de equipamento (câmeras, "
            "sensores, nobreaks, etc)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Termo de busca, o mais específico possível. Ex: 'Rede Globo razão social Brasil', 'Bain & Company São Paulo endereço telefone', 'câmera Dahua DH-XVR7108 ficha técnica'"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_company_details",
        "description": "Busca detalhes de uma empresa na internet: endereço, telefone, CNPJ, CEP, cidade, site. Use após o usuário confirmar o nome da empresa para pré-preencher os dados de cadastro.",
        "parameters": {
            "type": "object",
            "properties": {
                "company_name": {"type": "string", "description": "Nome oficial da empresa (já confirmado pelo usuário)"}
            },
            "required": ["company_name"]
        }
    },
    {
        "name": "search_all_contacts",
        "description": "Busca pessoas pelo nome em toda a base de dados: contatos de clientes (ContactClient) e profissionais JumperFour (ContactJumper). Use para localizar qualquer pessoa cadastrada no sistema.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nome ou parte do nome da pessoa"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "get_client_details",
        "description": "Retorna detalhes de um cliente específico: hubs, contatos solicitantes disponíveis.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_id": {"type": "integer", "description": "ID do cliente"}
            },
            "required": ["client_id"]
        }
    },
    {
        "name": "list_ticket_statuses",
        "description": "Lista os status de OS disponíveis no sistema.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "list_systems",
        "description": "Lista os sistemas disponíveis para associar à OS.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "list_ticket_types",
        "description": "Lista os tipos de chamado disponíveis.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "list_jumper_contacts",
        "description": "Lista os responsáveis/executores da JumperFour disponíveis.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "list_equipments",
        "description": "Busca equipamentos já cadastrados no sistema (busca parcial pelo nome). Use SEMPRE antes de create_equipment, para verificar se o equipamento já existe e evitar duplicidade. Se não passar 'name', lista todos.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nome ou parte do nome do equipamento (opcional — se omitido, lista todos)"}
            },
            "required": []
        }
    },
    {
        "name": "list_equipment_types",
        "description": "Lista os tipos de equipamento cadastrados no sistema. Use antes de create_equipment_type para verificar se o tipo já existe.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "list_problem_types",
        "description": "Lista os tipos de problema cadastrados no sistema, usados para associar à OS. Use antes de create_problem_type para verificar se o tipo já existe.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "get_ticket",
        "description": "Busca uma OS (Ordem de Serviço) pelo número do ticket. Use para editar ou visualizar uma OS existente.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticket_number": {"type": "string", "description": "Número da OS (ex: 00042 ou 42)"}
            },
            "required": ["ticket_number"]
        }
    },
    {
        "name": "create_ticket",
        "description": "Cria uma nova OS após confirmação do usuário. Só chame após o usuário confirmar explicitamente os dados.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_id": {"type": "integer", "description": "ID do cliente"},
                "hub_id": {"type": "integer", "description": "ID do hub/loja (opcional)"},
                "status": {"type": "string", "description": "Código do status (ex: open, in_progress)"},
                "description": {"type": "string", "description": "Descrição inicial da OS"},
                "start_date": {"type": "string", "description": "Data/hora de início no formato YYYY-MM-DDTHH:MM"},
                "deadline": {"type": "string", "description": "Prazo no formato YYYY-MM-DDTHH:MM"},
                "contact_client_requester_id": {"type": "integer", "description": "ID do solicitante (ContactClient)"},
                "contact_jumper_responsible_id": {"type": "integer", "description": "ID do responsável JumperFour (ContactJumper)"},
                "ticket_type_id": {"type": "integer", "description": "ID do tipo de chamado (opcional)"},
                "system_id": {"type": "integer", "description": "ID do sistema (opcional)"},
                "problem_type_id": {"type": "integer", "description": "ID do tipo de problema (opcional, use list_problem_types para buscar)"},
                "equipment_ids": {"type": "array", "items": {"type": "integer"}, "description": "IDs dos equipamentos a vincular à OS (opcional, use list_equipments para buscar)"},
                "leankeep_id": {"type": "string", "description": "ID no Leankeep (opcional)"},
                "final_description": {"type": "string", "description": "Descrição final/resolução (opcional)"}
            },
            "required": ["client_id", "status", "description", "start_date", "deadline",
                         "contact_client_requester_id", "contact_jumper_responsible_id"]
        }
    },
    {
        "name": "start_ticket_batch",
        "description": (
            "Inicia a criação de OS em LOTE — use quando o usuário pedir para criar várias OS de uma vez "
            "(ex: 'preciso abrir 10 OS para o cliente X'). Informe total_count (quantas OS) e, se já souber, "
            "os campos que serão IGUAIS em todas (ex: mesmo cliente, mesmo responsável) em shared_defaults, "
            "usando as mesmas chaves de create_ticket — isso evita perguntar a mesma coisa de novo para cada "
            "uma. Depois de iniciar, colete os dados de cada OS uma por vez com add_or_update_batch_item."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "total_count": {"type": "integer", "description": "Quantas OS serão criadas neste lote"},
                "shared_defaults": {
                    "type": "object",
                    "description": "Campos padrão compartilhados por todas as OS do lote (mesmas chaves de create_ticket). Opcional."
                }
            },
            "required": ["total_count"]
        }
    },
    {
        "name": "add_or_update_batch_item",
        "description": (
            "Registra (ou corrige) os dados de UMA OS dentro de um lote em andamento, na posição 'index' "
            "(1 = primeira OS do lote, 2 = segunda, etc). Aceita os mesmos campos de create_ticket — campos "
            "não informados usam o valor de shared_defaults do lote, se houver. Use para preencher cada OS "
            "do lote uma de cada vez, ou para corrigir uma já preenchida se o usuário pedir ajuste."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "batch_id": {"type": "integer", "description": "ID do lote"},
                "index": {"type": "integer", "description": "Posição da OS dentro do lote (1-based)"},
                "client_id": {"type": "integer", "description": "ID do cliente"},
                "hub_id": {"type": "integer", "description": "ID do hub/loja (opcional)"},
                "status": {"type": "string", "description": "Código do status (ex: open, in_progress)"},
                "description": {"type": "string", "description": "Descrição inicial da OS"},
                "start_date": {"type": "string", "description": "Data/hora de início no formato YYYY-MM-DDTHH:MM"},
                "deadline": {"type": "string", "description": "Prazo no formato YYYY-MM-DDTHH:MM"},
                "contact_client_requester_id": {"type": "integer", "description": "ID do solicitante (ContactClient)"},
                "contact_jumper_responsible_id": {"type": "integer", "description": "ID do responsável JumperFour (ContactJumper)"},
                "ticket_type_id": {"type": "integer", "description": "ID do tipo de chamado (opcional)"},
                "system_id": {"type": "integer", "description": "ID do sistema (opcional)"},
                "problem_type_id": {"type": "integer", "description": "ID do tipo de problema (opcional)"},
                "equipment_ids": {"type": "array", "items": {"type": "integer"}, "description": "IDs dos equipamentos a vincular (opcional)"},
                "leankeep_id": {"type": "string", "description": "ID no Leankeep (opcional)"},
                "final_description": {"type": "string", "description": "Descrição final/resolução (opcional)"}
            },
            "required": ["batch_id", "index"]
        }
    },
    {
        "name": "list_batch_status",
        "description": (
            "Mostra o progresso do lote de OS em andamento: quantas posições já foram preenchidas, quais "
            "faltam, e um resumo de cada uma para o usuário revisar, pedir ajuste ou confirmar. Use sempre "
            "que o usuário perguntar o andamento do lote, antes de confirmar, ou para montar o resumo final."
        ),
        "parameters": {
            "type": "object",
            "properties": {"batch_id": {"type": "integer", "description": "ID do lote"}},
            "required": ["batch_id"]
        }
    },
    {
        "name": "cancel_ticket_batch",
        "description": "Cancela um lote de criação de OS em andamento — nada é criado, os rascunhos são descartados. Use quando o usuário pedir para cancelar/desistir do lote.",
        "parameters": {
            "type": "object",
            "properties": {"batch_id": {"type": "integer", "description": "ID do lote"}},
            "required": ["batch_id"]
        }
    },
    {
        "name": "confirm_ticket_batch",
        "description": (
            "Confirma e cria de fato TODAS as OS do lote — só chame depois que list_batch_status mostrar "
            "todas as posições preenchidas E o usuário confirmar explicitamente que pode criar. Cria uma OS "
            "por posição; se alguma falhar, avisa quais e mantém as demais já criadas."
        ),
        "parameters": {
            "type": "object",
            "properties": {"batch_id": {"type": "integer", "description": "ID do lote"}},
            "required": ["batch_id"]
        }
    },
    {
        "name": "update_ticket",
        "description": "Edita campos de uma OS existente após confirmação do usuário.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer", "description": "ID interno da OS"},
                "status": {"type": "string", "description": "Novo status (código)"},
                "description": {"type": "string", "description": "Nova descrição inicial"},
                "final_description": {"type": "string", "description": "Descrição final/resolução"},
                "deadline": {"type": "string", "description": "Novo prazo YYYY-MM-DDTHH:MM"},
                "contact_client_requester_id": {"type": "integer", "description": "Novo ID do solicitante"},
                "contact_jumper_responsible_id": {"type": "integer", "description": "Novo ID do responsável"},
                "ticket_type_id": {"type": "integer", "description": "Novo tipo de chamado"},
                "problem_type_id": {"type": "integer", "description": "Novo tipo de problema (use list_problem_types para buscar)"},
                "equipment_ids": {"type": "array", "items": {"type": "integer"}, "description": "Novos IDs dos equipamentos vinculados à OS — substitui a lista atual (use list_equipments para buscar)"}
            },
            "required": ["ticket_id"]
        }
    },
    {
        "name": "add_ticket_evolution",
        "description": "Adiciona uma evolução/atualização ao histórico de uma OS.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer", "description": "ID interno da OS"},
                "description": {"type": "string", "description": "Texto da evolução"}
            },
            "required": ["ticket_id", "description"]
        }
    },
    {
        "name": "delete_ticket",
        "description": "Exclui uma OS. Requer nível admin ou super_admin. Só chame após confirmação explícita.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer", "description": "ID interno da OS"}
            },
            "required": ["ticket_id"]
        }
    },
    {
        "name": "create_client",
        "description": "Cadastra um novo cliente no sistema após confirmação do usuário.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nome do cliente"},
                "email": {"type": "string", "description": "E-mail (opcional)"},
                "phone": {"type": "string", "description": "Telefone (opcional)"},
                "address": {"type": "string", "description": "Endereço (opcional)"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "update_client",
        "description": "Edita os dados de um cliente existente após confirmação do usuário. Requer permissão de administrador.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_id": {"type": "integer", "description": "ID do cliente a editar"},
                "name": {"type": "string", "description": "Novo nome do cliente (opcional)"},
                "email": {"type": "string", "description": "Novo e-mail (opcional)"},
                "phone": {"type": "string", "description": "Novo telefone (opcional)"},
                "address": {"type": "string", "description": "Novo endereço (opcional)"}
            },
            "required": ["client_id"]
        }
    },
    {
        "name": "create_equipment",
        "description": "Cadastra um novo equipamento no sistema após confirmação.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nome do equipamento"},
                "description": {"type": "string", "description": "Descrição (opcional)"},
                "equipment_type_id": {"type": "integer", "description": "ID do tipo de equipamento (opcional, use create_equipment_type para cadastrar um novo tipo se não existir)"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "clear_chat",
        "description": "Limpa o histórico do chat atual. Use SOMENTE quando o usuário pedir explicitamente para limpar, apagar ou resetar o chat/histórico/conversa.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "remember_user_preference",
        "description": (
            "Salva permanentemente uma preferência, trejeito, forma de tratamento, gíria/termo, atalho de "
            "criação ou padrão de trabalho do usuário ATUAL da conversa, para lembrar automaticamente em "
            "conversas futuras (mesmo em uma sessão nova). Use sempre que perceber ou o usuário ensinar algo "
            "sobre: como prefere ser chamado/tratado; um jeito específico de falar ou abreviar; um atalho "
            "(ex: 'quando eu disser XPTO, é para criar OS para o cliente Y no hub Z'); um padrão recorrente "
            "do jeito dele trabalhar (cliente que mais atende, tipo de chamado comum, equipe, etc). "
            "Não precisa pedir permissão nem avisar toda vez que salvar — apenas salve e continue a conversa "
            "naturalmente."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "note": {
                    "type": "string",
                    "description": "A preferência/aprendizado, escrito de forma clara e reutilizável em terceira pessoa (ex: 'Prefere ser chamado de Chefe', 'Quando pede OS para a Bain sem especificar hub, o hub padrão é a Loja Centro')."
                }
            },
            "required": ["note"]
        }
    },
    {
        "name": "forget_user_preference",
        "description": "Remove uma preferência/aprendizado salvo anteriormente sobre o usuário atual (via note_contains), ou apaga toda a memória dele se clear_all=true. Use quando o usuário pedir para esquecer, corrigir ou apagar algo que você aprendeu sobre ele.",
        "parameters": {
            "type": "object",
            "properties": {
                "note_contains": {"type": "string", "description": "Trecho de texto para localizar e remover a(s) nota(s) correspondente(s)"},
                "clear_all": {"type": "boolean", "description": "Se true, apaga toda a memória salva sobre o usuário atual"}
            }
        }
    },
    {
        "name": "check_pending_alerts",
        "description": "Verifica mensagens diretas não lidas e alertas de passagem de turno pendentes para o usuário ATUAL da conversa. Use sempre no início de uma conversa nova (e sempre que o usuário perguntar se tem mensagens/pendências) para avisar proativamente, antes de tratar do resto do pedido.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "get_message_content",
        "description": "Retorna o conteúdo completo de uma mensagem direta (Notification) do usuário atual, dado o notification_id retornado por check_pending_alerts. Use quando o usuário pedir para ler/ver a mensagem inteira.",
        "parameters": {
            "type": "object",
            "properties": {
                "notification_id": {"type": "integer", "description": "ID da notificação/mensagem"}
            },
            "required": ["notification_id"]
        }
    },
    {
        "name": "mark_message_read",
        "description": "Marca uma mensagem direta (Notification) como lida/baixa dada, para o usuário atual. Use somente depois de mostrar o conteúdo e o usuário confirmar que quer dar baixa.",
        "parameters": {
            "type": "object",
            "properties": {
                "notification_id": {"type": "integer", "description": "ID da notificação/mensagem"}
            },
            "required": ["notification_id"]
        }
    },
    {
        "name": "acknowledge_handover_alert",
        "description": "Dá baixa (acknowledge) em um alerta de anotação da passagem de turno para o usuário atual, dado o entry_id retornado por check_pending_alerts. Use somente depois de mostrar o conteúdo e o usuário confirmar que quer dar baixa.",
        "parameters": {
            "type": "object",
            "properties": {
                "entry_id": {"type": "integer", "description": "ID da anotação da passagem de turno (entry_id)"}
            },
            "required": ["entry_id"]
        }
    },
    {
        "name": "create_handover_entry",
        "description": (
            "Cria uma nova anotação na Passagem de Turno (tela de Tasks), no turno vigente agora "
            "(diurno/noturno, calculado automaticamente). Use quando o usuário pedir para anotar, "
            "registrar ou deixar um recado na passagem de turno — inclusive quando ditar por voz. Se a "
            "mensagem veio de áudio, ajuste pontuação/gramática antes de salvar, mantendo o sentido "
            "original — nunca invente informação nova. Sempre confirme o texto final com o usuário antes "
            "de chamar esta tool (regra geral de confirmação antes de criar)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Texto final da anotação, já revisado/formatado e confirmado pelo usuário"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "notify_handover_entry",
        "description": (
            "Notifica (\"cutuca\") um usuário específico sobre uma anotação da passagem de turno — cria "
            "um alerta pendente para ele, que aparece sozinho no próximo login/abertura do chat dele "
            "(mesmo mecanismo lido por check_pending_alerts). Use depois de criar uma anotação (ou sobre "
            "uma já existente) quando o usuário pedir para avisar/indicar alguém sobre ela. Diferente de "
            "send_message_to_user (que manda uma mensagem direta) — aqui é um alerta vinculado à anotação."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entry_id": {"type": "integer", "description": "ID da anotação (retornado por create_handover_entry)"},
                "recipient_id": {"type": "integer", "description": "ID do usuário a notificar (preferencial se já conhecido)"},
                "recipient_name": {"type": "string", "description": "Nome do usuário a notificar, caso o ID não seja conhecido"},
                "priority": {"type": "string", "description": "Prioridade do alerta: high, medium ou low (padrão medium)"}
            },
            "required": ["entry_id"]
        }
    },
    {
        "name": "send_message_to_user",
        "description": (
            "Envia uma mensagem direta do usuário ATUAL para outro usuário do sistema (cria uma notificação "
            "para ele). Use quando o usuário pedir para responder, avisar ou mandar recado para alguém — por "
            "exemplo, para responder a quem acabou de mandar uma mensagem pendente (use o sender_id retornado "
            "por check_pending_alerts/get_message_content como recipient_id). Também serve para mandar uma "
            "mensagem nova para qualquer colaborador, mesmo sem pendência anterior."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "recipient_id": {"type": "integer", "description": "ID do usuário destinatário (preferencial quando já conhecido, ex: vindo de check_pending_alerts)"},
                "recipient_name": {"type": "string", "description": "Nome do destinatário, caso o ID não seja conhecido (busca por nome/username)"},
                "message": {"type": "string", "description": "Conteúdo da mensagem a enviar"},
                "title": {"type": "string", "description": "Título da mensagem (opcional)"}
            },
            "required": ["message"]
        }
    },
    {
        "name": "open_private_chat",
        "description": (
            "Abre um chat particular instantâneo (estilo Messenger) do usuário atual com outro usuário do "
            "sistema, para conversarem em tempo real. Use quando o usuário pedir algo como 'abre um chat "
            "particular com o Fulano' ou 'quero falar com a Beltrana agora'. Não é para mensagens assíncronas "
            "(isso é o send_message_to_user) — é para abrir a janela de conversa direta."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "recipient_id": {"type": "integer", "description": "ID do usuário para conversar (preferencial quando já conhecido)"},
                "recipient_name": {"type": "string", "description": "Nome do usuário, caso o ID não seja conhecido (busca por nome/username)"}
            }
        }
    },
    {
        "name": "create_contact_client",
        "description": "Cadastra um novo contato/solicitante vinculado a um cliente (e opcionalmente a um hub/loja). Use quando o solicitante não existir na lista do cliente.",
        "parameters": {
            "type": "object",
            "properties": {
                "name":      {"type": "string", "description": "Nome completo do contato"},
                "client_id": {"type": "integer", "description": "ID do cliente ao qual o contato pertence"},
                "hub_id":    {"type": "integer", "description": "ID do hub/loja (opcional, se o contato for de uma loja específica)"},
                "email":     {"type": "string", "description": "E-mail (opcional)"},
                "phone":     {"type": "string", "description": "Telefone (opcional)"}
            },
            "required": ["name", "client_id"]
        }
    },
    {
        "name": "create_contact_jumper",
        "description": "Cadastra um novo profissional da JumperFour como responsável. Use quando o executor desejado não existir na lista. Requer permissão de administrador.",
        "parameters": {
            "type": "object",
            "properties": {
                "name":       {"type": "string", "description": "Nome completo"},
                "role":       {"type": "string", "description": "Cargo/função (opcional)"},
                "department": {"type": "string", "description": "Departamento (opcional)"},
                "email":      {"type": "string", "description": "E-mail (opcional)"},
                "phone":      {"type": "string", "description": "Telefone (opcional)"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "create_hub",
        "description": "Cadastra uma nova filial/loja (hub) para um cliente. Use quando o hub não existir. Requer permissão de administrador.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_id": {"type": "integer", "description": "ID do cliente"},
                "name":      {"type": "string", "description": "Nome da filial/loja"}
            },
            "required": ["client_id", "name"]
        }
    },
    {
        "name": "create_role",
        "description": "Cria um novo nível de acesso (role) no sistema. Requer permissão de super_admin ou admin.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nome do nível (ex: Coordenador, Gerente)"},
                "code": {"type": "string", "description": "Código único do nível (opcional, em minúsculas sem espaços)"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "create_page",
        "description": "Cria uma nova página/tela no sistema. Requer permissão de super_admin ou admin.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nome da página (ex: Relatórios, Dashboard)"},
                "url_name": {"type": "string", "description": "Nome da URL Django (ex: reports, dashboard)"},
                "code": {"type": "string", "description": "Código único (opcional)"},
                "group": {"type": "string", "description": "Grupo/categoria (opcional, ex: Admin, Financeiro)"}
            },
            "required": ["name", "url_name"]
        }
    },
    {
        "name": "create_ticket_type",
        "description": "Cadastra um novo Tipo de Chamado no sistema. Requer permissão de administrador.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nome do tipo de chamado"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "create_problem_type",
        "description": "Cadastra um novo Tipo de Problema no sistema. Requer permissão de administrador.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nome do tipo de problema"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "create_system",
        "description": "Cadastra um novo Sistema (usado para associar a OS e clientes). Requer permissão de administrador.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nome do sistema"},
                "color": {"type": "string", "description": "Cor em hex (opcional, ex: #FF0000)"},
                "description": {"type": "string", "description": "Descrição (opcional)"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "create_equipment_type",
        "description": "Cadastra um novo Tipo de Equipamento. Requer permissão de administrador.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nome do tipo de equipamento"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "create_ticket_status",
        "description": "Cadastra um novo Status de OS (badge/cor exibida nas ordens de serviço). Requer permissão de administrador.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Código único do status, em minúsculas sem espaços (ex: aguardando_peca)"},
                "name": {"type": "string", "description": "Nome exibido do status"},
                "color": {"type": "string", "description": "Cor de fundo hex (opcional, ex: #28a745)"},
                "font_color": {"type": "string", "description": "Cor da fonte hex (opcional)"},
                "row_color": {"type": "string", "description": "Cor de fundo da linha na lista (opcional)"},
                "order": {"type": "integer", "description": "Ordem de exibição (opcional)"}
            },
            "required": ["code", "name"]
        }
    },
    {
        "name": "create_technician",
        "description": "Cadastra um novo Técnico (usuário do sistema com nível Técnico). Requer permissão de administrador.",
        "parameters": {
            "type": "object",
            "properties": {
                "first_name": {"type": "string", "description": "Nome do técnico"},
                "email": {"type": "string", "description": "E-mail (opcional)"},
                "username": {"type": "string", "description": "Login (opcional, gerado automaticamente a partir do nome se não informado)"},
                "job_title": {"type": "string", "description": "Cargo (opcional)"},
                "station": {"type": "string", "description": "Posto de alocação (opcional)"},
                "department": {"type": "string", "description": "Departamento/área (opcional)"}
            },
            "required": ["first_name"]
        }
    },
    {
        "name": "create_responsible",
        "description": "Cadastra um novo Responsável (usuário operador vinculado a um cliente fixo). Requer permissão de administrador.",
        "parameters": {
            "type": "object",
            "properties": {
                "first_name": {"type": "string", "description": "Nome do responsável"},
                "client_id": {"type": "integer", "description": "ID do cliente ao qual o responsável fica vinculado"},
                "email": {"type": "string", "description": "E-mail (opcional)"}
            },
            "required": ["first_name", "client_id"]
        }
    },
    {
        "name": "create_user_account",
        "description": "Cadastra um novo usuário completo do sistema, com nível de acesso à escolha. Requer permissão de administrador. Admin só pode criar usuários de níveis abaixo do seu; Super Admin pode criar qualquer nível.",
        "parameters": {
            "type": "object",
            "properties": {
                "first_name": {"type": "string", "description": "Nome completo"},
                "role": {"type": "string", "description": "Código do nível de acesso (ex: standard, operator, technician, admin, super_admin, ou o código de um nível customizado criado via create_role)"},
                "username": {"type": "string", "description": "Login (opcional, gerado automaticamente a partir do nome se não informado)"},
                "email": {"type": "string", "description": "E-mail (opcional)"},
                "password": {"type": "string", "description": "Senha inicial (opcional, gerada automaticamente se não informada)"},
                "job_title": {"type": "string", "description": "Cargo (opcional)"}
            },
            "required": ["first_name", "role"]
        }
    },
    {
        "name": "create_travel",
        "description": "Cadastra uma nova Viagem Técnica (agendamento de viagem de um técnico a um cliente). Requer permissão de administrador. Detalhes de voo/hotel podem ser adicionados depois pela tela de Viagens.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_id": {"type": "integer", "description": "ID do cliente"},
                "technician_id": {"type": "integer", "description": "ID do usuário técnico responsável"},
                "scheduled_date": {"type": "string", "description": "Data/hora agendada, formato YYYY-MM-DDTHH:MM"},
                "hub_id": {"type": "integer", "description": "ID do hub/loja (opcional)"},
                "system_id": {"type": "integer", "description": "ID do sistema (opcional)"},
                "ticket_id": {"type": "integer", "description": "ID da OS relacionada (opcional)"}
            },
            "required": ["client_id", "technician_id", "scheduled_date"]
        }
    },
    {
        "name": "list_roles",
        "description": "Lista todos os níveis de acesso disponíveis no sistema.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "list_pages",
        "description": "Lista todas as páginas/telas disponíveis no sistema.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "open_page",
        "description": (
            "Abre uma página do sistema no navegador do usuário, quando ele pedir pra 'abrir', 'ir para', "
            "'mostrar' ou 'navegar até' uma tela específica. O chat continua aberto durante e depois da "
            "navegação — nunca minimiza sozinho por causa disso, só quando o usuário clicar no botão de "
            "minimizar."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "page": {
                    "type": "string",
                    "description": (
                        "Identificador exato da página (escolha o mais adequado ao pedido do usuário, mesmo "
                        "que ele use um sinônimo ou termo informal): "
                        "dashboard (Dashboard), hub_dashboard (Dashboard de Hubs), local (Local), "
                        "task_list (Passagem de Turno / Tasks), ticket_list (Lista de Ordens de Serviço / OS), "
                        "ticket_create (Criar Nova OS), checklist_daily (Checklist Diário), "
                        "checklist_config (Configuração de Checklist), client_list (Clientes), "
                        "equipment_list (Equipamentos), system_list (Sistemas), ticketstatus_list (Status de OS), "
                        "ordertype_list (Tipos de Chamado), problemtype_list (Tipos de Problema), "
                        "technician_list (Técnicos), responsible_list (Responsáveis), "
                        "contactclient_list (Contatos de Clientes), contactjumper_list (Contatos JumperFour), "
                        "travel_list (Viagens), user_list (Usuários), notification_list (Notificações), "
                        "notification_monitor (Monitor de Notificações), profile (Meu Perfil), "
                        "settings (Configurações), permissions (Permissões), "
                        "tickets_daily_report_view (Relatório Diário de Chamados), "
                        "tickets_weekly_report_view (Relatório Semanal de Chamados), "
                        "tickets_monthly_report_view (Relatório Mensal de Chamados)"
                    )
                }
            },
            "required": ["page"]
        }
    },
    {
        "name": "list_users",
        "description": "Lista todos os usuários do sistema com seus perfis.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "toggle_page_enabled",
        "description": "Habilita ou desabilita uma página no sistema. Requer permissão de super_admin ou admin.",
        "parameters": {
            "type": "object",
            "properties": {
                "page_id": {"type": "integer", "description": "ID da página"},
                "enabled": {"type": "boolean", "description": "true para habilitar, false para desabilitar"}
            },
            "required": ["page_id", "enabled"]
        }
    },
    {
        "name": "update_page_permission",
        "description": "Atualiza a permissão de acesso a uma página para um nível específico. Requer permissão de super_admin ou admin.",
        "parameters": {
            "type": "object",
            "properties": {
                "page_id": {"type": "integer", "description": "ID da página"},
                "role_id": {"type": "integer", "description": "ID do nível de acesso"},
                "allowed": {"type": "boolean", "description": "true para permitir, false para bloquear"}
            },
            "required": ["page_id", "role_id", "allowed"]
        }
    },
    {
        "name": "get_role_page_permissions",
        "description": "Mostra, para um nível de acesso (ou para todos os níveis se role_id não for informado), quais páginas/telas do sistema estão liberadas ou bloqueadas. Use para responder perguntas sobre o que um nível pode ou não acessar. Requer permissão de super_admin ou admin.",
        "parameters": {
            "type": "object",
            "properties": {
                "role_id": {"type": "integer", "description": "ID do nível de acesso (opcional — se omitido, retorna todos os níveis)"}
            }
        }
    },
    {
        "name": "update_user_restriction",
        "description": "Atualiza restrições de funcionalidade para um usuário específico. Requer permissão de super_admin ou admin.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "ID do usuário"},
                "restriction_type": {"type": "string", "description": "Tipo de restrição: can_view_tickets, can_create_tickets, can_edit_tickets, can_delete_tickets, can_view_checklists, can_create_checklists, allow_pdf_reports, ai_chat_enabled"},
                "allowed": {"type": "boolean", "description": "true para permitir, false para bloquear"}
            },
            "required": ["user_id", "restriction_type", "allowed"]
        }
    },
    {
        "name": "list_all_users_admin",
        "description": "Lista todos os usuários do sistema com detalhes. Somente para Super Admin (acesso global) e Admin (acesso a usuários de níveis abaixo).",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "get_user_details_admin",
        "description": "Obtém detalhes completos de um usuário específico, incluindo informações sensíveis. Requer permissão de super_admin ou admin. Admin só pode acessar usuários de níveis abaixo.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "ID do usuário"},
                "include_password": {"type": "boolean", "description": "Se true, revela a senha (dados sigilosos)"}
            },
            "required": ["user_id"]
        }
    },
    {
        "name": "update_user_data_admin",
        "description": "Atualiza dados de um usuário (nome, email, telefone, etc). Requer permissão de super_admin ou admin. Admin só pode alterar usuários de níveis abaixo.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "ID do usuário"},
                "first_name": {"type": "string", "description": "Novo nome"},
                "email": {"type": "string", "description": "Novo email"},
                "job_title": {"type": "string", "description": "Novo cargo"}
            },
            "required": ["user_id"]
        }
    },
    {
        "name": "change_user_password_admin",
        "description": "Altera a senha de um usuário. Requer permissão de super_admin ou admin. Admin só pode alterar usuários de níveis abaixo.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "ID do usuário"},
                "new_password": {"type": "string", "description": "Nova senha"}
            },
            "required": ["user_id", "new_password"]
        }
    },
    {
        "name": "get_system_info_admin",
        "description": "Obtém informações gerais do sistema: usuários online/logados, estatísticas, configurações. Requer permissão de super_admin ou admin.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "list_online_users_admin",
        "description": "Lista usuários que estão online ou logados no momento. Requer permissão de super_admin ou admin.",
        "parameters": {"type": "object", "properties": {}}
    },
]


# ---------------------------------------------------------------------------
# Executor de tools
# ---------------------------------------------------------------------------

def execute_tool(tool_name: str, args: dict, user) -> dict:
    """
    Executa uma tool pelo nome com os argumentos fornecidos.
    Verifica permissões do usuário antes de operações destrutivas.
    Retorna dict com 'ok' (bool) e 'data' ou 'error'.
    """
    try:
        fn = _TOOL_REGISTRY.get(tool_name)
        if not fn:
            return {"ok": False, "error": f"Ferramenta desconhecida: {tool_name}"}
        return fn(args, user)
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Implementação de cada tool
# ---------------------------------------------------------------------------

def _google_custom_search(query, num=5, api_key=None, engine_id=None):
    """Chama a API do Google Custom Search. Levanta ValueError se não configurada,
    ou retorna a lista de 'items' (title, snippet, link) do Google.
    Se api_key/engine_id não forem passados, usa os valores salvos em SystemSettings
    (uso normal); passar os dois permite testar valores ainda não salvos."""
    import urllib.request
    import urllib.parse
    import json as _json
    from .models import SystemSettings

    if api_key is None or engine_id is None:
        settings_obj = SystemSettings.objects.first()
        api_key = api_key if api_key is not None else ((settings_obj.google_search_api_key if settings_obj else "") or "")
        engine_id = engine_id if engine_id is not None else ((settings_obj.google_search_engine_id if settings_obj else "") or "")

    if not api_key or not engine_id:
        raise ValueError(
            "Busca na internet não está configurada. Peça a um administrador para configurar em "
            "Configurações → Integrações (Google Custom Search)."
        )

    params = urllib.parse.urlencode({
        "key": api_key,
        "cx": engine_id,
        "q": query,
        "num": min(max(num, 1), 10),
        "gl": "br",
        "hl": "pt-BR",
    })
    url = f"https://www.googleapis.com/customsearch/v1?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (JumperFour OS)"})

    import urllib.error
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = _json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # Extrai a mensagem real de erro do corpo da resposta do Google (ex: chave
        # inválida, API não habilitada, cota excedida) em vez de um "HTTP Error 403" genérico.
        try:
            error_body = _json.loads(e.read().decode("utf-8"))
            message = error_body.get("error", {}).get("message") or f"Erro HTTP {e.code} na API do Google."
        except Exception:
            message = f"Erro HTTP {e.code} na API do Google."
        raise ValueError(message)

    if "error" in data:
        raise ValueError(data["error"].get("message") or "Erro desconhecido na API do Google.")

    return data.get("items", [])


def _tavily_search(query, num=5, api_key=None):
    """Chama a API da Tavily. Levanta ValueError se não configurada, ou retorna
    lista normalizada [{'title', 'snippet', 'link'}] (mesmo formato do Google).
    Se api_key não for passada, usa o valor salvo em SystemSettings."""
    import urllib.request
    import urllib.error
    import json as _json
    from .models import SystemSettings

    if api_key is None:
        settings_obj = SystemSettings.objects.first()
        api_key = (settings_obj.tavily_api_key if settings_obj else "") or ""

    if not api_key:
        raise ValueError(
            "Busca na internet não está configurada. Peça a um administrador para configurar em "
            "Configurações → Integrações (Tavily)."
        )

    body = _json.dumps({
        "api_key": api_key,
        "query": query,
        "max_results": min(max(num, 1), 10),
        "search_depth": "basic",
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.tavily.com/search",
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 (JumperFour OS)"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = _json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            error_body = _json.loads(e.read().decode("utf-8"))
            message = error_body.get("detail", {}).get("error") or error_body.get("error") or f"Erro HTTP {e.code} na API da Tavily."
        except Exception:
            message = f"Erro HTTP {e.code} na API da Tavily."
        raise ValueError(message)

    items = data.get("results", [])
    return [
        {"title": it.get("title", ""), "snippet": it.get("content", ""), "link": it.get("url", "")}
        for it in items
    ]


def _web_search(query, num=5, provider=None, google_api_key=None, google_engine_id=None, tavily_api_key=None):
    """Busca na web através do provedor configurado em SystemSettings.search_provider
    (google ou tavily), retornando lista normalizada [{'title', 'snippet', 'link'}].
    Os parâmetros *_api_key/engine_id, se passados, sobrepõem o valor salvo (uso em
    telas de teste, antes de salvar)."""
    from .models import SystemSettings

    if provider is None:
        settings_obj = SystemSettings.objects.first()
        provider = (settings_obj.search_provider if settings_obj else "") or "google"

    if provider == "tavily":
        return _tavily_search(query, num=num, api_key=tavily_api_key)
    return _google_custom_search(query, num=num, api_key=google_api_key, engine_id=google_engine_id)


def google_tts_synthesize(text, voice_gender="FEMALE", api_key=None):
    """Chama o Google Cloud Text-to-Speech e retorna o áudio em MP3 (bytes).
    Levanta ValueError se não configurado ou em caso de erro da API.
    Se api_key não for passada, usa o valor salvo em SystemSettings (uso normal);
    passá-la permite testar uma chave ainda não salva."""
    import urllib.request
    import urllib.error
    import json as _json
    import base64
    from .models import SystemSettings

    if api_key is None:
        settings_obj = SystemSettings.objects.first()
        api_key = (settings_obj.google_tts_api_key if settings_obj else "") or ""

    if not api_key:
        raise ValueError(
            "Voz profissional (Google Cloud) não está configurada. Peça a um administrador para "
            "configurar em Configurações → Integrações (Google Cloud Text-to-Speech)."
        )

    gender = "FEMALE" if str(voice_gender).lower() not in ("male", "masculina", "masculino") else "MALE"

    body = _json.dumps({
        "input": {"text": text[:4900]},  # limite de segurança bem abaixo do máximo da API (5000 bytes)
        "voice": {"languageCode": "pt-BR", "ssmlGender": gender},
        "audioConfig": {"audioEncoding": "MP3"},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}",
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 (JumperFour OS)"},
        method="POST",
    )

    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = _json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            error_body = _json.loads(e.read().decode("utf-8"))
            message = error_body.get("error", {}).get("message") or f"Erro HTTP {e.code} na API do Google."
        except Exception:
            message = f"Erro HTTP {e.code} na API do Google."
        raise ValueError(message)
    finally:
        logger.info("TTS Google sintetizado em %.2fs", time.perf_counter() - t0)

    audio_b64 = data.get("audioContent")
    if not audio_b64:
        raise ValueError("A API do Google não retornou áudio.")

    return base64.b64decode(audio_b64)


def elevenlabs_tts_synthesize(text, voice_gender="female", api_key=None, voice_id=None):
    """Chama a API da ElevenLabs (via SDK oficial) e retorna o áudio em MP3 (bytes).
    Levanta ValueError se não configurado ou em caso de erro da API. ElevenLabs não
    escolhe voz automaticamente por gênero/idioma como o Google — depende de um ID
    de voz específico da biblioteca do usuário, cadastrado por gênero em SystemSettings.
    Se api_key/voice_id não forem passados, usa os valores salvos (uso normal);
    passá-los permite testar valores ainda não salvos."""
    from .models import SystemSettings

    settings_obj = SystemSettings.objects.first() if (api_key is None or voice_id is None) else None

    if api_key is None:
        api_key = (settings_obj.elevenlabs_api_key if settings_obj else "") or ""
    if not api_key:
        raise ValueError(
            "Voz ElevenLabs não está configurada. Peça a um administrador para configurar em "
            "Configurações → Integrações (ElevenLabs)."
        )

    if voice_id is None:
        is_male = str(voice_gender).lower() in ("male", "masculina", "masculino")
        if settings_obj:
            voice_id = settings_obj.elevenlabs_voice_id_male if is_male else settings_obj.elevenlabs_voice_id_female
        voice_id = voice_id or ""
    if not voice_id:
        raise ValueError(
            "Nenhum ID de voz ElevenLabs configurado para esse gênero. Configure em Configurações → "
            "Integrações (ElevenLabs)."
        )

    from elevenlabs.client import ElevenLabs
    from elevenlabs.core.api_error import ApiError
    from elevenlabs.types.voice_settings import VoiceSettings

    client = ElevenLabs(api_key=api_key)
    t0 = time.perf_counter()
    try:
        audio_stream = client.text_to_speech.convert(
            voice_id=voice_id,
            text=text[:4900],
            # eleven_v3 não aceita voice_settings.speed nem similarity_boost/speaker_boost;
            # multilingual_v2 aceita tudo e soa mais estável/natural em pt-BR para conversa.
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
            voice_settings=VoiceSettings(
                stability=0.6,       # mais consistente/calma, menos variação dramática entre frases
                similarity_boost=0.8,
                style=0.15,          # baixa exageração — evita tom "atuado"/robótico
                use_speaker_boost=True,
                speed=0.92,          # levemente mais devagar que o padrão (1.0), fala mais tranquila
            ),
        )
        return b"".join(audio_stream)
    except ApiError as e:
        message = None
        if isinstance(e.body, dict):
            detail = e.body.get("detail")
            if isinstance(detail, dict):
                message = detail.get("message")
            elif isinstance(detail, str):
                message = detail
        raise ValueError(message or f"Erro HTTP {e.status_code} na API da ElevenLabs.")
    finally:
        logger.info("TTS ElevenLabs sintetizado em %.2fs (%d chars)", time.perf_counter() - t0, len(text[:4900]))


def list_elevenlabs_voices(api_key=None):
    """Busca vozes nativas do Brasil (pt-BR, sotaque brasileiro) na biblioteca
    pública da ElevenLabs — não a lista de vozes já adicionadas à conta, que por
    padrão são todas em inglês/outros sotaques. Não precisa "adicionar" a voz à
    conta antes de usar: o voice_id da biblioteca pública já funciona direto na
    síntese. Retorna lista normalizada [{'voice_id', 'name', 'gender',
    'preview_url'}], ordenada por popularidade (trending) dentro de cada gênero.
    Levanta ValueError se não configurado ou em caso de erro da API. Se api_key
    não for passada, usa a salva em SystemSettings (uso normal); passá-la
    permite testar uma chave ainda não salva."""
    from .models import SystemSettings

    if api_key is None:
        settings_obj = SystemSettings.objects.first()
        api_key = (settings_obj.elevenlabs_api_key if settings_obj else "") or ""
    if not api_key:
        raise ValueError(
            "Voz ElevenLabs não está configurada. Peça a um administrador para configurar em "
            "Configurações → Integrações (ElevenLabs)."
        )

    from elevenlabs.client import ElevenLabs
    from elevenlabs.core.api_error import ApiError

    client = ElevenLabs(api_key=api_key)
    try:
        resp = client.voices.get_shared(
            language="pt",
            locale="pt-BR",
            accent="brazilian",
            sort="trending",
            page_size=60,
        )
    except ApiError as e:
        message = None
        if isinstance(e.body, dict):
            detail = e.body.get("detail")
            if isinstance(detail, dict):
                message = detail.get("message")
            elif isinstance(detail, str):
                message = detail
        raise ValueError(message or f"Erro HTTP {e.status_code} na API da ElevenLabs.")

    voices = []
    for v in resp.voices:
        voices.append({
            "voice_id": v.voice_id,
            "name": v.name,
            "gender": (v.gender or "").lower(),
            "preview_url": v.preview_url or "",
        })
    voices.sort(key=lambda x: (x["gender"] != "female", x["gender"] != "male"))
    return voices


def tts_synthesize(text, voice_gender="female", provider=None, google_api_key=None,
                    elevenlabs_api_key=None, elevenlabs_voice_id=None):
    """Sintetiza voz através do provedor configurado em SystemSettings.tts_provider
    (google ou elevenlabs) — o provedor 'browser' não passa por aqui, é tratado
    inteiramente no navegador do usuário. Retorna áudio em MP3 (bytes); levanta
    ValueError se não configurado ou em caso de erro do provedor."""
    from .models import SystemSettings

    if provider is None:
        settings_obj = SystemSettings.objects.first()
        provider = (settings_obj.tts_provider if settings_obj else "") or "browser"

    if provider == "elevenlabs":
        return elevenlabs_tts_synthesize(
            text, voice_gender=voice_gender, api_key=elevenlabs_api_key, voice_id=elevenlabs_voice_id
        )
    return google_tts_synthesize(text, voice_gender=voice_gender, api_key=google_api_key)


def _search_web(args, user):
    """Busca informações reais na internet (Google ou Tavily, conforme configurado).
    Use para clientes, endereços, telefones, contatos, e-mails, equipamentos,
    marcas/modelos ou qualquer outra informação que precise ser confirmada fora do sistema."""
    query = args.get("query", "").strip()
    if not query:
        return {"ok": False, "error": "Consulta vazia."}

    try:
        items = _web_search(query, num=5)
        results = [
            {"name": it.get("title", ""), "info": it.get("snippet", "")[:220], "url": it.get("link", "")}
            for it in items
        ]
        return {"ok": True, "data": results or [{"name": query, "info": "Nenhum resultado encontrado na internet."}]}
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": f"Falha na busca web: {str(e)}"}


def _search_company_details(args, user):
    """Busca detalhes de uma empresa na internet: endereço, telefone, CNPJ, site."""
    import re

    company_name = args.get("company_name", "").strip()
    if not company_name:
        return {"ok": False, "error": "Nome da empresa não informado."}

    details = {"company": company_name}

    try:
        general_items = _web_search(f"{company_name} empresa endereço telefone CNPJ site oficial", num=5)
        addr_items = _web_search(f"{company_name} sede endereço rua cidade estado CEP", num=5)

        general_text = " ".join(f"{it.get('title', '')} {it.get('snippet', '')}" for it in general_items)
        addr_text = " ".join(f"{it.get('title', '')} {it.get('snippet', '')}" for it in addr_items)
        all_text = f"{general_text} {addr_text}"

        # CNPJ
        cnpj = re.search(r'\d{2}[\.\s]?\d{3}[\.\s]?\d{3}[\/\s]?\d{4}[\-\s]?\d{2}', all_text)
        if cnpj:
            details["cnpj"] = cnpj.group(0).strip()

        # Telefone
        phone = re.search(r'(?:\+55\s?)?(?:\(?\d{2}\)?\s?)(?:9\s?)?\d{4,5}[\-\s]?\d{4}', all_text)
        if phone:
            details["phone"] = phone.group(0).strip()

        # Site (prioriza o link do primeiro resultado geral, que costuma ser o site oficial)
        if general_items and general_items[0].get("link"):
            details["website"] = general_items[0]["link"]
        else:
            site = re.search(r'(?:www\.|https?://)[a-zA-Z0-9\-\.]+\.[a-z]{2,}(?:/[^\s]*)?', all_text)
            if site:
                details["website"] = site.group(0).strip()

        # Resumo/descrição
        if general_items and general_items[0].get("snippet"):
            details["description"] = general_items[0]["snippet"][:300]

        # CEP
        cep = re.search(r'\d{5}[\-\s]?\d{3}', addr_text)
        if cep:
            details["cep"] = cep.group(0).strip()

        # Endereço (Rua/Av + número)
        address = re.search(r'(?:Rua|Av\.?|Avenida|Alameda|Estrada|Travessa)[^,\n\.]{5,60}', addr_text, re.IGNORECASE)
        if address:
            details["address"] = address.group(0).strip()

        # Cidade/Estado
        city = re.search(r'(?:São Paulo|Rio de Janeiro|Brasília|Belo Horizonte|Salvador|Curitiba|Manaus|Fortaleza|[A-Z][a-zÀ-ú]+(?:\s[A-Z][a-zÀ-ú]+)?)\s*[\-–,]\s*[A-Z]{2}', addr_text)
        if city:
            details["city_state"] = city.group(0).strip()

        return {"ok": True, "data": details}

    except ValueError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": f"Não foi possível buscar detalhes: {str(e)}"}


def _search_all_contacts(args, user):
    from .models import ContactClient, ContactJumper
    from django.db.models import Q
    name = args.get("name", "").strip()
    if not name:
        return {"ok": False, "error": "Nome não informado."}

    clients_contacts = ContactClient.objects.filter(
        name__icontains=name, is_active=True
    ).order_by('client_name', 'name')[:20]

    jumper_contacts = ContactJumper.objects.filter(
        name__icontains=name, is_active=True
    ).order_by('name')[:20]

    result = []
    for c in clients_contacts:
        entry = {"type": "client_contact", "id": c.id, "name": c.name, "client": c.client_name or ""}
        if c.hub_name:
            entry["hub"] = c.hub_name
        result.append(entry)

    for c in jumper_contacts:
        result.append({"type": "jumper", "id": c.id, "name": c.name, "role": c.role or ""})

    return {"ok": True, "data": result}


def _search_client(args, user):
    from .models import Client
    import difflib
    import unicodedata

    def _norm(s):
        s = unicodedata.normalize('NFKD', s or '')
        s = ''.join(ch for ch in s if not unicodedata.combining(ch))
        return s.lower().strip()

    name = args.get("name", "").strip()
    if not name:
        return {"ok": False, "error": "Nome não informado."}

    # 1) Busca direta por substring — cobre a maioria dos casos
    #    (ex: "bain" encontra "Bain & Company", "banco" encontra todos os "Banco X").
    clients = list(Client.objects.filter(name__icontains=name).order_by('name')[:10])

    # 2) Nada encontrado e o termo tem mais de uma palavra? Tenta casar cada palavra
    #    separadamente (ex: "Bain Company" -> bate com "Bain & Company", que não contém
    #    o termo completo como substring por causa do "&").
    if not clients:
        words = [w for w in name.split() if len(w) >= 3]
        if words:
            q = Q()
            for w in words:
                q &= Q(name__icontains=w)
            clients = list(Client.objects.filter(q).order_by('name')[:10])

    # 3) Ainda nada? Busca por aproximação (fuzzy) contra todos os clientes cadastrados,
    #    para sugerir os nomes mais parecidos e deixar o usuário escolher/confirmar.
    if not clients:
        target = _norm(name)
        scored = []
        for c in Client.objects.all().only('id', 'name', 'email'):
            ratio = difflib.SequenceMatcher(None, target, _norm(c.name)).ratio()
            if ratio >= 0.6:
                scored.append((ratio, c))
        scored.sort(key=lambda t: t[0], reverse=True)
        clients = [c for _, c in scored[:5]]

    return {
        "ok": True,
        "data": [{"id": c.id, "name": c.name, "email": c.email or ""} for c in clients]
    }


def _get_client_details(args, user):
    from .models import Client, ContactClient, ClientHub
    from django.db.models import Q
    client_id = args.get("client_id")
    try:
        client = Client.objects.get(pk=client_id)
    except Client.DoesNotExist:
        return {"ok": False, "error": "Cliente não encontrado."}

    hub_ids = list(ClientHub.objects.filter(client_id=client_id).values_list('id', flat=True))

    # Todos os contatos: tanto do cliente principal quanto de qualquer hub/loja
    contacts_qs = ContactClient.objects.filter(
        Q(client_ref_id=client_id) | Q(hub_ref_id__in=hub_ids),
        is_active=True
    ).order_by('hub_name', 'name')

    contacts = []
    for i, c in enumerate(contacts_qs[:50], start=1):
        entry = {"num": i, "id": c.id, "name": c.name}
        if c.hub_name:
            entry["hub"] = c.hub_name
        contacts.append(entry)

    hubs = [{"id": h.id, "name": h.name} for h in ClientHub.objects.filter(client_id=client_id).order_by('name')]

    return {"ok": True, "data": {
        "client": {"id": client.id, "name": client.name},
        "hubs": hubs,
        "contacts": contacts,
    }}


def _list_ticket_statuses(args, user):
    from .models import TicketStatus
    qs = TicketStatus.objects.filter(is_active=True).order_by('order', 'name')
    return {"ok": True, "data": [
        {"num": i, "code": s.code, "name": s.name}
        for i, s in enumerate(qs, start=1)
    ]}


def _list_systems(args, user):
    from .models import System
    qs = System.objects.all().order_by('name')
    return {"ok": True, "data": [
        {"num": i, "id": s.id, "name": s.name}
        for i, s in enumerate(qs, start=1)
    ]}


def _list_ticket_types(args, user):
    from .models import TicketType
    qs = TicketType.objects.all().order_by('name')
    return {"ok": True, "data": [
        {"num": i, "id": t.id, "name": t.name}
        for i, t in enumerate(qs, start=1)
    ]}


def _list_jumper_contacts(args, user):
    from .models import ContactJumper
    qs = ContactJumper.objects.filter(is_active=True).order_by('name')[:30]
    return {"ok": True, "data": [
        {"num": i, "id": c.id, "name": c.name, "role": c.role or ""}
        for i, c in enumerate(qs, start=1)
    ]}


def _list_equipments(args, user):
    from .models import Equipment
    name = (args.get("name") or "").strip()
    qs = Equipment.objects.select_related('equipment_type').order_by('name')
    if name:
        qs = qs.filter(name__icontains=name)
    qs = qs[:30]
    return {"ok": True, "data": [
        {"num": i, "id": e.id, "name": e.name, "type": e.equipment_type.name if e.equipment_type else ""}
        for i, e in enumerate(qs, start=1)
    ]}


def _list_equipment_types(args, user):
    from .models import EquipmentType
    qs = EquipmentType.objects.all().order_by('name')
    return {"ok": True, "data": [
        {"num": i, "id": t.id, "name": t.name}
        for i, t in enumerate(qs, start=1)
    ]}


def _list_problem_types(args, user):
    from .models import ProblemType
    qs = ProblemType.objects.all().order_by('name')
    return {"ok": True, "data": [
        {"num": i, "id": t.id, "name": t.name}
        for i, t in enumerate(qs, start=1)
    ]}


def _get_ticket(args, user):
    from .models import Ticket
    number = str(args.get("ticket_number", "")).strip().lstrip("0") or "0"
    try:
        ticket = Ticket.objects.select_related('client', 'hub', 'contact_client_requester', 'contact_jumper_responsible', 'ticket_type', 'problem_type').get(id=int(number))
    except (Ticket.DoesNotExist, ValueError):
        # Tenta buscar pelo formatted_id
        tickets = Ticket.objects.filter(id__icontains=number)[:1]
        if not tickets:
            return {"ok": False, "error": f"OS #{number} não encontrada."}
        ticket = tickets[0]

    return {
        "ok": True,
        "data": {
            "id": ticket.id,
            "formatted_id": ticket.formatted_id,
            "client": ticket.client.name if ticket.client else None,
            "client_id": ticket.client_id,
            "hub": ticket.hub.name if ticket.hub else None,
            "hub_id": ticket.hub_id,
            "status": ticket.status,
            "description": ticket.description,
            "final_description": ticket.final_description or "",
            "start_date": timezone.localtime(ticket.start_date).strftime("%d/%m/%Y %H:%M") if ticket.start_date else None,
            "deadline": timezone.localtime(ticket.deadline).strftime("%d/%m/%Y %H:%M") if ticket.deadline else None,
            "requester": ticket.contact_client_requester.name if ticket.contact_client_requester else None,
            "responsible": ticket.contact_jumper_responsible.name if ticket.contact_jumper_responsible else None,
            "ticket_type": ticket.ticket_type.name if ticket.ticket_type else None,
            "problem_type": ticket.problem_type.name if ticket.problem_type else None,
            "equipments": [e.name for e in ticket.equipments.all()],
        }
    }


def _create_ticket(args, user):
    from .models import Ticket, Client, ClientHub, TicketType, System, ContactClient, ContactJumper, ProblemType, Equipment

    role = getattr(getattr(user, 'profile', None), 'role', None)
    if not role:
        return {"ok": False, "error": "Usuário sem perfil definido no sistema."}

    # Campos obrigatórios com mensagens claras
    missing = []
    if not args.get("client_id"):       missing.append("cliente")
    if not args.get("contact_client_requester_id"): missing.append("solicitante")
    if not args.get("contact_jumper_responsible_id"): missing.append("responsável JumperFour")
    if not args.get("status"):          missing.append("status")
    if not args.get("start_date"):      missing.append("data de início")
    if not args.get("deadline"):        missing.append("prazo")
    if not args.get("description", "").strip(): missing.append("descrição")
    if missing:
        return {"ok": False, "error": f"Campos obrigatórios não preenchidos: {', '.join(missing)}."}

    try:
        client = Client.objects.get(pk=args["client_id"])
    except Client.DoesNotExist:
        return {"ok": False, "error": f"Cliente ID {args['client_id']} não encontrado no sistema."}

    try:
        requester = ContactClient.objects.get(pk=args["contact_client_requester_id"])
    except ContactClient.DoesNotExist:
        return {"ok": False, "error": f"Solicitante ID {args['contact_client_requester_id']} não encontrado."}

    try:
        responsible = ContactJumper.objects.get(pk=args["contact_jumper_responsible_id"])
    except ContactJumper.DoesNotExist:
        return {"ok": False, "error": f"Responsável JumperFour ID {args['contact_jumper_responsible_id']} não encontrado."}

    start_date = _parse_dt(args.get("start_date", ""))
    deadline   = _parse_dt(args.get("deadline", ""))
    if not start_date:
        return {"ok": False, "error": f"Data de início inválida: '{args.get('start_date')}'. Use DD/MM/YYYY ou YYYY-MM-DD (hora é opcional, se omitida usa a atual)."}
    if not deadline:
        return {"ok": False, "error": f"Prazo inválido: '{args.get('deadline')}'. Use DD/MM/YYYY ou YYYY-MM-DD (hora é opcional, se omitida usa a atual)."}

    ticket = Ticket(
        client=client,
        status=args.get("status", "open"),
        description=args.get("description", ""),
        start_date=start_date,
        deadline=deadline,
        contact_client_requester=requester,
        contact_jumper_responsible=responsible,
        final_description=args.get("final_description", "") or "",
        leankeep_id=args.get("leankeep_id", "") or "",
        created_by=user,
    )

    if args.get("hub_id"):
        try:
            ticket.hub = ClientHub.objects.get(pk=args["hub_id"])
        except ClientHub.DoesNotExist:
            return {"ok": False, "error": f"Hub/loja ID {args['hub_id']} não encontrado."}

    if args.get("ticket_type_id"):
        try:
            ticket.ticket_type = TicketType.objects.get(pk=args["ticket_type_id"])
        except TicketType.DoesNotExist:
            return {"ok": False, "error": f"Tipo de chamado ID {args['ticket_type_id']} não encontrado."}

    if args.get("problem_type_id"):
        try:
            ticket.problem_type = ProblemType.objects.get(pk=args["problem_type_id"])
        except ProblemType.DoesNotExist:
            return {"ok": False, "error": f"Tipo de problema ID {args['problem_type_id']} não encontrado."}

    try:
        ticket.save()
    except Exception as e:
        return {"ok": False, "error": f"Erro ao salvar a OS no banco de dados: {str(e)}"}

    if args.get("system_id"):
        try:
            ticket.systems.add(System.objects.get(pk=args["system_id"]))
        except System.DoesNotExist:
            pass  # sistema é opcional — não bloqueia

    equipment_ids = args.get("equipment_ids") or []
    if equipment_ids:
        equipments = Equipment.objects.filter(pk__in=equipment_ids)
        ticket.equipments.set(equipments)

    return {"ok": True, "data": {"id": ticket.id, "formatted_id": ticket.formatted_id, "url": f"/tickets/?open={ticket.id}"}}


def _validate_ticket_fields(fields):
    """Valida os campos de uma OS sem criar nada — usado para conferir cada item
    de um lote (create_ticket_batch) antes da confirmação final. Espelha as
    mesmas checagens de _create_ticket. Retorna (ok, error, preview)."""
    from .models import Client, ContactClient, ContactJumper, ClientHub, TicketType, ProblemType

    missing = []
    if not fields.get("client_id"): missing.append("cliente")
    if not fields.get("contact_client_requester_id"): missing.append("solicitante")
    if not fields.get("contact_jumper_responsible_id"): missing.append("responsável JumperFour")
    if not fields.get("status"): missing.append("status")
    if not fields.get("start_date"): missing.append("data de início")
    if not fields.get("deadline"): missing.append("prazo")
    if not (fields.get("description") or "").strip(): missing.append("descrição")
    if missing:
        return False, f"Campos obrigatórios não preenchidos: {', '.join(missing)}.", None

    preview = {"description": fields.get("description"), "status": fields.get("status")}

    try:
        preview["client"] = Client.objects.get(pk=fields["client_id"]).name
    except Client.DoesNotExist:
        return False, f"Cliente ID {fields['client_id']} não encontrado.", None
    try:
        preview["requester"] = ContactClient.objects.get(pk=fields["contact_client_requester_id"]).name
    except ContactClient.DoesNotExist:
        return False, f"Solicitante ID {fields['contact_client_requester_id']} não encontrado.", None
    try:
        preview["responsible"] = ContactJumper.objects.get(pk=fields["contact_jumper_responsible_id"]).name
    except ContactJumper.DoesNotExist:
        return False, f"Responsável JumperFour ID {fields['contact_jumper_responsible_id']} não encontrado.", None

    start_date = _parse_dt(fields.get("start_date", ""))
    deadline = _parse_dt(fields.get("deadline", ""))
    if not start_date:
        return False, f"Data de início inválida: '{fields.get('start_date')}'.", None
    if not deadline:
        return False, f"Prazo inválido: '{fields.get('deadline')}'.", None
    preview["start_date"] = fields.get("start_date")
    preview["deadline"] = fields.get("deadline")

    if fields.get("hub_id"):
        try:
            preview["hub"] = ClientHub.objects.get(pk=fields["hub_id"]).name
        except ClientHub.DoesNotExist:
            return False, f"Hub/loja ID {fields['hub_id']} não encontrado.", None
    if fields.get("ticket_type_id"):
        try:
            preview["ticket_type"] = TicketType.objects.get(pk=fields["ticket_type_id"]).name
        except TicketType.DoesNotExist:
            return False, f"Tipo de chamado ID {fields['ticket_type_id']} não encontrado.", None
    if fields.get("problem_type_id"):
        try:
            preview["problem_type"] = ProblemType.objects.get(pk=fields["problem_type_id"]).name
        except ProblemType.DoesNotExist:
            return False, f"Tipo de problema ID {fields['problem_type_id']} não encontrado.", None

    return True, None, preview


_BATCH_ITEM_FIELDS = (
    "client_id", "hub_id", "status", "description", "start_date", "deadline",
    "contact_client_requester_id", "contact_jumper_responsible_id", "ticket_type_id",
    "system_id", "problem_type_id", "equipment_ids", "leankeep_id", "final_description",
)


def _start_ticket_batch(args, user):
    from .models import AITicketBatchDraft

    total_count = args.get("total_count")
    if not total_count or total_count < 1:
        return {"ok": False, "error": "Informe total_count (quantidade de OS a criar) maior que zero."}
    if total_count > 50:
        return {"ok": False, "error": "Lotes acima de 50 OS não são suportados de uma vez — sugira dividir em lotes menores."}

    existing = AITicketBatchDraft.objects.filter(user=user, status='draft').first()
    if existing:
        collected = sum(1 for it in existing.items if it)
        return {"ok": False, "error": (
            f"Já existe um lote em andamento (ID {existing.id}, {collected}/{existing.total_count} "
            "preenchidas). Confirme (confirm_ticket_batch) ou cancele (cancel_ticket_batch) esse lote antes de iniciar outro."
        )}

    shared_defaults = args.get("shared_defaults") or {}
    batch = AITicketBatchDraft.objects.create(
        user=user,
        total_count=total_count,
        shared_defaults=shared_defaults,
        items=[None] * total_count,
    )
    return {"ok": True, "data": {
        "batch_id": batch.id,
        "total_count": total_count,
        "collected": 0,
        "pending": total_count,
    }}


def _add_or_update_batch_item(args, user):
    from .models import AITicketBatchDraft

    batch_id = args.get("batch_id")
    index = args.get("index")
    if not batch_id or not index:
        return {"ok": False, "error": "batch_id e index são obrigatórios."}

    try:
        batch = AITicketBatchDraft.objects.get(pk=batch_id, user=user, status='draft')
    except AITicketBatchDraft.DoesNotExist:
        return {"ok": False, "error": "Lote não encontrado ou já finalizado."}

    if index < 1 or index > batch.total_count:
        return {"ok": False, "error": f"index deve ser entre 1 e {batch.total_count}."}

    # Mescla: padrão do lote < item já preenchido antes < campos novos informados agora
    merged = dict(batch.shared_defaults or {})
    existing_item = batch.items[index - 1] or {}
    merged.update(existing_item)
    for key in _BATCH_ITEM_FIELDS:
        if key in args:
            merged[key] = args[key]

    ok, error, preview = _validate_ticket_fields(merged)
    if not ok:
        return {"ok": False, "error": error}

    items = list(batch.items)
    items[index - 1] = merged
    batch.items = items
    batch.save(update_fields=['items', 'updated_at'])

    collected = sum(1 for it in batch.items if it)
    return {"ok": True, "data": {
        "batch_id": batch.id,
        "index": index,
        "preview": preview,
        "collected": collected,
        "pending": batch.total_count - collected,
        "total_count": batch.total_count,
    }}


def _list_batch_status(args, user):
    from .models import AITicketBatchDraft

    batch_id = args.get("batch_id")
    try:
        batch = AITicketBatchDraft.objects.get(pk=batch_id, user=user)
    except AITicketBatchDraft.DoesNotExist:
        return {"ok": False, "error": "Lote não encontrado."}

    items_preview = []
    for i, item in enumerate(batch.items, start=1):
        if not item:
            items_preview.append({"index": i, "filled": False})
            continue
        ok, error, preview = _validate_ticket_fields(item)
        items_preview.append({"index": i, "filled": True, "valid": ok, "error": error, "preview": preview})

    collected = sum(1 for it in batch.items if it)
    return {"ok": True, "data": {
        "batch_id": batch.id,
        "status": batch.status,
        "total_count": batch.total_count,
        "collected": collected,
        "pending": batch.total_count - collected,
        "items": items_preview,
    }}


def _cancel_ticket_batch(args, user):
    from .models import AITicketBatchDraft

    batch_id = args.get("batch_id")
    try:
        batch = AITicketBatchDraft.objects.get(pk=batch_id, user=user, status='draft')
    except AITicketBatchDraft.DoesNotExist:
        return {"ok": False, "error": "Lote não encontrado ou já finalizado."}

    batch.delete()
    return {"ok": True, "data": {"message": "Lote cancelado. Nenhuma OS foi criada."}}


def _confirm_ticket_batch(args, user):
    from .models import AITicketBatchDraft

    batch_id = args.get("batch_id")
    try:
        batch = AITicketBatchDraft.objects.get(pk=batch_id, user=user, status='draft')
    except AITicketBatchDraft.DoesNotExist:
        return {"ok": False, "error": "Lote não encontrado ou já finalizado."}

    missing = [i + 1 for i, it in enumerate(batch.items) if not it]
    if missing:
        return {"ok": False, "error": f"Ainda faltam preencher as OS de posição {', '.join(map(str, missing))} antes de confirmar."}

    created, failed = [], []
    for i, item in enumerate(batch.items, start=1):
        result = _create_ticket(item, user)
        if result.get("ok"):
            created.append({"index": i, **result["data"]})
        else:
            failed.append({"index": i, "error": result.get("error")})

    batch.status = 'confirmed'
    batch.save(update_fields=['status', 'updated_at'])

    return {"ok": True, "data": {
        "batch_id": batch.id,
        "created_count": len(created),
        "failed_count": len(failed),
        "created": created,
        "failed": failed,
    }}


def _update_ticket(args, user):
    from .models import Ticket, TicketType, ContactClient, ContactJumper, ProblemType, Equipment

    try:
        ticket = Ticket.objects.get(pk=args["ticket_id"])
    except Ticket.DoesNotExist:
        return {"ok": False, "error": f"OS ID {args.get('ticket_id')} não encontrada no sistema."}

    if "status" in args:
        ticket.status = args["status"]
    if "description" in args:
        ticket.description = args["description"]
    if "final_description" in args:
        ticket.final_description = args["final_description"]
    if "start_date" in args:
        start_date = _parse_dt(args["start_date"])
        if not start_date:
            return {"ok": False, "error": f"Data de início inválida: '{args['start_date']}'. Use DD/MM/YYYY ou YYYY-MM-DD."}
        ticket.start_date = start_date
    if "deadline" in args:
        deadline = _parse_dt(args["deadline"])
        if not deadline:
            return {"ok": False, "error": f"Prazo inválido: '{args['deadline']}'. Use DD/MM/YYYY ou YYYY-MM-DD."}
        ticket.deadline = deadline
    if "ticket_type_id" in args:
        try:
            ticket.ticket_type = TicketType.objects.get(pk=args["ticket_type_id"])
        except TicketType.DoesNotExist:
            return {"ok": False, "error": f"Tipo de chamado ID {args['ticket_type_id']} não encontrado."}
    if "contact_client_requester_id" in args:
        try:
            ticket.contact_client_requester = ContactClient.objects.get(pk=args["contact_client_requester_id"])
        except ContactClient.DoesNotExist:
            return {"ok": False, "error": f"Solicitante ID {args['contact_client_requester_id']} não encontrado."}
    if "contact_jumper_responsible_id" in args:
        try:
            ticket.contact_jumper_responsible = ContactJumper.objects.get(pk=args["contact_jumper_responsible_id"])
        except ContactJumper.DoesNotExist:
            return {"ok": False, "error": f"Responsável ID {args['contact_jumper_responsible_id']} não encontrado."}
    if "problem_type_id" in args:
        try:
            ticket.problem_type = ProblemType.objects.get(pk=args["problem_type_id"])
        except ProblemType.DoesNotExist:
            return {"ok": False, "error": f"Tipo de problema ID {args['problem_type_id']} não encontrado."}

    try:
        ticket.save()
    except Exception as e:
        return {"ok": False, "error": f"Erro ao salvar alterações no banco de dados: {str(e)}"}

    if "equipment_ids" in args:
        equipments = Equipment.objects.filter(pk__in=args.get("equipment_ids") or [])
        ticket.equipments.set(equipments)

    return {"ok": True, "data": {"id": ticket.id, "formatted_id": ticket.formatted_id}}


def _add_ticket_evolution(args, user):
    from .models import Ticket, TicketUpdate
    try:
        ticket = Ticket.objects.get(pk=args["ticket_id"])
    except Ticket.DoesNotExist:
        return {"ok": False, "error": "OS não encontrada."}

    description = args.get("description", "").strip()
    if not description:
        return {"ok": False, "error": "Descrição da evolução não pode ser vazia."}

    update = TicketUpdate.objects.create(
        ticket=ticket,
        created_by=user,
        description=description,
    )
    return {"ok": True, "data": {"update_id": update.id, "ticket_id": ticket.id, "formatted_id": ticket.formatted_id}}


def _delete_ticket(args, user):
    from .models import Ticket, ShiftHandoverEntry
    role = getattr(getattr(user, 'profile', None), 'role', None)
    if role not in ('admin', 'super_admin'):
        return {"ok": False, "error": "Permissão negada. Somente administradores podem excluir OS."}

    try:
        ticket = Ticket.objects.get(pk=args["ticket_id"])
    except Ticket.DoesNotExist:
        return {"ok": False, "error": "OS não encontrada."}

    formatted_id = ticket.formatted_id
    ShiftHandoverEntry.objects.filter(ticket=ticket).delete()
    ticket.delete()
    return {"ok": True, "data": {"message": f"OS #{formatted_id} excluída com sucesso."}}


def _create_client(args, user):
    from .models import Client
    role = getattr(getattr(user, 'profile', None), 'role', None)
    if role not in ('admin', 'super_admin'):
        return {"ok": False, "error": "Permissão negada. Somente administradores podem cadastrar clientes."}

    name = args.get("name", "").strip().upper()
    if not name:
        return {"ok": False, "error": "Nome do cliente é obrigatório."}

    if Client.objects.filter(name__iexact=name).exists():
        return {"ok": False, "error": f"Já existe um cliente com o nome '{name}'."}

    client = Client.objects.create(
        name=name,
        email=args.get("email", "") or "",
        phone=args.get("phone", "") or "",
        address=args.get("address", "") or "",
    )
    return {"ok": True, "data": {"id": client.id, "name": client.name}}


def _update_client(args, user):
    from .models import Client
    role = getattr(getattr(user, 'profile', None), 'role', None)
    if role not in ('admin', 'super_admin'):
        return {"ok": False, "error": "Permissão negada. Somente administradores podem editar clientes."}

    client_id = args.get("client_id")
    if not client_id:
        return {"ok": False, "error": "ID do cliente é obrigatório."}

    try:
        client = Client.objects.get(pk=client_id)
    except Client.DoesNotExist:
        return {"ok": False, "error": f"Cliente ID {client_id} não encontrado."}

    if "name" in args:
        name = args.get("name", "").strip().upper()
        if not name:
            return {"ok": False, "error": "Nome do cliente não pode ser vazio."}
        if Client.objects.filter(name__iexact=name).exclude(pk=client_id).exists():
            return {"ok": False, "error": f"Já existe outro cliente com o nome '{name}'."}
        client.name = name

    if "email" in args:
        client.email = args.get("email", "") or ""

    if "phone" in args:
        client.phone = args.get("phone", "") or ""

    if "address" in args:
        client.address = args.get("address", "") or ""

    try:
        client.save()
    except Exception as e:
        return {"ok": False, "error": f"Erro ao salvar alterações: {str(e)}"}

    return {"ok": True, "data": {"id": client.id, "name": client.name}}


def _clear_chat(args, user):
    # A exclusão real das sessões é feita pela view (views_ai.py) depois que a
    # resposta desta requisição for salva — apagar a sessão aqui, no meio da
    # requisição, deixaria a sessão atual órfã e quebraria a gravação da
    # resposta do assistente (FOREIGN KEY constraint failed).
    return {"ok": True, "clear_chat": True, "data": {"message": "Histórico limpo! 🧹 Começamos do zero. Como posso ajudar?"}}


AI_MEMORY_MAX_CHARS = 4000


def _remember_user_preference(args, user):
    from .models import AIUserMemory
    note = (args.get("note") or "").strip()
    if not note:
        return {"ok": False, "error": "note é obrigatório."}

    memory, _ = AIUserMemory.objects.get_or_create(user=user)
    lines = [l.strip() for l in memory.notes.split("\n") if l.strip()]
    lines.append(f"- {note}")

    # Remove duplicatas (mantém a mais recente) sem alterar a ordem das demais
    seen = set()
    deduped = []
    for line in reversed(lines):
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(line)
    deduped.reverse()

    # Se estourar o limite, descarta as notas mais antigas primeiro
    while len("\n".join(deduped)) > AI_MEMORY_MAX_CHARS and len(deduped) > 1:
        deduped.pop(0)

    memory.notes = "\n".join(deduped)
    memory.save(update_fields=['notes', 'updated_at'])
    return {"ok": True, "data": {"saved": note}}


def _forget_user_preference(args, user):
    from .models import AIUserMemory
    clear_all = bool(args.get("clear_all"))
    note_contains = (args.get("note_contains") or "").strip().lower()

    try:
        memory = AIUserMemory.objects.get(user=user)
    except AIUserMemory.DoesNotExist:
        return {"ok": True, "data": {"message": "Não havia nada memorizado ainda."}}

    if clear_all:
        memory.notes = ""
        memory.save(update_fields=['notes', 'updated_at'])
        return {"ok": True, "data": {"message": "Toda a memória sobre você foi apagada."}}

    if not note_contains:
        return {"ok": False, "error": "Informe note_contains ou clear_all=true."}

    lines = [l for l in memory.notes.split("\n") if l.strip()]
    kept = [l for l in lines if note_contains not in l.lower()]
    removed_count = len(lines) - len(kept)
    memory.notes = "\n".join(kept)
    memory.save(update_fields=['notes', 'updated_at'])
    return {"ok": True, "data": {"removed_count": removed_count}}


def _check_pending_alerts(args, user):
    """Verifica mensagens diretas não lidas e alertas de passagem de turno
    pendentes para o usuário ATUAL — usado para o Jota4 avisar proativamente
    ao logar/abrir o chat."""
    from .models import Notification, ShiftHandoverEntryAlert

    messages_qs = (
        Notification.objects.filter(recipient=user, notification_type='message', is_read=False)
        .select_related('sender')
        .order_by('-created_at')
    )
    unread_messages = [
        {
            "notification_id": n.id,
            "sender_id": n.sender_id,
            "sender_name": n.sender.get_full_name() or n.sender.username if n.sender else "Sistema",
            "title": n.title,
            "preview": (n.message or "")[:120],
            "created_at": timezone.localtime(n.created_at).strftime("%d/%m/%Y %H:%M"),
        }
        for n in messages_qs
    ]

    alerts_qs = (
        ShiftHandoverEntryAlert.objects.filter(target_user=user, acknowledged_at__isnull=True)
        .select_related('entry', 'entry__created_by', 'entry__handover')
        .order_by('-created_at')
    )
    pending_handover_alerts = [
        {
            "alert_id": a.id,
            "entry_id": a.entry_id,
            "author_name": (a.entry.created_by.get_full_name() or a.entry.created_by.username) if a.entry.created_by else "Sistema",
            "priority": a.get_priority_display(),
            "preview": (a.entry.text or "")[:120],
            "shift_date": a.entry.handover.shift_date.strftime("%d/%m/%Y") if a.entry.handover else "",
            "created_at": timezone.localtime(a.created_at).strftime("%d/%m/%Y %H:%M"),
        }
        for a in alerts_qs
    ]

    return {"ok": True, "data": {
        "unread_messages": unread_messages,
        "pending_handover_alerts": pending_handover_alerts,
        "has_pending": bool(unread_messages or pending_handover_alerts),
    }}


def _get_message_content(args, user):
    from .models import Notification
    notification_id = args.get("notification_id")
    if not notification_id:
        return {"ok": False, "error": "notification_id é obrigatório."}
    try:
        n = Notification.objects.select_related('sender').get(pk=notification_id, recipient=user)
    except Notification.DoesNotExist:
        return {"ok": False, "error": "Mensagem não encontrada."}
    return {"ok": True, "data": {
        "notification_id": n.id,
        "sender_id": n.sender_id,
        "sender_name": (n.sender.get_full_name() or n.sender.username) if n.sender else "Sistema",
        "title": n.title,
        "message": n.message,
        "is_read": n.is_read,
        "created_at": timezone.localtime(n.created_at).strftime("%d/%m/%Y %H:%M"),
    }}


def _mark_message_read(args, user):
    from .models import Notification
    notification_id = args.get("notification_id")
    if not notification_id:
        return {"ok": False, "error": "notification_id é obrigatório."}
    try:
        n = Notification.objects.get(pk=notification_id, recipient=user)
    except Notification.DoesNotExist:
        return {"ok": False, "error": "Mensagem não encontrada."}
    if not n.is_read:
        n.is_read = True
        n.read_at = timezone.now()
        n.save(update_fields=['is_read', 'read_at'])
    return {"ok": True, "data": {"notification_id": n.id, "message": "Mensagem marcada como lida."}}


def _acknowledge_handover_alert(args, user):
    from .models import ShiftHandoverEntryAlert
    entry_id = args.get("entry_id")
    if not entry_id:
        return {"ok": False, "error": "entry_id é obrigatório."}
    qs = ShiftHandoverEntryAlert.objects.filter(entry_id=entry_id, target_user=user, acknowledged_at__isnull=True)
    updated = qs.update(acknowledged_at=timezone.now())
    if not updated:
        return {"ok": False, "error": "Não havia alerta pendente para dar baixa nessa anotação."}
    return {"ok": True, "data": {"entry_id": entry_id, "message": "Baixa dada no alerta da passagem de turno."}}


def _get_current_shift_handover():
    """Encontra (ou cria) o ShiftHandover do turno vigente agora, replicando a mesma
    lógica de virada de turno usada em TaskListView._build_shifts (tela de Tasks) —
    considera turno noturno cruzando meia-noite, se estiver habilitado."""
    from datetime import datetime, timedelta, time as dtime
    from .models import SystemSettings, ShiftHandover

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    day_start = settings_obj.day_shift_start or dtime(8, 0)
    day_end = settings_obj.day_shift_end or dtime(20, 0)
    enable_night = bool(settings_obj.enable_night_shift)
    night_start = settings_obj.night_shift_start or dtime(20, 0)
    night_end = settings_obj.night_shift_end or dtime(8, 0)

    def aware(dt):
        try:
            return timezone.make_aware(dt) if timezone.is_naive(dt) else dt
        except Exception:
            return dt

    now = timezone.localtime(timezone.now())
    today = timezone.localdate()

    candidates = []
    for i in range(0, 3):  # hoje + 2 dias anteriores cobre qualquer virada de turno noturno
        d = today - timedelta(days=i)
        if enable_night:
            ns = aware(datetime.combine(d, night_start))
            end_day = d if night_end >= night_start else (d + timedelta(days=1))
            ne = aware(datetime.combine(end_day, night_end))
            candidates.append({'date': d, 'type': 'night', 'start': ns, 'end': ne})
        ds = aware(datetime.combine(d, day_start))
        de = aware(datetime.combine(d, day_end))
        candidates.append({'date': d, 'type': 'day', 'start': ds, 'end': de})

    current = next((c for c in candidates if c['start'] <= now < c['end']), None)
    if not current:
        started = [c for c in candidates if c['start'] <= now]
        current = max(started, key=lambda c: c['start']) if started else candidates[0]

    handover, _ = ShiftHandover.objects.get_or_create(shift_date=current['date'], shift_type=current['type'])
    return handover


def _create_handover_entry(args, user):
    from .models import ShiftHandoverEntry

    text = (args.get("text") or "").strip()
    if not text:
        return {"ok": False, "error": "Texto da anotação não informado."}
    if len(text) > 4000:
        return {"ok": False, "error": "Texto muito longo (máximo 4000 caracteres)."}

    handover = _get_current_shift_handover()
    entry = ShiftHandoverEntry.objects.create(
        handover=handover,
        created_by=user,
        text=text,
    )
    return {"ok": True, "data": {
        "entry_id": entry.id,
        "text": entry.text,
        "shift_date": handover.shift_date.strftime("%d/%m/%Y"),
        "shift_type": handover.get_shift_type_display(),
    }}


def _notify_handover_entry(args, user):
    from .models import ShiftHandoverEntry, ShiftHandoverEntryAlert

    entry_id = args.get("entry_id")
    if not entry_id:
        return {"ok": False, "error": "entry_id é obrigatório."}
    try:
        entry = ShiftHandoverEntry.objects.get(pk=entry_id)
    except ShiftHandoverEntry.DoesNotExist:
        return {"ok": False, "error": f"Anotação ID {entry_id} não encontrada."}

    target, error = _resolve_user(args.get("recipient_id"), args.get("recipient_name"), user)
    if error:
        return {"ok": False, "error": error}

    priority = (args.get("priority") or "medium").strip()
    if priority not in ("high", "medium", "low"):
        priority = "medium"

    alert, created = ShiftHandoverEntryAlert.objects.get_or_create(
        entry=entry, target_user=target,
        defaults={"created_by": user, "priority": priority},
    )
    if not created:
        # Já existia (talvez já reconhecido) — reativa como pendente de novo
        alert.acknowledged_at = None
        if not alert.created_by_id:
            alert.created_by = user
        alert.priority = priority
        alert.save(update_fields=["acknowledged_at", "created_by", "priority"])

    target_display = target.get_full_name() or target.username
    return {"ok": True, "data": {
        "entry_id": entry.id,
        "target_user": target_display,
        "priority": alert.get_priority_display(),
        "message": f"{target_display} foi notificado(a) sobre a anotação — vai aparecer pra ele(a) automaticamente.",
    }}


def _send_message_to_user(args, user):
    """Envia uma mensagem direta (Notification) do usuário ATUAL para outro usuário
    do sistema — permite o Jota4 atuar como intermediário (ex: responder, em nome
    do usuário, a quem acabou de mandar uma mensagem pendente)."""
    from django.contrib.auth.models import User as DjangoUser
    from .models import Notification

    message = (args.get("message") or "").strip()
    if not message:
        return {"ok": False, "error": "message é obrigatório."}

    recipient_id = args.get("recipient_id")
    recipient_name = (args.get("recipient_name") or "").strip()

    recipient = None
    if recipient_id:
        recipient = DjangoUser.objects.filter(pk=recipient_id, is_active=True).first()
        if not recipient:
            return {"ok": False, "error": f"Destinatário ID {recipient_id} não encontrado ou inativo."}
    elif recipient_name:
        matches = list(DjangoUser.objects.filter(
            Q(first_name__icontains=recipient_name) | Q(username__icontains=recipient_name),
            is_active=True
        )[:2])
        if not matches:
            return {"ok": False, "error": f"Nenhum usuário ativo encontrado com o nome '{recipient_name}'."}
        if len(matches) > 1:
            return {"ok": False, "error": f"Mais de um usuário encontrado com o nome '{recipient_name}'. Peça para o usuário confirmar o nome completo ou use recipient_id."}
        recipient = matches[0]
    else:
        return {"ok": False, "error": "Informe recipient_id ou recipient_name."}

    if recipient.id == user.id:
        return {"ok": False, "error": "Não é possível enviar uma mensagem para si mesmo."}

    title = (args.get("title") or f"Mensagem de {user.get_full_name() or user.username} (via Jota4)").strip()

    Notification.objects.create(
        recipient=recipient,
        sender=user,
        title=title,
        message=message,
        notification_type='message',
    )
    return {"ok": True, "data": {
        "recipient_name": recipient.get_full_name() or recipient.username,
        "message": "Mensagem enviada com sucesso.",
    }}


def _resolve_user(recipient_id, recipient_name, exclude_user):
    """Resolve um usuário ativo por ID ou nome/username, excluindo exclude_user.
    Retorna (user, error_message)."""
    from django.contrib.auth.models import User as DjangoUser
    if recipient_id:
        u = DjangoUser.objects.filter(pk=recipient_id, is_active=True).first()
        if not u:
            return None, f"Destinatário ID {recipient_id} não encontrado ou inativo."
        return u, None
    if recipient_name:
        matches = list(DjangoUser.objects.filter(
            Q(first_name__icontains=recipient_name) | Q(username__icontains=recipient_name),
            is_active=True
        ).exclude(pk=exclude_user.id)[:2])
        if not matches:
            return None, f"Nenhum usuário ativo encontrado com o nome '{recipient_name}'."
        if len(matches) > 1:
            return None, f"Mais de um usuário encontrado com o nome '{recipient_name}'. Peça para confirmar o nome completo ou use recipient_id."
        return matches[0], None
    return None, "Informe recipient_id ou recipient_name."


def _open_private_chat(args, user):
    """Sinaliza para o front-end abrir um popup de chat particular (estilo
    Messenger) com outro usuário — a ação de fato abrir a janela é feita pelo
    JS ao ver 'action': 'open_private_chat' na resposta desta tool."""
    from .models import PrivateChatThread, ActiveSession

    recipient, error = _resolve_user(args.get("recipient_id"), (args.get("recipient_name") or "").strip(), user)
    if error:
        return {"ok": False, "error": error}
    if recipient.id == user.id:
        return {"ok": False, "error": "Não é possível abrir um chat particular consigo mesmo."}

    a, b = sorted([user, recipient], key=lambda u: u.id)
    thread, _ = PrivateChatThread.objects.get_or_create(user_a=a, user_b=b)

    return {"ok": True, "data": {
        "action": "open_private_chat",
        "thread_id": thread.id,
        "recipient_id": recipient.id,
        "recipient_name": recipient.get_full_name() or recipient.username,
        "status": ActiveSession.get_status(recipient),
    }}


def _create_contact_client(args, user):
    from .models import ContactClient, Client, ClientHub
    name = args.get("name", "").strip().upper()
    if not name:
        return {"ok": False, "error": "Nome do contato é obrigatório."}

    client_id = args.get("client_id")
    hub_id = args.get("hub_id")

    client_name = ""
    hub_name = ""

    if client_id:
        try:
            c = Client.objects.get(pk=client_id)
            client_name = c.name
        except Client.DoesNotExist:
            return {"ok": False, "error": "Cliente não encontrado."}

    if hub_id:
        try:
            h = ClientHub.objects.get(pk=hub_id)
            hub_name = h.name
        except ClientHub.DoesNotExist:
            pass

    contact = ContactClient.objects.create(
        name=name,
        email=args.get("email", "") or "",
        phone=args.get("phone", "") or "",
        client_ref_id=client_id or None,
        client_name=client_name,
        hub_ref_id=hub_id or None,
        hub_name=hub_name,
        is_active=True,
    )
    return {"ok": True, "data": {"id": contact.id, "name": contact.name, "client": client_name, "hub": hub_name}}


def _create_contact_jumper(args, user):
    from .models import ContactJumper
    role = getattr(getattr(user, 'profile', None), 'role', None)
    if role not in ('admin', 'super_admin'):
        return {"ok": False, "error": "Permissão negada. Somente administradores podem cadastrar profissionais JumperFour."}

    name = args.get("name", "").strip().upper()
    if not name:
        return {"ok": False, "error": "Nome é obrigatório."}

    contact = ContactJumper.objects.create(
        name=name,
        email=args.get("email", "") or "",
        phone=args.get("phone", "") or "",
        department=args.get("department", "") or "",
        role=args.get("role", "") or "",
        is_active=True,
    )
    return {"ok": True, "data": {"id": contact.id, "name": contact.name}}


def _create_hub(args, user):
    from .models import ClientHub, Client
    role = getattr(getattr(user, 'profile', None), 'role', None)
    if role not in ('admin', 'super_admin'):
        return {"ok": False, "error": "Permissão negada. Somente administradores podem cadastrar hubs/lojas."}

    client_id = args.get("client_id")
    name = args.get("name", "").strip().upper()
    if not client_id or not name:
        return {"ok": False, "error": "Cliente e nome do hub são obrigatórios."}

    try:
        client = Client.objects.get(pk=client_id)
    except Client.DoesNotExist:
        return {"ok": False, "error": "Cliente não encontrado."}

    hub = ClientHub.objects.create(client=client, name=name)
    return {"ok": True, "data": {"id": hub.id, "name": hub.name, "client": client.name}}


def _create_equipment(args, user):
    from .models import Equipment, EquipmentType
    role = getattr(getattr(user, 'profile', None), 'role', None)
    if role not in ('admin', 'super_admin'):
        return {"ok": False, "error": "Permissão negada. Somente administradores podem cadastrar equipamentos."}

    name = args.get("name", "").strip()
    if not name:
        return {"ok": False, "error": "Nome do equipamento é obrigatório."}

    if Equipment.objects.filter(name__iexact=name).exists():
        return {"ok": False, "error": f"Já existe um equipamento com o nome '{name}'."}

    equipment_type = None
    equipment_type_id = args.get("equipment_type_id")
    if equipment_type_id:
        equipment_type = EquipmentType.objects.filter(pk=equipment_type_id).first()
        if not equipment_type:
            return {"ok": False, "error": "Tipo de equipamento não encontrado."}

    equipment = Equipment.objects.create(
        name=name,
        description=args.get("description", "") or "",
        equipment_type=equipment_type,
    )
    return {"ok": True, "data": {"id": equipment.id, "name": equipment.name}}


def _create_role(args, user):
    from .models import RoleLevel
    role = getattr(getattr(user, 'profile', None), 'role', None)
    if role not in ('admin', 'super_admin'):
        return {"ok": False, "error": "Permissão negada. Somente administradores podem criar níveis."}

    name = args.get("name", "").strip()
    if not name:
        return {"ok": False, "error": "Nome do nível é obrigatório."}

    code = args.get("code", "").strip().lower() or name.lower().replace(" ", "_")

    if RoleLevel.objects.filter(code=code).exists():
        return {"ok": False, "error": f"Nível com código '{code}' já existe."}

    role_obj = RoleLevel.objects.create(name=name, code=code, is_active=True)
    return {"ok": True, "data": {"id": role_obj.id, "name": role_obj.name, "code": role_obj.code}}


def _create_page(args, user):
    from .models import AppPage
    role = getattr(getattr(user, 'profile', None), 'role', None)
    if role not in ('admin', 'super_admin'):
        return {"ok": False, "error": "Permissão negada. Somente administradores podem criar páginas."}

    name = args.get("name", "").strip()
    url_name = args.get("url_name", "").strip()
    if not name or not url_name:
        return {"ok": False, "error": "Nome e URL name da página são obrigatórios."}

    if AppPage.objects.filter(url_name=url_name).exists():
        return {"ok": False, "error": f"Página com URL name '{url_name}' já existe."}

    code = args.get("code", "").strip() or url_name.lower()
    group = args.get("group", "").strip() or None

    page = AppPage.objects.create(
        name=name,
        url_name=url_name,
        code=code,
        group=group,
        is_enabled=True
    )
    return {"ok": True, "data": {"id": page.id, "name": page.name, "url_name": page.url_name}}


def _create_ticket_type(args, user):
    from .models import TicketType
    role = getattr(getattr(user, 'profile', None), 'role', None)
    if role not in ('admin', 'super_admin'):
        return {"ok": False, "error": "Permissão negada. Somente administradores podem cadastrar tipos de chamado."}

    name = args.get("name", "").strip()
    if not name:
        return {"ok": False, "error": "Nome do tipo de chamado é obrigatório."}

    if TicketType.objects.filter(name__iexact=name).exists():
        return {"ok": False, "error": f"Já existe um tipo de chamado com o nome '{name}'."}

    obj = TicketType.objects.create(name=name)
    return {"ok": True, "data": {"id": obj.id, "name": obj.name}}


def _create_problem_type(args, user):
    from .models import ProblemType
    role = getattr(getattr(user, 'profile', None), 'role', None)
    if role not in ('admin', 'super_admin'):
        return {"ok": False, "error": "Permissão negada. Somente administradores podem cadastrar tipos de problema."}

    name = args.get("name", "").strip()
    if not name:
        return {"ok": False, "error": "Nome do tipo de problema é obrigatório."}

    if ProblemType.objects.filter(name__iexact=name).exists():
        return {"ok": False, "error": f"Já existe um tipo de problema com o nome '{name}'."}

    obj = ProblemType.objects.create(name=name)
    return {"ok": True, "data": {"id": obj.id, "name": obj.name}}


def _create_system(args, user):
    from .models import System
    role = getattr(getattr(user, 'profile', None), 'role', None)
    if role not in ('admin', 'super_admin'):
        return {"ok": False, "error": "Permissão negada. Somente administradores podem cadastrar sistemas."}

    name = args.get("name", "").strip()
    if not name:
        return {"ok": False, "error": "Nome do sistema é obrigatório."}

    if System.objects.filter(name__iexact=name).exists():
        return {"ok": False, "error": f"Já existe um sistema com o nome '{name}'."}

    obj = System.objects.create(
        name=name,
        color=args.get("color", "") or "#6c757d",
        description=args.get("description", "") or "",
    )
    return {"ok": True, "data": {"id": obj.id, "name": obj.name}}


def _create_equipment_type(args, user):
    from .models import EquipmentType
    role = getattr(getattr(user, 'profile', None), 'role', None)
    if role not in ('admin', 'super_admin'):
        return {"ok": False, "error": "Permissão negada. Somente administradores podem cadastrar tipos de equipamento."}

    name = args.get("name", "").strip()
    if not name:
        return {"ok": False, "error": "Nome do tipo de equipamento é obrigatório."}

    if EquipmentType.objects.filter(name__iexact=name).exists():
        return {"ok": False, "error": f"Já existe um tipo de equipamento com o nome '{name}'."}

    obj = EquipmentType.objects.create(name=name)
    return {"ok": True, "data": {"id": obj.id, "name": obj.name}}


def _create_ticket_status(args, user):
    from .models import TicketStatus
    role = getattr(getattr(user, 'profile', None), 'role', None)
    if role not in ('admin', 'super_admin'):
        return {"ok": False, "error": "Permissão negada. Somente administradores podem cadastrar status de OS."}

    code = args.get("code", "").strip().lower().replace(" ", "_")
    name = args.get("name", "").strip()
    if not code or not name:
        return {"ok": False, "error": "Código e nome do status são obrigatórios."}

    if TicketStatus.objects.filter(code=code).exists():
        return {"ok": False, "error": f"Já existe um status com o código '{code}'."}

    obj = TicketStatus.objects.create(
        code=code,
        name=name,
        color=args.get("color", "") or "#6c757d",
        font_color=args.get("font_color", "") or "",
        row_color=args.get("row_color", "") or "",
        order=args.get("order") or 0,
        is_active=True,
    )
    return {"ok": True, "data": {"id": obj.id, "code": obj.code, "name": obj.name}}


def _create_technician(args, user):
    from django.contrib.auth.models import User as DjangoUser
    from .models import UserProfile
    import secrets

    role = getattr(getattr(user, 'profile', None), 'role', None)
    if role not in ('admin', 'super_admin'):
        return {"ok": False, "error": "Permissão negada. Somente administradores podem cadastrar técnicos."}

    first_name = args.get("first_name", "").strip()
    if not first_name:
        return {"ok": False, "error": "Nome do técnico é obrigatório."}

    username = args.get("username", "").strip() or _generate_username(first_name)
    if DjangoUser.objects.filter(username=username).exists():
        return {"ok": False, "error": f"Já existe um usuário com o login '{username}'."}

    temp_password = secrets.token_urlsafe(8)

    new_user = DjangoUser.objects.create_user(
        username=username,
        email=args.get("email", "") or "",
        password=temp_password,
        first_name=first_name,
    )
    profile, _ = UserProfile.objects.get_or_create(user=new_user)
    profile.role = 'technician'
    profile.job_title = args.get("job_title", "") or ""
    profile.station = args.get("station", "") or ""
    profile.department = args.get("department", "") or ""
    profile.save()

    return {"ok": True, "data": {
        "id": new_user.id, "name": first_name, "username": username,
        "temp_password": temp_password, "token": profile.token,
    }}


def _create_responsible(args, user):
    from django.contrib.auth.models import User as DjangoUser
    from .models import UserProfile, Client
    import secrets

    role = getattr(getattr(user, 'profile', None), 'role', None)
    if role not in ('admin', 'super_admin'):
        return {"ok": False, "error": "Permissão negada. Somente administradores podem cadastrar responsáveis."}

    first_name = args.get("first_name", "").strip()
    client_id = args.get("client_id")
    if not first_name or not client_id:
        return {"ok": False, "error": "Nome e cliente são obrigatórios."}

    try:
        client = Client.objects.get(pk=client_id)
    except Client.DoesNotExist:
        return {"ok": False, "error": "Cliente não encontrado."}

    username = _generate_username(first_name)
    temp_password = secrets.token_urlsafe(8)

    new_user = DjangoUser.objects.create_user(
        username=username,
        email=args.get("email", "") or "",
        password=temp_password,
        first_name=first_name,
    )
    profile, _ = UserProfile.objects.get_or_create(user=new_user)
    profile.role = 'operator'
    profile.fixed_client = client
    profile.save()

    return {"ok": True, "data": {
        "id": new_user.id, "name": first_name, "username": username,
        "client": client.name, "temp_password": temp_password, "token": profile.token,
    }}


def _create_user_account(args, user):
    from django.contrib.auth.models import User as DjangoUser
    from .models import UserProfile, RoleLevel
    import secrets

    role = getattr(getattr(user, 'profile', None), 'role', None)
    if role not in ('admin', 'super_admin'):
        return {"ok": False, "error": "Permissão negada. Somente administradores podem cadastrar usuários."}

    first_name = args.get("first_name", "").strip()
    target_role = (args.get("role") or "").strip().lower()

    if not first_name or not target_role:
        return {"ok": False, "error": "Nome e nível de acesso são obrigatórios."}

    valid_roles = {c[0] for c in UserProfile.ROLE_CHOICES}
    valid_roles |= set(RoleLevel.objects.filter(is_active=True).values_list('code', flat=True))

    if target_role not in valid_roles:
        return {"ok": False, "error": f"Nível inválido. Opções: {', '.join(sorted(valid_roles))}"}

    # Admin não pode criar admin/super_admin
    if role == 'admin' and target_role in ('admin', 'super_admin'):
        return {"ok": False, "error": "Permissão negada. Administradores só podem criar usuários de níveis abaixo."}

    username = args.get("username", "").strip() or _generate_username(first_name)
    if DjangoUser.objects.filter(username=username).exists():
        return {"ok": False, "error": f"Já existe um usuário com o login '{username}'."}

    password = args.get("password", "").strip() or secrets.token_urlsafe(8)

    new_user = DjangoUser.objects.create_user(
        username=username,
        email=args.get("email", "") or "",
        password=password,
        first_name=first_name,
    )
    profile, _ = UserProfile.objects.get_or_create(user=new_user)
    profile.role = target_role
    profile.job_title = args.get("job_title", "") or ""
    profile.save()

    return {"ok": True, "data": {
        "id": new_user.id, "name": first_name, "username": username,
        "role": target_role, "password": password, "token": profile.token,
    }}


def _create_travel(args, user):
    from django.contrib.auth.models import User as DjangoUser
    from .models import TechnicianTravel, Client, ClientHub, System, Ticket

    role = getattr(getattr(user, 'profile', None), 'role', None)
    if role not in ('admin', 'super_admin'):
        return {"ok": False, "error": "Permissão negada. Somente administradores podem cadastrar viagens técnicas."}

    client_id = args.get("client_id")
    technician_id = args.get("technician_id")
    scheduled_date_raw = args.get("scheduled_date")

    if not client_id or not technician_id or not scheduled_date_raw:
        return {"ok": False, "error": "Cliente, técnico e data agendada são obrigatórios."}

    scheduled_date = _parse_dt(scheduled_date_raw)
    if not scheduled_date:
        return {"ok": False, "error": "Data agendada inválida."}

    try:
        client = Client.objects.get(pk=client_id)
    except Client.DoesNotExist:
        return {"ok": False, "error": "Cliente não encontrado."}

    try:
        technician = DjangoUser.objects.get(pk=technician_id)
    except DjangoUser.DoesNotExist:
        return {"ok": False, "error": "Técnico não encontrado."}

    hub = None
    hub_id = args.get("hub_id")
    if hub_id:
        hub = ClientHub.objects.filter(pk=hub_id).first()

    system = None
    system_id = args.get("system_id")
    if system_id:
        system = System.objects.filter(pk=system_id).first()

    ticket = None
    ticket_id = args.get("ticket_id")
    if ticket_id:
        ticket = Ticket.objects.filter(pk=ticket_id).first()

    travel = TechnicianTravel.objects.create(
        client=client,
        hub=hub,
        scheduled_date=scheduled_date,
        technician=technician,
        system=system,
        service_order=ticket,
        created_by=user,
    )
    return {"ok": True, "data": {
        "id": travel.id,
        "client": client.name,
        "technician": technician.get_full_name() or technician.username,
        "scheduled_date": scheduled_date.strftime("%d/%m/%Y %H:%M"),
    }}


def _list_roles(args, user):
    from .models import RoleLevel
    try:
        roles = RoleLevel.objects.filter(is_active=True).order_by('name')
        return {"ok": True, "data": [
            {"num": i, "id": r.id, "name": r.name, "code": r.code}
            for i, r in enumerate(roles, start=1)
        ]}
    except Exception as e:
        return {"ok": False, "error": f"Erro ao listar níveis: {str(e)}"}


def _list_pages(args, user):
    from .models import AppPage
    try:
        pages = AppPage.objects.all().order_by('group', 'order', 'name')
        return {"ok": True, "data": [
            {"num": i, "id": p.id, "name": p.name, "url_name": p.url_name, "group": p.group or "Sem grupo", "enabled": p.is_enabled}
            for i, p in enumerate(pages, start=1)
        ]}
    except Exception as e:
        return {"ok": False, "error": f"Erro ao listar páginas: {str(e)}"}


# Páginas que o Jota4 pode abrir no navegador do usuário via tool "open_page".
# Cobre o universo de telas navegáveis (bem mais amplo que o cadastro em AppPage,
# que só existe pra ~31 páginas ligadas ao menu/permissões) — url_name -> nome amigável.
_NAVIGABLE_PAGES = {
    'dashboard': 'Dashboard',
    'hub_dashboard': 'Dashboard de Hubs',
    'local': 'Local',
    'task_list': 'Passagem de Turno / Tasks',
    'ticket_list': 'Lista de Ordens de Serviço (OS)',
    'ticket_create': 'Criar Nova OS',
    'checklist_daily': 'Checklist Diário',
    'checklist_config': 'Configuração de Checklist',
    'client_list': 'Clientes',
    'equipment_list': 'Equipamentos',
    'system_list': 'Sistemas',
    'ticketstatus_list': 'Status de OS',
    'ordertype_list': 'Tipos de Chamado',
    'problemtype_list': 'Tipos de Problema',
    'technician_list': 'Técnicos',
    'responsible_list': 'Responsáveis',
    'contactclient_list': 'Contatos de Clientes',
    'contactjumper_list': 'Contatos JumperFour',
    'travel_list': 'Viagens',
    'user_list': 'Usuários',
    'notification_list': 'Notificações',
    'notification_monitor': 'Monitor de Notificações',
    'profile': 'Meu Perfil',
    'settings': 'Configurações',
    'permissions': 'Permissões',
    'tickets_daily_report_view': 'Relatório Diário de Chamados',
    'tickets_weekly_report_view': 'Relatório Semanal de Chamados',
    'tickets_monthly_report_view': 'Relatório Mensal de Chamados',
}


def _user_can_access_page(user, url_name):
    """Replica a checagem de RolePageAccessMiddleware — mesma regra usada de
    verdade pro sistema bloquear/liberar acesso a uma página."""
    from .models import AppPage, RoleLevel, RolePagePermission

    role_code = getattr(getattr(user, 'profile', None), 'role', None)
    if role_code == 'super_admin':
        return True

    page = AppPage.objects.filter(url_name=url_name).first()
    if page and not page.is_enabled:
        return False
    if not role_code or not page:
        return True  # sem AppPage cadastrado -> mesmo comportamento do middleware (libera)

    role = RoleLevel.objects.filter(code=role_code, is_active=True).first()
    if not role:
        return True

    perm = RolePagePermission.objects.filter(role=role, page=page).first()
    if perm and not perm.allowed:
        return False
    return True


def _open_page(args, user):
    """Resolve o pedido de navegação do usuário para uma URL real — quem de fato
    navega o navegador é o widget do Chat IA no frontend, usando essa URL."""
    from django.urls import reverse, NoReverseMatch

    page_key = (args.get("page") or "").strip()
    if page_key not in _NAVIGABLE_PAGES:
        return {"ok": False, "error": f"Página '{page_key}' não reconhecida."}

    if not _user_can_access_page(user, page_key):
        return {"ok": False, "error": f"Você não tem permissão para acessar a página '{_NAVIGABLE_PAGES[page_key]}'."}

    try:
        url = reverse(page_key)
    except NoReverseMatch:
        return {"ok": False, "error": f"Não foi possível gerar o link para '{page_key}'."}

    return {"ok": True, "data": {"url": url, "page_name": _NAVIGABLE_PAGES[page_key]}}


def _list_users(args, user):
    from django.contrib.auth.models import User as DjangoUser
    try:
        users = DjangoUser.objects.select_related('profile').all().order_by('first_name', 'username')
        return {"ok": True, "data": [
            {
                "num": i,
                "id": u.id,
                "name": u.get_full_name() or u.username,
                "username": u.username,
                "email": u.email or "N/A",
                "role": getattr(u.profile, 'role', 'N/A') if hasattr(u, 'profile') else "N/A"
            }
            for i, u in enumerate(users, start=1)
        ]}
    except Exception as e:
        return {"ok": False, "error": f"Erro ao listar usuários: {str(e)}"}


def _toggle_page_enabled(args, user):
    from .models import AppPage
    role = getattr(getattr(user, 'profile', None), 'role', None)
    if role not in ('admin', 'super_admin'):
        return {"ok": False, "error": "Permissão negada. Somente Super Admin e Administrador podem habilitar/desabilitar páginas."}

    page_id = args.get("page_id")
    enabled = args.get("enabled")

    if page_id is None or enabled is None:
        return {"ok": False, "error": "page_id e enabled são obrigatórios."}

    try:
        page = AppPage.objects.get(pk=page_id)
    except AppPage.DoesNotExist:
        return {"ok": False, "error": f"Página ID {page_id} não encontrada."}

    page.is_enabled = enabled
    page.save(update_fields=['is_enabled'])

    status = "habilitada" if enabled else "desabilitada"
    return {"ok": True, "data": {"id": page.id, "name": page.name, "status": status}}


def _update_page_permission(args, user):
    from .models import AppPage, RoleLevel, RolePagePermission
    role = getattr(getattr(user, 'profile', None), 'role', None)
    if role not in ('admin', 'super_admin'):
        return {"ok": False, "error": "Permissão negada. Somente Super Admin e Administrador podem modificar permissões de páginas."}

    page_id = args.get("page_id")
    role_id = args.get("role_id")
    allowed = args.get("allowed")

    if page_id is None or role_id is None or allowed is None:
        return {"ok": False, "error": "page_id, role_id e allowed são obrigatórios."}

    try:
        page = AppPage.objects.get(pk=page_id)
        role_obj = RoleLevel.objects.get(pk=role_id)
    except (AppPage.DoesNotExist, RoleLevel.DoesNotExist):
        return {"ok": False, "error": "Página ou nível não encontrado."}

    perm, created = RolePagePermission.objects.get_or_create(role=role_obj, page=page)
    perm.allowed = allowed
    perm.save()

    action = "permitido" if allowed else "bloqueado"
    return {"ok": True, "data": {
        "page": page.name,
        "role": role_obj.name,
        "action": action
    }}


def _get_role_page_permissions(args, user):
    """Visão ampla de permissões: para um nível específico (ou todos, se role_id
    não informado), lista cada página do sistema e se está permitida ou bloqueada
    para aquele nível — combinando RolePagePermission com o status global (is_enabled)
    da página."""
    from .models import AppPage, RoleLevel, RolePagePermission

    admin_role = getattr(getattr(user, 'profile', None), 'role', None)
    if admin_role not in ('admin', 'super_admin'):
        return {"ok": False, "error": "Informações privilegiadas. Somente administradores podem acessar."}

    role_id = args.get("role_id")
    roles = RoleLevel.objects.filter(is_active=True).order_by('name')
    if role_id is not None:
        roles = roles.filter(pk=role_id)
        if not roles.exists():
            return {"ok": False, "error": f"Nível ID {role_id} não encontrado."}

    pages = list(AppPage.objects.all().order_by('group', 'order', 'name'))
    perms = {
        (p.role_id, p.page_id): p.allowed
        for p in RolePagePermission.objects.all()
    }

    result = []
    for r in roles:
        page_status = []
        for page in pages:
            if not page.is_enabled:
                allowed = False
                reason = "página desabilitada globalmente"
            else:
                allowed = perms.get((r.id, page.id), True)
                reason = "" if allowed else "bloqueada para este nível"
            page_status.append({
                "page": page.name,
                "url_name": page.url_name,
                "allowed": allowed,
                "motivo_bloqueio": reason,
            })
        result.append({
            "role_id": r.id,
            "role": r.name,
            "code": r.code,
            "paginas": page_status,
        })

    return {"ok": True, "data": result}


def _can_manage_user(admin_user, target_user):
    """
    Verifica se admin_user pode gerenciar target_user.
    Super Admin pode gerenciar qualquer um.
    Admin pode gerenciar apenas usuários de níveis abaixo.
    """
    admin_role = getattr(getattr(admin_user, 'profile', None), 'role', None)

    # Super Admin tem acesso global
    if admin_role == 'super_admin':
        return True, "global"

    # Admin tem acesso a usuários de níveis abaixo
    if admin_role != 'admin':
        return False, None

    target_role = getattr(getattr(target_user, 'profile', None), 'role', None)

    # Admin não pode gerenciar outros admins ou super_admins
    if target_role in ('admin', 'super_admin'):
        return False, None

    return True, "restricted"


def _update_user_restriction(args, user):
    from django.contrib.auth.models import User as DjangoUser
    from .models import UserProfile

    role = getattr(getattr(user, 'profile', None), 'role', None)
    if role not in ('admin', 'super_admin'):
        return {"ok": False, "error": "Permissão negada. Somente Super Admin e Administrador podem modificar restrições de usuários."}

    user_id = args.get("user_id")
    restriction_type = args.get("restriction_type")
    allowed = args.get("allowed")

    if user_id is None or not restriction_type or allowed is None:
        return {"ok": False, "error": "user_id, restriction_type e allowed são obrigatórios."}

    valid_restrictions = [
        'can_view_tickets', 'can_create_tickets', 'can_edit_tickets', 'can_delete_tickets',
        'can_view_checklists', 'can_create_checklists', 'allow_pdf_reports', 'ai_chat_enabled', 'can_view_reports'
    ]

    if restriction_type not in valid_restrictions:
        return {"ok": False, "error": f"Tipo de restrição inválido. Opções: {', '.join(valid_restrictions)}"}

    try:
        target_user = DjangoUser.objects.get(pk=user_id)
    except DjangoUser.DoesNotExist:
        return {"ok": False, "error": f"Usuário ID {user_id} não encontrado."}

    profile = getattr(target_user, 'profile', None)
    if not profile:
        profile = UserProfile.objects.create(user=target_user)

    setattr(profile, restriction_type, allowed)
    profile.save(update_fields=[restriction_type])

    action = "permitido" if allowed else "bloqueado"
    return {"ok": True, "data": {
        "user": target_user.get_full_name() or target_user.username,
        "restriction": restriction_type,
        "action": action
    }}


def _list_all_users_admin(args, user):
    from django.contrib.auth.models import User as DjangoUser

    role = getattr(getattr(user, 'profile', None), 'role', None)
    if role not in ('admin', 'super_admin'):
        return {"ok": False, "error": "Informações privilegiadas. Somente administradores podem acessar. Solicite ao gestor."}

    try:
        users = DjangoUser.objects.select_related('profile').all().order_by('first_name', 'username')
        result = []
        for u in users:
            profile = getattr(u, 'profile', None)
            user_role = getattr(profile, 'role', 'N/A') if profile else 'N/A'

            # Admin não pode ver detalhes de admins/super_admins
            if role == 'admin' and user_role in ('admin', 'super_admin'):
                continue

            result.append({
                "num": len(result) + 1,
                "id": u.id,
                "name": u.get_full_name() or u.username,
                "username": u.username,
                "email": u.email or "N/A",
                "role": user_role,
                "active": u.is_active,
                "last_login": timezone.localtime(u.last_login).strftime("%d/%m/%Y %H:%M") if u.last_login else "Nunca",
                "ai_chat_enabled": getattr(profile, 'ai_chat_enabled', True) if profile else True,
                "can_view_tickets": getattr(profile, 'can_view_tickets', True) if profile else True,
                "can_create_tickets": getattr(profile, 'can_create_tickets', True) if profile else True,
                "can_edit_tickets": getattr(profile, 'can_edit_tickets', True) if profile else True,
                "can_delete_tickets": getattr(profile, 'can_delete_tickets', True) if profile else True,
                "can_view_checklists": getattr(profile, 'can_view_checklists', True) if profile else True,
                "can_create_checklists": getattr(profile, 'can_create_checklists', True) if profile else True,
                "can_view_reports": getattr(profile, 'can_view_reports', True) if profile else True,
                "allow_pdf_reports": getattr(profile, 'allow_pdf_reports', True) if profile else True,
            })

        return {"ok": True, "data": result}
    except Exception as e:
        return {"ok": False, "error": f"Erro ao listar usuários: {str(e)}"}


def _get_user_details_admin(args, user):
    from django.contrib.auth.models import User as DjangoUser
    from .models import RoleLevel, RolePagePermission

    role = getattr(getattr(user, 'profile', None), 'role', None)
    if role not in ('admin', 'super_admin'):
        return {"ok": False, "error": "Informações privilegiadas. Somente administradores podem acessar. Solicite ao gestor."}

    user_id = args.get("user_id")
    include_password = args.get("include_password", False)

    if not user_id:
        return {"ok": False, "error": "user_id é obrigatório."}

    try:
        target_user = DjangoUser.objects.select_related('profile').get(pk=user_id)
    except DjangoUser.DoesNotExist:
        return {"ok": False, "error": f"Usuário ID {user_id} não encontrado."}

    # Validar permissão
    can_manage, scope = _can_manage_user(user, target_user)
    if not can_manage:
        return {"ok": False, "error": "Permissão negada. Você pode gerenciar apenas usuários de níveis abaixo."}

    profile = getattr(target_user, 'profile', None)
    if not profile:
        profile = UserProfile.objects.create(user=target_user)

    data = {
        "id": target_user.id,
        "name": target_user.get_full_name() or target_user.username,
        "username": target_user.username,
        "email": target_user.email or "N/A",
        "role": getattr(profile, 'role', 'N/A'),
        "active": target_user.is_active,
        "job_title": getattr(profile, 'job_title', '') or "N/A",
        "phone": getattr(profile, 'company_phone', '') or "N/A",
        "token": getattr(profile, 'token', 'N/A'),
        "last_login": timezone.localtime(target_user.last_login).strftime("%d/%m/%Y %H:%M") if target_user.last_login else "Nunca",
        "date_joined": timezone.localtime(target_user.date_joined).strftime("%d/%m/%Y %H:%M"),
        "restricoes_individuais": {
            "ai_chat_enabled": getattr(profile, 'ai_chat_enabled', True),
            "can_view_tickets": getattr(profile, 'can_view_tickets', True),
            "can_create_tickets": getattr(profile, 'can_create_tickets', True),
            "can_edit_tickets": getattr(profile, 'can_edit_tickets', True),
            "can_delete_tickets": getattr(profile, 'can_delete_tickets', True),
            "can_view_checklists": getattr(profile, 'can_view_checklists', True),
            "can_create_checklists": getattr(profile, 'can_create_checklists', True),
            "can_view_reports": getattr(profile, 'can_view_reports', True),
            "allow_pdf_reports": getattr(profile, 'allow_pdf_reports', True),
        },
    }

    # Páginas bloqueadas para o nível de acesso deste usuário (herdadas do RoleLevel)
    try:
        role_code = getattr(profile, 'role', None)
        role_obj = RoleLevel.objects.filter(code=role_code).first()
        if role_obj:
            blocked_pages = list(
                RolePagePermission.objects.filter(role=role_obj, allowed=False)
                .select_related('page').values_list('page__name', flat=True)
            )
            data["paginas_bloqueadas_pelo_nivel"] = blocked_pages or "Nenhuma — todas as páginas habilitadas para este nível estão liberadas"
    except Exception:
        pass

    if include_password and role == 'super_admin':
        # Apenas super_admin vê senhas
        data["password_hash"] = target_user.password[:30] + "..."
        data["password_note"] = "Hash da senha (dados sigilosos - Super Admin apenas)"
    elif include_password and role == 'admin':
        data["password_note"] = "Para alterar a senha, use a ferramenta 'change_user_password_admin'"

    return {"ok": True, "data": data}


def _update_user_data_admin(args, user):
    from django.contrib.auth.models import User as DjangoUser

    role = getattr(getattr(user, 'profile', None), 'role', None)
    if role not in ('admin', 'super_admin'):
        return {"ok": False, "error": "Informações privilegiadas. Somente administradores podem acessar. Solicite ao gestor."}

    user_id = args.get("user_id")
    if not user_id:
        return {"ok": False, "error": "user_id é obrigatório."}

    try:
        target_user = DjangoUser.objects.select_related('profile').get(pk=user_id)
    except DjangoUser.DoesNotExist:
        return {"ok": False, "error": f"Usuário ID {user_id} não encontrado."}

    # Validar permissão
    can_manage, scope = _can_manage_user(user, target_user)
    if not can_manage:
        return {"ok": False, "error": "Permissão negada. Você pode gerenciar apenas usuários de níveis abaixo."}

    updated_fields = []

    if "first_name" in args:
        target_user.first_name = args["first_name"].strip()
        updated_fields.append('first_name')

    if "email" in args:
        target_user.email = args["email"].strip()
        updated_fields.append('email')

    if "last_name" in args:
        target_user.last_name = args["last_name"].strip()
        updated_fields.append('last_name')

    if "job_title" in args:
        profile = getattr(target_user, 'profile', None)
        if not profile:
            profile = UserProfile.objects.create(user=target_user)
        profile.job_title = args["job_title"].strip()
        profile.save(update_fields=['job_title'])

    try:
        if updated_fields:
            target_user.save(update_fields=updated_fields)
        return {"ok": True, "data": {
            "user": target_user.get_full_name() or target_user.username,
            "updated_fields": updated_fields,
            "message": "Dados atualizados com sucesso"
        }}
    except Exception as e:
        return {"ok": False, "error": f"Erro ao atualizar usuário: {str(e)}"}


def _change_user_password_admin(args, user):
    from django.contrib.auth.models import User as DjangoUser

    role = getattr(getattr(user, 'profile', None), 'role', None)
    if role not in ('admin', 'super_admin'):
        return {"ok": False, "error": "Informações privilegiadas. Somente administradores podem acessar. Solicite ao gestor."}

    user_id = args.get("user_id")
    new_password = args.get("new_password")

    if not user_id or not new_password:
        return {"ok": False, "error": "user_id e new_password são obrigatórios."}

    if len(new_password) < 6:
        return {"ok": False, "error": "A senha deve ter pelo menos 6 caracteres."}

    try:
        target_user = DjangoUser.objects.get(pk=user_id)
    except DjangoUser.DoesNotExist:
        return {"ok": False, "error": f"Usuário ID {user_id} não encontrado."}

    # Validar permissão
    can_manage, scope = _can_manage_user(user, target_user)
    if not can_manage:
        return {"ok": False, "error": "Permissão negada. Você pode gerenciar apenas usuários de níveis abaixo."}

    target_user.set_password(new_password)
    target_user.save(update_fields=['password'])

    return {"ok": True, "data": {
        "user": target_user.get_full_name() or target_user.username,
        "message": "Senha alterada com sucesso"
    }}


def _get_system_info_admin(args, user):
    from django.contrib.auth.models import User as DjangoUser
    from .models import Ticket, SystemSettings, AIProviderConfig

    role = getattr(getattr(user, 'profile', None), 'role', None)
    if role not in ('admin', 'super_admin'):
        return {"ok": False, "error": "Informações privilegiadas. Somente administradores podem acessar. Solicite ao gestor."}

    try:
        total_users = DjangoUser.objects.count()
        active_users = DjangoUser.objects.filter(is_active=True).count()
        total_tickets = Ticket.objects.count()
        open_tickets = Ticket.objects.filter(status='open').count()

        settings = SystemSettings.objects.first()
        ai_enabled = settings.ai_enabled if settings else False
        active_config = AIProviderConfig.objects.filter(is_active=True).first()
        ai_provider = active_config.get_provider_display() if active_config else "Nenhuma configuração ativa"

        return {"ok": True, "data": {
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": total_users - active_users,
            "total_tickets": total_tickets,
            "open_tickets": open_tickets,
            "closed_tickets": total_tickets - open_tickets,
            "ai_enabled": ai_enabled,
            "ai_provider": ai_provider,
        }}
    except Exception as e:
        return {"ok": False, "error": f"Erro ao obter informações do sistema: {str(e)}"}


def _list_online_users_admin(args, user):
    from django.contrib.auth.models import User as DjangoUser
    from .models import ActiveSession

    role = getattr(getattr(user, 'profile', None), 'role', None)
    if role not in ('admin', 'super_admin'):
        return {"ok": False, "error": "Informações privilegiadas. Somente administradores podem acessar. Solicite ao gestor."}

    try:
        ActiveSession.cleanup_stale()
        sessions = ActiveSession.objects.select_related('user').all().order_by('-last_activity')

        online_users = []
        for i, session in enumerate(sessions, start=1):
            online_users.append({
                "num": i,
                "user_id": session.user.id,
                "name": session.user.get_full_name() or session.user.username,
                "username": session.user.username,
                "ip_address": session.ip_address,
                "last_activity": timezone.localtime(session.last_activity).strftime("%d/%m/%Y %H:%M:%S"),
                "logged_at": timezone.localtime(session.created_at).strftime("%d/%m/%Y %H:%M:%S"),
            })

        return {"ok": True, "data": {
            "total_online": len(online_users),
            "users": online_users
        }}
    except Exception as e:
        return {"ok": False, "error": f"Erro ao listar usuários online: {str(e)}"}


# Mapeamento nome → função
_TOOL_REGISTRY = {
    "search_web": _search_web,
    "search_company_details": _search_company_details,
    "search_all_contacts": _search_all_contacts,
    "search_client": _search_client,
    "get_client_details": _get_client_details,
    "list_ticket_statuses": _list_ticket_statuses,
    "list_systems": _list_systems,
    "list_ticket_types": _list_ticket_types,
    "list_jumper_contacts": _list_jumper_contacts,
    "list_equipments": _list_equipments,
    "list_equipment_types": _list_equipment_types,
    "list_problem_types": _list_problem_types,
    "get_ticket": _get_ticket,
    "create_ticket": _create_ticket,
    "start_ticket_batch": _start_ticket_batch,
    "add_or_update_batch_item": _add_or_update_batch_item,
    "list_batch_status": _list_batch_status,
    "cancel_ticket_batch": _cancel_ticket_batch,
    "confirm_ticket_batch": _confirm_ticket_batch,
    "update_ticket": _update_ticket,
    "add_ticket_evolution": _add_ticket_evolution,
    "delete_ticket": _delete_ticket,
    "create_client": _create_client,
    "update_client": _update_client,
    "create_equipment": _create_equipment,
    "clear_chat": _clear_chat,
    "remember_user_preference": _remember_user_preference,
    "forget_user_preference": _forget_user_preference,
    "check_pending_alerts": _check_pending_alerts,
    "get_message_content": _get_message_content,
    "mark_message_read": _mark_message_read,
    "acknowledge_handover_alert": _acknowledge_handover_alert,
    "create_handover_entry": _create_handover_entry,
    "notify_handover_entry": _notify_handover_entry,
    "send_message_to_user": _send_message_to_user,
    "open_private_chat": _open_private_chat,
    "create_contact_client": _create_contact_client,
    "create_contact_jumper": _create_contact_jumper,
    "create_hub": _create_hub,
    "create_role": _create_role,
    "create_page": _create_page,
    "create_ticket_type": _create_ticket_type,
    "create_problem_type": _create_problem_type,
    "create_system": _create_system,
    "create_equipment_type": _create_equipment_type,
    "create_ticket_status": _create_ticket_status,
    "create_technician": _create_technician,
    "create_responsible": _create_responsible,
    "create_user_account": _create_user_account,
    "create_travel": _create_travel,
    "list_roles": _list_roles,
    "list_pages": _list_pages,
    "open_page": _open_page,
    "list_users": _list_users,
    "toggle_page_enabled": _toggle_page_enabled,
    "update_page_permission": _update_page_permission,
    "get_role_page_permissions": _get_role_page_permissions,
    "update_user_restriction": _update_user_restriction,
    "list_all_users_admin": _list_all_users_admin,
    "get_user_details_admin": _get_user_details_admin,
    "update_user_data_admin": _update_user_data_admin,
    "change_user_password_admin": _change_user_password_admin,
    "get_system_info_admin": _get_system_info_admin,
    "list_online_users_admin": _list_online_users_admin,
}


# System prompt enviado para a IA em toda requisição
SYSTEM_PROMPT = """Você é o assistente de IA do sistema JumperFour OS — um sistema de gestão de Ordens de Serviço.
Você fala português brasileiro de forma natural e tranquila, como numa conversa falada com um colega —
não como quem está lendo um relatório em voz alta. Seja claro e objetivo, mas com calor humano.

IDENTIDADE:
Seu nome é Jota4. Ao iniciar uma nova conversa (histórico vazio) ou quando o usuário perguntar quem você é,
apresente-se com uma saudação de acordo com o horário atual informado (Bom dia / Boa tarde / Boa noite),
o primeiro nome do usuário e diga que é o Jota4, assistente IA da JumperFour OS/Tickets. Exemplo:
"Boa tarde, Everton! Eu sou o Jota4, assistente IA da JumperFour OS/Tickets. O que posso fazer por você hoje?"
Nas demais respostas não repita essa apresentação — apenas responda normalmente, podendo se referir a si
mesmo como Jota4 quando fizer sentido (ex: "Deixa que o Jota4 resolve isso pra você").

MEMÓRIA PERSONALIZADA POR USUÁRIO — MUITO IMPORTANTE:
Cada usuário tem sua própria memória persistente com o Jota4, que sobrevive entre conversas e sessões.
Se a mensagem de sistema contiver um bloco "MEMÓRIA SOBRE ESTE USUÁRIO", trate essas informações como
contexto real e já conhecido sobre ele — aja de acordo com elas desde a primeira resposta, sem precisar
perguntar de novo ou citar que está "consultando uma memória" (é natural, como se você já conhecesse a
pessoa do trabalho).
Ao longo da conversa, chame a ferramenta "remember_user_preference" (sem pedir permissão, sem avisar)
sempre que perceber ou o usuário ensinar:
- Como prefere ser chamado/tratado (apelido, "me chama de...", forma de tratamento);
- Um jeito específico de falar, gírias, abreviações ou termos próprios que ele usa;
- Atalhos de criação (ex: "quando eu disser XPTO, é para abrir OS para o cliente Y no hub Z");
- Padrões de trabalho recorrentes (cliente/hub que mais atende, tipo de chamado comum, equipe, turno,
  equipamentos que mexe com frequência, etc).
Se o usuário pedir para esquecer, corrigir ou apagar algo que você aprendeu sobre ele, use
"forget_user_preference". Não invente nem salve suposições — só registre o que for dito ou observado
claramente na conversa.

MENSAGENS E ALERTAS DE PASSAGEM DE TURNO PENDENTES — MUITO IMPORTANTE:
Se a mensagem de sistema contiver "VERIFICAÇÃO AUTOMÁTICA DE PENDÊNCIAS" (disparada quando o usuário loga
ou abre o chat), chame IMEDIATAMENTE "check_pending_alerts" antes de qualquer outra coisa. Se houver
mensagens diretas não lidas e/ou alertas de passagem de turno pendentes, cumprimente o usuário (saudação
pelo horário + nome) e avise sobre o que encontrou, de forma resumida e natural — sem citar nomes de
ferramentas. Pergunte se ele quer que você mostre o conteúdo. Exemplo:
"Bom dia, Everton! Verifiquei aqui e o Guilherme te enviou uma mensagem. Quer que eu leia e coloque aqui
pra você ver?"
Depois que mostrar o conteúdo (via "get_message_content" ou o texto do alerta), pergunte se ele quer que
você dê baixa (marque como lida/reconhecida) — e só chame "mark_message_read" ou
"acknowledge_handover_alert" se ele confirmar. Nunca dê baixa em algo sem o usuário ter visto o conteúdo
e confirmado.
Fora desse gatilho automático, também use "check_pending_alerts" sempre que o usuário perguntar se tem
mensagens, recados ou pendências de turno.
Enquanto o usuário não der baixa, o alerta automático volta a disparar a cada novo login (a mensagem de
sistema informará o número da tentativa) — nunca repita a mesma frase; varie o texto ficando gradualmente
mais insistente (porém sempre educado) a cada nova tentativa, como um colega que está de olho no assunto.
O alerta também pode disparar no meio de uma sessão já aberta, assim que uma mensagem nova chegar — não é
só no login.

PASSAGEM DE TURNO — CRIAR ANOTAÇÃO — MUITO IMPORTANTE:
Quando o usuário pedir para anotar algo, deixar um recado ou registrar uma informação na passagem de
turno (ex: "anota aí que...", "deixa registrado que...", "bota na passagem de turno que...", ou ditando
isso por áudio), monte o texto final: se a mensagem veio de voz, corrija pontuação/gramática/erros de
transcrição, mas NUNCA mude o sentido nem invente informação que não foi dita. Mostre o texto revisado
pro usuário e pergunte "Confirma?" antes de salvar (regra geral de confirmação antes de criar). Só então
chame "create_handover_entry" — o turno (diurno/noturno) e a data são calculados automaticamente, não
precisa perguntar isso ao usuário.
Depois de criar com sucesso, pergunte se ele quer avisar/indicar alguém específico sobre essa anotação
(ex: "Quer que eu avise alguém sobre isso?"). Se ele confirmar e disser o nome, use
"notify_handover_entry" com o entry_id retornado e o nome/ID da pessoa — isso cria um alerta pendente que
aparece sozinho pra ela (mesmo mecanismo de "VERIFICAÇÃO AUTOMÁTICA DE PENDÊNCIAS" acima), diferente de
"send_message_to_user" que é uma mensagem direta avulsa. Pode notificar mais de uma pessoa, uma de cada
vez, se o usuário pedir.

VOCÊ COMO INTERLOCUTOR (RELAY DE MENSAGENS):
Depois de mostrar uma mensagem pendente, se o usuário quiser responder (ex: "responde pra ele que já vou
ver isso", "manda um recado pro Guilherme dizendo X"), use "send_message_to_user" para enviar a resposta
em nome dele — use o "sender_id" retornado por check_pending_alerts/get_message_content como
"recipient_id" quando for uma resposta direta a alguém que mandou mensagem. Você também pode mandar
mensagens novas para qualquer colaborador quando o usuário pedir, mesmo sem pendência anterior. Sempre
confirme o envio de forma natural (ex: "Prontinho, mandei sua resposta para o Guilherme!").
Se o usuário quiser conversar em tempo real (não só mandar um recado avulso) — ex: "abre um chat particular
com o Guilherme", "quero falar com a Ana agora" — use "open_private_chat" em vez de "send_message_to_user".
Isso abre uma janela de chat instantâneo (estilo Messenger) entre os dois; dentro dessa janela, você
(Jota4) só participa se qualquer um dos dois te chamar pelo nome na própria conversa — não é você quem
troca as mensagens ali, é uma conversa direta entre as pessoas.

Você tem acesso a ferramentas para consultar e gerenciar dados do sistema.

ESCOPO DE ATUAÇÃO — MUITO IMPORTANTE:
Você só pode ajudar com assuntos relacionados ao sistema JumperFour OS:
- Criar, editar, visualizar, evoluir ou excluir Ordens de Serviço (OS/tickets)
- Cadastrar, editar ou buscar clientes, equipamentos, contatos, hubs/lojas e profissionais JumperFour
- Consultar status, sistemas, tipos de chamado disponíveis
- ADMIN ONLY: Cadastrar tipos de chamado, tipos de problema, sistemas, tipos de equipamento, status de OS, técnicos, responsáveis, usuários (qualquer nível) e viagens técnicas
- ADMIN ONLY: Gerenciar níveis de acesso, páginas, permissões e restrições de usuário (somente para Super Admin e Admin)
- Dúvidas sobre o funcionamento do sistema

NAVEGAÇÃO — ABRIR PÁGINAS DO SISTEMA:
Quando o usuário pedir para "abrir", "ir para", "mostrar" ou "navegar até" uma tela do sistema (ex: "abre a
lista de clientes", "vai pra passagem de turno", "mostra as configurações"), use a tool "open_page" com o
identificador da página mais próximo do pedido — não precisa perguntar confirmação antes (navegar não é uma
ação destrutiva). Depois de chamar a tool com sucesso, responda confirmando de forma curta (ex: "Abrindo
Clientes...") — a navegação em si acontece automaticamente no navegador do usuário, você não precisa (nem
consegue) fazer mais nada além de chamar a tool. O chat NUNCA minimiza sozinho por causa de uma navegação —
ele continua aberto do jeito que estava, acompanhando o usuário pelas telas; só fecha se o próprio usuário
clicar no botão de minimizar. Se a tool retornar erro (página não reconhecida ou sem permissão), informe o
motivo exato ao usuário, seguindo a regra geral de erros.

VISÃO DE PERMISSÕES E RESTRIÇÕES (ADMIN/SUPER ADMIN) — MUITO IMPORTANTE:
Você TEM visibilidade completa sobre o que está liberado ou bloqueado no sistema, tanto por nível de acesso
quanto por usuário individual. Nunca diga que não tem como verificar isso — use as ferramentas corretas:
- "list_all_users_admin" retorna, para TODOS os usuários de uma vez, o Chat IA e cada restrição individual
  (can_view_tickets, can_create_tickets, can_edit_tickets, can_delete_tickets, can_view_checklists,
  can_create_checklists, can_view_reports, allow_pdf_reports) — use quando o usuário perguntar sobre o
  estado de vários usuários ao mesmo tempo (ex: "os demais continuam bloqueados?").
- "get_user_details_admin" retorna o mesmo detalhamento para UM usuário específico, incluindo também as
  páginas bloqueadas herdadas do nível de acesso dele (campo "paginas_bloqueadas_pelo_nivel").
- "get_role_page_permissions" retorna, para um nível de acesso (ou todos, se role_id não for informado),
  quais páginas/telas estão liberadas ou bloqueadas para aquele nível.
Combine essas ferramentas para responder com precisão perguntas sobre "quem tem acesso a quê", "o que está
bloqueado para o nível X" ou "esse usuário pode fazer Y". Restrição individual (por usuário) sempre se
soma às permissões de página do nível — ambas podem bloquear algo independentemente uma da outra.

REGRA GERAL DE CADASTROS: você tem uma ferramenta "create_*" para TODO cadastro disponível no sistema
(cliente, equipamento, tipo de equipamento, contato de cliente, profissional JumperFour, hub/loja,
tipo de chamado, tipo de problema, sistema, status de OS, técnico, responsável, usuário, nível de acesso,
página e viagem técnica). Se o usuário pedir para cadastrar algo que existe no sistema, use a ferramenta
correspondente — nunca diga que não é capaz de cadastrar algo que tenha uma tool disponível.
Cada tool já valida a permissão do usuário logado e retorna erro claro caso ele não tenha permissão —
nesse caso, apenas repasse a mensagem de erro, não insista nem tente contornar.

CRIAÇÃO DE OS EM LOTE — MUITO IMPORTANTE:
Quando o usuário pedir para criar VÁRIAS OS de uma vez (ex: "preciso abrir 10 OS para o cliente X", "cria 5
chamados pra mim"), NÃO tente chamar create_ticket várias vezes seguidas sem parar para confirmar cada uma
— use o fluxo de lote:
1. Chame "start_ticket_batch" com o total_count e, se o usuário já disse o que é igual em todas (mesmo
   cliente, mesmo responsável, mesmo tipo de chamado, etc), passe isso em shared_defaults.
2. Vá coletando os dados de CADA OS, uma de cada vez, perguntando o que for pertinente e ainda não coberto
   pelos padrões do lote (ex: descrição, equipamento, hub/loja de cada uma). Depois de reunir os dados de
   uma posição, chame "add_or_update_batch_item" com o index dela (1, 2, 3...). Sempre informe ao usuário
   em que posição do lote vocês estão (ex: "Show, essa é a OS 3 de 10. Vamos para a próxima?").
3. A qualquer momento o usuário pode pedir para AJUSTAR uma OS já preenchida do lote (ex: "muda a descrição
   da OS 2") — chame add_or_update_batch_item de novo na mesma posição, só com os campos que mudaram. Ele
   também pode pedir para CANCELAR o lote inteiro a qualquer momento — nesse caso use
   "cancel_ticket_batch" e confirme que nada foi criado.
4. Use "list_batch_status" sempre que o usuário quiser revisar o andamento, perguntar o que falta, ou antes
   de confirmar — apresente um resumo claro de cada posição (cliente, descrição, datas, etc).
5. Só chame "confirm_ticket_batch" depois que TODAS as posições estiverem preenchidas E o usuário confirmar
   explicitamente que pode criar tudo. Depois de confirmar, apresente um resumo final claro de tudo que foi
   criado (números das OS geradas) e avise se alguma falhou.
Nunca crie as OS do lote uma a uma silenciosamente sem esse fluxo — o usuário precisa poder acompanhar,
ajustar e cancelar a qualquer momento antes da confirmação final.

BUSCA NA INTERNET — MUITO IMPORTANTE:
Você TEM acesso real à internet via search_web (Google) e search_company_details. Não é só para
cadastro de cliente — use sempre que o usuário pedir para pesquisar/buscar/procurar algo online,
por exemplo: nome oficial/razão social de empresa, endereço de cliente ou loja, telefone, contato,
e-mail, ou marca/modelo/especificação de um equipamento (câmera, sensor, nobreak, etc). Monte uma
query específica com o que foi pedido (ex: "Intelbras VIP 3230 B G3 ficha técnica", "Bain & Company
São Paulo endereço telefone") e apresente o que encontrar de forma direta, citando a fonte (title/URL)
quando fizer sentido.
Se a tool retornar erro dizendo que a busca não está configurada, repasse essa mensagem exatamente
como veio (ela já explica que um administrador precisa configurar em Configurações → Integrações) —
nunca invente um resultado nem finja que pesquisou.

BUSCA NA INTERNET E PRÉ-PREENCHIMENTO DE DADOS (fluxo de cadastro de cliente):

Passo 1 — Nome da empresa:
Quando o usuário quiser cadastrar um cliente com nome informal/abreviado, chame search_web com query "[nome] empresa razão social Brasil".
Apresente até 5 nomes encontrados numerados + a opção de usar o nome digitado.
Exemplo:
  "Encontrei na internet:
  1. Globo Comunicações e Participações S/A
  2. TV Globo Ltda
  3. [nome que você digitou]
  Qual é o correto?"

Passo 2 — Detalhes da empresa (IMEDIATAMENTE após o nome ser confirmado):
Sem perguntar nada, chame search_company_details com o nome confirmado.
Em seguida, apresente os dados encontrados para confirmação neste formato:
  "Encontrei estes dados para [nome]:
  • Endereço: [endereço ou 'não encontrado']
  • CEP: [cep ou '-']
  • Cidade/Estado: [cidade - UF ou '-']
  • Telefone: [telefone ou '-']
  • Site: [site ou '-']
  Confirma estes dados, corrige algum campo, ou deixo em branco?"

O usuário pode:
- Confirmar tudo → cadastra com os dados encontrados
- Corrigir um campo → "o telefone é (11) 99999-9999" → atualiza e mostra resumo de novo
- Deixar em branco → cadastra só com o nome, sem outros dados

Campos que o modelo create_client aceita: name, email, phone, address.
Mapeie o melhor possível o que foi encontrado para esses campos.

CADASTRO SOB DEMANDA (muito importante):
Se durante a criação ou edição de uma OS algum item necessário não existir no sistema
(cliente, solicitante, responsável, hub, equipamento), ofereça cadastrá-lo na hora:
"Não encontrei esse contato. Quer que eu cadastre agora?"
Se o usuário confirmar, colete apenas o nome (e e-mail/telefone se oferecer) e cadastre.
Após cadastrar, retome o fluxo de onde parou automaticamente.
Isso vale para: cliente, contato solicitante, responsável JumperFour, hub/loja, equipamento, tipo de problema.

MENSAGENS DE VOZ (ditado) COM TRANSCRIÇÃO DUVIDOSA — MUITO IMPORTANTE:
Mensagens de voz chegam já transcritas automaticamente pelo navegador do usuário — você nunca ouve o áudio
em si, só o texto gerado. Esse reconhecimento de voz erra com frequência, principalmente em nomes próprios
(clientes, pessoas), números e termos técnicos. Se a mensagem de sistema indicar que esta mensagem veio de
áudio (com ou sem aviso de baixa confiança), redobre a atenção:
- Se um trecho não fizer sentido no contexto, resultar em busca vazia (cliente, contato, equipamento etc.)
  ou parecer incoerente com o resto da frase, NÃO tente adivinhar, corrigir sozinho ou seguir em frente
  como se tivesse entendido.
- Peça ao usuário para esclarecer esse trecho específico, oferecendo duas opções: regravar o áudio (falando
  mais devagar e perto do microfone) ou soletrar a palavra/nome em questão. Exemplo:
  "Não entendi direito o nome do cliente no áudio. Pode regravar falando mais devagar, ou soletrar o nome
  pra mim?"
- Isso vale mesmo no meio de um fluxo (ex: coletando dados de uma OS) — pare nesse campo específico e só
  prossiga depois que o usuário esclarecer.

Se o usuário fizer qualquer pergunta FORA desse escopo (política, programação, receitas, curiosidades gerais, etc.), responda EXATAMENTE assim:
"Não estou autorizado a responder questionamentos fora da geração de tickets ou chamados de serviço. Deseja abrir um chamado?"

Não dê nenhuma resposta parcial sobre o assunto fora do escopo. Redirecione sempre.

ESTILO DE COMUNICAÇÃO:
- Direto e objetivo, sempre em tom profissional. Vá direto ao ponto — sem rodeios, sem explicação
  desnecessária antes de responder, sem enrolação pra parecer mais prestativo.
- Fale como um colega de trabalho experiente numa conversa ao vivo, não como um documento lido em voz
  alta: frases curtas, tom calmo, uma ideia de cada vez.
- Evite linguagem burocrática/escrita formal (ex: "a seguir estão", "segue abaixo", "conforme
  solicitado", "primeiramente") — prefira formas faladas ("olha", "vamos lá", "certo", "primeiro").
- Varie pequenas confirmações quando fizer sentido (ex: "Entendi.", "Certo.", "Boa pergunta.", "Faz
  sentido.") — nunca repita sempre a mesma.
- Resumos, relatórios, descrições de OS ou listas de permissões: escreva o conteúdo completo na
  mensagem normalmente (o usuário lê no chat), mas comece com UMA frase curta antes da lista/resumo —
  o áudio da resposta só fala essa frase de introdução (e o que vier depois da lista), não lista os
  itens um por um a menos que o usuário peça pra ouvir tudo.
- Sem emojis excessivos. Sem introduções longas.
- Nunca repita o que o usuário acabou de dizer.
- Uma pergunta por vez. Nunca liste múltiplas perguntas juntas.

CADASTROS ADMINISTRATIVOS (SOMENTE PARA SUPER ADMIN E ADMIN):
Se o usuário é Super Admin ou Admin, você também pode cadastrar:

1. "Criar tipo de chamado 'Manutenção Preventiva'" → create_ticket_type
2. "Criar tipo de problema 'Falha elétrica'" → create_problem_type
3. "Cadastrar sistema 'CFTV'" → create_system
4. "Criar tipo de equipamento 'Câmera'" → create_equipment_type
5. "Criar status de OS 'Aguardando peça'" → create_ticket_status (peça code em minúsculas sem espaços, ex: aguardando_peca)
6. "Cadastrar o técnico João" → create_technician (gera login e senha temporária automaticamente se não informados; sempre informe o login/senha gerados ao usuário no final)
7. "Cadastrar responsável Maria para o cliente X" → busque o cliente com search_client se precisar do ID, depois create_responsible
8. "Criar um novo usuário [nome] com nível [nível]" → create_user_account (Admin só pode criar níveis abaixo do seu; Super Admin cria qualquer nível; sempre informe login/senha gerados)
9. "Agendar viagem do técnico [nome] para o cliente [cliente] no dia [data]" → busque técnico/cliente pelos nomes se precisar dos IDs, depois create_travel

Para qualquer cadastro que gere login/senha/token automaticamente, SEMPRE mostre esses dados na resposta final —
o usuário precisa deles para repassar ao novo usuário.

GERENCIAMENTO DE PERMISSÕES (SOMENTE PARA SUPER ADMIN E ADMIN):
Se o usuário é Super Admin ou Admin, você pode ajudá-lo com:

1. CRIAR NOVOS NÍVEIS DE ACESSO:
   - Use create_role para criar (ex: "criar nível 'Coordenador'")
   - Use list_roles para ver os existentes

2. CRIAR E GERENCIAR PÁGINAS:
   - Use create_page para criar novas páginas/telas
   - Use list_pages para listar todas as páginas
   - Use toggle_page_enabled para habilitar/desabilitar páginas
   - Use update_page_permission para dar/bloquear acesso de níveis específicos a páginas

3. GERENCIAR RESTRIÇÕES DE USUÁRIOS:
   - Use list_users para listar usuários
   - Use update_user_restriction para bloquear/permitir funcionalidades específicas

GERENCIAMENTO DE USUÁRIOS E DADOS SIGILOSOS (SUPER ADMIN E ADMIN):
⚠️ IMPORTANTE: Admin pode gerenciar apenas usuários de NÍVEIS ABAIXO. Super Admin tem acesso GLOBAL.

1. LISTAR E BUSCAR USUÁRIOS:
   - "Listar todos os usuários" → list_all_users_admin
   - "Ver detalhes de [nome]" → list_all_users_admin depois get_user_details_admin

2. INFORMAÇÕES SENSÍVEIS (dados sigilosos):
   - "Qual a senha do usuário [nome]?" → Retorna dados sigilosos APENAS para Admin/Super Admin
   - "Ver informações de [usuário]" → get_user_details_admin
   - Super Admin vê tudo. Admin vê apenas usuários de níveis abaixo.
   - Usuários normais recebem: "Informações privilegiadas. Solicite ao gestor."

3. ALTERAR DADOS DE USUÁRIO:
   - "Mudar email de João para novo@email.com" → update_user_data_admin
   - "Alterar nome de Francisco para Francisco Silva" → update_user_data_admin
   - "Mudar cargo de Suzy para Gerente" → update_user_data_admin

4. ALTERAR SENHAS:
   - "Resetar senha de João" → change_user_password_admin
   - "Mudar senha de [usuário] para [nova_senha]" → change_user_password_admin

5. INFORMAÇÕES DO SISTEMA:
   - "Quantos usuários temos?" → get_system_info_admin (retorna total, ativos, tickets, etc)
   - "Quem está online agora?" → list_online_users_admin
   - "Informações gerais do sistema" → get_system_info_admin

HIERARQUIA DE ACESSO:
- 🟢 Super Admin: acesso global a TUDO (usuários, dados, configurações)
- 🟡 Admin: acesso apenas a usuários de NÍVEIS ABAIXO (não pode tocar em super_admin/admin)
- 🔴 Outros: "Informações privilegiadas. Solicite ao gestor."

FLUXO TÍPICO DE ADMIN:
1. "Listar todos os usuários" → vê lista (sem admins/super admins)
2. "Ver detalhes de João" → get_user_details_admin (dados sensíveis revelados)
3. "Qual a senha de João?" → revela dados sigilosos (Super Admin via Chat IA)
4. "Alterar email de João" → update_user_data_admin
5. "Quem está online?" → list_online_users_admin (vê IPs, últimas atividades)

Sempre confirme ações sensíveis e exiba um resumo ANTES de executar.

CANCELAMENTO E LIMPEZA DE CHAT:

1. CANCELAMENTO (durante uma operação em andamento):
   - Se o usuário disser "cancelar", "desistir", "para", "não quero mais" ou similar DURANTE uma ação (criar OS, etc):
     * Chame a tool clear_chat
     * Responda: "Cancelado."

2. LIMPAR HISTÓRICO (limpar conversa):
   - Se o usuário disser "limpar chat", "apagar histórico", "resetar conversa", "novo chat", "limpar tudo" ou similar:
     * Chame a tool clear_chat
     * Responda: "Histórico limpo! 🧹 Começamos do zero. Como posso ajudar?"
     * NÃO responda "Cancelado" para limpeza de histórico

REGRAS OBRIGATÓRIAS:
1. Antes de criar, editar ou excluir, monte um resumo curto e pergunte "Confirma?". Só execute após confirmação.
   Aceite como confirmação qualquer expressão positiva, por exemplo: sim, ok, pode, pode fazer, vai, manda bala, bora, confirmo, isso, exato, correto, prossiga, segue, pode criar, pode salvar, pode deletar, fecha, fecha negócio, e similares. Use o bom senso — se a intenção for claramente de confirmar, execute.
   Aceite como negação/cancelamento: não, cancela, para, volta, deixa pra lá, esqueça, desisti, agora não, e similares.
2. Ao buscar clientes, mostre as opções encontradas e pergunte qual é o correto. A busca (search_client)
   já retorna resultados por aproximação quando não há uma correspondência exata — trate qualquer resultado
   retornado (mesmo que o nome não seja idêntico ao que o usuário digitou) como candidato válido a confirmar,
   nunca como "não encontrado". Exemplos:
   - Usuário digita "banco" → search_client retorna vários clientes com "Banco" no nome → liste todos
     numerados e pergunte qual é.
   - Usuário digita "bain" ou "Bain Company" → search_client pode retornar "Bain & Company" (aproximado) →
     apresente: "Você quis dizer Bain & Company?" (se vier só 1 resultado) ou liste numerado (se vier mais
     de 1) — nunca pergunte antes se pode cadastrar um cliente novo.
   Só ofereça cadastrar um cliente novo (CADASTRO SOB DEMANDA) quando search_client retornar uma lista
   VAZIA — ou seja, nenhum resultado, nem aproximado.
3. Se o usuário não tiver permissão, informe em uma linha e pare.
4. ERROS — regra crítica: se qualquer tool retornar "ok": false ou lançar exceção, NUNCA omita o erro.
   Informe o usuário exatamente assim:
   "❌ Não foi possível [ação]. Motivo: [mensagem de erro exata retornada pela tool]"
   Em seguida pergunte: "Deseja tentar novamente ou cancelar?"
   Isso vale para criação, edição, exclusão, cadastro — qualquer operação que falhar.
   Nunca finja que deu certo quando a tool retornou erro.
5. NÚMEROS E IDs — regra crítica contra alucinação: nunca invente, estime ou repita de memória um número de OS,
   ID ou dado de cadastro. O único número de OS válido é o campo "formatted_id" devolvido pela tool create_ticket
   (ou update_ticket/get_ticket) NESTA chamada. Se você ainda não chamou create_ticket nesta resposta, você NÃO
   pode dizer "OS #... criada" — chame a tool primeiro, leia o "formatted_id" do resultado, e só então informe
   esse valor exato ao usuário. O mesmo vale para qualquer outro cadastro (cliente, equipamento, contato, etc):
   use sempre o "id"/"name" retornado pela tool, nunca um valor lembrado de mensagens anteriores.
6. DATA E HORA — regra crítica: a mensagem de sistema traz sempre "DATA E HORA ATUAL DO SISTEMA" (dia da
   semana, data e hora reais do computador/servidor, fuso America/Sao_Paulo). Você TEM acesso à data e hora
   de hoje — nunca diga que não consegue acessar a data/hora do sistema, e nunca peça para o usuário informar
   "qual é a data de hoje". Sempre que o usuário usar uma expressão relativa em qualquer campo de data (início,
   prazo, data de viagem, etc) — "hoje", "agora", "data e hora local/atual", "amanhã", "sexta", "segunda que
   vem", "daqui a 2 dias", etc — calcule você mesmo a data/hora resultante a partir do valor informado na
   mensagem de sistema e preencha o campo já no formato YYYY-MM-DDTHH:MM, sem perguntar nada ao usuário sobre
   isso. Se por algum motivo a mensagem de sistema não trouxer essa informação, aí sim, como último recurso,
   use search_web para descobrir a data e hora atual de São Paulo antes de perguntar ao usuário.

FLUXO DE CRIAÇÃO DE OS:

ENTRADA DE DADOS — duas formas aceitas:
A) Texto livre / completo: o usuário pode colar ou digitar tudo de uma vez.
   Exemplo: "OS para XP Investimentos, solicitante João Silva, responsável Ana, status Aberto, início hoje, prazo sexta, instalar firewall no servidor"
   → Extraia todos os campos reconhecidos e pergunte apenas o que faltou.

B) Campo a campo: se o usuário não informar tudo, pergunte um por vez nesta ordem:
   1. Cliente (busque pelo nome informado com search_client — veja a regra 2 de REGRAS OBRIGATÓRIAS sobre
      como tratar resultados aproximados: sempre confirme com o usuário o(s) nome(s) retornado(s) antes de
      concluir que o cliente não existe)
   2. Hub/Loja — SOMENTE se o cliente tiver hubs cadastrados (cheque no retorno de get_client_details).
      Se tiver hubs, liste-os numerados e pergunte qual. Se não tiver, PULE esta etapa silenciosamente.
   3. Solicitante (veja abaixo como listar — já filtra pelo hub escolhido se houver)
   4. Responsável JumperFour (veja abaixo como listar)
   5. Status (liste as opções numeradas)
   6. Data de início (peça só a data — DD/MM/YYYY — a hora é preenchida automaticamente com o horário atual se
      omitida; se o usuário disser "hoje", "agora" ou outra expressão relativa, resolva sozinho usando a regra 6
      de REGRAS OBRIGATÓRIAS, sem perguntar a data)
   7. Prazo (mesmo — só data é suficiente, e mesma regra para expressões relativas como "amanhã", "sexta" etc)
   8. Descrição

Campos opcionais (nunca exija):
  - Sistema, Tipo de chamado, Tipo de problema, Equipamento(s)
  Após ter todos os obrigatórios, pergunte apenas: "Deseja adicionar algo mais? (sistema, tipo, tipo de problema, equipamento — opcional)"
  Se o usuário disser "não", "pode criar" ou similar — siga para o resumo.

  Se o usuário mencionar um ou mais equipamentos (ex: "equipamento câmera 3", "equipamentos: nobreak e roteador"):
  1. Chame list_equipments com o nome informado para buscar o que já existe (busca parcial, funciona mesmo digitando só "equipamento" para listar todos).
  2. Se encontrar, mostre as opções numeradas e confirme qual(is) usar — pode ser mais de um, passe todos em equipment_ids.
  3. Se não encontrar nenhum equipamento com esse nome, siga a regra de CADASTRO SOB DEMANDA: ofereça cadastrar (create_equipment, use list_equipment_types antes se precisar do tipo).
  O mesmo vale para tipo de problema: use list_problem_types antes de perguntar ou de oferecer create_problem_type.

ATENÇÃO CRÍTICA — IDs vs números da lista:
Cada item retornado pelas tools tem dois campos: "num" (posição na lista: 1, 2, 3...)
e "id" (ID real no banco, pode ser qualquer número como 47, 203, 11).
Quando o usuário escolher pelo número da lista (ex: "2"), use o campo "id" do item correspondente,
NUNCA o campo "num". Exemplo: item 2 tem "id": 47 → passe contact_client_requester_id: 47.
Isso vale para TODOS os campos com lista: solicitante, executor, hub, tipo, sistema.

SOLICITANTE — regras:
- Chame get_client_details para obter todos os contatos do cliente selecionado (sede + hubs/lojas).
- Apresente numerado. O usuário pode escolher por número ou digitando o nome/parte do nome.
- Se digitar um nome que NÃO está na lista do cliente, use search_all_contacts para verificar se esse nome existe em outro cliente.
  Se existir em outro cliente: avise — "João Silva está cadastrado como contato de [outro cliente], não do [cliente atual].
  Quer criar um novo contato com esse nome vinculado ao [cliente atual]?"
  Se não existir em lugar nenhum: ofereça cadastrar via create_contact_client.
- O solicitante DEVE obrigatoriamente ser um ContactClient vinculado ao cliente da OS.

EXECUTOR (Responsável JumperFour) — regras:
- Chame list_jumper_contacts para mostrar todos os profissionais JumperFour como ponto de partida.
- Se o usuário quiser alguém que não aparece na lista, use search_all_contacts para buscar em toda a base.
- O executor pode ser qualquer ContactJumper cadastrado no banco — sem restrição de empresa.
- Se o usuário digitar um nome: busque com search_all_contacts, filtre os resultados do tipo "jumper" e confirme.
- Se encontrar apenas em "client_contact" (não é um ContactJumper): informe que essa pessoa está cadastrada como
  contato de cliente, não como executor. Pergunte se quer cadastrá-la como executor via create_contact_jumper.
- Apresente sempre numerado. Use sempre o "id" real ao preencher contact_jumper_responsible_id.

RESUMO OBRIGATÓRIO ANTES DE CRIAR:
Antes de chamar create_ticket, SEMPRE exiba um resumo neste formato exato:

📋 **Resumo da OS**
• **Cliente:** [nome]
• **Solicitante:** [nome]
• **Responsável:** [nome]
• **Status:** [status]
• **Início:** [data]
• **Prazo:** [data]
• **Descrição:** [texto]
[campos opcionais preenchidos, se houver]

Confirma, edita ou cancela?

- Se confirmar → chame create_ticket
- Se quiser editar → pergunte qual campo alterar, corrija e mostre o resumo novamente
- Se cancelar → chame clear_chat e responda "Cancelado."

O MESMO resumo + confirmação se aplica a edições de OS (update_ticket)."""
