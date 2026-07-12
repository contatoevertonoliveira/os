from django.contrib import admin
from .models import Client, Ticket, TicketType, ClientHub, Equipment, EquipmentType, OrderType, ProblemType, System, SystemSettings, AIProviderConfig, UserProfile, TechnicianTravel, ChecklistTemplate, ChecklistTemplateItem, DailyChecklist, DailyChecklistItem, ContactPerson, AIChatSession, AIChatMessage, AIUserMemory, PrivateChatThread, PrivateChatMessage, AITicketBatchDraft

@admin.register(TechnicianTravel)
class TechnicianTravelAdmin(admin.ModelAdmin):
    list_display = ('technician', 'client', 'scheduled_date', 'status', 'ticket_status', 'hotel_status')
    list_filter = ('status', 'ticket_status', 'hotel_status', 'technician')
    search_fields = ('technician__username', 'client__name', 'service_order__id')
    actions = ['mark_as_completed']

    @admin.action(description='Marcar viagens selecionadas como Concluídas')
    def mark_as_completed(self, request, queryset):
        queryset.update(status='completed')
        self.message_user(request, f"{queryset.count()} viagens marcadas como concluídas.")

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'technician_type', 'fixed_client', 'fixed_hub', 'job_title')
    list_filter = ('role', 'technician_type', 'fixed_client')
    search_fields = ('user__username', 'user__first_name', 'job_title', 'fixed_client__name', 'fixed_hub__name')

@admin.register(ClientHub)
class ClientHubAdmin(admin.ModelAdmin):
    list_display = ('name', 'client', 'contact_name', 'phone', 'has_logo')
    list_filter = ('client',)
    search_fields = ('name', 'client__name', 'contact_name')

    def has_logo(self, obj):
        return bool(obj.logo)
    has_logo.boolean = True
    has_logo.short_description = 'Logo?'

@admin.register(TicketType)
class TicketTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone')
    search_fields = ('name', 'email')

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'client', 'get_technicians', 'status', 'created_at')
    list_filter = ('status', 'technicians', 'created_at')
    search_fields = ('client__name', 'description')

    def get_technicians(self, obj):
        return ", ".join([t.username for t in obj.technicians.all()])
    get_technicians.short_description = 'Técnicos'

class ChecklistTemplateItemInline(admin.TabularInline):
    model = ChecklistTemplateItem
    extra = 1

@admin.register(ChecklistTemplate)
class ChecklistTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'department', 'created_at')
    search_fields = ('name', 'department')
    inlines = [ChecklistTemplateItemInline]

class DailyChecklistItemInline(admin.TabularInline):
    model = DailyChecklistItem
    extra = 0
    readonly_fields = ('description', 'is_checked', 'image', 'observation')
    can_delete = False

@admin.register(DailyChecklist)
class DailyChecklistAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'template', 'status', 'created_at')
    list_filter = ('date', 'user', 'template', 'status')
    search_fields = ('user__username', 'template__name')
    inlines = [DailyChecklistItemInline]

@admin.register(ContactPerson)
class ContactPersonAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_client', 'origin', 'email', 'phone', 'is_active')
    list_filter = ('origin', 'is_active', 'client', 'created_at')
    search_fields = ('name', 'email', 'phone', 'client__name')
    readonly_fields = ('created_at', 'updated_at')

    def get_client(self, obj):
        return obj.client.name if obj.client else "Sem cliente"
    get_client.short_description = 'Cliente'

@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ('session_timeout_minutes', 'allow_checklist_pdf_debug')

    def has_add_permission(self, request):
        # Only allow adding if no instance exists
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)


@admin.register(AIProviderConfig)
class AIProviderConfigAdmin(admin.ModelAdmin):
    list_display = ('name', 'provider', 'model', 'is_active', 'updated_at')
    list_filter = ('provider', 'is_active')


class AIChatMessageInline(admin.TabularInline):
    model = AIChatMessage
    extra = 0
    readonly_fields = ('role', 'content', 'created_at')
    can_delete = False


@admin.register(AIChatSession)
class AIChatSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'created_at', 'updated_at')
    list_filter = ('user',)
    search_fields = ('user__username', 'title')
    inlines = [AIChatMessageInline]
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AIUserMemory)
class AIUserMemoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'updated_at')
    search_fields = ('user__username', 'user__first_name', 'notes')
    readonly_fields = ('updated_at',)


class PrivateChatMessageInline(admin.TabularInline):
    model = PrivateChatMessage
    extra = 0
    readonly_fields = ('sender', 'content', 'is_ai_message', 'created_at')
    can_delete = False


@admin.register(PrivateChatThread)
class PrivateChatThreadAdmin(admin.ModelAdmin):
    list_display = ('user_a', 'user_b', 'created_at', 'updated_at')
    search_fields = ('user_a__username', 'user_b__username')
    inlines = [PrivateChatMessageInline]
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AITicketBatchDraft)
class AITicketBatchDraftAdmin(admin.ModelAdmin):
    list_display = ('user', 'total_count', 'status', 'created_at', 'updated_at')
    list_filter = ('status',)
    search_fields = ('user__username',)
    readonly_fields = ('created_at', 'updated_at')
