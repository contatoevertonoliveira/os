from .models import SystemSettings, Notification

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
        
    return context
