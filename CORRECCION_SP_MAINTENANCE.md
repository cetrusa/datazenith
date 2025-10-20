# 🔧 CORRECCIÓN: sp_infoventas_full_maintenance

## 🚨 PROBLEMA IDENTIFICADO

El procedimiento `sp_infoventas_rebuild_view()` estaba **reconstruyendo la vista con TODAS las tablas** que coincidieran con el patrón `infoventas_%`, incluyendo:

```
❌ infoventas_2024
❌ infoventas_2025
❌ infoventas_2026
✅ infoventas_2024_fact
✅ infoventas_2024_dev
✅ infoventas_2025_fact
✅ infoventas_2025_dev
```

### ¿Por qué es un problema?

1. **Duplicación de datos**: Los mismos registros aparecen en `infoventas_YYYY` Y en `infoventas_YYYY_fact/dev`
2. **Redundancia en la vista**: La vista `vw_infoventas` incluye ambas versiones (año completo + fact/dev)
3. **Datos inconsistentes**: No hay garantía de que las tablas anuales y las fact/dev estén sincronizadas
4. **Rendimiento degradado**: UNION ALL innecesarios sobre tablas duplicadas

---

## ✅ SOLUCIÓN IMPLEMENTADA

### Cambio 1: Filtro en el cursor (línea crítica)

**ANTES:**
```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = DATABASE() AND table_name LIKE 'infoventas\_%' ESCAPE '\\'
ORDER BY table_name;
```

**AHORA:**
```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = DATABASE() 
  AND table_name LIKE 'infoventas\_%' ESCAPE '\\'
  AND (table_name LIKE '%\_fact' ESCAPE '\\' OR table_name LIKE '%\_dev' ESCAPE '\\')
ORDER BY table_name;
```

### Impacto:
- ✅ La vista `vw_infoventas` ahora **SOLO incluye** `_fact` y `_dev`
- ✅ Las tablas anuales (`infoventas_YYYY`) se usan como **fuente de datos**, no se incluyen en la vista
- ✅ Datos consistentes y sin duplicación

---

## 📋 PASOS PARA APLICAR LA CORRECCIÓN

### 1️⃣ Conectar a la base de datos

```bash
# Desde PowerShell
mysql -h <HOST> -u <USER> -p <DATABASE> < scripts/sql/sp_infoventas_maintenance_fixed.sql
```

O desde phpMyAdmin/DBeaver:
- Copia el contenido de `sp_infoventas_maintenance_fixed.sql`
- Pégalo en la pestaña "SQL" de tu gestor de BD
- Ejecuta

### 2️⃣ Verificar que los procedimientos se crearon

```sql
SHOW PROCEDURE STATUS WHERE Name LIKE 'sp_infoventas%';
```

Deberías ver:
- `sp_infoventas_full_maintenance`
- `sp_infoventas_rebuild_view` ✅ (actualizado)
- `sp_infoventas_migrate_pending`
- etc.

### 3️⃣ Probar la corrección

**Ejecuta el procedimiento completo:**
```sql
CALL sp_infoventas_full_maintenance();
```

**Verifica el log de auditoría:**
```sql
SELECT * FROM audit_infoventas_maintenance 
ORDER BY timestamp DESC 
LIMIT 20;
```

Deberías ver:
- ✅ `ensure_current_next_year OK`
- ✅ `migrate_pending OK`
- ✅ `rebuild_view OK - SOLO _fact y _dev`
- ✅ `clasificacion_fact_dev OK`
- ✅ `migrate_historico OK`
- ✅ `staging_cleanup OK - N filas eliminadas`
- ✅ `EXITOSO`

### 4️⃣ Validar composición de la vista

```sql
-- ¿Qué tablas incluye ahora la vista?
SELECT GROUP_CONCAT(table_name) AS tablas_en_vista
FROM information_schema.tables
WHERE table_schema = DATABASE() 
  AND table_name LIKE 'infoventas\_%' ESCAPE '\\'
  AND (table_name LIKE '%\_fact' ESCAPE '\\' OR table_name LIKE '%\_dev' ESCAPE '\\')
ORDER BY table_name;
```

**Resultado esperado:**
```
infoventas_2024_dev, infoventas_2024_fact, infoventas_2025_dev, infoventas_2025_fact, ...
```

### 5️⃣ Comparar registros

```sql
SELECT 'vw_infoventas' AS origen, COUNT(*) AS cantidad FROM vw_infoventas
UNION ALL
SELECT 'infoventas_2025_fact', COUNT(*) FROM infoventas_2025_fact
UNION ALL
SELECT 'infoventas_2025_dev', COUNT(*) FROM infoventas_2025_dev
UNION ALL
SELECT 'infoventas_staging', COUNT(*) FROM infoventas;
```

**Validación:**
- `vw_infoventas` = `infoventas_2025_fact` + `infoventas_2025_dev` + otros años `_fact/_dev`
- `infoventas_2025` ≠ vista (es la fuente, NO se incluye en ella)
- `infoventas_staging` = registros pendientes de procesar

---

## 🔄 CAMBIOS EN cargue_infoventas_main.py

**No requiere cambios** en el archivo Python. El script ya:
- ✅ Llama correctamente a `sp_infoventas_full_maintenance()`
- ✅ Maneja reintentos adecuadamente
- ✅ Registra en la tabla de auditoría

Sin embargo, si lo deseas, puedes mejorar el logging para mostrar:

```python
# Después de ejecutar el procedimiento, consultar:
SELECT estado, COUNT(*) AS intentos, MAX(timestamp) AS último
FROM audit_infoventas_maintenance
WHERE proceso = 'sp_infoventas_full_maintenance'
GROUP BY estado;
```

---

## 🧪 PRUEBA RÁPIDA POST-CORRECCIÓN

### Test 1: Ejecutar el procedimiento completo

```bash
cd D:\Python\DataZenithBi\adminbi
python cargue_infoventas_main.py --base bi_distrijass --archivo "ruta/archivo.xlsx"
```

### Test 2: Verificar que la vista es correcta

En phpMyAdmin o DBeaver:
```sql
SHOW CREATE VIEW vw_infoventas;
```

Debe mostrar solo `_fact` y `_dev`, NO años completos.

### Test 3: Revisar auditoría

```sql
SELECT * FROM audit_infoventas_maintenance 
WHERE proceso = 'sp_infoventas_full_maintenance'
ORDER BY timestamp DESC LIMIT 1;
```

Debe mostrar `EXITOSO`.

---

## 📞 PRÓXIMAS ACCIONES

1. ✅ **Aplicar el script SQL** a la base de datos
2. ✅ **Ejecutar prueba con un archivo pequeño** para validar
3. ✅ **Verificar auditoría** para confirmar ejecución correcta
4. ✅ **Comparar registros** en vista vs tablas para garantizar consistencia
5. ✅ **Monitorear próximos cargues** para asegurar que no haya duplicación

---

## ❓ PREGUNTAS FRECUENTES

**P: ¿Debo borrar la vista actual?**  
R: No, el script usa `CREATE OR REPLACE VIEW`, que la actualiza automáticamente.

**P: ¿Los datos existentes se perderán?**  
R: No, solo se reconstruye la vista (`vw_infoventas`). Los datos en tablas permanecen intactos.

**P: ¿Qué pasa con los registros en `infoventas_2024`?**  
R: Siguen existiendo como fuente. Si necesitas migrar el histórico a `_fact/_dev`, el procedimiento `sp_infoventas_migrate_historico_to_fact_dev()` lo maneja.

**P: ¿Necesito reiniciar el servicio MySQL?**  
R: No, los cambios en procedimientos se aplican inmediatamente.

---

**Última actualización:** 18 de octubre de 2025
