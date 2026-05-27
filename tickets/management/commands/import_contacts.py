from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
from django.db.models import Q
import os
import csv
import re
from openpyxl import load_workbook
from tickets.models import Client, ClientHub, ContactClient, ContactJumper


class Command(BaseCommand):
    help = 'Importa contatos: /dados/clientes.csv -> ContactClient e JUMPERFOUR.xlsx -> ContactJumper'

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(self.style.SUCCESS('IMPORTANDO CONTATOS'))
        self.stdout.write(self.style.SUCCESS('='*60))
        
        self.stdout.write('\nImportando contatos dos clientes (clientes.csv)...')
        imported_clients = self.import_client_contacts_csv()
        self.stdout.write(f'Total de contatos de clientes importados: {imported_clients}\n')
        
        self.stdout.write('Importando contatos da planilha JumperFour...')
        imported_jumperfour = self.import_jumperfour_contacts()
        self.stdout.write(f'Total de contatos JumperFour importados: {imported_jumperfour}\n')
        
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(self.style.SUCCESS(f'Total importado: {imported_clients + imported_jumperfour} contatos'))
        self.stdout.write(self.style.SUCCESS('='*60))

    def _first_existing_path(self, candidates):
        for p in candidates:
            if p and os.path.exists(p):
                return p
        return None

    def _pick_col(self, df, candidates):
        cols = {str(c).strip().lower(): c for c in df.columns}
        for cand in candidates:
            key = str(cand).strip().lower()
            if key in cols:
                return cols[key]
        for cand in candidates:
            cand_norm = str(cand).strip().lower()
            for k, original in cols.items():
                if cand_norm in k:
                    return original
        return None

    def _clean_cell(self, value):
        if value is None:
            return ""
        s = str(value).strip()
        if s.lower() in {"nan", "none", "null"}:
            return ""
        return s

    def _normalize_space(self, value):
        value = (value or "").strip()
        value = re.sub(r"\s+", " ", value)
        return value.strip()

    def _cleanup_hub_name_duplicates(self, client_obj):
        if not client_obj:
            return

        hubs = list(ClientHub.objects.filter(client=client_obj).order_by("id"))
        canonical_by_norm = {}

        for hub in hubs:
            norm = self._normalize_space(hub.name).upper()
            if not norm:
                continue
            canonical = canonical_by_norm.get(norm)
            if not canonical:
                if hub.name != self._normalize_space(hub.name):
                    hub.name = self._normalize_space(hub.name)
                    hub.save(update_fields=["name"])
                canonical_by_norm[norm] = hub
                continue

            from tickets.models import Ticket, TechnicianTravel, UserProfile

            Ticket.objects.filter(hub=hub).update(hub=canonical)
            TechnicianTravel.objects.filter(hub=hub).update(hub=canonical)
            UserProfile.objects.filter(fixed_hub=hub).update(fixed_hub=canonical)
            ContactClient.objects.filter(hub_ref_id=hub.id).update(hub_ref_id=canonical.id, hub_name=canonical.name)
            hub.delete()

    def _prune_unused_hubs(self, client_obj, allowed_hub_names):
        if not client_obj:
            return 0

        allowed_norm = {self._normalize_space(n).upper() for n in (allowed_hub_names or set()) if self._normalize_space(n)}
        if not allowed_norm:
            return 0

        from tickets.models import Ticket, TechnicianTravel, UserProfile

        removed = 0
        for hub in ClientHub.objects.filter(client=client_obj).order_by("name"):
            hub_norm = self._normalize_space(hub.name).upper()
            if not hub_norm or hub_norm in allowed_norm:
                continue

            used = (
                Ticket.objects.filter(hub=hub).exists()
                or TechnicianTravel.objects.filter(hub=hub).exists()
                or UserProfile.objects.filter(fixed_hub=hub).exists()
                or ContactClient.objects.filter(hub_ref_id=hub.id).exists()
            )
            if used:
                continue

            hub.delete()
            removed += 1

        return removed

    def import_client_contacts_csv(self):
        imported = 0

        base_dir = str(getattr(settings, "BASE_DIR", os.getcwd()))
        csv_path = self._first_existing_path(
            [
                os.path.join(base_dir, "dados", "clientes.csv"),
                os.path.join(base_dir, "data", "clientes.csv"),
                os.path.join(base_dir, "clientes.csv"),
                os.path.join(os.getcwd(), "dados", "clientes.csv"),
                os.path.join(os.getcwd(), "data", "clientes.csv"),
            ]
        )

        if not csv_path:
            self.stdout.write(self.style.WARNING("  Arquivo clientes.csv nao encontrado em /dados ou /data"))
            return 0

        rows = None
        encoding_used = None
        for enc in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                with open(csv_path, "r", encoding=enc, newline="") as f:
                    sample = f.read(4096)
                    f.seek(0)
                    try:
                        dialect = csv.Sniffer().sniff(sample, delimiters=";,|\t")
                    except Exception:
                        dialect = csv.excel
                        dialect.delimiter = ";"
                    reader = csv.DictReader(f, dialect=dialect)
                    rows = list(reader)
                    encoding_used = enc
                    break
            except Exception:
                rows = None
                encoding_used = None

        if rows is None:
            self.stdout.write(self.style.WARNING(f"  Nao foi possivel ler o arquivo: {csv_path}"))
            return 0

        header_keys = list(rows[0].keys()) if rows else []
        header_norm = {str(k).strip().lower(): k for k in header_keys}

        def pick_key(candidates):
            for cand in candidates:
                key = str(cand).strip().lower()
                if key in header_norm:
                    return header_norm[key]
            for cand in candidates:
                cand_norm = str(cand).strip().lower()
                for k_norm, original in header_norm.items():
                    if cand_norm in k_norm:
                        return original
            return None

        group_col = pick_key(["grupo"])
        contract_col = pick_key(["contrato"])
        person_col = pick_key(["nome cliente", "nome do cliente", "contato", "nome"])
        email_col = pick_key(["e-mail", "email", "mail"])
        phone_col = pick_key(["telefone", "fone", "celular", "phone"])

        if not group_col or not contract_col or not person_col:
            self.stdout.write(self.style.WARNING("  Colunas minimas nao encontradas (grupo + contrato + nome cliente)"))
            return 0

        self.stdout.write(f"  Lendo CSV: {os.path.basename(csv_path)} (encoding={encoding_used})")

        claro_hubs_seen = set()
        xp_hubs_seen = set()

        for row in rows:
            group = self._clean_cell(row.get(group_col))
            contract = self._clean_cell(row.get(contract_col))
            name = self._clean_cell(row.get(person_col))
            email = self._clean_cell(row.get(email_col)) if email_col else ""
            phone = self._clean_cell(row.get(phone_col)) if phone_col else ""

            if not group or not contract or not name:
                continue

            group_upper = group.strip().upper()
            contract_clean = contract.strip()

            client_name_final = contract_clean
            hub_name_final = ""

            if group_upper == "CLARO":
                client_name_final = "CLARO"
                hub_name_final = contract_clean
            elif contract_clean.upper().startswith("XP ") or group_upper in {"XPINC", "ESPAÇO XP", "ESPACO XP"}:
                client_name_final = "XP Investimentos S/A"
                hub_name_final = contract_clean
                if hub_name_final.upper().startswith("XP "):
                    hub_name_final = hub_name_final[3:].strip()
            else:
                client_name_final = contract_clean
                hub_name_final = ""

            client_name_final = self._normalize_space(client_name_final)
            hub_name_final = self._normalize_space(hub_name_final)

            if client_name_final.upper() == "CLARO" and hub_name_final:
                claro_hubs_seen.add(hub_name_final)
            if client_name_final.upper().startswith("XP INVESTIMENTOS") and hub_name_final:
                xp_hubs_seen.add(hub_name_final)

            client_obj = Client.objects.filter(name__iexact=client_name_final).first()
            if not client_obj and client_name_final:
                client_obj = Client.objects.filter(name__icontains=client_name_final).first()

            hub_obj = None
            if client_obj and hub_name_final:
                hub_obj = ClientHub.objects.filter(client=client_obj, name__iexact=hub_name_final).first()
                if not hub_obj:
                    hub_obj = ClientHub.objects.create(client=client_obj, name=hub_name_final)

            defaults = {
                "email": email or None,
                "phone": phone or None,
                "client_ref_id": getattr(client_obj, "id", None),
                "client_name": (client_obj.name if client_obj else client_name_final) or "",
                "hub_ref_id": getattr(hub_obj, "id", None),
                "hub_name": (hub_obj.name if hub_obj else hub_name_final) or "",
                "is_active": True,
            }

            qs = ContactClient.objects.filter(name__iexact=name)
            if defaults["email"]:
                qs = qs.filter(email__iexact=defaults["email"])
            else:
                qs = qs.filter(Q(email__isnull=True) | Q(email=""))

            if defaults["hub_ref_id"]:
                qs = qs.filter(Q(hub_ref_id=defaults["hub_ref_id"]) | Q(hub_name__iexact=defaults["hub_name"]))
            else:
                qs = qs.filter(Q(hub_ref_id__isnull=True) | Q(hub_name__isnull=True) | Q(hub_name=""))

            if defaults["client_ref_id"]:
                qs = qs.filter(Q(client_ref_id=defaults["client_ref_id"]) | Q(client_name__iexact=defaults["client_name"]) | Q(client_name__iexact=name))
            else:
                qs = qs.filter(Q(client_ref_id__isnull=True) | Q(client_name__iexact=defaults["client_name"]) | Q(client_name__iexact=name))

            contact = qs.first()
            created = False
            if not contact:
                contact = ContactClient(**defaults, name=name)
                contact.save()
                created = True

            changed = False
            for k, v in defaults.items():
                if getattr(contact, k) != v:
                    setattr(contact, k, v)
                    changed = True
            if changed:
                contact.save()

            if created:
                imported += 1

        claro = Client.objects.filter(name__iexact="CLARO").first()
        xp = Client.objects.filter(name__icontains="XP Investimentos").first()

        self._cleanup_hub_name_duplicates(claro)
        self._cleanup_hub_name_duplicates(xp)

        removed_claro = self._prune_unused_hubs(claro, claro_hubs_seen)
        removed_xp = self._prune_unused_hubs(xp, xp_hubs_seen)

        if removed_claro:
            self.stdout.write(f"  Hubs removidos (CLARO, sem uso e fora do CSV): {removed_claro}")
        if removed_xp:
            self.stdout.write(f"  Hubs removidos (XP, sem uso e fora do CSV): {removed_xp}")

        return imported

    def import_jumperfour_contacts(self):
        base_dir = str(getattr(settings, "BASE_DIR", os.getcwd()))
        xlsx_path = self._first_existing_path(
            [
                os.path.join(base_dir, "data", "JUMPERFOUR.xlsx"),
                os.path.join(base_dir, "JUMPERFOUR.xlsx"),
                os.path.join(os.getcwd(), "data", "JUMPERFOUR.xlsx"),
            ]
        )

        if not xlsx_path:
            self.stdout.write(self.style.WARNING("  Arquivo JUMPERFOUR.xlsx nao encontrado"))
            return 0

        try:
            wb = load_workbook(xlsx_path, data_only=True)
        except Exception:
            self.stdout.write(self.style.WARNING(f"  Nao foi possivel ler o arquivo: {xlsx_path}"))
            return 0

        ws = wb.active
        values = list(ws.values)
        if not values:
            return 0

        headers = [self._clean_cell(h) for h in values[0]]
        header_norm = {str(h).strip().lower(): idx for idx, h in enumerate(headers) if str(h).strip()}

        def pick_idx(candidates):
            for cand in candidates:
                key = str(cand).strip().lower()
                if key in header_norm:
                    return header_norm[key]
            for cand in candidates:
                cand_norm = str(cand).strip().lower()
                for k_norm, idx in header_norm.items():
                    if cand_norm in k_norm:
                        return idx
            return None

        name_idx = pick_idx(["*nome", "nome", "name"])
        email_idx = pick_idx(["email", "e-mail", "mail"])
        phone_idx = pick_idx(["telefone", "fone", "celular", "phone"])
        dept_idx = pick_idx(["departamento", "dept"])
        role_idx = pick_idx(["cargo", "função", "funcao", "role"])

        if name_idx is None:
            self.stdout.write(self.style.WARNING("  Coluna de nome nao encontrada na planilha JUMPERFOUR.xlsx"))
            return 0

        imported = 0
        for row in values[1:]:
            name = self._clean_cell(row[name_idx] if name_idx < len(row) else "")
            email = self._clean_cell(row[email_idx] if email_idx is not None and email_idx < len(row) else "")
            phone = self._clean_cell(row[phone_idx] if phone_idx is not None and phone_idx < len(row) else "")
            department = self._clean_cell(row[dept_idx] if dept_idx is not None and dept_idx < len(row) else "")
            role = self._clean_cell(row[role_idx] if role_idx is not None and role_idx < len(row) else "")

            if not name:
                continue

            contact, created = ContactJumper.objects.get_or_create(
                name=name,
                email=email or None,
                defaults={
                    "phone": phone or None,
                    "department": department or "",
                    "role": role or "",
                    "is_active": True,
                },
            )

            if created:
                imported += 1
                self.stdout.write(f"  Importado: {contact.name} (JumperFour)")
            else:
                changed = False
                updates = {
                    "phone": phone or None,
                    "department": department or "",
                    "role": role or "",
                    "is_active": True,
                }
                for k, v in updates.items():
                    if getattr(contact, k) != v:
                        setattr(contact, k, v)
                        changed = True
                if changed:
                    contact.save()

        return imported
