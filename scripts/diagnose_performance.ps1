# Script para diagnosticar problemas de rendimiento en DataZenith
# Ejecutar con: .\scripts\diagnose_performance.ps1

Write-Host "=== DIAGNÓSTICO DE RENDIMIENTO DATAZENITH ===" -ForegroundColor Green
Write-Host ""

# 1. Verificar contenedores Docker
Write-Host "1. Estado de contenedores Docker:" -ForegroundColor Yellow
try {
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    Write-Host ""
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
}

# 2. Verificar Redis
Write-Host "2. Prueba de Redis:" -ForegroundColor Yellow
try {
    $redisTest = docker exec $(docker ps --filter "name=redis" -q | Select-Object -First 1) redis-cli ping 2>$null
    if ($redisTest -eq "PONG") {
        Write-Host "✅ Redis funcionando" -ForegroundColor Green
    } else {
        Write-Host "❌ Redis no responde" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ Error probando Redis: $_" -ForegroundColor Red
}

# 3. Verificar uso de memoria
Write-Host "3. Uso de memoria del sistema:" -ForegroundColor Yellow
$memory = Get-WmiObject -Class Win32_OperatingSystem
$totalMemory = [math]::Round($memory.TotalVisibleMemorySize / 1MB, 2)
$freeMemory = [math]::Round($memory.FreePhysicalMemory / 1MB, 2)
$usedMemory = $totalMemory - $freeMemory
$memoryPercent = [math]::Round(($usedMemory / $totalMemory) * 100, 2)

Write-Host "   Total: ${totalMemory}GB"
Write-Host "   Usado: ${usedMemory}GB (${memoryPercent}%)"
Write-Host "   Libre: ${freeMemory}GB"

if ($memoryPercent -gt 80) {
    Write-Host "⚠️ Memoria alta - esto puede causar lentitud" -ForegroundColor Yellow
} else {
    Write-Host "✅ Memoria en rango normal" -ForegroundColor Green
}
Write-Host ""

# 4. Verificar uso de CPU
Write-Host "4. Uso de CPU:" -ForegroundColor Yellow
$cpu = Get-WmiObject -Class Win32_Processor | Measure-Object -Property LoadPercentage -Average
$cpuUsage = $cpu.Average
Write-Host "   CPU promedio: ${cpuUsage}%"

if ($cpuUsage -gt 80) {
    Write-Host "⚠️ CPU alta - esto puede causar lentitud" -ForegroundColor Yellow
} else {
    Write-Host "✅ CPU en rango normal" -ForegroundColor Green
}
Write-Host ""

# 5. Verificar logs de Django para errores
Write-Host "5. Verificando logs de la aplicación:" -ForegroundColor Yellow
try {
    $logs = docker logs $(docker ps --filter "name=web" -q | Select-Object -First 1) --tail 10 2>$null
    if ($logs -match "ERROR|Exception|Traceback") {
        Write-Host "⚠️ Se encontraron errores en logs" -ForegroundColor Yellow
        Write-Host "Últimos errores:"
        $logs | Select-String "ERROR|Exception|Traceback" | Select-Object -Last 3
    } else {
        Write-Host "✅ No se encontraron errores recientes" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ No se pudieron obtener logs: $_" -ForegroundColor Red
}
Write-Host ""

# 6. Probar conexión a base de datos
Write-Host "6. Probando optimizaciones implementadas:" -ForegroundColor Yellow
if (Test-Path ".\scripts\monitor_connections_windows.py") {
    try {
        Write-Host "   Ejecutando monitor de conexiones..."
        python .\scripts\monitor_connections_windows.py
    } catch {
        Write-Host "   ❌ Error en monitor: $_" -ForegroundColor Red
    }
} else {
    Write-Host "   ⚠️ Monitor de conexiones no encontrado" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== RECOMENDACIONES ===" -ForegroundColor Cyan

if ($memoryPercent -gt 80) {
    Write-Host "• Cerrar aplicaciones no necesarias para liberar memoria" -ForegroundColor Yellow
}

if ($cpuUsage -gt 80) {
    Write-Host "• Verificar procesos que consumen mucho CPU" -ForegroundColor Yellow
}

Write-Host "• Si el login sigue lento, verificar:"
Write-Host "  - Configuración de base de datos en settings.py"
Write-Host "  - Pool de conexiones en scripts/conexion.py"
Write-Host "  - Caché de Redis funcionando correctamente"
Write-Host "  - Consultas SQL lentas en los logs"

Write-Host ""
Write-Host "Para monitoreo en tiempo real:" -ForegroundColor Green
Write-Host "  docker logs -f \$(docker ps --filter 'name=web' -q)"
