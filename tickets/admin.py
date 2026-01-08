from django.contrib import admin
from .models import Client, Ticket

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone')
    search_fields = ('name', 'email')

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'client', 'technician', 'status', 'created_at')
    list_filter = ('status', 'technician', 'created_at')
    search_fields = ('client__name', 'description')
