from django.db import models
from django.contrib.auth.models import User
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

    def __str__(self):
        return f"{self.user.username} - {self.role}"

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
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"

class ClientHub(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='hubs', verbose_name="Cliente")
    name = models.CharField(max_length=200, verbose_name="Nome do Hub/Loja")
    address = models.TextField(verbose_name="Endereço", blank=True, null=True)
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

    def __str__(self):
        return "Configurações do Sistema"

    class Meta:
        verbose_name = "Configuração do Sistema"
        verbose_name_plural = "Configurações do Sistema"

class Ticket(models.Model):
    STATUS_CHOICES = (
        ('open', 'Em Aberto'),
        ('in_progress', 'Em Andamento'),
        ('pending', 'Aguardando Aprovação'),
        ('finished', 'Finalizado'),
        ('canceled', 'Cancelado'),
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
    
    systems = models.ManyToManyField(System, verbose_name="Sistemas", blank=True, related_name="tickets")
    area_group = models.CharField(max_length=100, verbose_name="Grupo de Áreas", blank=True, null=True)
    area_subgroup = models.CharField(max_length=100, verbose_name="Subgrupo de Áreas", blank=True, null=True)
    area = models.CharField(max_length=100, verbose_name="Área", blank=True, null=True)
    
    call_type = models.CharField(max_length=50, choices=CALL_TYPE_CHOICES, verbose_name="Tipo de Chamado", blank=True, null=True)

    # Legacy field, but keeping it as it was there. Maybe user wants to use call_type instead.
    order_type = models.ForeignKey(OrderType, on_delete=models.PROTECT, verbose_name="Tipo de Ordem", null=True, blank=True)
    equipments = models.ManyToManyField(Equipment, verbose_name="Equipamentos", blank=True, related_name='tickets')
    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, verbose_name="Equipamento (Legacy)", null=True, blank=True)
    problem_type = models.ForeignKey(ProblemType, on_delete=models.PROTECT, verbose_name="Tipo de Problema", null=True)
    
    description = models.TextField(verbose_name="Descrição Detalhada", blank=True)
    final_description = models.TextField(verbose_name="Descrição Final (Resolução)", blank=True, null=True)
    image = models.ImageField(upload_to='tickets/', null=True, blank=True, verbose_name="Imagem do Evento")
    
    start_date = models.DateTimeField(null=True, blank=True, verbose_name="Data de Início")
    deadline = models.DateTimeField(null=True, blank=True, verbose_name="Data Limite para Execução")
    estimated_time = models.DurationField(null=True, blank=True, verbose_name="Tempo Estimado")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open', verbose_name="Status")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")
    
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="Data de Finalização")

    @property
    def formatted_id(self):
        return f"JMP{self.id:05d}"

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

class TicketFavorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorite_tickets')
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'ticket')
        verbose_name = "Favorito"
        verbose_name_plural = "Favoritos"

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
