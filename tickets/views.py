from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView, View
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
        context['total_tickets'] = Ticket.objects.count()
        context['open_tickets'] = Ticket.objects.filter(status='open').count()
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

class TicketDetailView(LoginRequiredMixin, DetailView):
    model = Ticket
    template_name = 'tickets/ticket_detail.html'

class TicketCreateView(LoginRequiredMixin, CreateView):
    model = Ticket
    form_class = TicketForm
    template_name = 'tickets/ticket_form.html'
    success_url = reverse_lazy('ticket_list')

class TicketUpdateView(LoginRequiredMixin, UpdateView):
    model = Ticket
    form_class = TicketForm
    template_name = 'tickets/ticket_form.html'
    success_url = reverse_lazy('ticket_list')

class TicketDeleteView(LoginRequiredMixin, DeleteView):
    model = Ticket
    template_name = 'ticket_confirm_delete.html'
    success_url = reverse_lazy('ticket_list')

class TicketModalView(LoginRequiredMixin, DetailView):
    model = Ticket
    template_name = 'tickets/ticket_modal_body.html'

# Client Views
class ClientListView(LoginRequiredMixin, ListView):
    model = Client
    template_name = 'cadastros/client_list.html'
    context_object_name = 'clients'

class ClientCreateView(LoginRequiredMixin, CreateView):
    model = Client
    form_class = ClientForm
    template_name = 'cadastros/client_form.html'
    success_url = reverse_lazy('client_list')

class ClientUpdateView(LoginRequiredMixin, UpdateView):
    model = Client
    form_class = ClientForm
    template_name = 'cadastros/client_form.html'
    success_url = reverse_lazy('client_list')

class ClientDeleteView(LoginRequiredMixin, DeleteView):
    model = Client
    template_name = 'cadastros/generic_confirm_delete.html'
    success_url = reverse_lazy('client_list')

# Equipment Views
class EquipmentListView(LoginRequiredMixin, ListView):
    model = Equipment
    template_name = 'cadastros/equipment_list.html'
    context_object_name = 'equipments'

class EquipmentCreateView(LoginRequiredMixin, CreateView):
    model = Equipment
    fields = '__all__'
    template_name = 'cadastros/equipment_form.html'
    success_url = reverse_lazy('equipment_list')

class EquipmentUpdateView(LoginRequiredMixin, UpdateView):
    model = Equipment
    fields = '__all__'
    template_name = 'cadastros/equipment_form.html'
    success_url = reverse_lazy('equipment_list')

class EquipmentDeleteView(LoginRequiredMixin, DeleteView):
    model = Equipment
    template_name = 'cadastros/generic_confirm_delete.html'
    success_url = reverse_lazy('equipment_list')

# OrderType Views
class OrderTypeListView(LoginRequiredMixin, ListView):
    model = OrderType
    template_name = 'cadastros/ordertype_list.html'
    context_object_name = 'ordertypes'

class OrderTypeCreateView(LoginRequiredMixin, CreateView):
    model = OrderType
    fields = '__all__'
    template_name = 'cadastros/simple_form.html'
    success_url = reverse_lazy('ordertype_list')

class OrderTypeUpdateView(LoginRequiredMixin, UpdateView):
    model = OrderType
    fields = '__all__'
    template_name = 'cadastros/simple_form.html'
    success_url = reverse_lazy('ordertype_list')

class OrderTypeDeleteView(LoginRequiredMixin, DeleteView):
    model = OrderType
    template_name = 'cadastros/generic_confirm_delete.html'
    success_url = reverse_lazy('ordertype_list')

# ProblemType Views
class ProblemTypeListView(LoginRequiredMixin, ListView):
    model = ProblemType
    template_name = 'cadastros/problemtype_list.html'
    context_object_name = 'problemtypes'

class ProblemTypeCreateView(LoginRequiredMixin, CreateView):
    model = ProblemType
    fields = '__all__'
    template_name = 'cadastros/simple_form.html'
    success_url = reverse_lazy('problemtype_list')

class ProblemTypeUpdateView(LoginRequiredMixin, UpdateView):
    model = ProblemType
    fields = '__all__'
    template_name = 'cadastros/simple_form.html'
    success_url = reverse_lazy('problemtype_list')

class ProblemTypeDeleteView(LoginRequiredMixin, DeleteView):
    model = ProblemType
    template_name = 'cadastros/generic_confirm_delete.html'
    success_url = reverse_lazy('problemtype_list')

# Technician Views
class TechnicianListView(LoginRequiredMixin, ListView):
    model = UserProfile
    template_name = 'cadastros/technician_list.html'
    context_object_name = 'technicians'
    
    def get_queryset(self):
        return UserProfile.objects.filter(role__in=['technician', 'standard']) # Adjust based on logic

class TechnicianCreateView(LoginRequiredMixin, CreateView):
    model = User
    form_class = TechnicianForm
    template_name = 'cadastros/technician_form.html'
    success_url = reverse_lazy('technician_list')

class TechnicianUpdateView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = TechnicianForm
    template_name = 'cadastros/technician_form.html'
    success_url = reverse_lazy('technician_list')

class TechnicianDeleteView(LoginRequiredMixin, DeleteView):
    model = User
    template_name = 'cadastros/generic_confirm_delete.html'
    success_url = reverse_lazy('technician_list')

# System Views
class SystemListView(LoginRequiredMixin, ListView):
    model = System
    template_name = 'cadastros/system_list.html'
    context_object_name = 'systems'

class SystemCreateView(LoginRequiredMixin, CreateView):
    model = System
    fields = '__all__'
    template_name = 'cadastros/system_form.html'
    success_url = reverse_lazy('system_list')

class SystemUpdateView(LoginRequiredMixin, UpdateView):
    model = System
    fields = '__all__'
    template_name = 'cadastros/system_form.html'
    success_url = reverse_lazy('system_list')

class SystemDeleteView(LoginRequiredMixin, DeleteView):
    model = System
    template_name = 'cadastros/generic_confirm_delete.html'
    success_url = reverse_lazy('system_list')

# Profile & Settings
class ProfileView(LoginRequiredMixin, DetailView):
    model = UserProfile
    template_name = 'profile.html'
    
    def get_object(self):
        if hasattr(self.request.user, 'profile'):
            return self.request.user.profile
        return None

class SettingsView(LoginRequiredMixin, TemplateView):
    template_name = 'settings.html'

# Tasks
class TaskListView(LoginRequiredMixin, ListView):
    model = Ticket # Placeholder
    template_name = 'tasks/task_list.html'
    context_object_name = 'tasks'

class TaskFavoriteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        return JsonResponse({'status': 'ok'})
