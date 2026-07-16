from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import time, timedelta
from django.db.utils import OperationalError, ProgrammingError
import uuid

class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('super_admin', 'Super Admin'),
        ('admin', 'Administrador'),
        ('technician', 'Técnico'),
        ('operator', 'Operador'),
        ('standard', 'Padrão'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    token = models.CharField(max_length=100, unique=True, default=uuid.uuid4)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='standard')
    
    photo = models.ImageField(upload_to='profile_photos/', verbose_name="Foto de Perfil", blank=True, null=True)
    job_title = models.CharField(max_length=100, verbose_name="Cargo", blank=True, null=True)
    station = models.CharField(max_length=100, verbose_name="Posto de Alocação", blank=True, null=True)
    
    # Hierarchy
    supervisor = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Supervisor/Gerente", related_name='subordinates')
    department = models.CharField(max_length=100, verbose_name="Departamento/Área", blank=True, null=True)
    
    personal_phone = models.CharField(max_length=20, verbose_name="Telefone Próprio", blank=True, null=True)
    company_phone = models.CharField(max_length=20, verbose_name="Telefone Empresa", blank=True, null=True)
    
    TECHNICIAN_TYPE_CHOICES = (
        ('fixo', 'Fixo'),
        ('volante', 'Volante'),
    )
    technician_type = models.CharField(max_length=10, choices=TECHNICIAN_TYPE_CHOICES, default='fixo', verbose_name="Tipo de Técnico")
    
    # Fixed Technician Location
    fixed_client = models.ForeignKey('Client', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Empresa (Fixo)", related_name='fixed_technicians')
    fixed_hub = models.ForeignKey('ClientHub', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Hub/Loja (Fixo)", related_name='fixed_technicians')
    
    blocked_until = models.DateTimeField(blank=True, null=True, verbose_name="Bloqueado até")
    blocked_reason = models.CharField(max_length=200, blank=True, null=True, verbose_name="Motivo do Bloqueio")
    allow_pdf_reports = models.BooleanField(default=True, verbose_name="Permitir relatórios PDF")

    # Controle de toasts da lista de OS (no máximo 2x por dia: primeiro acesso e fim do turno)
    ticket_toast_state_date = models.DateField(blank=True, null=True, verbose_name="Data do estado de toast (OS)")
    ticket_toast_morning_shown = models.BooleanField(default=False, verbose_name="Toast (OS) mostrado - primeiro acesso do dia")
    ticket_toast_end_shown = models.BooleanField(default=False, verbose_name="Toast (OS) mostrado - fim do turno")

    # Chat IA
    ai_chat_enabled = models.BooleanField(default=True, verbose_name="Ativar Chat IA")
    ai_proactive_alert_count = models.PositiveIntegerField(default=0, verbose_name="Tentativas de aviso do Jota4 sobre pendências não resolvidas")
    voice_wakeword_enabled = models.BooleanField(default=False, verbose_name="Escuta por voz (chamar o Jota4 dizendo o nome dele)")

    TTS_VOICE_GENDER_CHOICES = [
        ('female', 'Feminina'),
        ('male', 'Masculina'),
    ]
    tts_enabled = models.BooleanField(default=False, verbose_name="Respostas do Jota4 em voz alta")
    tts_voice_gender = models.CharField(max_length=10, choices=TTS_VOICE_GENDER_CHOICES, default='female', verbose_name="Voz preferida")
    # Voz específica escolhida pelo próprio usuário na biblioteca da ElevenLabs (só usada
    # quando o provedor de TTS ativo é 'elevenlabs' — nos demais provedores vale tts_voice_gender).
    elevenlabs_voice_id = models.CharField(max_length=100, blank=True, verbose_name="Voz ElevenLabs")

    # Restrições de Funcionalidades
    can_view_tickets = models.BooleanField(default=True, verbose_name="Visualizar Ordens de Serviço")
    can_create_tickets = models.BooleanField(default=True, verbose_name="Criar Ordens de Serviço")
    can_edit_tickets = models.BooleanField(default=True, verbose_name="Editar Ordens de Serviço")
    can_delete_tickets = models.BooleanField(default=True, verbose_name="Deletar Ordens de Serviço")
    can_view_checklists = models.BooleanField(default=True, verbose_name="Visualizar Checklists")
    can_create_checklists = models.BooleanField(default=True, verbose_name="Criar Checklists")
    can_view_reports = models.BooleanField(default=True, verbose_name="Visualizar Relatórios")

    def get_role_display(self):
        role = (self.role or '').strip()
        if not role:
            return ""
        try:
            role_obj = RoleLevel.objects.filter(code=role).first()
            if role_obj:
                return role_obj.name
        except (OperationalError, ProgrammingError):
            pass
        return dict(self.ROLE_CHOICES).get(role, role)

    def __str__(self):
        return f"{self.user.username} - {self.role}"


class RoleLevel(models.Model):
    code = models.SlugField(max_length=50, unique=True, verbose_name="Código do Nível")
    name = models.CharField(max_length=100, verbose_name="Nome do Nível")
    is_system = models.BooleanField(default=False, verbose_name="Nível do Sistema")
    is_active = models.BooleanField(default=True, verbose_name="Ativo")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Nível de Usuário"
        verbose_name_plural = "Níveis de Usuário"
        ordering = ['name']

    def __str__(self):
        return self.name


class AppPage(models.Model):
    code = models.SlugField(max_length=80, unique=True, verbose_name="Código da Página")
    name = models.CharField(max_length=120, verbose_name="Nome da Página")
    url_name = models.CharField(max_length=120, unique=True, verbose_name="URL Name (Django)")
    group = models.CharField(max_length=80, blank=True, null=True, verbose_name="Grupo")
    order = models.PositiveIntegerField(default=0, verbose_name="Ordem")
    is_enabled = models.BooleanField(default=True, verbose_name="Habilitada")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Página"
        verbose_name_plural = "Páginas"
        ordering = ['group', 'order', 'name']

    def __str__(self):
        return self.name


class RolePagePermission(models.Model):
    role = models.ForeignKey(RoleLevel, on_delete=models.CASCADE, related_name='page_permissions', verbose_name="Nível")
    page = models.ForeignKey(AppPage, on_delete=models.CASCADE, related_name='role_permissions', verbose_name="Página")
    allowed = models.BooleanField(default=True, verbose_name="Permitida")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Permissão por Página"
        verbose_name_plural = "Permissões por Página"
        unique_together = ('role', 'page')

    def __str__(self):
        return f"{self.role.code} -> {self.page.url_name}: {'ok' if self.allowed else 'bloq'}"

class Client(models.Model):
    name = models.CharField(max_length=200, verbose_name="Nome do Cliente")
    logo = models.ImageField(upload_to='client_logos/', verbose_name="Logomarca", blank=True, null=True)
    email = models.EmailField(verbose_name="Email", blank=True, null=True)
    phone = models.CharField(max_length=20, verbose_name="Telefone", blank=True, null=True)
    phone2 = models.CharField(max_length=20, verbose_name="Telefone 2", blank=True, null=True)
    address = models.TextField(verbose_name="Endereço", blank=True, null=True)
    
    # Contato 1
    contact1_name = models.CharField(max_length=100, verbose_name="Contato 1 (Nome)", blank=True, null=True)
    contact1_phone = models.CharField(max_length=20, verbose_name="Contato 1 (Telefone)", blank=True, null=True)
    contact1_email = models.EmailField(verbose_name="Contato 1 (Email)", blank=True, null=True)
    
    # Contato 2
    contact2_name = models.CharField(max_length=100, verbose_name="Contato 2 (Nome)", blank=True, null=True)
    contact2_phone = models.CharField(max_length=20, verbose_name="Contato 2 (Telefone)", blank=True, null=True)
    contact2_email = models.EmailField(verbose_name="Contato 2 (Email)", blank=True, null=True)
    
    # Excel Import Fields
    group = models.CharField(max_length=100, verbose_name="Grupo", blank=True, null=True)
    cm_code = models.CharField(max_length=50, verbose_name="CM", blank=True, null=True)
    supervisor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='supervised_clients', verbose_name="Supervisor")
    systems = models.ManyToManyField('System', blank=True, related_name='clients', verbose_name="Sistemas")
    periodicity = models.CharField(max_length=100, verbose_name="Periodicidade", blank=True, null=True)
    visits_count = models.IntegerField(default=0, verbose_name="Quantidade de Visitas", blank=True, null=True)
    emergency_policy = models.CharField(max_length=100, verbose_name="Emergenciais", blank=True, null=True)
    emergency_used = models.CharField(max_length=100, verbose_name="Emergencial Utilizadas", blank=True, null=True)
    service_hours = models.CharField(max_length=100, verbose_name="Horário de Atendimento", blank=True, null=True)
    technicians = models.ManyToManyField(User, blank=True, related_name='client_allocations', verbose_name="Técnicos Alocados")
    city = models.CharField(max_length=100, verbose_name="Cidade", blank=True, null=True)
    state = models.CharField(max_length=100, verbose_name="Estado", blank=True, null=True)
    monitoring_cso = models.CharField(max_length=100, verbose_name="Monitoramento CSO", blank=True, null=True)
    alarms_wpp = models.CharField(max_length=100, verbose_name="Alarmes WPP", blank=True, null=True)
    leankeep_assets = models.CharField(max_length=100, verbose_name="Ativos Leankeep", blank=True, null=True)
    maintenance_plan = models.CharField(max_length=200, verbose_name="Plano de Manutenção", blank=True, null=True)
    plan_review_due = models.CharField(max_length=50, verbose_name="Data Limite para revisão", blank=True, null=True)
    plan_review_status = models.CharField(max_length=50, verbose_name="Revisão do plano", blank=True, null=True)
    
    is_preferred = models.BooleanField(default=False, verbose_name="Empresa Preferencial/Padrão")
    
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.is_preferred:
            # Unset is_preferred for all other clients
            Client.objects.filter(is_preferred=True).exclude(pk=self.pk).update(is_preferred=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"

class ClientHub(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='hubs', verbose_name="Cliente")
    name = models.CharField(max_length=200, verbose_name="Nome do Hub/Loja")
    logo = models.ImageField(upload_to='hub_logos/', verbose_name="Logomarca do Hub", blank=True, null=True)
    address = models.TextField(verbose_name="Endereço", blank=True, null=True)
    contact_name = models.CharField(max_length=100, verbose_name="Contato (Responsável)", blank=True, null=True)
    phone = models.CharField(max_length=20, verbose_name="Telefone", blank=True, null=True)
    email = models.EmailField(verbose_name="Email", blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.client.name}"
    
    class Meta:
        verbose_name = "Hub/Loja"
        verbose_name_plural = "Hubs/Lojas"

class EquipmentType(models.Model):
    name = models.CharField(max_length=100, verbose_name="Tipo de Equipamento")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Tipo de Equipamento"
        verbose_name_plural = "Tipos de Equipamento"

class Equipment(models.Model):
    name = models.CharField(max_length=200, verbose_name="Nome do Equipamento")
    equipment_type = models.ForeignKey(EquipmentType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Tipo de Equipamento")
    description = models.TextField(verbose_name="Descrição", blank=True, null=True)
    
    def __str__(self):
        if self.equipment_type:
            return f"{self.name} ({self.equipment_type.name})"
        return self.name
    
    class Meta:
        verbose_name = "Equipamento"
        verbose_name_plural = "Equipamentos"

class OrderType(models.Model):
    name = models.CharField(max_length=100, verbose_name="Tipo de Ordem")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Tipo de Ordem"
        verbose_name_plural = "Tipos de Ordem"

class ProblemType(models.Model):
    name = models.CharField(max_length=100, verbose_name="Tipo de Problema")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Tipo de Problema"
        verbose_name_plural = "Tipos de Problema"

class ContactPerson(models.Model):
    ORIGIN_CHOICES = (
        ('client', 'Contato do Cliente'),
        ('jumperfour', 'Planilha JumperFour'),
        ('manual', 'Cadastro Manual'),
    )
    
    name = models.CharField(max_length=200, verbose_name="Nome")
    email = models.EmailField(verbose_name="Email", blank=True, null=True)
    phone = models.CharField(max_length=20, verbose_name="Telefone", blank=True, null=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Cliente Associado", related_name='contact_persons')
    origin = models.CharField(max_length=20, choices=ORIGIN_CHOICES, default='manual', verbose_name="Origem")
    is_active = models.BooleanField(default=True, verbose_name="Ativo")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name}" + (f" ({self.client.name})" if self.client else "")
    
    class Meta:
        verbose_name = "Contato"
        verbose_name_plural = "Contatos"
        ordering = ['client', 'name']


class ContactClient(models.Model):
    name = models.CharField(max_length=200, verbose_name="Nome")
    email = models.EmailField(verbose_name="Email", blank=True, null=True)
    phone = models.CharField(max_length=20, verbose_name="Telefone", blank=True, null=True)

    client_ref_id = models.IntegerField(blank=True, null=True, db_index=True, verbose_name="ID Cliente (referência)")
    client_name = models.CharField(max_length=200, blank=True, default="", verbose_name="Cliente")

    hub_ref_id = models.IntegerField(blank=True, null=True, db_index=True, verbose_name="ID Hub/Loja (referência)")
    hub_name = models.CharField(max_length=200, blank=True, default="", verbose_name="Hub/Loja")

    is_active = models.BooleanField(default=True, verbose_name="Ativo")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def display_label(self):
        """Formato: Cliente | Hub -> Nome"""
        prefix = self.client_name or ''
        if self.hub_name:
            prefix += f" | {self.hub_name}"
        if prefix:
            return f"{prefix} -> {self.name}"
        return self.name

    class Meta:
        verbose_name = "Contato do Cliente"
        verbose_name_plural = "Contatos dos Clientes"
        ordering = ["client_name", "hub_name", "name"]


class ContactJumper(models.Model):
    name = models.CharField(max_length=200, verbose_name="Nome")
    email = models.EmailField(verbose_name="Email", blank=True, null=True)
    phone = models.CharField(max_length=20, verbose_name="Telefone", blank=True, null=True)
    department = models.CharField(max_length=120, blank=True, default="", verbose_name="Departamento")
    role = models.CharField(max_length=120, blank=True, default="", verbose_name="Cargo/Função")

    is_active = models.BooleanField(default=True, verbose_name="Ativo")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def display_label(self):
        pieces = [self.name]
        if self.email:
            pieces.append(self.email)
        if self.phone:
            pieces.append(self.phone)
        return " - ".join(pieces)

    class Meta:
        verbose_name = "Contato JumperFour"
        verbose_name_plural = "Contatos JumperFour"
        ordering = ["name"]


class TicketType(models.Model):
    name = models.CharField(max_length=100, verbose_name="Tipo de Chamado")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Tipo de Chamado"
        verbose_name_plural = "Tipos de Chamados"

class System(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nome do Sistema")
    color = models.CharField(max_length=20, verbose_name="Cor (Hex)", default="#6c757d", help_text="Ex: #FF0000 para vermelho")
    description = models.TextField(verbose_name="Descrição", blank=True, null=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Sistema"
        verbose_name_plural = "Sistemas"

class SystemSettings(models.Model):
    session_timeout_minutes = models.PositiveIntegerField(
        default=30, 
        verbose_name="Tempo de Sessão (minutos)", 
        help_text="Tempo de inatividade para desconectar o usuário automaticamente."
    )
    
    allow_checklist_pdf_debug = models.BooleanField(
        default=False, 
        verbose_name="Liberar PDF de Checklist (Debug)", 
        help_text="Se marcado, permite gerar PDF de checklists não finalizados para testes."
    )

    # === Passagem de Turno / Turnos ===
    day_shift_start = models.TimeField(default=time(8, 0), verbose_name="Início do turno diurno")
    day_shift_end = models.TimeField(default=time(20, 0), verbose_name="Fim do turno diurno")

    enable_night_shift = models.BooleanField(default=False, verbose_name="Ativar turno noturno")
    night_shift_start = models.TimeField(default=time(20, 0), verbose_name="Início do turno noturno")
    night_shift_end = models.TimeField(default=time(8, 0), verbose_name="Fim do turno noturno")

    # === Inteligência Artificial ===
    # O provedor/modelo/chave em uso ficam em AIProviderConfig (permite cadastrar
    # várias e alternar qual está ativa) — aqui fica só o liga/desliga geral,
    # que é ortogonal a qual configuração está ativa no momento.
    ai_enabled = models.BooleanField(default=False, verbose_name="Ativar Assistente de IA")

    # Liga/desliga só a parte de voz e áudio (escuta por wake-word, ditado por voz
    # e respostas faladas/TTS) para todos os usuários, mantendo o Chat IA por texto
    # funcionando normalmente — diferente do ai_enabled acima, que desliga tudo.
    voice_globally_enabled = models.BooleanField(default=True, verbose_name="Ativar Voz e Áudio (geral)")

    # === Integrações — Voz: livre por usuário ou universal ===
    # Provedor/chave/vozes padrão em uso ficam em VoiceProviderConfig (mesma lógica
    # de lista + ativa do AIProviderConfig). Aqui só fica a decisão de QUEM escolhe
    # a voz: cada usuário (como sempre foi) ou uma única voz pra todos, definida
    # pelo Super Admin — nesse caso a escolha em Meu Perfil é ignorada.
    VOICE_SELECTION_MODE_CHOICES = [
        ('per_user', 'Cada usuário escolhe a própria voz'),
        ('universal', 'Voz única para todos (definida pelo Super Admin)'),
    ]
    voice_selection_mode = models.CharField(max_length=20, choices=VOICE_SELECTION_MODE_CHOICES, default='per_user', verbose_name="Modo de Seleção de Voz")
    universal_tts_voice_gender = models.CharField(max_length=10, choices=UserProfile.TTS_VOICE_GENDER_CHOICES, default='female', verbose_name="Gênero da Voz Universal")
    universal_elevenlabs_voice_id = models.CharField(max_length=100, blank=True, verbose_name="ID da Voz ElevenLabs Universal")

    def __str__(self):
        return "Configurações do Sistema"

    class Meta:
        verbose_name = "Configuração do Sistema"
        verbose_name_plural = "Configurações do Sistema"


class AIProviderConfig(models.Model):
    """
    Uma configuração cadastrada de provedor de IA (nome, provedor, modelo, chave).
    Podem existir várias; a marcada com is_active=True é a que o Jota4 usa no
    momento — trocar de provedor/modelo vira só ativar outra linha da lista.
    """
    PROVIDER_CHOICES = [
        ('deepseek', 'DeepSeek'),
        ('openai', 'OpenAI (GPT)'),
        ('anthropic', 'Anthropic (Claude)'),
        ('gemini', 'Google Gemini'),
    ]

    name = models.CharField(max_length=100, verbose_name="Nome")
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='deepseek', verbose_name="Provedor de IA")
    model = models.CharField(
        max_length=100, blank=True, verbose_name="Modelo",
        help_text="Deixe em branco para usar o modelo padrão do provedor"
    )
    api_key = models.CharField(max_length=500, blank=True, verbose_name="Chave de API")
    is_active = models.BooleanField(default=False, verbose_name="Ativa (em uso pelo Jota4)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.get_provider_display()})"

    def masked_api_key(self):
        """Só os últimos 4 caracteres visíveis — usado na listagem, nunca a chave completa."""
        if not self.api_key:
            return ""
        if len(self.api_key) <= 4:
            return "•" * len(self.api_key)
        return "•" * (len(self.api_key) - 4) + self.api_key[-4:]

    def save(self, *args, **kwargs):
        if self.is_active:
            # Garante que só uma fique ativa por vez
            AIProviderConfig.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Configuração de IA"
        verbose_name_plural = "Configurações de IA"
        ordering = ['-is_active', 'name']


class SearchProviderConfig(models.Model):
    """
    Uma configuração cadastrada de provedor de busca na internet (nome, provedor,
    chaves). Podem existir várias; a marcada com is_active=True é a que o Jota4
    usa no momento (tools search_web / search_company_details) — trocar de
    provedor vira só ativar outra linha da lista, sem perder as demais.
    """
    PROVIDER_CHOICES = [
        ('google', 'Google Custom Search'),
        ('tavily', 'Tavily'),
    ]

    name = models.CharField(max_length=100, verbose_name="Nome")
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='google', verbose_name="Provedor de Busca")
    api_key = models.CharField(max_length=200, blank=True, verbose_name="Chave de API")
    google_search_engine_id = models.CharField(max_length=100, blank=True, verbose_name="ID do Mecanismo de Busca (cx) — só Google")
    is_active = models.BooleanField(default=False, verbose_name="Ativa (em uso pelo Jota4)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.get_provider_display()})"

    def masked_api_key(self):
        if not self.api_key:
            return ""
        if len(self.api_key) <= 4:
            return "•" * len(self.api_key)
        return "•" * (len(self.api_key) - 4) + self.api_key[-4:]

    def save(self, *args, **kwargs):
        if self.is_active:
            SearchProviderConfig.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Configuração de Busca"
        verbose_name_plural = "Configurações de Busca"
        ordering = ['-is_active', 'name']


class VoiceProviderConfig(models.Model):
    """
    Uma configuração cadastrada de provedor de voz/TTS (nome, provedor, chaves,
    vozes padrão por gênero na ElevenLabs). Podem existir várias; a marcada com
    is_active=True é a que o Jota4 usa no momento — trocar de provedor vira só
    ativar outra linha da lista, sem perder as demais.
    """
    PROVIDER_CHOICES = [
        ('browser', 'Navegador (gratuito)'),
        ('google', 'Google Cloud Text-to-Speech'),
        ('elevenlabs', 'ElevenLabs'),
    ]

    name = models.CharField(max_length=100, verbose_name="Nome")
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='browser', verbose_name="Provedor de Voz (TTS)")
    api_key = models.CharField(max_length=200, blank=True, verbose_name="Chave de API")
    elevenlabs_voice_id_female = models.CharField(max_length=100, blank=True, verbose_name="ID da Voz Feminina (ElevenLabs)")
    elevenlabs_voice_id_male = models.CharField(max_length=100, blank=True, verbose_name="ID da Voz Masculina (ElevenLabs)")
    is_active = models.BooleanField(default=False, verbose_name="Ativa (em uso pelo Jota4)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.get_provider_display()})"

    def masked_api_key(self):
        if not self.api_key:
            return ""
        if len(self.api_key) <= 4:
            return "•" * len(self.api_key)
        return "•" * (len(self.api_key) - 4) + self.api_key[-4:]

    def save(self, *args, **kwargs):
        if self.is_active:
            VoiceProviderConfig.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Configuração de Voz"
        verbose_name_plural = "Configurações de Voz"
        ordering = ['-is_active', 'name']


class AIChatSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_chat_sessions')
    title = models.CharField(max_length=200, blank=True, verbose_name="Título")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Sessão de {self.user.get_full_name() or self.user.username} — {self.created_at:%d/%m/%Y %H:%M}"

    class Meta:
        verbose_name = "Sessão de Chat IA"
        verbose_name_plural = "Sessões de Chat IA"
        ordering = ['-updated_at']


class AIChatMessage(models.Model):
    ROLE_CHOICES = [
        ('user', 'Usuário'),
        ('assistant', 'Assistente'),
        ('tool', 'Ferramenta'),
    ]
    session = models.ForeignKey(AIChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    # Mensagem de voz: guarda o áudio gravado para tocar no chat (estilo WhatsApp);
    # 'content' continua com a transcrição, usada só internamente para a IA responder
    # — o texto falado não é mostrado na bolha quando há áudio.
    audio = models.FileField(upload_to='ai_chat_audio/%Y/%m/', null=True, blank=True, verbose_name="Áudio (mensagem de voz)")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.role}] {self.content[:60]}"

    class Meta:
        verbose_name = "Mensagem de Chat IA"
        verbose_name_plural = "Mensagens de Chat IA"
        ordering = ['created_at']


class AIUserMemory(models.Model):
    """
    Memória persistente do Chat IA (Jota4) para um usuário específico: trejeitos,
    forma de tratamento preferida, gírias/termos, atalhos de criação e padrões de
    trabalho aprendidos ao longo das conversas — para personalizar o atendimento
    já na primeira mensagem de cada nova sessão.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='ai_memory')
    notes = models.TextField(blank=True, default="", verbose_name="Notas aprendidas")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Memória IA de {self.user.get_full_name() or self.user.username}"

    class Meta:
        verbose_name = "Memória do Chat IA"
        verbose_name_plural = "Memórias do Chat IA"


class AITicketBatchDraft(models.Model):
    """
    Rascunho de criação de OS em lote pelo Chat IA (Jota4) — o usuário pede para
    criar várias OS de uma vez, o Jota4 vai coletando os dados de cada uma aqui
    (permitindo ajuste/cancelamento) e só cria de fato após confirmação final.
    Um por usuário por vez (não vinculado a uma sessão/janela de chat específica,
    já que o mesmo usuário pode continuar pelo chat principal ou pelo particular).
    """
    STATUS_CHOICES = (
        ('draft', 'Rascunho'),
        ('confirmed', 'Confirmado'),
        ('cancelled', 'Cancelado'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_ticket_batch_drafts')
    total_count = models.PositiveIntegerField(verbose_name="Quantidade total de OS no lote")
    shared_defaults = models.JSONField(default=dict, blank=True, verbose_name="Campos padrão compartilhados")
    items = models.JSONField(default=list, blank=True, verbose_name="Rascunhos de cada OS (um por posição)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Lote de {self.total_count} OS de {self.user.username} ({self.get_status_display()})"

    class Meta:
        verbose_name = "Lote de OS (Chat IA)"
        verbose_name_plural = "Lotes de OS (Chat IA)"


class PrivateChatThread(models.Model):
    """Conversa particular (1:1) entre dois usuários logados, no estilo Messenger.
    user_a sempre tem o menor ID — garante uma linha única por par de usuários."""
    user_a = models.ForeignKey(User, on_delete=models.CASCADE, related_name='private_threads_as_a')
    user_b = models.ForeignKey(User, on_delete=models.CASCADE, related_name='private_threads_as_b')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user_a', 'user_b')
        verbose_name = "Conversa Particular"
        verbose_name_plural = "Conversas Particulares"
        ordering = ['-updated_at']

    def other_user(self, current_user):
        return self.user_b if self.user_a_id == current_user.id else self.user_a

    def __str__(self):
        return f"{self.user_a.username} <-> {self.user_b.username}"


class PrivateChatMessage(models.Model):
    thread = models.ForeignKey(PrivateChatThread, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_private_chat_messages', verbose_name="Remetente (vazio = Jota4)")
    content = models.TextField()
    is_ai_message = models.BooleanField(default=False, verbose_name="Mensagem do Jota4")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = "Mensagem de Chat Particular"
        verbose_name_plural = "Mensagens de Chat Particular"

    def __str__(self):
        who = "Jota4" if self.is_ai_message else (self.sender.username if self.sender else "?")
        return f"[{who}] {self.content[:60]}"


class PrivateChatReadState(models.Model):
    """Até qual mensagem (id) cada usuário já viu, por conversa — usado pelo poll
    leve do front-end para saber quando abrir/piscar um popup novo."""
    thread = models.ForeignKey(PrivateChatThread, on_delete=models.CASCADE, related_name='read_states')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='private_chat_read_states')
    last_read_message_id = models.PositiveIntegerField(default=0)
    # "Limpar" o chat particular só esconde o histórico ANTERIOR para quem pediu
    # (como um "limpar conversa" de app de mensagens) — a outra pessoa continua
    # vendo tudo normalmente, nada é apagado do banco de dados.
    cleared_at = models.DateTimeField(null=True, blank=True, verbose_name="Limpou o histórico até (somente para este usuário)")

    class Meta:
        unique_together = ('thread', 'user')
        verbose_name = "Estado de Leitura (Chat Particular)"
        verbose_name_plural = "Estados de Leitura (Chat Particular)"


class ShiftHandover(models.Model):
    SHIFT_TYPE_CHOICES = (
        ('day', 'Diurno'),
        ('night', 'Noturno'),
    )

    shift_date = models.DateField(verbose_name="Data do turno")
    shift_type = models.CharField(max_length=10, choices=SHIFT_TYPE_CHOICES, default='day', verbose_name="Tipo de turno")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('shift_date', 'shift_type')
        ordering = ['-shift_date', '-id']
        verbose_name = "Passagem de Turno"
        verbose_name_plural = "Passagens de Turno"

    def __str__(self):
        return f"{self.shift_date} ({self.get_shift_type_display()})"


class ShiftHandoverEntry(models.Model):
    handover = models.ForeignKey(ShiftHandover, on_delete=models.CASCADE, related_name='entries', verbose_name="Turno")
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies', verbose_name="Resposta para")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Criado por")
    text = models.TextField(verbose_name="Texto")
    ticket = models.ForeignKey('Ticket', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Ticket gerado", related_name="handover_entries")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = "Anotação do Turno"
        verbose_name_plural = "Anotações do Turno"


class ShiftHandoverEntryAlert(models.Model):
    """
    Alerta direcionado de uma anotação para um usuário (passagem de turno).
    Enquanto não houver acknowledged_at, o alerta fica pendente e deve disparar toast no login.
    """
    PRIORITY_CHOICES = (
        ('high', 'Alta'),
        ('medium', 'Média'),
        ('low', 'Baixa'),
    )

    entry = models.ForeignKey(ShiftHandoverEntry, on_delete=models.CASCADE, related_name='alerts', verbose_name="Anotação")
    target_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='handover_alerts', verbose_name="Usuário alvo")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='handover_alerts_created', verbose_name="Criado por")
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium', verbose_name="Prioridade")

    class Meta:
        unique_together = ('entry', 'target_user')
        ordering = ['-created_at', '-id']
        verbose_name = "Alerta de Anotação (Turno)"
        verbose_name_plural = "Alertas de Anotação (Turno)"

class MicrosoftGraphToken(models.Model):
    purpose = models.SlugField(max_length=50, unique=True)
    access_token = models.TextField(blank=True, null=True)
    refresh_token = models.TextField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.purpose

class ClientSyncState(models.Model):
    source = models.SlugField(max_length=50, unique=True, default='sharepoint')
    etag = models.CharField(max_length=200, blank=True, null=True)
    remote_last_modified = models.DateTimeField(blank=True, null=True)
    last_checked_at = models.DateTimeField(blank=True, null=True)
    last_synced_at = models.DateTimeField(blank=True, null=True)
    last_success_at = models.DateTimeField(blank=True, null=True)
    last_error = models.TextField(blank=True, null=True)
    is_running = models.BooleanField(default=False)
    running_started_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.source

class TicketStatus(models.Model):
    code = models.SlugField(max_length=50, unique=True, verbose_name="Código")
    name = models.CharField(max_length=100, verbose_name="Nome do Status")
    color = models.CharField(max_length=20, verbose_name="Cor de Fundo (Hex)", default="#6c757d",
                             help_text="Código HEX da cor de fundo da badge (ex: #28a745).")
    font_color = models.CharField(max_length=20, blank=True, default="",
                                   verbose_name="Cor da Fonte (Hex)",
                                   help_text="Código HEX da cor do texto da badge (ex: #ffffff). Deixe em branco para contraste automático.")
    image = models.ImageField(upload_to='ticket_status_icons/', verbose_name="Imagem do Status", blank=True, null=True,
                               help_text="Imagem personalizada (se não definir, usa a badge com a cor escolhida)")
    image_width = models.PositiveIntegerField(default=100, verbose_name="Largura da Imagem (px)")
    image_height = models.PositiveIntegerField(default=26, verbose_name="Altura da Imagem (px)")
    row_color = models.CharField(max_length=20, blank=True, default="",
                                  verbose_name="Cor de Fundo (Hex)",
                                  help_text="Código HEX da cor de fundo do card na lista (ex: #28a745). Deixe em branco para usar o padrão.")
    order = models.PositiveIntegerField(default=0, verbose_name="Ordem")
    is_active = models.BooleanField(default=True, verbose_name="Ativo")

    class Meta:
        verbose_name = "Status de OS"
        verbose_name_plural = "Status de OS"
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

class Ticket(models.Model):
    STATUS_CHOICES = (
        ('open', 'Em Aberto'),
        ('in_progress', 'Em Andamento'),
        ('pending', 'Aguardando Aprovação'),
        ('finished', 'Finalizado'),
        ('canceled', 'Cancelado'),
    )

    DELETE_STATUS_CHOICES = (
        ('none', 'Nenhuma'),
        ('pending', 'Solicitada'),
        ('rejected', 'Rejeitada'),
    )

    CALL_TYPE_CHOICES = (
        ('acidente_com_afastamento', 'Acidente com Afastamento'),
        ('acidente_sem_afastamento', 'Acidente sem Afastamento'),
        ('acompanhamento', 'Acompanhamento'),
        ('anomalia_critica', 'Anomalia Crítica'),
        ('anomalia_simples', 'Anomalia Simples'),
        ('chamado', 'Chamado'),
        ('melhoria', 'Melhoria'),
        ('preventiva', 'Preventiva'),
        ('processo', 'Processo'),
        ('quebra', 'Quebra'),
        ('situacao_risco', 'Situação de Risco'),
    )
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE, verbose_name="Cliente")
    hub = models.ForeignKey(ClientHub, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Hub/Loja")
    technicians = models.ManyToManyField(User, verbose_name="Técnicos Responsáveis", blank=True, related_name='assigned_tickets')
    requester = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Solicitante", related_name='requested_tickets')
    requesters = models.ManyToManyField(User, verbose_name="Solicitantes", blank=True, related_name='requested_tickets_multi')

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_tickets',
        verbose_name="Criado por",
    )
    
    # Novos campos para contatos
    contact_requester = models.ForeignKey(ContactPerson, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Solicitante (Contato)", related_name='tickets_as_requester')
    contact_responsible = models.ForeignKey(ContactPerson, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Responsável/Executor (Contato)", related_name='tickets_as_responsible')
    contact_client_requester = models.ForeignKey(ContactClient, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Solicitante (Contato do Cliente)", related_name='tickets_as_requester')
    contact_jumper_responsible = models.ForeignKey(ContactJumper, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Responsável/Executor (Contato JumperFour)", related_name='tickets_as_responsible')
    
    systems = models.ManyToManyField(System, verbose_name="Sistemas", blank=True, related_name="tickets")
    area_group = models.CharField(max_length=100, verbose_name="Grupo de Áreas", blank=True, null=True)
    area_subgroup = models.CharField(max_length=100, verbose_name="Subgrupo de Áreas", blank=True, null=True)
    area = models.CharField(max_length=100, verbose_name="Área", blank=True, null=True)
    
    call_type = models.CharField(max_length=50, choices=CALL_TYPE_CHOICES, verbose_name="Tipo de Chamado (Legacy)", blank=True, null=True)
    ticket_type = models.ForeignKey(TicketType, on_delete=models.SET_NULL, verbose_name="Tipo de Chamado", null=True, blank=True, related_name='tickets')

    # Legacy field, but keeping it as it was there. Maybe user wants to use call_type instead.
    order_type = models.ForeignKey(OrderType, on_delete=models.PROTECT, verbose_name="Tipo de Ordem", null=True, blank=True)
    equipments = models.ManyToManyField(Equipment, verbose_name="Equipamentos", blank=True, related_name='tickets')
    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, verbose_name="Equipamento (Legacy)", null=True, blank=True)
    problem_type = models.ForeignKey(ProblemType, on_delete=models.PROTECT, verbose_name="Tipo de Problema", null=True)
    leankeep_id = models.CharField(max_length=50, verbose_name="Nº Ocorrência Leankeep", blank=True, null=True)
    
    description = models.TextField(verbose_name="Descrição Detalhada", blank=True)
    final_description = models.TextField(verbose_name="Descrição Final (Resolução)", blank=True, null=True)
    image = models.ImageField(upload_to='tickets/', null=True, blank=True, verbose_name="Imagem do Evento")
    
    start_date = models.DateTimeField(null=True, blank=True, verbose_name="Data de Início")
    deadline = models.DateTimeField(null=True, blank=True, verbose_name="Data Limite para Execução")
    estimated_time = models.DurationField(null=True, blank=True, verbose_name="Tempo Estimado")
    
    status = models.CharField(max_length=50, default='open', verbose_name="Status")

    # Fluxo de exclusão com aprovação
    delete_status = models.CharField(
        max_length=20,
        choices=DELETE_STATUS_CHOICES,
        default='none',
        verbose_name="Status de Exclusão",
    )
    delete_requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ticket_delete_requests',
        verbose_name="Exclusão solicitada por",
    )
    delete_requested_at = models.DateTimeField(null=True, blank=True, verbose_name="Exclusão solicitada em")
    delete_request_reason = models.CharField(max_length=250, blank=True, default="", verbose_name="Motivo da solicitação (opcional)")

    delete_decided_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ticket_delete_decisions',
        verbose_name="Solicitação decidida por",
    )
    delete_decided_at = models.DateTimeField(null=True, blank=True, verbose_name="Solicitação decidida em")
    delete_decision_note = models.CharField(max_length=250, blank=True, default="", verbose_name="Observação da decisão (opcional)")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")
    
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="Data de Finalização")

    @property
    def formatted_id(self):
        return f"JMP{self.id:05d}"

    @property
    def creator_user(self):
        """
        Usuário que abriu/criou a OS.
        Preferência: created_by (novo) -> requester (legado).
        """
        return self.created_by or self.requester

    @property
    def creator_display_name(self):
        u = self.creator_user
        if not u:
            return ""
        full = (u.get_full_name() or "").strip()
        if full:
            return full
        return (u.username or "").strip()

    @property
    def creator_role_label(self):
        """
        Retorna o nível/role do usuário criador, sem quebrar template se o perfil não existir.
        """
        u = self.creator_user
        if not u:
            return ""
        try:
            profile = getattr(u, "profile", None)
            if not profile:
                return ""
            label = ""
            try:
                label = (profile.get_role_display() or "").strip()
            except Exception:
                label = ""
            if label:
                return label
            return (getattr(profile, "role", "") or "").strip()
        except Exception:
            return ""

    @property
    def creator_photo_url(self):
        """
        URL da foto do perfil do criador. Retorna '' se não existir.
        """
        u = self.creator_user
        if not u:
            return ""
        try:
            profile = getattr(u, "profile", None)
            photo = getattr(profile, "photo", None) if profile else None
            if photo and getattr(photo, "url", None):
                return photo.url
        except Exception:
            return ""
        return ""

    @property
    def creator_job_title(self):
        """
        Cargo (job_title) do usuário criador. Retorna '' se não existir.
        """
        u = self.creator_user
        if not u:
            return ""
        try:
            profile = getattr(u, "profile", None)
            if not profile:
                return ""
            return (getattr(profile, "job_title", "") or "").strip()
        except Exception:
            return ""

    @property
    def calculated_hours(self):
        if not self.start_date or not self.deadline:
            return None
            
        # Ensure we are comparing dates, ignoring time if it was set
        start = self.start_date.date()
        end = self.deadline.date()
        
        if end < start:
            return None
            
        # Calculate days difference (inclusive)
        days = (end - start).days + 1
        
        # 8.8 hours per day (8h 48m)
        total_hours = days * 8.8
        
        # Format for display
        hours = int(total_hours)
        minutes = int((total_hours - hours) * 60)
        
        return f"{hours}:{minutes:02d}"

    @property
    def status_color(self):
        """Retorna HEX do status, ou fallback para nomes Bootstrap antigos."""
        try:
            ts = TicketStatus.objects.filter(code=self.status).first()
            if ts and ts.color:
                return ts.color
        except Exception:
            pass
        colors = {
            'open': '#0d6efd',
            'in_progress': '#ffc107',
            'pending': '#0dcaf0',
            'finished': '#198754',
            'canceled': '#dc3545',
            'delayed': '#dc3545',
        }
        return colors.get(self.status, '#6c757d')

    def get_status_display(self):
        """Sobrescreve o método padrão para buscar o nome do status no TicketStatus."""
        try:
            ts = TicketStatus.objects.filter(code=self.status).first()
            if ts:
                return ts.name
        except Exception:
            pass
        return dict(self.STATUS_CHOICES).get(self.status, self.status)

    def _badge_style(self, bg_hex, text, font_hex=None, width=None, height=None):
        """Gera HTML de badge com cor HEX via inline style."""
        if not bg_hex or not bg_hex.startswith('#'):
            return f'<span class="badge bg-secondary">{text}</span>'
        # Se font_hex for informado e for HEX, usa-o; senão calcula contraste automático
        if font_hex and font_hex.startswith('#') and len(font_hex) >= 4:
            text_color = font_hex
        else:
            h = bg_hex.lstrip('#')
            if len(h) == 3:
                h = h[0]*2 + h[1]*2 + h[2]*2
            try:
                r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
                luminance = (0.299*r + 0.587*g + 0.114*b) / 255
                text_color = '#000000' if luminance > 0.5 else '#ffffff'
            except (ValueError, IndexError):
                text_color = '#ffffff'
        style = f'background-color:{bg_hex};color:{text_color};'
        if width:
            style += f'min-width:{width}px;'
        if height:
            fs = max(10, round(height * 0.46))
            style += f'font-size:{fs}px;padding-top:{max(2, round(height*0.12))}px;padding-bottom:{max(2, round(height*0.12))}px;'
        return f'<span class="badge" style="{style}">{text}</span>'

    @property
    def status_display_html(self):
        """Retorna HTML para exibir o status (imagem se houver, ou badge colorida)."""
        try:
            ts = TicketStatus.objects.filter(code=self.status, is_active=True).first()
            if not ts:
                return self._badge_style(self.status_color, self.get_status_display())
            if ts.image and ts.image.name:
                w = ts.image_width or 100
                h = ts.image_height or 26
                return f'<img src="{ts.image.url}" alt="{ts.name}" style="height:{h}px;width:{w}px;object-fit:contain;">'
            return self._badge_style(ts.color, ts.name, ts.font_color, ts.image_width, ts.image_height)
        except Exception:
            return f'<span class="badge bg-light text-dark border">{self.get_status_display()}</span>'

    @property
    def status_row_bg(self):
        """Retorna a cor de fundo em rgba para o card na lista, ou None."""
        try:
            ts = TicketStatus.objects.filter(code=self.status, is_active=True).first()
            if ts and ts.row_color:
                return ts.row_color
        except Exception:
            pass
        return None

    @property
    def status_row_bg_rgba(self):
        """
        Retorna o valor rgba() pronto para usar inline no HTML,
        ex: 'rgba(218, 246, 4, 0.22)' ou None.
        """
        hex_color = self.status_row_bg
        if not hex_color or not hex_color.startswith('#'):
            return None
        h = hex_color.lstrip('#')
        if len(h) == 3:
            h = h[0]*2 + h[1]*2 + h[2]*2
        if len(h) != 6:
            return None
        try:
            r = int(h[0:2], 16)
            g = int(h[2:4], 16)
            b = int(h[4:6], 16)
            return f'rgba({r},{g},{b},0.6)'
        except (ValueError, IndexError):
            return None

    def save(self, *args, **kwargs):
        """
        Sobrescreve o método save para verificar se a deadline passou
        e automaticamente muda o status para 'delayed' (Atrasado).
        """
        # Verifica se a OS tem deadline e se já passou
        if self.deadline and self.status not in ['finished', 'canceled']:
            from django.utils import timezone
            now = timezone.now()
            if self.deadline <= now:
                # Se o deadline passou e a OS não está finalizada/cancelada, marca como atrasada
                self.status = 'delayed'

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.formatted_id} - {self.client.name}"

    class Meta:
        verbose_name = "Ordem de Serviço"
        verbose_name_plural = "Ordens de Serviço"

class TicketImage(models.Model):
    ticket = models.ForeignKey(Ticket, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='tickets/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Imagem da OS"
        verbose_name_plural = "Imagens da OS"
        ordering = ['-uploaded_at']

class TicketFavorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorite_tickets')
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'ticket')
        verbose_name = "Favorito"
        verbose_name_plural = "Favoritos"

class TicketListOrder(models.Model):
    """
    Ordem manual dos cards de OS na listagem, definida pelo próprio usuário
    (arrastar e soltar) ou pelo Jota4 a pedido dele. Um registro por usuário.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='ticket_list_order')
    order = models.JSONField(default=list, verbose_name="IDs das OS na ordem escolhida")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ordem da Lista de OS"
        verbose_name_plural = "Ordens da Lista de OS"

    def __str__(self):
        return f"Ordem de {self.user.username} ({len(self.order)} OS)"

    @staticmethod
    def apply_saved_order(user, tickets):
        """
        Reordena uma lista de Tickets (já na ordem padrão) de acordo com a ordem
        salva do usuário. OS que nunca foram reposicionadas mantêm a posição
        relativa padrão entre si (sort estável), aparecendo depois das que o
        usuário já organizou manualmente.
        """
        if not user or not getattr(user, 'is_authenticated', False):
            return tickets

        saved = TicketListOrder.objects.filter(user=user).values_list('order', flat=True).first()
        if not saved:
            return tickets

        position = {ticket_id: i for i, ticket_id in enumerate(saved)}
        fallback = len(saved)
        tickets = list(tickets)
        tickets.sort(key=lambda t: position.get(t.id, fallback))
        return tickets

    @staticmethod
    def save_new_order(user, visible_ids_in_new_order):
        """
        Mescla a nova ordem de um subconjunto visível (ex.: lista filtrada) com a
        ordem completa já salva, preservando a posição relativa das OS que não
        fazem parte deste subconjunto.
        """
        visible_ids_in_new_order = [int(i) for i in visible_ids_in_new_order]
        visible_set = set(visible_ids_in_new_order)

        existing_obj = TicketListOrder.objects.filter(user=user).first()
        existing = list(existing_obj.order) if existing_obj else []

        anchor = None
        remaining = []
        for ticket_id in existing:
            if ticket_id in visible_set:
                if anchor is None:
                    anchor = len(remaining)
                continue
            remaining.append(ticket_id)
        if anchor is None:
            anchor = len(remaining)

        new_order = remaining[:anchor] + visible_ids_in_new_order + remaining[anchor:]

        TicketListOrder.objects.update_or_create(user=user, defaults={'order': new_order})
        return new_order

    @staticmethod
    def get_full_ordered_ticket_ids():
        """
        Ordem padrão (mesma regra da listagem: status_order, depois -updated_at),
        usada como base para operações de reposicionamento pelo Jota4.
        """
        from django.db.models import Subquery, OuterRef
        ticket_status_order = TicketStatus.objects.filter(
            code=OuterRef('status')
        ).values('order')[:1]
        return list(
            Ticket.objects.annotate(status_order=Subquery(ticket_status_order))
            .order_by('status_order', '-updated_at')
            .values_list('id', flat=True)
        )

    @staticmethod
    def move_ticket(user, ticket_id, position=None, before_ticket_id=None, after_ticket_id=None):
        """
        Reposiciona uma única OS na ordem salva do usuário (usado pelo Jota4).
        `position`: 'top', 'bottom', 'up' ou 'down'.
        Retorna a nova ordem completa (lista de IDs) e o novo índice (0-based) da OS movida.
        """
        ticket_id = int(ticket_id)

        existing_obj = TicketListOrder.objects.filter(user=user).first()
        if existing_obj and existing_obj.order:
            order = list(existing_obj.order)
        else:
            order = TicketListOrder.get_full_ordered_ticket_ids()

        if ticket_id in order:
            current_index = order.index(ticket_id)
            order.pop(current_index)
        else:
            # OS ainda não apareceu na ordem salva (ex.: criada depois do último drag);
            # trata como se estivesse no fim, para "up"/"down" fazerem sentido.
            current_index = len(order)

        if before_ticket_id is not None:
            before_ticket_id = int(before_ticket_id)
            target = order.index(before_ticket_id) if before_ticket_id in order else len(order)
        elif after_ticket_id is not None:
            after_ticket_id = int(after_ticket_id)
            target = order.index(after_ticket_id) + 1 if after_ticket_id in order else len(order)
        elif position == 'top':
            target = 0
        elif position == 'bottom':
            target = len(order)
        elif position == 'up':
            target = max(0, current_index - 1)
        elif position == 'down':
            target = min(len(order), current_index + 1)
        else:
            target = current_index

        order.insert(target, ticket_id)
        TicketListOrder.objects.update_or_create(user=user, defaults={'order': order})
        return order, target

class TechnicianTravel(models.Model):
    TRAVEL_STATUS_CHOICES = (
        ('confirmed', 'Confirmado'),
        ('planned', 'Planejado'),
        ('pending_contract', 'Pendente de Contrato'),
        ('completed', 'Concluído'),
    )
    
    BOOKING_STATUS_CHOICES = (
        ('concluded', 'Concluída'),
        ('issued', 'Emitida'),
        ('pending', 'Pendente'),
        ('na', 'Não se Aplica'),
    )

    client = models.ForeignKey(Client, on_delete=models.CASCADE, verbose_name="Cliente")
    hub = models.ForeignKey(ClientHub, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Hub/Loja")
    scheduled_date = models.DateTimeField(verbose_name="Agendado para")
    technician = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Técnico Responsável", related_name='travels')
    system = models.ForeignKey(System, on_delete=models.SET_NULL, null=True, verbose_name="Sistema")
    service_order = models.ForeignKey(Ticket, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Ordem de Serviço (OS)", related_name='travels')
    
    multi_client = models.BooleanField(default=False, verbose_name="Atenderá mais clientes na viagem?")
    additional_clients = models.ManyToManyField(Client, blank=True, related_name='shared_travels', verbose_name="Clientes Adicionais")
    status = models.CharField(max_length=20, choices=TRAVEL_STATUS_CHOICES, default='planned', verbose_name="Status da Viagem")
    
    ticket_status = models.CharField(max_length=20, choices=BOOKING_STATUS_CHOICES, default='pending', verbose_name="Status Passagem (Ticket)")
    hotel_status = models.CharField(max_length=20, choices=BOOKING_STATUS_CHOICES, default='pending', verbose_name="Status Hotel")
    
    # Flight Details
    flight_number = models.CharField(max_length=50, blank=True, null=True, verbose_name="Número do Voo")
    departure_time = models.DateTimeField(blank=True, null=True, verbose_name="Data/Hora Saída (Voo)")
    arrival_time = models.DateTimeField(blank=True, null=True, verbose_name="Data/Hora Chegada (Voo)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_travels')

    class Meta:
        verbose_name = "Viagem Técnica"
        verbose_name_plural = "Viagens Técnicas"
        ordering = ['-scheduled_date']

    def __str__(self):
        return f"Viagem - {self.technician.get_full_name()} - {self.scheduled_date.strftime('%d/%m/%Y')}"

class TravelSegment(models.Model):
    TRANSPORT_TYPE_CHOICES = (
        ('air', 'Passagem Aérea'),
        ('bus', 'Passagem de Ônibus'),
        ('car', 'Carro Alugado'),
    )
    
    travel = models.ForeignKey(TechnicianTravel, on_delete=models.CASCADE, related_name='segments', verbose_name="Viagem")
    transport_type = models.CharField(max_length=20, choices=TRANSPORT_TYPE_CHOICES, verbose_name="Tipo de Transporte")
    
    # Common Fields
    carrier = models.CharField(max_length=100, verbose_name="Companhia/Locadora", help_text="Ex: GOL, Azul, Localiza")
    transport_number = models.CharField(max_length=50, blank=True, null=True, verbose_name="Número (Voo/Linha/Placa)")
    vehicle_details = models.CharField(max_length=100, blank=True, null=True, verbose_name="Aeronave/Veículo", help_text="Ex: Boeing 737-800, Fiat Mobi")
    
    # Route
    origin = models.CharField(max_length=100, verbose_name="Origem", help_text="Ex: São Paulo (GRU)")
    destination = models.CharField(max_length=100, verbose_name="Destino", help_text="Ex: Recife (REC)")
    
    # Timing
    departure_time = models.DateTimeField(verbose_name="Saída")
    arrival_time = models.DateTimeField(verbose_name="Chegada")
    
    # Booking Info
    booking_code = models.CharField(max_length=50, blank=True, null=True, verbose_name="Número do Bilhete / Contrato", help_text="Ex: 9572261127853 (Aéreo) ou Contrato de Locação")
    locator = models.CharField(max_length=50, blank=True, null=True, verbose_name="Localizador (PNR)", help_text="Ex: UJMQZS")
    status = models.CharField(max_length=50, default='Confirmado', verbose_name="Status")
    
    # Passenger Info (Defaults to Technician if empty)
    passenger_name = models.CharField(max_length=150, blank=True, null=True, verbose_name="Passageiro")
    passenger_document = models.CharField(max_length=50, blank=True, null=True, verbose_name="Documento")
    loyalty_program = models.CharField(max_length=100, blank=True, null=True, verbose_name="Programa de Fidelidade")
    
    # Ticket Details
    fare_type = models.CharField(max_length=100, blank=True, null=True, verbose_name="Tarifa", help_text="Ex: Plus (Inclui bagagem)")
    seat = models.CharField(max_length=20, blank=True, null=True, verbose_name="Assento")
    
    # File
    attachment = models.FileField(upload_to='travel_tickets/', null=True, blank=True, verbose_name="Anexo (PDF/Imagem)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Segmento de Viagem"
        verbose_name_plural = "Segmentos de Viagem"
        ordering = ['departure_time']

    def __str__(self):
        return f"{self.get_transport_type_display()} - {self.origin} -> {self.destination}"
    
    @property
    def duration(self):
        if self.departure_time and self.arrival_time:
            diff = self.arrival_time - self.departure_time
            hours = diff.seconds // 3600
            minutes = (diff.seconds % 3600) // 60
            return f"{hours:02d}h {minutes:02d}min"
        return "-"

class TicketUpdate(models.Model):
    ticket = models.ForeignKey(Ticket, related_name='updates', on_delete=models.CASCADE)
    description = models.TextField(verbose_name="Descrição da Evolução")
    image = models.ImageField(upload_to='ticket_updates/', null=True, blank=True, verbose_name="Imagem")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = "Evolução do Chamado"
        verbose_name_plural = "Evoluções do Chamado"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Garante que a OS suba para o topo do seu grupo de status na lista,
        # já que a listagem ordena por status e por 'updated_at' — sem isso,
        # evoluções feitas pelo botão rápido da lista ou pelo Chat IA (que não
        # salvam os campos da OS) deixavam a data de atualização desatualizada.
        Ticket.objects.filter(pk=self.ticket_id).update(updated_at=timezone.now())

class TicketUpdateImage(models.Model):
    update = models.ForeignKey(TicketUpdate, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='ticket_updates/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Imagem da Evolução"
        verbose_name_plural = "Imagens da Evolução"

class Notification(models.Model):
    TYPE_CHOICES = (
        ('message', 'Mensagem Direta'),
        ('alert', 'Alerta de Sistema'),
        ('assignment', 'Atribuição de Tarefa'),
    )

    URGENCY_CHOICES = (
        ('high', 'Alto'),
        ('medium', 'Médio'),
        ('low', 'Baixo'),
    )

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', verbose_name="Destinatário")
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_notifications', verbose_name="Remetente")

    title = models.CharField(max_length=200, verbose_name="Título")
    message = models.TextField(verbose_name="Mensagem")

    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='alert')
    urgency = models.CharField(max_length=10, choices=URGENCY_CHOICES, default='medium', verbose_name="Urgência")
    read_receipt_requested = models.BooleanField(default=False, verbose_name="Solicitar confirmação de leitura")
    read_receipt_notified = models.BooleanField(default=False, verbose_name="Confirmação de leitura já enviada")

    related_ticket = models.ForeignKey('Ticket', on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')

    is_read = models.BooleanField(default=False, verbose_name="Lida")
    read_at = models.DateTimeField(null=True, blank=True, verbose_name="Lida em")
    created_at = models.DateTimeField(auto_now_add=True)

    deleted_by_sender = models.BooleanField(default=False)
    deleted_by_recipient = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Notificação"
        verbose_name_plural = "Notificações"

    def __str__(self):
        return f"{self.title} - {self.recipient.username}"

class ChecklistTemplate(models.Model):
    name = models.CharField(max_length=200, verbose_name="Nome do Checklist")
    department = models.CharField(max_length=100, verbose_name="Departamento/Área", help_text="Ex: CSO, TI, Manutenção")
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Empresa/Cliente", help_text="Se selecionado, este modelo aparece como opção somente para este cliente.")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.department}"
    
    class Meta:
        verbose_name = "Modelo de Checklist"
        verbose_name_plural = "Modelos de Checklist"

class ChecklistTemplateItem(models.Model):
    FIELD_TYPE_CHOICES = (
        ('group', 'Grupo'),
        ('checkbox', 'Checkbox'),
        ('switch', 'Switch'),
        ('button', 'Botão'),
        ('select', 'Select'),
        ('text', 'Texto'),
    )

    template = models.ForeignKey(ChecklistTemplate, on_delete=models.CASCADE, related_name='items')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', verbose_name="Item Pai")
    title = models.CharField(max_length=200, verbose_name="Título da Atividade", default="Atividade")
    description = models.CharField(max_length=500, verbose_name="Descrição da Atividade")
    order = models.PositiveIntegerField(default=0, verbose_name="Ordem")
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES, default='switch', verbose_name="Tipo do Campo")
    is_required = models.BooleanField(default=True, verbose_name="Obrigatório")
    select_options = models.TextField(blank=True, null=True, verbose_name="Opções do Select", help_text="Uma opção por linha (somente para tipo Select).")
    
    # New field to link to a client
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Cliente Vinculado", help_text="Se selecionado, esta tarefa será vinculada a este cliente específico.")

    def __str__(self):
        return self.description
    
    class Meta:
        ordering = ['parent_id', 'order', 'id']
        verbose_name = "Item do Modelo"
        verbose_name_plural = "Itens do Modelo"


class ChecklistTemplateItemOption(models.Model):
    FIELD_TYPE_CHOICES = (
        ('text', 'Texto (input)'),
        ('textarea', 'Texto (área)'),
        ('number', 'Número'),
        ('date', 'Data'),
        ('select', 'Select'),
        ('radio', 'Radio'),
        ('checkbox', 'Checkbox'),
        ('switch', 'Switch'),
        ('button', 'Botão'),
    )

    item = models.ForeignKey(ChecklistTemplateItem, on_delete=models.CASCADE, related_name='options', verbose_name="Atividade")
    label = models.CharField(max_length=200, verbose_name="Rótulo")
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES, default='text', verbose_name="Tipo")
    is_required = models.BooleanField(default=False, verbose_name="Obrigatório")
    order = models.PositiveIntegerField(default=0, verbose_name="Ordem")
    options_text = models.TextField(blank=True, null=True, verbose_name="Opções", help_text="Uma opção por linha (Select/Radio).")

    def __str__(self):
        return f"{self.item_id} - {self.label}"

    @property
    def options_list(self):
        raw = self.options_text or ''
        return [line.strip() for line in raw.splitlines() if line.strip()]

    class Meta:
        ordering = ['order', 'id']
        verbose_name = "Opção do Item"
        verbose_name_plural = "Opções dos Itens"

class DailyChecklist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Usuário")
    date = models.DateField(verbose_name="Data", default=timezone.now)
    template = models.ForeignKey(ChecklistTemplate, on_delete=models.SET_NULL, null=True, verbose_name="Modelo Utilizado")
    pdf_generated_at = models.DateTimeField(null=True, blank=True, verbose_name="PDF Gerado em")
    status = models.CharField(max_length=20, default='pending', choices=[('pending', 'Pendente'), ('completed', 'Concluído')], verbose_name="Status")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def activities_status(self):
        """Returns a summary of activities status."""
        total = self.items.count()
        completed = self.items.filter(is_checked=True).count()
        return f"{completed}/{total} Concluídos"

    @property
    def pdf_generated(self):
        return self.pdf_generated_at is not None

    @property
    def is_complete(self):
        return self.status == 'completed'

    def __str__(self):
        return f"Checklist {self.user.username} - {self.date}"

    class Meta:
        unique_together = ('user', 'date')
        verbose_name = "Checklist Diário"
        verbose_name_plural = "Checklists Diários"

class DailyChecklistItem(models.Model):
    FIELD_TYPE_CHOICES = ChecklistTemplateItem.FIELD_TYPE_CHOICES

    daily_checklist = models.ForeignKey(DailyChecklist, on_delete=models.CASCADE, related_name='items')
    # Link back to the template item to access configuration like client
    template_item = models.ForeignKey(ChecklistTemplateItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='daily_items')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', verbose_name="Item Pai")
    
    title = models.CharField(max_length=200, verbose_name="Título da Atividade", default="Atividade")
    description = models.CharField(max_length=500, verbose_name="Descrição da Atividade")
    order = models.PositiveIntegerField(default=0, verbose_name="Ordem")
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES, default='switch', verbose_name="Tipo do Campo")
    is_required = models.BooleanField(default=True, verbose_name="Obrigatório")
    select_options = models.TextField(blank=True, null=True, verbose_name="Opções do Select")
    value_text = models.TextField(blank=True, null=True, verbose_name="Valor")
    is_checked = models.BooleanField(default=False, verbose_name="Realizado")
    image = models.ImageField(upload_to='checklist_photos/', null=True, blank=True, verbose_name="Foto Comprobatória")
    observation = models.TextField(blank=True, null=True, verbose_name="Observação")
    
    def __str__(self):
        return self.description

    @property
    def report_image(self):
        """Returns the image selected for the report, or the first one if none selected."""
        # Check for explicitly selected report image
        report_img = self.images.filter(is_report_image=True).first()
        if report_img:
            return report_img
        
        # Fallback to first image
        return self.images.first()

    class Meta:
        ordering = ['parent_id', 'order', 'id']
        verbose_name = "Item do Checklist Diário"
        verbose_name_plural = "Itens do Checklist Diário"


class DailyChecklistItemOptionValue(models.Model):
    daily_item = models.ForeignKey(DailyChecklistItem, on_delete=models.CASCADE, related_name='option_values', verbose_name="Item do Checklist")
    template_option = models.ForeignKey(ChecklistTemplateItemOption, on_delete=models.SET_NULL, null=True, blank=True, related_name='daily_values', verbose_name="Opção do Modelo")
    value_text = models.TextField(blank=True, null=True, verbose_name="Valor (texto)")
    value_bool = models.BooleanField(null=True, blank=True, verbose_name="Valor (booleano)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('daily_item', 'template_option')
        verbose_name = "Valor de Opção"
        verbose_name_plural = "Valores de Opções"

class DailyChecklistItemImage(models.Model):
    item = models.ForeignKey(DailyChecklistItem, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='checklist_photos/', verbose_name="Foto")
    is_report_image = models.BooleanField(default=False, verbose_name="Foto do Relatório")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.is_report_image:
            # Ensure only one image per item is selected for the report
            DailyChecklistItemImage.objects.filter(item=self.item, is_report_image=True).exclude(pk=self.pk).update(is_report_image=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Imagem do item {self.item.id}"

class ActiveSession(models.Model):
    # Sessões sem nenhuma atividade dentro desta janela são consideradas abandonadas
    # (cookie expirou, navegador fechado, queda de rede etc. — sem logout explícito)
    # e são descartadas automaticamente sempre que "quem está online" é consultado.
    ONLINE_WINDOW_MINUTES = 5
    # Entre este limite e o ONLINE_WINDOW_MINUTES, o usuário aparece como "ausente"
    # (sessão ainda ativa, mas sem atividade recente) em vez de "online".
    AWAY_AFTER_MINUTES = 2

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='active_sessions', verbose_name="Usuário")
    session_key = models.CharField(max_length=40, unique=True, verbose_name="Chave da Sessão")
    ip_address = models.CharField(max_length=45, verbose_name="Endereço IP")
    user_agent = models.TextField(blank=True, null=True, verbose_name="User Agent")
    last_activity = models.DateTimeField(auto_now=True, verbose_name="Última Atividade")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        verbose_name = "Sessão Ativa"
        verbose_name_plural = "Sessões Ativas"
        ordering = ['-last_activity']

    def __str__(self):
        return f"{self.user.username} - {self.ip_address}"

    @classmethod
    def cleanup_stale(cls):
        threshold = timezone.now() - timedelta(minutes=cls.ONLINE_WINDOW_MINUTES)
        cls.objects.filter(last_activity__lt=threshold).delete()

    @classmethod
    def online_user_ids(cls):
        cls.cleanup_stale()
        return cls.objects.values_list('user_id', flat=True).distinct()

    @classmethod
    def is_user_online(cls, user):
        cls.cleanup_stale()
        return cls.objects.filter(user=user).exists()

    @classmethod
    def get_status(cls, user):
        """'online' (atividade recente), 'away' (sessão viva mas parada há um
        tempo) ou 'offline' (sem sessão ativa) — usado para a bolinha de status
        no chat particular."""
        cls.cleanup_stale()
        session = cls.objects.filter(user=user).order_by('-last_activity').first()
        if not session:
            return 'offline'
        if timezone.now() - session.last_activity <= timedelta(minutes=cls.AWAY_AFTER_MINUTES):
            return 'online'
        return 'away'

class DailyChecklistItemDetail(models.Model):
    item = models.ForeignKey(DailyChecklistItem, on_delete=models.CASCADE, related_name='details')
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Cliente")
    hub = models.ForeignKey(ClientHub, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Hub/Loja")
    ticket = models.ForeignKey(Ticket, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="OS Relacionada")
    description = models.TextField(verbose_name="Descrição do Detalhe")
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Detalhe para {self.item} - {self.client}"

    class Meta:
        verbose_name = "Detalhe do Item"
        verbose_name_plural = "Detalhes dos Itens"
