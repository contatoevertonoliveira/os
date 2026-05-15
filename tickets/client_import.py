import re
import unicodedata

from django.contrib.auth.models import User

from .models import Client, System, UserProfile


class ClientImporter:
    def __init__(self, stdout=None):
        self.stdout = stdout

    def write(self, text):
        if self.stdout:
            try:
                self.stdout.write(text)
            except Exception:
                pass

    def import_rows(self, rows, dry_run=False):
        processed = 0
        created = 0
        updated = 0
        for idx, row in enumerate(rows):
            try:
                result = self.process_row(row, dry_run=dry_run)
                if not result:
                    continue
                processed += 1
                if result == 'created':
                    created += 1
                elif result == 'updated':
                    updated += 1
            except Exception as e:
                self.write(f'Erro processando linha {idx}: {e}')
        return {'processed': processed, 'created': created, 'updated': updated}

    def process_row(self, row, dry_run=False):
        contract_name = str((row.get('Contrato') or '')).strip()
        if not contract_name or contract_name.lower() == 'none':
            return None

        if dry_run:
            existing = self.find_client(contract_name=contract_name, cm_code=row.get('CM'))
            action = 'created' if existing is None else 'updated'
            self.write(f'[DRY-RUN] {action.upper()} Client: {contract_name}')
            return action

        client_data = {
            'name': contract_name,
            'group': self.clean_value(row.get('Grupo')),
            'cm_code': self.clean_value(row.get('CM')),
            'periodicity': self.clean_value(row.get('Periodicidade')),
            'visits_count': self.parse_int(row.get('Visitas')),
            'emergency_policy': self.clean_value(row.get('Emergenciais')),
            'emergency_used': self.clean_value(row.get('Emergencial Utilizadas')),
            'service_hours': self.clean_value(row.get('Horário')),
            'address': self.clean_value(row.get('Endereço')),
            'city': self.clean_value(row.get('Cidade')),
            'state': self.clean_value(row.get('Estado')),
            'contact1_name': self.clean_value(row.get('Nome Cliente')),
            'contact1_email': self.clean_value(row.get('E-mail')),
            'contact1_phone': self.clean_value(row.get('Telefone')),
            'email': self.clean_value(row.get('E-mail')),
            'phone': self.clean_value(row.get('Telefone')),
            'monitoring_cso': self.clean_value(row.get('Monitoramento CSO')),
            'alarms_wpp': self.clean_value(row.get('Alarmes WPP')),
            'leankeep_assets': self.clean_value(row.get('Ativos Leankeep')),
            'maintenance_plan': self.clean_value(row.get('Plano de Manutenção')),
            'plan_review_due': self.clean_value(row.get('Data Limite para revisão')),
            'plan_review_status': self.clean_value(row.get('Revisão do plano')),
        }

        client, created = self.get_or_create_client(contract_name=contract_name, cm_code=row.get('CM'))
        action = 'created' if created else 'updated'
        for field, value in client_data.items():
            setattr(client, field, value)
        client.save()
        self.write(f'{action.upper()} Client: {client.name}')

        systems_to_set = []
        systems_str = str(row.get('Sistemas') or '').strip()
        if systems_str and systems_str.lower() != 'none':
            system_names = [s.strip() for s in re.split(r'[;,\n]', systems_str) if s.strip()]
            for sys_name in system_names:
                system_obj, _ = System.objects.get_or_create(name=sys_name)
                systems_to_set.append(system_obj)
        client.systems.set(systems_to_set)

        supervisor_name = str(row.get('Supervisor') or '').strip()
        client.supervisor = None
        if supervisor_name and supervisor_name.lower() != 'none':
            supervisor_user = self.get_or_create_user(supervisor_name)
            if supervisor_user:
                client.supervisor = supervisor_user
        client.save()

        techs_to_set = []
        techs_str = str(row.get('Técnicos Alocados') or '').strip()
        if techs_str and techs_str.lower() != 'none':
            tech_names = [t.strip() for t in re.split(r'[;,\n]', techs_str) if t.strip()]
            for tech_name in tech_names:
                tech_user = self.get_or_create_user(tech_name)
                if tech_user:
                    techs_to_set.append(tech_user)
        client.technicians.set(techs_to_set)

        contact_name = client_data.get('contact1_name')
        contact_email = client_data.get('contact1_email')
        if contact_name or contact_email:
            self.get_or_create_contact_user(contact_name, contact_email, client)

        return action

    def clean_value(self, value):
        if value is None:
            return None
        if isinstance(value, str):
            v = value.strip()
            if not v or v.lower() in {'none', 'nan', 'n/a'}:
                return None
            return v
        return value

    def parse_int(self, value):
        try:
            value_str = str(value).strip()
            if not value_str or value_str.lower() in {'none', 'nan', 'n/a'}:
                return 0
            return int(float(value_str))
        except Exception:
            return 0

    def get_or_create_client(self, contract_name, cm_code=None):
        client = self.find_client(contract_name=contract_name, cm_code=cm_code)
        if client:
            cm_code_str = self.clean_value(cm_code)
            if cm_code_str and not client.cm_code:
                client.cm_code = cm_code_str
                client.save(update_fields=['cm_code'])
            return client, False

        cm_code_str = self.clean_value(cm_code)
        client = Client.objects.create(name=contract_name, cm_code=cm_code_str)
        return client, True

    def find_client(self, contract_name, cm_code=None):
        cm_code_str = self.clean_value(cm_code)
        if cm_code_str:
            client = Client.objects.filter(name=contract_name, cm_code=cm_code_str).first()
            if client:
                return client
        return Client.objects.filter(name=contract_name).first()

    def get_or_create_user(self, full_name):
        full_name = (full_name or '').strip()
        if not full_name:
            return None

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

        username = self.slugify_username(full_name)
        existing = User.objects.filter(username=username).first()
        if existing:
            return existing

        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        user = User(username=username, first_name=first_name, last_name=last_name)
        user.set_unusable_password()
        user.save()
        if not hasattr(user, 'profile'):
            UserProfile.objects.create(user=user)
        self.write(f'Created new user: {full_name} ({username})')
        return user

    def get_or_create_contact_user(self, full_name, email, client):
        full_name = (full_name or '').strip()
        email = (email or '').strip() or None

        if not full_name and not email:
            return None

        user = None
        if email:
            user = User.objects.filter(email__iexact=email).first()

        first_name = full_name
        last_name = ''
        if full_name:
            parts = full_name.split()
            if len(parts) >= 2:
                first_name = parts[0]
                last_name = ' '.join(parts[1:])

        if not user and full_name:
            user = (
                User.objects.filter(first_name__iexact=first_name, last_name__iexact=last_name)
                .select_related('profile')
                .first()
            )

        if not user:
            username_seed = email or full_name
            username = self.slugify_username(username_seed)
            existing = User.objects.filter(username=username).first()
            if existing:
                user = existing
            else:
                base_username = username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1
                user = User(username=username, first_name=first_name, last_name=last_name)
                if email:
                    user.email = email
                user.set_unusable_password()
                user.save()
                self.write(f'Created new contact user: {full_name or email} ({username})')

        user_changed = False
        if email and (not (user.email or '').strip()):
            user.email = email
            user_changed = True
        if full_name and (not (user.first_name or '').strip()) and (not (user.last_name or '').strip()):
            user.first_name = first_name
            user.last_name = last_name
            user_changed = True
        if user_changed:
            user.save()

        profile = getattr(user, 'profile', None)
        if not profile:
            profile = UserProfile.objects.create(user=user)

        profile_changed = False
        if client and profile.fixed_client_id != client.id:
            profile.fixed_client = client
            profile_changed = True
        if not (profile.role or '').strip():
            profile.role = 'standard'
            profile_changed = True
        if profile_changed:
            profile.save()

        return user

    def slugify_username(self, value):
        normalized = unicodedata.normalize('NFKD', value)
        normalized = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
        normalized = normalized.lower()
        normalized = re.sub(r'[^a-z0-9]+', '.', normalized)
        normalized = normalized.strip('.')
        return normalized or 'user'

