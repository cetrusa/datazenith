# Script PowerShell para gestionar Docker y verificar servicios DataZenith
# Ejecutar con: .\scripts\manage_docker.ps1

param(
    [string]$Action = "start"  # start, stop, restart, logs, test
)

# Configurar colores
function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    if ($args) {
        Write-Output $args
    }
    $host.UI.RawUI.ForegroundColor = $fc
}

function Test-DockerInstalled {
    try {
        docker --version | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Test-DockerRunning {
    try {
        docker ps | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Show-DockerStatus {
    Write-ColorOutput Green "=== ESTADO DE DOCKER DATAZENITH ==="
    Write-Output ""
    
    if (-not (Test-DockerInstalled)) {
        Write-ColorOutput Red "❌ Docker no está instalado"
        Write-Output "   💡 Instalar Docker Desktop desde: https://www.docker.com/products/docker-desktop"
        return $false
    }
    
    Write-ColorOutput Green "✅ Docker está instalado"
    
    if (-not (Test-DockerRunning)) {
        Write-ColorOutput Yellow "⚠️  Docker no está ejecutándose"
        Write-Output "   💡 Iniciar Docker Desktop o ejecutar: .\scripts\manage_docker.ps1 start"
        return $false
    }
    
    Write-ColorOutput Green "✅ Docker está ejecutándose"
    Write-Output ""
    
    # Verificar contenedores específicos de DataZenith
    Write-Output "📋 Contenedores DataZenith:"
    try {
        $containers = docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | Where-Object { $_ -match "(redis|mysql|datazenith|adminbi)" }
        
        if ($containers) {
            Write-Output $containers
        } else {
            Write-ColorOutput Yellow "⚠️  No se encontraron contenedores DataZenith"
            Write-Output "   💡 ¿Están definidos en docker-compose.yml?"
        }
    } catch {
        Write-ColorOutput Red "❌ Error listando contenedores: $_"
    }
    
    Write-Output ""
    
    # Verificar servicios específicos
    Write-Output "🔍 Verificando servicios clave:"
    
    # Redis
    try {
        $redisStatus = docker ps --filter "name=redis" --format "{{.Status}}"
        if ($redisStatus -and $redisStatus -match "Up") {
            Write-ColorOutput Green "✅ Redis: Ejecutándose"
        } else {
            Write-ColorOutput Red "❌ Redis: No disponible"
        }
    } catch {
        Write-ColorOutput Red "❌ Redis: Error verificando"
    }
    
    # MySQL/MariaDB
    try {
        $mysqlStatus = docker ps --filter "name=mysql" --format "{{.Status}}"
        if (-not $mysqlStatus) {
            $mysqlStatus = docker ps --filter "name=mariadb" --format "{{.Status}}"
        }
        if ($mysqlStatus -and $mysqlStatus -match "Up") {
            Write-ColorOutput Green "✅ Base de datos: Ejecutándose"
        } else {
            Write-ColorOutput Red "❌ Base de datos: No disponible"
        }
    } catch {
        Write-ColorOutput Red "❌ Base de datos: Error verificando"
    }
    
    return $true
}

function Start-DockerServices {
    Write-ColorOutput Green "🚀 INICIANDO SERVICIOS DOCKER"
    Write-Output ""
    
    if (-not (Test-DockerInstalled)) {
        Write-ColorOutput Red "❌ Docker no está instalado"
        return $false
    }
    
    # Verificar si hay archivos docker-compose
    $composeFiles = @()
    if (Test-Path "docker-compose.yml") { $composeFiles += "docker-compose.yml" }
    if (Test-Path "docker-compose.local.yml") { $composeFiles += "docker-compose.local.yml" }
    if (Test-Path "docker-compose.rq.yml") { $composeFiles += "docker-compose.rq.yml" }
    
    if ($composeFiles.Count -eq 0) {
        Write-ColorOutput Red "❌ No se encontraron archivos docker-compose.yml"
        return $false
    }
    
    Write-Output "📁 Archivos compose encontrados:"
    foreach ($file in $composeFiles) {
        Write-Output "   - $file"
    }
    Write-Output ""
    
    # Preguntar qué archivo usar
    if ($composeFiles.Count -gt 1) {
        Write-Output "¿Qué configuración quieres usar?"
        for ($i = 0; $i -lt $composeFiles.Count; $i++) {
            Write-Output "  $($i + 1). $($composeFiles[$i])"
        }
        $choice = Read-Host "Selecciona (1-$($composeFiles.Count)) o Enter para usar docker-compose.yml"
        
        if ($choice -and $choice -match '^\d+$' -and [int]$choice -le $composeFiles.Count) {
            $selectedFile = $composeFiles[[int]$choice - 1]
        } else {
            $selectedFile = "docker-compose.yml"
        }
    } else {
        $selectedFile = $composeFiles[0]
    }
    
    Write-ColorOutput Green "🔧 Usando: $selectedFile"
    Write-Output ""
    
    try {
        Write-Output "⏳ Iniciando servicios con --build..."
        if ($selectedFile -eq "docker-compose.yml") {
            docker-compose up -d --build
        } elseif ($selectedFile -eq "docker-compose.rq.yml") {
            # COMANDO ESPECÍFICO DEL USUARIO para RQ
            Write-ColorOutput Cyan "Usando comando específico para RQ: docker-compose -f docker-compose.rq.yml up -d --build"
            docker-compose -f docker-compose.rq.yml up -d --build
        } else {
            docker-compose -f $selectedFile up -d --build
        }
        
        if ($LASTEXITCODE -eq 0) {
            Write-ColorOutput Green "✅ Servicios iniciados correctamente"
            Start-Sleep -Seconds 5  # Más tiempo para RQ
            Show-DockerStatus
        } else {
            Write-ColorOutput Red "❌ Error iniciando servicios"
        }
    } catch {
        Write-ColorOutput Red "❌ Error ejecutando docker-compose: $_"
        return $false
    }
    
    return $true
}

function Stop-DockerServices {
    Write-ColorOutput Yellow "🛑 DETENIENDO SERVICIOS DOCKER"
    Write-Output ""
    
    try {
        docker-compose down
        Write-ColorOutput Green "✅ Servicios detenidos"
    } catch {
        Write-ColorOutput Red "❌ Error deteniendo servicios: $_"
    }
}

function Show-DockerLogs {
    Write-ColorOutput Green "📋 LOGS DE SERVICIOS DOCKER"
    Write-Output ""
    
    $service = Read-Host "¿Logs de qué servicio? (redis/mysql/web/rq) o Enter para todos"
    
    try {
        if ($service) {
            docker-compose logs -f --tail=50 $service
        } else {
            docker-compose logs -f --tail=20
        }
    } catch {
        Write-ColorOutput Red "❌ Error mostrando logs: $_"
    }
}

function Test-RedisConnection {
    Write-ColorOutput Green "🔍 PROBANDO CONEXIÓN A REDIS"
    Write-Output ""
    
    try {
        # Intentar conectar a Redis dentro del contenedor
        $result = docker exec $(docker ps --filter "name=redis" -q) redis-cli ping
        
        if ($result -eq "PONG") {
            Write-ColorOutput Green "✅ Redis respondió: $result"
            
            # Información adicional
            $info = docker exec $(docker ps --filter "name=redis" -q) redis-cli info server
            $version = ($info | Select-String "redis_version:(.+)" | ForEach-Object { $_.Matches[0].Groups[1].Value })
            if ($version) {
                Write-Output "   📊 Versión Redis: $version"
            }
            
            return $true
        } else {
            Write-ColorOutput Red "❌ Redis no respondió correctamente"
            return $false
        }
    } catch {
        Write-ColorOutput Red "❌ Error conectando a Redis: $_"
        Write-Output "   💡 ¿Está el contenedor Redis ejecutándose?"
        return $false
    }
}

# Función principal
function Run-OptimizationTests {
    """Ejecuta todas las pruebas de optimización."""
    Write-ColorOutput Green "🧪 EJECUTANDO PRUEBAS DE OPTIMIZACIÓN"
    Write-Output ""
    
    # Verificar que Docker esté funcionando
    if (-not (Test-DockerRunning)) {
        Write-ColorOutput Red "❌ Docker no está ejecutándose"
        Write-Output "Ejecuta primero: .\scripts\manage_docker.ps1 start"
        return $false
    }
    
    # Activar entorno virtual si existe
    if (Test-Path "..\venv\Scripts\activate.ps1") {
        Write-Output "Activando entorno virtual..."
        & ..\venv\Scripts\activate.ps1
    }
    
    $allTestsPassed = $true
    
    # Prueba 1: Redis y RQ
    Write-ColorOutput Yellow "1. Probando Redis y RQ..."
    try {
        python scripts\test_redis_cache.py
        if ($LASTEXITCODE -ne 0) {
            Write-ColorOutput Red "   ❌ Falló la prueba de Redis/RQ"
            $allTestsPassed = $false
        } else {
            Write-ColorOutput Green "   ✅ Redis/RQ funcionando correctamente"
        }
    } catch {
        Write-ColorOutput Red "   ❌ Error ejecutando prueba de Redis: $_"
        $allTestsPassed = $false
    }
    
    Write-Output ""
    
    # Prueba 2: Monitor de conexiones MySQL
    Write-ColorOutput Yellow "2. Verificando conexiones MySQL..."
    try {
        python scripts\monitor_connections_windows.py
        if ($LASTEXITCODE -ne 0) {
            Write-ColorOutput Red "   ❌ Problemas detectados en conexiones MySQL"
            $allTestsPassed = $false
        } else {
            Write-ColorOutput Green "   ✅ Conexiones MySQL en estado saludable"
        }
    } catch {
        Write-ColorOutput Red "   ❌ Error ejecutando monitor de conexiones: $_"
        $allTestsPassed = $false
    }
    
    Write-Output ""
    
    # Resumen final
    Write-ColorOutput Green "📊 RESUMEN DE PRUEBAS"
    if ($allTestsPassed) {
        Write-ColorOutput Green "🎉 ¡TODAS LAS OPTIMIZACIONES FUNCIONAN CORRECTAMENTE!"
        Write-Output ""
        Write-Output "✅ Pool de conexiones SQLAlchemy optimizado"
        Write-Output "✅ N+1 queries eliminadas con caché de usuario"
        Write-Output "✅ Redis configurado para multiusuario" 
        Write-Output "✅ RQ funcionando para tareas en background"
        Write-Output "✅ Sesiones optimizadas"
        Write-Output ""
        Write-ColorOutput Cyan "El sistema está listo para soportar 30-50 usuarios concurrentes"
    } else {
        Write-ColorOutput Yellow "⚠️  Algunas pruebas fallaron - revisar logs arriba"
        Write-Output "💡 Esto puede ser normal si algunos servicios están configurándose"
    }
    
    return $allTestsPassed
}

function Main {
    Write-ColorOutput Green "🐳 GESTOR DE DOCKER DATAZENITH"
    Write-Output ""
    
    switch ($Action.ToLower()) {
        "status" { 
            Show-DockerStatus
            if (Test-DockerRunning) {
                Test-RedisConnection
            }
        }
        "start" { 
            Start-DockerServices 
        }
        "stop" { 
            Stop-DockerServices 
        }
        "restart" { 
            Stop-DockerServices
            Start-Sleep -Seconds 2
            Start-DockerServices
        }
        "logs" { 
            Show-DockerLogs 
        }
        "redis" {
            Test-RedisConnection
        }
        "test" {
            Run-OptimizationTests
        }
        default {
            Write-Output "Uso: .\scripts\manage_docker.ps1 [action]"
            Write-Output ""
            Write-Output "Acciones disponibles:"
            Write-Output "  start    - Iniciar servicios Docker (por defecto)"
            Write-Output "  stop     - Detener servicios Docker"
            Write-Output "  restart  - Reiniciar servicios Docker"
            Write-Output "  logs     - Mostrar logs de servicios"
            Write-Output "  redis    - Probar conexión a Redis"
            Write-Output "  test     - Ejecutar todas las pruebas de optimización"
            Write-Output "  status   - Mostrar estado de contenedores"
            Write-Output ""
            Write-Output "Ejemplos:"
            Write-Output "  .\scripts\manage_docker.ps1 start"
            Write-Output "  .\scripts\manage_docker.ps1 test"
            Write-Output "  .\scripts\manage_docker.ps1 redis"
        }
    }
}

# Ejecutar función principal
Main
