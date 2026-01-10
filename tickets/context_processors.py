from .models import SystemSettings

def system_settings(request):
    try:
        settings = SystemSettings.objects.first()
        if not settings:
            settings = SystemSettings.objects.create()
    except Exception:
        return {}
        
    return {
        'system_settings': settings,
        'session_timeout_minutes': settings.session_timeout_minutes
    }
