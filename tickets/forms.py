from django import forms
from django.contrib.auth.models import User
from .models import UserProfile, Ticket

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
            
            profile.role = 'standard'
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
        queryset=User.objects.filter(profile__role='standard'),
        required=False,
        label="Técnico Responsável",
        empty_label="Selecione um técnico"
    )

    class Meta:
        model = Ticket
        fields = ['client', 'order_type', 'equipment', 'problem_type', 'technician', 'description', 'status']

class TicketUpdateForm(TicketForm):
    class Meta(TicketForm.Meta):
        fields = TicketForm.Meta.fields + ['finished_at']
        widgets = {
            'finished_at': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure the input format matches the HTML5 datetime-local requirement
        self.fields['finished_at'].input_formats = ('%Y-%m-%dT%H:%M',)
