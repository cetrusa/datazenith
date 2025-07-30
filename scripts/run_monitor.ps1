# Script PowerShell para instalar y ejecutar el monitor de conexiones en Windows
# Ejecutar con: .\scripts\run_monitor.ps1

# Configurar colores
$Host.UI.RawUI.ForegroundColor = "White"

function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    if ($args) {
        Write-Output $args
    }
    $host.UI.RawUI.ForegroundColor = $fc
}

Write-ColorOutput Green "=== Monitor de Conexiones DataZenith ==="
Write-Output "Preparando entorno de monitoreo..."

# Activar entorno virtual si existe
if (Test-Path "..\venv\Scripts\activate.ps1") {
    Write-ColorOutput Green "Activando entorno virtual existente..."
    & ..\venv\Scripts\activate.ps1
} elseif (Test-Path "..\venv\Scripts\Activate.ps1") {
    Write-ColorOutput Green "Activando entorno virtual existente..."
    & ..\venv\Scripts\Activate.ps1
} else {
    Write-ColorOutput Yellow "No se encontró entorno virtual, usando Python del sistema"
}

# Verificar Python
try {
    $pythonVersion = python --version 2>&1
    Write-ColorOutput Green "Python encontrado: $pythonVersion"
} catch {
    Write-ColorOutput Red "ERROR: Python no está instalado o no está en PATH"
    exit 1
}

# Verificar archivo secret.json
if (-Not (Test-Path "secret.json")) {
    Write-ColorOutput Red "ERROR: No se encontró secret.json"
    Write-Output "Por favor, asegúrate de que secret.json existe en el directorio actual"
    Write-Output "El archivo debe contener: DB_HOST, DB_USERNAME, DB_PASS, DB_PORT"
    exit 1
}
Write-ColorOutput Green "Archivo secret.json encontrado"

# Verificar dependencias (instalar si es necesario)
Write-Output "Verificando dependencias de Python..."
try {
    python -c "import pymysql, psutil" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-ColorOutput Green "Dependencias ya instaladas"
    } else {
        throw "Faltan dependencias"
    }
} catch {
    Write-Output "Instalando dependencias necesarias..."
    try {
        pip install pymysql psutil
        if ($LASTEXITCODE -eq 0) {
            Write-ColorOutput Green "Dependencias instaladas correctamente"
        } else {
            throw "Error en pip install"
        }
    } catch {
        Write-ColorOutput Red "ERROR crítico instalando dependencias"
        exit 1
    }
}

# Ejecutar monitor
Write-Output "Ejecutando monitor de conexiones..."
try {
    python scripts\monitor_connections_windows.py
    if ($LASTEXITCODE -eq 0) {
        Write-ColorOutput Green "Monitor ejecutado correctamente"
    } else {
        throw "Error ejecutando monitor"
    }
} catch {
    Write-ColorOutput Red "ERROR ejecutando monitor"
    exit 1
}

# Mostrar resultados
Write-ColorOutput Green "=== Monitor de Conexiones Completado ==="
Write-Output "Archivos generados:"
Write-Output "  - connection_monitor.log: Log detallado"
Write-Output "  - connection_stats.json: Estadísticas históricas"
Write-Output ""
Write-Output "Para ejecutar manualmente: python scripts\monitor_connections_windows.py"

# Opción para configurar tarea programada
$response = Read-Host "¿Quieres configurar una tarea programada para ejecutar el monitor cada 5 minutos? (y/n)"
if ($response -match '^[Yy]$') {
    Write-Output "Configurando tarea programada..."
    
    $scriptPath = (Get-Location).Path + "\scripts\run_monitor.ps1"
    $action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-File `"$scriptPath`""
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5)
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    
    try {
        Register-ScheduledTask -TaskName "DataZenith Connection Monitor" -Action $action -Trigger $trigger -Settings $settings -Force
        Write-ColorOutput Green "Tarea programada configurada - el monitor se ejecutará cada 5 minutos"
    } catch {
        Write-ColorOutput Yellow "No se pudo configurar la tarea programada automáticamente"
        Write-Output "Puedes configurarla manualmente en el Programador de tareas de Windows"
    }
}

Write-ColorOutput Green "Monitor de conexiones listo para usar"
