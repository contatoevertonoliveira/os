import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jumperfour.settings')
django.setup()

from tickets.models import System

systems_data = [
    {'name': 'BMS', 'color': '#0d6efd', 'description': 'Building Management System'},
    {'name': 'CFTV', 'color': '#6610f2', 'description': 'Circuito Fechado de TV'},
    {'name': 'COMBATE INCENDIO', 'color': '#dc3545', 'description': 'Sistema de Combate a Incêndio'},
    {'name': 'CONTROLE FUMAÇA', 'color': '#fd7e14', 'description': 'Sistema de Controle de Fumaça'},
    {'name': 'SCA', 'color': '#198754', 'description': 'Sistema de Controle de Acesso'},
    {'name': 'SDAI', 'color': '#ffc107', 'description': 'Sistema de Detecção e Alarme de Incêndio'},
]

print("Populating systems...")
for data in systems_data:
    system, created = System.objects.get_or_create(
        name=data['name'],
        defaults={
            'color': data['color'],
            'description': data['description']
        }
    )
    if created:
        print(f"Created: {system.name}")
    else:
        print(f"Already exists: {system.name}")
        # Update color if needed
        if system.color != data['color']:
            system.color = data['color']
            system.save()
            print(f"Updated color for: {system.name}")

print("Done.")
