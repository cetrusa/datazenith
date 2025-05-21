-- Script para crear índices en cuboventas solo si no existen (MariaDB/MySQL)
-- Ejecutar este script en la base de datos correspondiente

-- Índice por dtContabilizacion
SET @idx := (SELECT COUNT(1) FROM information_schema.statistics WHERE table_schema=DATABASE() AND table_name='cuboventas' AND index_name='Id1');
SET @sql := IF(@idx=0, 'CREATE INDEX Id1 ON cuboventas (dtContabilizacion);', 'SELECT "Id1 ya existe";');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Índice por nbPlanilla
SET @idx := (SELECT COUNT(1) FROM information_schema.statistics WHERE table_schema=DATABASE() AND table_name='cuboventas' AND index_name='Index1');
SET @sql := IF(@idx=0, 'CREATE INDEX Index1 ON cuboventas (nbPlanilla);', 'SELECT "Index1 ya existe";');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Índice compuesto: dtContabilizacion, nbFactura, prcIva
SET @idx := (SELECT COUNT(1) FROM information_schema.statistics WHERE table_schema=DATABASE() AND table_name='cuboventas' AND index_name='idx_cuboventas_group');
SET @sql := IF(@idx=0, 'CREATE INDEX idx_cuboventas_group ON cuboventas (dtContabilizacion, nbFactura, prcIva);', 'SELECT "idx_cuboventas_group ya existe";');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Índice compuesto: td, dtContabilizacion
SET @idx := (SELECT COUNT(1) FROM information_schema.statistics WHERE table_schema=DATABASE() AND table_name='cuboventas' AND index_name='idx_cuboventas_td_date');
SET @sql := IF(@idx=0, 'CREATE INDEX idx_cuboventas_td_date ON cuboventas (td, dtContabilizacion);', 'SELECT "idx_cuboventas_td_date ya existe";');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Índice compuesto: td, dtContabilizacion, nbFactura, prcIva, idPuntoVenta
SET @idx := (SELECT COUNT(1) FROM information_schema.statistics WHERE table_schema=DATABASE() AND table_name='cuboventas' AND index_name='idx_cuboventas_opt');
SET @sql := IF(@idx=0, 'CREATE INDEX idx_cuboventas_opt ON cuboventas (td, dtContabilizacion, nbFactura, prcIva, idPuntoVenta);', 'SELECT "idx_cuboventas_opt ya existe";');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
