from .models import SystemSettings, Notification, ChecklistTemplate, AppPage, RoleLevel, RolePagePermission, SearchProviderConfig, VoiceProviderConfig
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

    try:
        context['active_search_config'] = SearchProviderConfig.objects.filter(is_active=True).first()
        context['active_voice_config'] = VoiceProviderConfig.objects.filter(is_active=True).first()
    except (OperationalError, ProgrammingError):
        context['active_search_config'] = None
        context['active_voice_config'] = None

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
        allow_pdf_reports = getattr(profile, 'allow_pdf_reports', True) if profile else True

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

        sidebar_url_names = {
            'dashboard',
            'hub_dashboard',
            'local',
            'client_list',
            'equipment_list',
            'ordertype_list',
            'problemtype_list',
            'technician_list',
            'responsible_list',
            'contactclient_list',
            'contactjumper_list',
            'travel_list',
            'system_list',
            'ticketstatus_list',
            'user_list',
            'ticket_list',
            'task_list',
            'checklist_daily',
            'notification_list',
            'notification_monitor',
            'settings',
            'settings_integrations',
            'permissions',
        }

        feature_url_names = {
            'ticket_pdf_view',
            'ticket_pdf',
            'tickets_daily_report_view',
            'tickets_daily_pdf',
            'checklist_pdf',
            'ticket_delete',
        }

        ui_url_names = sidebar_url_names | feature_url_names

        allowed_url_names = set(ui_url_names)
        admin_only_url_names = {'settings', 'settings_integrations', 'permissions', 'user_list', 'notification_monitor'}

        if role_code not in {'admin', 'super_admin'}:
            allowed_url_names -= admin_only_url_names

        try:
            pages = list(AppPage.objects.filter(url_name__in=ui_url_names))
            page_by_id = {p.id: p for p in pages}
            page_by_url_name = {p.url_name: p for p in pages}

            for url_name, page in page_by_url_name.items():
                if not page.is_enabled and url_name in allowed_url_names:
                    allowed_url_names.remove(url_name)

            if role_code and role_code != 'super_admin':
                role = RoleLevel.objects.filter(code=role_code, is_active=True).first()
                if role:
                    denied_page_ids = set(
                        RolePagePermission.objects.filter(
                            role=role,
                            page_id__in=page_by_id.keys(),
                            allowed=False,
                        ).values_list('page_id', flat=True)
                    )
                    for page_id in denied_page_ids:
                        page = page_by_id.get(page_id)
                        if page and page.url_name in allowed_url_names:
                            allowed_url_names.remove(page.url_name)
        except (OperationalError, ProgrammingError):
            pass
        except Exception:
            pass

        if not allow_pdf_reports:
            allowed_url_names -= feature_url_names

        context['allow_pdf_reports'] = allow_pdf_reports
        context['allowed_url_names'] = allowed_url_names
    else:
        context['allowed_url_names'] = set()
        
    return context
