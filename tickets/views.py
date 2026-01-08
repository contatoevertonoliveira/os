from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.db.models import Count
from django.contrib.auth import login
from django.contrib import messages
from .models import Ticket, Client, UserProfile, Equipment, OrderType, ProblemType
from django.contrib.auth.models import User
from .forms import TechnicianForm, TicketForm, TicketUpdateForm

from django.contrib.messages.views import SuccessMessageMixin

# Mixin para verificar permissão de admin/super_admin
class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and \
               hasattr(self.request.user, 'profile') and \
               self.request.user.profile.role in ['admin', 'super_admin']

class TokenLoginView(View):
    template_name = 'login.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard')
        return render(request, self.template_name)

    def post(self, request):
        token = request.POST.get('token')
        try:
            profile = UserProfile.objects.get(token=token)
            login(request, profile.user)
            return redirect('dashboard')
        except UserProfile.DoesNotExist:
            messages.error(request, 'Token inválido. Acesso negado.')
            return render(request, self.template_name)

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # General Stats
        context['total_tickets'] = Ticket.objects.count()
        context['tickets_open'] = Ticket.objects.filter(status='open').count()
        context['tickets_pending'] = Ticket.objects.filter(status='pending').count()
        context['tickets_finished'] = Ticket.objects.filter(status='finished').count()
        context['tickets_in_progress'] = Ticket.objects.filter(status='in_progress').count()
        
        # Chart Data: Status Distribution
        status_data = Ticket.objects.values('status').annotate(count=Count('status'))
        context['chart_status_labels'] = [item['status'] for item in status_data]
        context['chart_status_data'] = [item['count'] for item in status_data]
        
        # Chart Data: By Technician
        tech_data = Ticket.objects.values('technician__username').annotate(count=Count('id'))
        context['chart_tech_labels'] = [item['technician__username'] if item['technician__username'] else 'Sem Técnico' for item in tech_data]
        context['chart_tech_data'] = [item['count'] for item in tech_data]

        return context

class TicketListView(LoginRequiredMixin, ListView):
    model = Ticket
    template_name = 'ticket_list.html'
    context_object_name = 'tickets'
    ordering = ['-created_at']

class TicketCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Ticket
    template_name = 'ticket_form.html'
    form_class = TicketForm
    success_url = reverse_lazy('ticket_list')
    success_message = "Ordem de Serviço criada com sucesso!"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Nova Ordem de Serviço'
        return context

class TicketUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Ticket
    template_name = 'ticket_form.html'
    form_class = TicketUpdateForm
    success_url = reverse_lazy('ticket_list')
    success_message = "Ordem de Serviço atualizada com sucesso!"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Editar OS #{self.object.id}'
        return context

# View para deletar tickets (Apenas Admin/SuperAdmin)
class TicketDeleteView(AdminRequiredMixin, DeleteView):
    model = Ticket
    template_name = 'ticket_confirm_delete.html'
    success_url = reverse_lazy('ticket_list')

# --- CLIENTS CRUD ---
class ClientListView(LoginRequiredMixin, ListView):
    model = Client
    template_name = 'cadastros/client_list.html'
    context_object_name = 'clients'

class ClientCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Client
    template_name = 'cadastros/generic_form.html'
    fields = ['name', 'email', 'phone', 'address']
    success_url = reverse_lazy('client_list')
    success_message = "Cliente cadastrado com sucesso!"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Novo Cliente'
        context['back_url'] = reverse_lazy('client_list')
        return context

class ClientUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Client
    template_name = 'cadastros/generic_form.html'
    fields = ['name', 'email', 'phone', 'address']
    success_url = reverse_lazy('client_list')
    success_message = "Cliente atualizado com sucesso!"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Editar Cliente'
        context['back_url'] = reverse_lazy('client_list')
        return context

class ClientDeleteView(AdminRequiredMixin, DeleteView):
    model = Client
    template_name = 'cadastros/generic_confirm_delete.html'
    success_url = reverse_lazy('client_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = reverse_lazy('client_list')
        return context

# --- EQUIPMENTS CRUD ---
class EquipmentListView(LoginRequiredMixin, ListView):
    model = Equipment
    template_name = 'cadastros/equipment_list.html'
    context_object_name = 'equipments'

class EquipmentCreateView(LoginRequiredMixin, CreateView):
    model = Equipment
    template_name = 'cadastros/generic_form.html'
    fields = ['name', 'description']
    success_url = reverse_lazy('equipment_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Novo Equipamento'
        context['back_url'] = reverse_lazy('equipment_list')
        return context

class EquipmentUpdateView(LoginRequiredMixin, UpdateView):
    model = Equipment
    template_name = 'cadastros/generic_form.html'
    fields = ['name', 'description']
    success_url = reverse_lazy('equipment_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Editar Equipamento'
        context['back_url'] = reverse_lazy('equipment_list')
        return context

class EquipmentDeleteView(AdminRequiredMixin, DeleteView):
    model = Equipment
    template_name = 'cadastros/generic_confirm_delete.html'
    success_url = reverse_lazy('equipment_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = reverse_lazy('equipment_list')
        return context

# --- ORDER TYPE CRUD ---
class OrderTypeListView(LoginRequiredMixin, ListView):
    model = OrderType
    template_name = 'cadastros/ordertype_list.html'
    context_object_name = 'ordertypes'

class OrderTypeCreateView(LoginRequiredMixin, CreateView):
    model = OrderType
    template_name = 'cadastros/generic_form.html'
    fields = ['name']
    success_url = reverse_lazy('ordertype_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Novo Tipo de Ordem'
        context['back_url'] = reverse_lazy('ordertype_list')
        return context

class OrderTypeUpdateView(LoginRequiredMixin, UpdateView):
    model = OrderType
    template_name = 'cadastros/generic_form.html'
    fields = ['name']
    success_url = reverse_lazy('ordertype_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Editar Tipo de Ordem'
        context['back_url'] = reverse_lazy('ordertype_list')
        return context

class OrderTypeDeleteView(AdminRequiredMixin, DeleteView):
    model = OrderType
    template_name = 'cadastros/generic_confirm_delete.html'
    success_url = reverse_lazy('ordertype_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = reverse_lazy('ordertype_list')
        return context

# --- PROBLEM TYPE CRUD ---
class ProblemTypeListView(LoginRequiredMixin, ListView):
    model = ProblemType
    template_name = 'cadastros/problemtype_list.html'
    context_object_name = 'problemtypes'

class ProblemTypeCreateView(LoginRequiredMixin, CreateView):
    model = ProblemType
    template_name = 'cadastros/generic_form.html'
    fields = ['name']
    success_url = reverse_lazy('problemtype_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Novo Tipo de Problema'
        context['back_url'] = reverse_lazy('problemtype_list')
        return context

class ProblemTypeUpdateView(LoginRequiredMixin, UpdateView):
    model = ProblemType
    template_name = 'cadastros/generic_form.html'
    fields = ['name']
    success_url = reverse_lazy('problemtype_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Editar Tipo de Problema'
        context['back_url'] = reverse_lazy('problemtype_list')
        return context

class ProblemTypeDeleteView(AdminRequiredMixin, DeleteView):
    model = ProblemType
    template_name = 'cadastros/generic_confirm_delete.html'
    success_url = reverse_lazy('problemtype_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = reverse_lazy('problemtype_list')
        return context

# --- TECHNICIAN (USER) CRUD ---
class TechnicianListView(LoginRequiredMixin, ListView):
    model = User
    template_name = 'cadastros/technician_list.html'
    context_object_name = 'technicians'
    
    def get_queryset(self):
        return User.objects.filter(profile__role='standard')

class TechnicianCreateView(AdminRequiredMixin, CreateView):
    model = User
    form_class = TechnicianForm
    template_name = 'cadastros/generic_form.html'
    success_url = reverse_lazy('technician_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Novo Técnico'
        context['back_url'] = reverse_lazy('technician_list')
        return context
        
    def form_valid(self, form):
        # The form's save method handles password and profile creation
        return super().form_valid(form)

class TechnicianUpdateView(AdminRequiredMixin, UpdateView):
    model = User
    form_class = TechnicianForm
    template_name = 'cadastros/generic_form.html'
    success_url = reverse_lazy('technician_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Editar Técnico'
        context['back_url'] = reverse_lazy('technician_list')
        return context

class TechnicianDeleteView(AdminRequiredMixin, DeleteView):
    model = User
    template_name = 'cadastros/generic_confirm_delete.html'
    success_url = reverse_lazy('technician_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = reverse_lazy('technician_list')
        return context
