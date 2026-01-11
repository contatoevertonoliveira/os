from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate
from .models import UserProfile, Ticket, TicketUpdate, System, Client, SystemSettings

class TokenLoginForm(forms.Form):
    token = forms.CharField(label="Token de Acesso", widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Cole seu token aqui'}))

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        token = self.cleaned_data.get('token')
        
        if token:
            self.user_cache = authenticate(self.request, token=token)
            if self.user_cache is None:
                raise forms.ValidationError(
                    "Token inválido ou expirado. Verifique e tente novamente.",
                    code='invalid_login',
                )
            else:
                self.confirm_login_allowed(self.user_cache)
        
        return self.cleaned_data
    
    def confirm_login_allowed(self, user):
        """
        Controls whether the given User may log in. This is a policy check,
        independent of end-user authentication. This default behavior is to
        allow login by active users, and reject login by inactive users.
        
        If the given user cannot log in, this method should raise a
        ``forms.ValidationError``.
        
        If the given user may log in, this method should return None.
        """
        if not user.is_active:
            raise forms.ValidationError(
                "Esta conta está inativa.",
                code='inactive',
            )
    
    def get_user(self):
        return self.user_cache

class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            'name', 'email', 'phone', 'phone2', 'address',
            'contact1_name', 'contact1_phone', 'contact1_email',
            'contact2_name', 'contact2_phone', 'contact2_email'
        ]
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control phone-mask', 'placeholder': '(00) 0000-0000'}),
            'phone2': forms.TextInput(attrs={'class': 'form-control phone-mask', 'placeholder': '(00) 0000-0000'}),
            'contact1_phone': forms.TextInput(attrs={'class': 'form-control phone-mask', 'placeholder': '(00) 0000-0000'}),
            'contact2_phone': forms.TextInput(attrs={'class': 'form-control phone-mask', 'placeholder': '(00) 0000-0000'}),
            'address': forms.Textarea(attrs={'rows': 2}),
        }

class TechnicianForm(forms.ModelForm):
    first_name = forms.CharField(label="Nome do Técnico", max_length=150, required=True)
    username = forms.CharField(label="Login (Usuário)", max_length=150, required=True)
    email = forms.EmailField(label="Email", required=False)
    
    # Profile fields
    job_title = forms.CharField(label="Cargo do Técnico", max_length=100, required=False)
    station = forms.CharField(label="Posto de Alocação", max_length=100, required=False)

    class Meta:
        model = User
        fields = ['first_name', 'username', 'email']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if hasattr(self.instance, 'profile'):
                self.fields['job_title'].initial = self.instance.profile.job_title
                self.fields['station'].initial = self.instance.profile.station

    def save(self, commit=True):
        user = super().save(commit=False)
        # Only set password if it's a new user
        if not user.pk:
            user.set_password('123456')
        
        if commit:
            user.save()
            # Create or update profile
            if hasattr(user, 'profile'):
                profile = user.profile
            else:
                profile = UserProfile(user=user)
            
            profile.role = 'technician'
            profile.job_title = self.cleaned_data['job_title']
            profile.station = self.cleaned_data['station']
            profile.save()
        return user

class TechnicianChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        if obj.first_name or obj.last_name:
            return f"{obj.get_full_name()} ({obj.username})"
        return obj.username

class TicketForm(forms.ModelForm):
    technician = TechnicianChoiceField(
        queryset=User.objects.filter(profile__role__in=['standard', 'technician']),
        required=False,
        label="Técnico Responsável",
        empty_label="Selecione um técnico"
    )
    requester = TechnicianChoiceField(
        queryset=User.objects.filter(profile__role__in=['standard', 'technician']),
        required=False,
        label="Solicitante",
        empty_label="Selecione um solicitante"
    )

    class Meta:
        model = Ticket
        fields = [
            'client', 'systems', 'area_group', 'area_subgroup', 'area',
            'equipment', 'order_type', 'call_type', 'problem_type',
            'requester', 'technician', 'start_date', 'deadline', 'estimated_time', 
            'description', 'image', 'status'
        ]
        widgets = {
            'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'deadline': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'estimated_time': forms.TextInput(attrs={'placeholder': 'HH:MM:SS ou DD HH:MM:SS'}),
            'systems': forms.SelectMultiple(attrs={'class': 'form-select', 'size': '4'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['start_date'].input_formats = ('%Y-%m-%dT%H:%M',)
        self.fields['deadline'].input_formats = ('%Y-%m-%dT%H:%M',)
        self.fields['systems'].queryset = System.objects.all()

class TicketUpdateForm(TicketForm):
    class Meta(TicketForm.Meta):
        fields = TicketForm.Meta.fields + ['finished_at']
        widgets = {
            'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'deadline': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'estimated_time': forms.TextInput(attrs={'placeholder': 'HH:MM:SS ou DD HH:MM:SS'}),
            'systems': forms.SelectMultiple(attrs={'class': 'form-select', 'size': '4'}),
            'finished_at': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure the input format matches the HTML5 datetime-local requirement
        self.fields['finished_at'].input_formats = ('%Y-%m-%dT%H:%M',)

class TicketEvolutionForm(forms.ModelForm):
    class Meta:
        model = TicketUpdate
        fields = ['description', 'image']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Descreva a evolução do atendimento...'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
        }

class UserProfileForm(forms.ModelForm):
    first_name = forms.CharField(label="Nome Completo", max_length=150, required=True)
    email = forms.EmailField(label="Email", required=True)
    
    class Meta:
        model = UserProfile
        fields = ['photo', 'personal_phone', 'company_phone', 'station', 'role']
        widgets = {
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'personal_phone': forms.TextInput(attrs={'class': 'form-control phone-mask', 'placeholder': '(00) 00000-0000'}),
            'company_phone': forms.TextInput(attrs={'class': 'form-control phone-mask', 'placeholder': '(00) 0000-0000'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Populate user fields
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['email'].initial = self.instance.user.email

        # Role restriction logic
        is_admin = self.user and hasattr(self.user, 'profile') and self.user.profile.role in ['admin', 'super_admin']
        
        if not is_admin:
            # Hide/Disable restricted fields for non-admins
            self.fields['role'].disabled = True
            self.fields['station'].disabled = True # Assuming station is assigned by admin
        
    def save(self, commit=True):
        profile = super().save(commit=False)
        
        # Update User model fields
        user = profile.user
        user.first_name = self.cleaned_data['first_name']
        user.email = self.cleaned_data['email']
        
        if commit:
            user.save()
            profile.save()
            
        return profile

class SystemSettingsForm(forms.ModelForm):
    class Meta:
        model = SystemSettings
        fields = ['session_timeout_minutes']
        widgets = {
            'session_timeout_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '1440'}),
        }
