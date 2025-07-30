@echo off
setlocal enabledelayedexpansion

REM Script de despliegue para servidor DataZenith BI - Windows
REM Puerto: 30000

echo 🚀 INICIANDO DESPLIEGUE EN SERVIDOR - PUERTO 30000
echo ==================================================

REM Verificar si Docker está corriendo
docker info >nul 2>&1
if !errorlevel! neq 0 (
    echo ❌ ERROR: Docker no está corriendo. Por favor, inicia Docker primero.
    pause
    exit /b 1
)

REM Verificar si Docker Compose está disponible
docker-compose --version >nul 2>&1
if !errorlevel! neq 0 (
    echo ❌ ERROR: Docker Compose no está instalado.
    pause
    exit /b 1
)

echo ✅ Docker y Docker Compose están disponibles

REM Crear directorios necesarios
echo 📁 Creando directorios necesarios...
if not exist "logs" mkdir logs
if not exist "staticfiles" mkdir staticfiles
if not exist "media" mkdir media

REM Verificar si el puerto está en uso
echo 🔍 Verificando disponibilidad del puerto 30000...
netstat -an | findstr ":30000" >nul 2>&1
if !errorlevel! equ 0 (
    echo ⚠️  Puerto 30000 ya está en uso. Deteniendo servicios existentes...
    docker-compose -f docker-compose-server.yml down --remove-orphans
)

REM Limpiar contenedores e imágenes anteriores
echo 🧹 Limpiando contenedores e imágenes anteriores...
docker-compose -f docker-compose-server.yml down --volumes --remove-orphans 2>nul
docker system prune -f 2>nul

REM Construir imágenes
echo 🔨 Construyendo imágenes desde cero...
docker-compose -f docker-compose-server.yml build --no-cache --force-rm

if !errorlevel! equ 0 (
    echo ✅ Imágenes construidas exitosamente
) else (
    echo ❌ ERROR: Error al construir las imágenes
    pause
    exit /b 1
)

REM Iniciar servicios
echo 🚀 Iniciando servicios...
docker-compose -f docker-compose-server.yml up -d

REM Esperar a que los servicios estén listos
echo ⏳ Esperando a que los servicios estén listos...
timeout /t 30 /nobreak >nul

REM Verificar estado de los servicios
echo 🔍 Verificando estado de los servicios...
docker-compose -f docker-compose-server.yml ps

REM Health check
echo 🏥 Realizando health check...
set max_attempts=10
set attempt=1

:health_check_loop
if !attempt! gtr !max_attempts! goto health_check_failed

curl -f http://localhost:30000/health/ >nul 2>&1
if !errorlevel! equ 0 (
    echo ✅ Aplicación está respondiendo correctamente en puerto 30000
    goto health_check_success
) else (
    echo ⚠️  Intento !attempt!/!max_attempts!: Aplicación aún no responde...
    timeout /t 10 /nobreak >nul
    set /a attempt+=1
    goto health_check_loop
)

:health_check_failed
echo ❌ ERROR: La aplicación no respondió después de !max_attempts! intentos
echo 📋 Mostrando logs para diagnóstico...
docker-compose -f docker-compose-server.yml logs --tail=50
pause
exit /b 1

:health_check_success
REM Mostrar información final
echo.
echo 🎉 DESPLIEGUE COMPLETADO EXITOSAMENTE
echo ==================================================
echo 📊 INFORMACIÓN DEL DESPLIEGUE:
echo    🌐 URL: http://localhost:30000
echo    🐳 Contenedores activos:
docker-compose -f docker-compose-server.yml ps

echo.
echo 📋 COMANDOS ÚTILES:
echo    Ver logs: docker-compose -f docker-compose-server.yml logs -f
echo    Detener: docker-compose -f docker-compose-server.yml down
echo    Reiniciar: docker-compose -f docker-compose-server.yml restart
echo    Estado: docker-compose -f docker-compose-server.yml ps

echo.
echo ✅ Despliegue finalizado correctamente
pause
