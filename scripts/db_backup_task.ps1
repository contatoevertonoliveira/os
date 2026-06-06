param(
    [Parameter(Mandatory = $false)]
    [ValidateSet('auto','pause','resume','stop','backup','status','run')]
    [string]$Mode = 'status',

    [Parameter(Mandatory = $false)]
    [string]$TaskName = 'JumperFour - Backup SQLite (JSON)',

    [Parameter(Mandatory = $false)]
    [string]$TaskPath = '\JumperFour\',

    [Parameter(Mandatory = $false)]
    [string]$Time = '18:00',

    [Parameter(Mandatory = $false)]
    [int]$KeepDays = 30,

    [Parameter(Mandatory = $false)]
    [string]$PythonPath = '',

    [Parameter(Mandatory = $false)]
    [string]$ProjectRoot = ''
)

$ErrorActionPreference = 'Stop'

function Resolve-ProjectRoot {
    param([string]$ExplicitRoot)
    if ($ExplicitRoot -and (Test-Path $ExplicitRoot)) {
        return (Resolve-Path $ExplicitRoot).Path
    }
    # Por padrão, assume que este script está em /scripts e o projeto está 1 nível acima
    $root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
    return $root
}

function Resolve-Python {
    param([string]$Root, [string]$ExplicitPython)
    if ($ExplicitPython) { return $ExplicitPython }

    $venvPython = Join-Path $Root '.venv\Scripts\python.exe'
    if (Test-Path $venvPython) { return $venvPython }

    return 'python'
}

function Invoke-Backup {
    param([string]$Root, [string]$Py, [int]$Keep)

    $manage = Join-Path $Root 'manage.py'
    if (-not (Test-Path $manage)) {
        throw "manage.py não encontrado em: $Root"
    }

    $outDir = Join-Path $Root 'data\db_backups'
    if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Force -Path $outDir | Out-Null }

    Push-Location $Root
    try {
        # Sem saída desnecessária (preferência: salvar em arquivo apenas)
        & $Py $manage backup_db_json --keep-days $Keep --quiet
        if ($LASTEXITCODE -ne 0) {
            throw "backup_db_json retornou exit code $LASTEXITCODE"
        }
    } finally {
        Pop-Location
    }
}

function Get-FullTaskName {
    param([string]$Path, [string]$Name)
    # PowerShell cmdlets usam TaskName separado do TaskPath. Mantemos os dois.
    return @{ TaskName = $Name; TaskPath = $Path }
}

function Ensure-TaskFolder {
    param([string]$Path)
    # Se o TaskPath não existir, o Register-ScheduledTask cria implicitamente ao registrar.
    # Mantemos esta função por clareza.
    return
}

function Install-Or-UpdateTask {
    param(
        [string]$Path,
        [string]$Name,
        [string]$AtTime,
        [int]$Keep,
        [string]$Root,
        [string]$Py
    )

    Ensure-TaskFolder -Path $Path

    $script = $PSCommandPath
    if (-not $script) { $script = $MyInvocation.MyCommand.Path }

    # Ação: executar este script em modo "run"
    $args = @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', "`"$script`"",
        '-Mode', 'run',
        '-KeepDays', $Keep,
        '-ProjectRoot', "`"$Root`""
    )
    if ($Py -and $Py -ne 'python') {
        $args += @('-PythonPath', "`"$Py`"")
    }

    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ($args -join ' ')
    $trigger = New-ScheduledTaskTrigger -Daily -At $AtTime
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    $principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
    $task = New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -Principal $principal

    # Atualiza se já existir
    try {
        Unregister-ScheduledTask -TaskName $Name -TaskPath $Path -Confirm:$false -ErrorAction SilentlyContinue | Out-Null
    } catch {}

    Register-ScheduledTask -TaskName $Name -TaskPath $Path -InputObject $task | Out-Null
    Enable-ScheduledTask -TaskName $Name -TaskPath $Path | Out-Null
}

$rootPath = Resolve-ProjectRoot -ExplicitRoot $ProjectRoot
$py = Resolve-Python -Root $rootPath -ExplicitPython $PythonPath

switch ($Mode) {
    'run' {
        Invoke-Backup -Root $rootPath -Py $py -Keep $KeepDays
        # Modo agendado: sem mensagens/ruído
    }
    'backup' {
        Invoke-Backup -Root $rootPath -Py $py -Keep $KeepDays
        Write-Host "OK: backup manual executado."
    }
    'auto' {
        Install-Or-UpdateTask -Path $TaskPath -Name $TaskName -AtTime $Time -Keep $KeepDays -Root $rootPath -Py $py
        Write-Host "OK: agendamento criado/atualizado ($Time)."
    }
    'pause' {
        Disable-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath | Out-Null
        Write-Host "OK: agendamento pausado."
    }
    'resume' {
        Enable-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath | Out-Null
        Write-Host "OK: agendamento retomado."
    }
    'stop' {
        Unregister-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -Confirm:$false | Out-Null
        Write-Host "OK: agendamento removido."
    }
    'status' {
        $t = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction SilentlyContinue
        if (-not $t) {
            Write-Host "Agendamento não encontrado. Use: .\scripts\\backup_auto.cmd"
            exit 0
        }
        $info = Get-ScheduledTaskInfo -TaskName $TaskName -TaskPath $TaskPath
        Write-Host ("Task: {0}{1}" -f $TaskPath, $TaskName)
        Write-Host ("State: {0}" -f $t.State)
        Write-Host ("LastRun: {0}" -f $info.LastRunTime)
        Write-Host ("LastResult: {0}" -f $info.LastTaskResult)
        Write-Host ("NextRun: {0}" -f $info.NextRunTime)
    }
}
