from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate
from .models import UserProfile, Ticket, TicketUpdate, System, Client, SystemSettings, Notification, ClientHub, Equipment

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
            'name', 'logo', 'email', 'phone', 'phone2', 'address',
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['logo'].widget.attrs.update({'class': 'form-control'})


class ClientHubForm(forms.ModelForm):
    class Meta:
        model = ClientHub
        fields = ['name', 'address', 'phone']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome do Hub/Loja'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Endereço'}),
            'phone': forms.TextInput(attrs={'class': 'form-control phone-mask', 'placeholder': '(00) 0000-0000'}),
        }

ClientHubFormSet = forms.inlineformset_factory(
    Client, ClientHub, form=ClientHubForm,
    extra=1, can_delete=True
)


class TechnicianForm(forms.ModelForm):
    first_name = forms.CharField(label="Nome do Técnico", max_length=150, required=True)
    username = forms.CharField(label="Login (Usuário)", max_length=150, required=True)
    email = forms.EmailField(label="Email", required=False)
    
    # Profile fields
    job_title = forms.CharField(label="Cargo do Técnico", max_length=100, required=False)
    station = forms.CharField(label="Posto de Alocação", max_length=100, required=False)
    
    # Hierarchy
    department = forms.CharField(label="Departamento/Área", max_length=100, required=False)
    supervisor = forms.ModelChoiceField(
        queryset=UserProfile.objects.filter(role__in=['admin', 'super_admin', 'technician']),
        label="Supervisor/Gerente",
        required=False,
        empty_label="Selecione um supervisor"
    )

    photo = forms.ImageField(label="Foto de Perfil", required=False)
    
    class Meta:
        model = User
        fields = ['first_name', 'username', 'email']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if hasattr(self.instance, 'profile'):
                self.fields['job_title'].initial = self.instance.profile.job_title
                self.fields['station'].initial = self.instance.profile.station
                self.fields['department'].initial = self.instance.profile.department
                self.fields['supervisor'].initial = self.instance.profile.supervisor
                self.fields['photo'].initial = self.instance.profile.photo
                
                # Exclude self from supervisor queryset to avoid loops
                self.fields['supervisor'].queryset = self.fields['supervisor'].queryset.exclude(user=self.instance)

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
            profile.department = self.cleaned_data['department']
            profile.supervisor = self.cleaned_data['supervisor']
            
            if self.cleaned_data.get('photo'):
                profile.photo = self.cleaned_data['photo']
            profile.save()
        return user

class TechnicianChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        if obj.first_name or obj.last_name:
            return f"{obj.get_full_name()} ({obj.username})"
        return obj.username

class TechnicianMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        if obj.first_name or obj.last_name:
            return f"{obj.get_full_name()} ({obj.username})"
        return obj.username

class TicketForm(forms.ModelForm):
    technicians = TechnicianMultipleChoiceField(
        queryset=User.objects.filter(profile__role='technician', is_active=True).order_by('first_name'),
        required=False,
        label="Técnicos Responsáveis",
        widget=forms.SelectMultiple(attrs={'class': 'form-select', 'size': '4'})
    )
    requester = TechnicianChoiceField(
        queryset=User.objects.filter(is_active=True).order_by('first_name'),
        required=False,
        label="Solicitante",
        empty_label="Selecione um solicitante"
    )

    equipment_selection = forms.ModelChoiceField(
        queryset=Equipment.objects.all().order_by('name'),
        required=False,
        label="Adicionar Equipamento",
        empty_label="Selecione um equipamento...",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_equipment_selection'})
    )

    class Meta:
        model = Ticket
        fields = [
            'client', 'hub', 'systems', 'area_group', 'area_subgroup', 'area',
            'equipments', 'order_type', 'ticket_type', 'problem_type',
            'requester', 'technicians', 'start_date', 'deadline', 'estimated_time', 
            'description', 'final_description', 'image', 'status'
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'deadline': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'systems': forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input system-switch'}),
            'hub': forms.Select(attrs={'class': 'form-select'}),
            'ticket_type': forms.Select(attrs={'class': 'form-select'}),
            'final_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Descreva o que foi feito para resolver o problema...'}),
            'equipments': forms.SelectMultiple(attrs={'class': 'd-none', 'id': 'id_equipments'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['start_date'].input_formats = ('%Y-%m-%dT%H:%M',)
        self.fields['deadline'].input_formats = ('%Y-%m-%dT%H:%M',)
        self.fields['systems'].queryset = System.objects.all()
        
        # Rename description label
        self.fields['description'].label = "Descrição Inicial"

        # Hide final_description on creation
        if not self.instance.pk:
            if 'final_description' in self.fields:
                del self.fields['final_description']
        
        # Pre-select equipments from legacy field if needed
        if self.instance.pk and self.instance.equipment and not self.instance.equipments.exists():
            self.initial['equipments'] = [self.instance.equipment]

        # Dynamic filtering for hubs
        self.fields['hub'].queryset = ClientHub.objects.none()
        self.fields['hub'].empty_label = "Todas as Lojas / Sem Hub Específico"

        if 'client' in self.data:
            try:
                client_id = int(self.data.get('client'))
                self.fields['hub'].queryset = ClientHub.objects.filter(client_id=client_id).order_by('name')
            except (ValueError, TypeError):
                pass  # invalid input from the client; ignore and fallback to empty queryset
        elif self.instance.pk:
            self.fields['hub'].queryset = self.instance.client.hubs.order_by('name')

    def clean_estimated_time(self):
        data = self.cleaned_data.get('estimated_time')
        if not data:
            return None
            
        if isinstance(data, timedelta):
            return data
            
        if isinstance(data, str):
            # Try standard Django duration parsing first (if it was a DurationField)
            # But since we made it CharField, we parse manually
            
            # Check for standard HH:MM:SS
            if re.match(r'^\d+:\d+(:\d+)?$', data):
                parts = list(map(int, data.split(':')))
                if len(parts) == 2:
                    return timedelta(hours=parts[0], minutes=parts[1])
                elif len(parts) == 3:
                    return timedelta(hours=parts[0], minutes=parts[1], seconds=parts[2])
            
            # Custom formats: 2h, 2.5h, 2h30m, 30m
            data_clean = data.lower().replace(' ', '')
            total_seconds = 0
            matched = False
            
            # Extract hours
            h_match = re.search(r'(\d+(?:\.\d+)?)h', data_clean)
            if h_match:
                total_seconds += float(h_match.group(1)) * 3600
                matched = True
                
            # Extract minutes
            m_match = re.search(r'(\d+(?:\.\d+)?)m', data_clean)
            if m_match:
                total_seconds += float(m_match.group(1)) * 60
                matched = True
                
            if matched and total_seconds > 0:
                return timedelta(seconds=total_seconds)
                
            # If no custom format matched, try to interpret as int minutes if purely numeric (optional, but maybe risky)
            # Let's stick to explicit formats for now, or fallback to standard
            
        return data  # Return string if parsing failed (will cause model validation error probably)

class TicketUpdateForm(TicketForm):
    class Meta(TicketForm.Meta):
        fields = TicketForm.Meta.fields + ['finished_at']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'deadline': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'estimated_time': forms.TextInput(attrs={'placeholder': 'HH:MM:SS ou DD HH:MM:SS'}),
            'finished_at': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure the input format matches the HTML5 datetime-local requirement
        self.fields['finished_at'].input_formats = ('%Y-%m-%dT%H:%M',)

class TicketModalForm(TicketUpdateForm):
    class Meta(TicketUpdateForm.Meta):
        widgets = {
            **TicketUpdateForm.Meta.widgets,
            'systems': forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input system-switch'}),
        }

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class TicketEvolutionForm(forms.ModelForm):
    class Meta:
        model = TicketUpdate
        fields = ['description', 'image']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Descreva a evolução do atendimento...'}),
            'image': MultipleFileInput(attrs={'class': 'form-control'}),
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

class UserManagementForm(forms.ModelForm):
    first_name = forms.CharField(label="Nome Completo", max_length=150, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    username = forms.CharField(label="Login (Usuário)", max_length=150, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(label="Email", required=False, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    password = forms.CharField(label="Senha", widget=forms.PasswordInput(attrs={'class': 'form-control'}), required=False, help_text="Deixe em branco para manter a senha atual.")
    access_token = forms.CharField(label="Token de Acesso", max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}), help_text="Token único para acesso via API ou login simplificado.")
    
    # Profile fields
    role = forms.ChoiceField(label="Nível de Acesso", choices=UserProfile.ROLE_CHOICES, required=True, widget=forms.Select(attrs={'class': 'form-select'}))
    job_title = forms.CharField(label="Cargo", max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    station = forms.CharField(label="Posto de Alocação", max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    personal_phone = forms.CharField(label="Telefone Pessoal", max_length=20, required=False, widget=forms.TextInput(attrs={'class': 'form-control phone-mask'}))
    company_phone = forms.CharField(label="Telefone Empresa", max_length=20, required=False, widget=forms.TextInput(attrs={'class': 'form-control phone-mask'}))
    photo = forms.ImageField(label="Foto de Perfil", required=False, widget=forms.FileInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['first_name', 'username', 'email', 'password']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if hasattr(self.instance, 'profile'):
                self.fields['role'].initial = self.instance.profile.role
                self.fields['job_title'].initial = self.instance.profile.job_title
                self.fields['station'].initial = self.instance.profile.station
                self.fields['personal_phone'].initial = self.instance.profile.personal_phone
                self.fields['company_phone'].initial = self.instance.profile.company_phone
                self.fields['photo'].initial = self.instance.profile.photo
                self.fields['access_token'].initial = self.instance.profile.token
        else:
             self.fields['password'].required = True
             self.fields['password'].help_text = "Senha inicial para o usuário."
             import uuid
             self.fields['access_token'].initial = str(uuid.uuid4())

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
        
        if commit:
            user.save()
            # Create or update profile
            profile, created = UserProfile.objects.get_or_create(user=user)
            
            profile.role = self.cleaned_data['role']
            profile.job_title = self.cleaned_data['job_title']
            profile.station = self.cleaned_data['station']
            profile.personal_phone = self.cleaned_data['personal_phone']
            profile.company_phone = self.cleaned_data['company_phone']
            
            if self.cleaned_data.get('photo'):
                 profile.photo = self.cleaned_data['photo']
            
            if self.cleaned_data.get('access_token'):
                profile.token = self.cleaned_data['access_token']
            
            profile.save()
        return user

class SendMessageForm(forms.ModelForm):
    recipient = forms.ModelChoiceField(queryset=User.objects.all(), required=False, label="Destinatário", widget=forms.Select(attrs={'class': 'form-select select2'}))
    send_to_all = forms.BooleanField(required=False, label="Enviar para todos (Público)", widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    group = forms.ChoiceField(choices=[('', 'Selecione um grupo (opcional)'), ('technician', 'Técnicos'), ('client', 'Clientes'), ('admin', 'Administradores')], required=False, label="Enviar para Grupo", widget=forms.Select(attrs={'class': 'form-select'}))

    class Meta:
        model = Notification
        fields = ['recipient', 'title', 'message']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Assunto'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Escreva sua mensagem...'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        recipient = cleaned_data.get('recipient')
        send_to_all = cleaned_data.get('send_to_all')
        group = cleaned_data.get('group')

        if not recipient and not send_to_all and not group:
            raise forms.ValidationError("Selecione um destinatário, um grupo ou marque 'Enviar para todos'.")
        
        return cleaned_data
