from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.utils import timezone
from .models import UserProfile

class TokenBackend(ModelBackend):
    def authenticate(self, request, token=None, **kwargs):
        if not token:
            return None
        
        try:
            profile = UserProfile.objects.select_related('user').get(token=token)
            if profile.user.is_active:
                return profile.user
            blocked_until = getattr(profile, 'blocked_until', None)
            if blocked_until and blocked_until <= timezone.now():
                profile.user.is_active = True
                profile.user.save(update_fields=['is_active'])
                profile.blocked_until = None
                profile.blocked_reason = None
                profile.save(update_fields=['blocked_until', 'blocked_reason'])
                return profile.user
        except UserProfile.DoesNotExist:
            return None
        except UserProfile.MultipleObjectsReturned:
            # Caso existam múltiplos usuários com o mesmo token (não deveria acontecer), pega o primeiro
            profile = UserProfile.objects.select_related('user').filter(token=token).first()
            if profile and profile.user.is_active:
                return profile.user
            if profile:
                blocked_until = getattr(profile, 'blocked_until', None)
                if blocked_until and blocked_until <= timezone.now():
                    profile.user.is_active = True
                    profile.user.save(update_fields=['is_active'])
                    profile.blocked_until = None
                    profile.blocked_reason = None
                    profile.save(update_fields=['blocked_until', 'blocked_reason'])
                    return profile.user
            return None
            
    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
