#!/usr/bin/env python
"""
Script de Migração: Clientes & Contatos
JumperFour (Client + ClientHub + ContactClient) → Odoo (res.partner)

Modelos migrados:
  1. Client → res.partner (is_company=True)
  2. ClientHub → res.partner (child de Client)
  3. ContactClient → res.partner (contact)

Execução:
  python 02_migrate_clients.py [--dry-run] [--batch-size 10]
"""
import os
import sys
import django
import argparse
import time
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jumperfour.settings')
django.setup()

from tickets.models import Client, ClientHub, ContactClient
from odoo_client import OdooMigrationClient
from migration_config import (
    get_logger, log_migration_start, log_migration_end,
    MIGRATION_CONFIG
)

logger = get_logger(__name__)


class ClientMigration:
    """Migração de clientes e contatos"""

    def __init__(self, dry_run=False, batch_size=None):
        self.dry_run = dry_run
        self.odoo = OdooMigrationClient()
        self.batch_size = batch_size or MIGRATION_CONFIG.get('batch_size_clients', 10)
        self.stats = {
            'clients': {'success': 0, 'error': 0, 'skipped': 0},
            'hubs': {'success': 0, 'error': 0, 'skipped': 0},
            'contacts': {'success': 0, 'error': 0, 'skipped': 0},
        }
        self.client_mapping = {}  # JF Client ID → Odoo res.partner ID

    def migrate_clients(self):
        """Migra Client → res.partner (is_company=True)"""
        logger.info("\n" + "="*80)
        logger.info("MIGRANDO: Client → res.partner")
        logger.info("="*80)

        clients = Client.objects.all()
        log_migration_start('02_migrate_clients', 'Client', clients.count())

        for client in clients:
            try:
                # Verificar se já existe
                existing = self.odoo.search_records('res.partner',
                    filters=[('name', '=', client.name), ('is_company', '=', True)],
                    limit=1)

                if existing:
                    logger.info(f"✅ Cliente '{client.name}' já existe (Odoo ID: {existing[0]['id']})")
                    self.stats['clients']['skipped'] += 1
                    self.client_mapping[client.id] = existing[0]['id']
                    continue

                # Preparar dados do cliente
                partner_data = {
                    'name': client.name,
                    'email': client.email or '',
                    'phone': client.phone or '',
                    'is_company': True,
                    'active': True,
                }

                # Adicionar campos opcionais se existirem
                if client.address:
                    partner_data['street'] = client.address
                if client.city:
                    partner_data['city'] = client.city

                if not self.dry_run:
                    result = self.odoo.create_record('res.partner', partner_data)
                    if result:
                        odoo_id = result.get('id')
                        logger.info(f"✅ Cliente criado: '{client.name}' (Odoo ID: {odoo_id})")
                        self.stats['clients']['success'] += 1
                        self.client_mapping[client.id] = odoo_id
                    else:
                        logger.error(f"❌ Erro ao criar cliente '{client.name}'")
                        self.stats['clients']['error'] += 1
                else:
                    logger.info(f"[DRY-RUN] Criaria cliente: {partner_data}")
                    self.stats['clients']['success'] += 1
                    self.client_mapping[client.id] = 99999  # Mock ID

            except Exception as e:
                logger.error(f"❌ Erro ao migrar cliente '{client.name}': {e}")
                self.stats['clients']['error'] += 1

        log_migration_end('02_migrate_clients', 'Client',
                         self.stats['clients']['success'],
                         self.stats['clients']['error'],
                         self.stats['clients']['skipped'])

    def migrate_hubs(self):
        """Migra ClientHub → res.partner (child)"""
        logger.info("\n" + "="*80)
        logger.info("MIGRANDO: ClientHub → res.partner (child)")
        logger.info("="*80)

        hubs = ClientHub.objects.all()
        log_migration_start('02_migrate_clients', 'ClientHub', hubs.count())

        for hub in hubs:
            try:
                # Verificar se cliente pai existe em Odoo
                parent_odoo_id = self.client_mapping.get(hub.client_id)
                if not parent_odoo_id:
                    logger.warning(f"⚠️  Cliente pai não encontrado para hub '{hub.name}'")
                    self.stats['hubs']['skipped'] += 1
                    continue

                # Verificar se hub já existe
                existing = self.odoo.search_records('res.partner',
                    filters=[('name', '=', hub.name), ('parent_id', '=', parent_odoo_id)],
                    limit=1)

                if existing:
                    logger.info(f"✅ Hub '{hub.name}' já existe")
                    self.stats['hubs']['skipped'] += 1
                    continue

                # Preparar dados do hub
                hub_data = {
                    'name': hub.name,
                    'parent_id': parent_odoo_id,
                    'type': 'delivery',  # Endereço de entrega
                    'active': True,
                }

                if hub.address:
                    hub_data['street'] = hub.address
                if hub.phone:
                    hub_data['phone'] = hub.phone

                if not self.dry_run:
                    result = self.odoo.create_record('res.partner', hub_data)
                    if result:
                        logger.info(f"✅ Hub criado: '{hub.name}' (Odoo ID: {result.get('id')})")
                        self.stats['hubs']['success'] += 1
                    else:
                        logger.error(f"❌ Erro ao criar hub '{hub.name}'")
                        self.stats['hubs']['error'] += 1
                else:
                    logger.info(f"[DRY-RUN] Criaria hub: {hub_data}")
                    self.stats['hubs']['success'] += 1

            except Exception as e:
                logger.error(f"❌ Erro ao migrar hub '{hub.name}': {e}")
                self.stats['hubs']['error'] += 1

        log_migration_end('02_migrate_clients', 'ClientHub',
                         self.stats['hubs']['success'],
                         self.stats['hubs']['error'],
                         self.stats['hubs']['skipped'])

    def migrate_contacts(self):
        """Migra ContactClient → res.partner (contact type)"""
        logger.info("\n" + "="*80)
        logger.info("MIGRANDO: ContactClient → res.partner (contact)")
        logger.info("="*80)

        contacts = ContactClient.objects.all()
        log_migration_start('02_migrate_clients', 'ContactClient', contacts.count())

        # Processar em batches
        total_batches = (contacts.count() + self.batch_size - 1) // self.batch_size

        for batch_num in range(total_batches):
            start_idx = batch_num * self.batch_size
            end_idx = min(start_idx + self.batch_size, contacts.count())
            batch = contacts[start_idx:end_idx]

            logger.info(f"\nProcessando batch {batch_num + 1}/{total_batches}...")

            for contact in batch:
                try:
                    # Verificar se cliente pai existe
                    parent_odoo_id = self.client_mapping.get(contact.client_id)
                    if not parent_odoo_id:
                        logger.warning(f"⚠️  Cliente não encontrado para contato '{contact.name}'")
                        self.stats['contacts']['skipped'] += 1
                        continue

                    # Verificar se contato já existe
                    existing = self.odoo.search_records('res.partner',
                        filters=[('name', '=', contact.name), ('parent_id', '=', parent_odoo_id),
                                ('type', '=', 'contact')],
                        limit=1)

                    if existing:
                        logger.info(f"✅ Contato '{contact.name}' já existe")
                        self.stats['contacts']['skipped'] += 1
                        continue

                    # Preparar dados do contato
                    contact_data = {
                        'name': contact.name,
                        'parent_id': parent_odoo_id,
                        'type': 'contact',
                        'active': True,
                    }

                    if contact.email:
                        contact_data['email'] = contact.email
                    if contact.phone:
                        contact_data['phone'] = contact.phone
                    if contact.title:
                        contact_data['function'] = contact.title

                    if not self.dry_run:
                        result = self.odoo.create_record('res.partner', contact_data)
                        if result:
                            self.stats['contacts']['success'] += 1
                        else:
                            logger.error(f"❌ Erro ao criar contato '{contact.name}'")
                            self.stats['contacts']['error'] += 1
                    else:
                        logger.info(f"[DRY-RUN] Criaria contato: {contact_data}")
                        self.stats['contacts']['success'] += 1

                except Exception as e:
                    logger.error(f"❌ Erro ao migrar contato '{contact.name}': {e}")
                    self.stats['contacts']['error'] += 1

            # Delay entre batches
            if batch_num < total_batches - 1:
                logger.info(f"Aguardando {MIGRATION_CONFIG['batch_delay']}s antes do próximo batch...")
                time.sleep(MIGRATION_CONFIG['batch_delay'])

        log_migration_end('02_migrate_clients', 'ContactClient',
                         self.stats['contacts']['success'],
                         self.stats['contacts']['error'],
                         self.stats['contacts']['skipped'])

    def run(self):
        """Executa migração completa de clientes"""
        logger.info(f"\n{'#'*80}")
        logger.info(f"# INICIANDO MIGRAÇÃO: CLIENTES & CONTATOS")
        logger.info(f"# Modo: {'DRY-RUN' if self.dry_run else 'EXECUÇÃO'}")
        logger.info(f"# Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'#'*80}\n")

        # Verificar conexão
        if not self.odoo.health_check():
            logger.error("❌ Odoo não está acessível!")
            return False

        try:
            self.migrate_clients()      # Primeiro: clientes principais
            self.migrate_hubs()         # Segundo: hubs (dependem de clientes)
            self.migrate_contacts()     # Terceiro: contatos (dependem de clientes)

            # Resumo
            logger.info(f"\n{'='*80}")
            logger.info("📊 RESUMO FINAL")
            logger.info(f"{'='*80}")
            logger.info(f"Clientes:    ✅ {self.stats['clients']['success']} | ❌ {self.stats['clients']['error']} | ⏭️  {self.stats['clients']['skipped']}")
            logger.info(f"Hubs:        ✅ {self.stats['hubs']['success']} | ❌ {self.stats['hubs']['error']} | ⏭️  {self.stats['hubs']['skipped']}")
            logger.info(f"Contatos:    ✅ {self.stats['contacts']['success']} | ❌ {self.stats['contacts']['error']} | ⏭️  {self.stats['contacts']['skipped']}")
            logger.info(f"{'='*80}\n")

            return True

        except Exception as e:
            logger.error(f"❌ Erro geral na migração: {e}", exc_info=True)
            return False


def main():
    parser = argparse.ArgumentParser(description='Migra clientes para Odoo')
    parser.add_argument('--dry-run', action='store_true',
                       help='Simula migração')
    parser.add_argument('--batch-size', type=int, default=10,
                       help='Tamanho do batch para contatos')

    args = parser.parse_args()

    migrator = ClientMigration(dry_run=args.dry_run, batch_size=args.batch_size)
    success = migrator.run()

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
