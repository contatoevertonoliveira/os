## Backup automático do banco (Windows Server)

Arquivos:
- `db_backup_task.ps1`: script principal (cria/pausa/remove tarefa agendada + backup manual)
- `backup_*.cmd`: “atalhos” para rodar os modos mais comuns

### Comandos (no servidor)

Abra um Prompt/PowerShell na raiz do projeto e rode:

- Ativar automático (todo dia 18:00): `scripts\backup_auto.cmd`
- Pausar: `scripts\backup_pause.cmd`
- Retomar: `scripts\backup_resume.cmd`
- Parar/remover: `scripts\backup_stop.cmd`
- Backup manual agora: `scripts\backup_now.cmd`
- Status: `scripts\backup_status.cmd`

### Onde salva

Os backups ficam em `data\db_backups\backup_YYYYMMDD_HHMM.json`

### Restaurar (manual)

```bat
python manage.py loaddata data\db_backups\backup_YYYYMMDD_HHMM.json
```

