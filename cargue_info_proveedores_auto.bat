@echo off
REM ============================================================
REM CARGUE AUTOMATICO DE INFO PROVEEDORES
REM ============================================================
REM Script que:
REM 1. Copia el archivo desde la red (Z:\) al directorio local
REM 2. Ejecuta el cargue automatico con Python
REM ============================================================

echo.
echo ============================================================
echo   CARGUE AUTOMATICO DE INFO PROVEEDORES - DISTRIJASS
echo ============================================================
echo.

REM Mostrar fecha y hora de inicio
echo [%date% %time%] Iniciando proceso automatico...
echo.

REM ============================================================
REM PASO 1: VERIFICAR RUTAS Y CREAR DIRECTORIOS
REM ============================================================

echo [%date% %time%] Verificando rutas y unidades de red...

REM Mostrar unidades disponibles
echo.
echo Unidades disponibles:
wmic logicaldisk get size,freespace,caption

echo.
echo Verificando acceso a la unidad Z:\...

REM Verificar si la unidad Z existe
if not exist "Z:\" (
    echo.
    echo ⚠️  ADVERTENCIA: La unidad Z:\ no esta accesible
    echo.
    echo Intentando mapear la unidad Z:\ automaticamente...
    echo Nota: Esto puede requerir credenciales de red
    echo.
    
    REM Intentar mapear la unidad (ajustar la ruta UNC segun corresponda)
    REM net use Z: \\servidor\carpeta /persistent:yes
    
    echo Si el mapeo automatico falla, ejecute manualmente:
    echo   net use Z: \\servidor\ruta\completa /persistent:yes
    echo.
    echo Presione cualquier tecla para continuar o Ctrl+C para cancelar...
    pause > nul
)

REM Verificar que existe el directorio padre
if not exist "Z:\Distrijass\" (
    echo.
    echo ❌ ERROR: No se encuentra el directorio Z:\Distrijass\
    echo.
    echo Opciones:
    echo 1. Verificar que la unidad Z:\ este correctamente mapeada
    echo 2. Usar la ruta UNC completa en lugar de Z:\
    echo 3. Contactar al administrador de red
    echo.
    pause
    exit /b 1
)

REM Verificar que existe el archivo origen
if not exist "Z:\Distrijass\Sistema Info\Información\Impactos\info proveedores.xlsx" (
    echo.
    echo ❌ ERROR: No se encuentra el archivo origen:
    echo    Z:\Distrijass\Sistema Info\Información\Impactos\info proveedores.xlsx
    echo.
    echo Diagnostico:
    dir "Z:\Distrijass\Sistema Info\Información\Impactos\" /b 2>nul
    if %ERRORLEVEL% neq 0 (
        echo    - No se puede acceder al directorio
    ) else (
        echo    - El directorio existe pero el archivo no esta presente
        echo    - Archivos encontrados en el directorio:
        dir "Z:\Distrijass\Sistema Info\Información\Impactos\*.xlsx" /b 2>nul
    )
    echo.
    echo    Verifique que:
    echo    - La unidad Z:\ este conectada y accesible
    echo    - El archivo existe con el nombre exacto
    echo    - Tiene permisos de lectura en la carpeta
    echo    - No hay caracteres especiales en el nombre
    echo.
    pause
    exit /b 1
)

REM Crear directorio destino si no existe
if not exist "D:\Python\DataZenithBi\Info proveedores 2025\" (
    echo [%date% %time%] Creando directorio destino...
    mkdir "D:\Python\DataZenithBi\Info proveedores 2025\"
)

REM ============================================================
REM PASO 2: COPIAR ARCHIVO DESDE LA RED
REM ============================================================

echo [%date% %time%] Iniciando copia del archivo...
echo.

REM Definir rutas origen y destino
set "ARCHIVO_ORIGEN=Z:\Distrijass\Sistema Info\Información\Impactos\info proveedores.xlsx"
set "ARCHIVO_DESTINO=D:\Python\DataZenithBi\Info proveedores 2025\Info proveedores.xlsx"

REM Ruta UNC alternativa (ajustar segun corresponda)
REM set "ARCHIVO_ORIGEN_UNC=\\servidor\carpeta\Distrijass\Sistema Info\Información\Impactos\info proveedores.xlsx"

echo Origen:  %ARCHIVO_ORIGEN%
echo Destino: %ARCHIVO_DESTINO%
echo.

REM Intentar copia con la unidad mapeada
copy /Y "%ARCHIVO_ORIGEN%" "%ARCHIVO_DESTINO%" 2>nul

REM Si falla con Z:, intentar con ruta UNC (descomente y ajuste la linea siguiente)
if %ERRORLEVEL% neq 0 (
    echo.
    echo ⚠️  La copia con unidad Z:\ fallo, intentando metodos alternativos...
    echo.
    
    REM Opcion 1: Intentar mapear temporalmente
    echo Intentando mapear temporalmente la unidad...
    net use Z: /delete /y >nul 2>&1
    REM net use Z: \\servidor\carpeta >nul 2>&1
    
    REM Opcion 2: Mostrar archivos similares para ayuda
    echo Buscando archivos similares en la carpeta...
    dir "Z:\Distrijass\Sistema Info\Información\Impactos\*proveedor*" /b 2>nul
    dir "Z:\Distrijass\Sistema Info\Información\Impactos\*info*" /b 2>nul
    
    echo.
    echo Para resolver este problema:
    echo 1. Abra el Explorador de Windows
    echo 2. Navegue a Z:\Distrijass\Sistema Info\Información\Impactos\
    echo 3. Verifique el nombre exacto del archivo
    echo 4. Copie manualmente el archivo a: %ARCHIVO_DESTINO%
    echo 5. Presione cualquier tecla para continuar con el cargue
    echo.
    pause
    
    REM Verificar si el usuario copio manualmente
    if not exist "%ARCHIVO_DESTINO%" (
        echo ❌ ERROR: El archivo aun no esta disponible en el destino
        exit /b 1
    ) else (
        echo ✅ Archivo encontrado en destino, continuando...
    )
) else (
    echo [%date% %time%] ✅ Archivo copiado exitosamente
)
echo.

REM ============================================================
REM PASO 3: ACTIVAR ENTORNO VIRTUAL Y EJECUTAR CARGUE
REM ============================================================

echo [%date% %time%] Cambiando al directorio de trabajo...
cd /d "D:\Python\DataZenithBi\adminbi"

REM Verificar que estamos en el directorio correcto
if not exist "cargue_infoventas_main.py" (
    echo.
    echo ❌ ERROR: No se encuentra el script cargue_infoventas_main.py
    echo    Directorio actual: %CD%
    echo.
    pause
    exit /b 1
)

echo [%date% %time%] Activando entorno virtual Python...

REM Activar entorno virtual si existe
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    echo [%date% %time%] ✅ Entorno virtual activado
) else (
    echo [%date% %time%] ⚠️  No se encontro entorno virtual, usando Python del sistema
)

echo.
echo [%date% %time%] Ejecutando cargue de Info Proveedores...
echo.

REM Ejecutar el script de cargue
python cargue_infoventas_main.py --base distrijass --archivo "D:\Python\DataZenithBi\Info proveedores 2025\Info proveedores.xlsx"

REM Capturar codigo de salida
set CARGUE_RESULT=%ERRORLEVEL%

echo.
if %CARGUE_RESULT% equ 0 (
    echo [%date% %time%] ✅ PROCESO COMPLETADO EXITOSAMENTE
    echo.
    echo ============================================================
    echo   RESUMEN DEL PROCESO
    echo ============================================================
    echo ✅ Archivo copiado desde la red
    echo ✅ Cargue de datos ejecutado correctamente
    echo ✅ Proceso finalizado sin errores
    echo ============================================================
) else (
    echo [%date% %time%] ❌ ERROR EN EL CARGUE DE DATOS
    echo    Codigo de error: %CARGUE_RESULT%
    echo.
    echo ============================================================
    echo   PROCESO COMPLETADO CON ERRORES
    echo ============================================================
    echo ✅ Archivo copiado desde la red
    echo ❌ Error en el cargue de datos (codigo: %CARGUE_RESULT%)
    echo ============================================================
)

echo.
echo Presione cualquier tecla para salir...
pause > nul

exit /b %CARGUE_RESULT%