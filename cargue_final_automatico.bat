@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

echo.
echo ============================================================
echo   CARGUE AUTOMATICO - INFO PROVEEDORES DISTRIJASS
echo ============================================================
echo.

echo [%date% %time%] Iniciando proceso automatico completo...

REM Configuracion de rutas
set "SERVIDOR_UNC=Distrijass-bi"
set "UNIDAD_COMPARTIDA=d"
set "RUTA_UNC=\\%SERVIDOR_UNC%\%UNIDAD_COMPARTIDA%"
set "RUTA_BASE=%RUTA_UNC%\Distrijass\Sistema Info"
set "RUTA_DESTINO=D:\Python\DataZenithBi\Info proveedores 2025\Info proveedores.xlsx"

echo Configuracion:
echo   Servidor: %SERVIDOR_UNC%
echo   Archivo destino: %RUTA_DESTINO%
echo.

REM ============================================================
REM FASE 1: COPIAR ARCHIVO
REM ============================================================

echo [%date% %time%] === FASE 1: COPIA DE ARCHIVO ===
echo.

echo [%date% %time%] Verificando conectividad...
ping -n 1 %SERVIDOR_UNC% >nul 2>&1
if !ERRORLEVEL! neq 0 (
    echo ❌ ERROR: No se puede conectar al servidor %SERVIDOR_UNC%
    exit /b 1
)

echo [%date% %time%] Buscando archivo...

set "ARCHIVO_ENCONTRADO="
set "RUTA_INFO=%RUTA_BASE%\Información\Impactos\info proveedores.xlsx"
if exist "!RUTA_INFO!" (
    set "ARCHIVO_ENCONTRADO=!RUTA_INFO!"
    echo ✅ Archivo encontrado: !ARCHIVO_ENCONTRADO!
) else (
    set "RUTA_INFO=%RUTA_BASE%\Informacion\Impactos\info proveedores.xlsx"
    if exist "!RUTA_INFO!" (
        set "ARCHIVO_ENCONTRADO=!RUTA_INFO!"
        echo ✅ Archivo encontrado: !ARCHIVO_ENCONTRADO!
    )
)

if "!ARCHIVO_ENCONTRADO!"=="" (
    echo ❌ AVISO: No se encontro el archivo en la unidad de red
    echo ❌ Verificando si existe archivo local previo...
    
    if exist "%RUTA_DESTINO%" (
        echo ✅ Se encontro archivo local en: %RUTA_DESTINO%
        echo ✅ Continuando con el archivo existente...
        set "USAR_ARCHIVO_LOCAL=1"
    ) else (
        echo ❌ ERROR: No hay archivo de red ni archivo local disponible
        exit /b 1
    )
) else (
    set "USAR_ARCHIVO_LOCAL=0"
)

echo [%date% %time%] Creando directorio destino...
if not exist "D:\Python\DataZenithBi\Info proveedores 2025" (
    mkdir "D:\Python\DataZenithBi\Info proveedores 2025"
)

if "!USAR_ARCHIVO_LOCAL!"=="0" (
    echo [%date% %time%] Copiando archivo desde red...
    copy /Y "!ARCHIVO_ENCONTRADO!" "%RUTA_DESTINO%" >nul

    if !ERRORLEVEL! neq 0 (
        echo ❌ ERROR: Fallo la copia, verificando archivo local...
        if exist "%RUTA_DESTINO%" (
            echo ✅ Usando archivo local existente
        ) else (
            echo ❌ ERROR: No se puede copiar ni encontrar archivo local
            exit /b 1
        )
    ) else (
        echo [%date% %time%] ✅ Archivo copiado exitosamente desde red
    )
) else (
    echo [%date% %time%] ✅ Usando archivo local existente
)
echo.

REM ============================================================
REM FASE 2: EJECUTAR PYTHON
REM ============================================================

echo [%date% %time%] === FASE 2: CARGUE PYTHON ===
echo.

cd /d "D:\Python\DataZenithBi\adminbi"

if not exist "cargue_infoventas_main.py" (
    echo ❌ ERROR: Script Python no encontrado
    exit /b 1
)

echo [%date% %time%] Activando entorno virtual...
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat" >nul
)

echo [%date% %time%] Ejecutando cargue Python...
echo.

powershell -Command "& '.venv\Scripts\python.exe' cargue_infoventas_main.py --base distrijass --archivo '%RUTA_DESTINO%'"

set "PYTHON_RESULT=!ERRORLEVEL!"

echo.
echo [%date% %time%] === PROCESO FINALIZADO ===

if !PYTHON_RESULT! equ 0 (
    echo [%date% %time%] ✅ CARGUE COMPLETADO EXITOSAMENTE
    echo.
    echo ============================================================
    echo   RESUMEN FINAL
    echo ============================================================
    if "!USAR_ARCHIVO_LOCAL!"=="1" (
        echo ✅ Archivo: %RUTA_DESTINO% (ARCHIVO LOCAL)
        echo ⚠️  AVISO: Se uso archivo local (unidad de red no disponible)
    ) else (
        echo ✅ Archivo: !ARCHIVO_ENCONTRADO!
    )
    echo ✅ Destino: %RUTA_DESTINO%
    echo ✅ Base de datos: distrijass - CARGUE EXITOSO
    echo ============================================================
) else (
    echo [%date% %time%] ❌ ERROR EN EL CARGUE
    echo Codigo de error: !PYTHON_RESULT!
)

echo.
exit /b !PYTHON_RESULT!