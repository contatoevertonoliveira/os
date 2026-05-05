from .models import SystemSettings, Notification, ChecklistTemplate, AppPage, RoleLevel, RolePagePermission
from django.db.utils import OperationalError, ProgrammingError

def system_settings(request):
    try:
        settings = SystemSettings.objects.first()
        if not settings:
            settings = SystemSettings.objects.create()
    except Exception:
        settings = None
        
    context = {}
    if settings:
        context['system_settings'] = settings
        context['session_timeout_minutes'] = settings.session_timeout_minutes

    if request.user.is_authenticated:
        unread = Notification.objects.filter(recipient=request.user, is_read=False).order_by('-created_at')
        context['unread_notifications'] = unread
        context['unread_notifications_count'] = unread.count()
        
        # Add checklist templates for sidebar
        try:
            context['sidebar_checklist_templates'] = ChecklistTemplate.objects.prefetch_related('items').all().order_by('department', 'name')
        except Exception:
            context['sidebar_checklist_templates'] = []

        profile = getattr(request.user, 'profile', None)
        role_code = getattr(profile, 'role', None) if profile else None

        can_access_permissions = role_code in {'admin', 'super_admin'}
        if role_code == 'super_admin':
            can_access_permissions = True
        elif role_code == 'admin':
            try:
                page = AppPage.objects.filter(url_name='permissions').first()
                if page and not page.is_enabled:
                    can_access_permissions = False
                else:
                    role = RoleLevel.objects.filter(code='admin', is_active=True).first()
                    if role and page:
                        perm = RolePagePermission.objects.filter(role=role, page=page).first()
                        if perm and not perm.allowed:
                            can_access_permissions = False
            except (OperationalError, ProgrammingError):
                can_access_permissions = True
            except Exception:
                can_access_permissions = True

        context['can_access_permissions'] = can_access_permissions
        
    return context
