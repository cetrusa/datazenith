# ============================================================
# 📦 CARGUE_INFOVENTAS_MAIN.PY
# ------------------------------------------------------------
# Descripción:
#   Script autónomo para cargar archivos de información de ventas
#   (.xlsx o .csv) hacia la base de datos correspondiente, sin
#   depender de Django. Utiliza ConfigBasic para resolver
#   automáticamente las credenciales y parámetros de conexión.
#
# ------------------------------------------------------------
# 🧰 Requisitos previos:
#   - Estructura de directorios:
#       scripts/
#           ├── conexion.py
#           ├── config.py
#           ├── config_repository.py
#           ├── cargue_infoventas_insert.py
#   - Configuración de acceso a la base:
#       Las credenciales deben estar registradas en las tablas
#       `powerbi_adm.conf_server` y `powerbi_adm.conf_tipo`,
#       o bien en `secret.json` si ConfigBasic lo permite.
#
# ------------------------------------------------------------
# ⚙️ Modo de uso (línea de comandos):
#
#   🔸 1. Procesar todos los archivos de una carpeta:
#       python cargue_infoventas_main.py --base bi_distrijass --carpeta "D:\Python\DataZenithBi\Info proveedores 2024"
#
#   🔸 2. Procesar un archivo único:
#       python cargue_infoventas_main.py --base bi_distrijass --archivo "D:\Python\DataZenithBi\Info proveedores 2024\infoventas_2025_01.xlsx"
#
#   🔸 3. Mostrar ayuda:
#       python cargue_infoventas_main.py --help
#
# ------------------------------------------------------------
# 🔍 Descripción de parámetros:
#
#   --base      Nombre lógico del entorno o conexión configurada.
#               (Ejemplo: bi_distrijass)
#
#   --carpeta   Ruta completa a una carpeta que contiene archivos
#               .xlsx o .csv a procesar. Los archivos se ejecutan
#               en orden alfabético.
#
#   --archivo   Ruta completa de un solo archivo a procesar.
#               Si se indica este parámetro, ignora --carpeta.
#
# ------------------------------------------------------------
# 🧠 Funcionamiento interno:
#
#   1. ConfigBasic obtiene las credenciales de conexión (usuario,
#      contraseña, host, puerto, base de datos) desde la fuente
#      configurada.
#
#   2. Se crea la conexión mediante ConexionMariadb3.
#
#   3. Se inicializa ConfigRepository y CargueInfoVentasInsert.
#
#   4. Cada archivo se procesa y se insertan los registros en la
#      tabla staging (infoventas), siguiendo la lógica interna
#      del cargador.
#
#   5. Se registra en consola el resumen de filas insertadas,
#      duplicadas y duración total del proceso.
#
# ------------------------------------------------------------
# 🧾 Ejemplo de salida esperada:
#
#   2025-10-03 14:10:25 [INFO] ⚙️ Configurando conexión para entorno 'bi_distrijass'...
#   2025-10-03 14:10:26 [INFO] ✅ Conectado a bi_distrijass en 181.49.241.226:3306
#   2025-10-03 14:10:26 [INFO] 🚀 Iniciando cargue del archivo: infoventas_2025_01.xlsx
#   2025-10-03 14:10:55 [INFO] ✅ Cargue completado con éxito.
#   2025-10-03 14:10:55 [INFO] 📊 Filas insertadas: 256334
#   2025-10-03 14:10:55 [INFO] 📦 Filas duplicadas: 112
#   2025-10-03 14:10:55 [INFO] 🕒 Duración total: 29.14 segundos
#
# ------------------------------------------------------------
# 🧩 Recomendaciones:
#
#   - Usa rutas absolutas (no relativas) para carpetas o archivos.
#   - Verifica antes del cargue que los nombres de columnas del
#     archivo coincidan con los esperados por CargueInfoVentasInsert.
#   - Puedes usar `time.sleep()` entre archivos para evitar sobrecarga
#     en el servidor si cargas grandes volúmenes.
#   - Ideal para programar en tareas automáticas (Windows Task
#     Scheduler o cron en Linux).
#
# ------------------------------------------------------------
# 👨‍💻 Autor: [Tu nombre o equipo]
# 📅 Última actualización: 2025-10-03
# ============================================================
# ============================================================
# 📦 CARGUE_INFOVENTAS_MAIN.PY (Versión final con mantenimiento automático)
# ============================================================

import os
import sys
import time
import logging
import argparse
from datetime import datetime
from scripts.cargue.cargue_infoventas_insert import CargueInfoVentasInsert
from sqlalchemy import text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

# ------------------------------------------------------------
# 🔍 Detectar fechas en el nombre del archivo
# ------------------------------------------------------------
def detectar_fechas_desde_nombre(nombre_archivo: str):
    """Extrae año y mes desde el nombre del archivo (ej: 2025-08 o 202508)."""
    import re
    match = re.search(r"(\d{4})[-_]?(\d{2})", nombre_archivo)
    if match:
        anio, mes = match.groups()
        from calendar import monthrange
        fecha_ini = datetime(int(anio), int(mes), 1).date()
        fecha_fin = datetime(int(anio), int(mes), monthrange(int(anio), int(mes))[1]).date()
        return fecha_ini, fecha_fin
    return None, None


# ------------------------------------------------------------
# ⚙️ Proceso completo de cargue + mantenimiento
# ------------------------------------------------------------
def run_cargue(database_name: str, archivo_path: str, usuario: str = None):
    """Ejecuta el proceso completo de cargue y mantenimiento."""
    start_time = time.time()
    logging.info(f"🚀 Iniciando cargue del archivo: {archivo_path}")

    # Detectar fechas desde nombre del archivo
    fecha_ini, fecha_fin = detectar_fechas_desde_nombre(os.path.basename(archivo_path))
    if not fecha_ini or not fecha_fin:
        logging.warning("⚠️ No se pudieron detectar fechas desde el nombre. Se usará el mes actual.")
        hoy = datetime.now()
        from calendar import monthrange
        fecha_ini = datetime(hoy.year, hoy.month, 1).date()
        fecha_fin = datetime(hoy.year, hoy.month, monthrange(hoy.year, hoy.month)[1]).date()

    logging.info(f"📅 Rango de fechas detectado: {fecha_ini} → {fecha_fin}")

    conn = None
    try:
        # 🔹 Crear instancia del cargador
        cargador = CargueInfoVentasInsert(
            excel_file=archivo_path,
            database_name=database_name,
            IdtReporteIni=str(fecha_ini),
            IdtReporteFin=str(fecha_fin),
            user_id=usuario or "SYSTEM"
        )

        # 🔹 Ejecutar proceso de cargue
        resultado = cargador.procesar_cargue()
        logging.info("✅ Cargue completado correctamente.")
        logging.info(f"📊 Filas insertadas: {resultado.get('insertadas', 0)}")
        logging.info(f"⚠️ Filas duplicadas: {resultado.get('duplicadas', 0)}")
        
        
        logging.info("🧹 Ejecutando mantenimiento post-cargue (sp_infoventas_full_maintenance)...")

        # Obtener conexión cruda desde el engine SQLAlchemy
        with cargador.engine_mysql.raw_connection() as conn:
            conn.autocommit(True)
            with conn.cursor() as cursor:
                cursor.execute("call sp_infoventas_full_maintenance();")
                conn.commit()

            # Validar si se vació la tabla infoventas
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM infoventas;")
                restantes = cursor.fetchone()[0]

            if restantes == 0:
                logging.info("✅ Mantenimiento completado. Tabla infoventas limpia.")
            else:
                logging.warning(f"⚠️ Mantenimiento ejecutado, pero aún hay {restantes} registros en infoventas.")

    except Exception as e:
        logging.error(f"❌ Error ejecutando mantenimiento: {e}", exc_info=True)

    finally:
        if conn:
            try:
                conn.close()
                logging.info("🔒 Conexión cerrada correctamente.")
            except Exception:
                pass


# ------------------------------------------------------------
# 🧩 Lógica principal con CLI
# ------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Carga automatizada de InfoVentas")
    parser.add_argument("--base", required=True, help="Nombre de la base de datos (ej: bi_distrijass)")
    parser.add_argument("--archivo", help="Ruta de un archivo específico")
    parser.add_argument("--carpeta", help="Ruta de carpeta con múltiples archivos")
    parser.add_argument("--usuario", help="Usuario que ejecuta el proceso (por defecto SYSTEM)")

    args = parser.parse_args()
    database_name = args.base
    usuario = args.usuario or "SYSTEM"

    if args.archivo:
        run_cargue(database_name, args.archivo, usuario)
    elif args.carpeta:
        archivos = sorted([
            os.path.join(args.carpeta, f)
            for f in os.listdir(args.carpeta)
            if f.endswith(".xlsx") or f.endswith(".csv")
        ])
        for archivo in archivos:
            run_cargue(database_name, archivo, usuario)
            time.sleep(3)  # Pequeña pausa entre archivos
    else:
        logging.error("❌ Debes indicar --archivo o --carpeta.")


if __name__ == "__main__":
    main()
