@echo off
chcp 65001 >nul
REM ============================================================
REM CARGUE SIMPLE - SIN CARACTERES ESPECIALES
REM ============================================================
echo.
echo ============================================================
echo   CARGUE AUTOMATICO - INFO PROVEEDORES (SIMPLE)
echo ============================================================
echo.

echo [%date% %time%] Iniciando proceso...

REM ============================================================
REM BUSQUEDA INTELIGENTE DEL ARCHIVO
REM ============================================================

echo [%date% %time%] Buscando archivo en el servidor...

REM Definir servidor
set "SERVIDOR=\\Distrijass-bi\d"

REM Buscar el archivo en cualquier ubicación del servidor
echo Buscando archivos con 'proveedor' en toda la unidad...
for /f "delims=" %%a in ('dir "%SERVIDOR%\*proveedor*.xlsx" /s /b 2^>nul') do (
    echo Encontrado: %%a
    set "ARCHIVO_ORIGEN=%%a"
    goto :encontrado
)

REM Buscar archivos con 'info' en el nombre
echo Buscando archivos con 'info' en toda la unidad...
for /f "delims=" %%a in ('dir "%SERVIDOR%\*info*.xlsx" /s /b 2^>nul') do (
    echo Encontrado: %%a
    set "ARCHIVO_ORIGEN=%%a"
    goto :encontrado
)

echo ❌ No se encontro ningun archivo Excel con 'proveedor' o 'info'
echo.
echo Mostrando archivos Excel en el servidor:
dir "%SERVIDOR%\*.xlsx" /s /b 2>nul
echo.
pause
exit /b 1

:encontrado
echo.
echo ✅ Archivo encontrado: %ARCHIVO_ORIGEN%
echo.

REM ============================================================
REM COPIA Y PROCESAMIENTO
REM ============================================================

set "DESTINO=D:\Python\DataZenithBi\Info proveedores 2025\Info proveedores.xlsx"

echo [%date% %time%] Creando directorio destino...
if not exist "D:\Python\DataZenithBi\Info proveedores 2025\" (
    mkdir "D:\Python\DataZenithBi\Info proveedores 2025\"
)

echo [%date% %time%] Copiando archivo...
copy /Y "%ARCHIVO_ORIGEN%" "%DESTINO%"

if %ERRORLEVEL% neq 0 (
    echo ❌ Error al copiar archivo
    pause
    exit /b 1
)

echo ✅ Archivo copiado exitosamente
echo.

REM ============================================================
REM EJECUTAR CARGUE
REM ============================================================

cd /d "D:\Python\DataZenithBi\adminbi"

echo [%date% %time%] Activando entorno Python...
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    echo ✅ Entorno virtual activado
)

echo.
echo [%date% %time%] Ejecutando cargue de datos...
python cargue_infoventas_main.py --base distrijass --archivo "%DESTINO%"

if %ERRORLEVEL% equ 0 (
    echo.
    echo [%date% %time%] ✅ PROCESO COMPLETADO EXITOSAMENTE
) else (
    echo.
    echo [%date% %time%] ❌ ERROR EN EL CARGUE
)

echo.
pause
exit /b %ERRORLEVEL%