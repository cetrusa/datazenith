# 🔍 EJEMPLO VISUAL - DÓNDE ESTÁ CADA DATO EN EL LOG

**Documento técnico - 20 de octubre 2025**

---

## 📄 ESTRUCTURA COMPLETA DEL LOG

```
D:\Logs\DataZenithBI\cargue_distrijass.log
```

### LÍNEAS 1-50: INICIO Y CONFIGURACIÓN

```log
2025-10-20 04:02:22,724 🚀🚀🚀 INICIO FUNCIÓN run_cargue - DEBUG LOG 🚀🚀🚀
2025-10-20 04:02:22,724 🚀 Iniciando cargue del archivo: D:\Python\DataZenithBi\Info proveedores 2025\Info proveedores.xlsx
2025-10-20 04:02:22,724 ⚠️ No se pudieron detectar fechas desde el nombre. Se usará el mes actual.
2025-10-20 04:02:22,724 📅 Rango de fechas detectado: 2025-10-01 → 2025-10-31  ← AQUÍ ESTÁ EL RANGO
2025-10-20 04:02:22,724 🔧 Fase 1: Creando instancia del cargador...
2025-10-20 04:02:22,724 Creando nueva conexión para cetrusa@dbmariam04...
2025-10-20 04:02:24,836 Reutilizando conexión existente para cetrusa@dbmariam04...
...
```

### LÍNEAS 51-150: FASE 1 (CARGA)

```log
2025-10-20 04:02:30,866 🔧 Fase 2: Ejecutando proceso de cargue...
2025-10-20 04:02:30,866 ✅ Cargador creado exitosamente
2025-10-20 04:02:30,866 🔧 Fase 2: Ejecutando proceso de cargue...
2025-10-20 04:05:04,148 ✅ Cargue completado correctamente.

📊 Registros procesados: 316815
📊 Registros insertados: 316815  ← AQUÍ: CUÁNTOS INSERTADOS
📊 Registros actualizados: 0     ← AQUÍ: CUÁNTOS ACTUALIZADOS  
📊 Registros preservados: 0      ← AQUÍ: CUÁNTOS PRESERVADOS

📅 RANGO DE FECHAS PROCESADAS: 2025-10-01 → 2025-10-31  ← AQUÍ: RANGO CLARO
```

### LÍNEAS 151-200: FASE 2 (MANTENIMIENTO)

```log
2025-10-20 04:05:04,148 🔧 Fase 3: Iniciando mantenimiento post-cargue...
2025-10-20 04:05:04,148 🧹 === INICIANDO MANTENIMIENTO POST-CARGUE ===
2025-10-20 04:05:04,513 📊 Registros en infoventas ANTES del mantenimiento: 316815

Método 1: Ejecutando con raw_connection y reintentos...
   ↳ Intento 1/3 de ejecución del procedimiento...
   
2025-10-20 04:05:54,782 📋 Resultados parciales del procedimiento: (('Vista vw_infoventas reconstruida correctamente',),)
2025-10-20 04:07:54,791 ⚠️ Error de base de datos (código 0): (0, '')
2025-10-20 04:07:55,629 📊 Registros en infoventas DESPUÉS del mantenimiento: 0

✅ Mantenimiento completado. Tabla infoventas limpia.
🎉 === MANTENIMIENTO COMPLETADO EXITOSAMENTE ===
```

### LÍNEAS 201-300: FASE 3 (DIAGNÓSTICO Y ESTADÍSTICAS)

```log
2025-10-20 04:07:55,763 🔧 Fase 4: Ejecutando diagnóstico de la vista...

🔍 DIAGNÓSTICO DE TABLA CLASIFICADA:
 
   ✅ Vista vw_infoventas:
   
   📊 Tablas clasificadas incluidas en vista:
      ├─ Tabla: infoventas_2023_fact
      ├─ Tabla: infoventas_2024_fact
      ├─ Tabla: infoventas_2025_fact
      ├─ Tabla: infoventas_2026_fact
      ├─ Tabla: infoventas_2023_dev
      ├─ Tabla: infoventas_2024_dev
      ├─ Tabla: infoventas_2025_dev
      └─ Tabla: infoventas_2026_dev
      
   📊 Conteo de registros por tabla:
      • infoventas_2023_fact: 3,123,456
      • infoventas_2024_fact: 4,521,789
      • infoventas_2025_fact: 2,789,012
      • infoventas_2026_fact: 2,192,653
      • infoventas_2023_dev: 87,654
      • infoventas_2024_dev: 156,789
      • infoventas_2025_dev: 168,901
      • infoventas_2026_dev: 100,429
      
   📊 Total _fact: 12,626,910 registros  ← AQUÍ: TOTAL _FACT
   📊 Total _dev: 513,773 registros      ← AQUÍ: TOTAL _DEV
   📊 Total en vista: 13,140,683 registros (debe = fact + dev)
   
   ✅ Consistencia verificada.
```

### LÍNEAS 301-350: ESTADÍSTICAS FINALES ⭐

```log
2025-10-20 04:09:36,575 🔧 Fase 5: Capturando estadísticas finales...

================================================================================
📊 === ESTADÍSTICAS FINALES DE CARGUE ===
================================================================================

📅 Período procesado: 2025-10-01 → 2025-10-31  ← FECHA INICIO/FIN

⏱️  Duración total: 433.85 segundos

📝 RESUMEN DE INSERCIÓN:
   • Registros procesados: 316,815      ← CUÁNTOS PROCESADOS
   • Registros insertados: 316,815      ← CUÁNTOS INSERTADOS
   • Registros actualizados: 0          ← CUÁNTOS ACTUALIZADOS
   • Registros preservados: 0           ← CUÁNTOS PRESERVADOS

📦 DISTRIBUCIÓN POR TABLA CLASIFICADA:
   • Registros en _fact: 12,626,910     ← TOTAL EN _FACT
   • Registros en _dev: 513,773          ← TOTAL EN _DEV
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

================================================================================
```

### LÍNEAS 351-360: CIERRE

```log
2025-10-20 04:09:36,575 🎉 PROCESO COMPLETADO EXITOSAMENTE en 433.85 segundos
2025-10-20 04:09:36,576 🔒 Engine de base de datos cerrado correctamente.
```

---

## 🎯 MAPA RÁPIDO: ¿DÓNDE ENCONTRAR CADA DATO?

### 1️⃣ "¿Cuántos registros INSERTADOS?"

**Respuesta:** Línea ~320

```log
   • Registros insertados: 316,815
```

**Búsqueda:** `Select-String "Registros insertados" -Path "D:\Logs\DataZenithBI\cargue_distrijass.log"`

---

### 2️⃣ "¿Cuántos registros ACTUALIZADOS?"

**Respuesta:** Línea ~322

```log
   • Registros actualizados: 0
```

**Búsqueda:** `Select-String "Registros actualizados" -Path "D:\Logs\DataZenithBI\cargue_distrijass.log"`

---

### 3️⃣ "¿Rango de fechas?"

**Respuesta:** Línea ~4 (y repetido en línea ~312)

```log
📅 Período procesado: 2025-10-01 → 2025-10-31
```

**Búsqueda:** `Select-String "Período procesado" -Path "D:\Logs\DataZenithBI\cargue_distrijass.log"`

---

### 4️⃣ "¿Cuántos en _fact?"

**Respuesta:** Línea ~328

```log
   • Registros en _fact: 12,626,910
```

**Búsqueda:** `Select-String "Registros en _fact" -Path "D:\Logs\DataZenithBI\cargue_distrijass.log"`

---

### 5️⃣ "¿Cuántos en _dev?"

**Respuesta:** Línea ~329

```log
   • Registros en _dev: 513,773
```

**Búsqueda:** `Select-String "Registros en _dev" -Path "D:\Logs\DataZenithBI\cargue_distrijass.log"`

---

### 6️⃣ "¿Detalles por tabla?"

**Respuesta:** Líneas ~333-340

```log
📋 DETALLES POR TABLA:
   • infoventas_2023_fact: 3,123,456 registros [_fact]
   • infoventas_2024_fact: 4,521,789 registros [_fact]
   ...
   • infoventas_2023_dev: 87,654 registros [_dev]
   ...
```

**Búsqueda:** `Select-String "DETALLES POR TABLA" -Path "D:\Logs\DataZenithBI\cargue_distrijass.log" -Context 15`

---

## 📊 TABLA RESUMEN - UBICACIONES

| Dato | Sección | Línea Aproximada | Búsqueda |
|------|---------|------------------|----------|
| **Rango inicial** | Inicio | 4 | `Rango de fechas detectado` |
| **Insertados** | Estadísticas | 320 | `Registros insertados:` |
| **Actualizados** | Estadísticas | 322 | `Registros actualizados:` |
| **Preservados** | Estadísticas | 324 | `Registros preservados:` |
| **Período** | Estadísticas | 312 | `Período procesado:` |
| **_fact** | Estadísticas | 328 | `Registros en _fact:` |
| **_dev** | Estadísticas | 329 | `Registros en _dev:` |
| **Detalles** | Estadísticas | 333-340 | `DETALLES POR TABLA:` |

---

## 💡 EJEMPLO PRÁCTICO: EXTRAER TODO CON POWERSHELL

### Script para extraer todas las estadísticas

```powershell
# Guardar en: D:\extract_stats.ps1

$logFile = "D:\Logs\DataZenithBI\cargue_distrijass.log"

Write-Host "="*80
Write-Host "EXTRAYENDO ESTADÍSTICAS DEL CARGUE"
Write-Host "="*80
Write-Host ""

Write-Host "📅 RANGO DE FECHAS:"
Select-String "Período procesado" $logFile | ForEach-Object { $_.Line }
Write-Host ""

Write-Host "📝 INSERCIÓN:"
Select-String "Registros insertados:|Registros actualizados:|Registros preservados:" $logFile | ForEach-Object { $_.Line }
Write-Host ""

Write-Host "📦 DISTRIBUCIÓN:"
Select-String "Registros en _fact:|Registros en _dev:" $logFile | ForEach-Object { $_.Line }
Write-Host ""

Write-Host "📋 DETALLES POR TABLA:"
Select-String "infoventas_.*_(fact|dev):" $logFile | ForEach-Object { $_.Line }
Write-Host ""

Write-Host "⏱️  DURACIÓN:"
Select-String "PROCESO COMPLETADO" $logFile | ForEach-Object { $_.Line }
Write-Host ""

Write-Host "="*80
```

### Ejecución

```powershell
# En PowerShell
cd D:\
.\extract_stats.ps1
```

### Salida esperada

```
================================================================================
EXTRAYENDO ESTADÍSTICAS DEL CARGUE
================================================================================

📅 RANGO DE FECHAS:
   📅 Período procesado: 2025-10-01 → 2025-10-31

📝 INSERCIÓN:
   • Registros insertados: 316,815
   • Registros actualizados: 0
   • Registros preservados: 0

📦 DISTRIBUCIÓN:
   • Registros en _fact: 12,626,910
   • Registros en _dev: 513,773

📋 DETALLES POR TABLA:
   • infoventas_2023_fact: 3,123,456 registros [_fact]
   • infoventas_2024_fact: 4,521,789 registros [_fact]
   ...

⏱️  DURACIÓN:
   🎉 PROCESO COMPLETADO EXITOSAMENTE en 433.85 segundos

================================================================================
```

---

## 🔧 AUTOMATIZAR BÚSQUEDA CON ALIAS

```powershell
# Agregar a tu perfil de PowerShell ($PROFILE):

function Get-CargueStats {
    param(
        [string]$LogPath = "D:\Logs\DataZenithBI\cargue_distrijass.log"
    )
    
    if (-not (Test-Path $LogPath)) {
        Write-Host "❌ Log no encontrado: $LogPath"
        return
    }
    
    Write-Host "📊 === ESTADÍSTICAS DEL CARGUE ===" -ForegroundColor Cyan
    Write-Host ""
    
    Select-String "Período procesado|Registros insertados|Registros en _fact|Registros en _dev|PROCESO COMPLETADO" `
        -Path $LogPath | ForEach-Object { 
        Write-Host $_.Line -ForegroundColor Yellow 
    }
}

# Uso:
# Get-CargueStats
```

---

## 📮 CONTENIDO DEL EMAIL (SI LO HABILITAS)

Recibirás un email HTML con las mismas secciones:

```html
<!-- Email automatizado incluye: -->

✅ Status: EXITOSO

📅 Rango: 2025-10-01 → 2025-10-31

📝 Inserción:
  • Insertados: 316,815
  • Actualizados: 0
  • Preservados: 0

📦 Distribución:
  • _fact: 12,626,910
  • _dev: 513,773

📋 Tabla detallada de detalles

⏱️ Duración: 433.85 segundos
```

---

## ✅ CHECKLIST DE VERIFICACIÓN

Después de ejecutar cargue, verifica:

```
☑ ¿Existe el archivo de log?
  → D:\Logs\DataZenithBI\cargue_distrijass.log
  
☑ ¿Contiene "ESTADÍSTICAS FINALES"?
  → Select-String "ESTADÍSTICAS FINALES" -Path "..."
  
☑ ¿Aparecen los datos que buscas?
  → Período procesado
  → Registros insertados
  → Registros en _fact
  → Registros en _dev
  → Detalles por tabla
  
☑ ¿Está todo con números?
  → No dice "N/A" o vacío
  → Todos los campos tienen cifras
  
☑ ✅ ¡Listo - Sistema 100% operacional!
```

---

**Documento técnico de referencia - Guarda para consultas**

*v2.2 - 20 de octubre 2025*
