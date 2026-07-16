from django.shortcuts import render, get_object_or_404, redirect
import os
import json
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Exists, OuterRef, Subquery, Prefetch
from django.template.loader import get_template, render_to_string
try:
    from xhtml2pdf import pisa
except ModuleNotFoundError:
    pisa = None
from django.contrib.staticfiles import finders
from django.conf import settings
from django.db import transaction
from django.utils.text import slugify
from django.db.utils import OperationalError, ProgrammingError
from django.forms import inlineformset_factory
from .models import *
from .forms import *
from .api import TicketAPIView  # Re-export for URL compatibility
from .views_checklist_config import ChecklistConfigView, ChecklistTemplateCreateView, ChecklistTemplateUpdateView, ChecklistTemplateDeleteView, ChecklistItemCreateView, ChecklistItemDeleteView, ChecklistItemUpdateView
from django.utils import timezone
from datetime import timedelta, datetime
from django.db.models import Count, Q, Case, When, Value, IntegerField
from django.db.models.functions import Coalesce
from collections import defaultdict
from django.views.decorators.http import require_http_methods

@method_decorator(ensure_csrf_cookie, name='dispatch')
class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Period handling
        # Período dos cards/gráficos principais (mantém opção de filtro)
        period = self.request.GET.get('period', 'year')
        now = timezone.now()

        # Set default range (year)
        start_date = now - timedelta(days=365)
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
            # Mês corrente (do dia 1 até agora)
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
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

        # Formatar label do período para exibir na badge
        if period == 'today':
            context['period_label'] = 'Hoje'
        elif period == 'yesterday':
            context['period_label'] = 'Ontem'
        elif period == 'week':
            context['period_label'] = 'Semana'
        elif period == 'month':
            context['period_label'] = 'Mês'
        elif period == 'year':
            context['period_label'] = 'Ano'
        elif period == 'custom':
            # Formatar datas para o padrão dd/mm/yyyy
            start_formatted = start_date.strftime('%d/%m/%Y')
            end_formatted = end_date.strftime('%d/%m/%Y')
            context['period_label'] = f'{start_formatted} à {end_formatted}'
        else:
            context['period_label'] = 'Este ano'

        # Filtros adicionais: cliente e colaborador
        client_id = self.request.GET.get('client')
        collaborator_id = self.request.GET.get('collaborator')

        # Filter Tickets
        tickets_qs = Ticket.objects.filter(created_at__range=(start_date, end_date))

        # Aplicar filtros de cliente e colaborador
        if client_id:
            try:
                tickets_qs = tickets_qs.filter(client_id=int(client_id))
            except (TypeError, ValueError):
                pass

        if collaborator_id:
            try:
                tickets_qs = tickets_qs.filter(technicians__id=int(collaborator_id)).distinct()
            except (TypeError, ValueError):
                pass

        # Adicionar dados de filtros ao context
        context['current_client'] = client_id
        context['current_collaborator'] = collaborator_id
        context['clients_list'] = Client.objects.all().order_by('name')
        context['collaborators_list'] = User.objects.filter(is_active=True).select_related('profile').order_by('first_name', 'last_name')

        # Obter nome do cliente para exibir na badge
        if client_id:
            try:
                client_obj = Client.objects.get(id=int(client_id))
                context['current_client_name'] = client_obj.name
            except (Client.DoesNotExist, TypeError, ValueError):
                context['current_client_name'] = None

        # Obter nome do colaborador para exibir na badge
        if collaborator_id:
            try:
                collab_obj = User.objects.get(id=int(collaborator_id))
                context['current_collaborator_name'] = collab_obj.get_full_name() or collab_obj.username
            except (User.DoesNotExist, TypeError, ValueError):
                context['current_collaborator_name'] = None
        
        # Counts
        context['total_tickets'] = tickets_qs.count()
        context['tickets_open'] = tickets_qs.filter(status='open').count()
        context['tickets_pending'] = tickets_qs.filter(status='pending').count()
        context['tickets_finished'] = tickets_qs.filter(status='finished').count()
        
        # Charts Data - Status
        status_counts = []
        status_labels = []
        from .models import TicketStatus
        all_statuses = list(TicketStatus.objects.filter(is_active=True).order_by('order', 'name'))
        if not all_statuses:
            for status_code, status_label in Ticket.STATUS_CHOICES:
                count = tickets_qs.filter(status=status_code).count()
                status_counts.append(count)
                status_labels.append(status_label)
        else:
            for ts in all_statuses:
                count = tickets_qs.filter(status=ts.code).count()
                status_counts.append(count)
                status_labels.append(ts.name)
        
        context['chart_status_labels'] = status_labels
        context['chart_status_data'] = status_counts
        
        # Charts Data - Produtividade Recente (OS por Cliente no mês)
        # Agrupa tickets do período por cliente
        from django.db.models import Count
        client_counts = (
            tickets_qs
            .values('client__name')
            .annotate(total=Count('id'))
            .order_by('-total')[:20]  # Top 20 clientes
        )

        # Separa em labels e dados
        client_labels = []
        client_data = []
        for item in client_counts:
            name = item['client__name'] or 'Sem Cliente'
            client_labels.append(name)
            client_data.append(item['total'])

        context['chart_client_labels'] = client_labels
        context['chart_client_data'] = client_data
        
        # Charts Data - Systems
        systems = System.objects.all()
        system_labels = []
        system_resolved = []
        system_open = []
        system_overdue = []
        system_volume = []
        system_colors = []
        now = timezone.now()
        
        for system in systems:
            sys_tickets = tickets_qs.filter(systems=system)
            count = sys_tickets.count()
            
            if count > 0:
                resolved = sys_tickets.filter(status='finished').count()
                open_tickets = sys_tickets.filter(Q(status='open') | Q(status='pending'))
                open = open_tickets.filter(deadline__gte=now).count()
                overdue = open_tickets.filter(deadline__lt=now).count()
                
                system_labels.append(system.name)
                system_resolved.append(resolved)
                system_open.append(open)
                system_overdue.append(overdue)
                system_volume.append(count)
                system_colors.append(system.color if system.color else '#6c757d')
                
        context['chart_system_labels'] = system_labels
        context['chart_system_data'] = system_volume
        context['chart_system_colors'] = system_colors
        
        context['chart_sys_health_labels'] = system_labels
        context['chart_sys_resolved'] = system_resolved
        context['chart_sys_open'] = system_open
        context['chart_sys_overdue'] = system_overdue
        
        context['my_tickets'] = tickets_qs.filter(technicians=self.request.user).count()
        return context

@method_decorator(ensure_csrf_cookie, name='dispatch')
class TokenLoginView(LoginView):
    template_name = 'login.html'
    authentication_form = TokenLoginForm
    redirect_authenticated_user = True

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip

    def form_valid(self, form):
        try:
            # Garante que o usuário está ativo
            user = form.get_user()
            if not user.is_active:
                if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'errors': {'token': ['Usuário inativo.']}}, status=400)
                return self.form_invalid(form)

            # Obtém o IP do cliente
            ip = self.get_client_ip(self.request)

            # Verifica se já existe uma ActiveSession para este usuário com IP diferente
            from .models import ActiveSession
            existing_sessions = ActiveSession.objects.filter(user=user)
            for active in existing_sessions:
                if active.ip_address != ip:
                    # Sessão de outro IP - invalida as sessões do Django antigas
                    from django.contrib.sessions.models import Session
                    try:
                        old_session = Session.objects.filter(session_key=active.session_key).first()
                        if old_session:
                            old_session.delete()
                    except Exception:
                        pass
                    active.delete()

            # Realiza o login (chama auth_login internamente)
            response = super().form_valid(form)

            # Cria/atualiza ActiveSession para a nova sessão
            try:
                ActiveSession.objects.update_or_create(
                    session_key=self.request.session.session_key,
                    defaults={
                        'user': user,
                        'ip_address': ip,
                        'user_agent': self.request.META.get('HTTP_USER_AGENT', '')[:500],
                    }
                )
            except Exception:
                pass

            # Se for AJAX, retorna JSON em vez de redirecionar
            # Check for both standard header and custom Django header
            if self.request.headers.get('x-requested-with') == 'XMLHttpRequest' or \
               self.request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'redirect_url': str(self.get_success_url())})

            return response
        except Exception as e:
            # Em caso de erro inesperado, retorna JSON se for AJAX para evitar "Erro de conexão" genérico no frontend
            if self.request.headers.get('x-requested-with') == 'XMLHttpRequest' or \
               self.request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
                import traceback
                traceback.print_exc() # Loga o erro no console do servidor
                return JsonResponse({'success': False, 'errors': {'__all__': [f"Erro interno no servidor: {str(e)}"]}}, status=500)
            raise e

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest' or \
           self.request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
        return super().form_invalid(form)

    def get_success_url(self):
        url = self.get_redirect_url()
        return url or reverse_lazy('dashboard')

@method_decorator(ensure_csrf_cookie, name='dispatch')
class ServicesHubView(TemplateView):
    template_name = 'services_hub.html'

    def get(self, request, *args, **kwargs):
        return redirect('home')

class WelcomeView(TemplateView):
    template_name = 'welcome.html'

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('dashboard')
        # Padronização: a home (/) deve levar direto para a tela de login
        # (o layout do login é mantido em templates/login.html).
        return redirect('login')

# Ticket Views
@method_decorator(ensure_csrf_cookie, name='dispatch')
class TicketListView(LoginRequiredMixin, ListView):
    model = Ticket
    template_name = 'tickets/ticket_list.html'
    context_object_name = 'tickets'

    def get_queryset(self):
        queryset = (
            Ticket.objects.all()
            .select_related(
                'client',
                'hub',
                'equipment',
                'ticket_type',
                'created_by',
                'created_by__profile',
                'requester',
                'requester__profile',
            )
            .prefetch_related('technicians', 'equipments')
        )
        
        today = timezone.localtime(timezone.now()).date()

        q = self.request.GET.get('q') or None
        status = self.request.GET.get('status') or None
        ticket_type = self.request.GET.get('ticket_type') or None
        period = self.request.GET.get('period') or None
        start_date = self.request.GET.get('start_date') or None
        end_date = self.request.GET.get('end_date') or None
        leankeep_id = self.request.GET.get('leankeep_id') or None
        client_id = self.request.GET.get('client') or None
        creator = self.request.GET.get('creator') or None

        # Se nenhum periodo foi especificado, mostra TODAS as OS (não mais apenas de hoje)
        has_main_filters = any([q, status, ticket_type, period, start_date, end_date, leankeep_id])
        if not has_main_filters and not period:
            # Se nenhum filtro foi informado e nenhum período foi selecionado,
            # mostra todas as OS (sem filtro de data por padrão)
            pass

        if client_id:
            try:
                queryset = queryset.filter(client_id=int(client_id))
            except (TypeError, ValueError):
                pass

        if q:
            status_lower = q.strip().lower()
            status_map = {
                'aberto': 'open',
                'em andamento': 'in_progress',
                'pendente': 'pending',
                'finalizado': 'finished',
                'cancelado': 'canceled',
                'aberta': 'open',
                'pendente': 'pending',
                'finalizada': 'finished',
                'cancelada': 'canceled'
            }
            status_filter = status_map.get(status_lower, None)
            
            q_filter = (
                Q(client__name__icontains=q) |
                Q(description__icontains=q) |
                Q(id__icontains=q) |
                Q(ticket_type__name__icontains=q) |
                Q(leankeep_id__icontains=q) |
                Q(equipment__name__icontains=q) |
                Q(equipments__name__icontains=q)
            )
            
            if status_filter is not None:
                q_filter |= Q(status=status_filter)
            
            queryset = queryset.filter(q_filter)

        if leankeep_id:
            queryset = queryset.filter(leankeep_id__icontains=leankeep_id)

        if status:
            queryset = queryset.filter(status=status)

        if creator:
            try:
                creator_id = int(creator)
                queryset = queryset.filter(
                    Q(created_by_id=creator_id) | (Q(created_by__isnull=True) & Q(requester_id=creator_id))
                )
            except (TypeError, ValueError):
                pass

        if ticket_type:
            queryset = queryset.filter(ticket_type_id=ticket_type)

        if period == 'today':
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
        elif period == 'month':
            start_month = today.replace(day=1)
            start_month_dt = timezone.make_aware(datetime.combine(start_month, datetime.min.time()))
            queryset = queryset.filter(created_at__gte=start_month_dt)

        # Data inicial/fim (funciona independente do radio de período)
        if start_date:
            try:
                sd = datetime.strptime(start_date, '%Y-%m-%d')
                sd_dt = timezone.make_aware(datetime.combine(sd, datetime.min.time()))
                queryset = queryset.filter(created_at__gte=sd_dt)
            except (ValueError, TypeError):
                pass
        if end_date:
            try:
                ed = datetime.strptime(end_date, '%Y-%m-%d')
                ed_dt = timezone.make_aware(datetime.combine(ed, datetime.max.time()))
                queryset = queryset.filter(created_at__lte=ed_dt)
            except (ValueError, TypeError):
                pass

        # Ordenação pela ordem definida em "Cadastros > Status de OS"
        # Usa o campo 'order' de TicketStatus para definir a prioridade
        from django.db.models import Subquery, OuterRef

        # Busca o valor de 'order' de cada TicketStatus para o status do Ticket
        ticket_status_order = TicketStatus.objects.filter(
            code=OuterRef('status')
        ).values('order')[:1]

        queryset = queryset.annotate(
            status_order=Subquery(ticket_status_order)
        )

        queryset = queryset.order_by('status_order', '-updated_at')

        from .models import TicketListOrder
        return TicketListOrder.apply_saved_order(self.request.user, queryset)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Context for filters
        context['ticket_types'] = TicketType.objects.all().order_by('name')
        context['status_list'] = TicketStatus.objects.filter(is_active=True).order_by('order', 'name')
        context['status_choices'] = list(context['status_list'].values_list('code', 'name'))
        if not context['status_choices']:
            context['status_choices'] = Ticket.STATUS_CHOICES

        # Mapa de badge HTML por status (para atualização AJAX inline)
        from django.utils.safestring import mark_safe
        badge_map = {}
        for ts in context['status_list']:
            dummy_ticket = Ticket(status=ts.code)
            badge_map[ts.code] = dummy_ticket.status_display_html
        entries = ',\n'.join(f'  "{k}": {json.dumps(v)}' for k, v in badge_map.items())
        context['status_badge_html_map'] = mark_safe(f'{{\n{entries}\n}}')
        
        # Determine if any filter is active
        is_filtered = any([
            self.request.GET.get('q'),
            self.request.GET.get('status'),
            self.request.GET.get('ticket_type'),
            self.request.GET.get('period'),
            self.request.GET.get('start_date'),
            self.request.GET.get('end_date'),
            self.request.GET.get('leankeep_id'),
            self.request.GET.get('creator'),
        ])

        # If no filter is active, default visual state to 'all' (mostra todas as OS)
        context['current_period'] = self.request.GET.get('period', 'all' if not is_filtered else '')
        context['current_status'] = self.request.GET.get('status', '')
        context['current_ticket_type'] = self.request.GET.get('ticket_type', '')
        context['current_q'] = self.request.GET.get('q', '')
        context['current_start_date'] = self.request.GET.get('start_date', '')
        context['current_end_date'] = self.request.GET.get('end_date', '')
        context['current_leankeep_id'] = self.request.GET.get('leankeep_id', '')
        context['current_client'] = self.request.GET.get('client', '')
        context['current_creator'] = self.request.GET.get('creator', '')

        # Lista de criadores (colaboradores que abriram OS)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        creator_ids = (
            Ticket.objects.annotate(
                _cid=Coalesce('created_by_id', 'requester_id')
            )
            .exclude(_cid__isnull=True)
            .values_list('_cid', flat=True)
            .distinct()
        )
        context['creators_filter_list'] = (
            User.objects.filter(is_active=True, id__in=creator_ids)
            .order_by('first_name', 'username')
            .only('id', 'first_name', 'username')
        )

        # Lista de clientes para filtro (select)
        context['clients_filter_list'] = Client.objects.all().order_by('name').only('id', 'name')
        
        # Alerts (Toasts) for open/delayed tickets
        # Requisito: não saturar. Mostrar no máximo 2x por dia por usuário:
        # 1) primeira vez do dia (primeiro acesso/login)
        # 2) após o término do turno (ex.: 20:00 no diurno), uma vez.
        now = timezone.localtime(timezone.now())
        today = timezone.localdate()

        # Persistência por usuário (não depende de sessão, para não repetir após logout/login)
        should_show = False
        try:
            profile = getattr(self.request.user, 'profile', None)
            if profile:
                # Mostrar apenas UMA vez por dia: na primeira visita do dia à página.
                # Quando a data do último toast for diferente de hoje, mostra e grava a data.
                if profile.ticket_toast_state_date != today:
                    profile.ticket_toast_state_date = today
                    should_show = True

                if should_show:
                    profile.save(update_fields=[
                        'ticket_toast_state_date',
                    ])
        except Exception:
            # Se falhar (ex.: migração ainda não aplicada), mantém comportamento antigo: mostra.
            should_show = True

        alerts = []
        if should_show:
            # Logic: Check for ANY ticket (not just filtered ones) that requires attention
            # Delayed: deadline < now AND status != finished/canceled
            # Open: status in [open, in_progress, pending]
            delayed_tickets = Ticket.objects.filter(
                deadline__lt=now
            ).exclude(
                status__in=['finished', 'canceled']
            ).select_related('client')

            open_tickets_qs = Ticket.objects.exclude(
                status__in=['finished', 'canceled']
            ).select_related('client')

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

        start_of_day = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        end_of_day = timezone.make_aware(datetime.combine(today, datetime.max.time()))
        today_count = Ticket.objects.filter(created_at__range=(start_of_day, end_of_day)).count()
        context['today_date'] = today
        context['now'] = now
        context['today_tickets_count'] = today_count
        context['can_daily_report_all'] = getattr(getattr(self.request.user, 'profile', None), 'role', None) in ['admin', 'super_admin']
        context['all_tickets'] = Ticket.objects.all().select_related('client').order_by('-created_at')

        # Permitir que admin/super_admin ajuste o "criador" da OS direto na lista
        role = getattr(getattr(self.request.user, 'profile', None), 'role', None)
        context['can_edit_ticket_creator'] = role in ['admin', 'super_admin']
        if context['can_edit_ticket_creator']:
            context['creator_candidates'] = (
                User.objects.filter(is_active=True)
                .select_related('profile')
                .order_by('first_name', 'last_name', 'username')
            )
        
        return context

class TicketDetailView(LoginRequiredMixin, DetailView):
    model = Ticket
    template_name = 'tickets/ticket_detail.html'
    context_object_name = 'ticket'

    def dispatch(self, request, *args, **kwargs):
        pk = kwargs.get('pk')
        return redirect(f"{reverse('ticket_list')}?period=all&open={pk}")

    def get_queryset(self):
        return Ticket.objects.select_related('client', 'hub', 'equipment', 'requester').prefetch_related('requesters', 'technicians', 'equipments', 'systems', 'updates', 'updates__images', 'images')

    def dispatch(self, request, *args, **kwargs):
        pk = kwargs.get('pk')
        return redirect(f"{reverse('ticket_list')}?period=all&open={pk}")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = reverse_lazy('ticket_list')
        return context


class TicketPDFView(LoginRequiredMixin, View):
    def get(self, request, pk, *args, **kwargs):
        if pisa is None:
            return HttpResponse('PDF indisponível.', status=500)

        ticket = (
            Ticket.objects.select_related('client', 'hub', 'equipment', 'requester', 'ticket_type', 'problem_type', 'order_type')
            .prefetch_related('requesters', 'technicians', 'equipments', 'systems', 'updates', 'updates__images', 'images')
            .filter(pk=pk)
            .first()
        )
        if not ticket:
            return HttpResponse('OS não encontrada.', status=404)

        updates = ticket.updates.all().order_by('created_at', 'id')
        attachments = []
        if ticket.image:
            attachments.append({'url': ticket.image.url, 'label': 'Imagem Inicial'})
        for img in ticket.images.all():
            attachments.append({'url': img.image.url, 'label': 'Anexo'})
        attachment_rows = []
        for i in range(0, len(attachments), 4):
            row = attachments[i:i + 4]
            if len(row) < 4:
                row = row + ([None] * (4 - len(row)))
            attachment_rows.append(row)
        context = {
            'user': request.user,
            'ticket': ticket,
            'updates': updates,
            'attachment_rows': attachment_rows,
            'generated_at': timezone.now(),
            'logo_path': os.path.join(settings.MEDIA_ROOT, 'images', 'logo_principal.png'),
        }

        template_path = 'tickets/ticket_pdf.html'
        response = HttpResponse(content_type='application/pdf')
        response['X-Frame-Options'] = 'SAMEORIGIN'
        download = str(request.GET.get('download') or '').strip() == '1'
        disposition = 'attachment' if download else 'inline'
        leankeep_part = (ticket.leankeep_id or '').strip() or '00000'
        client_part = (ticket.client.name or '').strip()
        client_part = slugify(client_part).replace('-', '_').upper() or 'CLIENTE'
        response['Content-Disposition'] = f'{disposition}; filename="{ticket.formatted_id}_{leankeep_part}_{client_part}.pdf"'

        template = get_template(template_path)
        html = template.render(context)

        def link_callback(uri, rel):
            if uri.startswith('http://') or uri.startswith('https://'):
                return uri

            if settings.STATIC_URL and uri.startswith(settings.STATIC_URL):
                path = uri.replace(settings.STATIC_URL, '')
                absolute_path = finders.find(path)
                if absolute_path:
                    return absolute_path

            if settings.MEDIA_URL and uri.startswith(settings.MEDIA_URL):
                path = uri.replace(settings.MEDIA_URL, '')
                absolute_path = os.path.join(settings.MEDIA_ROOT, path.replace('/', os.sep))
                if os.path.exists(absolute_path):
                    return absolute_path

            if not uri.startswith('/'):
                if 'media/' in uri:
                    possible_path = os.path.join(settings.BASE_DIR, uri.replace('/', os.sep))
                    if os.path.exists(possible_path):
                        return possible_path

            return uri

        pisa_status = pisa.CreatePDF(html, dest=response, link_callback=link_callback)
        if pisa_status.err:
            return HttpResponse('Erro ao gerar PDF.', status=500)
        return response


class TicketPDFViewerView(LoginRequiredMixin, TemplateView):
    template_name = 'tickets/pdf_viewer.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pk = kwargs.get('pk')
        ticket = Ticket.objects.filter(pk=pk).only('id').first()
        if not ticket:
            context['not_found'] = True
            return context
        context['title'] = 'Relatório Detalhado do Chamado'
        context['pdf_url'] = reverse('ticket_pdf', kwargs={'pk': pk})
        context['status_url'] = reverse('ticket_pdf_status', kwargs={'pk': pk})
        context['download_url'] = f"{context['pdf_url']}?download=1"
        return context

class TicketCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Ticket
    form_class = TicketForm
    template_name = 'tickets/ticket_form.html'
    success_url = reverse_lazy('ticket_list')
    success_message = "Ordem de Serviço criada com sucesso!"

    def dispatch(self, request, *args, **kwargs):
        # Criação centralizada na lista (/tickets/) via modal
        return redirect(f"{reverse('ticket_list')}?create=1")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Nova Ordem de Serviço"
        context['back_url'] = reverse_lazy('ticket_list')
        return context

    def form_valid(self, form):
        # Garante que a OS sempre registre quem abriu/criou.
        if not getattr(form.instance, "created_by_id", None):
            form.instance.created_by = self.request.user
        response = super().form_valid(form)
        files = self.request.FILES.getlist('ticket_images')
        if files:
            if not self.object.image:
                self.object.image = files[0]
                self.object.save(update_fields=['image'])
            for f in files:
                if hasattr(f, 'seek'):
                    f.seek(0)
                TicketImage.objects.create(ticket=self.object, image=f, uploaded_by=self.request.user)
        return response


class TicketCreateModalView(LoginRequiredMixin, View):
    """
    Criação de OS via modal (AJAX) na lista.
    GET -> retorna HTML do corpo da modal (form).
    POST -> cria a OS e retorna JSON com o id para inserir na lista.
    """

    template_name = 'tickets/ticket_create_modal_body.html'

    def get(self, request, *args, **kwargs):
        form = TicketForm(prefix='create')
        context = {'form': form}
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        form = TicketForm(request.POST, request.FILES, prefix='create')
        if not form.is_valid():
            html = render_to_string(self.template_name, {'form': form}, request=request)
            return JsonResponse({'status': 'error', 'html': html}, status=400)

        ticket = form.save(commit=False)
        if not getattr(ticket, "created_by_id", None):
            ticket.created_by = request.user
        ticket.save()
        form.save_m2m()

        # Imagens (mesmo fluxo do TicketCreateView)
        files = request.FILES.getlist(f'{form.prefix}-ticket_images')
        if files:
            if not ticket.image:
                ticket.image = files[0]
                ticket.save(update_fields=['image'])
            for f in files:
                if hasattr(f, 'seek'):
                    f.seek(0)
                TicketImage.objects.create(ticket=ticket, image=f, uploaded_by=request.user)

        return JsonResponse({'status': 'success', 'ticket_id': ticket.id})


class TicketAccordionItemView(LoginRequiredMixin, View):
    """
    Retorna o HTML de 1 item do accordion da lista (para inserir via JS após criar uma OS).
    """

    template_name = 'tickets/_ticket_accordion_item.html'

    def get(self, request, pk, *args, **kwargs):
        ticket = (
            Ticket.objects.filter(pk=pk)
            .select_related(
                'client',
                'hub',
                'equipment',
                'ticket_type',
                'created_by',
                'created_by__profile',
                'requester',
                'requester__profile',
            )
            .prefetch_related('technicians', 'equipments')
            .first()
        )
        if not ticket:
            return HttpResponse('OS não encontrada.', status=404)

        role = getattr(getattr(request.user, 'profile', None), 'role', None)
        can_edit_ticket_creator = role in ['admin', 'super_admin']
        context = {
            'ticket': ticket,
            'now': timezone.now(),
            'can_edit_ticket_creator': can_edit_ticket_creator,
        }
        return render(request, self.template_name, context)


class TicketMiniPreviewView(LoginRequiredMixin, View):
    """
    Retorna um resumo da OS para ser usado como "miniatura" na Passagem de Turno,
    permitindo consultar rapidamente sem sair da página.
    """

    template_name = 'tasks/_ticket_mini_preview.html'

    def get(self, request, pk, *args, **kwargs):
        ticket = (
            Ticket.objects.filter(pk=pk)
            .select_related(
                'client',
                'hub',
                'ticket_type',
                'requester',
                'created_by',
                'contact_requester',
                'contact_client_requester',
                'contact_responsible',
                'contact_jumper_responsible',
            )
            .prefetch_related('systems', 'technicians')
            .first()
        )
        if not ticket:
            return HttpResponse('OS não encontrada.', status=404)
        return render(request, self.template_name, {'ticket': ticket})

class TicketUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Ticket
    form_class = TicketForm
    template_name = 'tickets/ticket_form.html'
    success_url = reverse_lazy('ticket_list')
    success_message = "Ordem de Serviço atualizada com sucesso!"

    def dispatch(self, request, *args, **kwargs):
        # Edição centralizada na lista (/tickets/) via accordion
        pk = kwargs.get('pk')
        return redirect(f"{reverse('ticket_list')}?period=all&open={pk}")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Editar OS #{self.object.formatted_id}"
        context['back_url'] = reverse_lazy('ticket_list')
        context['updates'] = self.object.updates.all()
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        files = self.request.FILES.getlist('ticket_images')
        if files:
            if not self.object.image:
                self.object.image = files[0]
                self.object.save(update_fields=['image'])
            for f in files:
                if hasattr(f, 'seek'):
                    f.seek(0)
                TicketImage.objects.create(ticket=self.object, image=f, uploaded_by=self.request.user)
        return response

class TicketDeleteView(LoginRequiredMixin, DeleteView):
    model = Ticket
    template_name = 'ticket_confirm_delete.html'
    success_url = reverse_lazy('ticket_list')

    def dispatch(self, request, *args, **kwargs):
        # Esta view é "delete direto". Mantemos restrito a Admin/Super Admin,
        # pois outros níveis usam o fluxo de solicitação/aprovação.
        try:
            from django.core.exceptions import PermissionDenied
            if not _is_admin_or_super(request.user):
                raise PermissionDenied
            role_code = getattr(getattr(request.user, 'profile', None), 'role', None)
            if role_code != 'super_admin':
                page = AppPage.objects.filter(url_name='ticket_delete').first()
                if page and not page.is_enabled:
                    raise PermissionDenied

                if page and role_code:
                    role = RoleLevel.objects.filter(code=role_code, is_active=True).first()
                    if role:
                        perm = RolePagePermission.objects.filter(role=role, page=page).first()
                        if perm and not perm.allowed:
                            raise PermissionDenied
        except (OperationalError, ProgrammingError):
            # Se tabelas de permissão ainda não existirem, não bloqueia aqui
            pass
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = reverse_lazy('ticket_list')
        ticket = self.get_object()
        context['linked_entries_count'] = ShiftHandoverEntry.objects.filter(ticket=ticket).count()
        return context

    def form_valid(self, form):
        ticket = self.get_object()
        ShiftHandoverEntry.objects.filter(ticket=ticket).delete()
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
            # Close behavior: retorna HTML para o JS fechar (exceto se não for AJAX)
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                context = self.get_context_data(form=form)
                return render(self.request, self.template_name, context)
            # Fallback para non-AJAX
            messages.success(self.request, self.success_message)
            return redirect(self.get_success_url())

        else:
            # Stay/Refresh behavior (for 'stay' or AutoSave)
            if has_evolution:
                messages.success(self.request, "Evolução registrada com sucesso!")
            elif save_action == 'stay':
                messages.success(self.request, "Alterações salvas!")

            context = self.get_context_data(form=form)
            return render(self.request, self.template_name, context)


class TicketInlineView(TicketModalView):
    """
    Mesma edição da OS da modal, porém renderizada para uso inline (collapse) na lista.
    """
    template_name = 'tickets/ticket_inline_body.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['now'] = timezone.now()
        return context

    def post(self, request, *args, **kwargs):
        # Para evitar salvar alterações "sem querer", só persistimos campos da OS
        # quando o usuário clicar explicitamente no botão de salvar.
        # O botão "Salvar e Evoluir" deve apenas registrar evolução (texto/imagens),
        # sem alterar os campos da OS se o usuário não salvou.
        self.object = self.get_object()

        inline_action = (request.POST.get('inline_action') or '').strip()
        if inline_action == 'evolve':
            # Registra evolução sem salvar alterações nos campos da OS
            evolution_desc = request.POST.get('evolution_description', '')
            evolution_imgs = request.FILES.getlist('evolution_image')

            user = request.user
            if hasattr(user, 'profile') and user.profile.role in ['technician', 'standard']:
                if not self.object.technicians.filter(id=user.id).exists():
                    self.object.technicians.add(user)

            if evolution_desc or evolution_imgs:
                update = TicketUpdate.objects.create(
                    ticket=self.object,
                    created_by=request.user,
                    description=evolution_desc,
                    image=None
                )
                for img in evolution_imgs:
                    if hasattr(img, 'seek'):
                        img.seek(0)
                    TicketUpdateImage.objects.create(update=update, image=img)
                inline_save_status = 'ok'
                inline_save_message = 'Evolução registrada com sucesso!'
            else:
                inline_save_status = 'warning'
                inline_save_message = 'Informe a evolução ou selecione uma imagem.'

            form = self.form_class(instance=self.object)
            context = self.get_context_data(form=form)
            context['inline_save_status'] = inline_save_status
            context['inline_save_message'] = inline_save_message
            return render(request, self.template_name, context)

        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        context = self.get_context_data(form=form)
        context['inline_save_status'] = 'error'
        return render(self.request, self.template_name, context)

    def form_valid(self, form):
        # Reaproveita a regra da modal, mas sem redirect ao "fechar".
        # Aqui o frontend decide se vai recolher o card.
        self.object = form.save()

        user = self.request.user
        if hasattr(user, 'profile') and user.profile.role in ['technician', 'standard']:
            if not self.object.technicians.filter(id=user.id).exists():
                self.object.technicians.add(user)

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
                TicketUpdateImage.objects.create(update=update, image=img)
            has_evolution = True

        # Upload de imagens da OS (thumbnails)
        ticket_files = self.request.FILES.getlist('ticket_images')
        if ticket_files:
            if not self.object.image:
                self.object.image = ticket_files[0]
                self.object.save(update_fields=['image'])
            for f in ticket_files:
                if hasattr(f, 'seek'):
                    f.seek(0)
                TicketImage.objects.create(ticket=self.object, image=f, uploaded_by=self.request.user)

        # Exclusões pendentes do histórico (aplica somente quando salvar a OS)
        pending_delete_updates = (self.request.POST.get('pending_delete_updates') or '').strip()
        if pending_delete_updates:
            ids = [s.strip() for s in pending_delete_updates.split(',') if s.strip().isdigit()]
            if ids:
                role = getattr(getattr(self.request.user, 'profile', None), 'role', None)
                for update_id in ids:
                    upd = TicketUpdate.objects.filter(pk=int(update_id), ticket=self.object).first()
                    if not upd:
                        continue
                    can_delete = bool(role in ['admin', 'super_admin'] or upd.created_by_id == self.request.user.id)
                    if not can_delete:
                        continue
                    upd.delete()

        save_action = self.request.POST.get('save_action')
        if has_evolution:
            inline_save_message = "Evolução registrada com sucesso!"
        elif save_action in ['stay', 'collapse']:
            inline_save_message = "Alterações salvas!"
        else:
            inline_save_message = ""

        context = self.get_context_data(form=form)
        context['inline_save_status'] = 'ok'
        context['inline_save_message'] = inline_save_message
        return render(self.request, self.template_name, context)

# Client Views
@method_decorator(ensure_csrf_cookie, name='dispatch')
class ClientListView(LoginRequiredMixin, ListView):
    model = Client
    template_name = 'cadastros/client_list.html'
    context_object_name = 'clients'

    def get_queryset(self):
        return (
            Client.objects.all()
            .select_related('supervisor')
            .prefetch_related('systems', 'technicians')
            .order_by('name')
        )


@login_required
def client_quick_update(request, pk):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método inválido.'}, status=405)

    client = get_object_or_404(Client, pk=pk)

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'Dados inválidos.'}, status=400)

    name = (payload.get('name') or '').strip()
    if not name:
        return JsonResponse({'status': 'error', 'message': 'O nome do cliente é obrigatório.'}, status=400)

    client.name = name
    client.email = (payload.get('email') or '').strip() or None
    client.phone = (payload.get('phone') or '').strip() or None
    client.phone2 = (payload.get('phone2') or '').strip() or None
    client.address = (payload.get('address') or '').strip() or None

    client.contact1_name = (payload.get('contact1_name') or '').strip() or None
    client.contact1_phone = (payload.get('contact1_phone') or '').strip() or None
    client.contact1_email = (payload.get('contact1_email') or '').strip() or None

    client.contact2_name = (payload.get('contact2_name') or '').strip() or None
    client.contact2_phone = (payload.get('contact2_phone') or '').strip() or None
    client.contact2_email = (payload.get('contact2_email') or '').strip() or None

    client.is_preferred = bool(payload.get('is_preferred'))

    try:
        client.save()
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'Não foi possível salvar as alterações.'}, status=500)

    return JsonResponse({
        'status': 'success',
        'client': {
            'id': client.id,
            'name': client.name,
            'email': client.email or '',
            'phone': client.phone or '',
            'phone2': client.phone2 or '',
            'address': client.address or '',
            'contact1_name': client.contact1_name or '',
            'contact1_phone': client.contact1_phone or '',
            'contact1_email': client.contact1_email or '',
            'contact2_name': client.contact2_name or '',
            'contact2_phone': client.contact2_phone or '',
            'contact2_email': client.contact2_email or '',
            'is_preferred': client.is_preferred,
        }
    })

def sync_contact_client_from_client(client):
    """Sincroniza ContactPerson + ClientHub contacts -> ContactClient para aparecer no solicitante da OS."""
    # Remove registros antigos para evitar duplicidade
    ContactClient.objects.filter(client_ref_id=client.id).delete()
    for cp in client.contact_persons.filter(is_active=True):
        if cp.name.strip():
            ContactClient.objects.create(
                client_ref_id=client.id,
                name=cp.name,
                email=cp.email or '',
                phone=cp.phone or '',
                client_name=client.name,
                is_active=True,
            )
    # Sincroniza contatos dos hubs/lojas
    for hub in client.hubs.all():
        if hub.contact_name and hub.contact_name.strip():
            ContactClient.objects.create(
                client_ref_id=client.id,
                hub_ref_id=hub.id,
                name=hub.contact_name.strip(),
                email=hub.email or '',
                phone=hub.phone or '',
                client_name=client.name,
                hub_name=hub.name,
                is_active=True,
            )


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
        if self.request.POST:
            context['hubs'] = ClientHubFormSet(self.request.POST, self.request.FILES)
            context['contacts_formset'] = ContactPersonFormSet(self.request.POST)
        else:
            context['hubs'] = ClientHubFormSet()
            context['contacts_formset'] = ContactPersonFormSet()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        hubs = context['hubs']
        contacts_formset = context['contacts_formset']
        if hubs.is_valid() and contacts_formset.is_valid():
            self.object = form.save()
            hubs.instance = self.object
            hubs.save()
            contacts_formset.instance = self.object
            contacts_formset.save()
            sync_contact_client_from_client(self.object)
            return super().form_valid(form)
        else:
            return self.render_to_response(self.get_context_data(form=form))


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
        if self.request.POST:
            context['hubs'] = ClientHubFormSet(self.request.POST, self.request.FILES, instance=self.object)
            context['contacts_formset'] = ContactPersonFormSet(self.request.POST, instance=self.object)
        else:
            context['hubs'] = ClientHubFormSet(instance=self.object)
            context['contacts_formset'] = ContactPersonFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        hubs = context['hubs']
        contacts_formset = context['contacts_formset']
        if hubs.is_valid() and contacts_formset.is_valid():
            self.object = form.save()
            hubs.instance = self.object
            hubs.save()
            contacts_formset.instance = self.object
            contacts_formset.save()
            sync_contact_client_from_client(self.object)
            return super().form_valid(form)
        else:
            return self.render_to_response(self.get_context_data(form=form))

class ClientDeleteView(LoginRequiredMixin, DeleteView):
    model = Client
    template_name = 'cadastros/generic_confirm_delete.html'
    success_url = reverse_lazy('client_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = reverse_lazy('client_list')

        # Verifica OSs vinculadas a este cliente
        client = self.get_object()
        from .models import Ticket
        open_tickets = Ticket.objects.filter(client=client).exclude(status='finished')
        total_tickets = Ticket.objects.filter(client=client).count()
        context['related_tickets_count'] = total_tickets
        context['related_open_tickets'] = open_tickets

        # Verifica outros vínculos importantes
        context['related_hubs_count'] = client.hubs.count()
        context['related_contacts_count'] = client.contact_persons.count()

        return context

    def delete(self, request, *args, **kwargs):
        client = self.get_object()

        # Verifica se há OSs em aberto (não finalizadas)
        from .models import Ticket
        open_tickets = Ticket.objects.filter(client=client).exclude(status='finished')

        if open_tickets.exists():
            messages.error(request, 
                f'Não é possível excluir este cliente pois existem {open_tickets.count()} OS(s) em aberto vinculadas a ele. '
                f'Finalize ou cancele as OSs antes de excluir o cliente.')
            return redirect('client_list')

        total_tickets = Ticket.objects.filter(client=client).count()
        if total_tickets > 0:
            messages.warning(request, 
                f'Atenção: Todas as {total_tickets} OS(s) deste cliente também serão excluídas permanentemente!')

        return super().delete(request, *args, **kwargs)


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

# OrderType Views (Now Managing TicketType as "Tipos de Chamados")
class OrderTypeListView(LoginRequiredMixin, ListView):
    model = TicketType
    template_name = 'cadastros/ordertype_list.html'
    context_object_name = 'ordertypes'

class OrderTypeCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = TicketType
    fields = '__all__'
    template_name = 'cadastros/simple_form.html'
    success_url = reverse_lazy('ordertype_list')
    success_message = "Tipo de Chamado cadastrado com sucesso!"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Novo Tipo de Chamado"
        context['back_url'] = reverse_lazy('ordertype_list')
        return context

class OrderTypeUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = TicketType
    fields = '__all__'
    template_name = 'cadastros/simple_form.html'
    success_url = reverse_lazy('ordertype_list')
    success_message = "Tipo de Chamado atualizado com sucesso!"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Editar Tipo de Chamado: {self.object.name}"
        context['back_url'] = reverse_lazy('ordertype_list')
        return context

class OrderTypeDeleteView(LoginRequiredMixin, DeleteView):
    model = TicketType
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


class ResponsibleListView(LoginRequiredMixin, ListView):
    model = User
    template_name = 'cadastros/responsible_list.html'
    context_object_name = 'responsibles'

    def get_queryset(self):
        return (
            User.objects.filter(profile__role='operator', profile__fixed_client__isnull=False)
            .select_related('profile', 'profile__fixed_client')
            .order_by('first_name', 'username')
        )


class ResponsibleCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = User
    form_class = ResponsibleForm
    template_name = 'cadastros/responsible_form.html'
    success_url = reverse_lazy('responsible_list')
    success_message = "Responsável cadastrado com sucesso!"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Novo Responsável"
        context['back_url'] = reverse_lazy('responsible_list')
        return context


class ResponsibleUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = User
    form_class = ResponsibleForm
    template_name = 'cadastros/responsible_form.html'
    success_url = reverse_lazy('responsible_list')
    success_message = "Responsável atualizado com sucesso!"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Editar Responsável: {self.object.first_name or self.object.username}"
        context['back_url'] = reverse_lazy('responsible_list')
        return context


class ResponsibleDeleteView(LoginRequiredMixin, DeleteView):
    model = User
    template_name = 'cadastros/generic_confirm_delete.html'
    success_url = reverse_lazy('responsible_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = reverse_lazy('responsible_list')
        return context

    def form_valid(self, form):
        messages.success(self.request, "Responsável excluído com sucesso!")
        return super().form_valid(form)


class ContactClientListView(LoginRequiredMixin, ListView):
    model = ContactClient
    template_name = "cadastros/contactclient_list.html"
    context_object_name = "contacts"

    def get_queryset(self):
        return ContactClient.objects.all().order_by("client_name", "hub_name", "name")


class ContactClientCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = ContactClient
    form_class = ContactClientForm
    template_name = "cadastros/generic_form.html"
    success_url = reverse_lazy("contactclient_list")
    success_message = "Contato do cliente cadastrado com sucesso!"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Novo Contato do Cliente"
        context["back_url"] = reverse_lazy("contactclient_list")
        return context


class ContactClientUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = ContactClient
    form_class = ContactClientForm
    template_name = "cadastros/generic_form.html"
    success_url = reverse_lazy("contactclient_list")
    success_message = "Contato do cliente atualizado com sucesso!"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Editar Contato do Cliente: {self.object.name}"
        context["back_url"] = reverse_lazy("contactclient_list")
        return context


class ContactClientDeleteView(LoginRequiredMixin, DeleteView):
    model = ContactClient
    template_name = "cadastros/generic_confirm_delete.html"
    success_url = reverse_lazy("contactclient_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["back_url"] = reverse_lazy("contactclient_list")
        return context

    def form_valid(self, form):
        messages.success(self.request, "Contato do cliente excluído com sucesso!")
        return super().form_valid(form)


class ContactJumperListView(LoginRequiredMixin, ListView):
    model = ContactJumper
    template_name = "cadastros/contactjumper_list.html"
    context_object_name = "contacts"

    def get_queryset(self):
        return ContactJumper.objects.all().order_by("name")


class ContactJumperCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = ContactJumper
    form_class = ContactJumperForm
    template_name = "cadastros/generic_form.html"
    success_url = reverse_lazy("contactjumper_list")
    success_message = "Contato JumperFour cadastrado com sucesso!"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Novo Contato JumperFour"
        context["back_url"] = reverse_lazy("contactjumper_list")
        return context


class ContactJumperUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = ContactJumper
    form_class = ContactJumperForm
    template_name = "cadastros/generic_form.html"
    success_url = reverse_lazy("contactjumper_list")
    success_message = "Contato JumperFour atualizado com sucesso!"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Editar Contato JumperFour: {self.object.name}"
        context["back_url"] = reverse_lazy("contactjumper_list")
        return context


class ContactJumperDeleteView(LoginRequiredMixin, DeleteView):
    model = ContactJumper
    template_name = "cadastros/generic_confirm_delete.html"
    success_url = reverse_lazy("contactjumper_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["back_url"] = reverse_lazy("contactjumper_list")
        return context

    def form_valid(self, form):
        messages.success(self.request, "Contato JumperFour excluído com sucesso!")
        return super().form_valid(form)

class TravelSegmentCreateView(LoginRequiredMixin, CreateView):
    model = TravelSegment
    form_class = TravelSegmentForm
    template_name = 'cadastros/travel_segment_form.html'
    
    def get_success_url(self):
        return reverse('travel_list') # Redirect to main list, or maybe detail
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['travel_id'] = self.kwargs.get('travel_id')
        return context

    def form_valid(self, form):
        travel = get_object_or_404(TechnicianTravel, pk=self.kwargs['travel_id'])
        form.instance.travel = travel
        return super().form_valid(form)

class TravelSegmentUpdateView(LoginRequiredMixin, UpdateView):
    model = TravelSegment
    form_class = TravelSegmentForm
    template_name = 'cadastros/travel_segment_form.html'
    success_url = reverse_lazy('travel_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['travel_id'] = self.object.travel.id
        return context

class TravelSegmentDeleteView(LoginRequiredMixin, DeleteView):
    model = TravelSegment
    template_name = 'cadastros/generic_confirm_delete.html'
    
    def get_success_url(self):
        return reverse('travel_detail', kwargs={'pk': self.object.travel.pk})

    def form_valid(self, form):
        messages.success(self.request, "Segmento excluído com sucesso!")
        return super().form_valid(form)

class TicketUpdateDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        update = get_object_or_404(TicketUpdate, pk=pk)
        ticket = update.ticket
        
        # Check permissions if needed
        
        update.delete()
        
        # Return JSON for AJAX requests
        return JsonResponse({'status': 'success', 'message': 'Evolução excluída com sucesso!'})

class TicketUpdateImageDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        img_obj = get_object_or_404(TicketUpdateImage, pk=pk)
        update = img_obj.update
        role = getattr(getattr(request.user, 'profile', None), 'role', None)
        can_delete = bool(role in ['admin', 'super_admin'] or update.created_by_id == request.user.id)
        if not can_delete:
            return JsonResponse({'status': 'error', 'message': 'Sem permissão para excluir esta imagem.'}, status=403)

        if img_obj.image:
            img_obj.image.delete(save=False)
        img_obj.delete()
        return JsonResponse({'status': 'success', 'message': 'Imagem excluída com sucesso!'})

class TicketImageDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        img_obj = get_object_or_404(TicketImage, pk=pk)
        ticket = img_obj.ticket
        role = getattr(getattr(request.user, 'profile', None), 'role', None)
        can_delete = bool(
            role in ['admin', 'super_admin']
            or img_obj.uploaded_by_id == request.user.id
            or getattr(ticket, 'created_by_id', None) == request.user.id
        )
        if not can_delete:
            return JsonResponse({'status': 'error', 'message': 'Sem permissão para excluir esta imagem.'}, status=403)

        # Se esta imagem estiver setada como "principal" no ticket.image, trocar para outra ou limpar.
        next_img = TicketImage.objects.filter(ticket=ticket).exclude(pk=img_obj.pk).order_by('-uploaded_at').first()
        is_primary = bool(getattr(ticket, 'image', None) and img_obj.image and ticket.image.name == img_obj.image.name)

        if img_obj.image:
            img_obj.image.delete(save=False)
        img_obj.delete()

        if is_primary:
            ticket.image = next_img.image if next_img else None
            ticket.save(update_fields=['image'])

        return JsonResponse({'status': 'success', 'message': 'Imagem excluída com sucesso!'})

class TicketUpdateEditView(LoginRequiredMixin, View):
    def post(self, request, pk):
        update = get_object_or_404(TicketUpdate, pk=pk)
        ticket = update.ticket
        
        new_description = request.POST.get('description')
        if new_description:
            update.description = new_description
            update.save()
            messages.success(request, "Evolução atualizada com sucesso!")
        
        # Re-render (modal ou inline)
        form = TicketModalForm(instance=ticket)
        context = {
            'ticket': ticket,
            'form': form,
            'updates': ticket.updates.all().order_by('-created_at'),
            'now': timezone.now(),
        }

        if request.headers.get('X-Ticket-Inline') == '1':
            return render(request, 'tickets/ticket_inline_body.html', context)
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

# TicketStatus Views
class TicketStatusListView(LoginRequiredMixin, ListView):
    model = TicketStatus
    template_name = 'cadastros/ticketstatus_list.html'
    context_object_name = 'status_list'

class TicketStatusCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = TicketStatus
    form_class = TicketStatusForm
    template_name = 'cadastros/ticketstatus_form.html'
    success_url = reverse_lazy('ticketstatus_list')
    success_message = "Status de OS criado com sucesso!"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Novo Status de OS"
        context['back_url'] = reverse_lazy('ticketstatus_list')
        return context


class TicketStatusUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = TicketStatus
    form_class = TicketStatusForm
    template_name = 'cadastros/ticketstatus_form.html'
    success_url = reverse_lazy('ticketstatus_list')
    success_message = "Status de OS atualizado com sucesso!"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Editar Status de OS"
        context['back_url'] = reverse_lazy('ticketstatus_list')
        return context

class TicketStatusDeleteView(LoginRequiredMixin, DeleteView):
    model = TicketStatus
    template_name = 'cadastros/generic_confirm_delete.html'
    success_url = reverse_lazy('ticketstatus_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = reverse_lazy('ticketstatus_list')
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
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not hasattr(request.user, 'profile') or request.user.profile.role not in ['admin', 'super_admin']:
             from django.core.exceptions import PermissionDenied
             raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
    
    def get_object(self, queryset=None):
        obj, created = SystemSettings.objects.get_or_create(pk=1)
        return obj

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        tab = request.POST.get('_tab', '')

        if tab == 'ai':
            # Chave geral (liga/desliga Chat IA + Voz para todos os usuários) — só
            # o Super Admin pode mexer nisso, mesmo que a request chegue direto no
            # POST (a tela já esconde o formulário para Admin comum).
            if request.user.profile.role != 'super_admin':
                from django.core.exceptions import PermissionDenied
                raise PermissionDenied
            obj = self.object
            obj.ai_enabled = request.POST.get('ai_enabled') == 'on'
            obj.save(update_fields=['ai_enabled'])
            messages.success(request, "Configurações de IA atualizadas com sucesso!")
            return redirect(reverse_lazy('settings') + '?tab=ai')

        # A aba "Integrações" saiu daqui — agora é a tela própria /settings/integrations/
        # (IntegrationsSettingsView), com cadastro em lista pra Busca e Voz.

        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['checklist_templates'] = ChecklistTemplate.objects.annotate(item_count=Count('items')).all()
        context['ai_provider_configs'] = AIProviderConfig.objects.all()
        context['ai_provider_config_form'] = AIProviderConfigForm()
        return context


def _require_settings_admin(request):
    """Mesma checagem de acesso usada em SettingsView — admin/super_admin apenas."""
    from django.core.exceptions import PermissionDenied
    if not request.user.is_authenticated:
        raise PermissionDenied
    if not hasattr(request.user, 'profile') or request.user.profile.role not in ['admin', 'super_admin']:
        raise PermissionDenied


class AIProviderConfigCreateView(LoginRequiredMixin, View):
    """POST /settings/ai-config/create/ — cadastra uma nova configuração de IA na lista."""

    def post(self, request):
        _require_settings_admin(request)
        form = AIProviderConfigForm(request.POST)
        if form.is_valid():
            config = form.save(commit=False)
            # Primeira configuração cadastrada já entra ativa, senão a lista ficaria sem nenhuma em uso
            if not AIProviderConfig.objects.exists():
                config.is_active = True
            config.save()
            messages.success(request, f'Configuração "{config.name}" cadastrada com sucesso!')
        else:
            messages.error(request, "Não foi possível cadastrar: verifique os campos informados.")
        return redirect(reverse_lazy('settings') + '?tab=ai')


class AIProviderConfigUpdateView(LoginRequiredMixin, View):
    """POST /settings/ai-config/<pk>/update/ — edita uma configuração de IA existente."""

    def post(self, request, pk):
        _require_settings_admin(request)
        config = get_object_or_404(AIProviderConfig, pk=pk)
        # Precisa ser capturada ANTES de vincular o form — form.save(commit=False)
        # muta a própria instância de "config" em memória (mesmo objeto), então
        # lê-la depois já traria o valor novo (vazio), não o antigo.
        old_api_key = config.api_key
        form = AIProviderConfigForm(request.POST, instance=config)
        if form.is_valid():
            updated = form.save(commit=False)
            # Chave em branco no formulário de edição = manter a chave já salva
            if not (request.POST.get('api_key') or '').strip():
                updated.api_key = old_api_key
            updated.save()
            messages.success(request, f'Configuração "{updated.name}" atualizada com sucesso!')
        else:
            messages.error(request, "Não foi possível salvar: verifique os campos informados.")
        return redirect(reverse_lazy('settings') + '?tab=ai')


class AIProviderConfigDeleteView(LoginRequiredMixin, View):
    """POST /settings/ai-config/<pk>/delete/ — remove uma configuração de IA da lista."""

    def post(self, request, pk):
        _require_settings_admin(request)
        config = get_object_or_404(AIProviderConfig, pk=pk)
        was_active = config.is_active
        name = config.name
        config.delete()
        if was_active:
            # Ativa automaticamente outra, se sobrar alguma — pra não deixar o Jota4 sem provedor
            fallback = AIProviderConfig.objects.first()
            if fallback:
                fallback.is_active = True
                fallback.save(update_fields=['is_active'])
        messages.success(request, f'Configuração "{name}" removida.')
        return redirect(reverse_lazy('settings') + '?tab=ai')


class AIProviderConfigActivateView(LoginRequiredMixin, View):
    """POST /settings/ai-config/<pk>/activate/ — marca esta configuração como a ativa (switch da lista)."""

    def post(self, request, pk):
        _require_settings_admin(request)
        config = get_object_or_404(AIProviderConfig, pk=pk)
        config.is_active = True
        config.save()  # o save() do model já desativa as demais
        return JsonResponse({"ok": True, "active_id": config.id})


class AIProviderConfigRevealView(LoginRequiredMixin, View):
    """GET /settings/ai-config/<pk>/reveal/ — retorna a chave de API completa (não mascarada).
    Restrito a Super Admin — Admin comum só enxerga a chave mascarada na listagem."""

    def get(self, request, pk):
        profile = getattr(request.user, 'profile', None)
        if not profile or profile.role != 'super_admin':
            return JsonResponse({"ok": False, "error": "Apenas Super Admin pode visualizar a chave completa."}, status=403)
        config = get_object_or_404(AIProviderConfig, pk=pk)
        resp = JsonResponse({"ok": True, "api_key": config.api_key})
        resp['Cache-Control'] = 'no-store'
        return resp


class IntegrationsSettingsView(LoginRequiredMixin, View):
    """
    GET/POST /settings/integrations/ — tela própria (não uma aba de Settings) pra
    caber no sistema de permissões por página: por padrão só Super Admin acessa
    (ver AppPage/RolePagePermission criados na migration 0098), mas pode ser
    liberada pra outros níveis depois, normalmente, pela tela de Permissões.
    """
    template_name = 'settings_integrations.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not hasattr(request.user, 'profile') or request.user.profile.role not in ['admin', 'super_admin']:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_object(self):
        obj, _ = SystemSettings.objects.get_or_create(pk=1)
        return obj

    def get(self, request):
        context = {
            'system_settings': self.get_object(),
            'search_provider_configs': SearchProviderConfig.objects.all(),
            'voice_provider_configs': VoiceProviderConfig.objects.all(),
            'search_provider_config_form': SearchProviderConfigForm(),
            'voice_provider_config_form': VoiceProviderConfigForm(),
        }
        return render(request, self.template_name, context)

    def post(self, request):
        # Única ação de POST direto nesta tela (fora dos modais/CRUD): salvar o
        # modo de seleção de voz (livre por usuário x universal).
        obj = self.get_object()
        obj.voice_selection_mode = request.POST.get('voice_selection_mode', 'per_user')
        obj.universal_tts_voice_gender = request.POST.get('universal_tts_voice_gender', 'female')
        obj.universal_elevenlabs_voice_id = request.POST.get('universal_elevenlabs_voice_id', '').strip()
        obj.save(update_fields=['voice_selection_mode', 'universal_tts_voice_gender', 'universal_elevenlabs_voice_id'])
        messages.success(request, "Modo de voz atualizado com sucesso!")
        return redirect(reverse_lazy('settings_integrations'))


class SearchProviderConfigCreateView(LoginRequiredMixin, View):
    """POST /settings/search-config/create/ — cadastra uma nova configuração de busca na lista."""

    def post(self, request):
        _require_settings_admin(request)
        form = SearchProviderConfigForm(request.POST)
        if form.is_valid():
            config = form.save(commit=False)
            if not SearchProviderConfig.objects.exists():
                config.is_active = True
            config.save()
            messages.success(request, f'Configuração de busca "{config.name}" cadastrada com sucesso!')
        else:
            messages.error(request, "Não foi possível cadastrar: verifique os campos informados.")
        return redirect(reverse_lazy('settings_integrations'))


class SearchProviderConfigUpdateView(LoginRequiredMixin, View):
    """POST /settings/search-config/<pk>/update/ — edita uma configuração de busca existente."""

    def post(self, request, pk):
        _require_settings_admin(request)
        config = get_object_or_404(SearchProviderConfig, pk=pk)
        old_api_key = config.api_key
        form = SearchProviderConfigForm(request.POST, instance=config)
        if form.is_valid():
            updated = form.save(commit=False)
            if not (request.POST.get('api_key') or '').strip():
                updated.api_key = old_api_key
            updated.save()
            messages.success(request, f'Configuração de busca "{updated.name}" atualizada com sucesso!')
        else:
            messages.error(request, "Não foi possível salvar: verifique os campos informados.")
        return redirect(reverse_lazy('settings_integrations'))


class SearchProviderConfigDeleteView(LoginRequiredMixin, View):
    """POST /settings/search-config/<pk>/delete/ — remove uma configuração de busca da lista."""

    def post(self, request, pk):
        _require_settings_admin(request)
        config = get_object_or_404(SearchProviderConfig, pk=pk)
        was_active = config.is_active
        name = config.name
        config.delete()
        if was_active:
            fallback = SearchProviderConfig.objects.first()
            if fallback:
                fallback.is_active = True
                fallback.save(update_fields=['is_active'])
        messages.success(request, f'Configuração de busca "{name}" removida.')
        return redirect(reverse_lazy('settings_integrations'))


class SearchProviderConfigActivateView(LoginRequiredMixin, View):
    """POST /settings/search-config/<pk>/activate/ — marca esta configuração como a ativa."""

    def post(self, request, pk):
        _require_settings_admin(request)
        config = get_object_or_404(SearchProviderConfig, pk=pk)
        config.is_active = True
        config.save()
        return JsonResponse({"ok": True, "active_id": config.id})


class SearchProviderConfigRevealView(LoginRequiredMixin, View):
    """GET /settings/search-config/<pk>/reveal/ — retorna a chave de API completa.
    Restrito a Super Admin."""

    def get(self, request, pk):
        profile = getattr(request.user, 'profile', None)
        if not profile or profile.role != 'super_admin':
            return JsonResponse({"ok": False, "error": "Apenas Super Admin pode visualizar a chave completa."}, status=403)
        config = get_object_or_404(SearchProviderConfig, pk=pk)
        resp = JsonResponse({"ok": True, "api_key": config.api_key})
        resp['Cache-Control'] = 'no-store'
        return resp


class VoiceProviderConfigCreateView(LoginRequiredMixin, View):
    """POST /settings/voice-config/create/ — cadastra uma nova configuração de voz na lista."""

    def post(self, request):
        _require_settings_admin(request)
        form = VoiceProviderConfigForm(request.POST)
        if form.is_valid():
            config = form.save(commit=False)
            if not VoiceProviderConfig.objects.exists():
                config.is_active = True
            config.save()
            messages.success(request, f'Configuração de voz "{config.name}" cadastrada com sucesso!')
        else:
            messages.error(request, "Não foi possível cadastrar: verifique os campos informados.")
        return redirect(reverse_lazy('settings_integrations'))


class VoiceProviderConfigUpdateView(LoginRequiredMixin, View):
    """POST /settings/voice-config/<pk>/update/ — edita uma configuração de voz existente."""

    def post(self, request, pk):
        _require_settings_admin(request)
        config = get_object_or_404(VoiceProviderConfig, pk=pk)
        old_api_key = config.api_key
        form = VoiceProviderConfigForm(request.POST, instance=config)
        if form.is_valid():
            updated = form.save(commit=False)
            if not (request.POST.get('api_key') or '').strip():
                updated.api_key = old_api_key
            updated.save()
            messages.success(request, f'Configuração de voz "{updated.name}" atualizada com sucesso!')
        else:
            messages.error(request, "Não foi possível salvar: verifique os campos informados.")
        return redirect(reverse_lazy('settings_integrations'))


class VoiceProviderConfigDeleteView(LoginRequiredMixin, View):
    """POST /settings/voice-config/<pk>/delete/ — remove uma configuração de voz da lista."""

    def post(self, request, pk):
        _require_settings_admin(request)
        config = get_object_or_404(VoiceProviderConfig, pk=pk)
        was_active = config.is_active
        name = config.name
        config.delete()
        if was_active:
            fallback = VoiceProviderConfig.objects.first()
            if fallback:
                fallback.is_active = True
                fallback.save(update_fields=['is_active'])
        messages.success(request, f'Configuração de voz "{name}" removida.')
        return redirect(reverse_lazy('settings_integrations'))


class VoiceProviderConfigActivateView(LoginRequiredMixin, View):
    """POST /settings/voice-config/<pk>/activate/ — marca esta configuração como a ativa."""

    def post(self, request, pk):
        _require_settings_admin(request)
        config = get_object_or_404(VoiceProviderConfig, pk=pk)
        config.is_active = True
        config.save()
        return JsonResponse({"ok": True, "active_id": config.id})


class VoiceProviderConfigRevealView(LoginRequiredMixin, View):
    """GET /settings/voice-config/<pk>/reveal/ — retorna a chave de API completa.
    Restrito a Super Admin."""

    def get(self, request, pk):
        profile = getattr(request.user, 'profile', None)
        if not profile or profile.role != 'super_admin':
            return JsonResponse({"ok": False, "error": "Apenas Super Admin pode visualizar a chave completa."}, status=403)
        config = get_object_or_404(VoiceProviderConfig, pk=pk)
        resp = JsonResponse({"ok": True, "api_key": config.api_key})
        resp['Cache-Control'] = 'no-store'
        return resp


class SearchIntegrationTestView(LoginRequiredMixin, View):
    """POST /settings/search-integration/test/ — testa a busca (Google ou Tavily,
    conforme o provedor informado) com a chave/engine informados (permite testar
    antes de salvar)."""

    def post(self, request):
        _require_settings_admin(request)
        try:
            body = json.loads(request.body)
        except Exception:
            body = {}

        provider = (body.get('provider') or 'google').strip()
        google_api_key = (body.get('google_api_key') or '').strip() or None
        engine_id = (body.get('engine_id') or '').strip() or None
        tavily_api_key = (body.get('tavily_api_key') or '').strip() or None

        from .ai_tools import _web_search
        try:
            items = _web_search(
                "JumperFour OS teste de busca", num=1, provider=provider,
                google_api_key=google_api_key, google_engine_id=engine_id, tavily_api_key=tavily_api_key,
            )
            if items:
                return JsonResponse({"ok": True, "message": f"Encontrado: {items[0].get('title', '')}"})
            return JsonResponse({"ok": True, "message": "Conexão estabelecida, mas sem resultados para essa consulta de teste."})
        except ValueError as e:
            return JsonResponse({"ok": False, "error": str(e)})
        except Exception as e:
            return JsonResponse({"ok": False, "error": str(e)})


class TTSIntegrationTestView(LoginRequiredMixin, View):
    """POST /settings/tts-integration/test/ — sintetiza uma frase de teste com a chave
    do provedor informado (Google Cloud TTS ou ElevenLabs — permite testar antes de
    salvar, e ouvir a qualidade da voz na hora). Retorna o áudio (MP3) direto em caso
    de sucesso, ou JSON de erro em caso de falha."""

    def post(self, request):
        _require_settings_admin(request)
        try:
            body = json.loads(request.body)
        except Exception:
            body = {}

        provider = (body.get('provider') or 'google').strip()
        voice_gender = (body.get('voice_gender') or 'female').strip()
        google_api_key = (body.get('google_api_key') or body.get('api_key') or '').strip() or None
        elevenlabs_api_key = (body.get('elevenlabs_api_key') or '').strip() or None
        elevenlabs_voice_id = (body.get('elevenlabs_voice_id') or '').strip() or None

        sample_text = "Olá! Esta é a voz profissional do Jota4, o assistente de IA da JumperFour OS."

        from .ai_tools import tts_synthesize
        try:
            audio_bytes = tts_synthesize(
                sample_text, voice_gender=voice_gender, provider=provider,
                google_api_key=google_api_key,
                elevenlabs_api_key=elevenlabs_api_key, elevenlabs_voice_id=elevenlabs_voice_id,
            )
            resp = HttpResponse(audio_bytes, content_type="audio/mpeg")
            resp['Cache-Control'] = 'no-store'
            return resp
        except ValueError as e:
            return JsonResponse({"ok": False, "error": str(e)})
        except Exception as e:
            return JsonResponse({"ok": False, "error": str(e)})


# Tasks (refatorado: Passagem de Turno)
@method_decorator(ensure_csrf_cookie, name='dispatch')
class TaskListView(LoginRequiredMixin, TemplateView):
    template_name = 'tasks/task_list.html'

    def _get_shift_settings(self):
        settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
        return settings_obj

    def _build_shifts(self, now):
        settings_obj = self._get_shift_settings()
        day_start = getattr(settings_obj, 'day_shift_start', None) or datetime.strptime('08:00', '%H:%M').time()
        day_end = getattr(settings_obj, 'day_shift_end', None) or datetime.strptime('20:00', '%H:%M').time()
        enable_night = bool(getattr(settings_obj, 'enable_night_shift', False))
        night_start = getattr(settings_obj, 'night_shift_start', None) or datetime.strptime('20:00', '%H:%M').time()
        night_end = getattr(settings_obj, 'night_shift_end', None) or datetime.strptime('08:00', '%H:%M').time()

        def aware(dt):
            try:
                return timezone.make_aware(dt) if timezone.is_naive(dt) else dt
            except Exception:
                return dt

        shifts = []
        today = timezone.localdate()
        # Gera uma janela de dias suficiente para montar 7 turnos
        for i in range(0, 14):
            d = today - timedelta(days=i)

            # Turno noturno (opcional)
            if enable_night:
                ns = aware(datetime.combine(d, night_start))
                # Pode cruzar meia-noite
                end_day = d if night_end >= night_start else (d + timedelta(days=1))
                ne = aware(datetime.combine(end_day, night_end))
                if ns <= now:
                    shifts.append({'date': d, 'type': 'night', 'start': ns, 'end': ne})

            # Turno diurno (padrão)
            ds = aware(datetime.combine(d, day_start))
            de = aware(datetime.combine(d, day_end))
            if ds <= now:
                shifts.append({'date': d, 'type': 'day', 'start': ds, 'end': de})

            if len(shifts) >= 7:
                break

        # Marca o turno atual (start <= now < end)
        for sh in shifts:
            sh['is_current'] = bool(sh['start'] <= now < sh['end'])

        # Mantém o turno atual sempre como primeiro destaque
        shifts.sort(key=lambda x: (1 if x.get('is_current') else 0, x['start']), reverse=True)
        return shifts[:7], settings_obj

    def _build_shifts_for_range(self, now, date_start, date_end_exclusive):
        """
        Monta turnos entre datas (date_start <= dia < date_end_exclusive).
        Retorna (shifts, settings_obj) sem limitar quantidade (paginação é feita depois).
        """
        settings_obj = self._get_shift_settings()
        day_start = getattr(settings_obj, 'day_shift_start', None) or datetime.strptime('08:00', '%H:%M').time()
        day_end = getattr(settings_obj, 'day_shift_end', None) or datetime.strptime('20:00', '%H:%M').time()
        enable_night = bool(getattr(settings_obj, 'enable_night_shift', False))
        night_start = getattr(settings_obj, 'night_shift_start', None) or datetime.strptime('20:00', '%H:%M').time()
        night_end = getattr(settings_obj, 'night_shift_end', None) or datetime.strptime('08:00', '%H:%M').time()

        def aware(dt):
            try:
                return timezone.make_aware(dt) if timezone.is_naive(dt) else dt
            except Exception:
                return dt

        shifts = []
        d = date_start
        while d < date_end_exclusive:
            # Noturno
            if enable_night:
                ns = aware(datetime.combine(d, night_start))
                end_day = d if night_end >= night_start else (d + timedelta(days=1))
                ne = aware(datetime.combine(end_day, night_end))
                shifts.append({'date': d, 'type': 'night', 'start': ns, 'end': ne})

            # Diurno
            ds = aware(datetime.combine(d, day_start))
            de = aware(datetime.combine(d, day_end))
            shifts.append({'date': d, 'type': 'day', 'start': ds, 'end': de})

            d = d + timedelta(days=1)

        for sh in shifts:
            sh['is_current'] = bool(sh['start'] <= now < sh['end'])

        shifts.sort(key=lambda x: (1 if x.get('is_current') else 0, x['start']), reverse=True)
        return shifts, settings_obj

    def _status_dot(self, ticket, ref_now):
        try:
            status = (ticket.status or '').strip()
            deadline = getattr(ticket, 'deadline', None)
            if deadline and deadline < ref_now and status in {'open', 'in_progress'}:
                return 'dot-delayed'
            return {
                'finished': 'dot-finished',
                'pending': 'dot-pending',
                'in_progress': 'dot-in-progress',
                'canceled': 'dot-canceled',
                'open': 'dot-open',
            }.get(status, 'dot-open')
        except Exception:
            return 'dot-open'

    def _status_emoji(self, ticket, ref_now):
        """
        Emoji para exibição rápida no post-it.
        """
        try:
            status = (ticket.status or '').strip()
            deadline = getattr(ticket, 'deadline', None)
            if deadline and deadline < ref_now and status in {'open', 'in_progress'}:
                return '🔴'
            return {
                'finished': '🟢',
                'pending': '🟣',
                'in_progress': '🔵',
                'canceled': '⚫',
                'open': '🟡',
            }.get(status, '🟡')
        except Exception:
            return '🟡'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.localtime(timezone.now())

        # Filtros de histórico (dia/semana/mês/ano) com paginação
        period = (self.request.GET.get('period') or 'recent').strip()
        page = self.request.GET.get('page') or '1'
        try:
            page = max(int(page), 1)
        except Exception:
            page = 1
        per_page = 30

        today = timezone.localdate()
        range_label = "Últimos 7 turnos"

        shifts = []
        settings_obj = None

        if period == 'week':
            # input type="week" → YYYY-Www
            week_val = (self.request.GET.get('week') or '').strip()
            if not week_val:
                iso = today.isocalendar()
                week_val = f"{iso.year}-W{iso.week:02d}"
            try:
                year_str, w_str = week_val.split('-W')
                y = int(year_str)
                w = int(w_str)
                start_date = datetime.fromisocalendar(y, w, 1).date()
                end_date = start_date + timedelta(days=7)
            except Exception:
                start_date = today - timedelta(days=today.weekday())
                end_date = start_date + timedelta(days=7)
                iso = start_date.isocalendar()
                week_val = f"{iso.year}-W{iso.week:02d}"

            shifts, settings_obj = self._build_shifts_for_range(now, start_date, end_date)
            range_label = f"Semana {week_val}"
            context['current_week'] = week_val

        elif period in {'month', 'year'}:
            # Mês: YYYY-MM (input type="month")
            # Ano: usuário escolhe ano e mês (select)
            if period == 'month':
                month_val = (self.request.GET.get('month') or '').strip()
                if not month_val:
                    month_val = f"{today.year:04d}-{today.month:02d}"
                try:
                    y, m = month_val.split('-')
                    y = int(y)
                    m = int(m)
                except Exception:
                    y, m = today.year, today.month
                    month_val = f"{y:04d}-{m:02d}"
                context['current_month'] = month_val
            else:
                y = self.request.GET.get('year') or str(today.year)
                m = self.request.GET.get('month_num') or f"{today.month:02d}"
                try:
                    y = int(y)
                    m = int(m)
                except Exception:
                    y, m = today.year, today.month
                context['current_year'] = str(y)
                context['current_month_num'] = f"{m:02d}"
                month_val = f"{y:04d}-{m:02d}"

            # semana do mês (1-5) opcional
            week_in_month = (self.request.GET.get('week_in_month') or '').strip()
            try:
                import calendar
                last_day = calendar.monthrange(y, m)[1]
            except Exception:
                last_day = 31

            start_day = 1
            end_day = last_day
            if week_in_month and week_in_month.isdigit():
                wim = int(week_in_month)
                if 1 <= wim <= 5:
                    start_day = (wim - 1) * 7 + 1
                    end_day = min(wim * 7, last_day)
                    context['current_week_in_month'] = str(wim)
            else:
                context['current_week_in_month'] = ''

            start_date = datetime(y, m, start_day).date()
            end_date = datetime(y, m, end_day).date() + timedelta(days=1)

            shifts, settings_obj = self._build_shifts_for_range(now, start_date, end_date)
            if period == 'month':
                range_label = f"Mês {month_val}" + (f" (semana {context['current_week_in_month']})" if context.get('current_week_in_month') else "")
            else:
                range_label = f"Ano {y} - {month_val}"

        else:
            period = 'recent'
            shifts, settings_obj = self._build_shifts(now)

        # Paginação (máximo 30 post-its por página)
        total = len(shifts)
        total_pages = max((total + per_page - 1) // per_page, 1)
        if page > total_pages:
            page = total_pages
        start_i = (page - 1) * per_page
        end_i = start_i + per_page
        shifts_page = shifts[start_i:end_i]

        context['handover_period'] = period
        context['handover_range_label'] = range_label
        context['handover_page'] = page
        context['handover_total_pages'] = total_pages
        context['handover_total'] = total

        # choices para ano/mês
        context['year_choices'] = [str(today.year - i) for i in range(0, 6)]
        context['month_choices'] = [
            ('01', 'Jan'), ('02', 'Fev'), ('03', 'Mar'), ('04', 'Abr'),
            ('05', 'Mai'), ('06', 'Jun'), ('07', 'Jul'), ('08', 'Ago'),
            ('09', 'Set'), ('10', 'Out'), ('11', 'Nov'), ('12', 'Dez'),
        ]

        weekday_pt = {
            0: 'Segunda',
            1: 'Terça',
            2: 'Quarta',
            3: 'Quinta',
            4: 'Sexta',
            5: 'Sábado',
            6: 'Domingo',
        }

        context['handover_user_choices'] = (
            User.objects.filter(is_active=True)
            .select_related('profile')
            .order_by('first_name', 'last_name', 'username')
        )

        # Prefetch leve para exibir lista
        data = []
        for sh in shifts_page:
            handover, _ = ShiftHandover.objects.get_or_create(shift_date=sh['date'], shift_type=sh['type'])

            shift_end_ref = min(sh['end'], now) if sh['start'] <= now else sh['end']

            tickets_created = (
                Ticket.objects
                .select_related('client', 'hub')
                .prefetch_related('systems', 'technicians')
                .filter(created_at__gte=sh['start'], created_at__lt=sh['end'])
                .order_by('-created_at')
            )[:30]

            pendencias = (
                Ticket.objects
                .select_related('client', 'hub')
                .prefetch_related('systems', 'technicians')
                .exclude(status__in=['finished', 'canceled'])
                .filter(created_at__lte=sh['end'])
                .filter(Q(deadline__lt=sh['end']) | Q(status__in=['pending', 'in_progress', 'open']))
                .order_by('deadline', '-updated_at')
            )[:30]

            def serialize_ticket(t):
                return {
                    'id': t.id,
                    'formatted_id': t.formatted_id,
                    'leankeep_id': (t.leankeep_id or '').strip() or '-',
                    'client_name': getattr(getattr(t, 'client', None), 'name', '') or '',
                    'status_dot': self._status_dot(t, shift_end_ref),
                    'status_emoji': self._status_emoji(t, shift_end_ref),
                    'preview_url': reverse('ticket_mini_preview', kwargs={'pk': t.id}),
                }

            # Prefetch alertas (para destinatário e para o criador acompanhar baixas)
            user_alerts = list(
                handover.entries
                .prefetch_related(
                    Prefetch(
                        'alerts',
                        queryset=ShiftHandoverEntryAlert.objects.select_related('target_user').all(),
                        to_attr='alerts_all'
                    ),
                    Prefetch(
                        'alerts',
                        queryset=ShiftHandoverEntryAlert.objects.filter(target_user=self.request.user),
                        to_attr='alerts_for_user'
                    )
                )
                .select_related('created_by', 'parent')
                .all()
            )

            entry_tree = build_handover_entry_tree(user_alerts)

            data.append({
                'handover': handover,
                'shift': sh,
                'weekday_label': weekday_pt.get(sh['date'].weekday(), ''),
                'title_date': sh['date'],
                'shift_label': 'Diurno' if sh['type'] == 'day' else 'Noturno',
                'is_current': bool(sh.get('is_current')),
                'tickets_created': [serialize_ticket(t) for t in tickets_created],
                'pendencias': [serialize_ticket(t) for t in pendencias],
                'entries_data': [build_handover_entry_data(e, self.request.user) for e in entry_tree],
            })

        context['handover_cards'] = data
        context['handover_settings'] = settings_obj
        return context


def build_handover_entry_data(entry, user):
    """
    Monta o payload usado no template para:
    - Destinatário: destacar/pulsar + dar baixa + prioridade
    - Criador: mostrar confirmação de leitura (todos deram baixa / X de Y)
    """
    alerts_for_user = getattr(entry, 'alerts_for_user', None)
    if alerts_for_user is None:
        alerts_for_user = list(entry.alerts.filter(target_user=user))

    alerts_all = getattr(entry, 'alerts_all', None)
    if alerts_all is None:
        alerts_all = list(entry.alerts.select_related('target_user').all())

    has_alert = bool(alerts_for_user)
    has_pending_alert = any(a.acknowledged_at is None for a in alerts_for_user)
    has_ack_alert = any(a.acknowledged_at is not None for a in alerts_for_user)
    priority = (alerts_for_user[0].priority if alerts_for_user else None)

    recipients = ''
    priority_code = None
    if alerts_all:
        try:
            recipients = ', '.join(
                [((a.target_user.get_full_name() or a.target_user.username) if getattr(a, 'target_user', None) else '') for a in alerts_all]
            ).strip(', ').strip()
        except Exception:
            recipients = ''
        pr_order = {'high': 3, 'medium': 2, 'low': 1}
        try:
            priority_code = sorted(
                [a.priority for a in alerts_all if getattr(a, 'priority', None)],
                key=lambda p: pr_order.get(p, 0),
                reverse=True
            )[0]
        except Exception:
            priority_code = None

    priority_label = {'high': 'Alta', 'medium': 'Média', 'low': 'Baixa'}.get(priority_code) if priority_code else None

    creator_total = 0
    creator_ack_count = 0
    creator_all_ack = False
    if entry.created_by_id == user.id and alerts_all:
        creator_total = len(alerts_all)
        creator_ack_count = sum(1 for a in alerts_all if a.acknowledged_at is not None)
        creator_all_ack = (creator_total > 0 and creator_ack_count == creator_total)

    replies = getattr(entry, 'replies_prefetched', []) or []
    replies_data = []
    reply_count = 0
    for reply in replies:
        reply_payload = build_handover_entry_data(reply, user)
        replies_data.append(reply_payload)
        reply_count += 1 + int(reply_payload.get('reply_count', 0) or 0)

    return {
        'obj': entry,
        'has_alert': has_alert,
        'has_pending_alert': has_pending_alert,
        'has_ack_alert': has_ack_alert,
        'priority': priority,
        'creator_total': creator_total,
        'creator_ack_count': creator_ack_count,
        'creator_all_ack': creator_all_ack,
        'recipients': recipients,
        'priority_code': priority_code,
        'priority_label': priority_label,
        'replies_data': replies_data,
        'reply_count': reply_count,
        'has_replies': reply_count > 0,
        'is_reply': bool(entry.parent_id),
        'parent_id': entry.parent_id,
        'ticket_id': entry.ticket_id,
        'ticket_formatted_id': entry.ticket.formatted_id if getattr(entry, 'ticket_id', None) and getattr(entry, 'ticket', None) else None,
        'ticket_url': reverse('ticket_list') + f'?period=all&open={entry.ticket_id}' if entry.ticket_id else None,
    }


def build_handover_entry_tree(entries):
    """
    Organiza entradas/respostas em árvore:
    - raízes mais novas primeiro
    - respostas em ordem cronológica
    """
    children_map = defaultdict(list)
    ordered = sorted(entries, key=lambda e: (e.created_at, e.id))
    for e in ordered:
        children_map[getattr(e, 'parent_id', None)].append(e)

    def attach(node):
        node.replies_prefetched = [attach(child) for child in children_map.get(node.id, [])]
        return node

    roots = list(children_map.get(None, []))
    roots.sort(key=lambda e: (e.created_at, e.id), reverse=True)
    return [attach(root) for root in roots]


def render_handover_entry_html(entry, request):
    entry_data = build_handover_entry_data(entry, request.user)
    return render_to_string(
        'tasks/_handover_entry.html',
        {'entry': entry, 'entry_data': entry_data, 'request': request},
        request=request
    )


class ShiftHandoverEntryCreateView(LoginRequiredMixin, View):
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        handover_id = request.POST.get('handover_id')
        parent_id = request.POST.get('parent_id')
        text = (request.POST.get('text') or '').strip()
        if parent_id and not str(parent_id).isdigit():
            return JsonResponse({'status': 'error', 'message': 'Registro pai inválido.'}, status=400)
        if not handover_id and not parent_id:
            return JsonResponse({'status': 'error', 'message': 'Turno inválido.'}, status=400)
        if not text:
            return JsonResponse({'status': 'error', 'message': 'Digite uma anotação.'}, status=400)
        if len(text) > 4000:
            return JsonResponse({'status': 'error', 'message': 'Texto muito longo.'}, status=400)

        parent = None
        if parent_id:
            parent = get_object_or_404(ShiftHandoverEntry.objects.select_related('handover'), pk=int(parent_id))
            handover = parent.handover
        else:
            handover = get_object_or_404(ShiftHandover, pk=int(handover_id))

        # Criar apenas anotação, sem gerar ticket automaticamente
        # As OS devem ser criadas exclusivamente na tela de "Ordens de Serviço"
        entry = ShiftHandoverEntry.objects.create(
            handover=handover,
            parent=parent,
            created_by=request.user,
            text=text,
            ticket=None,
        )
        entry = ShiftHandoverEntry.objects.filter(pk=entry.pk).prefetch_related(
            Prefetch('alerts', queryset=ShiftHandoverEntryAlert.objects.select_related('target_user').all(), to_attr='alerts_all'),
            Prefetch('alerts', queryset=ShiftHandoverEntryAlert.objects.filter(target_user=request.user), to_attr='alerts_for_user'),
        ).select_related('created_by', 'parent').first() or entry
        html = render_handover_entry_html(entry, request)
        return JsonResponse({
            'status': 'success',
            'html': html,
            'is_reply': bool(parent),
            'parent_id': parent.id if parent else None,
            'entry_id': entry.id,
        })


class ShiftHandoverEntryDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        entry = get_object_or_404(ShiftHandoverEntry.objects.select_related('ticket'), pk=pk)
        role = getattr(getattr(request.user, 'profile', None), 'role', None)
        can_delete = bool(role in ['admin', 'super_admin'] or entry.created_by_id == request.user.id)
        if not can_delete:
            return JsonResponse({'status': 'error', 'message': 'Sem permissão para excluir.'}, status=403)
        parent_id = entry.parent_id
        ticket_id = None
        ticket_formatted_id = None
        if entry.ticket_id:
            ticket_id = entry.ticket_id
            ticket_formatted_id = entry.ticket.formatted_id
            entry.ticket.delete()
        entry.delete()
        return JsonResponse({
            'status': 'success',
            'parent_id': parent_id,
            'ticket_deleted': bool(ticket_id),
            'ticket_formatted_id': ticket_formatted_id,
        })


class ShiftHandoverEntryEditView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        entry = get_object_or_404(ShiftHandoverEntry, pk=pk)
        role = getattr(getattr(request.user, 'profile', None), 'role', None)
        can_edit = bool(role in ['admin', 'super_admin'] or entry.created_by_id == request.user.id)
        if not can_edit:
            return JsonResponse({'status': 'error', 'message': 'Sem permissão para editar.'}, status=403)

        text = (request.POST.get('text') or '').strip()
        if not text:
            return JsonResponse({'status': 'error', 'message': 'Digite uma anotação.'}, status=400)
        if len(text) > 4000:
            return JsonResponse({'status': 'error', 'message': 'Texto muito longo.'}, status=400)

        entry.text = text
        entry.save(update_fields=['text'])
        # mantém o estado de alerta para o usuário atual
        entry = ShiftHandoverEntry.objects.filter(pk=entry.pk).prefetch_related(
            Prefetch('alerts', queryset=ShiftHandoverEntryAlert.objects.select_related('target_user').all(), to_attr='alerts_all'),
            Prefetch('alerts', queryset=ShiftHandoverEntryAlert.objects.filter(target_user=request.user), to_attr='alerts_for_user'),
        ).select_related('created_by', 'parent').first() or entry
        html = render_handover_entry_html(entry, request)
        return JsonResponse({'status': 'success', 'html': html, 'parent_id': entry.parent_id})


class ShiftHandoverUsersView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        users = (
            User.objects.filter(is_active=True)
            .select_related('profile')
            .order_by('first_name', 'username')
        )
        data = []
        for u in users:
            name = (u.get_full_name() or u.username or '').strip()
            data.append({'id': u.id, 'name': name})
        return JsonResponse({'status': 'success', 'users': data})


class ShiftHandoverEntryNotifyView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        entry = get_object_or_404(ShiftHandoverEntry, pk=pk)
        priority = (request.POST.get('priority') or 'medium').strip()
        if priority not in {'high', 'medium', 'low'}:
            priority = 'medium'
        raw_ids = request.POST.getlist('user_ids[]') or request.POST.getlist('user_ids') or []
        # aceita "1,2,3"
        if len(raw_ids) == 1 and isinstance(raw_ids[0], str) and ',' in raw_ids[0]:
            raw_ids = [x.strip() for x in raw_ids[0].split(',') if x.strip()]

        user_ids = []
        for x in raw_ids:
            if str(x).isdigit():
                user_ids.append(int(x))
        user_ids = list(dict.fromkeys(user_ids))  # uniq mantendo ordem

        if not user_ids:
            return JsonResponse({'status': 'error', 'message': 'Selecione ao menos um usuário.'}, status=400)

        # cria/reativa alertas
        for uid in user_ids:
            target = User.objects.filter(pk=uid, is_active=True).first()
            if not target:
                continue
            alert, created = ShiftHandoverEntryAlert.objects.get_or_create(
                entry=entry,
                target_user=target,
                defaults={'created_by': request.user, 'priority': priority}
            )
            if not created:
                # reativa (volta a pendente)
                alert.acknowledged_at = None
                if not alert.created_by_id:
                    alert.created_by = request.user
                alert.priority = priority
                alert.save(update_fields=['acknowledged_at', 'created_by', 'priority'])

        # Retorna HTML do item (sem highlight para quem está notificando, a menos que ele também seja alvo)
        entry = ShiftHandoverEntry.objects.filter(pk=entry.pk).prefetch_related(
            Prefetch('alerts', queryset=ShiftHandoverEntryAlert.objects.select_related('target_user').all(), to_attr='alerts_all'),
            Prefetch('alerts', queryset=ShiftHandoverEntryAlert.objects.filter(target_user=request.user), to_attr='alerts_for_user'),
        ).select_related('created_by').first() or entry
        html = render_handover_entry_html(entry, request)
        return JsonResponse({'status': 'success', 'html': html})


class ShiftHandoverEntryAcknowledgeView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        entry = get_object_or_404(ShiftHandoverEntry, pk=pk)
        now = timezone.now()
        qs = ShiftHandoverEntryAlert.objects.filter(
            entry=entry,
            target_user=request.user,
            acknowledged_at__isnull=True
        )
        updated = qs.update(acknowledged_at=now)
        if not updated:
            return JsonResponse({'status': 'error', 'message': 'Nada para dar baixa.'}, status=400)

        # Notifica o remetente (comprovação)
        try:
            alert_obj = qs.select_related('created_by').first()
            sender = getattr(alert_obj, 'created_by', None)
            if sender and sender.id != request.user.id:
                Notification.objects.create(
                    recipient=sender,
                    sender=request.user,
                    title='Lembrete de turno lido',
                    message=f"O usuário {request.user.get_full_name() or request.user.username} deu baixa no lembrete: \"{(entry.text or '')[:200]}\"",
                    notification_type='message'
                )
        except Exception:
            pass

        # Retorna HTML já com estado atualizado para o usuário atual
        entry = ShiftHandoverEntry.objects.filter(pk=entry.pk).prefetch_related(
            Prefetch('alerts', queryset=ShiftHandoverEntryAlert.objects.select_related('target_user').all(), to_attr='alerts_all'),
            Prefetch('alerts', queryset=ShiftHandoverEntryAlert.objects.filter(target_user=request.user), to_attr='alerts_for_user'),
        ).select_related('created_by').first() or entry
        html = render_handover_entry_html(entry, request)
        return JsonResponse({'status': 'success', 'html': html})


class ShiftHandoverPendingAlertsView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        qs = ShiftHandoverEntryAlert.objects.filter(target_user=request.user, acknowledged_at__isnull=True).select_related('entry', 'entry__handover')
        count = qs.count()
        # retorna poucos itens para o toast
        items = []
        for a in qs.order_by('-created_at')[:5]:
            items.append({
                'entry_id': a.entry_id,
                'handover_id': a.entry.handover_id,
                'text': (a.entry.text or '')[:120],
            })
        return JsonResponse({'status': 'success', 'count': count, 'items': items})

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

class UserAccessUpdateView(AdminRequiredMixin, View):
    def post(self, request, pk):
        target_user = get_object_or_404(User, pk=pk)
        if request.user.id == target_user.id:
            messages.error(request, "Você não pode bloquear/desbloquear o seu próprio acesso.")
            return redirect(request.META.get('HTTP_REFERER', reverse_lazy('user_list')))

        action = (request.POST.get('action') or '').strip()
        reason = (request.POST.get('reason') or '').strip() or None
        profile = getattr(target_user, 'profile', None)
        if not profile:
            profile = UserProfile.objects.create(user=target_user)

        now = timezone.now()
        blocked_until = None
        blocked_reason = None

        if action == 'unblock':
            target_user.is_active = True
            target_user.save(update_fields=['is_active'])
            profile.blocked_until = None
            profile.blocked_reason = None
            profile.save(update_fields=['blocked_until', 'blocked_reason'])
            messages.success(request, f"Acesso liberado: {target_user.get_full_name() or target_user.username}")
            return redirect(request.META.get('HTTP_REFERER', reverse_lazy('user_list')))

        if action == 'block_1h':
            blocked_until = now + timedelta(hours=1)
            blocked_reason = "Bloqueio temporário (1h)"
        elif action == 'block_1d':
            blocked_until = now + timedelta(days=1)
            blocked_reason = "Bloqueio temporário (24h)"
        elif action == 'block':
            blocked_until = None
            blocked_reason = "Bloqueio"
        else:
            messages.error(request, "Ação inválida.")
            return redirect(request.META.get('HTTP_REFERER', reverse_lazy('user_list')))

        if reason:
            blocked_reason = f"{blocked_reason} - {reason}"

        target_user.is_active = False
        target_user.save(update_fields=['is_active'])
        profile.blocked_until = blocked_until
        profile.blocked_reason = blocked_reason
        profile.save(update_fields=['blocked_until', 'blocked_reason'])

        messages.success(request, f"Acesso bloqueado: {target_user.get_full_name() or target_user.username}")
        return redirect(request.META.get('HTTP_REFERER', reverse_lazy('user_list')))


class PermissionsView(AdminRequiredMixin, TemplateView):
    template_name = 'tickets/permissions.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Permissões"

        try:
            roles = RoleLevel.objects.filter(is_active=True).order_by('name')
            pages = AppPage.objects.all().order_by('group', 'order', 'name')
        except (OperationalError, ProgrammingError):
            context['db_missing'] = True
            context['roles'] = []
            context['groups'] = []
            context['pdf_user_rows'] = []
            return context

        perms = RolePagePermission.objects.filter(role__in=roles, page__in=pages)
        perm_map = {}
        for p in perms:
            perm_map[(p.role_id, p.page_id)] = p.allowed

        groups = []
        by_group = {}
        for page in pages:
            group_name = page.group or "Geral"
            by_group.setdefault(group_name, []).append(page)

        for group_name, group_pages in by_group.items():
            group_rows = []
            for page in group_pages:
                allowed_by_role = []
                for role in roles:
                    allowed_by_role.append({
                        'role': role,
                        'allowed': perm_map.get((role.id, page.id), True),
                    })
                group_rows.append({
                    'page': page,
                    'allowed_by_role': allowed_by_role,
                })
            groups.append({
                'name': group_name,
                'rows': group_rows,
            })

        context['roles'] = roles
        context['groups'] = groups
        try:
            # Super Admin nunca aparece nesta tabela — o nível tem acesso global
            # e não pode ser restringido por este formulário em massa.
            users = User.objects.select_related('profile').all().exclude(profile__role='super_admin').order_by('first_name', 'username')
            pdf_user_rows = []
            for u in users:
                # Garante que o profile existe
                profile = getattr(u, 'profile', None)
                if not profile:
                    profile = UserProfile.objects.create(user=u)

                pdf_user_rows.append({
                    'user': u,
                    'allowed': getattr(profile, 'allow_pdf_reports', True),
                    'can_view_tickets': getattr(profile, 'can_view_tickets', True),
                    'can_create_tickets': getattr(profile, 'can_create_tickets', True),
                    'can_edit_tickets': getattr(profile, 'can_edit_tickets', True),
                    'can_delete_tickets': getattr(profile, 'can_delete_tickets', True),
                    'can_view_checklists': getattr(profile, 'can_view_checklists', True),
                    'can_create_checklists': getattr(profile, 'can_create_checklists', True),
                    'can_view_reports': getattr(profile, 'can_view_reports', True),
                    'ai_chat_enabled': getattr(profile, 'ai_chat_enabled', True),
                })
            context['pdf_user_rows'] = pdf_user_rows
        except (OperationalError, ProgrammingError):
            context['pdf_user_rows'] = []
        except Exception:
            context['pdf_user_rows'] = []
        return context

    def post(self, request, *args, **kwargs):
        try:
            RoleLevel.objects.exists()
        except (OperationalError, ProgrammingError):
            messages.error(request, "Permissões ainda não foram inicializadas no banco. Rode: python manage.py migrate")
            return redirect('settings')

        action = request.POST.get('action')

        if action == 'create_role':
            name = (request.POST.get('role_name') or '').strip()
            code = (request.POST.get('role_code') or '').strip()
            if not code and name:
                code = slugify(name)

            if not name or not code:
                messages.error(request, "Informe o nome e o código do nível de usuário.")
                return redirect('permissions')

            try:
                _, created = RoleLevel.objects.update_or_create(
                    code=code,
                    defaults={'name': name, 'is_system': False, 'is_active': True},
                )
            except Exception:
                messages.error(request, "Não foi possível salvar o nível de usuário.")
                return redirect('permissions')

            if created:
                messages.success(request, f"Nível criado: {name} ({code}).")
            else:
                messages.success(request, f"Nível atualizado: {name} ({code}).")
            return redirect('permissions')

        if action == 'create_page':
            name = (request.POST.get('page_name') or '').strip()
            url_name = (request.POST.get('page_url_name') or '').strip()
            code = (request.POST.get('page_code') or '').strip()
            group = (request.POST.get('page_group') or '').strip() or None

            if not code and name:
                code = slugify(name)

            if not name or not url_name or not code:
                messages.error(request, "Informe nome, url_name e código da página.")
                return redirect('permissions')

            try:
                _, created = AppPage.objects.update_or_create(
                    url_name=url_name,
                    defaults={
                        'code': code,
                        'name': name,
                        'group': group,
                        'is_enabled': True,
                    },
                )
            except Exception:
                messages.error(request, "Não foi possível salvar a página.")
                return redirect('permissions')

            if created:
                messages.success(request, f"Página criada: {name} ({url_name}).")
            else:
                messages.success(request, f"Página atualizada: {name} ({url_name}).")
            return redirect('permissions')

        if action == 'save_user_pdf':
            try:
                # Super Admin nunca pode ser restringido por este formulário em massa
                users = list(User.objects.select_related('profile').all().exclude(profile__role='super_admin'))
            except Exception:
                messages.error(request, "Não foi possível carregar usuários.")
                return redirect('permissions')

            changed = 0
            try:
                with transaction.atomic():
                    for u in users:
                        allowed = request.POST.get(f'user_pdf_{u.id}') == 'on'
                        profile = getattr(u, 'profile', None)
                        if not profile:
                            profile = UserProfile.objects.create(user=u)
                        current = getattr(profile, 'allow_pdf_reports', True)
                        if current != allowed:
                            profile.allow_pdf_reports = allowed
                            profile.save(update_fields=['allow_pdf_reports'])
                            changed += 1
            except Exception:
                messages.error(request, "Erro ao salvar permissões de PDF por usuário.")
                return redirect('permissions')

            if changed == 0:
                messages.info(request, "Nenhuma alteração de PDF por usuário para salvar.")
            else:
                messages.success(request, f"Permissões de PDF por usuário salvas! Alterações: {changed}.")
            return redirect('permissions')

        if action == 'save_user_restrictions':
            try:
                # Super Admin nunca pode ser restringido por este formulário em massa —
                # o nível tem acesso global por definição em todo o sistema.
                users = list(User.objects.select_related('profile').all().exclude(profile__role='super_admin'))
            except Exception:
                messages.error(request, "Não foi possível carregar usuários.")
                return redirect('permissions')

            # IMPORTANTE: todo campo listado aqui precisa ter um checkbox correspondente
            # no template (permissions.html), senão ele é sempre lido como ausente do
            # POST e fica travado em False para todos os usuários a cada salvamento.
            restriction_fields = [
                'can_view_tickets', 'can_create_tickets', 'can_edit_tickets', 'can_delete_tickets',
                'can_view_checklists', 'can_create_checklists', 'can_view_reports',
                'allow_pdf_reports', 'ai_chat_enabled'
            ]
            changed = 0
            try:
                with transaction.atomic():
                    for u in users:
                        profile = getattr(u, 'profile', None)
                        if not profile:
                            profile = UserProfile.objects.create(user=u)

                        fields_to_update = []
                        for field in restriction_fields:
                            new_value = request.POST.get(f'{field}_{u.id}') == 'on'
                            current_value = getattr(profile, field, True)
                            if current_value != new_value:
                                setattr(profile, field, new_value)
                                fields_to_update.append(field)
                                changed += 1

                        if fields_to_update:
                            profile.save(update_fields=fields_to_update)
            except Exception as e:
                messages.error(request, f"Erro ao salvar restrições de usuário: {str(e)}")
                return redirect('permissions')

            if changed == 0:
                messages.info(request, "Nenhuma alteração de restrições para salvar.")
            else:
                messages.success(request, f"Restrições de usuário salvas! Alterações: {changed}.")
            return redirect('permissions')

        roles = list(RoleLevel.objects.filter(is_active=True).order_by('name'))
        pages = list(AppPage.objects.all().order_by('group', 'order', 'name'))

        existing_perm_map = {}
        try:
            for p in RolePagePermission.objects.filter(role__in=roles, page__in=pages):
                existing_perm_map[(p.role_id, p.page_id)] = p.allowed
        except (OperationalError, ProgrammingError):
            existing_perm_map = {}

        changed_pages = 0
        changed_perms = 0

        try:
            with transaction.atomic():
                for page in pages:
                    enabled = request.POST.get(f'page_enabled_{page.id}') == 'on'
                    if page.is_enabled != enabled:
                        page.is_enabled = enabled
                        page.save(update_fields=['is_enabled'])
                        changed_pages += 1

                for role in roles:
                    for page in pages:
                        allowed = request.POST.get(f'perm_{role.id}_{page.id}') == 'on'
                        current_allowed = existing_perm_map.get((role.id, page.id), True)
                        if current_allowed != allowed:
                            changed_perms += 1
                        RolePagePermission.objects.update_or_create(
                            role=role,
                            page=page,
                            defaults={'allowed': allowed},
                        )
        except Exception:
            messages.error(request, "Erro ao salvar permissões. Nenhuma alteração foi aplicada.")
            return redirect('permissions')

        if changed_pages == 0 and changed_perms == 0:
            messages.info(request, "Nenhuma alteração para salvar.")
        else:
            messages.success(request, f"Permissões salvas com sucesso! Páginas: {changed_pages} | Permissões: {changed_perms}.")

        return redirect('permissions')

# Notification Views
class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = 'notifications/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 20

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

@login_required
def mark_notification_read(request, pk):
    if request.method == 'POST':
        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save()
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def load_hubs(request):
    client_id = request.GET.get('client_id')
    if client_id:
        hubs = list(ClientHub.objects.filter(client_id=client_id).order_by('name').values('id', 'name'))
    else:
        hubs = []
    return JsonResponse(hubs, safe=False)

@login_required
def load_client_people(request):
    client_id = request.GET.get('client_id')
    if not client_id:
        return JsonResponse({'requesters': [], 'technicians': []})

    client = Client.objects.filter(id=client_id).first()
    if not client:
        return JsonResponse({'requesters': [], 'technicians': []})

    from .client_import import ClientImporter

    importer = ClientImporter(stdout=None)
    if getattr(client, 'contact1_name', None) or getattr(client, 'contact1_email', None):
        importer.get_or_create_contact_user(client.contact1_name, client.contact1_email, client)
    if getattr(client, 'contact2_name', None) or getattr(client, 'contact2_email', None):
        importer.get_or_create_contact_user(client.contact2_name, client.contact2_email, client)

    # Solicitante: apenas pessoas do cliente selecionado (role=operator)
    requesters_qs = (
        User.objects.filter(is_active=True, profile__fixed_client=client, profile__role='operator')
        .select_related('profile')
        .order_by('first_name', 'last_name', 'username')
    )

    # Responsável: todas as pessoas do cliente (operator) + TODOS os usuários da JumperFour (sem fixed_client, qualquer role)
    technicians_qs = (
        User.objects.filter(
            Q(is_active=True, profile__fixed_client=client, profile__role='operator')  # pessoas do cliente selecionado
            | Q(is_active=True, profile__fixed_client__isnull=True)  # TODOS os usuários da JumperFour (sem cliente fixo)
        )
        .select_related('profile')
        .distinct()
        .order_by('first_name', 'last_name', 'username')
    )

    requesters = []
    for u in requesters_qs:
        name = u.first_name.strip() if u.first_name else u.username.strip()
        if u.profile and u.profile.fixed_client:
            client_abbr = u.profile.fixed_client.name.split()[0] if ' ' in u.profile.fixed_client.name else u.profile.fixed_client.name
            label = f"[{client_abbr}] {name}"
        else:
            label = name
        requesters.append({
            'id': u.id,
            'label': label,
        })

    technicians = []
    for u in technicians_qs:
        name = u.first_name.strip() if u.first_name else u.username.strip()
        if u.profile and u.profile.fixed_client:
            client_abbr = u.profile.fixed_client.name.split()[0] if ' ' in u.profile.fixed_client.name else u.profile.fixed_client.name
            label = f"[{client_abbr}] {name}"
        else:
            label = name
        technicians.append({
            'id': u.id,
            'label': label,
        })

    return JsonResponse({'requesters': requesters, 'technicians': technicians})


@login_required
def load_os_contacts(request):
    client_id = request.GET.get("client_id")
    hub_id = request.GET.get("hub_id")

    client_ref_id = None
    hub_ref_id = None
    try:
        client_ref_id = int(client_id) if client_id else None
    except (ValueError, TypeError):
        client_ref_id = None
    try:
        hub_ref_id = int(hub_id) if hub_id else None
    except (ValueError, TypeError):
        hub_ref_id = None

    requesters = []
    if client_ref_id:
        qs = ContactClient.objects.filter(is_active=True, client_ref_id=client_ref_id)
        if hub_ref_id:
            qs = qs.filter(Q(hub_ref_id=hub_ref_id) | Q(hub_ref_id__isnull=True))
        qs = qs.order_by("hub_name", "name")
        requesters = [{"id": c.id, "label": c.display_label} for c in qs]

    responsibles_qs = ContactJumper.objects.filter(is_active=True).order_by("name")
    responsibles = [{"id": c.id, "label": c.display_label} for c in responsibles_qs]

    return JsonResponse({"requesters": requesters, "responsibles": responsibles})


@login_required
def ticket_status_html(request, pk):
    """Retorna o HTML do status de uma OS (para atualização AJAX)."""
    from django.http import HttpResponse
    from .models import Ticket
    ticket = get_object_or_404(Ticket, pk=pk)
    return HttpResponse(ticket.status_display_html)


def _role_code(user):
    return getattr(getattr(user, 'profile', None), 'role', None)


def _is_admin_or_super(user):
    return _role_code(user) in {'admin', 'super_admin'}


def _is_operator(user):
    return _role_code(user) in {'operator'}


def _is_analyst(user):
    # Compatível com possíveis códigos diferentes (ajuste se necessário)
    return _role_code(user) in {'analista', 'analyst'}


def _is_basic(user):
    # Compatível com possíveis códigos diferentes (ajuste se necessário)
    return _role_code(user) in {'standard', 'basico', 'basic'}


def _notify_users(sender, recipients, title, message, related_ticket=None, notification_type='alert'):
    if not recipients:
        return
    try:
        for u in recipients:
            if not u:
                continue
            Notification.objects.create(
                recipient=u,
                sender=sender,
                title=title,
                message=message,
                notification_type=notification_type,
                related_ticket=related_ticket,
            )
    except Exception:
        # Não quebra o fluxo por falha de notificação
        pass


@login_required
def ticket_delete_request(request, pk):
    """
    Fluxo de exclusão:
    - Admin/Super Admin: exclui imediatamente.
    - Operador: só exclui imediatamente as OS que ele criou. Caso contrário, bloqueia.
    - Analista: solicita exclusão (aprovação do criador ou admin).
    - Básico: solicita exclusão (aprovação dos admins).
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método inválido.'}, status=405)

    ticket = get_object_or_404(Ticket, pk=pk)
    actor = request.user
    now = timezone.now()
    reason = (request.POST.get('reason') or '').strip()

    creator = getattr(ticket, 'creator_user', None) or getattr(ticket, 'created_by', None) or getattr(ticket, 'requester', None)

    # Admin/Super Admin: exclusão imediata
    if _is_admin_or_super(actor):
        ticket_id = ticket.id
        ticket_label = ticket.formatted_id
        linked_entries = ShiftHandoverEntry.objects.filter(ticket=ticket).delete()[0]
        ticket.delete()
        return JsonResponse({'status': 'ok', 'mode': 'deleted', 'ticket_id': ticket_id, 'ticket': ticket_label, 'linked_entries': linked_entries})

    # Operador: só exclui sua própria OS
    if _is_operator(actor):
        if creator and creator.id == actor.id:
            ticket_id = ticket.id
            ticket_label = ticket.formatted_id
            linked_entries = ShiftHandoverEntry.objects.filter(ticket=ticket).delete()[0]
            ticket.delete()
            return JsonResponse({'status': 'ok', 'mode': 'deleted', 'ticket_id': ticket_id, 'ticket': ticket_label, 'linked_entries': linked_entries})
        return JsonResponse({'status': 'error', 'message': 'Operador só pode excluir a própria OS.'}, status=403)

    # Se já existe solicitação pendente, não recria
    if ticket.delete_status == 'pending':
        return JsonResponse({'status': 'ok', 'mode': 'already_pending'})

    # Solicitação (Analista ou Básico/outros)
    ticket.delete_status = 'pending'
    ticket.delete_requested_by = actor
    ticket.delete_requested_at = now
    ticket.delete_request_reason = reason
    ticket.delete_decided_by = None
    ticket.delete_decided_at = None
    ticket.delete_decision_note = ''
    ticket.save(update_fields=[
        'delete_status',
        'delete_requested_by',
        'delete_requested_at',
        'delete_request_reason',
        'delete_decided_by',
        'delete_decided_at',
        'delete_decision_note',
    ])

    # Define destinatários
    admins = list(User.objects.filter(is_active=True, profile__role__in=['admin', 'super_admin']).select_related('profile'))

    if _is_analyst(actor):
        # Aprovação: criador OU admins (fallback)
        recipients = []
        if creator and creator.is_active:
            recipients.append(creator)
        recipients += [u for u in admins if (not creator) or u.id != creator.id]
        msg = f"{actor.get_full_name() or actor.username} solicitou a exclusão da OS {ticket.formatted_id}."
        if reason:
            msg += f"\nMotivo: {reason}"
        _notify_users(
            sender=actor,
            recipients=recipients,
            title=f"Solicitação de exclusão: OS {ticket.formatted_id}",
            message=msg,
            related_ticket=ticket,
            notification_type='alert',
        )
    else:
        # Básico/outros: aprova admins
        msg = f"{actor.get_full_name() or actor.username} solicitou a exclusão da OS {ticket.formatted_id}."
        if reason:
            msg += f"\nMotivo: {reason}"
        _notify_users(
            sender=actor,
            recipients=admins,
            title=f"Solicitação de exclusão: OS {ticket.formatted_id}",
            message=msg,
            related_ticket=ticket,
            notification_type='alert',
        )

    return JsonResponse({'status': 'ok', 'mode': 'requested'})


def _can_decide_delete(user, ticket):
    if _is_admin_or_super(user):
        return True
    creator = getattr(ticket, 'creator_user', None) or getattr(ticket, 'created_by', None) or getattr(ticket, 'requester', None)
    return bool(creator and creator.id == user.id)


@login_required
def ticket_delete_approve(request, pk):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método inválido.'}, status=405)

    ticket = get_object_or_404(Ticket, pk=pk)
    if ticket.delete_status != 'pending':
        return JsonResponse({'status': 'error', 'message': 'Não há solicitação pendente.'}, status=400)

    if not _can_decide_delete(request.user, ticket):
        return JsonResponse({'status': 'error', 'message': 'Sem permissão para aprovar.'}, status=403)

    requester = ticket.delete_requested_by
    ticket_id = ticket.id
    ticket_label = ticket.formatted_id

    # Notifica quem solicitou antes de excluir (porque depois some o related_ticket)
    if requester and requester.is_active:
        _notify_users(
            sender=request.user,
            recipients=[requester],
            title=f"Exclusão aprovada: OS {ticket_label}",
            message=f"A exclusão da OS {ticket_label} foi aprovada por {request.user.get_full_name() or request.user.username}.",
            related_ticket=None,
            notification_type='alert',
        )

    linked_entries = ShiftHandoverEntry.objects.filter(ticket=ticket).delete()[0]
    ticket.delete()
    return JsonResponse({'status': 'ok', 'mode': 'deleted', 'ticket_id': ticket_id, 'ticket': ticket_label, 'linked_entries': linked_entries})


@login_required
def ticket_delete_reject(request, pk):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método inválido.'}, status=405)

    ticket = get_object_or_404(Ticket, pk=pk)
    if ticket.delete_status != 'pending':
        return JsonResponse({'status': 'error', 'message': 'Não há solicitação pendente.'}, status=400)

    if not _can_decide_delete(request.user, ticket):
        return JsonResponse({'status': 'error', 'message': 'Sem permissão para rejeitar.'}, status=403)

    note = (request.POST.get('note') or '').strip()
    ticket.delete_status = 'rejected'
    ticket.delete_decided_by = request.user
    ticket.delete_decided_at = timezone.now()
    ticket.delete_decision_note = note
    ticket.save(update_fields=['delete_status', 'delete_decided_by', 'delete_decided_at', 'delete_decision_note'])

    requester = ticket.delete_requested_by
    if requester and requester.is_active:
        msg = f"A solicitação de exclusão da OS {ticket.formatted_id} foi rejeitada."
        if note:
            msg += f"\nMotivo: {note}"
        _notify_users(
            sender=request.user,
            recipients=[requester],
            title=f"Exclusão rejeitada: OS {ticket.formatted_id}",
            message=msg,
            related_ticket=ticket,
            notification_type='alert',
        )

    return JsonResponse({'status': 'ok', 'mode': 'rejected'})


@login_required
def ticket_set_creator(request, pk):
    """
    Admin/Super Admin: define/ajusta quem criou a OS (Ticket.created_by).
    Usado pela tela de lista de OS (edição rápida).
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método inválido.'}, status=405)

    role = getattr(getattr(request.user, 'profile', None), 'role', None)
    if role not in ['admin', 'super_admin']:
        return JsonResponse({'status': 'error', 'message': 'Sem permissão.'}, status=403)

    ticket = get_object_or_404(Ticket, pk=pk)
    user_id = (request.POST.get('user_id') or '').strip()

    if not user_id:
        ticket.created_by = None
        ticket.save(update_fields=['created_by'])
        return JsonResponse({'status': 'ok', 'creator': None})

    try:
        uid = int(user_id)
    except (ValueError, TypeError):
        return JsonResponse({'status': 'error', 'message': 'user_id inválido.'}, status=400)

    creator = User.objects.filter(pk=uid, is_active=True).select_related('profile').first()
    if not creator:
        return JsonResponse({'status': 'error', 'message': 'Usuário não encontrado.'}, status=404)

    ticket.created_by = creator
    ticket.save(update_fields=['created_by'])

    profile = getattr(creator, 'profile', None)
    photo_url = profile.photo.url if profile and getattr(profile, 'photo', None) else ''
    role_label = ''
    try:
        role_label = (profile.get_role_display() or '').strip() if profile else ''
    except Exception:
        role_label = ''
    if not role_label and profile:
        role_label = (getattr(profile, 'role', '') or '').strip()

    name = (creator.get_full_name() or '').strip() or (creator.username or '').strip()
    return JsonResponse({
        'status': 'ok',
        'creator': {
            'id': creator.id,
            'name': name,
            'role': role_label,
            'photo_url': photo_url,
        }
    })

@login_required
def ticket_reorder(request):
    """
    Salva a ordem manual (arrastar e soltar) dos cards de OS na listagem,
    por usuário. Usado pelo drag-and-drop da lista e também pelo Jota4.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método inválido.'}, status=405)

    from .models import TicketListOrder

    try:
        payload = json.loads(request.POST.get('order') or '[]')
    except (ValueError, TypeError):
        return JsonResponse({'status': 'error', 'message': 'Ordem inválida.'}, status=400)

    if not isinstance(payload, list):
        return JsonResponse({'status': 'error', 'message': 'Ordem inválida.'}, status=400)

    try:
        ticket_ids = [int(i) for i in payload]
    except (ValueError, TypeError):
        return JsonResponse({'status': 'error', 'message': 'IDs inválidos.'}, status=400)

    TicketListOrder.save_new_order(request.user, ticket_ids)
    return JsonResponse({'status': 'ok'})

@login_required
def mark_all_notifications_read(request):
    if request.method == 'POST':
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True, read_at=timezone.now())
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def clients_sharepoint_sync_status(request):
    from .models import ClientSyncState
    from .microsoft_graph import shared_clients_url, get_graph_access_token

    url = shared_clients_url()
    enabled = bool(url)
    state = ClientSyncState.objects.filter(source='sharepoint').first()
    access_token = get_graph_access_token() if enabled else None
    requires_auth = enabled and not bool(access_token)

    payload = {
        'enabled': enabled,
        'requires_auth': requires_auth,
        'last_checked_at': state.last_checked_at.isoformat() if state and state.last_checked_at else None,
        'last_synced_at': state.last_synced_at.isoformat() if state and state.last_synced_at else None,
        'last_success_at': state.last_success_at.isoformat() if state and state.last_success_at else None,
        'last_error': state.last_error if state else None,
        'is_running': bool(state.is_running) if state else False,
    }
    return JsonResponse(payload)


@login_required
def microsoft_connect_start(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método inválido.'}, status=405)
    from .microsoft_graph import start_device_code_flow
    try:
        data = start_device_code_flow()
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({
        'status': 'ok',
        'device_code': data.get('device_code'),
        'user_code': data.get('user_code'),
        'verification_uri': data.get('verification_uri'),
        'expires_in': data.get('expires_in'),
        'interval': data.get('interval'),
        'message': data.get('message'),
    })


@login_required
def microsoft_connect_poll(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método inválido.'}, status=405)
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}
    device_code = (payload.get('device_code') or '').strip()
    if not device_code:
        return JsonResponse({'status': 'error', 'message': 'device_code obrigatório.'}, status=400)

    from .microsoft_graph import poll_device_code
    from .sync_sharepoint import trigger_sync_background
    result = poll_device_code(device_code)
    if result.get('status') == 'ok':
        trigger_sync_background()
    return JsonResponse(result)


@login_required
def clients_sharepoint_sync_run(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método inválido.'}, status=405)
    from .sync_sharepoint import trigger_sync_background
    trigger_sync_background()
    return JsonResponse({'status': 'ok'})

class NotificationMonitorView(AdminRequiredMixin, ListView):
    model = Notification
    template_name = 'notifications/notification_monitor.html'
    context_object_name = 'notifications'
    paginate_by = 50

    def get_queryset(self):
        qs = Notification.objects.select_related('recipient', 'sender').all().order_by('-created_at')
        
        # Filters
        notification_type = self.request.GET.get('type')
        if notification_type:
            qs = qs.filter(notification_type=notification_type)
            
        status = self.request.GET.get('status')
        if status == 'read':
            qs = qs.filter(is_read=True)
        elif status == 'unread':
            qs = qs.filter(is_read=False)
            
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Monitoramento de Notificações"
        context['type_choices'] = Notification.TYPE_CHOICES
        return context

class SendMessageView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Notification
    form_class = SendMessageForm
    template_name = 'notifications/send_message_form.html'
    success_url = reverse_lazy('dashboard')
    success_message = "Mensagem enviada com sucesso!"

    def form_valid(self, form):
        recipient = form.cleaned_data.get('recipient')
        send_to_all = form.cleaned_data.get('send_to_all')
        group = form.cleaned_data.get('group')
        title = form.cleaned_data.get('title')
        message = form.cleaned_data.get('message')
        sender = self.request.user

        recipients = set()

        if recipient:
            recipients.add(recipient)
        
        if send_to_all:
            recipients.update(User.objects.filter(is_active=True).exclude(pk=sender.pk))
        
        if group:
            if group == 'admin':
                recipients.update(User.objects.filter(is_active=True, profile__role__in=['admin', 'super_admin']).exclude(pk=sender.pk))
            elif group == 'technician':
                recipients.update(User.objects.filter(is_active=True, profile__role='technician').exclude(pk=sender.pk))
            elif group == 'client':
                recipients.update(User.objects.filter(is_active=True, profile__role='client').exclude(pk=sender.pk))

        # Create notifications
        notifications = []
        for user in recipients:
            notifications.append(Notification(
                recipient=user,
                sender=sender,
                title=title,
                message=message,
                notification_type='message'
            ))
        
        if notifications:
            Notification.objects.bulk_create(notifications)
            messages.success(self.request, f"Mensagem enviada para {len(notifications)} destinatários.")
        else:
             messages.warning(self.request, "Nenhum destinatário encontrado.")

        return redirect(self.success_url)
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Nova Mensagem"
        return context

# Technician Travel Views
class TechnicianTravelListView(LoginRequiredMixin, ListView):
    model = TechnicianTravel
    template_name = 'cadastros/travel_list.html'
    context_object_name = 'travels'
    ordering = ['-scheduled_date']

    def get_queryset(self):
        queryset = super().get_queryset().select_related('client', 'hub', 'technician', 'system', 'service_order')
        
        # Default filter: exclude completed unless requested
        show_history = self.request.GET.get('history') == 'true'
        if not show_history:
            queryset = queryset.exclude(status='completed')
        
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(client__name__icontains=q) |
                Q(technician__first_name__icontains=q) |
                Q(technician__username__icontains=q) |
                Q(system__name__icontains=q)
            )
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['show_history'] = self.request.GET.get('history') == 'true'
        return context

class TechnicianTravelDetailView(LoginRequiredMixin, DetailView):
    model = TechnicianTravel
    template_name = 'cadastros/travel_detail.html'
    context_object_name = 'travel'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Detalhes da Viagem: {self.object.technician.get_full_name()} - {self.object.scheduled_date.strftime('%d/%m/%Y')}"
        context['back_url'] = reverse_lazy('travel_list')
        context['now'] = timezone.now()
        return context

class TechnicianTravelCompleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        travel = get_object_or_404(TechnicianTravel, pk=pk)
        travel.status = 'completed'
        travel.save()
        messages.success(request, "Viagem marcada como concluída!")
        return redirect('travel_list')


class TechnicianTravelCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = TechnicianTravel
    form_class = TechnicianTravelForm
    template_name = 'cadastros/travel_form.html'
    success_url = reverse_lazy('travel_list')
    success_message = "Viagem cadastrada com sucesso!"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Nova Viagem"
        context['back_url'] = reverse_lazy('travel_list')
        context['all_hubs'] = ClientHub.objects.all().select_related('client')
        context['all_clients'] = Client.objects.all().order_by('name')
        return context

class TechnicianTravelUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = TechnicianTravel
    form_class = TechnicianTravelForm
    template_name = 'cadastros/travel_form.html'
    success_url = reverse_lazy('travel_list')
    success_message = "Viagem atualizada com sucesso!"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Editar Viagem"
        context['back_url'] = reverse_lazy('travel_list')
        context['all_hubs'] = ClientHub.objects.all().select_related('client')
        context['all_clients'] = Client.objects.all().order_by('name')
        return context


class TechnicianTravelDeleteView(LoginRequiredMixin, SuccessMessageMixin, DeleteView):
    model = TechnicianTravel
    template_name = 'cadastros/generic_confirm_delete.html'
    success_url = reverse_lazy('travel_list')
    success_message = "Viagem removida com sucesso!"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Excluir Viagem"
        context['back_url'] = reverse_lazy('travel_list')
        return context

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

class HubDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'tickets/hub_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        selected_client_id = self.request.GET.get('client')
        selected_client_id_int = None
        try:
            if selected_client_id:
                selected_client_id_int = int(selected_client_id)
        except (TypeError, ValueError):
            selected_client_id_int = None

        clients_qs = Client.objects.all().order_by('name')
        context['clients'] = clients_qs
        context['selected_client_id'] = selected_client_id_int

        # Filter Logic
        hubs_qs = ClientHub.objects.all()
        tickets_qs = Ticket.objects.select_related('client', 'hub', 'ticket_type').prefetch_related('technicians', 'systems')
        travels_qs = TechnicianTravel.objects.select_related('technician', 'service_order', 'hub', 'client').prefetch_related('segments')

        if selected_client_id_int:
            hubs_qs = hubs_qs.filter(client_id=selected_client_id_int)
            tickets_qs = tickets_qs.filter(client_id=selected_client_id_int)
            travels_qs = travels_qs.filter(client_id=selected_client_id_int)

        # Helper for date formatting
        def fmt_dt(dt, with_time=False):
            if not dt: return '-'
            if with_time:
                return timezone.localtime(dt).strftime('%d/%m/%Y %H:%M')
            return timezone.localtime(dt).strftime('%d/%m/%Y')

                # Build card items for grid (clients with hubs inside)
        dashboard_items = []
        # Group hubs by client
        client_hubs_map = defaultdict(list)
        for h in hubs_qs:
            client_hubs_map[h.client_id].append(h)

        if selected_client_id_int:
            client_obj = clients_qs.filter(id=selected_client_id_int).first()
            if client_obj:
                hubs_do_cliente = client_hubs_map.get(client_obj.id, [])
                dashboard_items.append({
                    'type': 'client',
                    'id': client_obj.id,
                    'display_name': client_obj.name,
                    'client_name': client_obj.name,
                    'address': getattr(client_obj, 'address', None),
                    'logo': client_obj.logo if hasattr(client_obj, 'logo') else None,
                    'hubs': [{'id': h.id, 'name': h.name} for h in hubs_do_cliente],
                })
        else:
            for client_obj in clients_qs:
                hubs_do_cliente = client_hubs_map.get(client_obj.id, [])
                dashboard_items.append({
                    'type': 'client',
                    'id': client_obj.id,
                    'display_name': client_obj.name,
                    'client_name': client_obj.name,
                    'address': getattr(client_obj, 'address', None),
                    'logo': client_obj.logo if hasattr(client_obj, 'logo') else None,
                    'hubs': [{'id': h.id, 'name': h.name} for h in hubs_do_cliente],
                })
        context['dashboard_items'] = dashboard_items

                # Organize data by hub/client for modal details
        hubs_data = {}
        
        # Initialize with real hubs
        for hub in hubs_qs:
            hubs_data[hub.id] = {
                'id': hub.id,
                'name': hub.name,
                'address': hub.address,
                'client_name': hub.client.name,
                'tickets': [],
                'travels': []
            }
        
        # Group hubs by client for quick lookup
        client_hubs_dict = defaultdict(list)
        for hub in hubs_qs:
            client_hubs_dict[hub.client_id].append(hub)
        
        no_hub_key = 'no_hub'
        hubs_data[no_hub_key] = {
            'id': None,
            'name': 'Sem Hub/Loja',
            'address': '-',
            'client_name': '-',
            'tickets': [],
            'travels': []
        }

        hub_tickets_map = defaultdict(list)
        for t in tickets_qs:
            hub_id = t.hub_id if t.hub_id else no_hub_key
            hub_tickets_map[hub_id].append(t)
            
        hub_travels_map = defaultdict(list)
        for tr in travels_qs:
            if tr.service_order and tr.service_order.hub_id:
                hub_id = tr.service_order.hub_id
            elif tr.hub_id:
                hub_id = tr.hub_id
            else:
                hub_id = no_hub_key
            hub_travels_map[hub_id].append(tr)

        # Client-level aggregation
        client_tickets_map = defaultdict(list)
        for t in tickets_qs:
            if t.client_id:
                client_tickets_map[t.client_id].append(t)
        client_travels_map = defaultdict(list)
        for tr in travels_qs:
            if tr.client_id:
                client_travels_map[tr.client_id].append(tr)

        final_hubs_list = []
        hubs_data_map = {}
        
        for hub_id, hub_info in hubs_data.items():
            tickets = hub_tickets_map[hub_id]
            travels = hub_travels_map[hub_id]
            
            # Skip empty "No Hub"
            if hub_id == no_hub_key and not tickets and not travels:
                continue

            data = self._build_hub_data(tickets, travels, fmt_dt)
            hub_info.update(data)
            final_hubs_list.append(hub_info)
            hubs_data_map[f"hub_{hub_info['id'] if hub_info['id'] is not None else 'nohub'}"] = data

        # Sort: "No Hub" last, others by name
        final_hubs_list.sort(key=lambda x: (x['id'] is None, x['name']))
        
        # Add client-level entries to hubs_data_map
        for client in clients_qs:
            ct = client_tickets_map.get(client.id, [])
            cv = client_travels_map.get(client.id, [])
            data = self._build_hub_data(ct, cv, fmt_dt)
            hubs_data_map[f"client_{client.id}"] = data

        context['hubs_data'] = hubs_data_map
        return context

    def _build_hub_data(self, tickets, travels, fmt_dt):
        agendadas = []
        os_abertas = []
        viagens = []
        technicians_map = {}

        open_statuses = {'open', 'in_progress', 'pending'}

        for ticket in tickets:
            systems_names = ", ".join(system.name for system in ticket.systems.all()) or "-"
            tech_names = []
            for tech in ticket.technicians.all():
                technicians_map[tech.id] = tech
                tech_names.append(tech.get_full_name() or tech.username)

            travel_obj = None
            if hasattr(ticket, 'travels'):
                travel_obj = ticket.travels.all().first()

            travel_payload = None
            if travel_obj:
                segment = travel_obj.segments.all().first()
                if segment:
                    travel_payload = {
                        'segment_exists': True,
                        'origin': segment.origin,
                        'destination': segment.destination,
                        'transport_type_display': segment.get_transport_type_display(),
                        'carrier': segment.carrier,
                        'transport_number': segment.transport_number,
                        'duration': segment.duration,
                        'locator': segment.locator,
                        'booking_code': segment.booking_code,
                        'seat': segment.seat,
                        'departure': fmt_dt(segment.departure_time, with_time=True),
                        'arrival': fmt_dt(segment.arrival_time, with_time=True),
                    }
                else:
                    travel_payload = {
                        'segment_exists': False,
                        'status': travel_obj.get_status_display(),
                        'technician': travel_obj.technician.get_full_name() or travel_obj.technician.username,
                        'flight_number': travel_obj.flight_number,
                        'departure': fmt_dt(travel_obj.departure_time, with_time=True),
                        'arrival': fmt_dt(travel_obj.arrival_time, with_time=True),
                    }

            agendadas.append({
                'id': ticket.id,
                'leankeep_id': ticket.leankeep_id or ticket.formatted_id,
                'type': ticket.ticket_type.name if ticket.ticket_type else '-',
                'status': ticket.get_status_display(),
                'status_code': ticket.status,
                'systems': systems_names,
                'description': (ticket.description or '')[:200],
                'technicians': tech_names,
                'os_url': reverse('ticket_detail', args=[ticket.id]),
                'travel': travel_payload,
            })

            if ticket.status in open_statuses:
                os_abertas.append({
                    'id': ticket.id,
                    'leankeep': ticket.leankeep_id or ticket.formatted_id,
                    'system': systems_names,
                    'status': ticket.get_status_display(),
                    'status_code': ticket.status,
                    'description': (ticket.description or '')[:200],
                })

        for travel in travels:
            technicians_map[travel.technician_id] = travel.technician
            viagens.append({
                'id': travel.id,
                'technician': travel.technician.get_full_name() or travel.technician.username,
                'ticket_status': travel.ticket_status,
                'ticket_status_display': travel.get_ticket_status_display(),
                'date': fmt_dt(travel.scheduled_date),
            })

        technicians = []
        for tech in technicians_map.values():
            profile = getattr(tech, 'profile', None)
            photo_url = profile.photo.url if profile and profile.photo else None
            role = profile.job_title if profile and profile.job_title else 'Técnico'
            technicians.append({
                'name': tech.get_full_name() or tech.username,
                'role': role,
                'photo': photo_url,
            })

        return {
            'agendadas': agendadas,
            'os_abertas': os_abertas,
            'viagens': viagens,
            'technicians': technicians,
        }

class ChecklistDailyView(LoginRequiredMixin, TemplateView):
    template_name = 'tickets/daily_checklist.html'

    def _is_admin_user(self):
        user = self.request.user
        return bool(getattr(getattr(user, 'profile', None), 'role', None) in ['admin', 'super_admin'])

    def _get_item_formset_class(self, checklist):
        if self._is_admin_user():
            return inlineformset_factory(
                DailyChecklist,
                DailyChecklistItem,
                form=DailyChecklistItemAdminForm,
                formset=BaseDailyChecklistItemFormSet,
                fields=['title', 'description', 'field_type', 'select_options', 'value_text', 'is_checked', 'observation', 'order', 'is_required', 'parent'],
                extra=0,
                can_delete=True
            )

        max_num = checklist.items.count() if checklist else 0
        return inlineformset_factory(
            DailyChecklist,
            DailyChecklistItem,
            form=DailyChecklistItemUserForm,
            formset=BaseDailyChecklistItemFormSet,
            fields=['is_checked', 'value_text', 'observation'],
            extra=0,
            can_delete=False,
            max_num=max_num,
            validate_max=True
        )

    def _build_item_formset(self, checklist, data=None, files=None):
        FormSet = self._get_item_formset_class(checklist)
        if data is not None:
            return FormSet(data, files, instance=checklist, prefix='items')
        return FormSet(instance=checklist, prefix='items')

    def get_target_date(self):
        date_str = self.request.GET.get('date')
        if date_str:
            try:
                return datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        return timezone.now().date()

    def _populate_items_from_template(self, checklist, template):
        template_items = list(template.items.all().prefetch_related('options').order_by('parent_id', 'order', 'id'))
        with transaction.atomic():
            checklist.items.all().delete()
            if not template_items:
                return
            daily_by_template_id = {}
            for template_item in template_items:
                daily_item = DailyChecklistItem.objects.create(
                    daily_checklist=checklist,
                    template_item=template_item,
                    title=template_item.title,
                    description=template_item.description,
                    order=template_item.order,
                    field_type=template_item.field_type,
                    is_required=template_item.is_required,
                    select_options=template_item.select_options,
                )
                daily_by_template_id[template_item.id] = daily_item
                options = list(getattr(template_item, 'options', []).all()) if hasattr(template_item, 'options') else []
                for opt in options:
                    DailyChecklistItemOptionValue.objects.create(
                        daily_item=daily_item,
                        template_option=opt
                    )

            for template_item in template_items:
                if not template_item.parent_id:
                    continue
                daily_item = daily_by_template_id.get(template_item.id)
                parent_daily = daily_by_template_id.get(template_item.parent_id)
                if daily_item and parent_daily:
                    daily_item.parent_id = parent_daily.id
                    daily_item.save(update_fields=['parent'])

    def _required_item_is_completed(self, item):
        if getattr(item, 'template_item_id', None):
            template_item = getattr(item, 'template_item', None)
            if template_item is not None and hasattr(template_item, 'options') and template_item.options.exists():
                option_values = list(item.option_values.select_related('template_option').all()) if hasattr(item, 'option_values') else []
                by_opt_id = {ov.template_option_id: ov for ov in option_values if ov.template_option_id}
                for opt in template_item.options.all():
                    if not opt.is_required:
                        continue
                    ov = by_opt_id.get(opt.id)
                    if opt.field_type in ('checkbox', 'switch', 'button'):
                        if not (ov and ov.value_bool):
                            return False
                    else:
                        if not (ov and (ov.value_text or '').strip()):
                            return False
                if getattr(item, 'is_required', True) and not bool(item.is_checked):
                    return False
                return True

        field_type = getattr(item, 'field_type', None) or 'switch'
        if field_type == 'group':
            return True
        if field_type in ('checkbox', 'switch', 'button'):
            return bool(item.is_checked)
        value = (item.value_text or '').strip()
        if field_type == 'select':
            return value != ''
        if field_type == 'text':
            return value != ''
        return bool(item.is_checked) or value != ''

    def _ensure_option_values(self, checklist):
        items = checklist.items.select_related('template_item').prefetch_related('template_item__options', 'option_values').all()
        to_create = []
        for item in items:
            template_item = getattr(item, 'template_item', None)
            if not template_item or not hasattr(template_item, 'options'):
                continue
            existing = {ov.template_option_id for ov in item.option_values.all() if ov.template_option_id}
            for opt in template_item.options.all():
                if opt.id not in existing:
                    to_create.append(DailyChecklistItemOptionValue(daily_item=item, template_option=opt))
        if to_create:
            DailyChecklistItemOptionValue.objects.bulk_create(to_create, ignore_conflicts=True)

    def _save_option_values(self, request, checklist):
        values = DailyChecklistItemOptionValue.objects.filter(daily_item__daily_checklist=checklist).select_related('template_option')
        for v in values:
            key = f"opt-{v.id}"
            opt = v.template_option
            if opt and opt.field_type in ('checkbox', 'switch', 'button'):
                v.value_bool = key in request.POST
                v.value_text = None
            else:
                raw = request.POST.get(key, '')
                val = raw.strip()
                v.value_text = val if val else None
                v.value_bool = None
            v.save(update_fields=['value_text', 'value_bool', 'updated_at'])

    def _get_pending_required_items(self, checklist):
        pending = []
        for item in checklist.items.all():
            if not getattr(item, 'is_required', True):
                continue
            if not self._required_item_is_completed(item):
                pending.append(item)
        return pending

    def get(self, request, *args, **kwargs):
        # Handle template selection via GET param (e.g. from sidebar)
        if 'template_id' in request.GET:
            template_id = request.GET.get('template_id')
            today = timezone.now().date() # Creation defaults to today
            
            # Check if we already have a checklist
            existing_checklist = DailyChecklist.objects.filter(user=request.user, date=today).first()
            
            if existing_checklist:
                # If existing checklist has no template (orphan), we can adopt it
                if existing_checklist.template_id is None:
                    template = get_object_or_404(ChecklistTemplate, pk=template_id)
                    existing_checklist.template = template
                    existing_checklist.save()
                    
                    # Populate items
                    self._populate_items_from_template(existing_checklist, template)
                    
                    messages.success(request, f"Checklist iniciado: {template.name}")
                    return redirect('checklist_daily')

                # If we have one with template, check if it matches the requested template
                elif str(existing_checklist.template_id) != str(template_id):
                    # Different template. 
                    # We can't have two checklists per day (unique_together constraint).
                    # We notify the user they are viewing their current checklist.
                    target_template = ChecklistTemplate.objects.filter(pk=template_id).first()
                    target_name = target_template.name if target_template else "Outro"
                    current_name = existing_checklist.template.name if existing_checklist.template else "Sem Modelo"
                    messages.warning(request, f"Você já possui um checklist aberto hoje ({current_name}). Finalize ou reinicie para mudar para {target_name}.")
                # If it matches, we just proceed to show it.
            else:
                # No checklist exists. Create one for this template!
                template = get_object_or_404(ChecklistTemplate, pk=template_id)
                
                checklist = DailyChecklist.objects.create(
                    user=request.user,
                    date=today,
                    template=template
                )
                
                # Populate items
                self._populate_items_from_template(checklist, template)
                
                messages.success(request, f"Checklist iniciado: {template.name}")
                return redirect('checklist_daily')
        
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        target_date = self.get_target_date()
        user = self.request.user
        
        context['target_date'] = target_date
        context['is_today'] = (target_date == timezone.now().date())
        context['is_admin_user'] = self._is_admin_user()
        
        # Get System Settings
        context['system_settings'] = SystemSettings.objects.first()
        
        checklist = DailyChecklist.objects.filter(user=user, date=target_date).first()
        
        # Only consider checklist valid if it has a template associated
        # This handles cases where a checklist was created automatically but no template matched
        if checklist and checklist.template:
            # If checklist exists, check if items need population (e.g. created but empty)
            if not checklist.items.exists():
                self._populate_items_from_template(checklist, checklist.template)

            self._ensure_option_values(checklist)

            checklist = DailyChecklist.objects.filter(user=user, date=target_date).prefetch_related(
                'items__images',
                Prefetch('items__details', queryset=DailyChecklistItemDetail.objects.order_by('hub__name', 'created_at')),
                Prefetch(
                    'items__option_values',
                    queryset=DailyChecklistItemOptionValue.objects.select_related('template_option').order_by('template_option__order', 'id')
                ),
                Prefetch(
                    'items__template_item__options',
                    queryset=ChecklistTemplateItemOption.objects.order_by('order', 'id')
                ),
            ).first()
            
            # Formset for existing checklist
            if self.request.POST and 'items-TOTAL_FORMS' in self.request.POST:
                formset = self._build_item_formset(checklist, data=self.request.POST, files=self.request.FILES)
            else:
                formset = self._build_item_formset(checklist)
            
            context['checklist'] = checklist
            context['formset'] = formset

            top_level = []
            children = {}
            new_forms = []
            for f in formset.forms:
                if not getattr(f.instance, 'id', None):
                    new_forms.append(f)
                    continue
                if f.instance.parent_id:
                    children.setdefault(f.instance.parent_id, []).append(f)
                else:
                    top_level.append(f)
            context['top_level_forms'] = top_level
            context['children_forms_map'] = children
            context['new_forms'] = new_forms
            context['top_level_nodes'] = [{'form': f, 'children': children.get(f.instance.id, [])} for f in top_level]
            if context['is_admin_user']:
                context['item_empty_form'] = formset.empty_form
        else:
            # No checklist yet OR orphan checklist (no template), provide templates for selection
            # Only show templates if we are on today (cannot create checklists for past days via this flow)
            if context['is_today']:
                user_department = getattr(getattr(user, 'profile', None), 'department', None)
                user_fixed_client_id = getattr(getattr(user, 'profile', None), 'fixed_client_id', None)
                dept_templates_qs = ChecklistTemplate.objects.all()
                if user_department:
                    dept_templates_qs = dept_templates_qs.filter(department__iexact=user_department)
                if user_fixed_client_id:
                    dept_templates_qs = dept_templates_qs.filter(Q(client__isnull=True) | Q(client_id=user_fixed_client_id))

                dept_templates_qs = dept_templates_qs.annotate(item_count=Count('items'))

                if dept_templates_qs.count() == 1:
                    template = dept_templates_qs.first()
                    if checklist:
                        checklist.template = template
                        checklist.save()
                        checklist.items.all().delete()
                    else:
                        checklist = DailyChecklist.objects.create(
                            user=user,
                            date=target_date,
                            template=template
                        )

                    self._populate_items_from_template(checklist, template)

                    if self.request.POST and 'items-TOTAL_FORMS' in self.request.POST:
                        formset = self._build_item_formset(checklist, data=self.request.POST, files=self.request.FILES)
                    else:
                        formset = self._build_item_formset(checklist)

                    context['checklist'] = checklist
                    context['formset'] = formset
                    context['available_templates'] = []
                    context['existing_orphan_checklist'] = None
                    return context

                context['available_templates'] = dept_templates_qs
            else:
                context['available_templates'] = []
                
            # If it's an orphan checklist, pass it so we can update it instead of creating new
            context['checklist'] = None # We treat it as None for the UI to show selection
            context['existing_orphan_checklist'] = checklist 
            context['formset'] = None
        
        # System Activities (Tickets)
        # Should we show activities for the target date? Yes, makes sense for context.
        date_start = datetime.combine(target_date, datetime.min.time())
        date_end = datetime.combine(target_date, datetime.max.time())
        
        tickets_activities = Ticket.objects.filter(
            Q(technicians=user) | Q(requester=user),
            updated_at__range=(date_start, date_end)
        ).distinct()
        
        context['tickets_activities'] = tickets_activities

        # History Checklists
        context['history_checklists'] = DailyChecklist.objects.filter(user=user).order_by('-date')
        
        # Clients for details
        context['clients_for_details'] = Client.objects.all().order_by('name')

        return context

    def post(self, request, *args, **kwargs):
        # Handle Delete History
        if request.POST.get('action') == 'delete_history':
            history_id = request.POST.get('history_id')
            history_item = get_object_or_404(DailyChecklist, pk=history_id, user=request.user)
            history_item.delete()
            messages.success(request, "Histórico de checklist excluído com sucesso.")
            return redirect('checklist_daily')

        # Handle Reset/Change Template
        if request.POST.get('action') == 'reset':
            today = timezone.now().date() # Reset only applies to today? Or target date?
            # Assuming reset is for the current active checklist, usually today. 
            # If viewing past checklist, 'reset' button might not be visible or appropriate.
            # Let's stick to today for reset for safety, or use target_date if we want to allow deleting past checklists via reset.
            # Given delete_history exists, maybe reset is just for today.
            checklist = DailyChecklist.objects.filter(user=request.user, date=today).first()
            if checklist:
                checklist.delete()
                messages.success(request, "Checklist reiniciado. Selecione um novo modelo.")
            return redirect('checklist_daily')
            
        # Handle Finish Checklist
        if request.POST.get('action') == 'finish':
            target_date = self.get_target_date()
            checklist = DailyChecklist.objects.filter(user=request.user, date=target_date).first()
            
            # Save current state first (handle formset save)
            context = self.get_context_data(**kwargs)
            formset = context.get('formset')
            
            if formset and formset.is_valid():
                formset.save()
                
                # Process images similar to normal save
                for i, form in enumerate(formset.forms):
                    if form.cleaned_data.get('DELETE'):
                        continue
                    if not form.cleaned_data.get('id'):
                        continue
                    instance = form.instance
                    files = request.FILES.getlist(f'items-{i}-new_images')
                    for f in files:
                        DailyChecklistItemImage.objects.create(item=instance, image=f)
                if checklist:
                    self._save_option_values(request, checklist)
            else:
                messages.error(request, "Erro ao finalizar checklist. Verifique os campos.")
                if target_date != timezone.now().date():
                    return redirect(f"{reverse('checklist_daily')}?date={target_date}")
                return redirect('checklist_daily')

            if checklist:
                pending = self._get_pending_required_items(checklist)
                if pending:
                    messages.error(request, f"Não é possível finalizar: {len(pending)} item(ns) obrigatório(s) pendente(s).")
                else:
                    checklist.status = 'completed'
                    checklist.save()
                    messages.success(request, "Checklist finalizado com sucesso! Agora você pode gerar o relatório PDF.")
            
            # Redirect preserving date if it's not today
            if target_date != timezone.now().date():
                return redirect(f"{reverse('checklist_daily')}?date={target_date}")
            return redirect('checklist_daily')

        # Handle Template Selection
        if 'template_id' in request.POST:
            template_id = request.POST.get('template_id')
            template = get_object_or_404(ChecklistTemplate, pk=template_id)
            today = timezone.now().date()
            
            # Check if an orphan checklist exists to update, or create new
            checklist = DailyChecklist.objects.filter(user=request.user, date=today).first()
            
            if checklist:
                # Update existing
                checklist.template = template
                checklist.save()
            else:
                # Create new
                checklist = DailyChecklist.objects.create(
                    user=request.user,
                    date=today,
                    template=template
                )
            
            # Populate items
            self._populate_items_from_template(checklist, template)
                
            messages.success(request, f"Checklist iniciado com o modelo: {template.name}")
            return redirect('checklist_daily')

        # Handle Checklist Save (Updated for multiple images)
        context = self.get_context_data(**kwargs)
        formset = context.get('formset')
        
        if formset and formset.is_valid():
            instances = formset.save()
            
            # Process multiple images manually
            # We iterate over the formset forms to find the corresponding instance and files
            for i, form in enumerate(formset.forms):
                if form.cleaned_data.get('DELETE'):
                    continue
                if not form.cleaned_data.get('id'):
                    continue
                
                instance = form.instance
                # Look for files in request.FILES with key 'items-N-new_images'
                files = request.FILES.getlist(f'items-{i}-new_images')
                
                for f in files:
                    DailyChecklistItemImage.objects.create(
                        item=instance,
                        image=f
                    )
            if context.get('checklist'):
                self._save_option_values(request, context['checklist'])

            messages.success(request, "Checklist atualizado com sucesso!")
            target_date = self.get_target_date()
            if target_date != timezone.now().date():
                 return redirect(f"{reverse('checklist_daily')}?date={target_date}")
            return redirect('checklist_daily')
        
        if formset:
             messages.error(request, "Erro ao atualizar checklist. Verifique os campos.")
        
        return self.render_to_response(context)

class ChecklistPDFView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        # Determine date
        date_str = request.GET.get('date')
        target_date = timezone.now().date()
        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        user = request.user
        
        checklist = DailyChecklist.objects.filter(user=user, date=target_date).prefetch_related(
            'items__images',
            Prefetch('items__details', queryset=DailyChecklistItemDetail.objects.order_by('hub__name', 'created_at')),
            Prefetch(
                'items__option_values',
                queryset=DailyChecklistItemOptionValue.objects.select_related('template_option').order_by('template_option__order', 'id')
            ),
            Prefetch(
                'items__template_item__options',
                queryset=ChecklistTemplateItemOption.objects.order_by('order', 'id')
            ),
        ).first()
        if not checklist:
            messages.warning(request, f"Nenhum checklist encontrado para {target_date.strftime('%d/%m/%Y')}.")
            return redirect('checklist_daily')

        # Tickets Activities
        date_start = datetime.combine(target_date, datetime.min.time())
        date_end = datetime.combine(target_date, datetime.max.time())
        
        tickets_activities = Ticket.objects.filter(
            Q(technicians=user) | Q(requester=user),
            updated_at__range=(date_start, date_end)
        ).distinct()

        def item_completed(item):
            template_item = getattr(item, 'template_item', None)
            if template_item is not None and hasattr(template_item, 'options') and template_item.options.exists():
                option_values = list(item.option_values.all()) if hasattr(item, 'option_values') else []
                by_opt_id = {ov.template_option_id: ov for ov in option_values if ov.template_option_id}
                for opt in template_item.options.all():
                    if not opt.is_required:
                        continue
                    ov = by_opt_id.get(opt.id)
                    if opt.field_type in ('checkbox', 'switch', 'button'):
                        if not (ov and ov.value_bool):
                            return False
                    else:
                        if not (ov and (ov.value_text or '').strip()):
                            return False
                return bool(item.is_checked) if getattr(item, 'is_required', True) else True

            field_type = getattr(item, 'field_type', None) or 'switch'
            if field_type == 'group':
                return True
            if field_type in ('checkbox', 'switch', 'button'):
                return bool(item.is_checked)
            value = (getattr(item, 'value_text', None) or '').strip()
            if field_type in ('select', 'text'):
                return value != ''
            return bool(item.is_checked) or value != ''

        required_items = [i for i in checklist.items.all() if getattr(i, 'is_required', True)]
        total_items = len([i for i in required_items if (getattr(i, 'field_type', None) or 'switch') != 'group'])
        checked_items = len([i for i in required_items if (getattr(i, 'field_type', None) or 'switch') != 'group' and item_completed(i)])
        pending_items = max(total_items - checked_items, 0)
        activities_count = tickets_activities.count()

        context = {
            'checklist': checklist,
            'tickets_activities': tickets_activities,
            'user': user,
            'date': target_date,
            'total_items': total_items,
            'checked_items': checked_items,
            'pending_items': pending_items,
            'activities_count': activities_count,
            'logo_path': os.path.join(settings.MEDIA_ROOT, 'images', 'logo_jumper.png'),
        }
        
        template_path = 'tickets/checklist_pdf.html'
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="checklist_{user.username}_{target_date}.pdf"'
        
        template = get_template(template_path)
        html = template.render(context)
        
        def link_callback(uri, rel):
            if uri.startswith('http://') or uri.startswith('https://'):
                return uri
            
            # Handle Static Files
            if settings.STATIC_URL and uri.startswith(settings.STATIC_URL):
                path = uri.replace(settings.STATIC_URL, '')
                absolute_path = finders.find(path)
                if absolute_path:
                    return absolute_path

            # Handle Media Files
            if settings.MEDIA_URL and uri.startswith(settings.MEDIA_URL):
                path = uri.replace(settings.MEDIA_URL, '')
                absolute_path = os.path.join(settings.MEDIA_ROOT, path.replace('/', os.sep))
                if os.path.exists(absolute_path):
                    return absolute_path
            
            # Handle relative paths (fallback)
            if not uri.startswith('/'):
                    # Check if it is a media file referenced relatively
                    if 'media/' in uri:
                        possible_path = os.path.join(settings.BASE_DIR, uri.replace('/', os.sep))
                        if os.path.exists(possible_path):
                            return possible_path

            return uri
        
        try:
            if pisa is None:
                return HttpResponse('PDF indisponível.', status=500)
            pisa_status = pisa.CreatePDF(html, dest=response, link_callback=link_callback)
            if pisa_status.err:
                return HttpResponse(f'We had some errors <pre>{html}</pre>')
        except Exception as e:
            return HttpResponse(f'Error generating PDF: {str(e)}')
            
        return response

class TicketsDailyReportPDFView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        user = request.user
        role = getattr(getattr(user, 'profile', None), 'role', None)

        date_str = request.GET.get('date')
        target_date = timezone.localdate()
        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        start_of_day = timezone.make_aware(datetime.combine(target_date, datetime.min.time()))
        end_of_day = timezone.make_aware(datetime.combine(target_date, datetime.max.time()))

        scope = request.GET.get('scope', 'mine')
        if scope == 'all' and role not in ['admin', 'super_admin']:
            scope = 'mine'

        tickets_qs = Ticket.objects.select_related('client', 'hub', 'ticket_type').prefetch_related('systems', 'technicians').filter(
            created_at__range=(start_of_day, end_of_day)
        )

        if scope != 'all':
            tickets_qs = tickets_qs.filter(Q(technicians=user) | Q(requester=user)).distinct()

        tickets_qs = tickets_qs.order_by('created_at', 'id')

        context = {
            'user': user,
            'date': target_date,
            'tickets': tickets_qs,
            'scope': scope,
            'logo_path': os.path.join(settings.MEDIA_ROOT, 'images', 'logo_principal.png'),
            'report_title': 'Relatório Diário de Chamados',
        }

        template_path = 'tickets/tickets_daily_report_pdf.html'
        response = HttpResponse(content_type='application/pdf')
        response['X-Frame-Options'] = 'SAMEORIGIN'
        download = str(request.GET.get('download') or '').strip() == '1'
        disposition = 'attachment' if download else 'inline'
        response['Content-Disposition'] = f'{disposition}; filename="jumperfour_chamados.pdf"'

        template = get_template(template_path)
        html = template.render(context)

        def link_callback(uri, rel):
            if uri.startswith('http://') or uri.startswith('https://'):
                return uri

            if settings.STATIC_URL and uri.startswith(settings.STATIC_URL):
                path = uri.replace(settings.STATIC_URL, '')
                absolute_path = finders.find(path)
                if absolute_path:
                    return absolute_path

            if settings.MEDIA_URL and uri.startswith(settings.MEDIA_URL):
                path = uri.replace(settings.MEDIA_URL, '')
                absolute_path = os.path.join(settings.MEDIA_ROOT, path.replace('/', os.sep))
                if os.path.exists(absolute_path):
                    return absolute_path

            if not uri.startswith('/'):
                if 'media/' in uri:
                    possible_path = os.path.join(settings.BASE_DIR, uri.replace('/', os.sep))
                    if os.path.exists(possible_path):
                        return possible_path

            return uri

        try:
            if pisa is None:
                return HttpResponse('PDF indisponível.', status=500)
            pisa_status = pisa.CreatePDF(html, dest=response, link_callback=link_callback)
            if pisa_status.err:
                return HttpResponse(f'We had some errors <pre>{html}</pre>')
        except Exception as e:
            return HttpResponse(f'Error generating PDF: {str(e)}')

        return response


class TicketsWeeklyReportPDFView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        week_str = request.GET.get('week')
        today = timezone.localdate()
        
        if week_str:
            try:
                year, week_num = map(int, week_str.split('-W'))
                target_date = datetime.strptime(f'{year}-W{week_num}-1', '%Y-W%W-%w').date()
            except ValueError:
                target_date = today
        else:
            target_date = today
        
        days_to_subtract = (target_date.weekday() + 1) % 7
        start_week = target_date - timedelta(days=days_to_subtract)
        end_week = start_week + timedelta(days=6)
        
        start_of_week = timezone.make_aware(datetime.combine(start_week, datetime.min.time()))
        end_of_week = timezone.make_aware(datetime.combine(end_week, datetime.max.time()))
        
        tickets_qs = Ticket.objects.select_related('client', 'hub', 'ticket_type').prefetch_related('systems', 'technicians').filter(
            created_at__range=(start_of_week, end_of_week)
        ).order_by('created_at', 'id')
        
        day_counts = {}
        for i in range(7):
            day = start_week + timedelta(days=i)
            day_start = timezone.make_aware(datetime.combine(day, datetime.min.time()))
            day_end = timezone.make_aware(datetime.combine(day, datetime.max.time()))
            count = Ticket.objects.filter(created_at__range=(day_start, day_end)).count()
            day_counts[day.strftime('%d/%m/%Y')] = count
        
        avg_week = sum(day_counts.values()) / len(day_counts) if day_counts else 0
        
        context = {
            'user': request.user,
            'start_date': start_week,
            'end_date': end_week,
            'tickets': tickets_qs,
            'day_counts': day_counts,
            'avg_week': round(avg_week, 1),
            'logo_path': os.path.join(settings.MEDIA_ROOT, 'images', 'logo_principal.png'),
            'report_title': 'Relatório Semanal de Chamados',
        }
        
        template_path = 'tickets/tickets_weekly_report_pdf.html'
        response = HttpResponse(content_type='application/pdf')
        response['X-Frame-Options'] = 'SAMEORIGIN'
        download = str(request.GET.get('download') or '').strip() == '1'
        disposition = 'attachment' if download else 'inline'
        response['Content-Disposition'] = f'{disposition}; filename="jumperfour_chamados_semanal.pdf"'
        
        template = get_template(template_path)
        html = template.render(context)
        
        def link_callback(uri, rel):
            if uri.startswith('http://') or uri.startswith('https://'):
                return uri

            if settings.STATIC_URL and uri.startswith(settings.STATIC_URL):
                path = uri.replace(settings.STATIC_URL, '')
                absolute_path = finders.find(path)
                if absolute_path:
                    return absolute_path

            if settings.MEDIA_URL and uri.startswith(settings.MEDIA_URL):
                path = uri.replace(settings.MEDIA_URL, '')
                absolute_path = os.path.join(settings.MEDIA_ROOT, path.replace('/', os.sep))
                if os.path.exists(absolute_path):
                    return absolute_path

            if not uri.startswith('/'):
                if 'media/' in uri:
                    possible_path = os.path.join(settings.BASE_DIR, uri.replace('/', os.sep))
                    if os.path.exists(possible_path):
                        return possible_path

            return uri
        
        try:
            if pisa is None:
                return HttpResponse('PDF indisponível.', status=500)
            pisa_status = pisa.CreatePDF(html, dest=response, link_callback=link_callback)
            if pisa_status.err:
                return HttpResponse(f'We had some errors <pre>{html}</pre>')
        except Exception as e:
            return HttpResponse(f'Error generating PDF: {str(e)}')
        
        return response


class TicketsMonthlyReportPDFView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        month_str = request.GET.get('month')
        today = timezone.localdate()
        
        if month_str:
            try:
                year, month_num = map(int, month_str.split('-'))
                target_date = datetime(year, month_num, 1).date()
            except ValueError:
                target_date = today
        else:
            target_date = today
        
        start_month = target_date.replace(day=1)
        if start_month.month == 12:
            end_month = start_month.replace(year=start_month.year+1, day=1) - timedelta(days=1)
        else:
            end_month = start_month.replace(month=start_month.month+1, day=1) - timedelta(days=1)
        
        start_of_month = timezone.make_aware(datetime.combine(start_month, datetime.min.time()))
        end_of_month = timezone.make_aware(datetime.combine(end_month, datetime.max.time()))
        
        tickets_qs = Ticket.objects.select_related('client', 'hub', 'ticket_type').prefetch_related('systems', 'technicians').filter(
            created_at__range=(start_of_month, end_of_month)
        ).order_by('created_at', 'id')
        
        day_counts = {}
        day = start_month
        while day <= end_month:
            day_start = timezone.make_aware(datetime.combine(day, datetime.min.time()))
            day_end = timezone.make_aware(datetime.combine(day, datetime.max.time()))
            count = Ticket.objects.filter(created_at__range=(day_start, day_end)).count()
            day_counts[day.strftime('%d/%m/%Y')] = count
            day += timedelta(days=1)
        
        avg_day = sum(day_counts.values()) / len(day_counts) if day_counts else 0
        
        week_counts = {}
        current_week = 1
        current_week_count = 0
        for i, (day_str, count) in enumerate(day_counts.items()):
            current_week_count += count
            if (i + 1) % 7 == 0 or i == len(day_counts) - 1:
                week_counts[f'Semana {current_week}'] = current_week_count
                current_week += 1
                current_week_count = 0
        
        avg_week = sum(week_counts.values()) / len(week_counts) if week_counts else 0
        
        client_counts = {}
        for ticket in tickets_qs:
            client_name = ticket.client.name
            if client_name in client_counts:
                client_counts[client_name] += 1
            else:
                client_counts[client_name] = 1
        
        avg_month = sum(client_counts.values()) / len(client_counts) if client_counts else 0
        
        context = {
            'user': request.user,
            'month': start_month,
            'tickets': tickets_qs,
            'day_counts': day_counts,
            'avg_day': round(avg_day, 1),
            'week_counts': week_counts,
            'avg_week': round(avg_week, 1),
            'client_counts': client_counts,
            'avg_month': round(avg_month, 1),
            'logo_path': os.path.join(settings.MEDIA_ROOT, 'images', 'logo_principal.png'),
            'report_title': 'Relatório Mensal de Chamados',
        }
        
        template_path = 'tickets/tickets_monthly_report_pdf.html'
        response = HttpResponse(content_type='application/pdf')
        response['X-Frame-Options'] = 'SAMEORIGIN'
        download = str(request.GET.get('download') or '').strip() == '1'
        disposition = 'attachment' if download else 'inline'
        response['Content-Disposition'] = f'{disposition}; filename="jumperfour_chamados_mensal.pdf"'
        
        template = get_template(template_path)
        html = template.render(context)
        
        def link_callback(uri, rel):
            if uri.startswith('http://') or uri.startswith('https://'):
                return uri

            if settings.STATIC_URL and uri.startswith(settings.STATIC_URL):
                path = uri.replace(settings.STATIC_URL, '')
                absolute_path = finders.find(path)
                if absolute_path:
                    return absolute_path

            if settings.MEDIA_URL and uri.startswith(settings.MEDIA_URL):
                path = uri.replace(settings.MEDIA_URL, '')
                absolute_path = os.path.join(settings.MEDIA_ROOT, path.replace('/', os.sep))
                if os.path.exists(absolute_path):
                    return absolute_path

            if not uri.startswith('/'):
                if 'media/' in uri:
                    possible_path = os.path.join(settings.BASE_DIR, uri.replace('/', os.sep))
                    if os.path.exists(possible_path):
                        return possible_path

            return uri
        
        try:
            if pisa is None:
                return HttpResponse('PDF indisponível.', status=500)
            pisa_status = pisa.CreatePDF(html, dest=response, link_callback=link_callback)
            if pisa_status.err:
                return HttpResponse(f'We had some errors <pre>{html}</pre>')
        except Exception as e:
            return HttpResponse(f'Error generating PDF: {str(e)}')
        
        return response


class TicketsDailyReportViewerView(LoginRequiredMixin, TemplateView):
    template_name = 'tickets/pdf_viewer.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        date_str = self.request.GET.get('date')
        target_date = timezone.localdate()
        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        user = self.request.user
        role = getattr(getattr(user, 'profile', None), 'role', None)
        scope = self.request.GET.get('scope', 'mine')
        if scope == 'all' and role not in ['admin', 'super_admin']:
            scope = 'mine'

        qs = f"?date={target_date.strftime('%Y-%m-%d')}&scope={scope}"
        pdf_url = reverse('tickets_daily_pdf') + qs
        context['title'] = 'Relatório Diário de Chamados'
        context['pdf_url'] = pdf_url
        context['status_url'] = reverse('tickets_daily_pdf_status') + qs
        context['download_url'] = pdf_url + '&download=1'
        return context


class TicketPDFStatusView(LoginRequiredMixin, View):
    def get(self, request, pk, *args, **kwargs):
        if pisa is None:
            return JsonResponse({'ok': False, 'message': 'PDF indisponível.'}, status=200)
        exists = Ticket.objects.filter(pk=pk).exists()
        if not exists:
            return JsonResponse({'ok': False, 'message': 'OS não encontrada.'}, status=200)
        return JsonResponse({'ok': True})


class TicketsDailyReportPDFStatusView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        if pisa is None:
            return JsonResponse({'ok': False, 'message': 'PDF indisponível.'}, status=200)
        return JsonResponse({'ok': True})

class ChecklistItemDetailAddView(LoginRequiredMixin, View):
    def post(self, request, item_id):
        item = get_object_or_404(DailyChecklistItem, pk=item_id)
        
        # Verify ownership (optional but recommended)
        if item.daily_checklist.user != request.user:
            return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)

        client_id = request.POST.get('client')
        hub_id = request.POST.get('hub')
        description = request.POST.get('description')
        ticket_id = request.POST.get('ticket') # Optional link to OS

        if not description:
             return JsonResponse({'status': 'error', 'message': 'Descrição é obrigatória'}, status=400)

        detail = DailyChecklistItemDetail(
            item=item,
            description=description
        )

        if client_id:
            detail.client_id = client_id
        if hub_id:
            detail.hub_id = hub_id
        if ticket_id:
            detail.ticket_id = ticket_id

        detail.save()

        # Return HTML fragment for the new detail row
        html = f"""
        <div class="d-flex justify-content-between align-items-start border-bottom py-2" id="detail-{detail.id}">
            <div>
                <small class="text-muted d-block">
                    {detail.created_at.strftime('%H:%M')} 
                    {f'- <strong>{detail.client.name}</strong>' if detail.client else ''}
                    {f'/ {detail.hub.name}' if detail.hub else ''}
                </small>
                <span>{detail.description}</span>
                {f'<span class="badge bg-info text-white ms-2" title="OS Vinculada">OS #{detail.ticket.id}</span>' if detail.ticket else ''}
            </div>
            <div class="d-flex">
                 <!-- Edit not fully implemented in frontend for div structure yet, keeping delete -->
                <button type="button" class="btn btn-link text-danger p-0 ms-2" onclick="deleteDetail({detail.id})">
                    <i class="fas fa-trash-alt"></i>
                </button>
            </div>
        </div>
        """

        return JsonResponse({'status': 'success', 'html': html})

class ChecklistItemDetailUpdateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        detail = get_object_or_404(DailyChecklistItemDetail, pk=pk)
        
        if detail.item.daily_checklist.user != request.user:
            return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)

        hub_id = request.POST.get('hub')
        description = request.POST.get('description')

        if not description:
             return JsonResponse({'status': 'error', 'message': 'Descrição é obrigatória'}, status=400)

        if hub_id:
            detail.hub_id = hub_id
        else:
            detail.hub_id = None
            
        detail.description = description
        detail.save()

        # Return updated HTML fragment for the row
        html = f"""
        <div class="d-flex justify-content-between align-items-start border-bottom py-2" id="detail-{detail.id}">
            <div>
                <small class="text-muted d-block">
                    {detail.created_at.strftime('%H:%M')} 
                    {f'- <strong>{detail.client.name}</strong>' if detail.client else ''}
                    {f'/ {detail.hub.name}' if detail.hub else ''}
                </small>
                <span>{detail.description}</span>
                {f'<span class="badge bg-info text-white ms-2" title="OS Vinculada">OS #{detail.ticket.id}</span>' if detail.ticket else ''}
            </div>
            <div class="d-flex">
                 <!-- Edit not fully implemented in frontend for div structure yet, keeping delete -->
                <button type="button" class="btn btn-link text-danger p-0 ms-2" onclick="deleteDetail({detail.id})">
                    <i class="fas fa-trash-alt"></i>
                </button>
            </div>
        </div>
        """

        return JsonResponse({'status': 'success', 'html': html, 'id': detail.id})

class ChecklistItemDetailDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        detail = get_object_or_404(DailyChecklistItemDetail, pk=pk)
        
        if detail.item.daily_checklist.user != request.user:
            return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
            
        detail.delete()
        return JsonResponse({'status': 'success'})

class ClientHubsAPIView(LoginRequiredMixin, View):
    def get(self, request, client_id):
        hubs = ClientHub.objects.filter(client_id=client_id).values('id', 'name').order_by('name')
        return JsonResponse(list(hubs), safe=False)

class ClientTodaysTicketsAPIView(LoginRequiredMixin, View):
    def get(self, request, client_id):
        today = timezone.now().date()
        today_start = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
        today_end = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.max.time()))
        
        tickets = Ticket.objects.filter(
            client_id=client_id,
            created_at__range=(today_start, today_end)
        ).values('id', 'formatted_id', 'description', 'hub__name', 'hub__id', 'client__id', 'created_at')
        
        # Format for frontend
        data = []
        for t in tickets:
            data.append({
                'id': t['id'],
                'label': f"OS #{t['formatted_id']} - {t['created_at'].strftime('%H:%M')} - {t['hub__name'] or 'Geral'}",
                'description': t['description'],
                'client_id': t['client__id'],
                'hub_id': t['hub__id']
            })
            
        return JsonResponse(data, safe=False)

class ChecklistImageToggleReportView(LoginRequiredMixin, View):
    def post(self, request, pk):
        image = get_object_or_404(DailyChecklistItemImage, pk=pk)
        
        # Verify ownership (optional but recommended)
        if image.item.daily_checklist.user != request.user and not request.user.is_superuser:
             return JsonResponse({'error': 'Permission denied'}, status=403)
        
        # Toggle status
        image.is_report_image = not image.is_report_image
        image.save()
        
        return JsonResponse({
            'success': True, 
            'is_report_image': image.is_report_image,
            'item_id': image.item.id
        })

class LocalView(LoginRequiredMixin, TemplateView):
    template_name = 'tickets/local.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        technicians = (
            User.objects.filter(is_active=True, profile__role__in=['technician', 'standard'])
            .select_related('profile')
            .order_by('first_name', 'username')
        )

        technician_cards = []
        for tech in technicians:
            profile = getattr(tech, 'profile', None)
            photo_url = profile.photo.url if profile and profile.photo else None
            job_title = profile.job_title if profile and profile.job_title else None
            station = profile.station if profile and profile.station else None
            technician_type = profile.get_technician_type_display() if profile else None
            fixed_client = profile.fixed_client.name if profile and profile.fixed_client else None
            fixed_hub = profile.fixed_hub.name if profile and profile.fixed_hub else None

            technician_cards.append({
                'id': tech.id,
                'name': tech.get_full_name() or tech.username,
                'initial': (tech.first_name or tech.username or '?')[:1].upper(),
                'photo': photo_url,
                'job_title': job_title,
                'station': station,
                'technician_type': technician_type,
                'fixed_client': fixed_client,
                'fixed_hub': fixed_hub,
            })

        context['technicians'] = technician_cards
        context['today'] = timezone.localdate().strftime('%Y-%m-%d')
        return context


class LocalAgendaAPIView(LoginRequiredMixin, View):
    def get(self, request, technician_id):
        tech = get_object_or_404(User, pk=technician_id, is_active=True)
        profile = getattr(tech, 'profile', None)

        date_str = request.GET.get('date')
        target_date = timezone.localdate()
        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                target_date = timezone.localdate()

        tz = timezone.get_current_timezone()
        day_start = timezone.make_aware(datetime.combine(target_date, datetime.min.time()), tz)
        day_end = timezone.make_aware(datetime.combine(target_date, datetime.max.time()), tz)

        tickets_qs = Ticket.objects.filter(technicians=tech).exclude(status='canceled')
        tickets_for_day = (
            tickets_qs.filter(
                (Q(start_date__isnull=False) & Q(start_date__lte=day_end) & (Q(deadline__gte=day_start) | Q(deadline__isnull=True))) |
                (Q(start_date__isnull=True) & Q(deadline__range=(day_start, day_end)))
            )
            .select_related('client', 'hub', 'ticket_type')
            .prefetch_related('systems')
            .order_by('created_at')
        )

        travels_for_day = (
            TechnicianTravel.objects.filter(technician=tech, scheduled_date__range=(day_start, day_end))
            .select_related('client', 'hub', 'system', 'service_order')
            .prefetch_related('segments')
            .order_by('scheduled_date')
        )

        def fmt_dt(value, with_time=False):
            if not value:
                return None
            if with_time:
                return timezone.localtime(value).strftime('%d/%m/%Y %H:%M')
            return timezone.localtime(value).strftime('%d/%m/%Y')

        def fmt_time(value):
            if not value:
                return None
            return timezone.localtime(value).strftime('%H:%M')

        def fmt_duration(value):
            if not value:
                return None
            total_minutes = int(value.total_seconds() // 60)
            hours = total_minutes // 60
            minutes = total_minutes % 60
            return f"{hours}:{minutes:02d}"

        items = []
        location_counts = defaultdict(int)
        total_estimated_minutes = 0

        for t in tickets_for_day:
            hub_name = t.hub.name if t.hub else None
            location_label = f"{t.client.name} - {hub_name}" if hub_name else t.client.name
            location_counts[location_label] += 1

            estimated = fmt_duration(t.estimated_time) or t.calculated_hours
            if t.estimated_time:
                total_estimated_minutes += int(t.estimated_time.total_seconds() // 60)

            systems_names = ", ".join(system.name for system in t.systems.all()) or "-"

            items.append({
                'kind': 'os',
                'id': t.id,
                'label': t.leankeep_id or t.formatted_id,
                'status': t.get_status_display(),
                'status_code': t.status,
                'client': t.client.name,
                'hub': hub_name,
                'location': location_label,
                'systems': systems_names,
                'estimated_time': estimated,
                'start_time': fmt_time(t.start_date),
                'deadline_time': fmt_time(t.deadline),
                'url': reverse('ticket_detail', args=[t.id]),
                'description': (t.description or '')[:160],
                'created_at': timezone.localtime(t.created_at).isoformat(),
            })

        for tr in travels_for_day:
            hub_name = tr.hub.name if tr.hub else None
            location_label = f"{tr.client.name} - {hub_name}" if hub_name else tr.client.name
            location_counts[location_label] += 1

            segment = tr.segments.all().first()
            travel_payload = {
                'segment_exists': bool(segment),
                'transport_type': segment.get_transport_type_display() if segment else None,
                'carrier': segment.carrier if segment else None,
                'transport_number': segment.transport_number if segment else None,
                'locator': segment.locator if segment else None,
                'departure': fmt_dt(segment.departure_time, with_time=True) if segment else fmt_dt(tr.departure_time, with_time=True),
                'arrival': fmt_dt(segment.arrival_time, with_time=True) if segment else fmt_dt(tr.arrival_time, with_time=True),
            }

            items.append({
                'kind': 'agendamento',
                'id': tr.id,
                'client': tr.client.name,
                'hub': hub_name,
                'location': location_label,
                'status': tr.get_status_display(),
                'status_code': tr.status,
                'scheduled_at': fmt_dt(tr.scheduled_date, with_time=True),
                'system': tr.system.name if tr.system else None,
                'service_order': tr.service_order.leankeep_id if tr.service_order and tr.service_order.leankeep_id else (tr.service_order.formatted_id if tr.service_order else None),
                'travel': travel_payload,
                'url': reverse('travel_detail', args=[tr.id]),
            })

        primary_location = None
        if location_counts:
            primary_location = sorted(location_counts.items(), key=lambda x: (-x[1], x[0]))[0][0]
        elif profile and profile.technician_type == 'fixo' and profile.fixed_client:
            primary_location = f"{profile.fixed_client.name} - {profile.fixed_hub.name}" if profile.fixed_hub else profile.fixed_client.name

        total_estimated = None
        if total_estimated_minutes > 0:
            total_estimated = f"{total_estimated_minutes // 60}:{total_estimated_minutes % 60:02d}"

        return JsonResponse({
            'technician': {
                'id': tech.id,
                'name': tech.get_full_name() or tech.username,
            },
            'date': target_date.strftime('%Y-%m-%d'),
            'date_label': target_date.strftime('%d/%m/%Y'),
            'summary': {
                'primary_location': primary_location,
                'total_estimated_time': total_estimated,
                'items_count': len(items),
            },
            'items': items,
        }, safe=False)

