# 🚀 GUÍA RÁPIDA: Aplicar la corrección del Full Maintenance

## ⚡ VERSIÓN CORTA (5 minutos)

### Paso 1: Aplicar procedimientos SQL
```bash
# En PowerShell, dentro del directorio del proyecto:
Get-Content scripts/sql/sp_infoventas_maintenance_fixed.sql | mysql -h <HOST> -u <USER> -p <DATABASE>
```

O manualmente en phpMyAdmin/DBeaver:
1. Abre phpMyAdmin o DBeaver
2. Conecta a tu BD
3. Abre pestaña "SQL"
4. Copia el contenido de `scripts/sql/sp_infoventas_maintenance_fixed.sql`
5. Pega y ejecuta

### Paso 2: Verificar procedimientos
```sql
SHOW PROCEDURE STATUS WHERE Name LIKE 'sp_infoventas%';
```

Deberías ver:
- ✅ `sp_infoventas_full_maintenance`
- ✅ `sp_infoventas_rebuild_view` (ACTUALIZADO)
- ✅ Otros procedimientos

### Paso 3: Ejecutar cargue de prueba
```bash
cd d:\Python\DataZenithBi\adminbi
python cargue_infoventas_main.py --base bi_distrijass --archivo "ruta/archivo_pequeno.xlsx"
```

### Paso 4: Revisar diagnóstico
Al final de la ejecución verás un bloque como:

```
======================================================================
🔍 DIAGNÓSTICO: Composición de vw_infoventas
======================================================================

1️⃣ Estructura de vw_infoventas:
   📊 Tablas en la vista: 4
   ✅ La vista NO incluye tablas anuales completas.     ← ESTO ES CORRECTO
   ✅ La vista incluye correctamente tablas _fact y _dev.

2️⃣ Tablas detectadas...
   ✅ Consistencia verificada.                         ← ESTO CONFIRMA QUE FUNCIONA
```

**✅ ¡LISTO!** Si ves "✅" en los puntos cruciales, la corrección está aplicada correctamente.

---

## 📋 VERSIÓN COMPLETA CON VALIDACIONES (15 minutos)

### Fase 1: Preparación
```bash
# 1. Navega al proyecto
cd d:\Python\DataZenithBi\adminbi

# 2. Verifica que el archivo de script existe
Get-Item scripts/sql/sp_infoventas_maintenance_fixed.sql
```

### Fase 2: Aplicar cambios a la BD
```bash
# Opción A: Terminal (recomendado)
Get-Content scripts/sql/sp_infoventas_maintenance_fixed.sql | mysql -h <HOST> -u <USER> -p<PASSWORD> <DATABASE>

# Opción B: Archivo con salida de log
Get-Content scripts/sql/sp_infoventas_maintenance_fixed.sql | mysql -h <HOST> -u <USER> -p<PASSWORD> <DATABASE> > bd_update.log 2>&1
Get-Content bd_update.log  # Ver resultados
```

### Fase 3: Validar procedimientos
```sql
-- Conecta a la BD y ejecuta:

-- 1️⃣ Ver definición del procedimiento actualizado
SHOW CREATE PROCEDURE sp_infoventas_rebuild_view;

-- 2️⃣ Verificar que tiene el filtro correcto (debe contener '%_fact' y '%_dev')
-- Deberías ver en la salida: ... LIKE '%\_fact' ... LIKE '%\_dev' ...

-- 3️⃣ Ver última ejecución del procedimiento
SELECT * FROM audit_infoventas_maintenance 
WHERE proceso = 'sp_infoventas_rebuild_view'
ORDER BY timestamp DESC LIMIT 3;
```

### Fase 4: Ejecutar prueba completa
```bash
# Ejecutar cargue pequeño con diagnóstico automático
python cargue_infoventas_main.py --base bi_distrijass --archivo "ruta/archivo.xlsx"
```

### Fase 5: Verificaciones post-ejecución
```sql
-- En la BD, ejecuta:

-- 1️⃣ Verificar que vista SOLO tiene _fact y _dev
SELECT GROUP_CONCAT(table_name ORDER BY table_name) AS tablas_en_vista
FROM information_schema.tables
WHERE table_schema = DATABASE() 
  AND table_name LIKE 'infoventas\_%' ESCAPE '\\'
  AND (table_name LIKE '%\_fact' ESCAPE '\\' OR table_name LIKE '%\_dev' ESCAPE '\\')
ORDER BY table_name;

-- Resultado esperado:
-- infoventas_2024_dev, infoventas_2024_fact, infoventas_2025_dev, infoventas_2025_fact, ...

-- 2️⃣ Contar registros para validar consistencia
SELECT 'Vista' AS origen, COUNT(*) AS qty FROM vw_infoventas
UNION ALL
SELECT '_fact+_dev' AS origen,
  (SELECT COUNT(*) FROM infoventas_2024_fact) +
  (SELECT COUNT(*) FROM infoventas_2024_dev) +
  (SELECT COUNT(*) FROM infoventas_2025_fact) +
  (SELECT COUNT(*) FROM infoventas_2025_dev) AS qty;

-- Si ambas filas tienen el MISMO número = ✅ CORRECTO

-- 3️⃣ Revisar auditoría
SELECT * FROM audit_infoventas_maintenance 
WHERE YEAR(timestamp) = YEAR(NOW())
ORDER BY timestamp DESC LIMIT 20;
```

---

## 🎯 PUNTOS DE CONTROL CRÍTICOS

| Checkpoint | Qué verificar | Esperado |
|-----------|---------------|----------|
| Procedimientos creados | `SHOW PROCEDURE STATUS` | Ver `sp_infoventas_rebuild_view` |
| Vista contiene | `SHOW CREATE VIEW vw_infoventas` | Contiene `_fact` y `_dev`, NO `infoventas_2024` |
| Sin duplicación | Comparar vista vs suma fact+dev | Ambas suman igual |
| Diagnóstico ejecuta | Revisar salida del script | Muestra "✅ Consistencia verificada" |
| Auditoría registra | Consultar tabla `audit_infoventas_maintenance` | Últimas ejecuciones aparecen |

---

## 🆘 SI ALGO FALLA

### Error: "Tabla de auditoría no existe"
```sql
-- Crear tabla manualmente:
CREATE TABLE IF NOT EXISTS audit_infoventas_maintenance (
  id INT AUTO_INCREMENT PRIMARY KEY,
  proceso VARCHAR(255),
  estado VARCHAR(255),
  timestamp DATETIME DEFAULT NOW(),
  KEY idx_timestamp (timestamp),
  KEY idx_proceso (proceso)
);
```

### Error: "Procedimiento no actualiza"
1. Verifica que se ejecutó sin errores el script .sql
2. Ejecuta manualmente en BD:
   ```sql
   CALL sp_infoventas_rebuild_view();
   ```
3. Mira si hay errores en la ejecución

### Error: "Vista sigue teniendo tablas anuales"
1. Verifica la definición actual:
   ```sql
   SHOW CREATE VIEW vw_infoventas\G
   ```
2. Si sigue incluyendo `infoventas_2024` completo:
   - Asegúrate que ejecutaste el script correcto
   - Verifica no hay triggers que modifican la vista
   - Intenta eliminar y recrear:
     ```sql
     DROP VIEW IF EXISTS vw_infoventas;
     CALL sp_infoventas_rebuild_view();
     ```

### Error: "Datos se duplican en la vista"
1. Consulta tablas que hay:
   ```sql
   SELECT GROUP_CONCAT(table_name) 
   FROM information_schema.tables
   WHERE table_schema = DATABASE() AND table_name LIKE 'infoventas%';
   ```
2. Si hay tablas extras (`_staging`, `_temp`, etc.), elimínalas:
   ```sql
   DROP TABLE IF EXISTS infoventas_staging, infoventas_temp;
   ```
3. Reconstruye vista:
   ```sql
   CALL sp_infoventas_rebuild_view();
   ```

---

## 📊 COMANDO COMPLETO EN UNA LÍNEA (Para automatizar)

```bash
# Aplicar cambios + ejecutar diagnóstico
Get-Content scripts/sql/sp_infoventas_maintenance_fixed.sql | mysql -h localhost -u root -padmin bi_distrijass; python cargue_infoventas_main.py --base bi_distrijass --archivo "archivo.xlsx"
```

---

## ✅ CHECKLIST FINAL

- [ ] Script SQL ejecutado sin errores
- [ ] `sp_infoventas_rebuild_view` actualizado
- [ ] Tabla `audit_infoventas_maintenance` existe
- [ ] Cargue de prueba ejecutado
- [ ] Diagnóstico muestra "✅ Consistencia verificada"
- [ ] Conteo de registros coincide (vista = sum(fact+dev))
- [ ] No hay tablas anuales en la vista
- [ ] Auditoría registra ejecuciones correctas

**Si todos están marcados: ✅ ¡IMPLEMENTACIÓN EXITOSA!**

---

**Tiempo estimado total:** 15-20 minutos  
**Dificultad:** Baja  
**Riesgo de datos:** Muy bajo (solo se modifica vista, no datos)
