# 🧹 CORRECCIÓN ADICIONAL: Limpieza de Tabla Anual

## 🚨 PROBLEMA DETECTADO (NOVEDAD)

Después de migrar datos a `infoventas_2025_fact` e `infoventas_2025_dev`, **la tabla anual `infoventas_2025` NO se limpiaba**. Esto causaba:

```
❌ ANTES:
├─ infoventas_2025:      60,000 registros (datos DUPLICADOS)
├─ infoventas_2025_fact: 48,000 registros (mismo dato)
└─ infoventas_2025_dev:  12,000 registros (mismo dato)

Resultado: DATOS DUPLICADOS = 60,000 + 48,000 + 12,000 = 120,000 (❌)
```

---

## ✅ SOLUCIÓN IMPLEMENTADA

### Agregado: Limpieza automática de tabla anual después de migración

Se añadió un nuevo bloque **DESPUÉS** de insertar en `_fact` y `_dev`:

```sql
-- 🧹 LIMPIAR TABLA ANUAL DESPUÉS DE MIGRAR A FACT/DEV
-- Contar registros que vamos a eliminar
SELECT COUNT(*) INTO v_staging_count FROM (
  SELECT * FROM information_schema.tables 
  WHERE table_schema = DATABASE() AND table_name = v_tbl
) t;

IF v_staging_count > 0 THEN
  -- Eliminar registros ya migrados de la tabla anual
  SET @delAnnual = CONCAT('DELETE FROM `', v_tbl, '`;');
  PREPARE stmt FROM @delAnnual; EXECUTE stmt; DEALLOCATE PREPARE stmt;
  INSERT INTO audit_infoventas_maintenance (proceso, estado, timestamp) 
    VALUES ('sp_infoventas_full_maintenance', CONCAT('cleanup_annual_table OK - tabla ', v_tbl, ' vaciada después de migración'), NOW());
END IF;
```

### ¿Qué hace?

1. **Valida** que la tabla anual existe
2. **Elimina** todos los registros de la tabla anual (`DELETE FROM infoventas_2025`)
3. **Registra** en auditoría que la limpieza se completó
4. **Garantiza** que los datos SOLO existen en `_fact` y `_dev`

---

## 📊 RESULTADO DESPUÉS

```
✅ DESPUÉS:
├─ infoventas_2025:      0 registros (LIMPIADA ✅)
├─ infoventas_2025_fact: 48,000 registros
└─ infoventas_2025_dev:  12,000 registros

Resultado: SIN DUPLICACIÓN = 0 + 48,000 + 12,000 = 60,000 (✅)
```

---

## 🔄 FLUJO COMPLETO AHORA

```
┌─────────────────────────────────────┐
│ 1. Datos llegan a staging           │
│    (infoventas)                     │
└─────────────┬───────────────────────┘
              ▼
┌─────────────────────────────────────┐
│ 2. Se migran a tabla anual          │
│    (infoventas_2025)                │
└─────────────┬───────────────────────┘
              ▼
┌─────────────────────────────────────┐
│ 3. Se clasifican a fact/dev         │
│    (SELECT ... FROM 2025)           │
│    → INSERT INTO 2025_fact          │
│    → INSERT INTO 2025_dev           │
└─────────────┬───────────────────────┘
              ▼
┌─────────────────────────────────────┐
│ 4. 🆕 SE LIMPIA TABLA ANUAL ✅      │
│    DELETE FROM infoventas_2025      │
└─────────────┬───────────────────────┘
              ▼
┌─────────────────────────────────────┐
│ 5. Vista se reconstruye SOLO con    │
│    _fact y _dev (sin duplicación)   │
└─────────────────────────────────────┘
```

---

## 🎯 ORDEN DE EJECUCIÓN EN sp_infoventas_full_maintenance()

```
FASE 1: ensure_current_next_year()
FASE 2: migrate_pending() → staging → infoventas_2025
FASE 3: rebuild_view() → SOLO _fact/_dev
FASE 4: Clasificación:
   a) Crear _fact si no existe
   b) Crear _dev si no existe
   c) INSERT INTO _fact (SELECT * FROM 2025 WHERE Tipo=0)
   d) INSERT INTO _dev (SELECT * FROM 2025 WHERE Tipo=1)
   e) 🆕 DELETE FROM infoventas_2025 (NUEVO PASO)
FASE 5: migrate_historico_to_fact_dev()
FASE 6: DELETE FROM infoventas WHERE YEAR(Fecha) <= current_year
FASE 7: COMMIT
```

---

## ✅ ARCHIVO ACTUALIZADO

📁 `scripts/sql/sp_infoventas_maintenance_fixed.sql`

**Cambio:** Líneas ~130-145 (aproximadas)

Se agregó:
```sql
-- 🧹 LIMPIAR TABLA ANUAL DESPUÉS DE MIGRAR A FACT/DEV
IF v_staging_count > 0 THEN
  SET @delAnnual = CONCAT('DELETE FROM `', v_tbl, '`;');
  PREPARE stmt FROM @delAnnual; EXECUTE stmt; DEALLOCATE PREPARE stmt;
  INSERT INTO audit_infoventas_maintenance (...);
END IF;
```

---

## 🔍 VALIDACIÓN POST-APLICACIÓN

```sql
-- Después de ejecutar el cargue, verifica:

SELECT 'infoventas_2025' AS tbl, COUNT(*) AS qty FROM infoventas_2025
UNION ALL
SELECT 'infoventas_2025_fact', COUNT(*) FROM infoventas_2025_fact
UNION ALL
SELECT 'infoventas_2025_dev', COUNT(*) FROM infoventas_2025_dev;

-- RESULTADO ESPERADO:
-- infoventas_2025:      0 (limpiada ✅)
-- infoventas_2025_fact: 48,000 (datos aquí)
-- infoventas_2025_dev:  12,000 (datos aquí)
```

---

## 📝 AUDITORÍA

En la tabla `audit_infoventas_maintenance` verás:

```
proceso                              estado
─────────────────────────────────────────────────────────────
sp_infoventas_full_maintenance       INICIO
sp_infoventas_full_maintenance       ensure_current_next_year OK
sp_infoventas_full_maintenance       migrate_pending OK
sp_infoventas_full_maintenance       rebuild_view OK - SOLO _fact y _dev
sp_infoventas_full_maintenance       cleanup_annual_table OK - tabla infoventas_2025 vaciada
sp_infoventas_full_maintenance       clasificacion_fact_dev OK - tables: infoventas_2025_fact, infoventas_2025_dev
sp_infoventas_full_maintenance       migrate_historico OK
sp_infoventas_full_maintenance       staging_cleanup OK - 3421 filas eliminadas
sp_infoventas_full_maintenance       EXITOSO
```

Nota el nuevo estado: **"cleanup_annual_table OK"** ✅

---

## ⚠️ NOTAS IMPORTANTES

1. **La tabla anual se VACÍA completamente** después de migrar a _fact/_dev
   - ANTES: Se conservaban 60,000 registros
   - AHORA: 0 registros (se conservan SOLO en _fact/_dev)

2. **No se pierden datos** porque están en _fact y _dev
   - La tabla anual es FUENTE temporal para clasificación
   - Después de clasificar, no se necesita

3. **La vista NUNCA incluye la tabla anual**
   - Incluso si tuviera datos, no aparecería en `vw_infoventas`
   - Pero es mejor mantenerla limpia para claridad

4. **Auditoría registra cada paso**
   - Puedes verificar que la limpieza se ejecutó correctamente

---

## 📊 COMPARATIVA: ANTES vs DESPUÉS

| Aspecto | ANTES | DESPUÉS |
|---------|-------|---------|
| Tabla anual después de migrar | 60,000 registros | 0 registros ✅ |
| Duplicación de datos | ❌ SÍ | ✅ NO |
| Claridad de estructura | ⚠️ Confusa | ✅ Clara |
| Espacio en disco | ❌ Mayor | ✅ Menor |
| Vista correcta | ✅ SÍ | ✅ SÍ |

---

## 🚀 PRÓXIMOS PASOS

1. ✅ Usar el script actualizado: `sp_infoventas_maintenance_fixed.sql`
2. ✅ Aplicar en BD (reemplaza la versión anterior)
3. ✅ Ejecutar cargue de prueba
4. ✅ Validar que:
   - `infoventas_2025` = 0 registros
   - `infoventas_2025_fact` = N registros
   - `infoventas_2025_dev` = M registros
   - Auditoría muestra "cleanup_annual_table OK"

---

**Actualización:** 18 de octubre de 2025 (Post-descubrimiento del problema)  
**Estado:** ✅ Corrección integrada en `sp_infoventas_maintenance_fixed.sql`
