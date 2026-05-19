from .models import SystemSettings
from django.core.exceptions import PermissionDenied
from django.urls import resolve
from .models import AppPage, RoleLevel, RolePagePermission
from django.db.utils import OperationalError, ProgrammingError

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
