from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand, call_command
from django.utils import timezone


class Command(BaseCommand):
    help = "Gera backup JSON do banco (dumpdata) em data/db_backups/ com timestamp."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            default=str(Path(settings.BASE_DIR) / "data" / "db_backups"),
            help="Pasta destino para os backups (default: data/db_backups).",
        )
        parser.add_argument(
            "--keep-days",
            type=int,
            default=30,
            help="Quantos dias manter os backups antes de apagar (default: 30).",
        )
        parser.add_argument(
            "--indent",
            type=int,
            default=2,
            help="Indentação do JSON (default: 2).",
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Não imprime mensagens (útil para agendamentos).",
        )

    def handle(self, *args, **options):
        output_dir = Path(options["output_dir"])
        keep_days = int(options["keep_days"] or 0)
        indent = int(options["indent"] or 0)
        quiet = bool(options.get("quiet"))

        output_dir.mkdir(parents=True, exist_ok=True)

        # Usa timezone do Django (settings.TIME_ZONE) para nome do arquivo
        now = timezone.localtime(timezone.now())
        stamp = now.strftime("%Y%m%d_%H%M")
        out_file = output_dir / f"backup_{stamp}.json"

        if not quiet:
            self.stdout.write(f"Gerando backup JSON: {out_file}")

        with out_file.open("w", encoding="utf-8") as fh:
            # Gera um dump completo (todas as apps/models)
            call_command(
                "dumpdata",
                "--natural-foreign",
                "--natural-primary",
                "--indent",
                str(indent),
                stdout=fh,
            )

        # Limpeza de backups antigos (por mtime)
        if keep_days > 0:
            cutoff = timezone.now() - timedelta(days=keep_days)
            removed = 0
            for p in output_dir.glob("backup_*.json"):
                try:
                    mtime = timezone.datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.get_current_timezone())
                    if mtime < cutoff:
                        p.unlink(missing_ok=True)
                        removed += 1
                except Exception:
                    # Não falha o backup por causa de um arquivo problemático
                    continue
            if removed and (not quiet):
                self.stdout.write(self.style.WARNING(f"Backups antigos removidos: {removed}"))

        if not quiet:
            self.stdout.write(self.style.SUCCESS("Backup concluído."))
