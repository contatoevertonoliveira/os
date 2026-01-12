from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.db.models import Q, Exists, OuterRef, Subquery
from .models import *
from .forms import *
from .api import TicketAPIView  # Re-export for URL compatibility
from django.utils import timezone
from datetime import timedelta, datetime
from django.db.models import Count, Q

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Period handling
        period = self.request.GET.get('period', 'week')
        now = timezone.now()
        
        # Set default range (week)
        start_date = now - timedelta(days=7)
        end_date = now
        
        if period == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now
        elif period == 'yesterday':
            start_date = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = (now - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == 'week':
            start_date = now - timedelta(days=7)
            end_date = now
        elif period == 'month':
            start_date = now - timedelta(days=30)
            end_date = now
        elif period == 'year':
            start_date = now - timedelta(days=365)
            end_date = now
        elif period == 'custom':
            start_str = self.request.GET.get('start_date')
            end_str = self.request.GET.get('end_date')
            if start_str and end_str:
                try:
                    start_date = datetime.strptime(start_str, '%Y-%m-%d')
                    start_date = timezone.make_aware(start_date)
                    end_date = datetime.strptime(end_str, '%Y-%m-%d')
                    end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
                    end_date = timezone.make_aware(end_date)
                except ValueError:
                    pass # Fallback to default
        
        context['selected_period'] = period
        context['start_date'] = start_date
        context['end_date'] = end_date
        
        # Filter Tickets
        tickets_qs = Ticket.objects.filter(created_at__range=(start_date, end_date))
        
        # Counts
        context['total_tickets'] = tickets_qs.count()
        context['tickets_open'] = tickets_qs.filter(status='open').count()
        context['tickets_pending'] = tickets_qs.filter(status='pending').count()
        context['tickets_finished'] = tickets_qs.filter(status='finished').count()
        
        # Charts Data - Status
        status_counts = []
        status_labels = []
        for status_code, status_label in Ticket.STATUS_CHOICES:
            count = tickets_qs.filter(status=status_code).count()
            status_counts.append(count)
            status_labels.append(status_label)
        
        context['chart_status_labels'] = status_labels
        context['chart_status_data'] = status_counts
        
        # Charts Data - Tech Productivity (Line Chart with Photos)
        # We need data grouped by day for each tech
        techs = User.objects.filter(profile__role='technician')
        tech_chart_datasets = []
        
        # Generate date labels for the X-axis (all days in range)
        date_labels = []
        current_d = start_date
        while current_d <= end_date:
            date_labels.append(current_d.strftime('%d/%m'))
            current_d += timedelta(days=1)
            
        context['chart_tech_labels'] = date_labels
        
        for tech in techs:
            # Get completed tickets for this tech in the period
            tech_tickets = tickets_qs.filter(technicians=tech, status='finished')
            if tech_tickets.exists():
                # Group by day using Python to avoid DB timezone errors
                counts_dict = {}
                for created_at in tech_tickets.values_list('created_at', flat=True):
                    if created_at:
                        local_created_at = timezone.localtime(created_at)
                        day_str = local_created_at.strftime('%d/%m')
                        counts_dict[day_str] = counts_dict.get(day_str, 0) + 1
                
                # Map counts to the date_labels
                data_points = []
                for label in date_labels:
                    data_points.append(counts_dict.get(label, 0))
                
                # Tech Photo URL
                photo_url = None
                if hasattr(tech, 'profile') and tech.profile.photo:
                    photo_url = tech.profile.photo.url
                
                tech_chart_datasets.append({
                    'label': tech.username,
                    'data': data_points,
                    'photo': photo_url,
                    'borderColor': '#26923B'  # Default color since UserProfile doesn't have color field yet
                })
        
        context['chart_tech_datasets'] = tech_chart_datasets
        
        # Charts Data - Systems (Failures: Resolved vs Unresolved)
        systems = System.objects.all()
        system_labels = []
        system_resolved = []
        system_unresolved = []
        
        for system in systems:
            sys_tickets = tickets_qs.filter(systems=system)
            if sys_tickets.exists():
                resolved = sys_tickets.filter(status='finished').count()
                unresolved = sys_tickets.filter(Q(status='open') | Q(status='pending')).count()
                
                system_labels.append(system.name)
                system_resolved.append(resolved)
                system_unresolved.append(unresolved)
                
        context['chart_system_labels'] = system_labels # Keeping this for the Polar chart if needed, or reusing
        context['chart_system_data'] = [] # Placeholder if we remove the Polar chart or keep it
        # Actually, let's keep the Polar chart as "Tickets by System" (volume) 
        # and add the new one as "System Health" (Resolved vs Unresolved)
        
        # Re-populating the Polar chart data (Volume)
        polar_data = []
        polar_colors = []
        for system in systems:
             count = tickets_qs.filter(systems=system).count()
             if count > 0:
                 polar_data.append(count)
                 polar_colors.append(system.color if system.color else '#6c757d')
        context['chart_system_polar_data'] = polar_data
        context['chart_system_colors'] = polar_colors
        
        # New System Health Data
        context['chart_sys_health_labels'] = system_labels
        context['chart_sys_resolved'] = system_resolved
        context['chart_sys_unresolved'] = system_unresolved
        
        context['my_tickets'] = tickets_qs.filter(technicians=self.request.user).count()
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

class TicketModalView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Ticket
    form_class = TicketModalForm
    template_name = 'tickets/ticket_modal_body.html'
    success_message = "Ordem de Serviço atualizada com sucesso!"
    
    def get_success_url(self):
        # Retorna para a página anterior ou lista de tickets
        return self.request.META.get('HTTP_REFERER', reverse_lazy('ticket_list'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['updates'] = self.object.updates.all().order_by('-created_at')
        return context

    def form_valid(self, form):
        # Save the ticket changes first
        self.object = form.save()
        
        # Auto-assign current user to technicians if they are a technician/standard and not already assigned
        user = self.request.user
        if hasattr(user, 'profile') and user.profile.role in ['technician', 'standard']:
            if not self.object.technicians.filter(id=user.id).exists():
                self.object.technicians.add(user)
        
        # Process Evolution
        evolution_desc = self.request.POST.get('evolution_description', '')
        evolution_imgs = self.request.FILES.getlist('evolution_image')
        
        has_evolution = False
        if evolution_desc or evolution_imgs:
            update = TicketUpdate.objects.create(
                ticket=self.object,
                created_by=self.request.user,
                description=evolution_desc,
                image=None
            )
            
            for img in evolution_imgs:
                if hasattr(img, 'seek'):
                    img.seek(0)
                TicketUpdateImage.objects.create(
                    update=update,
                    image=img
                )
                
            has_evolution = True
            
        # Determine action
        save_action = self.request.POST.get('save_action')
        
        if save_action == 'close':
            # Redirect behavior (Standard SuccessMessageMixin behavior)
            messages.success(self.request, self.success_message)
            return redirect(self.get_success_url())
            
        else:
            # Stay/Refresh behavior (for 'stay' or AutoSave)
            if has_evolution:
                messages.success(self.request, "Evolução registrada com sucesso!")
            elif save_action == 'stay':
                messages.success(self.request, "Alterações salvas!")
            
            # For AutoSave (save_action is None), we usually don't want a flash message
            # or we want it handled by JS. 
            # But the view doesn't know it's AutoSave unless we pass a flag.
            # However, if we return rendered HTML, the JS replaces the modal content.
            # The JS for AutoSave does NOT show a toast if isAutoSave is true.
            
            context = self.get_context_data(form=form)
            return render(self.request, self.template_name, context)

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

class TicketUpdateDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        update = get_object_or_404(TicketUpdate, pk=pk)
        ticket = update.ticket
        
        # Check permissions if needed
        
        update.delete()
        
        # Return JSON for AJAX requests
        return JsonResponse({'status': 'success', 'message': 'Evolução excluída com sucesso!'})

class TicketUpdateEditView(LoginRequiredMixin, View):
    def post(self, request, pk):
        update = get_object_or_404(TicketUpdate, pk=pk)
        ticket = update.ticket
        
        new_description = request.POST.get('description')
        if new_description:
            update.description = new_description
            update.save()
            messages.success(request, "Evolução atualizada com sucesso!")
        
        # Render the modal body again
        form = TicketModalForm(instance=ticket)
        context = {
            'ticket': ticket,
            'form': form,
            'updates': ticket.updates.all().order_by('-created_at')
        }
        return render(request, 'tickets/ticket_modal_body.html', context)

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
class ProfileView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = UserProfile
    template_name = 'profile.html'
    form_class = UserProfileForm
    success_url = reverse_lazy('profile')
    success_message = "Perfil atualizado com sucesso!"
    
    def get_object(self, queryset=None):
        if hasattr(self.request.user, 'profile'):
            return self.request.user.profile
        return None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

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
    context_object_name = 'tickets'

    def get_queryset(self):
        queryset = Ticket.objects.select_related('client').prefetch_related('systems', 'technicians', 'technicians__profile')
        
        queryset = queryset.annotate(
            is_favorite=Exists(
                TicketFavorite.objects.filter(
                    ticket=OuterRef('pk'),
                    user=self.request.user
                )
            ),
            my_favorite_created_at=Subquery(
                TicketFavorite.objects.filter(
                    ticket=OuterRef('pk'),
                    user=self.request.user
                ).values('created_at')[:1]
            )
        )
        
        # Ordenar por cliente (para o regroup), favoritos primeiro, depois ordem de seleção
        return queryset.order_by('client__name', '-is_favorite', 'my_favorite_created_at')

class TaskFavoriteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk)
        favorite, created = TicketFavorite.objects.get_or_create(user=request.user, ticket=ticket)
        
        if not created:
            favorite.delete()
            is_favorite = False
        else:
            is_favorite = True
            
        return JsonResponse({'status': 'ok', 'is_favorite': is_favorite})

# User Management Views
class AdminRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not hasattr(request.user, 'profile') or request.user.profile.role not in ['admin', 'super_admin']:
             from django.core.exceptions import PermissionDenied
             raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

class UserListView(AdminRequiredMixin, ListView):
    model = User
    template_name = 'cadastros/user_list.html'
    context_object_name = 'users'
    
    def get_queryset(self):
        return User.objects.select_related('profile').all().order_by('first_name')

class UserCreateView(AdminRequiredMixin, SuccessMessageMixin, CreateView):
    model = User
    form_class = UserManagementForm
    template_name = 'cadastros/user_form.html'
    success_url = reverse_lazy('user_list')
    success_message = "Usuário cadastrado com sucesso!"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Novo Usuário"
        context['back_url'] = reverse_lazy('user_list')
        return context

class UserUpdateView(AdminRequiredMixin, SuccessMessageMixin, UpdateView):
    model = User
    form_class = UserManagementForm
    template_name = 'cadastros/user_form.html'
    success_url = reverse_lazy('user_list')
    success_message = "Usuário atualizado com sucesso!"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Editar Usuário: {self.object.get_full_name() or self.object.username}"
        context['back_url'] = reverse_lazy('user_list')
        return context

class UserDeleteView(AdminRequiredMixin, DeleteView):
    model = User
    template_name = 'cadastros/generic_confirm_delete.html'
    success_url = reverse_lazy('user_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = reverse_lazy('user_list')
        return context
