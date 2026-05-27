from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
import re

from tickets.models import Client, ClientHub, Ticket, TechnicianTravel, UserProfile, ContactPerson, ContactClient


class Command(BaseCommand):
    help = "Converte clientes siglas (BREAG..SPOVMN) em Hubs/Lojas do cliente CLARO e move referencias."

    def add_arguments(self, parser):
        parser.add_argument("--from", dest="from_code", default="BREAG")
        parser.add_argument("--to", dest="to_code", default="SPOVMN")
        parser.add_argument("--client-name", dest="client_name", default="CLARO")
        parser.add_argument("--source-prefix", dest="source_prefix", default="")
        parser.add_argument("--source-suffix", dest="source_suffix", default="")
        parser.add_argument("--exclude", dest="exclude_names", action="append", default=[])
        parser.add_argument("--hub-name-mode", dest="hub_name_mode", choices=["code", "after_prefix", "full"], default="code")
        parser.add_argument("--hub-strip-suffix", dest="hub_strip_suffix", default="")
        parser.add_argument("--dry-run", action="store_true", default=False)
        parser.add_argument("--delete-old", action="store_true", default=True)

    def _is_code(self, value):
        value = (value or "").strip()
        return bool(re.fullmatch(r"[A-Z]{5,6}", value))

    def _in_range(self, value, start, end):
        value = (value or "").strip()
        return start <= value <= end

    def _find_target_client(self, name):
        exact = Client.objects.filter(name__iexact=name).first()
        if exact:
            return exact
        norm = self._normalize_key(name)
        if norm:
            for c in Client.objects.all().only("id", "name"):
                if self._normalize_key(c.name) == norm:
                    return c
        return Client.objects.filter(name__icontains=name).first()

    def _normalize_key(self, value):
        value = (value or "").strip().upper()
        return re.sub(r"[^A-Z0-9]+", "", value)

    def _build_hub_name(self, old_name, hub_name_mode, source_prefix, hub_strip_suffix):
        old_name = (old_name or "").strip()
        name = old_name
        if hub_name_mode == "after_prefix" and source_prefix:
            if name.upper().startswith(source_prefix.upper()):
                name = name[len(source_prefix) :].strip()
        elif hub_name_mode == "code":
            name = old_name.strip()
        elif hub_name_mode == "full":
            name = old_name.strip()

        name = re.sub(r"\s+", " ", name).strip()
        if hub_strip_suffix:
            suffix = hub_strip_suffix.strip()
            if suffix and name.upper().endswith(suffix.upper()):
                name = name[: -len(suffix)].strip()
                name = re.sub(r"\s+", " ", name).strip()
        return name or old_name.strip()

    @transaction.atomic
    def handle(self, *args, **options):
        start = (options.get("from_code") or "BREAG").strip().upper()
        end = (options.get("to_code") or "SPOVMN").strip().upper()
        target_name = (options.get("client_name") or "CLARO").strip()
        source_prefix = (options.get("source_prefix") or "").strip()
        source_suffix = (options.get("source_suffix") or "").strip()
        exclude_names = [str(x).strip() for x in (options.get("exclude_names") or []) if str(x).strip()]
        hub_name_mode = (options.get("hub_name_mode") or "code").strip()
        hub_strip_suffix = (options.get("hub_strip_suffix") or "").strip()
        dry_run = bool(options.get("dry_run"))
        delete_old = bool(options.get("delete_old"))

        candidates = []
        for c in Client.objects.all().only("id", "name"):
            name = (c.name or "").strip()
            if source_prefix:
                if not name.upper().startswith(source_prefix.upper()):
                    continue
                if source_suffix and not name.upper().endswith(source_suffix.upper()):
                    continue
                if exclude_names and any(name.lower() == ex.lower() for ex in exclude_names):
                    continue
                if name.lower() == target_name.lower():
                    continue
                candidates.append(c.id)
            else:
                if self._is_code(name) and self._in_range(name, start, end):
                    candidates.append(c.id)

        clients = list(Client.objects.filter(id__in=candidates).order_by("name"))

        target = self._find_target_client(target_name)
        if not target:
            target = Client(name=target_name)
            if not dry_run:
                target.save()
            self.stdout.write(f"Criado cliente alvo: {target_name}")
        else:
            if not dry_run and (target.name or "").strip() != target_name and self._normalize_key(target.name) == self._normalize_key(target_name):
                target.name = target_name
                target.save(update_fields=["name"])
            self.stdout.write(f"Cliente alvo: {target.name} (id={target.id})")

        if source_prefix:
            self.stdout.write(f"Encontrados {len(clients)} clientes com prefixo '{source_prefix}'.")
        else:
            self.stdout.write(f"Encontrados {len(clients)} clientes-codigo entre {start} e {end}.")

        if not clients:
            if dry_run:
                return
            if source_prefix and hub_name_mode == "after_prefix":
                cleaned = 0
                merged = 0
                prefixed_hubs = list(ClientHub.objects.filter(client=target, name__istartswith=source_prefix).order_by("name"))
                for h in prefixed_hubs:
                    stripped = self._build_hub_name(h.name, "after_prefix", source_prefix, hub_strip_suffix)
                    if not stripped:
                        continue
                    existing = ClientHub.objects.filter(client=target, name__iexact=stripped).exclude(id=h.id).first()
                    if existing:
                        Ticket.objects.filter(hub=h).update(hub=existing)
                        TechnicianTravel.objects.filter(hub=h).update(hub=existing)
                        UserProfile.objects.filter(fixed_hub=h).update(fixed_hub=existing)
                        h.delete()
                        merged += 1
                        continue
                    if h.name != stripped:
                        h.name = stripped
                        h.save(update_fields=["name"])
                        cleaned += 1
                if prefixed_hubs:
                    self.stdout.write(f"Cleanup hubs com prefixo '{source_prefix}': renomeados={cleaned} removidos/mesclados={merged}")
            return

        hub_by_code = {}
        for old in clients:
            hub_name = self._build_hub_name(old.name, hub_name_mode, source_prefix, hub_strip_suffix)
            hub = ClientHub.objects.filter(client=target, name__iexact=hub_name).first()
            if not hub:
                hub = ClientHub(client=target, name=hub_name)
                if not dry_run:
                    hub.save()
            hub_by_code[old.id] = hub

        moved_tickets = 0
        moved_travels = 0
        moved_profiles = 0
        moved_contacts = 0
        moved_contactclients = 0

        for old in clients:
            hub = hub_by_code[old.id]

            qs_tickets = Ticket.objects.filter(client=old)
            if not dry_run:
                for t in qs_tickets.select_related("hub"):
                    t.client = target
                    if not t.hub_id:
                        t.hub = hub
                    t.save(update_fields=["client", "hub"])
            moved_tickets += qs_tickets.count()

            qs_travels = TechnicianTravel.objects.filter(client=old)
            if not dry_run:
                for tr in qs_travels.select_related("hub"):
                    tr.client = target
                    if not tr.hub_id:
                        tr.hub = hub
                    tr.save(update_fields=["client", "hub"])
            moved_travels += qs_travels.count()

            qs_profiles = UserProfile.objects.filter(fixed_client=old)
            if not dry_run:
                for p in qs_profiles.select_related("fixed_hub"):
                    p.fixed_client = target
                    if not p.fixed_hub_id:
                        p.fixed_hub = hub
                    p.save(update_fields=["fixed_client", "fixed_hub"])
            moved_profiles += qs_profiles.count()

            qs_cp = ContactPerson.objects.filter(client=old)
            if not dry_run:
                qs_cp.update(client=target)
            moved_contacts += qs_cp.count()

            qs_cc = ContactClient.objects.filter(Q(client_ref_id=old.id) | Q(client_name__iexact=(old.name or "").strip()))
            if not dry_run:
                for cc in qs_cc:
                    cc.client_ref_id = target.id
                    cc.client_name = target.name
                    if not cc.hub_ref_id and not cc.hub_name:
                        cc.hub_ref_id = hub.id
                        cc.hub_name = hub.name
                    cc.save(update_fields=["client_ref_id", "client_name", "hub_ref_id", "hub_name"])
            moved_contactclients += qs_cc.count()

            if not dry_run:
                target.systems.add(*old.systems.all())
                target.technicians.add(*old.technicians.all())

                if not target.supervisor_id and old.supervisor_id:
                    target.supervisor_id = old.supervisor_id
                    target.save(update_fields=["supervisor"])

            if not dry_run and delete_old:
                old_hubs = ClientHub.objects.filter(client=old)
                if old_hubs.exists():
                    for h in old_hubs:
                        exists_same = ClientHub.objects.filter(client=target, name__iexact=h.name).exclude(id=h.id).exists()
                        if exists_same:
                            h.delete()
                        else:
                            h.client = target
                            h.save(update_fields=["client"])

                # additional_clients M2M: swap old -> target
                for tr in TechnicianTravel.objects.filter(additional_clients=old).distinct():
                    tr.additional_clients.remove(old)
                    tr.additional_clients.add(target)

                refs_left = {
                    "tickets": Ticket.objects.filter(client=old).count(),
                    "travels": TechnicianTravel.objects.filter(client=old).count(),
                    "profiles": UserProfile.objects.filter(fixed_client=old).count(),
                    "contacts": ContactPerson.objects.filter(client=old).count(),
                    "clienthubs": ClientHub.objects.filter(client=old).count(),
                    "additional_clients": TechnicianTravel.objects.filter(additional_clients=old).count(),
                }
                if sum(refs_left.values()) == 0:
                    old.delete()

        self.stdout.write(f"Tickets movidos: {moved_tickets}")
        self.stdout.write(f"Viagens movidas: {moved_travels}")
        self.stdout.write(f"Perfis movidos: {moved_profiles}")
        self.stdout.write(f"ContactPerson movidos: {moved_contacts}")
        self.stdout.write(f"ContactClient ajustados: {moved_contactclients}")
        self.stdout.write(f"Hubs criados/garantidos no alvo: {len(hub_by_code)}")
        if dry_run:
            self.stdout.write("DRY-RUN: nenhuma alteracao foi gravada.")
            return

        if source_prefix and hub_name_mode == "after_prefix":
            cleaned = 0
            merged = 0
            prefixed_hubs = list(ClientHub.objects.filter(client=target, name__istartswith=source_prefix).order_by("name"))
            for h in prefixed_hubs:
                stripped = self._build_hub_name(h.name, "after_prefix", source_prefix, hub_strip_suffix)
                if not stripped:
                    continue
                existing = ClientHub.objects.filter(client=target, name__iexact=stripped).exclude(id=h.id).first()
                if existing:
                    Ticket.objects.filter(hub=h).update(hub=existing)
                    TechnicianTravel.objects.filter(hub=h).update(hub=existing)
                    UserProfile.objects.filter(fixed_hub=h).update(fixed_hub=existing)
                    h.delete()
                    merged += 1
                    continue
                if h.name != stripped:
                    h.name = stripped
                    h.save(update_fields=["name"])
                    cleaned += 1
            if prefixed_hubs:
                self.stdout.write(f"Cleanup hubs com prefixo '{source_prefix}': renomeados={cleaned} removidos/mesclados={merged}")
