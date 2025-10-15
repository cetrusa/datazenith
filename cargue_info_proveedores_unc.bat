@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
REM ============================================================
REM CARGUE AUTOMATICO - VERSION CON RUTA UNC
REM ============================================================
REM Esta version usa rutas UNC y maneja caracteres especiales
REM como tildes y eñes correctamente
REM ============================================================

echo.
echo ============================================================
echo   CARGUE AUTOMATICO (UNC) - INFO PROVEEDORES DISTRIJASS
echo ============================================================
echo.

echo [%date% %time%] Iniciando proceso con ruta UNC...
echo.

REM ============================================================
REM CONFIGURACION - SERVIDOR DISTRIJASS-BI
REM ============================================================

REM Servidor: Distrijass-bi, Unidad: d
set "SERVIDOR_UNC=\\Distrijass-bi\d"

REM Definir rutas sin caracteres especiales
set "CARPETA_BASE=%SERVIDOR_UNC%\Distrijass\Sistema Info"
set "CARPETA_IMPACTOS=%CARPETA_BASE%\Informacion\Impactos"
set "ARCHIVO_EXCEL=info proveedores.xlsx"
set "RUTA_ORIGEN=%CARPETA_IMPACTOS%\%ARCHIVO_EXCEL%"
set "RUTA_DESTINO=D:\Python\DataZenithBi\Info proveedores 2025\Info proveedores.xlsx"

REM Rutas alternativas comunes (por si la carpeta tiene nombre diferente)
set "CARPETA_ALT1=%CARPETA_BASE%\Información\Impactos"
set "CARPETA_ALT2=%SERVIDOR_UNC%\Distrijass\SistemaInfo\Impactos"
set "CARPETA_ALT3=%SERVIDOR_UNC%\Distrijass\Sistema_Info\Informacion\Impactos"

echo Configuracion:
echo   Servidor: Distrijass-bi
echo   Unidad compartida: d
echo   Ruta completa: %SERVIDOR_UNC%
echo   Archivo origen: %RUTA_ORIGEN%
echo   Archivo destino: %RUTA_DESTINO%
echo.

REM ============================================================
REM VERIFICACION Y DIAGNOSTICO
REM ============================================================

echo [%date% %time%] Verificando conectividad con Distrijass-bi...

REM Verificar si se puede hacer ping al servidor
ping -n 1 Distrijass-bi >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ⚠️  No se puede hacer ping al servidor Distrijass-bi
    echo    Verifique la conectividad de red
)

echo Intentando acceder a la unidad compartida d en Distrijass-bi...
dir "%SERVIDOR_UNC%" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo.
    echo ❌ ERROR: No se puede acceder a \\Distrijass-bi\d
    echo.
    echo Posibles soluciones:
    echo 1. Verificar credenciales de red:
    echo    net use \\Distrijass-bi\d /user:DOMINIO\usuario
    echo 2. Verificar que el servidor Distrijass-bi este encendido
    echo 3. Verificar que la unidad d este compartida
    echo 4. Contactar al administrador de red
    echo.
    echo Para mapear manualmente:
    echo    net use Z: \\Distrijass-bi\d /persistent:yes
    echo.
    pause
    exit /b 1
)

REM Verificar archivo origen en múltiples ubicaciones
echo [%date% %time%] Buscando archivo en ubicaciones posibles...

set "ARCHIVO_ENCONTRADO="

REM Intentar ubicación principal (sin tilde)
if exist "%RUTA_ORIGEN%" (
    set "ARCHIVO_ENCONTRADO=%RUTA_ORIGEN%"
    echo ✅ Archivo encontrado en: %RUTA_ORIGEN%
    goto :archivo_encontrado
)

REM Intentar ubicación alternativa 1 (con tilde)
set "RUTA_ALT1=%CARPETA_ALT1%\%ARCHIVO_EXCEL%"
if exist "%RUTA_ALT1%" (
    set "ARCHIVO_ENCONTRADO=%RUTA_ALT1%"
    echo ✅ Archivo encontrado en: %RUTA_ALT1%
    goto :archivo_encontrado
)

REM Intentar ubicación alternativa 2
set "RUTA_ALT2_FULL=%CARPETA_ALT2%\%ARCHIVO_EXCEL%"
if exist "%RUTA_ALT2_FULL%" (
    set "ARCHIVO_ENCONTRADO=%RUTA_ALT2_FULL%"
    echo ✅ Archivo encontrado en: %RUTA_ALT2_FULL%
    goto :archivo_encontrado
)

REM Intentar ubicación alternativa 3
set "RUTA_ALT3_FULL=%CARPETA_ALT3%\%ARCHIVO_EXCEL%"
if exist "%RUTA_ALT3_FULL%" (
    set "ARCHIVO_ENCONTRADO=%RUTA_ALT3_FULL%"
    echo ✅ Archivo encontrado en: %RUTA_ALT3_FULL%
    goto :archivo_encontrado
)

REM Si no se encuentra, mostrar diagnóstico
echo.
echo ❌ ERROR: Archivo no encontrado en ninguna ubicación
echo.
echo Ubicaciones buscadas:
echo 1. %RUTA_ORIGEN%
echo 2. %RUTA_ALT1%
echo 3. %RUTA_ALT2_FULL%
echo 4. %RUTA_ALT3_FULL%
echo.

echo Explorando estructura de carpetas...
echo.
echo === Contenido de %SERVIDOR_UNC%\Distrijass\ ===
dir "%SERVIDOR_UNC%\Distrijass\" /b 2>nul

echo.
echo === Contenido de %CARPETA_BASE%\ ===
dir "%CARPETA_BASE%" /b 2>nul

echo.
echo === Buscando archivos Excel con 'proveedor' en el nombre ===
for /r "%SERVIDOR_UNC%\Distrijass" %%f in (*proveedor*.xlsx) do echo %%f
for /r "%SERVIDOR_UNC%\Distrijass" %%f in (*info*.xlsx) do echo %%f

echo.
pause
exit /b 1

:archivo_encontrado

REM ============================================================
REM COPIA Y PROCESAMIENTO
REM ============================================================

echo [%date% %time%] Creando directorio destino...
if not exist "D:\Python\DataZenithBi\Info proveedores 2025\" (
    mkdir "D:\Python\DataZenithBi\Info proveedores 2025\"
)

echo [%date% %time%] Copiando archivo...
echo Origen:  %ARCHIVO_ENCONTRADO%
echo Destino: %RUTA_DESTINO%
echo.

copy /Y "%ARCHIVO_ENCONTRADO%" "%RUTA_DESTINO%"

if %ERRORLEVEL% neq 0 (
    echo ❌ ERROR: Fallo la copia (codigo: %ERRORLEVEL%)
    pause
    exit /b 1
)

echo [%date% %time%] ✅ Archivo copiado exitosamente
echo.

REM ============================================================
REM EJECUTAR CARGUE PYTHON
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
    echo.
    echo Archivos Python disponibles:
    dir *.py /b 2>nul
    echo.
    pause
    exit /b 1
)

echo ✅ Script Python encontrado: cargue_infoventas_main.py
echo.

echo [%date% %time%] Verificando entorno virtual...
if exist ".venv\Scripts\activate.bat" (
    echo ✅ Entorno virtual encontrado en: %CD%\.venv\Scripts\activate.bat
    echo [%date% %time%] Activando entorno virtual...
    call ".venv\Scripts\activate.bat"
    echo [%date% %time%] ✅ Entorno virtual activado - ERRORLEVEL: %ERRORLEVEL%
) else (
    echo ⚠️  No se encontro entorno virtual en: %CD%\.venv\Scripts\activate.bat
    echo ⚠️  Usando Python del sistema
)

echo.
echo [%date% %time%] Verificando Python disponible...
echo Intentando: python --version
python --version 2>nul
set "PYTHON_CHECK=%ERRORLEVEL%"
echo Python check result: %PYTHON_CHECK%

if %PYTHON_CHECK% neq 0 (
    echo ⚠️  Python comando 'python' no disponible, intentando ruta completa...
    echo Intentando: "%CD%\.venv\Scripts\python.exe" --version
    "%CD%\.venv\Scripts\python.exe" --version 2>nul
    set "PYTHON_CHECK=%ERRORLEVEL%"
    echo Python full path check result: %PYTHON_CHECK%
    
    if !PYTHON_CHECK! neq 0 (
        echo ❌ ERROR: Python no esta disponible por ninguna ruta
        echo.
        echo Diagnostico:
        echo - Entorno virtual: %CD%\.venv\Scripts\
        dir "%CD%\.venv\Scripts\python*" 2>nul
        echo.
        pause
        exit /b 1
    )
)

echo.
echo [%date% %time%] === EJECUTANDO CARGUE DE DATOS ===
echo.
echo Comando a ejecutar:
echo "%CD%\.venv\Scripts\python.exe" cargue_infoventas_main.py --base distrijass --archivo "%RUTA_DESTINO%"
echo.

rem Verificar que estamos en el directorio correcto
echo [%date% %time%] Verificando directorio de trabajo...
echo Directorio actual: %CD%
echo Archivo Python: %CD%\cargue_infoventas_main.py

if not exist "%CD%\cargue_infoventas_main.py" (
    echo ❌ ERROR: No se encuentra el archivo cargue_infoventas_main.py en el directorio actual
    echo Cambiando al directorio correcto...
    cd /d "D:\Python\DataZenithBi\adminbi"
    echo Nuevo directorio: %CD%
)

if not exist "%CD%\cargue_infoventas_main.py" (
    echo ❌ ERROR CRITICO: No se puede localizar cargue_infoventas_main.py
    pause
    exit /b 1
)

echo.
echo Presione cualquier tecla para continuar con el cargue...
pause

echo [%date% %time%] Ejecutando comando Python...
"%CD%\.venv\Scripts\python.exe" cargue_infoventas_main.py --base distrijass --archivo "%RUTA_DESTINO%"

set "PYTHON_RESULT=%ERRORLEVEL%"
echo.
echo [%date% %time%] === CARGUE PYTHON FINALIZADO ===
echo Codigo de salida: %PYTHON_RESULT%

echo.
if %PYTHON_RESULT% equ 0 (
    echo [%date% %time%] ✅ PROCESO COMPLETADO EXITOSAMENTE
    echo.
    echo ============================================================
    echo   RESUMEN FINAL
    echo ============================================================
    echo ✅ Archivo copiado desde: %ARCHIVO_ENCONTRADO%
    echo ✅ Archivo guardado en:   %RUTA_DESTINO%
    echo ✅ Cargue Python ejecutado correctamente
    echo ✅ Base de datos:         distrijass
    echo ============================================================
) else (
    echo [%date% %time%] ❌ ERROR EN EL CARGUE PYTHON
    echo    Codigo de error: %PYTHON_RESULT%
    echo.
    echo ============================================================
    echo   RESUMEN CON ERRORES
    echo ============================================================
    echo ✅ Archivo copiado correctamente
    echo ❌ Error en el cargue Python (codigo: %PYTHON_RESULT%)
    echo.
    echo Posibles causas:
    echo - Error de conexion a la base de datos
    echo - Formato incorrecto del archivo Excel
    echo - Problema con las dependencias Python
    echo ============================================================
)

echo.
echo Presione cualquier tecla para salir...
pause
exit /b %PYTHON_RESULT%