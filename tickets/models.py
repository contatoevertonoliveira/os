from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import time
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
        pieces = [self.name]
        if self.email:
            pieces.append(self.email)
        if self.phone:
            pieces.append(self.phone)
        return " - ".join(pieces)

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

    def __str__(self):
        return "Configurações do Sistema"

    class Meta:
        verbose_name = "Configuração do Sistema"
        verbose_name_plural = "Configurações do Sistema"


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
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Criado por")
    text = models.TextField(verbose_name="Texto")
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
    color = models.CharField(max_length=20, verbose_name="Cor (Bootstrap)", default="secondary",
                             help_text="Ex: primary, warning, success, danger, info")
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
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open', verbose_name="Status")

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
        colors = {
            'open': 'primary',
            'in_progress': 'warning',
            'pending': 'info',
            'finished': 'success',
            'canceled': 'danger'
        }
        return colors.get(self.status, 'secondary')

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

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', verbose_name="Destinatário")
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_notifications', verbose_name="Remetente")
    
    title = models.CharField(max_length=200, verbose_name="Título")
    message = models.TextField(verbose_name="Mensagem")
    
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='alert')
    
    related_ticket = models.ForeignKey('Ticket', on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    
    is_read = models.BooleanField(default=False, verbose_name="Lida")
    read_at = models.DateTimeField(null=True, blank=True, verbose_name="Lida em")
    created_at = models.DateTimeField(auto_now_add=True)

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
