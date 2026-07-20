import re
import unicodedata
from datetime import timedelta

from django import forms
from django.db.models import Q
from django.forms import inlineformset_factory
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate
from django.utils import timezone
from .models import UserProfile, Ticket, TicketUpdate, System, Client, SystemSettings, AIProviderConfig, SearchProviderConfig, VoiceProviderConfig, Notification, ClientHub, Equipment, TicketType, ProblemType, TechnicianTravel, TravelSegment, DailyChecklist, DailyChecklistItem, ChecklistTemplate, ChecklistTemplateItem, ChecklistTemplateItemOption, ContactPerson, ContactClient, ContactJumper, TicketStatus


class ContactClientForm(forms.ModelForm):
    client = forms.ModelChoiceField(
        queryset=Client.objects.all().order_by('name'),
        label="Cliente",
        required=True,
        empty_label="Selecione o cliente",
    )
    hub = forms.ModelChoiceField(
        queryset=ClientHub.objects.all().order_by('name'),
        label="Hub/Loja (opcional)",
        required=False,
        empty_label="Nenhum (cliente inteiro)",
    )

    class Meta:
        model = ContactClient
        fields = [
            "name",
            "email",
            "phone",
            "is_active",
        ]
        widgets = {
            "phone": forms.TextInput(attrs={"class": "form-control phone-mask", "placeholder": "(00) 0000-0000"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.client_ref_id:
                self.fields['client'].initial = self.instance.client_ref_id
            if self.instance.hub_ref_id:
                self.fields['hub'].initial = self.instance.hub_ref_id

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip().upper()
        return name

    def save(self, commit=True):
        contact = super().save(commit=False)
        client = self.cleaned_data.get('client')
        hub = self.cleaned_data.get('hub')
        contact.client_ref_id = client.id if client else None
        contact.client_name = client.name if client else ''
        contact.hub_ref_id = hub.id if hub else None
        contact.hub_name = hub.name if hub else ''
        if commit:
            contact.save()
        return contact


class ContactJumperForm(forms.ModelForm):
    class Meta:
        model = ContactJumper
        fields = [
            "name",
            "email",
            "phone",
            "department",
            "role",
            "is_active",
        ]
        widgets = {
            "phone": forms.TextInput(attrs={"class": "form-control phone-mask", "placeholder": "(00) 0000-0000"}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip().upper()
        return name

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
            profile = getattr(user, 'profile', None)
            blocked_until = getattr(profile, 'blocked_until', None) if profile else None
            if blocked_until and blocked_until <= timezone.now():
                user.is_active = True
                user.save(update_fields=['is_active'])
                profile.blocked_until = None
                profile.blocked_reason = None
                profile.save(update_fields=['blocked_until', 'blocked_reason'])
                return None
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
            'is_preferred'
        ]
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control phone-mask', 'placeholder': '(00) 0000-0000'}),
            'phone2': forms.TextInput(attrs={'class': 'form-control phone-mask', 'placeholder': '(00) 0000-0000'}),
            'address': forms.Textarea(attrs={'rows': 2}),
            'is_preferred': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['logo'].widget.attrs.update({'class': 'form-control'})

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip().upper()
        return name


class ClientHubForm(forms.ModelForm):
    class Meta:
        model = ClientHub
        fields = ['name', 'address', 'contact_name', 'phone', 'email', 'logo']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome do Hub/Loja'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Endereço'}),
            'contact_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Responsável'}),
            'phone': forms.TextInput(attrs={'class': 'form-control phone-mask', 'placeholder': '(00) 0000-0000'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@exemplo.com'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control form-control-sm'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip().upper()
        return name

ClientHubFormSet = forms.inlineformset_factory(
    Client, ClientHub, form=ClientHubForm,
    extra=1, can_delete=True
)


class ContactPersonForm(forms.ModelForm):
    class Meta:
        model = ContactPerson
        fields = ['name', 'email', 'phone', 'is_active']
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control form-control-sm phone-mask', 'placeholder': '(00) 0000-0000'}),
            'email': forms.EmailInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'email@exemplo.com'}),
            'name': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Nome do contato'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['is_active'].label = 'Ativo'
        self.fields['name'].required = True


ContactPersonFormSet = forms.inlineformset_factory(
    Client, ContactPerson, form=ContactPersonForm,
    extra=1, can_delete=True,
    min_num=0,
    validate_min=False,
)


class TicketStatusForm(forms.ModelForm):
    class Meta:
        model = TicketStatus
        fields = ['code', 'name', 'color', 'font_color', 'image', 'image_width', 'image_height', 'row_color', 'order', 'is_active']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: finished, in_progress'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Finalizado'}),
            'color': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '#28a745'}),
            'font_color': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '#ffffff'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control form-control-sm'}),
            'image_width': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'image_height': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'row_color': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '#6c757d'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }


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
    
    # Token
    access_token = forms.CharField(label="Token de Acesso", max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}), help_text="Token único para acesso via API ou login simplificado.")

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
                self.fields['access_token'].initial = self.instance.profile.token
                
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
            
            if self.cleaned_data.get('access_token'):
                profile.token = self.cleaned_data['access_token']
            
            if self.cleaned_data.get('photo'):
                profile.photo = self.cleaned_data['photo']
            profile.save()
        return user


class ResponsibleForm(forms.ModelForm):
    first_name = forms.CharField(label="Nome do Responsável", max_length=150, required=True)
    email = forms.EmailField(label="Email (opcional)", required=False)
    fixed_client = forms.ModelChoiceField(
        queryset=Client.objects.all().order_by('name'),
        label="Cliente",
        required=True,
        empty_label="Selecione o cliente",
    )

    class Meta:
        model = User
        fields = ['first_name', 'email']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            profile = getattr(self.instance, 'profile', None)
            if profile and profile.fixed_client_id:
                self.fields['fixed_client'].initial = profile.fixed_client_id

    def _slugify_username(self, value):
        normalized = unicodedata.normalize('NFKD', value or '')
        normalized = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
        normalized = normalized.lower()
        normalized = re.sub(r'[^a-z0-9]+', '.', normalized)
        normalized = normalized.strip('.')
        return normalized or 'user'

    def _unique_username(self, seed):
        base = self._slugify_username(seed)
        username = base
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base}{counter}"
            counter += 1
        return username

    def save(self, commit=True):
        user = super().save(commit=False)

        if not user.pk:
            seed = (self.cleaned_data.get('email') or self.cleaned_data.get('first_name') or 'user').strip()
            user.username = self._unique_username(seed)
            user.set_unusable_password()

        if commit:
            user.save()
            profile = getattr(user, 'profile', None)
            if not profile:
                profile = UserProfile(user=user)

            profile.role = 'operator'
            profile.fixed_client = self.cleaned_data.get('fixed_client')
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
        queryset=User.objects.none(),
        required=False,
        label="Responsável",
        widget=forms.SelectMultiple(attrs={'class': 'd-none', 'id': 'id_technicians'})
    )
    technician_selection = TechnicianChoiceField(
        queryset=User.objects.none(),
        required=False,
        label="Responsável",
        empty_label="Selecione um responsável",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_technician_selection'})
    )

    requesters = TechnicianMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        label="Solicitantes",
        widget=forms.SelectMultiple(attrs={'class': 'd-none', 'id': 'id_requesters'})
    )
    requester_selection = TechnicianChoiceField(
        queryset=User.objects.none(),
        required=False,
        label="Solicitante",
        empty_label="Selecione um solicitante",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_requester_selection'})
    )

    contact_client_requester = forms.ModelChoiceField(
        queryset=ContactClient.objects.filter(is_active=True).order_by("client_name", "hub_name", "name"),
        required=False,
        label="Solicitante",
        empty_label="Selecione um solicitante...",
        widget=forms.Select(attrs={"class": "form-select", "id": "id_contact_client_requester"}),
    )

    contact_jumper_responsible = forms.ModelChoiceField(
        queryset=ContactJumper.objects.filter(is_active=True).order_by("name"),
        required=False,
        label="Responsável/Executor",
        empty_label="Selecione um responsável...",
        widget=forms.Select(attrs={"class": "form-select", "id": "id_contact_jumper_responsible"}),
    )

    equipment_selection = forms.ModelChoiceField(
        queryset=Equipment.objects.all().order_by('name'),
        required=False,
        label="Adicionar Equipamento",
        empty_label="Selecione um equipamento...",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_equipment_selection'})
    )

    status = forms.ChoiceField(
        choices=[],
        label="Status",
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    ticket_type = forms.ModelChoiceField(
        queryset=TicketType.objects.all().order_by('name'),
        required=False,
        label="Tipo de Chamado",
        empty_label="Selecione o tipo de chamado"
    )

    problem_type = forms.ModelChoiceField(
        queryset=ProblemType.objects.all().order_by('name'),
        required=False,
        label="Tipo de Problema",
        empty_label="Selecione o tipo de problema"
    )

    class Meta:
        model = Ticket
        fields = [
            'client', 'hub', 'systems',
            'equipments', 'order_type', 'ticket_type', 'problem_type',
            'requesters', 'technicians',
            'contact_client_requester', 'contact_jumper_responsible',
            'start_date', 'deadline', 'estimated_time',
            'leankeep_id', 'description', 'final_description', 'status'
        ]
        widgets = {
            'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'deadline': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'systems': forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input system-switch'}),
            'hub': forms.Select(attrs={'class': 'form-select'}),
            'ticket_type': forms.Select(attrs={'class': 'form-select'}),
            'final_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Descreva o que foi feito para resolver o problema...'}),
            'equipments': forms.SelectMultiple(attrs={'class': 'd-none', 'id': 'id_equipments'}),
            'requesters': forms.SelectMultiple(attrs={'class': 'd-none', 'id': 'id_requesters'}),
            'technicians': forms.SelectMultiple(attrs={'class': 'd-none', 'id': 'id_technicians'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Status dinâmico a partir do TicketStatus
        from .models import TicketStatus
        status_qs = TicketStatus.objects.filter(is_active=True).order_by('order', 'name')
        self.fields['status'].choices = [('', 'Selecione o status')] + [(s.code, s.name) for s in status_qs]
        # Toda OS nova já nasce "Em Aberto" — o usuário pode mudar antes de salvar, mas
        # não precisa escolher manualmente todo santo dia.
        if not self.instance.pk:
            self.initial['status'] = 'open'
        self.fields['start_date'].input_formats = ('%Y-%m-%dT%H:%M',)
        self.fields['deadline'].input_formats = ('%Y-%m-%dT%H:%M',)
        self.fields['systems'].queryset = System.objects.all()

        # Garante que o responsável já salvo na OS sempre apareça no queryset (mesmo inativo)
        existing_responsible_id = getattr(self.instance, 'contact_jumper_responsible_id', None)
        if existing_responsible_id:
            self.fields['contact_jumper_responsible'].queryset = (
                ContactJumper.objects.filter(is_active=True) | ContactJumper.objects.filter(pk=existing_responsible_id)
            ).order_by('name')

        # Rename description label
        self.fields['description'].label = "Descrição Inicial"

        # Hide final_description on creation
        if not self.instance.pk:
            if 'final_description' in self.fields:
                del self.fields['final_description']
        
        # Pre-select equipments from legacy field if needed
        if self.instance.pk and self.instance.equipment and not self.instance.equipments.exists():
            self.initial['equipments'] = [self.instance.equipment]

        if self.instance.pk and self.instance.requester and not self.instance.requesters.exists():
            self.initial['requesters'] = [self.instance.requester]

        current_client = None
        client_key = self.add_prefix('client')
        raw_client_id = None
        if client_key in self.data:
            raw_client_id = self.data.get(client_key)
        elif 'client' in self.data:
            raw_client_id = self.data.get('client')

        if raw_client_id:
            try:
                client_id = int(raw_client_id)
                current_client = Client.objects.filter(id=client_id).first()
            except (ValueError, TypeError):
                current_client = None
        elif self.instance.pk:
            current_client = getattr(self.instance, 'client', None)
        else:
            initial_client = self.initial.get('client')
            if isinstance(initial_client, Client):
                current_client = initial_client
            else:
                try:
                    client_id = int(initial_client) if initial_client else None
                    if client_id:
                        current_client = Client.objects.filter(id=client_id).first()
                except (ValueError, TypeError):
                    current_client = None

        current_hub_id = None
        hub_key = self.add_prefix('hub')
        raw_hub_id = None
        if hub_key in self.data:
            raw_hub_id = self.data.get(hub_key)
        elif "hub" in self.data:
            raw_hub_id = self.data.get("hub")

        if raw_hub_id:
            try:
                current_hub_id = int(raw_hub_id) if raw_hub_id else None
            except (ValueError, TypeError):
                current_hub_id = None
        elif self.instance.pk and getattr(self.instance, "hub_id", None):
            current_hub_id = self.instance.hub_id

        # Campos obrigatórios para salvar OS (restante opcional)
        for field_name in [
            'client', 'status', 'start_date', 'deadline', 'description',
            'contact_client_requester', 'contact_jumper_responsible',
        ]:
            if field_name in self.fields:
                self.fields[field_name].required = True

        if current_client:
            qs = ContactClient.objects.filter(is_active=True, client_ref_id=current_client.id)
            if current_hub_id:
                qs = qs.filter(Q(hub_ref_id=current_hub_id) | Q(hub_ref_id__isnull=True))
            # Garante que o contato já salvo na OS sempre apareça no queryset (mesmo inativo)
            existing_requester_id = getattr(self.instance, 'contact_client_requester_id', None)
            if existing_requester_id:
                qs = qs | ContactClient.objects.filter(pk=existing_requester_id)
            self.fields["contact_client_requester"].queryset = qs.order_by("hub_name", "name")
        else:
            self.fields["contact_client_requester"].queryset = ContactClient.objects.filter(is_active=True).order_by(
                "client_name", "hub_name", "name"
            )

        if current_client:
            selected_ids = set()
            if self.instance.pk:
                selected_ids = set(self.instance.requesters.values_list('id', flat=True))
                if self.instance.requester_id:
                    selected_ids.add(self.instance.requester_id)

            requester_filter = Q(is_active=True, profile__fixed_client=current_client, profile__role='operator')
            if selected_ids:
                requester_filter |= Q(id__in=selected_ids)
            requester_qs = (
                User.objects.filter(requester_filter)
                .select_related('profile')
                .distinct()
                .order_by('first_name', 'last_name', 'username')
            )
            self.fields['requesters'].queryset = requester_qs
            self.fields['requester_selection'].queryset = requester_qs

            selected_tech_ids = set()
            if self.instance.pk:
                selected_tech_ids = set(self.instance.technicians.values_list('id', flat=True))

            tech_filter = (
                Q(is_active=True, profile__fixed_client=current_client, profile__role='operator')  # pessoas do cliente selecionado
                | Q(is_active=True, profile__fixed_client__isnull=True)  # TODOS os usuários da JumperFour (sem cliente fixo)
            )
            if selected_tech_ids:
                tech_filter |= Q(id__in=selected_tech_ids)
            tech_qs = (
                User.objects.filter(tech_filter)
                .select_related('profile')
                .distinct()
                .order_by('first_name', 'last_name', 'username')
            )
            self.fields['technicians'].queryset = tech_qs
            self.fields['technician_selection'].queryset = tech_qs

        # Dynamic filtering for hubs
        self.fields['hub'].queryset = ClientHub.objects.none()
        self.fields['hub'].empty_label = "Todas as Lojas / Sem Hub Específico"

        # Suporte a forms com prefix (ex.: modal de criação usa prefix='create')
        client_key = self.add_prefix('client')
        raw_client_id = None
        if client_key in self.data:
            raw_client_id = self.data.get(client_key)
        elif 'client' in self.data:
            raw_client_id = self.data.get('client')

        if raw_client_id:
            try:
                client_id = int(raw_client_id)
                self.fields['hub'].queryset = ClientHub.objects.filter(client_id=client_id).order_by('name')
            except (ValueError, TypeError):
                pass  # invalid input from the client; ignore and fallback to empty queryset
        elif self.instance.pk and getattr(self.instance, 'client_id', None):
            self.fields['hub'].queryset = self.instance.client.hubs.order_by('name')

    def save(self, commit=True):
        instance = super().save(commit=False)
        if "requesters" in self.data:
            requesters = self.cleaned_data.get("requesters") or []
            try:
                primary_requester = requesters[0] if isinstance(requesters, list) else next(iter(requesters), None)
            except Exception:
                primary_requester = None
            instance.requester = primary_requester

        if commit:
            instance.save()
            self.save_m2m()
        return instance

    def clean_systems(self):
        systems = self.cleaned_data.get('systems')
        if systems is not None and len(systems) > 1:
            raise forms.ValidationError("Selecione apenas 1 sistema.")
        return systems

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
            'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'deadline': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
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

class MultipleFileInput(forms.FileInput):
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
    job_title = forms.CharField(label="Cargo", max_length=100, required=False)

    class Meta:
        model = UserProfile
        # 'ai_chat_enabled' foi removido de propósito: como o template deste formulário
        # não renderiza o checkbox, o ModelForm gravava False a cada salvamento (checkbox
        # ausente = não enviado = False), fazendo o Chat IA sumir. É uma permissão
        # gerenciada apenas pela tela de Permissões.
        # 'voice_wakeword_enabled', 'tts_enabled', 'tts_voice_gender' e 'elevenlabs_voice_id'
        # são preferências do próprio usuário (diferente de ai_chat_enabled) — os campos SÃO
        # sempre renderizados em profile.html, então não sofrem o mesmo problema.
        # 'elevenlabs_voice_id' é renderizado manualmente no template (select populado via
        # JS, sem choices fixas no form) — o campo aqui só cuida da validação/salvamento.
        fields = ['photo', 'personal_phone', 'company_phone', 'job_title', 'station', 'role',
                  'voice_wakeword_enabled', 'tts_enabled', 'tts_voice_gender', 'elevenlabs_voice_id']
        widgets = {
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'job_title': forms.TextInput(attrs={'class': 'form-control'}),
            'personal_phone': forms.TextInput(attrs={'class': 'form-control phone-mask', 'placeholder': '(00) 00000-0000'}),
            'company_phone': forms.TextInput(attrs={'class': 'form-control phone-mask', 'placeholder': '(00) 0000-0000'}),
            'voice_wakeword_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'tts_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'tts_voice_gender': forms.Select(attrs={'class': 'form-select form-select-sm'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Populate user fields
        if self.instance and self.instance.pk and hasattr(self.instance, 'user'):
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['email'].initial = self.instance.user.email
            self.fields['job_title'].initial = self.instance.job_title

        # Role restriction logic
        is_admin = self.user and hasattr(self.user, 'profile') and self.user.profile.role in ['admin', 'super_admin']

        if not is_admin:
            # Hide/Disable restricted fields for non-admins
            self.fields['role'].disabled = True
            self.fields['station'].disabled = True # Assuming station is assigned by admin
            self.fields['job_title'].disabled = True

        # Escuta/resposta por voz só fazem sentido se o Chat IA estiver ativo pra este
        # usuário (ai_chat_enabled é gerenciado só pela tela de Permissões, não por este form).
        if self.instance and not getattr(self.instance, 'ai_chat_enabled', True):
            self.fields['voice_wakeword_enabled'].disabled = True
            self.fields['tts_enabled'].disabled = True

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

class TravelSegmentForm(forms.ModelForm):
    class Meta:
        model = TravelSegment
        fields = ['transport_type', 'carrier', 'transport_number', 'vehicle_details', 'origin', 'destination', 'departure_time', 'arrival_time', 'booking_code', 'locator', 'status', 'passenger_name', 'passenger_document', 'loyalty_program', 'fare_type', 'seat', 'attachment']
        widgets = {
            'transport_type': forms.Select(attrs={'class': 'form-select'}),
            'carrier': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: LATAM, GOL, Azul'}),
            'transport_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: LA3270'}),
            'vehicle_details': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Boeing 737-800'}),
            'origin': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: São Paulo (GRU)'}),
            'destination': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Recife (REC)'}),
            'departure_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'arrival_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'booking_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 9572261127853'}),
            'locator': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: UJMQZS'}),
            'status': forms.TextInput(attrs={'class': 'form-control'}),
            'passenger_name': forms.TextInput(attrs={'class': 'form-control'}),
            'passenger_document': forms.TextInput(attrs={'class': 'form-control'}),
            'loyalty_program': forms.TextInput(attrs={'class': 'form-control'}),
            'fare_type': forms.TextInput(attrs={'class': 'form-control'}),
            'seat': forms.TextInput(attrs={'class': 'form-control'}),
            'attachment': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure the input format matches the HTML5 datetime-local requirement
        self.fields['departure_time'].input_formats = ('%Y-%m-%dT%H:%M',)
        self.fields['arrival_time'].input_formats = ('%Y-%m-%dT%H:%M',)

class SystemSettingsForm(forms.ModelForm):
    class Meta:
        model = SystemSettings
        fields = [
            'session_timeout_minutes',
            'day_shift_start',
            'day_shift_end',
            'enable_night_shift',
            'night_shift_start',
            'night_shift_end',
            'ai_enabled',
        ]
        widgets = {
            'session_timeout_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '1440'}),
            'day_shift_start': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'day_shift_end': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'enable_night_shift': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
            'night_shift_start': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'night_shift_end': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'ai_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch', 'id': 'id_ai_enabled'}),
        }


class AIProviderConfigForm(forms.ModelForm):
    class Meta:
        model = AIProviderConfig
        fields = ['name', 'provider', 'model', 'api_key']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: DeepSeek principal'}),
            'provider': forms.Select(attrs={'class': 'form-select'}),
            'model': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Deixe em branco para usar o padrão'}),
            'api_key': forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'off', 'placeholder': 'sk-...'}, render_value=False),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Na edição, a chave não é obrigatória (deixar em branco mantém a atual)
        if self.instance and self.instance.pk:
            self.fields['api_key'].required = False


class SearchProviderConfigForm(forms.ModelForm):
    class Meta:
        model = SearchProviderConfig
        fields = ['name', 'provider', 'api_key', 'google_search_engine_id']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Google principal'}),
            'provider': forms.Select(attrs={'class': 'form-select'}),
            'api_key': forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'off', 'placeholder': 'Cole sua chave aqui...'}, render_value=False),
            'google_search_engine_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: a1b2c3d4e5f6g7h8i'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['api_key'].required = False


class VoiceProviderConfigForm(forms.ModelForm):
    class Meta:
        model = VoiceProviderConfig
        fields = ['name', 'provider', 'api_key', 'elevenlabs_voice_id_female', 'elevenlabs_voice_id_male']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: ElevenLabs principal'}),
            'provider': forms.Select(attrs={'class': 'form-select'}),
            'api_key': forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'off', 'placeholder': 'Cole sua chave aqui...'}, render_value=False),
            'elevenlabs_voice_id_female': forms.Select(attrs={'class': 'form-select'}),
            'elevenlabs_voice_id_male': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['api_key'].required = False
        # Os selects de voz são <select> comuns (CharField, sem choices fixas) —
        # as opções são populadas via JS (busca na API da ElevenLabs), igual ao
        # mesmo padrão já usado em profile.html.
        self.fields['elevenlabs_voice_id_female'].required = False
        self.fields['elevenlabs_voice_id_male'].required = False


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def to_python(self, data):
        if not data:
            return []
        if not isinstance(data, list):
            data = [data]
        return data

    def clean(self, data, initial=None):
        if not data and self.required:
             raise forms.ValidationError(self.error_messages['required'], code='required')
        if not data:
             return []
        return data

class BaseDailyChecklistItemForm(forms.ModelForm):
    # Field for multiple images (not bound to model directly)
    new_images = MultipleFileField(
        widget=MultipleFileInput(attrs={'class': 'form-control form-control-sm', 'multiple': True}),
        label="Adicionar Fotos",
        required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field_type = getattr(self.instance, 'field_type', None) or 'switch'

        if 'value_text' in self.fields:
            if field_type == 'select':
                raw = (getattr(self.instance, 'select_options', None) or '')
                options = [o.strip() for o in raw.splitlines() if o.strip()]
                choices = [('', 'Selecione...')] + [(o, o) for o in options]
                self.fields['value_text'].widget = forms.Select(choices=choices, attrs={'class': 'form-select'})
            elif field_type == 'text':
                self.fields['value_text'].widget = forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Digite aqui...'})
            else:
                self.fields['value_text'].widget = forms.HiddenInput()

        if 'is_checked' in self.fields and field_type in ('select', 'text', 'group', 'button'):
            self.fields['is_checked'].widget = forms.HiddenInput()


class DailyChecklistItemAdminForm(BaseDailyChecklistItemForm):
    class Meta:
        model = DailyChecklistItem
        fields = ['title', 'description', 'field_type', 'select_options', 'value_text', 'is_checked', 'observation', 'order', 'is_required', 'parent']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control fw-bold', 'placeholder': 'Título da Atividade'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Descrição da Tarefa'}),
            'is_checked': forms.CheckboxInput(attrs={'class': 'form-check-input', 'style': 'width: 2.5em; height: 1.25em;'}),
            'observation': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Observações Adicionais...'}),
            'select_options': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Uma opção por linha'}),
            'value_text': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Preencha o valor...'}),
            'field_type': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'order': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': 0}),
            'is_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'parent': forms.Select(attrs={'class': 'form-select form-select-sm'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and getattr(self.instance, 'daily_checklist_id', None):
            qs = DailyChecklistItem.objects.filter(daily_checklist_id=self.instance.daily_checklist_id).order_by('parent_id', 'order', 'id')
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            self.fields['parent'].queryset = qs
        else:
            self.fields['parent'].queryset = DailyChecklistItem.objects.none()


class DailyChecklistItemUserForm(BaseDailyChecklistItemForm):
    class Meta:
        model = DailyChecklistItem
        fields = ['is_checked', 'value_text', 'observation']
        widgets = {
            'is_checked': forms.CheckboxInput(attrs={'class': 'form-check-input', 'style': 'width: 2.5em; height: 1.25em;'}),
            'observation': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Observações Adicionais...'}),
            'value_text': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Preencha o valor...'}),
        }

class BaseDailyChecklistItemFormSet(forms.BaseInlineFormSet):
    def get_queryset(self):
        return super().get_queryset().order_by('parent_id', 'order', 'id')

    def add_fields(self, form, index):
        super().add_fields(form, index)
        if 'parent' not in form.fields:
            return
        if not getattr(self.instance, 'pk', None):
            form.fields['parent'].queryset = DailyChecklistItem.objects.none()
            return
        qs = DailyChecklistItem.objects.filter(daily_checklist_id=self.instance.pk).order_by('parent_id', 'order', 'id')
        if getattr(form.instance, 'pk', None):
            qs = qs.exclude(pk=form.instance.pk)
        form.fields['parent'].queryset = qs


class ChecklistTemplateForm(forms.ModelForm):
    class Meta:
        model = ChecklistTemplate
        fields = ['name', 'department', 'client']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'client': forms.Select(attrs={'class': 'form-select'}),
        }


class ChecklistTemplateItemForm(forms.ModelForm):
    class Meta:
        model = ChecklistTemplateItem
        fields = ['title', 'client', 'description', 'order']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'client': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }

    def __init__(self, *args, **kwargs):
        kwargs.pop('template', None)
        super().__init__(*args, **kwargs)


class ChecklistTemplateItemOptionForm(forms.ModelForm):
    class Meta:
        model = ChecklistTemplateItemOption
        fields = ['label', 'field_type', 'is_required', 'order', 'options_text']
        widgets = {
            'label': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Cliente atendido'}),
            'field_type': forms.Select(attrs={'class': 'form-select'}),
            'is_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'options_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Uma opção por linha'}),
        }


ChecklistTemplateItemOptionFormSet = forms.inlineformset_factory(
    ChecklistTemplateItem,
    ChecklistTemplateItemOption,
    form=ChecklistTemplateItemOptionForm,
    extra=0,
    can_delete=True
)

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
    # NOTA: 'ai_chat_enabled' NÃO faz parte deste formulário de propósito. É uma permissão
    # gerenciada exclusivamente pela tela de Permissões. Se fosse incluída aqui sem um
    # checkbox no template, todo salvamento (nome/senha/token) a zeraria silenciosamente.

    class Meta:
        model = User
        fields = ['first_name', 'username', 'email', 'password']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            role_levels = RoleLevel.objects.filter(is_active=True).order_by('name')
            if role_levels.exists():
                self.fields['role'].choices = [(r.code, r.name) for r in role_levels]
        except Exception:
            pass
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
            # 'ai_chat_enabled' NÃO é alterado aqui de propósito — ver nota na definição
            # do formulário. É gerenciado apenas pela tela de Permissões.

            if self.cleaned_data.get('photo'):
                 profile.photo = self.cleaned_data['photo']

            if self.cleaned_data.get('access_token'):
                profile.token = self.cleaned_data['access_token']

            profile.save()
        return user

class SendMessageForm(forms.ModelForm):
    recipient = forms.ModelChoiceField(queryset=User.objects.filter(is_active=True).order_by('first_name', 'username'), required=False, label="Destinatário", widget=forms.Select(attrs={'class': 'form-select'}))
    send_to_all = forms.BooleanField(required=False, label="Enviar para todos (Público)", widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    group = forms.ChoiceField(choices=[('', 'Selecione um grupo (opcional)'), ('technician', 'Técnicos'), ('client', 'Clientes'), ('admin', 'Administradores')], required=False, label="Enviar para Grupo", widget=forms.Select(attrs={'class': 'form-select'}))

    class Meta:
        model = Notification
        fields = ['recipient', 'title', 'message', 'urgency', 'read_receipt_requested']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Assunto'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Escreva sua mensagem...'}),
            'urgency': forms.Select(attrs={'class': 'form-select'}),
            'read_receipt_requested': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'urgency': 'Urgência',
            'read_receipt_requested': 'Solicitar confirmação de leitura',
        }

    def clean(self):
        cleaned_data = super().clean()
        recipient = cleaned_data.get('recipient')
        send_to_all = cleaned_data.get('send_to_all')
        group = cleaned_data.get('group')

        if not recipient and not send_to_all and not group:
            raise forms.ValidationError("Selecione um destinatário, um grupo ou marque 'Enviar para todos'.")
        
        return cleaned_data

class TechnicianTravelForm(forms.ModelForm):
    technician = forms.ModelChoiceField(
        queryset=User.objects.filter(profile__role__in=['technician', 'standard'], is_active=True).order_by('first_name'),
        label="Técnico Responsável",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    scheduled_date = forms.DateTimeField(
        label="Agendado para",
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'})
    )

    departure_time = forms.DateTimeField(
        label="Data/Hora Saída (Voo)",
        required=False,
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'})
    )
    arrival_time = forms.DateTimeField(
        label="Data/Hora Chegada (Voo)",
        required=False,
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'})
    )

    class Meta:
        model = TechnicianTravel
        fields = ['client', 'hub', 'scheduled_date', 'technician', 'system', 'service_order', 'multi_client', 'additional_clients', 'status', 'ticket_status', 'hotel_status', 'flight_number', 'departure_time', 'arrival_time']
        widgets = {
            'client': forms.Select(attrs={'class': 'form-select'}),
            'hub': forms.Select(attrs={'class': 'form-select'}),
            'system': forms.Select(attrs={'class': 'form-select'}),
            'service_order': forms.Select(attrs={'class': 'form-select'}),
            'multi_client': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_multi_client'}),
            'additional_clients': forms.SelectMultiple(attrs={'class': 'form-select d-none'}), # Hidden by default, managed by JS
            'status': forms.Select(attrs={'class': 'form-select'}),
            'ticket_status': forms.Select(attrs={'class': 'form-select'}),
            'hotel_status': forms.Select(attrs={'class': 'form-select'}),
            'flight_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: LATAM 3456'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Setup querysets
        if 'client' in self.data:
            try:
                client_id = int(self.data.get('client'))
                self.fields['hub'].queryset = ClientHub.objects.filter(client_id=client_id).order_by('name')
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.client:
            self.fields['hub'].queryset = self.instance.client.hubs.all().order_by('name')
        else:
            self.fields['hub'].queryset = ClientHub.objects.none()

