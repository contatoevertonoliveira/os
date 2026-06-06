## Backup diário do banco (SQLite → JSON)

Este projeto usa SQLite por padrão (`db.sqlite3`). Para facilitar restauração rápida, existe um comando de backup em JSON.

### Gerar backup (manual)

Na raiz do projeto (onde existe `manage.py`):

```bash
python manage.py backup_db_json
```

Isso cria um arquivo em:

`data/db_backups/backup_YYYYMMDD_HHMM.json`

Por padrão, mantém os últimos 30 dias (apaga backups mais antigos).

Parâmetros úteis:

```bash
python manage.py backup_db_json --keep-days 30
python manage.py backup_db_json --output-dir data/db_backups --indent 2
```

### Restaurar backup (um comando)

```bash
python manage.py loaddata data/db_backups/backup_YYYYMMDD_HHMM.json
```

Se precisar zerar antes (banco “limpo”):

```bash
python manage.py flush --no-input
python manage.py migrate
python manage.py loaddata data/db_backups/backup_YYYYMMDD_HHMM.json
```

### Agendamento (servidor)

Em Linux via cron (exemplo 18:00 todos os dias):

```cron
0 18 * * * cd /caminho/do/projeto && /caminho/do/venv/bin/python manage.py backup_db_json --keep-days 30
```

Em Windows (Task Scheduler), a ação deve executar:

```bat
python manage.py backup_db_json --keep-days 30
```

