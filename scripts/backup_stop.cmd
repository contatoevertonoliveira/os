@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0db_backup_task.ps1" -Mode stop
endlocal

