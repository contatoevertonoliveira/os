# ============================================================
#  INICIADOR DO SISTEMA - JUMPERFOUR (Django)
#  Inicia o servidor na porta 8000 com acesso Local ou Intranet.
#  Processos antigos que estejam usando a porta 8000 são
#  encerrados antes de subir um novo servidor.
# ============================================================

# --- Configurações ---
$PORT        = 8000
$SCRIPT_DIR  = $PSScriptRoot
$PROJECT_DIR = Split-Path $SCRIPT_DIR -Parent   # pasta pai de scripts/ = raiz do projeto
$VENV_PY     = Join-Path $PROJECT_DIR ".venv\Scripts\python.exe"
$MANAGE      = Join-Path $PROJECT_DIR "manage.py"
$ACTIVATE    = Join-Path $PROJECT_DIR ".venv\Scripts\Activate.ps1"

# --- Validações ---
if (-not (Test-Path $VENV_PY)) {
    Write-Host "ERRO: ambiente virtual (.venv) nao encontrado em: $VENV_PY" -ForegroundColor Red
    Read-Host "Pressione ENTER para fechar"
    exit 1
}
if (-not (Test-Path $MANAGE)) {
    Write-Host "ERRO: manage.py nao encontrado em: $MANAGE" -ForegroundColor Red
    Read-Host "Pressione ENTER para fechar"
    exit 1
}

# --- Função: encerra qualquer processo escutando na porta informada ---
function Stop-ProcessByPort {
    param([int]$Port)
    $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $listeners) {
        Write-Host "  -> Porta $Port livre." -ForegroundColor DarkGray
        return
    }
    $pids = $listeners | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($procId in $pids) {
        $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "  -> Encerrando processo antigo: $($proc.ProcessName) (PID $procId) na porta $Port" -ForegroundColor Yellow
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    }
    Start-Sleep -Milliseconds 500
}

# --- Menu de opções ---
$HOST_IP = ""
while (-not $HOST_IP) {
    Clear-Host
    Write-Host "==============================================" -ForegroundColor Cyan
    Write-Host "   INICIADOR DO SISTEMA - JUMPERFOUR" -ForegroundColor Cyan
    Write-Host "==============================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  1 - Acessar LOCALMENTE   (http://127.0.0.1:$PORT)" -ForegroundColor White
    Write-Host "  2 - Acessar na INTRANET  (acesso pela rede da empresa)" -ForegroundColor White
    Write-Host "  0 - Sair" -ForegroundColor White
    Write-Host ""
    $choice = Read-Host "  Escolha uma opcao"

    switch ($choice) {
        "1" { $HOST_IP = "127.0.0.1" }
        "2" { $HOST_IP = "0.0.0.0" }
        "0" { Write-Host "Encerrando..." -ForegroundColor Gray; exit 0 }
        default {
            Write-Host "  Opcao invalida. Digite 1, 2 ou 0." -ForegroundColor Red
            Start-Sleep -Milliseconds 1500
        }
    }
}

Clear-Host
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "   INICIANDO SISTEMA - JUMPERFOUR" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

# --- 1. Encerrar processos antigos na porta 8000 ---
Write-Host "[1/3] Verificando porta $PORT ..." -ForegroundColor Gray
Stop-ProcessByPort -Port $PORT

# --- 2. Ativar ambiente virtual ---
Write-Host "[2/3] Ativando ambiente virtual (.venv) ..." -ForegroundColor Gray
& $ACTIVATE

# --- 3. Subir o servidor ---
Write-Host "[3/3] Subindo servidor Django em $HOST_IP`:$PORT ..." -ForegroundColor Gray
Write-Host ""

if ($HOST_IP -eq "127.0.0.1") {
    Write-Host "  >>> ACESSO LOCAL: http://127.0.0.1:$PORT" -ForegroundColor Green
} else {
    Write-Host "  >>> ACESSO INTRANET: digite um dos enderecos abaixo no navegador:" -ForegroundColor Green
    $ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" }
    foreach ($ip in $ips) {
        Write-Host "      http://$($ip.IPAddress):$PORT" -ForegroundColor Green
    }
}
Write-Host ""
Write-Host "  Pressione CTRL+C no terminal para parar o servidor." -ForegroundColor DarkGray
Write-Host ""

# Executa o servidor (bloqueia até ser encerrado)
Push-Location $PROJECT_DIR
& $VENV_PY $MANAGE runserver "$HOST_IP`:$PORT"
$code = $LASTEXITCODE
Pop-Location

Write-Host ""
if ($code -ne 0) {
    Write-Host "  Servidor encerrado com erro (codigo $code)." -ForegroundColor Red
} else {
    Write-Host "  Servidor encerrado." -ForegroundColor Yellow
}
Read-Host "Pressione ENTER para fechar"
