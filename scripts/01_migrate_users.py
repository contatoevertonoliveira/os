#!/usr/bin/env python
"""
Script de Migração: Usuários & Roles
JumperFour (User + UserProfile) → Odoo (res.users + hr.employee + res.groups)

Modelos migrados:
  1. RoleLevel → res.groups
  2. User → res.users
  3. UserProfile → hr.employee

Execução:
  python 01_migrate_users.py [--dry-run] [--skip-roles]
"""
import os
import sys
import django
import argparse
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jumperfour.settings')
django.setup()

from django.contrib.auth.models import User
from tickets.models import UserProfile, RoleLevel
from odoo_client import OdooMigrationClient
from migration_config import (
    get_logger, log_migration_start, log_migration_end,
    ROLE_MAPPING, SUCCESS, ERROR, SKIPPED
)

logger = get_logger(__name__)


class UserMigration:
    """Migração de usuários e roles"""

    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.odoo = OdooMigrationClient()
        self.stats = {
            'roles': {'success': 0, 'error': 0, 'skipped': 0},
            'users': {'success': 0, 'error': 0, 'skipped': 0},
            'employees': {'success': 0, 'error': 0, 'skipped': 0},
        }

    def migrate_roles(self, skip=False):
        """Migra RoleLevel → res.groups"""
        if skip:
            logger.info("⏭️  Pulando migração de RoleLevel")
            return

        logger.info("\n" + "="*80)
        logger.info("MIGRANDO: RoleLevel → res.groups")
        logger.info("="*80)

        roles = RoleLevel.objects.filter(is_active=True)
        log_migration_start('01_migrate_users', 'RoleLevel', roles.count())

        for role in roles:
            try:
                # Verificar se grupo já existe no Odoo
                existing = self.odoo.search_records('res.groups',
                    filters=[('code', '=', role.code)], limit=1)

                if existing:
                    logger.info(f"✅ Grupo '{role.name}' já existe no Odoo (ID: {existing[0]['id']})")
                    self.stats['roles']['skipped'] += 1
                    continue

                # Criar novo grupo
                group_data = {
                    'name': role.name,
                    'code': role.code or role.name.lower().replace(' ', '_'),
                }

                if not self.dry_run:
                    result = self.odoo.create_record('res.groups', group_data)
                    if result:
                        logger.info(f"✅ Grupo criado: '{role.name}' (Odoo ID: {result.get('id')})")
                        self.stats['roles']['success'] += 1
                    else:
                        logger.error(f"❌ Erro ao criar grupo '{role.name}'")
                        self.stats['roles']['error'] += 1
                else:
                    logger.info(f"[DRY-RUN] Criaria grupo: {group_data}")
                    self.stats['roles']['success'] += 1

            except Exception as e:
                logger.error(f"❌ Erro ao migrar role '{role.name}': {e}")
                self.stats['roles']['error'] += 1

        log_migration_end('01_migrate_users', 'RoleLevel',
                         self.stats['roles']['success'],
                         self.stats['roles']['error'],
                         self.stats['roles']['skipped'])

    def migrate_users(self):
        """Migra User → res.users"""
        logger.info("\n" + "="*80)
        logger.info("MIGRANDO: User → res.users")
        logger.info("="*80)

        users = User.objects.filter(is_active=True)
        log_migration_start('01_migrate_users', 'User', users.count())

        for user in users:
            try:
                # Verificar se usuário já existe
                existing = self.odoo.search_records('res.users',
                    filters=[('login', '=', user.username)], limit=1)

                if existing:
                    logger.info(f"✅ Usuário '{user.username}' já existe (Odoo ID: {existing[0]['id']})")
                    self.stats['users']['skipped'] += 1
                    continue

                # Preparar dados do usuário
                user_data = {
                    'login': user.username,
                    'name': f"{user.first_name} {user.last_name}".strip() or user.username,
                    'email': user.email or '',
                    'active': user.is_active,
                }

                if not self.dry_run:
                    result = self.odoo.create_record('res.users', user_data)
                    if result:
                        logger.info(f"✅ Usuário criado: '{user.username}' (Odoo ID: {result.get('id')})")
                        self.stats['users']['success'] += 1

                        # Armazenar mapping para uso posterior
                        self._save_mapping('res.users', user.id, result.get('id'), user.username)
                    else:
                        logger.error(f"❌ Erro ao criar usuário '{user.username}'")
                        self.stats['users']['error'] += 1
                else:
                    logger.info(f"[DRY-RUN] Criaria usuário: {user_data}")
                    self.stats['users']['success'] += 1

            except Exception as e:
                logger.error(f"❌ Erro ao migrar usuário '{user.username}': {e}")
                self.stats['users']['error'] += 1

        log_migration_end('01_migrate_users', 'User',
                         self.stats['users']['success'],
                         self.stats['users']['error'],
                         self.stats['users']['skipped'])

    def migrate_employees(self):
        """Migra UserProfile → hr.employee"""
        logger.info("\n" + "="*80)
        logger.info("MIGRANDO: UserProfile → hr.employee")
        logger.info("="*80)

        profiles = UserProfile.objects.filter(user__is_active=True)
        log_migration_start('01_migrate_users', 'UserProfile', profiles.count())

        for profile in profiles:
            try:
                user = profile.user

                # Buscar usuário Odoo já criado
                odoo_user = self.odoo.search_records('res.users',
                    filters=[('login', '=', user.username)], limit=1)

                if not odoo_user:
                    logger.warning(f"⚠️  Usuário Odoo não encontrado para '{user.username}'")
                    self.stats['employees']['skipped'] += 1
                    continue

                odoo_user_id = odoo_user[0]['id']

                # Verificar se employee já existe
                existing = self.odoo.search_records('hr.employee',
                    filters=[('user_id', '=', odoo_user_id)], limit=1)

                if existing:
                    logger.info(f"✅ Funcionário já existe para '{user.username}'")
                    self.stats['employees']['skipped'] += 1
                    continue

                # Preparar dados do funcionário
                employee_data = {
                    'name': f"{user.first_name} {user.last_name}".strip() or user.username,
                    'user_id': odoo_user_id,
                    'job_title': profile.job_title or '',
                    'department_id': False,  # Será preenchido manualmente
                    'work_location_id': False,
                }

                if not self.dry_run:
                    result = self.odoo.create_record('hr.employee', employee_data)
                    if result:
                        logger.info(f"✅ Funcionário criado: '{user.username}' (Odoo ID: {result.get('id')})")
                        self.stats['employees']['success'] += 1
                    else:
                        logger.error(f"❌ Erro ao criar funcionário '{user.username}'")
                        self.stats['employees']['error'] += 1
                else:
                    logger.info(f"[DRY-RUN] Criaria funcionário: {employee_data}")
                    self.stats['employees']['success'] += 1

            except Exception as e:
                logger.error(f"❌ Erro ao migrar profile '{profile.user.username}': {e}")
                self.stats['employees']['error'] += 1

        log_migration_end('01_migrate_users', 'UserProfile',
                         self.stats['employees']['success'],
                         self.stats['employees']['error'],
                         self.stats['employees']['skipped'])

    def _save_mapping(self, odoo_model, jf_id, odoo_id, name):
        """Salva mapeamento para referência futura"""
        # TODO: Salvar em banco local para referência
        pass

    def run(self, skip_roles=False):
        """Executa migração completa de usuários"""
        logger.info(f"\n{'#'*80}")
        logger.info(f"# INICIANDO MIGRAÇÃO: USUÁRIOS & ROLES")
        logger.info(f"# Modo: {'DRY-RUN' if self.dry_run else 'EXECUÇÃO'}")
        logger.info(f"# Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'#'*80}\n")

        # Verificar conexão com Odoo
        if not self.odoo.health_check():
            logger.error("❌ Odoo não está acessível! Abortando migração.")
            return False

        try:
            self.migrate_roles(skip=skip_roles)
            self.migrate_users()
            self.migrate_employees()

            # Resumo final
            logger.info(f"\n{'='*80}")
            logger.info("📊 RESUMO FINAL")
            logger.info(f"{'='*80}")
            logger.info(f"Roles:     ✅ {self.stats['roles']['success']} | ❌ {self.stats['roles']['error']} | ⏭️  {self.stats['roles']['skipped']}")
            logger.info(f"Usuários:  ✅ {self.stats['users']['success']} | ❌ {self.stats['users']['error']} | ⏭️  {self.stats['users']['skipped']}")
            logger.info(f"Funcionários: ✅ {self.stats['employees']['success']} | ❌ {self.stats['employees']['error']} | ⏭️  {self.stats['employees']['skipped']}")
            logger.info(f"{'='*80}\n")

            return True

        except Exception as e:
            logger.error(f"❌ Erro geral na migração: {e}", exc_info=True)
            return False


def main():
    parser = argparse.ArgumentParser(
        description='Migra usuários e roles do JumperFour para Odoo'
    )
    parser.add_argument('--dry-run', action='store_true',
                       help='Simula migração sem fazer mudanças')
    parser.add_argument('--skip-roles', action='store_true',
                       help='Pula migração de roles')

    args = parser.parse_args()

    migrator = UserMigration(dry_run=args.dry_run)
    success = migrator.run(skip_roles=args.skip_roles)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
