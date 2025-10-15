@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

echo ============================================================
echo   DIAGNOSTICO DE CARGUE AUTOMATICO
echo ============================================================
echo.

echo [%date% %time%] === FASE 1: COPIA DE ARCHIVO ===
echo [%date% %time%] SIMULANDO copia exitosa...
echo [%date% %time%] ✅ Archivo copiado exitosamente
echo.

echo [%date% %time%] === FASE 2: DIAGNOSTICO PYTHON ===
echo.

echo [%date% %time%] Cambiando al directorio de trabajo...
cd /d "D:\Python\DataZenithBi\adminbi"
echo Directorio actual: %CD%
echo.

echo [%date% %time%] Verificando archivos necesarios...
if exist "cargue_infoventas_main.py" (
    echo ✅ cargue_infoventas_main.py encontrado
) else (
    echo ❌ cargue_infoventas_main.py NO encontrado
    exit /b 1
)

if exist ".venv\Scripts\python.exe" (
    echo ✅ Python del entorno virtual encontrado
) else (
    echo ❌ Python del entorno virtual NO encontrado
    exit /b 1
)

if exist ".venv\Scripts\activate.bat" (
    echo ✅ Script de activacion encontrado
) else (
    echo ❌ Script de activacion NO encontrado
    exit /b 1
)
echo.

echo [%date% %time%] Activando entorno virtual...
call ".venv\Scripts\activate.bat"
set "ACTIVATE_RESULT=!ERRORLEVEL!"
echo Resultado activacion: !ACTIVATE_RESULT!
echo.

echo [%date% %time%] Verificando Python version...
python --version
set "PYTHON_VERSION_RESULT=!ERRORLEVEL!"
echo Resultado python --version: !PYTHON_VERSION_RESULT!
echo.

echo [%date% %time%] Verificando Python con ruta completa...
".venv\Scripts\python.exe" --version
set "PYTHON_FULL_RESULT=!ERRORLEVEL!"
echo Resultado python ruta completa: !PYTHON_FULL_RESULT!
echo.

echo [%date% %time%] Verificando dependencias criticas...
echo Verificando pandas...
".venv\Scripts\python.exe" -c "import pandas; print('✅ pandas OK')" 2>nul
set "PANDAS_RESULT=!ERRORLEVEL!"
echo Resultado pandas: !PANDAS_RESULT!

echo Verificando openpyxl...
".venv\Scripts\python.exe" -c "import openpyxl; print('✅ openpyxl OK')" 2>nul
set "OPENPYXL_RESULT=!PANDAS_RESULT!"
echo Resultado openpyxl: !OPENPYXL_RESULT!
echo.

echo [%date% %time%] Prueba del script principal (solo help)...
".venv\Scripts\python.exe" cargue_infoventas_main.py --help 2>nul
set "SCRIPT_HELP_RESULT=!ERRORLEVEL!"
echo Resultado script help: !SCRIPT_HELP_RESULT!
echo.

echo [%date% %time%] === RESUMEN DIAGNOSTICO ===
echo Activacion entorno virtual: !ACTIVATE_RESULT!
echo Python version: !PYTHON_VERSION_RESULT!
echo Python ruta completa: !PYTHON_FULL_RESULT!
echo Pandas: !PANDAS_RESULT!
echo OpenPYXL: !OPENPYXL_RESULT!
echo Script help: !SCRIPT_HELP_RESULT!
echo.

if !PANDAS_RESULT! neq 0 (
    echo ❌ PROBLEMA: pandas no disponible
)

if !OPENPYXL_RESULT! neq 0 (
    echo ❌ PROBLEMA: openpyxl no disponible
)

if !SCRIPT_HELP_RESULT! neq 0 (
    echo ❌ PROBLEMA: script principal tiene errores
)

echo [%date% %time%] Diagnostico completado
pause