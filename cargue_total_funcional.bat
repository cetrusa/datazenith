@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

REM ============================================================
REM CARGUE TOTAL - COPIA + PROCESAMIENTO + MANTENIMIENTO
REM Esta version ejecuta las etapas validadas del proceso:
REM   1) Copia del archivo maestro desde el servidor UNC
REM   2) Cargue de informacion mediante cargue_infoventas_main.py
REM   3) Ejecucion de los procedimientos de mantenimiento (dentro del script)
REM ============================================================

echo.
echo ============================================================
echo   CARGUE TOTAL INFO PROVEEDORES - DISTRIJASS
echo ============================================================
echo.

echo [%date% %time%] Iniciando proceso total...

REM ------------------------------------------------------------
REM Configuracion de ubicaciones
REM ------------------------------------------------------------
set "SERVIDOR_UNC=Distrijass-bi"
set "UNIDAD_COMPARTIDA=d"
set "RUTA_UNC=\%SERVIDOR_UNC%\%UNIDAD_COMPARTIDA%"
set "RUTA_BASE=%RUTA_UNC%\Distrijass\Sistema Info"
set "CARPETA_DESTINO=D:\Python\DataZenithBi\Info proveedores 2025"
set "ARCHIVO_DESTINO=%CARPETA_DESTINO%\Info proveedores.xlsx"

echo Configuracion activa:
echo   Servidor UNC ............: %SERVIDOR_UNC%
echo   Ruta base servidor ......: %RUTA_BASE%
echo   Carpeta destino local ...: %CARPETA_DESTINO%
echo   Archivo destino ..........: %ARCHIVO_DESTINO%
echo.

REM ------------------------------------------------------------
REM Paso 1: Verificar conectividad y ubicar archivo
REM ------------------------------------------------------------
echo [%date% %time%] Verificando conectividad con %SERVIDOR_UNC%...
ping -n 1 %SERVIDOR_UNC% >nul 2>&1
if !ERRORLEVEL! neq 0 (
	echo ERROR: No se puede contactar al servidor %SERVIDOR_UNC%.
	exit /b 1
)

echo [%date% %time%] Buscando archivo de origen...
set "ARCHIVO_ORIGEN="
set "RUTA_INFO=%RUTA_BASE%\Información\Impactos\info proveedores.xlsx"
if exist "!RUTA_INFO!" (
	set "ARCHIVO_ORIGEN=!RUTA_INFO!"
)

if "!ARCHIVO_ORIGEN!"=="" (
	set "RUTA_INFO=%RUTA_BASE%\Informacion\Impactos\info proveedores.xlsx"
	if exist "!RUTA_INFO!" (
		set "ARCHIVO_ORIGEN=!RUTA_INFO!"
	)
)

if "!ARCHIVO_ORIGEN!"=="" (
	echo ERROR: No se encontro el archivo origen en las rutas esperadas.
	echo    Revisar:
	echo      %RUTA_BASE%\Información\Impactos\info proveedores.xlsx
	echo      %RUTA_BASE%\Informacion\Impactos\info proveedores.xlsx
	exit /b 1
)

echo Archivo origen localizado en: !ARCHIVO_ORIGEN!
echo.

REM ------------------------------------------------------------
REM Paso 2: Copiar archivo al destino local
REM ------------------------------------------------------------
echo [%date% %time%] Preparando carpeta destino...
if not exist "%CARPETA_DESTINO%" (
	mkdir "%CARPETA_DESTINO%"
)

echo [%date% %time%] Copiando archivo al destino local...
copy /Y "!ARCHIVO_ORIGEN!" "%ARCHIVO_DESTINO%" >nul
if !ERRORLEVEL! neq 0 (
	echo ERROR: Fallo la copia del archivo (codigo !ERRORLEVEL!).
	exit /b 1
)

echo Copia completada: %ARCHIVO_DESTINO%
echo.

REM ------------------------------------------------------------
REM Paso 3: Ejecutar cargue Python (incluye procedimientos)
REM ------------------------------------------------------------
echo [%date% %time%] Iniciando fase de cargue Python...
cd /d "D:\Python\DataZenithBi\adminbi"

if not exist "cargue_infoventas_main.py" (
	echo ERROR: No se encontro cargue_infoventas_main.py en %CD%.
	exit /b 1
)

set "PYTHON_BIN=.venv\Scripts\python.exe"
if not exist "%PYTHON_BIN%" (
	echo ADVERTENCIA: No se localizo %PYTHON_BIN%; se usara Python del sistema.
	set "PYTHON_BIN=python"
)

echo Ejecutando: %PYTHON_BIN% cargue_infoventas_main.py --base distrijass --archivo "%ARCHIVO_DESTINO%"
echo.
"%PYTHON_BIN%" cargue_infoventas_main.py --base distrijass --archivo "%ARCHIVO_DESTINO%"
set "RESULTADO_PYTHON=!ERRORLEVEL!"

echo.
echo [%date% %time%] Resultado ejecucion Python: !RESULTADO_PYTHON!

if !RESULTADO_PYTHON! neq 0 (
	echo ERROR: El cargue Python reporto fallas. Revisar logs para mas detalle.
	exit /b !RESULTADO_PYTHON!
)

echo Cargue Python finalizado correctamente (insercion + procedimientos).

REM ------------------------------------------------------------
REM Paso 4: Resumen final
REM ------------------------------------------------------------
echo.
echo ============================================================
echo   RESUMEN FINAL
echo ============================================================
echo Archivo origen .............: !ARCHIVO_ORIGEN!
echo Archivo procesado ..........: %ARCHIVO_DESTINO%
echo Procedimientos ejecutados ..: sp_infoventas_full_maintenance (desde Python)
echo ============================================================

echo.
echo [%date% %time%] Proceso total completado con exito.
exit /b 0
```}