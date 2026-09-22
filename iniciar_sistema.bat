@echo off
rem ============================================================
rem  INICIADOR DO SISTEMA - JUMPERFOUR (atalho da area de trabalho)
rem  Inicia o servidor na porta 8000 (Local ou Intranet).
rem ============================================================
title Iniciar Sistema - JumperFour
chcp 65001 >nul

rem Usa o caminho relativo quando o bat esta na pasta do projeto;
rem caso contrario (ex.: na area de trabalho) usa o caminho absoluto.
if exist "%~dp0scripts\iniciar_sistema.ps1" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\iniciar_sistema.ps1"
) else (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "d:\Sistemas\os\scripts\iniciar_sistema.ps1"
)
