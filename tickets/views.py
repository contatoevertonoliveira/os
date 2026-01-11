from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.db.models import Q
from .models import *
from .forms import *
from .api import TicketAPIView  # Re-export for URL compatibility

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Counts
        context['total_tickets'] = Ticket.objects.count()
        context['tickets_open'] = Ticket.objects.filter(status='open').count()
        context['tickets_pending'] = Ticket.objects.filter(status='pending').count()
        context['tickets_finished'] = Ticket.objects.filter(status='finished').count()
        
        # Charts Data - Status
        status_counts = []
        status_labels = []
        for status_code, status_label in Ticket.STATUS_CHOICES:
            count = Ticket.objects.filter(status=status_code).count()
            status_counts.append(count)
            status_labels.append(status_label)
        
        context['chart_status_labels'] = status_labels
        context['chart_status_data'] = status_counts
        
        # Charts Data - Techs
        techs = User.objects.filter(profile__role='technician')
        tech_labels = []
        tech_data = []
        for tech in techs:
            count = Ticket.objects.filter(technician=tech).count()
            if count > 0:
                tech_labels.append(tech.username)
                tech_data.append(count)
                
        context['chart_tech_labels'] = tech_labels
        context['chart_tech_data'] = tech_data
        
        context['my_tickets'] = Ticket.objects.filter(technician=self.request.user).count()
        return context

class TokenLoginView(LoginView):
    template_name = 'login.html'
    authentication_form = TokenLoginForm
    redirect_authenticated_user = True
    
    def form_valid(self, form):
        # Garante que o usuário está ativo
        user = form.get_user()
        if not user.is_active:
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('dashboard')

# Ticket Views
class TicketListView(LoginRequiredMixin, ListView):
    model = Ticket
    template_name = 'tickets/ticket_list.html'
    context_object_name = 'tickets'
    ordering = ['-created_at']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Passa URLs de retorno para templates que possam ser reutilizados
        return context

class TicketDetailView(LoginRequiredMixin, DetailView):
    model = Ticket
    template_name = 'tickets/ticket_detail.html'
    context_object_name = 'ticket'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = reverse_lazy('ticket_list')
        return context

class TicketCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Ticket
    form_class = TicketForm
    template_name = 'tickets/ticket_form.html'
    success_url = reverse_lazy('ticket_list')
    success_message = "Ordem de Serviço criada com sucesso!"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Nova Ordem de Serviço"
        context['back_url'] = reverse_lazy('ticket_list')
        return context

class TicketUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Ticket
    form_class = TicketUpdateForm
    template_name = 'tickets/ticket_form.html'
    success_url = reverse_lazy('ticket_list')
    success_message = "Ordem de Serviço atualizada com sucesso!"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Editar OS #{self.object.formatted_id}"
        context['back_url'] = reverse_lazy('ticket_list')
        context['updates'] = self.object.updates.all()
        return context

class TicketDeleteView(LoginRequiredMixin, DeleteView):
    model = Ticket
    template_name = 'ticket_confirm_delete.html'
    success_url = reverse_lazy('ticket_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = reverse_lazy('ticket_list')
        return context

    def form_valid(self, form):
        messages.success(self.request, "Ordem de Serviço excluída com sucesso!")
        return super().form_valid(form)

class TicketModalView(LoginRequiredMixin, DetailView):
    model = Ticket
    template_name = 'tickets/ticket_modal_body.html'

# Client Views
class ClientListView(LoginRequiredMixin, ListView):
    model = Client
    template_name = 'cadastros/client_list.html'
    context_object_name = 'clients'

class ClientCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Client
    form_class = ClientForm
    template_name = 'cadastros/client_form.html'
    success_url = reverse_lazy('client_list')
    success_message = "Cliente cadastrado com sucesso!"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Novo Cliente"
        context['back_url'] = reverse_lazy('client_list')
        return context

class ClientUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Client
    form_class = ClientForm
    template_name = 'cadastros/client_form.html'
    success_url = reverse_lazy('client_list')
    success_message = "Cliente atualizado com sucesso!"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Editar Cliente: {self.object.name}"
        context['back_url'] = reverse_lazy('client_list')
        return context

class ClientDeleteView(LoginRequiredMixin, DeleteView):
    model = Client
    template_name = 'cadastros/generic_confirm_delete.html'
    success_url = reverse_lazy('client_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = reverse_lazy('client_list')
        return context

# Equipment Views
class EquipmentListView(LoginRequiredMixin, ListView):
    model = Equipment
    template_name = 'cadastros/equipment_list.html'
    context_object_name = 'equipments'

class EquipmentCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Equipment
    fields = '__all__'
    template_name = 'cadastros/equipment_form.html'
    success_url = reverse_lazy('equipment_list')
    success_message = "Equipamento cadastrado com sucesso!"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Novo Equipamento"
        context['back_url'] = reverse_lazy('equipment_list')
        return context

class EquipmentUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Equipment
    fields = '__all__'
    template_name = 'cadastros/equipment_form.html'
    success_url = reverse_lazy('equipment_list')
    success_message = "Equipamento atualizado com sucesso!"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Editar Equipamento: {self.object.name}"
        context['back_url'] = reverse_lazy('equipment_list')
        return context

class EquipmentDeleteView(LoginRequiredMixin, DeleteView):
    model = Equipment
    template_name = 'cadastros/generic_confirm_delete.html'
    success_url = reverse_lazy('equipment_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = reverse_lazy('equipment_list')
        return context

# OrderType Views
class OrderTypeListView(LoginRequiredMixin, ListView):
    model = OrderType
    template_name = 'cadastros/ordertype_list.html'
    context_object_name = 'ordertypes'

class OrderTypeCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = OrderType
    fields = '__all__'
    template_name = 'cadastros/simple_form.html'
    success_url = reverse_lazy('ordertype_list')
    success_message = "Tipo de Ordem cadastrado com sucesso!"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Novo Tipo de Ordem"
        context['back_url'] = reverse_lazy('ordertype_list')
        return context

class OrderTypeUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = OrderType
    fields = '__all__'
    template_name = 'cadastros/simple_form.html'
    success_url = reverse_lazy('ordertype_list')
    success_message = "Tipo de Ordem atualizado com sucesso!"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Editar Tipo de Ordem: {self.object.name}"
        context['back_url'] = reverse_lazy('ordertype_list')
        return context

class OrderTypeDeleteView(LoginRequiredMixin, DeleteView):
    model = OrderType
    template_name = 'cadastros/generic_confirm_delete.html'
    success_url = reverse_lazy('ordertype_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = reverse_lazy('ordertype_list')
        return context

# ProblemType Views
class ProblemTypeListView(LoginRequiredMixin, ListView):
    model = ProblemType
    template_name = 'cadastros/problemtype_list.html'
    context_object_name = 'problemtypes'

class ProblemTypeCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = ProblemType
    fields = '__all__'
    template_name = 'cadastros/simple_form.html'
    success_url = reverse_lazy('problemtype_list')
    success_message = "Tipo de Problema cadastrado com sucesso!"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Novo Tipo de Problema"
        context['back_url'] = reverse_lazy('problemtype_list')
        return context

class ProblemTypeUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = ProblemType
    fields = '__all__'
    template_name = 'cadastros/simple_form.html'
    success_url = reverse_lazy('problemtype_list')
    success_message = "Tipo de Problema atualizado com sucesso!"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Editar Tipo de Problema: {self.object.name}"
        context['back_url'] = reverse_lazy('problemtype_list')
        return context

class ProblemTypeDeleteView(LoginRequiredMixin, DeleteView):
    model = ProblemType
    template_name = 'cadastros/generic_confirm_delete.html'
    success_url = reverse_lazy('problemtype_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = reverse_lazy('problemtype_list')
        return context

# Technician Views
class TechnicianListView(LoginRequiredMixin, ListView):
    model = User
    template_name = 'cadastros/technician_list.html'
    context_object_name = 'technicians'
    
    def get_queryset(self):
        return User.objects.filter(profile__role__in=['technician', 'standard'])

class TechnicianCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = User
    form_class = TechnicianForm
    template_name = 'cadastros/technician_form.html'
    success_url = reverse_lazy('technician_list')
    success_message = "Técnico cadastrado com sucesso!"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Novo Técnico"
        context['back_url'] = reverse_lazy('technician_list')
        return context

class TechnicianUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = User
    form_class = TechnicianForm
    template_name = 'cadastros/technician_form.html'
    success_url = reverse_lazy('technician_list')
    success_message = "Técnico atualizado com sucesso!"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Editar Técnico: {self.object.first_name}"
        context['back_url'] = reverse_lazy('technician_list')
        return context

class TechnicianDeleteView(LoginRequiredMixin, DeleteView):
    model = User
    template_name = 'cadastros/generic_confirm_delete.html'
    success_url = reverse_lazy('technician_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = reverse_lazy('technician_list')
        return context

    def form_valid(self, form):
        messages.success(self.request, "Técnico excluído com sucesso!")
        return super().form_valid(form)

# System Views
class SystemListView(LoginRequiredMixin, ListView):
    model = System
    template_name = 'cadastros/system_list.html'
    context_object_name = 'systems'

class SystemCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = System
    fields = '__all__'
    template_name = 'cadastros/system_form.html'
    success_url = reverse_lazy('system_list')
    success_message = "Sistema cadastrado com sucesso!"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Novo Sistema"
        context['back_url'] = reverse_lazy('system_list')
        return context

class SystemUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = System
    fields = '__all__'
    template_name = 'cadastros/system_form.html'
    success_url = reverse_lazy('system_list')
    success_message = "Sistema atualizado com sucesso!"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Editar Sistema: {self.object.name}"
        context['back_url'] = reverse_lazy('system_list')
        return context

class SystemDeleteView(LoginRequiredMixin, DeleteView):
    model = System
    template_name = 'cadastros/generic_confirm_delete.html'
    success_url = reverse_lazy('system_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = reverse_lazy('system_list')
        return context

# Profile & Settings
class ProfileView(LoginRequiredMixin, DetailView):
    model = UserProfile
    template_name = 'profile.html'
    
    def get_object(self):
        if hasattr(self.request.user, 'profile'):
            return self.request.user.profile
        return None

class SettingsView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    template_name = 'settings.html'
    form_class = SystemSettingsForm
    success_url = reverse_lazy('settings')
    success_message = "Configurações atualizadas com sucesso!"
    
    def get_object(self, queryset=None):
        obj, created = SystemSettings.objects.get_or_create(pk=1)
        return obj

# Tasks
class TaskListView(LoginRequiredMixin, ListView):
    model = Ticket
    template_name = 'tasks/task_list.html'
    context_object_name = 'tickets'  # Corrigido para corresponder ao template que usa 'tickets'
    ordering = ['client__name']  # Ordenação necessária para o regroup no template

class TaskFavoriteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        return JsonResponse({'status': 'ok'})
