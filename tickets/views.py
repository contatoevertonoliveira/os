from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy, reverse
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
        date_labels_objs = []
        current_d = start_date
        while current_d <= end_date:
            date_labels.append(current_d.strftime('%d/%m'))
            date_labels_objs.append(current_d)
            current_d += timedelta(days=1)
            
        context['chart_tech_labels'] = date_labels
        
        # Define a list of colors to cycle through
        colors = [
            '#4e73df', '#1cc88a', '#36b9cc', '#f6c23e', '#e74a3b', 
            '#858796', '#5a5c69', '#6610f2', '#fd7e14', '#20c997'
        ]
        
        for idx, tech in enumerate(techs):
            # Get ALL tickets for this tech to calculate historical backlog
            # We don't restrict by created_at here because we need to know about tickets created before start_date
            all_tech_tickets = Ticket.objects.filter(technicians=tech).exclude(status='canceled')
            
            # Global open tickets for this tech (for the legend/tooltip)
            open_tickets_count = all_tech_tickets.filter(status='open').count()
            
            # Calculate ACTIVE WORKLOAD (Backlog) for each day
            # This shows "Demanda" (Demand) - rising means more work assigned, falling means work completed
            data_points = []
            point_colors = [] # To show status (e.g. Red if overdue tickets existed on that day)
            
            has_activity_in_period = False
            
            for label_date in date_labels_objs: # We need the actual date objects corresponding to labels
                d_end = label_date.replace(hour=23, minute=59, second=59, microsecond=999999)
                
                # Active tickets on this day:
                # Created before/on this day AND (Not finished yet OR Finished after this day)
                active_on_day = all_tech_tickets.filter(
                    Q(created_at__lte=d_end) & 
                    (Q(finished_at__gt=d_end) | Q(finished_at__isnull=True))
                )
                
                count_today = active_on_day.count()
                data_points.append(count_today)
                
                if count_today > 0:
                    has_activity_in_period = True
                    
                # Check for delays on this specific day
                # Any active ticket on this day that had a deadline BEFORE this day
                has_overdue = active_on_day.filter(deadline__lt=d_end).exists()
                if has_overdue:
                    point_colors.append('#dc3545') # Red for overdue
                else:
                    point_colors.append(colors[idx % len(colors)]) # Default color
            
            # Only include tech if they have some activity (open tickets OR active in period)
            if open_tickets_count > 0 or has_activity_in_period:
                # Tech Photo URL
                photo_url = None
                job_title = "Técnico"
                station = ""
                email = tech.email
                personal_phone = ""
                company_phone = ""
                department = ""
                supervisor_name = ""
                profile_id = None
                
                if hasattr(tech, 'profile'):
                    if tech.profile.photo:
                        photo_url = tech.profile.photo.url
                    job_title = tech.profile.job_title or "Técnico"
                    station = tech.profile.station or ""
                    personal_phone = tech.profile.personal_phone or ""
                    company_phone = tech.profile.company_phone or ""
                    department = tech.profile.department or ""
                    profile_id = tech.profile.id
                    if tech.profile.supervisor and tech.profile.supervisor.user:
                        supervisor_name = f"{tech.profile.supervisor.user.get_full_name()}"
                
                # Build hierarchy string: "Diretoria / Serviços / Santander-SP"
                hierarchy_parts = []
                if department: hierarchy_parts.append(department)
                if job_title: hierarchy_parts.append(job_title)
                if station: hierarchy_parts.append(station)
                hierarchy_str = " / ".join(hierarchy_parts)
                
                # Determine Current Status Color (for the final point/legend)
                now = timezone.now()
                unfinished_tickets = all_tech_tickets.exclude(status='finished')
                has_overdue = unfinished_tickets.filter(deadline__lt=now).exists()
                has_warning = unfinished_tickets.filter(deadline__range=(now, now + timedelta(days=1))).exists()
                
                if has_overdue:
                    status_color = '#dc3545' # Red
                elif has_warning:
                    status_color = '#ffc107' # Yellow
                else:
                    status_color = '#198754' # Green

                tech_chart_datasets.append({
                    'label': f"{tech.first_name} {tech.last_name} ({tech.username}) - Backlog Atual: {count_today}", # count_today is the last one
                    'data': data_points,
                    'photo': photo_url,
                    'borderColor': colors[idx % len(colors)],
                    'open_tickets': open_tickets_count,
                    'status_color': status_color,
                    'pointBorderColors': point_colors, # Custom colors per point
                    # Extra info for Modal
                    'full_name': tech.get_full_name() or tech.username,
                    'email': email,
                    'hierarchy': hierarchy_str,
                    'phones': [p for p in [personal_phone, company_phone] if p],
                    'profile_id': tech.id, # Using User ID for edit link
                    'supervisor': supervisor_name
                })
        
        context['chart_tech_datasets'] = tech_chart_datasets
        
        # Charts Data - Systems
        systems = System.objects.all()
        system_labels = []
        system_resolved = []
        system_unresolved = []
        system_volume = []
        system_colors = []
        
        for system in systems:
            sys_tickets = tickets_qs.filter(systems=system)
            count = sys_tickets.count()
            
            if count > 0:
                resolved = sys_tickets.filter(status='finished').count()
                unresolved = sys_tickets.filter(Q(status='open') | Q(status='pending')).count()
                
                system_labels.append(system.name)
                system_resolved.append(resolved)
                system_unresolved.append(unresolved)
                system_volume.append(count)
                system_colors.append(system.color if system.color else '#6c757d')
                
        context['chart_system_labels'] = system_labels
        context['chart_system_data'] = system_volume
        context['chart_system_colors'] = system_colors
        
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

    def get_queryset(self):
        queryset = Ticket.objects.all().select_related('client', 'hub', 'equipment', 'ticket_type').prefetch_related('technicians', 'equipments')
        
        today = timezone.localtime(timezone.now()).date()

        q = self.request.GET.get('q') or None
        status = self.request.GET.get('status') or None
        ticket_type = self.request.GET.get('ticket_type') or None
        period = self.request.GET.get('period') or None
        start_date = self.request.GET.get('start_date') or None
        end_date = self.request.GET.get('end_date') or None
        leankeep_id = self.request.GET.get('leankeep_id') or None

        if not any([q, status, ticket_type, period, start_date, end_date, leankeep_id]):
            start_of_day = timezone.make_aware(datetime.combine(today, datetime.min.time()))
            end_of_day = timezone.make_aware(datetime.combine(today, datetime.max.time()))
            queryset = queryset.filter(created_at__range=(start_of_day, end_of_day))
            return queryset.order_by('-created_at')

        if q:
            queryset = queryset.filter(
                Q(client__name__icontains=q) |
                Q(description__icontains=q) |
                Q(id__icontains=q) |
                Q(ticket_type__name__icontains=q) |
                Q(leankeep_id__icontains=q)
            )

        if leankeep_id:
            queryset = queryset.filter(leankeep_id__icontains=leankeep_id)

        if status:
            queryset = queryset.filter(status=status)

        if ticket_type:
            queryset = queryset.filter(ticket_type_id=ticket_type)

        if period == 'all':
             pass # No date filter
        elif period == 'today':
            # Filter range for the whole day to avoid timezone issues
            start_of_day = timezone.make_aware(datetime.combine(today, datetime.min.time()))
            end_of_day = timezone.make_aware(datetime.combine(today, datetime.max.time()))
            queryset = queryset.filter(created_at__range=(start_of_day, end_of_day))
        elif period == 'week':
            # Start of week (Sunday)
            days_to_subtract = (today.weekday() + 1) % 7
            start_week = today - timedelta(days=days_to_subtract)
            start_week_dt = timezone.make_aware(datetime.combine(start_week, datetime.min.time()))
            queryset = queryset.filter(created_at__gte=start_week_dt)
        elif period == 'fortnight':
            start_fortnight = today - timedelta(days=15)
            start_fortnight_dt = timezone.make_aware(datetime.combine(start_fortnight, datetime.min.time()))
            queryset = queryset.filter(created_at__gte=start_fortnight_dt)
        elif period == 'month':
            start_month = today.replace(day=1)
            start_month_dt = timezone.make_aware(datetime.combine(start_month, datetime.min.time()))
            queryset = queryset.filter(created_at__gte=start_month_dt)
        elif period == 'custom':
            if start_date:
                queryset = queryset.filter(created_at__date__gte=start_date)
            if end_date:
                queryset = queryset.filter(created_at__date__lte=end_date)

        # Always order by created_at desc
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Context for filters
        context['ticket_types'] = TicketType.objects.all().order_by('name')
        context['status_choices'] = Ticket.STATUS_CHOICES
        
        # Determine if any filter is active
        is_filtered = any([
            self.request.GET.get('q'),
            self.request.GET.get('status'),
            self.request.GET.get('ticket_type'),
            self.request.GET.get('period'),
            self.request.GET.get('start_date'),
            self.request.GET.get('end_date'),
            self.request.GET.get('leankeep_id'),
        ])

        # If no filter is active, default visual state to 'today'
        context['current_period'] = self.request.GET.get('period', 'today' if not is_filtered else '')
        context['current_status'] = self.request.GET.get('status', '')
        context['current_ticket_type'] = self.request.GET.get('ticket_type', '')
        context['current_q'] = self.request.GET.get('q', '')
        context['current_start_date'] = self.request.GET.get('start_date', '')
        context['current_end_date'] = self.request.GET.get('end_date', '')
        context['current_leankeep_id'] = self.request.GET.get('leankeep_id', '')
        
        # Alerts (Toasts) for open/delayed tickets
        # Logic: Check for ANY ticket (not just filtered ones) that requires attention
        # Delayed: deadline < now AND status != finished/canceled
        # Open: status in [open, in_progress, pending]
        
        now = timezone.now()
        
        delayed_tickets = Ticket.objects.filter(
            deadline__lt=now
        ).exclude(
            status__in=['finished', 'canceled']
        ).select_related('client')

        open_tickets_qs = Ticket.objects.exclude(
            status__in=['finished', 'canceled']
        ).select_related('client')

        alerts = []

        for ticket in delayed_tickets:
            alerts.append({
                'type': 'danger',
                'title': 'Atenção: Atraso',
                'message': f'A ocorrência {ticket.formatted_id} está atrasada.',
                'icon': 'exclamation-triangle',
                'ticket_id': ticket.id
            })

        for ticket in open_tickets_qs:
            if ticket in delayed_tickets:
                continue
            if ticket.status == 'open':
                msg = f'A ocorrência {ticket.formatted_id} está em aberto.'
            elif ticket.status == 'in_progress':
                msg = f'A ocorrência {ticket.formatted_id} está em andamento.'
            elif ticket.status == 'pending':
                msg = f'A ocorrência {ticket.formatted_id} está aguardando aprovação.'
            else:
                msg = f'A ocorrência {ticket.formatted_id} requer atenção.'

            alerts.append({
                'type': 'info',
                'title': 'Pendência',
                'message': msg,
                'icon': 'info-circle',
                'ticket_id': ticket.id
            })

        context['alerts'] = alerts
        
        return context

class TicketDetailView(LoginRequiredMixin, DetailView):
    model = Ticket
    template_name = 'tickets/ticket_detail.html'
    context_object_name = 'ticket'

    def get_queryset(self):
        return Ticket.objects.select_related('client', 'hub', 'equipment', 'requester').prefetch_related('technicians', 'equipments', 'systems', 'updates', 'updates__images')

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

class ClientSearchView(LoginRequiredMixin, ListView):
    model = Client
    template_name = 'tickets/client_search.html'
    context_object_name = 'clients'
    paginate_by = 50

    def get_queryset(self):
        queryset = Client.objects.all().prefetch_related('systems', 'technicians', 'supervisor')
        q = self.request.GET.get('q')

        if q:
            queryset = queryset.filter(
                Q(name__icontains=q) |
                Q(group__icontains=q) |
                Q(cm_code__icontains=q) |
                Q(address__icontains=q) |
                Q(city__icontains=q) |
                Q(state__icontains=q) |
                Q(contact1_name__icontains=q) |
                Q(contact1_email__icontains=q) |
                Q(supervisor__username__icontains=q) |
                Q(supervisor__first_name__icontains=q) |
                Q(technicians__username__icontains=q) |
                Q(technicians__first_name__icontains=q) |
                Q(systems__name__icontains=q)
            ).distinct()
        
        return queryset.order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q'] = self.request.GET.get('q', '')
        return context
