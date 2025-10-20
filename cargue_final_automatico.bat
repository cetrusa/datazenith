@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
REM Establecer UTF-8 para Python
set PYTHONIOENCODING=utf-8

REM ============================================================
REM CONFIGURACION DE LOGGING
REM ============================================================
set "LOG_DIR=D:\Logs\DataZenithBI"
set "LOG_FILE=%LOG_DIR%\cargue_distrijass.log"
set "LOG_SUMMARY=%LOG_DIR%\cargue_summary_latest.log"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo. >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"
echo INICIO: %date% %time% >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"

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

echo [%date% %time%] Configuracion: >> "%LOG_FILE%"
echo [%date% %time%]   Servidor: %SERVIDOR_UNC% >> "%LOG_FILE%"
echo [%date% %time%]   Archivo destino: %RUTA_DESTINO% >> "%LOG_FILE%"

REM ============================================================
REM FASE 1: COPIAR ARCHIVO
REM ============================================================

echo [%date% %time%] === FASE 1: COPIA DE ARCHIVO ===
echo [%date% %time%] === FASE 1: COPIA DE ARCHIVO === >> "%LOG_FILE%"
echo.

echo [%date% %time%] Verificando conectividad...
echo [%date% %time%] Verificando conectividad al servidor %SERVIDOR_UNC%... >> "%LOG_FILE%"

ping -n 1 %SERVIDOR_UNC% >nul 2>&1
if !ERRORLEVEL! neq 0 (
    echo ❌ ERROR: No se puede conectar al servidor %SERVIDOR_UNC%
    echo [%date% %time%] ❌ ERROR: No se puede conectar al servidor %SERVIDOR_UNC% >> "%LOG_FILE%"
    call :log_summary FALLO Conectividad
    exit /b 1
)

echo [%date% %time%] Buscando archivo...

echo [%date% %time%] Buscando archivo... >> "%LOG_FILE%"

set "ARCHIVO_ENCONTRADO="
set "RUTA_INFO=%RUTA_BASE%\Información\Impactos\info proveedores.xlsx"
if exist "!RUTA_INFO!" (
    set "ARCHIVO_ENCONTRADO=!RUTA_INFO!"
    echo ✅ Archivo encontrado: !ARCHIVO_ENCONTRADO!
    echo [%date% %time%] ✅ Archivo encontrado: !ARCHIVO_ENCONTRADO! >> "%LOG_FILE%"
) else (
    set "RUTA_INFO=%RUTA_BASE%\Informacion\Impactos\info proveedores.xlsx"
    if exist "!RUTA_INFO!" (
        set "ARCHIVO_ENCONTRADO=!RUTA_INFO!"
        echo ✅ Archivo encontrado: !ARCHIVO_ENCONTRADO!
        echo [%date% %time%] ✅ Archivo encontrado: !ARCHIVO_ENCONTRADO! >> "%LOG_FILE%"
    )
)

if "!ARCHIVO_ENCONTRADO!"=="" (
    echo ❌ AVISO: No se encontro el archivo en la unidad de red
    echo ❌ Verificando si existe archivo local previo...
    echo [%date% %time%] ❌ AVISO: No se encontro el archivo en la unidad de red >> "%LOG_FILE%"
    echo [%date% %time%] ❌ Verificando si existe archivo local previo... >> "%LOG_FILE%"
    
    if exist "%RUTA_DESTINO%" (
        echo ✅ Se encontro archivo local en: %RUTA_DESTINO%
        echo ✅ Continuando con el archivo existente...
        echo [%date% %time%] ✅ Se encontro archivo local en: %RUTA_DESTINO% >> "%LOG_FILE%"
        echo [%date% %time%] ✅ Continuando con el archivo existente... >> "%LOG_FILE%"
        set "USAR_ARCHIVO_LOCAL=1"
    ) else (
        echo ❌ ERROR: No hay archivo de red ni archivo local disponible
        echo [%date% %time%] ❌ ERROR CRITICO: No hay archivo de red ni archivo local disponible >> "%LOG_FILE%"
        call :log_summary FALLO "Archivo no disponible"
        exit /b 1
    )
) else (
    set "USAR_ARCHIVO_LOCAL=0"
)

echo [%date% %time%] Creando directorio destino...
echo [%date% %time%] Creando directorio destino... >> "%LOG_FILE%"

if not exist "D:\Python\DataZenithBi\Info proveedores 2025" (
    mkdir "D:\Python\DataZenithBi\Info proveedores 2025"
)

if "!USAR_ARCHIVO_LOCAL!"=="0" (
    echo [%date% %time%] Copiando archivo desde red...
    echo [%date% %time%] Copiando archivo desde red... >> "%LOG_FILE%"
    
    copy /Y "!ARCHIVO_ENCONTRADO!" "%RUTA_DESTINO%" >nul

    if !ERRORLEVEL! neq 0 (
        echo ❌ ERROR: Fallo la copia, verificando archivo local...
        echo [%date% %time%] ❌ ERROR: Fallo la copia, verificando archivo local... >> "%LOG_FILE%"
        
        if exist "%RUTA_DESTINO%" (
            echo ✅ Usando archivo local existente
            echo [%date% %time%] ✅ Usando archivo local existente >> "%LOG_FILE%"
        ) else (
            echo ❌ ERROR: No se puede copiar ni encontrar archivo local
            echo [%date% %time%] ❌ ERROR CRITICO: No se puede copiar ni encontrar archivo local >> "%LOG_FILE%"
            call :log_summary FALLO "Copia de archivo"
            exit /b 1
        )
    ) else (
        echo [%date% %time%] ✅ Archivo copiado exitosamente desde red
        echo [%date% %time%] ✅ Archivo copiado exitosamente desde red >> "%LOG_FILE%"
    )
) else (
    echo [%date% %time%] ✅ Usando archivo local existente
    echo [%date% %time%] ✅ Usando archivo local existente >> "%LOG_FILE%"
)
echo.

REM ============================================================
REM FASE 2: VALIDAR ARCHIVO EXCEL
REM ============================================================

echo [%date% %time%] === FASE 2: VALIDACION DE ARCHIVO ===
echo [%date% %time%] === FASE 2: VALIDACION DE ARCHIVO === >> "%LOG_FILE%"
echo.

echo [%date% %time%] Validando archivo Excel...
echo [%date% %time%] Validando archivo Excel... >> "%LOG_FILE%"

REM Verificar que el archivo no este vacio (>0 bytes)
for %%A in ("%RUTA_DESTINO%") do (
    set "FILE_SIZE=%%~zA"
)

if !FILE_SIZE! equ 0 (
    echo ❌ ERROR: Archivo Excel esta vacio ^(0 bytes^)
    echo [%date% %time%] ❌ ERROR: Archivo Excel esta vacio ^(0 bytes^) >> "%LOG_FILE%"
    call :log_summary FALLO "Archivo vacio"
    exit /b 1
)

echo [%date% %time%] ✅ Archivo valido - Tamano: !FILE_SIZE! bytes
echo [%date% %time%] ✅ Archivo valido - Tamano: !FILE_SIZE! bytes >> "%LOG_FILE%"
echo.

REM ============================================================
REM FASE 3: EJECUTAR PYTHON (CON REINTENTOS)
REM ============================================================

echo [%date% %time%] === FASE 3: CARGUE PYTHON ===
echo [%date% %time%] === FASE 3: CARGUE PYTHON === >> "%LOG_FILE%"
echo.

cd /d "D:\Python\DataZenithBi\adminbi"

if not exist "cargue_infoventas_main.py" (
    echo ❌ ERROR: Script Python no encontrado
    echo [%date% %time%] ❌ ERROR: Script Python no encontrado en cargue_infoventas_main.py >> "%LOG_FILE%"
    call :log_summary FALLO "Script Python no encontrado"
    exit /b 1
)

REM Configurar reintentos
set "MAX_REINTENTOS=3"
set "INTENTO=1"
set "PYTHON_RESULT=1"

:reintentar_cargue
if !INTENTO! leq !MAX_REINTENTOS! (
    echo [%date% %time%] Intento !INTENTO! de !MAX_REINTENTOS!...
    echo [%date% %time%] Intento !INTENTO! de !MAX_REINTENTOS!... >> "%LOG_FILE%"

    echo [%date% %time%] Activando entorno virtual...
    echo [%date% %time%] Activando entorno virtual... >> "%LOG_FILE%"
    
    if exist ".venv\Scripts\activate.bat" (
        call ".venv\Scripts\activate.bat" >nul
    )

    echo [%date% %time%] Ejecutando cargue Python...
    echo [%date% %time%] Ejecutando cargue Python... >> "%LOG_FILE%"
    echo.

    powershell -Command "& '.venv\Scripts\python.exe' cargue_infoventas_main.py --base distrijass --archivo '%RUTA_DESTINO%'" >> "%LOG_FILE%" 2>&1

    set "PYTHON_RESULT=!ERRORLEVEL!"

    if !PYTHON_RESULT! equ 0 (
        echo [%date% %time%] ✅ Intento !INTENTO! exitoso
        echo [%date% %time%] ✅ Intento !INTENTO! exitoso >> "%LOG_FILE%"
        goto :cargue_exitoso
    ) else (
        if !INTENTO! lss !MAX_REINTENTOS! (
            echo [%date% %time%] ❌ Intento !INTENTO! fallo - Esperando 30 segundos...
            echo [%date% %time%] ❌ Intento !INTENTO! fallo - Esperando 30 segundos... >> "%LOG_FILE%"
            timeout /t 30 /nobreak
            
            set /a INTENTO=!INTENTO! + 1
            goto :reintentar_cargue
        ) else (
            goto :cargue_fallo
        )
    )
)

REM ============================================================
REM ETIQUETAS DE RESULTADO
REM ============================================================

:cargue_exitoso
echo.
echo [%date% %time%] === PROCESO FINALIZADO ===
echo [%date% %time%] === PROCESO FINALIZADO === >> "%LOG_FILE%"
echo [%date% %time%] ✅ CARGUE COMPLETADO EXITOSAMENTE
echo [%date% %time%] ✅ CARGUE COMPLETADO EXITOSAMENTE >> "%LOG_FILE%"
echo.
echo ============================================================
echo   RESUMEN FINAL
echo ============================================================
echo [%date% %time%] === RESUMEN FINAL === >> "%LOG_FILE%"

if "!USAR_ARCHIVO_LOCAL!"=="1" (
    echo ✅ Archivo: %RUTA_DESTINO% (ARCHIVO LOCAL)
    echo ⚠️  AVISO: Se uso archivo local (unidad de red no disponible)
    echo [%date% %time%] ✅ Archivo: %RUTA_DESTINO% (ARCHIVO LOCAL) >> "%LOG_FILE%"
    echo [%date% %time%] ⚠️  AVISO: Se uso archivo local (unidad de red no disponible) >> "%LOG_FILE%"
) else (
    echo ✅ Archivo: !ARCHIVO_ENCONTRADO!
    echo [%date% %time%] ✅ Archivo: !ARCHIVO_ENCONTRADO! >> "%LOG_FILE%"
)

echo ✅ Destino: %RUTA_DESTINO%
echo ✅ Base de datos: distrijass - CARGUE EXITOSO
echo ============================================================
echo [%date% %time%] ✅ Destino: %RUTA_DESTINO% >> "%LOG_FILE%"
echo [%date% %time%] ✅ Base de datos: distrijass - CARGUE EXITOSO >> "%LOG_FILE%"
echo [%date% %time%] FIN: %date% %time% >> "%LOG_FILE%"

REM ============================================================
REM ENVIO DE REPORTE POR EMAIL (OPCIONAL)
REM ============================================================
echo.
echo [%date% %time%] === FASE 4: ENVIO DE REPORTE ===
echo Intentando enviar reporte por correo...

REM Descomenta las siguientes lineas para habilitar envio de reportes:
REM echo [%date% %time%] Ejecutando send_cargue_report.py... >> "%LOG_FILE%"
REM cd /d "D:\Python\DataZenithBi\adminbi"
REM call .venv\Scripts\activate.bat
REM python send_cargue_report.py --log "%LOG_FILE%" --email "admin@distrijass.com" >> "%LOG_FILE%" 2>&1
REM if errorlevel 1 (
REM     echo [%date% %time%] ⚠️  No se pudo enviar reporte (no es fatal) >> "%LOG_FILE%"
REM ) else (
REM     echo [%date% %time%] ✅ Reporte enviado exitosamente >> "%LOG_FILE%"
REM )

call :log_summary EXITOSO "Cargue completado correctamente"

echo.
echo Log guardado en: %LOG_FILE%
echo.
exit /b 0

:cargue_fallo
echo.
echo [%date% %time%] === PROCESO FINALIZADO CON ERROR ===
echo [%date% %time%] === PROCESO FINALIZADO CON ERROR === >> "%LOG_FILE%"
echo [%date% %time%] ❌ ERROR EN EL CARGUE DESPUES DE !MAX_REINTENTOS! INTENTOS
echo [%date% %time%] ❌ ERROR EN EL CARGUE DESPUES DE !MAX_REINTENTOS! INTENTOS >> "%LOG_FILE%"
echo [%date% %time%] Codigo de error: !PYTHON_RESULT!
echo [%date% %time%] Codigo de error: !PYTHON_RESULT! >> "%LOG_FILE%"

call :log_summary FALLO "Python cargue - Codigo !PYTHON_RESULT!"

echo.
echo Log guardado en: %LOG_FILE%
echo.
exit /b !PYTHON_RESULT!

REM ============================================================
REM FUNCION: Registrar resumen en archivo de resumen rapido
REM ============================================================
:log_summary
setlocal enabledelayedexpansion
set "STATUS=%~1"
set "DETAIL=%~2"

if not exist "%LOG_SUMMARY%" (
    echo. > "%LOG_SUMMARY%"
    echo ============================================================ >> "%LOG_SUMMARY%"
    echo RESUMEN DE CARGUES - DISTRIJASS >> "%LOG_SUMMARY%"
    echo ============================================================ >> "%LOG_SUMMARY%"
    echo. >> "%LOG_SUMMARY%"
)

echo [%date% %time%] Estado: %STATUS% - %DETAIL% >> "%LOG_SUMMARY%"

endlocal
exit /b 0
