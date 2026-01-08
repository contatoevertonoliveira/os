from django.db import models
from django.contrib.auth.models import User
import uuid

class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('super_admin', 'Super Admin'),
        ('admin', 'Administrador'),
        ('standard', 'Padrão'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    token = models.CharField(max_length=100, unique=True, default=uuid.uuid4)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='standard')
    
    job_title = models.CharField(max_length=100, verbose_name="Cargo", blank=True, null=True)
    station = models.CharField(max_length=100, verbose_name="Posto de Alocação", blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.role}"

class Client(models.Model):
    name = models.CharField(max_length=200, verbose_name="Nome do Cliente")
    email = models.EmailField(verbose_name="Email", blank=True, null=True)
    phone = models.CharField(max_length=20, verbose_name="Telefone", blank=True, null=True)
    address = models.TextField(verbose_name="Endereço", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"

class Equipment(models.Model):
    name = models.CharField(max_length=200, verbose_name="Nome do Equipamento")
    description = models.TextField(verbose_name="Descrição", blank=True, null=True)
    
    def __str__(self):
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

class Ticket(models.Model):
    STATUS_CHOICES = (
        ('open', 'Em Aberto'),
        ('in_progress', 'Em Andamento'),
        ('pending', 'Aguardando Aprovação'),
        ('finished', 'Finalizado'),
        ('canceled', 'Cancelado'),
    )
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE, verbose_name="Cliente")
    technician = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Técnico Responsável")
    
    # Changed from CharField/Choices to ForeignKey
    order_type = models.ForeignKey(OrderType, on_delete=models.PROTECT, verbose_name="Tipo de Ordem", null=True)
    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, verbose_name="Equipamento", null=True)
    problem_type = models.ForeignKey(ProblemType, on_delete=models.PROTECT, verbose_name="Tipo de Problema", null=True)
    
    description = models.TextField(verbose_name="Descrição Detalhada", blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open', verbose_name="Status")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")
    
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="Data de Finalização")

    def __str__(self):
        return f"OS #{self.id} - {self.client.name}"
    
    class Meta:
        verbose_name = "Ordem de Serviço"
        verbose_name_plural = "Ordens de Serviço"
