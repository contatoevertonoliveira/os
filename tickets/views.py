from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView, View, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.db.models import Count, Exists, OuterRef
from django.contrib.auth import login
from django.contrib import messages
from django.http import JsonResponse
from .models import Ticket, Client, UserProfile, Equipment, OrderType, ProblemType, TicketUpdate, TicketFavorite, System
from django.contrib.auth.models import User
from .forms import TechnicianForm, TicketForm, TicketUpdateForm, TicketEvolutionForm, UserProfileForm, ClientForm

from django.contrib.messages.views import SuccessMessageMixin

# Mixin para verificar permissão de admin/super_admin
class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and \
               hasattr(self.request.user, 'profile') and \
               self.request.user.profile.role in ['admin', 'super_admin']

class ProfileView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = UserProfile
    form_class = UserProfileForm
    template_name = 'profile.html'
    success_url = reverse_lazy('profile')
    success_message = "Perfil atualizado com sucesso!"

    def get_object(self, queryset=None):
        return self.request.user.profile

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Meu Perfil'
        return context

class SettingsView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    template_name = 'settings.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Configurações'
        return context

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

class TaskListView(LoginRequiredMixin, ListView):
    model = Ticket
    template_name = 'tasks/task_list.html'
    context_object_name = 'tickets'

    def get_queryset(self):
        # Subquery to check if favorited by current user
        is_favorite = TicketFavorite.objects.filter(
            ticket=OuterRef('pk'),
            user=self.request.user
        )
        
        return Ticket.objects.exclude(status__in=['finished', 'canceled']).annotate(
            is_favorite=Exists(is_favorite)
        ).order_by('client__name', '-is_favorite', 'deadline', 'created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Lista de Tasks'
        return context

class TaskFavoriteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk)
        favorite, created = TicketFavorite.objects.get_or_create(user=request.user, ticket=ticket)
        
        if not created:
            favorite.delete()
            is_favorite = False
        else:
            is_favorite = True
            
        return JsonResponse({'is_favorite': is_favorite})

class TicketListView(LoginRequiredMixin, ListView):
    model = Ticket
    template_name = 'ticket_list.html'
    context_object_name = 'tickets'
    ordering = ['-created_at']

class TicketDetailView(LoginRequiredMixin, DetailView):
    model = Ticket
    template_name = 'ticket_detail.html'
    context_object_name = 'ticket'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['updates'] = self.object.updates.all()
        context['evolution_form'] = TicketEvolutionForm()
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = TicketEvolutionForm(request.POST, request.FILES)
        if form.is_valid():
            evolution = form.save(commit=False)
            evolution.ticket = self.object
            evolution.created_by = request.user
            evolution.save()
            messages.success(request, "Evolução registrada com sucesso!")
            return redirect('ticket_detail', pk=self.object.pk)
        
        context = self.get_context_data()
        context['evolution_form'] = form
        return self.render_to_response(context)

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
        context['updates'] = self.object.updates.all()
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
    template_name = 'cadastros/client_form.html'
    form_class = ClientForm
    success_url = reverse_lazy('client_list')
    success_message = "Cliente cadastrado com sucesso!"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Novo Cliente'
        context['back_url'] = reverse_lazy('client_list')
        return context

class ClientUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Client
    template_name = 'cadastros/client_form.html'
    form_class = ClientForm
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
    template_name = 'cadastros/equipment_form.html'
    fields = ['name', 'description']
    success_url = reverse_lazy('equipment_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Novo Equipamento'
        context['back_url'] = reverse_lazy('equipment_list')
        return context

class EquipmentUpdateView(LoginRequiredMixin, UpdateView):
    model = Equipment
    template_name = 'cadastros/equipment_form.html'
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
    template_name = 'cadastros/simple_form.html'
    fields = ['name']
    success_url = reverse_lazy('ordertype_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Novo Tipo de Ordem'
        context['back_url'] = reverse_lazy('ordertype_list')
        return context

class OrderTypeUpdateView(LoginRequiredMixin, UpdateView):
    model = OrderType
    template_name = 'cadastros/simple_form.html'
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
    template_name = 'cadastros/simple_form.html'
    fields = ['name']
    success_url = reverse_lazy('problemtype_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Novo Tipo de Problema'
        context['back_url'] = reverse_lazy('problemtype_list')
        return context

class ProblemTypeUpdateView(LoginRequiredMixin, UpdateView):
    model = ProblemType
    template_name = 'cadastros/simple_form.html'
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

# --- TECHNICIAN CRUD ---
class TechnicianListView(LoginRequiredMixin, ListView):
    model = User
    template_name = 'cadastros/technician_list.html'
    context_object_name = 'technicians'
    
    def get_queryset(self):
        return User.objects.filter(profile__role='standard')

class TechnicianCreateView(LoginRequiredMixin, CreateView):
    model = User
    template_name = 'cadastros/technician_form.html'
    form_class = TechnicianForm
    success_url = reverse_lazy('technician_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Novo Técnico'
        context['back_url'] = reverse_lazy('technician_list')
        return context

class TechnicianUpdateView(LoginRequiredMixin, UpdateView):
    model = User
    template_name = 'cadastros/technician_form.html'
    form_class = TechnicianForm
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

# --- SYSTEM CRUD ---
class SystemListView(LoginRequiredMixin, ListView):
    model = System
    template_name = 'cadastros/system_list.html'
    context_object_name = 'systems'

class SystemCreateView(LoginRequiredMixin, CreateView):
    model = System
    template_name = 'cadastros/system_form.html'
    fields = ['name', 'color', 'description']
    success_url = reverse_lazy('system_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Novo Sistema'
        context['back_url'] = reverse_lazy('system_list')
        return context

class SystemUpdateView(LoginRequiredMixin, UpdateView):
    model = System
    template_name = 'cadastros/system_form.html'
    fields = ['name', 'color', 'description']
    success_url = reverse_lazy('system_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Editar Sistema'
        context['back_url'] = reverse_lazy('system_list')
        return context

class SystemDeleteView(AdminRequiredMixin, DeleteView):
    model = System
    template_name = 'cadastros/generic_confirm_delete.html'
    success_url = reverse_lazy('system_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = reverse_lazy('system_list')
        return context

# --- MODAL EDIT VIEW ---
class TicketModalView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Ticket
    template_name = 'ticket_modal_body.html'
    form_class = TicketUpdateForm
    success_url = reverse_lazy('ticket_list')
    success_message = "Ordem de Serviço atualizada com sucesso!"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['updates'] = self.object.updates.all()
        return context

    def form_valid(self, form):
        # Save the form but don't redirect
        self.object = form.save()
        
        # Check for evolution fields in POST data
        evolution_description = self.request.POST.get('evolution_description')
        evolution_image = self.request.FILES.get('evolution_image')
        
        if evolution_description:
            TicketUpdate.objects.create(
                ticket=self.object,
                created_by=self.request.user,
                description=evolution_description,
                image=evolution_image
            )
            
        # Return the rendered template with the updated object
        # This allows AJAX to update the modal content
        context = self.get_context_data(form=form)
        return self.render_to_response(context)
