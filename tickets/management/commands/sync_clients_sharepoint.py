from django.core.management.base import BaseCommand

from tickets.sync_sharepoint import sync_clients_from_sharepoint


class Command(BaseCommand):
    help = 'Sincroniza clientes automaticamente a partir da planilha no SharePoint/Teams (Microsoft Graph).'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--force', action='store_true')

    def handle(self, *args, **options):
        result = sync_clients_from_sharepoint(
            stdout=self.stdout,
            dry_run=bool(options.get('dry_run')),
            force=bool(options.get('force')),
        )
        self.stdout.write(str(result))

