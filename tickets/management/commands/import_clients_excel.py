import pandas as pd
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from tickets.models import Client, System, UserProfile, ClientHub
import os
import re

class Command(BaseCommand):
    help = 'Imports clients from media/clientes.xlsx'

    def handle(self, *args, **options):
        # Try data/ first (for deployment), then media/ (legacy/local)
        file_path = 'data/clientes.xlsx'
        if not os.path.exists(file_path):
            file_path = 'media/clientes.xlsx'
        
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'File not found in data/ or media/: clientes.xlsx'))
            return

        try:
            self.stdout.write(self.style.SUCCESS(f'Reading from {file_path}...'))
            df = pd.read_excel(file_path)
            # Replace NaN with None/Empty string
            df = df.where(pd.notnull(df), None)
            
            self.stdout.write(self.style.SUCCESS(f'Found {len(df)} rows to process.'))

            for index, row in df.iterrows():
                try:
                    self.process_row(row)
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error processing row {index}: {e}'))

            self.stdout.write(self.style.SUCCESS('Import completed successfully.'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Critical error: {e}'))

    def process_row(self, row):
        # 1. Extract basic data
        contract_name = str(row.get('Contrato', '')).strip()
        if not contract_name or contract_name == 'None':
            return

        client_data = {
            'name': contract_name,
            'group': row.get('Grupo'),
            'cm_code': row.get('CM'),
            'periodicity': row.get('Periodicidade'),
            'visits_count': self.parse_int(row.get('Visitas')),
            'service_hours': row.get('Horário'),
            'address': row.get('Endereço'),
            'city': row.get('Cidade'),
            'state': row.get('Estado'),
            'contact1_name': row.get('Nome Cliente'),
            'contact1_email': row.get('E-mail'),
            'contact1_phone': row.get('Telefone'),
        }

        # 2. Get or Create Client
        client, created = Client.objects.update_or_create(
            name=contract_name,
            defaults=client_data
        )
        action = "Created" if created else "Updated"
        self.stdout.write(f'{action} Client: {client.name}')

        # 3. Handle Systems (Sistemas)
        systems_str = str(row.get('Sistemas', '')).strip()
        if systems_str and systems_str != 'None':
            system_names = [s.strip() for s in re.split(r'[;,\n]', systems_str) if s.strip()]
            for sys_name in system_names:
                system_obj, _ = System.objects.get_or_create(name=sys_name)
                client.systems.add(system_obj)

        # 4. Handle Supervisor
        supervisor_name = str(row.get('Supervisor', '')).strip()
        if supervisor_name and supervisor_name != 'None':
            supervisor_user = self.get_or_create_user(supervisor_name, role='supervisor')
            if supervisor_user:
                client.supervisor = supervisor_user
                client.save()

        # 5. Handle Technicians (Técnicos Alocados)
        techs_str = str(row.get('Técnicos Alocados', '')).strip()
        if techs_str and techs_str != 'None':
            tech_names = [t.strip() for t in re.split(r'[;,\n]', techs_str) if t.strip()]
            for tech_name in tech_names:
                tech_user = self.get_or_create_user(tech_name, role='technician')
                if tech_user:
                    client.technicians.add(tech_user)

    def parse_int(self, value):
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    def get_or_create_user(self, full_name, role='technician'):
        if not full_name:
            return None
        
        # Try to match by full name (case insensitive)
        # Note: This is a simple matching strategy. 
        parts = full_name.split()
        if len(parts) >= 2:
            first_name = parts[0]
            last_name = ' '.join(parts[1:])
        else:
            first_name = full_name
            last_name = ''

        users = User.objects.filter(first_name__iexact=first_name, last_name__iexact=last_name)
        if users.exists():
            return users.first()
        
        # Try matching username (generate a username)
        username = full_name.lower().replace(' ', '.')
        try:
            user = User.objects.get(username=username)
            return user
        except User.DoesNotExist:
            pass

        # Create new user
        try:
            # Check if username exists, if so append random number
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1

            user = User.objects.create_user(
                username=username,
                first_name=first_name,
                last_name=last_name,
                email=f"{username}@example.com", # Placeholder email
                password='defaultpassword123'
            )
            
            # Create UserProfile if not exists
            if not hasattr(user, 'profile'):
                UserProfile.objects.create(user=user)
            
            self.stdout.write(self.style.WARNING(f'Created new user: {full_name} ({username})'))
            return user
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error creating user {full_name}: {e}'))
            return None
