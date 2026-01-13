from django.contrib import admin
from .models import Client, Ticket, TicketType

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
