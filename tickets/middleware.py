from .models import SystemSettings, ActiveSession, UserProfile, AppPage, RoleLevel, RolePagePermission
from django.core.exceptions import PermissionDenied
from django.urls import resolve
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone
from django.contrib.auth import logout
from datetime import timedelta

class EnsureUserProfileMiddleware:
    """
    Garante que todo usuário autenticado tenha um UserProfile.
    Se não tiver, cria um automaticamente com ai_chat_enabled = True por padrão.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                if not hasattr(request.user, 'profile') or request.user.profile is None:
                    UserProfile.objects.get_or_create(user=request.user)
            except Exception:
                pass

        response = self.get_response(request)
        return response


class SingleSessionPerIpMiddleware:
    """
    Garante que um mesmo usuário não possa ter sessões ativas de IPs diferentes.
    Se o usuário logar de um IP diferente, a sessão antiga é invalidada.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            ip = self.get_client_ip(request)
            session_key = request.session.session_key

            if session_key:
                # Verifica/atualiza o registro ActiveSession para esta sessão
                try:
                    active, created = ActiveSession.objects.get_or_create(
                        session_key=session_key,
                        defaults={
                            'user': request.user,
                            'ip_address': ip,
                            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500],
                        }
                    )

                    if not created:
                        # Sessão já existe, verificar se o IP mudou
                        if active.ip_address != ip:
                            # IP mudou! Pode ser alguém tentando usar a mesma sessão de outro lugar
                            # ou o IP real do cliente mudou (ex: VPN). Vamos invalidar.
                            logout(request)
                            active.delete()
                            return self.get_response(request)

                        # Atualiza o usuário caso tenha mudado (não deveria)
                        if active.user != request.user:
                            active.user = request.user
                            active.save()
                        else:
                            # Mantém last_activity "vivo" enquanto o usuário navega — sem isso,
                            # o campo (auto_now) só era gravado no primeiro request da sessão,
                            # fazendo qualquer verificação de "usuário online" parecer desatualizada
                            # mesmo com o usuário navegando ativamente. Grava no máximo 1x/min.
                            now = timezone.now()
                            if (now - active.last_activity) > timedelta(minutes=1):
                                active.save(update_fields=['last_activity'])
                except Exception:
                    # Se der erro (ex: tabela não existe), ignora
                    pass
        else:
            # Usuário não autenticado - não faz nada
            pass

        response = self.get_response(request)
        return response

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip

class SessionTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                settings = SystemSettings.objects.first()
                if settings:
                    # Define a expiração da sessão em segundos
                    request.session.set_expiry(settings.session_timeout_minutes * 60)
            except Exception:
                pass

            try:
                from .sync_sharepoint import maybe_trigger_sync
                maybe_trigger_sync(request)
            except Exception:
                pass
                
        response = self.get_response(request)
        return response


class RolePageAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.path.startswith('/admin/'):
            return None

        if not request.user.is_authenticated:
            return None

        match = getattr(request, 'resolver_match', None)
        if match is None:
            try:
                match = resolve(request.path_info)
            except Exception:
                return None

        url_name = getattr(match, 'url_name', None)
        if not url_name:
            return None

        if url_name in {
            'home',
            'login',
            'logout',
            'services_hub',
            'api_tickets',
            'api_clients',
            'api_equipments',
            'clients_sharepoint_sync_status',
            'clients_sharepoint_sync_run',
            'microsoft_connect_start',
            'microsoft_connect_poll',
        }:
            return None

        profile = getattr(request.user, 'profile', None)
        role_code = getattr(profile, 'role', None) if profile else None

        if role_code == 'super_admin':
            return None

        pdf_url_names = {
            'ticket_pdf_view',
            'ticket_pdf',
            'tickets_daily_report_view',
            'tickets_daily_pdf',
            'checklist_pdf',
        }

        if url_name in pdf_url_names and profile and not getattr(profile, 'allow_pdf_reports', True):
            raise PermissionDenied

        try:
            page = AppPage.objects.filter(url_name=url_name).first()
        except (OperationalError, ProgrammingError):
            return None
        if page and not page.is_enabled:
            raise PermissionDenied

        if not role_code or not page:
            return None

        try:
            role = RoleLevel.objects.filter(code=role_code, is_active=True).first()
        except (OperationalError, ProgrammingError):
            return None
        if not role:
            return None

        try:
            permission = RolePagePermission.objects.filter(role=role, page=page).first()
        except (OperationalError, ProgrammingError):
            return None
        if permission and not permission.allowed:
            raise PermissionDenied

        return None
