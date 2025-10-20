# 🎯 REFERENCIA RÁPIDA - Corrección Full Maintenance v2.1

## 📌 TL;DR (Too Long; Didn't Read)

### Problema 1: Vista duplicada
**Problema:** `sp_infoventas_rebuild_view()` incluía tablas anuales completas → duplicación de datos
**Solución:** Filtrar SOLO `_fact` y `_dev` en el cursor

### Problema 2: Tabla anual no se limpiaba
**Problema:** Después de migrar a `_fact` y `_dev`, la tabla anual (`infoventas_2025`) NO se limpiaba
**Solución:** Agregar `DELETE FROM infoventas_2025` después de clasificación

**Resultado:** Vista consistente, sin duplicación, tabla anual limpia, con validación automática

---

## 📂 ARCHIVOS CLAVE

| Archivo | Propósito |
|---------|-----------|
| `scripts/sql/sp_infoventas_maintenance_fixed.sql` | ✅ SQL para aplicar en BD |
| `GUIA_RAPIDA_APLICAR_CAMBIOS.md` | ✅ Instrucciones paso a paso |
| `cargue_infoventas_main.py` | ✅ Ahora incluye diagnóstico automático |

---

## 🚀 APLICACIÓN EN 3 PASOS

### 1️⃣ Ejecutar SQL
```bash
Get-Content scripts/sql/sp_infoventas_maintenance_fixed.sql | mysql -h HOST -u USER -pPASS DB
```

### 2️⃣ Verificar
```sql
SHOW PROCEDURE STATUS WHERE Name = 'sp_infoventas_rebuild_view';
```

### 3️⃣ Probar
```bash
python cargue_infoventas_main.py --base bi_distrijass --archivo "archivo.xlsx"
```

---

## ✅ VALIDACIÓN

Si ves esto al final: **¡CORRECCIÓN EXITOSA!**
```
✅ La vista NO incluye tablas anuales completas.
✅ La vista incluye correctamente tablas _fact y _dev.
✅ Consistencia verificada.
```

---

## 🔍 EL CAMBIO CRÍTICO

**Antes:**
```sql
WHERE table_name LIKE 'infoventas\_%'
```
Resultado: `infoventas_2024`, `infoventas_2024_fact`, `infoventas_2025`, ...

**Ahora:**
```sql
WHERE table_name LIKE 'infoventas\_%' 
  AND (table_name LIKE '%\_fact' OR table_name LIKE '%\_dev')
```
Resultado: SOLO `infoventas_2024_fact`, `infoventas_2024_dev`, ...

---

## 📊 ANTES vs DESPUÉS

| Aspecto | Antes | Después |
|---------|-------|---------|
| Tablas en vista | 6+ | 4 |
| Duplicación | ❌ SÍ | ✅ NO |
| Validación | ❌ Manual | ✅ Automática |
| Rendimiento | ⚠️ Lento | ✅ Rápido |

---

**Duración:** 15-20 min | **Riesgo:** Muy bajo | **Impacto:** Alto (datos consistentes)
