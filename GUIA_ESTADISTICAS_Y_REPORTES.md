# 📊 GUÍA COMPLETA: ESTADÍSTICAS DETALLADAS Y REPORTE POR EMAIL

**Última actualización:** 20 de octubre 2025  
**Versión:** 2.2  
**Estado:** ✅ Completamente implementado

---

## 🎯 DESCRIPCIÓN GENERAL

Se han implementado mejoras completas para **capturar y reportar estadísticas detalladas** del cargue de información de ventas, incluyendo:

✅ Registro detallado de registros en _fact y _dev  
✅ Captura del rango de fechas procesadas  
✅ Estadísticas completas en archivos de log  
✅ Envío automático de reportes por correo electrónico  
✅ Reportes HTML con formato profesional  

---

## 📝 ¿QUÉ INFORMACIÓN AHORA CAPTURA EL LOG?

### 1️⃣ RANGO DE FECHAS PROCESADAS

```log
📅 RANGO DE FECHAS PROCESADAS: 2025-10-01 → 2025-10-31
```

El script detecta automáticamente:
- **Desde nombre del archivo:** Si el archivo se llama `info_2025_10.xlsx`, detecta octubre 2025
- **Desde fecha actual:** Si no puede detectar, usa el mes actual completo

**Ubicación en log:** Línea 4-5 del cargue

### 2️⃣ REGISTROS PROCESADOS

```log
📊 Registros procesados: 316,815
📊 Registros insertados: 316,815
📊 Registros actualizados: 0
📊 Registros preservados: 0
```

**Ubicación en log:** Sección "RESUMEN DE INSERCIÓN"

### 3️⃣ DISTRIBUCIÓN POR TABLA CLASIFICADA

**NUEVO - Información detallada:**

```log
📦 DISTRIBUCIÓN POR TABLA CLASIFICADA:
   • Registros en _fact: 12,626,910
   • Registros en _dev: 513,773
   • Total clasificado: 13,140,683
   • Registros en staging (post-limpieza): 0

📋 DETALLES POR TABLA:
   • infoventas_2023_fact: 3,123,456 registros [_fact]
   • infoventas_2024_fact: 4,521,789 registros [_fact]
   • infoventas_2025_fact: 2,789,012 registros [_fact]
   • infoventas_2026_fact: 2,192,653 registros [_fact]
   • infoventas_2023_dev: 87,654 registros [_dev]
   • infoventas_2024_dev: 156,789 registros [_dev]
   • infoventas_2025_dev: 168,901 registros [_dev]
   • infoventas_2026_dev: 100,429 registros [_dev]
```

**Ubicación en log:** Sección "ESTADÍSTICAS FINALES DE CARGUE"

---

## 📍 DÓNDE ENCONTRAR ESTA INFORMACIÓN

### 📄 En el Archivo de Log

**Ubicación:** `D:\Logs\DataZenithBI\cargue_distrijass.log`

**Cómo visualizar:**
```powershell
# En PowerShell - Ver últimas líneas con estadísticas
Get-Content "D:\Logs\DataZenithBI\cargue_distrijass.log" -Tail 50

# Ver sección de estadísticas finales
Select-String "ESTADÍSTICAS FINALES" "D:\Logs\DataZenithBI\cargue_distrijass.log" -Context 20
```

### 💻 En la Consola

Durante la ejecución verás:

```
🔧 FASE 5: Capturando estadísticas finales...
📊 === ESTADÍSTICAS FINALES DE CARGUE ===
================================================================================
📅 Período procesado: 2025-10-01 → 2025-10-31
⏱️  Duración total: 433.85 segundos

📝 RESUMEN DE INSERCIÓN:
   • Registros procesados: 316,815
   • Registros insertados: 316,815
   ...
```

---

## 📧 ENVÍO DE REPORTES POR EMAIL

### 🛠️ CONFIGURACIÓN INICIAL

#### 1️⃣ Configurar credenciales de Gmail

**Opción A: Usar contraseña de aplicación (RECOMENDADO)**

```
1. Ir a: https://myaccount.google.com/apppasswords
2. Seleccionar "Mail" y "Windows Computer"
3. Google genera una contraseña de 16 caracteres
4. Copiar esa contraseña (sin espacios)
```

#### 2️⃣ Editar `config_email.json`

```bash
# Ubicación: D:\Python\DataZenithBi\adminbi\config_email.json
```

**Contenido:**

```json
{
  "smtp": {
    "servidor": "smtp.gmail.com",
    "puerto": 587
  },
  "credenciales": {
    "usuario": "tu_email@gmail.com",
    "contrasena": "xyzw abcd efgh ijkl"
  },
  "destinatarios": {
    "reportes_exito": [
      "admin@distrijass.com",
      "bi@distrijass.com"
    ],
    "reportes_error": [
      "admin@distrijass.com",
      "soporte@distrijass.com"
    ]
  }
}
```

### 🚀 USAR EL REPORTE

#### **Opción 1: Enviar manualmente después de cargue**

```bash
cd D:\Python\DataZenithBi\adminbi

# Activar entorno virtual
.venv\Scripts\activate.bat

# Enviar reporte
python send_cargue_report.py ^
  --log "D:\Logs\DataZenithBI\cargue_distrijass.log" ^
  --email "admin@distrijass.com"
```

**Resultado:**
```
📧 Enviando reporte a: admin@distrijass.com
📄 Log: D:\Logs\DataZenithBI\cargue_distrijass.log
📖 Parseando archivo de log...
   ✓ Registros procesados: 316,815
   ✓ Rango: 2025-10-01 → 2025-10-31
   ✓ Status: EXITOSO
📨 Conectando al servidor de correo...
✅ Reporte enviado exitosamente a 1 destinatario(s)
```

#### **Opción 2: Enviar automáticamente desde batch script**

Editar `cargue_final_automatico.bat` y descomenta estas líneas (alrededor de la línea 265):

```batch
REM Descomenta las siguientes lineas para habilitar envio de reportes:
echo [%date% %time%] Ejecutando send_cargue_report.py... >> "%LOG_FILE%"
cd /d "D:\Python\DataZenithBi\adminbi"
call .venv\Scripts\activate.bat
python send_cargue_report.py --log "%LOG_FILE%" --email "admin@distrijass.com" >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] ⚠️  No se pudo enviar reporte (no es fatal) >> "%LOG_FILE%"
) else (
    echo [%date% %time%] ✅ Reporte enviado exitosamente >> "%LOG_FILE%"
)
```

---

## 📋 CONTENIDO DEL REPORTE POR EMAIL

El reporte HTML incluye:

### 📊 Sección 1: Resumen Rápido
- ✅ Status (EXITOSO / ERROR)
- 📊 Registros procesados totales
- 📦 Desglose _fact / _dev
- ⏱️ Duración total
- 📅 Rango de fechas

### 📝 Sección 2: Detalles de Operaciones
- ✅ Registros insertados
- 🔄 Registros actualizados
- 📌 Registros preservados
- 🧹 Registros en staging post-limpieza

### 📦 Sección 3: Distribución por Tabla
Tabla detallada con:
- Nombre de tabla (_fact o _dev)
- Tipo de registro
- Cantidad de registros

---

## 🔍 EJEMPLOS DE USO

### Ejemplo 1: Verificar estadísticas del último cargue

```powershell
# PowerShell
$log = "D:\Logs\DataZenithBI\cargue_distrijass.log"
Select-String "ESTADÍSTICAS FINALES" -Path $log -Context 50 | ForEach-Object { $_.Line }
```

**Salida:**
```
📊 === ESTADÍSTICAS FINALES DE CARGUE ===
================================================================================
📅 Período procesado: 2025-10-01 → 2025-10-31
...
```

### Ejemplo 2: Obtener solo cifras principales

```powershell
# Extraer registros en _fact y _dev
Select-String "Registros en _fact|Registros en _dev" -Path $log
```

**Salida:**
```
   • Registros en _fact: 12,626,910
   • Registros en _dev: 513,773
```

### Ejemplo 3: Enviar reporte personalizado

```bash
python send_cargue_report.py ^
  --log "D:\Logs\DataZenithBI\cargue_distrijass.log" ^
  --email "director@distrijass.com" ^
  --usuario "reportes@gmail.com" ^
  --contrasena "xyzw abcd efgh ijkl" ^
  --asunto "[URGENTE] Reporte de Cargue - Distrijass"
```

---

## 🎯 FLUJO COMPLETO INTEGRADO

```
1. CARGUE INICIA
   ├─ Detecta rango de fechas
   ├─ Procesa archivo Excel (316.8K registros)
   └─ Inserta en tabla staging

2. CLASIFICACIÓN AUTOMÁTICA
   ├─ Separa registros en _fact y _dev
   ├─ Registra: 12.6M en _fact, 513K en _dev
   └─ Limpia tabla staging (0 registros)

3. CAPTURA DE ESTADÍSTICAS
   ├─ Lee tablas clasificadas desde BD
   ├─ Obtiene conteo por tabla
   ├─ Calcula totales
   └─ Registra TODO en log

4. REPORTE DISPONIBLE EN:
   ├─ D:\Logs\DataZenithBI\cargue_distrijass.log (detallado)
   ├─ D:\Logs\DataZenithBI\cargue_summary_latest.log (resumen)
   └─ Correo electrónico (HTML profesional, OPCIONAL)
```

---

## ⚙️ CONFIGURACIÓN AVANZADA

### Personalizar Destinatarios

En `config_email.json`:

```json
"destinatarios": {
  "reportes_exito": ["admin@distrijass.com", "bi@distrijass.com"],
  "reportes_error": ["admin@distrijass.com", "soporte@distrijass.com"],
  "copia_siempre": ["logs@distrijass.com"]
}
```

### Usar servidor SMTP diferente

```bash
python send_cargue_report.py ^
  --log "..." ^
  --email "..." ^
  --smtp-server "smtp.tuempresa.com" ^
  --smtp-port 587
```

### Procesamiento por lote (múltiples emails)

```bash
# Crear archivo direcciones.txt
echo admin@distrijass.com >> direcciones.txt
echo bi@distrijass.com >> direcciones.txt

# Procesar
for /f %%i in (direcciones.txt) do (
  python send_cargue_report.py --log "..." --email %%i
)
```

---

## 🚨 TROUBLESHOOTING

### ❌ "Credenciales SMTP no configuradas"

**Solución:**
1. Verificar que `config_email.json` esté correctamente formateado (JSON válido)
2. O pasar credenciales por línea de comandos:
   ```bash
   python send_cargue_report.py --usuario "tu@gmail.com" --contrasena "xxxxx"
   ```

### ❌ "Error conectando a SMTP"

**Solución:**
1. Verificar contraseña de aplicación de Gmail es correcta
2. Verificar que el correo tenga habilitado "Acceso a aplicaciones menos seguras"
3. Probar con otra red (posible bloqueo de firewall)

### ❌ "Archivo de log no encontrado"

**Solución:**
1. Verificar que el cargue haya ejecutado completamente
2. Confirmar ruta: `D:\Logs\DataZenithBI\cargue_distrijass.log`
3. Si no existe, ejecutar primero el batch: `cargue_final_automatico.bat`

---

## 📊 ESTADÍSTICAS EN TASK SCHEDULER

Para habilitar envío automático desde Task Scheduler:

### 1️⃣ Crear tarea programada

```
Nombre: Cargue InfoVentas + Reporte
Programa: D:\Python\DataZenithBi\adminbi\cargue_final_automatico.bat
Carpeta trabajo: D:\Python\DataZenithBi\adminbi\
```

### 2️⃣ Descomentar envío en batch (línea ~265)

### 3️⃣ Probar manualmente

```bash
D:\Python\DataZenithBi\adminbi\cargue_final_automatico.bat
```

Si todo funciona, configurar en Task Scheduler.

---

## 📚 RESUMEN DE ARCHIVOS

| Archivo | Propósito |
|---------|-----------|
| `cargue_infoventas_main.py` | Script principal con captura de estadísticas |
| `scripts/email_reporter.py` | Módulo de reportes por email |
| `send_cargue_report.py` | Script de utilidad para enviar reportes |
| `config_email.json` | Configuración de credenciales y destinatarios |
| `cargue_final_automatico.bat` | Batch con hook para envío de reportes |
| `D:\Logs\DataZenithBI\cargue_distrijass.log` | Log detallado con todas las estadísticas |

---

## ✅ VALIDACIÓN

Ejecuta el siguiente comando para verificar que todo está configurado:

```bash
cd D:\Python\DataZenithBi\adminbi
python -c "from scripts.email_reporter import EmailReporter; print('✅ Módulo de reportes cargado correctamente')"
```

**Resultado esperado:**
```
✅ Módulo de reportes cargado correctamente
```

---

**🎉 ¡Sistema completamente configurado para reportes detallados!**

*Última actualización: 20 de octubre 2025*
