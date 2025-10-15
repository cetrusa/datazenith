@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
REM ============================================================
REM CARGUE AUTOMATICO - VERSION SIN PAUSAS PARA AUTOMATIZACION
REM ============================================================
REM Esta version ejecuta completamente sin pausas ni intervenciones
REM ============================================================

echo.
echo ============================================================
echo   CARGUE AUTOMATICO - INFO PROVEEDORES DISTRIJASS
echo ============================================================
echo.

echo [%date% %time%] Iniciando proceso automatico...

REM Configuracion de rutas
set "SERVIDOR_UNC=Distrijass-bi"
set "UNIDAD_COMPARTIDA=d"
set "RUTA_UNC=\\%SERVIDOR_UNC%\%UNIDAD_COMPARTIDA%"
set "RUTA_BASE=%RUTA_UNC%\Distrijass\Sistema Info"

REM Archivo destino
set "RUTA_DESTINO=D:\Python\DataZenithBi\Info proveedores 2025\Info proveedores.xlsx"

echo Configuracion:
echo   Servidor: %SERVIDOR_UNC%
echo   Unidad compartida: %UNIDAD_COMPARTIDA%
echo   Ruta completa: %RUTA_UNC%
echo   Archivo destino: %RUTA_DESTINO%
echo.

REM ============================================================
REM FASE 1: BUSCAR Y COPIAR ARCHIVO
REM ============================================================

echo [%date% %time%] Verificando conectividad con %SERVIDOR_UNC%...
ping -n 1 %SERVIDOR_UNC% >nul 2>&1
if !ERRORLEVEL! neq 0 (
    echo ❌ ERROR: No se puede conectar al servidor %SERVIDOR_UNC%
    exit /b 1
)

echo [%date% %time%] Buscando archivo en ubicaciones posibles...

REM Intentar con tilde
set "ARCHIVO_ENCONTRADO="
set "RUTA_INFO=%RUTA_BASE%\Información\Impactos\info proveedores.xlsx"
if exist "!RUTA_INFO!" (
    set "ARCHIVO_ENCONTRADO=!RUTA_INFO!"
    echo ✅ Archivo encontrado en: !ARCHIVO_ENCONTRADO!
)

REM Intentar sin tilde si no se encontro
if "!ARCHIVO_ENCONTRADO!"=="" (
    set "RUTA_INFO=%RUTA_BASE%\Informacion\Impactos\info proveedores.xlsx"
    if exist "!RUTA_INFO!" (
        set "ARCHIVO_ENCONTRADO=!RUTA_INFO!"
        echo ✅ Archivo encontrado en: !ARCHIVO_ENCONTRADO!
    )
)

if "!ARCHIVO_ENCONTRADO!"=="" (
    echo ❌ ERROR: No se pudo encontrar el archivo en ninguna ubicacion
    echo Ubicaciones verificadas:
    echo   - %RUTA_BASE%\Información\Impactos\info proveedores.xlsx
    echo   - %RUTA_BASE%\Informacion\Impactos\info proveedores.xlsx
    exit /b 1
)

echo [%date% %time%] Creando directorio destino si no existe...
if not exist "D:\Python\DataZenithBi\Info proveedores 2025" (
    mkdir "D:\Python\DataZenithBi\Info proveedores 2025"
)

echo [%date% %time%] Copiando archivo...
echo Origen:  !ARCHIVO_ENCONTRADO!
echo Destino: %RUTA_DESTINO%
echo.

copy /Y "!ARCHIVO_ENCONTRADO!" "%RUTA_DESTINO%"

if !ERRORLEVEL! neq 0 (
    echo ❌ ERROR: Fallo la copia (codigo: !ERRORLEVEL!)
    exit /b 1
)

echo [%date% %time%] ✅ Archivo copiado exitosamente
echo.

REM ============================================================
REM FASE 2: EJECUTAR CARGUE PYTHON
REM ============================================================

echo [%date% %time%] === INICIANDO FASE DE CARGUE PYTHON ===
echo.

echo [%date% %time%] Cambiando al directorio de trabajo...
cd /d "D:\Python\DataZenithBi\adminbi"

echo Directorio actual: %CD%
echo.

REM Verificar que el script Python existe
if not exist "cargue_infoventas_main.py" (
    echo ❌ ERROR: No se encuentra cargue_infoventas_main.py en %CD%
    exit /b 1
)

echo ✅ Script Python encontrado: cargue_infoventas_main.py
echo.

echo [%date% %time%] Verificando entorno virtual...
if exist ".venv\Scripts\activate.bat" (
    echo ✅ Entorno virtual encontrado en: %CD%\.venv\Scripts\activate.bat
    echo [%date% %time%] Activando entorno virtual...
    call ".venv\Scripts\activate.bat"
    echo [%date% %time%] ✅ Entorno virtual activado - ERRORLEVEL: !ERRORLEVEL!
) else (
    echo ⚠️  No se encontro entorno virtual en: %CD%\.venv\Scripts\activate.bat
    echo ⚠️  Usando Python del sistema
)

echo.
echo [%date% %time%] === EJECUTANDO CARGUE DE DATOS ===
echo.
echo Comando a ejecutar:
echo "%CD%\.venv\Scripts\python.exe" cargue_infoventas_main.py --base distrijass --archivo "%RUTA_DESTINO%"
echo.

echo [%date% %time%] Ejecutando comando Python...
echo.
echo === INICIANDO EJECUCION PYTHON ===
"%CD%\.venv\Scripts\python.exe" cargue_infoventas_main.py --base distrijass --archivo "%RUTA_DESTINO%" 2>&1
echo === FIN EJECUCION PYTHON ===

set "PYTHON_RESULT=!ERRORLEVEL!"
echo.
echo [%date% %time%] === CARGUE PYTHON FINALIZADO ===
echo Codigo de salida: !PYTHON_RESULT!

echo.
if !PYTHON_RESULT! equ 0 (
    echo [%date% %time%] ✅ PROCESO COMPLETADO EXITOSAMENTE
    echo.
    echo ============================================================
    echo   RESUMEN FINAL
    echo ============================================================
    echo ✅ Archivo copiado desde: !ARCHIVO_ENCONTRADO!
    echo ✅ Archivo guardado en:   %RUTA_DESTINO%
    echo ✅ Cargue Python ejecutado correctamente
    echo ✅ Base de datos:         distrijass
    echo ============================================================
) else (
    echo [%date% %time%] ❌ ERROR EN EL CARGUE PYTHON
    echo    Codigo de error: !PYTHON_RESULT!
    echo.
    echo ============================================================
    echo   RESUMEN CON ERRORES
    echo ============================================================
    echo ✅ Archivo copiado correctamente
    echo ❌ Error en el cargue Python (codigo: !PYTHON_RESULT!)
    echo.
    echo Posibles causas:
    echo - Error de conexion a la base de datos
    echo - Formato incorrecto del archivo Excel
    echo - Problema con las dependencias Python
    echo ============================================================
)

echo.
echo [%date% %time%] Proceso automatico finalizado
exit /b !PYTHON_RESULT!