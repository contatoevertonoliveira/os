from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from .models import UserProfile

class TokenBackend(ModelBackend):
    def authenticate(self, request, token=None, **kwargs):
        if not token:
            return None
        
        try:
            profile = UserProfile.objects.select_related('user').get(token=token)
            if profile.user.is_active:
                return profile.user
        except UserProfile.DoesNotExist:
            return None
            
    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
