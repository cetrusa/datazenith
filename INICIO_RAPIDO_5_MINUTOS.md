# 🚀 INICIO RÁPIDO - 5 MINUTOS

**Para los apurados - Lo que necesitas saber AHORA**

---

## ❓ TUS PREGUNTAS RESPONDIDAS EN 30 SEGUNDOS

### P1: ¿Cuántos se actualizaron?
**A:** En el log: `D:\Logs\DataZenithBI\cargue_distrijass.log`
```log
Registros insertados: 316,815
Registros actualizados: 0
```

### P2: ¿Rango de fechas?
**A:** En el mismo log:
```log
Período procesado: 2025-10-01 → 2025-10-31
```

### P3: ¿Cuántos en _fact y _dev?
**A:** En el mismo log:
```log
Registros en _fact: 12,626,910
Registros en _dev: 513,773
```

### P4: ¿Recibir por email?
**A:** ✅ SÍ - Configura en 5 minutos

---

## 🎯 DÓNDE ESTÁ TODO

```
Log: D:\Logs\DataZenithBI\cargue_distrijass.log
├─ Rango de fechas: Sección "ESTADÍSTICAS FINALES"
├─ Insertados: Sección "RESUMEN DE INSERCIÓN"
├─ _fact y _dev: Sección "DISTRIBUCIÓN POR TABLA"
└─ Detalles: Sección "DETALLES POR TABLA"
```

---

## 📧 HABILITAR EMAIL EN 3 PASOS (5 minutos)

### Paso 1: Gmail
```
1. Ir: https://myaccount.google.com/apppasswords
2. Seleccionar: Mail + Windows Computer
3. Copiar: Tu contraseña de aplicación
```

### Paso 2: config_email.json
```bash
# Editar: D:\Python\DataZenithBi\adminbi\config_email.json
{
  "credenciales": {
    "usuario": "tu_email@gmail.com",
    "contrasena": "XYZW ABCD EFGH IJKL"
  }
}
```

### Paso 3: Batch
```bash
# Editar: D:\Python\DataZenithBi\adminbi\cargue_final_automatico.bat
# Líneas 266-273: Descomenta estas líneas
python send_cargue_report.py --log "%LOG_FILE%" --email "..."
```

### Listo ✅
Próximo cargue recibirás email automático

---

## 📊 EJEMPLO DE DATOS

Después de cargue verás en el log:

```
REGISTROS: 316,815 procesados
_FACT: 12,626,910
_DEV: 513,773
FECHAS: 2025-10-01 → 2025-10-31
DURACIÓN: 433.85 segundos
```

---

## 🔍 BÚSQUEDA RÁPIDA

En PowerShell:
```powershell
# Ver todas las estadísticas
Select-String "ESTADÍSTICAS FINALES" -Path "D:\Logs\DataZenithBI\cargue_distrijass.log" -Context 30

# Ver solo _fact y _dev
Select-String "Registros en _fact|Registros en _dev" -Path "D:\Logs\DataZenithBI\cargue_distrijass.log"
```

---

## 📚 DOCUMENTACIÓN

Necesitas más info? Lee estos en orden:

1. **REFERENCIA_RAPIDA_ESTADISTICAS.md** (3 min)
2. **RESUMEN_EJECUTIVO_FINAL.md** (5 min)
3. **GUIA_ESTADISTICAS_Y_REPORTES.md** (15 min)

---

## ✅ CHECKLIST MÍNIMO

```
☑ Ejecutar: .\cargue_final_automatico.bat
☑ Esperar: ~8.5 minutos
☑ Abrir: D:\Logs\DataZenithBI\cargue_distrijass.log
☑ Buscar: "ESTADÍSTICAS FINALES"
☑ Listo ✅ - Todos los datos están ahí
```

---

## 📮 RECIBIR POR EMAIL

```bash
# Manual (cuando necesites):
python send_cargue_report.py \
  --log "D:\Logs\DataZenithBI\cargue_distrijass.log" \
  --email "admin@distrijass.com"

# Automático (después de cada cargue):
# Configurar según "Habilitar EMAIL en 3 PASOS" arriba
```

---

## 🚨 PROBLEMA?

| Problema | Solución |
|----------|----------|
| No veo estadísticas | Ejecutar cargue completo (~8.5 min) |
| Email no llega | Verificar credenciales en config_email.json |
| No encuentra log | Log está en: D:\Logs\DataZenithBI\cargue_distrijass.log |

---

## 💡 PRO TIP

Copia este comando PowerShell:

```powershell
# Guardar como: C:\get_stats.ps1
$log = "D:\Logs\DataZenithBI\cargue_distrijass.log"
Select-String "Período procesado|Registros insertados|Registros en _fact|Registros en _dev" -Path $log | ForEach-Object { $_.Line }
```

Luego ejecuta:
```powershell
C:\get_stats.ps1
```

Y obtienes todos los datos en segundos.

---

**¡Ya estás listo! 🎉**

*Para más detalles, ver: REFERENCIA_RAPIDA_ESTADISTICAS.md*
