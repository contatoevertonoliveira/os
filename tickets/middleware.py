from .models import SystemSettings

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
                
        response = self.get_response(request)
        return response
