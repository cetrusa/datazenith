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
from sqlalchemy.exc import OperationalError as SAOperationalError
from pymysql.err import OperationalError as PyMySQLOperationalError, InterfaceError as PyMySQLInterfaceError

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
# 🔁 Helper para ejecutar procedimientos con reintentos
# ------------------------------------------------------------
def ejecutar_procedimiento_con_reintentos(cargador, sentencia_sql: str, intentos: int = 3, espera_segundos: int = 45):
    """Ejecuta un procedimiento almacenado con reintentos y ajustes de timeout."""
    ultimo_error = None
    print(f"♻️ Preparando ejecución con hasta {intentos} intentos... [DEBUG]")
    logging.info(f"♻️ Preparando ejecución del procedimiento con hasta {intentos} intentos...")

    for intento in range(1, intentos + 1):
        print(f"   ▶️ Intento {intento}/{intentos}... [DEBUG]")
        logging.info(f"   ▶️ Intento {intento}/{intentos} de ejecución del procedimiento...")

        try:
            conn = cargador.engine_mysql_bi.raw_connection()
            try:
                conn.autocommit(True)
                cursor = conn.cursor()
                try:
                    ajustes_timeout = [
                        "SET SESSION wait_timeout = 7200",
                        "SET SESSION interactive_timeout = 7200",
                        "SET SESSION net_read_timeout = 600",
                        "SET SESSION net_write_timeout = 600",
                        "SET SESSION innodb_lock_wait_timeout = 900",
                    ]
                    for comando in ajustes_timeout:
                        cursor.execute(comando)

                    cursor.execute(sentencia_sql)

                    while True:
                        try:
                            filas = cursor.fetchall()
                            if filas:
                                print(f"📋 Resultados parciales: {filas} [DEBUG]")
                                logging.info(f"📋 Resultados parciales del procedimiento: {filas}")
                        except Exception:
                            pass

                        try:
                            tiene_mas = cursor.nextset()
                        except Exception:
                            tiene_mas = False

                        if not tiene_mas:
                            break

                    conn.commit()
                    print(f"   ✅ Procedimiento finalizado en intento {intento} [DEBUG]")
                    logging.info(f"   ✅ Procedimiento finalizado en intento {intento}")
                    return True, None

                finally:
                    cursor.close()
            finally:
                conn.close()

        except (PyMySQLOperationalError, PyMySQLInterfaceError, SAOperationalError) as db_err:
            # Normalizar código de error
            if isinstance(db_err, SAOperationalError) and hasattr(db_err, "orig"):
                codigo_error = getattr(db_err.orig, "args", [None])[0] if db_err.orig else None
                mensaje_error = str(db_err.orig)
            else:
                codigo_error = getattr(db_err, "args", [None])[0]
                mensaje_error = str(db_err)

            ultimo_error = db_err
            print(f"   ⚠️ Error de base de datos (código {codigo_error}): {mensaje_error} [DEBUG]")
            logging.warning(f"   ⚠️ Error de base de datos (código {codigo_error}): {mensaje_error}")

            if codigo_error == 0:
                print("   ℹ️ Código 0 recibido; se asume ejecución finalizada por cierre de resultados. [DEBUG]")
                logging.info("   ℹ️ Código 0 recibido; se asume ejecución finalizada por cierre de resultados.")
                return True, None

            if codigo_error in (2006, 2013, 1205) and intento < intentos:
                print(f"   ⏳ Reintentando en {espera_segundos} segundos... [DEBUG]")
                logging.info(f"   ⏳ Reintentando en {espera_segundos} segundos...")
                time.sleep(espera_segundos)
                continue
            else:
                break

        except Exception as error_general:
            ultimo_error = error_general
            print(f"   ❌ Error inesperado en intento {intento}: {error_general} [DEBUG]")
            logging.error(f"   ❌ Error inesperado en intento {intento}: {error_general}")

            if intento < intentos:
                print(f"   ⏳ Reintentando en {espera_segundos} segundos... [DEBUG]")
                logging.info(f"   ⏳ Reintentando en {espera_segundos} segundos...")
                time.sleep(espera_segundos)
                continue
            else:
                break

    return False, ultimo_error


# ------------------------------------------------------------
# ⚙️ Proceso completo de cargue + mantenimiento
# ------------------------------------------------------------
def run_cargue(database_name: str, archivo_path: str, usuario: str = None):
    """Ejecuta el proceso completo de cargue y mantenimiento."""
    print("🚀🚀🚀 INICIO FUNCIÓN run_cargue - DEBUG LOG 🚀🚀🚀")
    logging.info("🚀🚀🚀 INICIO FUNCIÓN run_cargue - DEBUG LOG 🚀🚀🚀")
    
    start_time = time.time()
    logging.info(f"🚀 Iniciando cargue del archivo: {archivo_path}")
    print(f"🚀 Iniciando cargue del archivo: {archivo_path}")

    # Detectar fechas desde nombre del archivo
    fecha_ini, fecha_fin = detectar_fechas_desde_nombre(os.path.basename(archivo_path))
    if not fecha_ini or not fecha_fin:
        logging.warning("⚠️ No se pudieron detectar fechas desde el nombre. Se usará el mes actual.")
        hoy = datetime.now()
        from calendar import monthrange
        fecha_ini = datetime(hoy.year, hoy.month, 1).date()
        fecha_fin = datetime(hoy.year, hoy.month, monthrange(hoy.year, hoy.month)[1]).date()

    logging.info(f"📅 Rango de fechas detectado: {fecha_ini} → {fecha_fin}")
    print(f"📅 Rango de fechas detectado: {fecha_ini} → {fecha_fin}")

    cargador = None
    
    try:
        # 🔹 FASE 1: CREAR INSTANCIA DEL CARGADOR
        print("🔧 FASE 1: Creando instancia del cargador... [DEBUG]")
        logging.info("🔧 Fase 1: Creando instancia del cargador...")
        cargador = CargueInfoVentasInsert(
            excel_file=archivo_path,
            database_name=database_name,
            IdtReporteIni=str(fecha_ini),
            IdtReporteFin=str(fecha_fin),
            user_id=usuario or "SYSTEM"
        )
        print("✅ Cargador creado exitosamente [DEBUG]")
        logging.info("✅ Cargador creado exitosamente")

        # 🔹 FASE 2: EJECUTAR PROCESO DE CARGUE
        print("🔧 FASE 2: Ejecutando proceso de cargue... [DEBUG]")
        logging.info("🔧 Fase 2: Ejecutando proceso de cargue...")
        resultado = cargador.procesar_cargue()
        print("✅ Cargue completado correctamente [DEBUG]")
        logging.info("✅ Cargue completado correctamente.")
        logging.info(f"📊 Registros procesados: {resultado.get('registros_procesados', 0)}")
        logging.info(f"📊 Registros insertados: {resultado.get('registros_insertados', 0)}")
        logging.info(f"📊 Registros actualizados: {resultado.get('registros_actualizados', 0)}")
        logging.info(f"📊 Registros preservados: {resultado.get('registros_preservados', 0)}")
        
        # 🔹 FASE 3: EJECUTAR MANTENIMIENTO POST-CARGUE
        print("🔧 FASE 3: Iniciando mantenimiento post-cargue... [DEBUG]")
        logging.info("🔧 Fase 3: Iniciando mantenimiento post-cargue...")
        ejecutar_mantenimiento_completo(cargador)
        
        # 🔹 FASE 4: REPORTE FINAL
        elapsed_time = time.time() - start_time
        print(f"🎉 PROCESO COMPLETADO EXITOSAMENTE en {elapsed_time:.2f} segundos [DEBUG]")
        logging.info(f"🎉 PROCESO COMPLETADO EXITOSAMENTE en {elapsed_time:.2f} segundos")
        
    except Exception as e:
        print(f"❌ ERROR CRÍTICO en el proceso principal: {e} [DEBUG]")
        logging.error(f"❌ ERROR CRÍTICO en el proceso principal: {e}", exc_info=True)
        raise e
    finally:
        # Limpieza final
        print("🧹 Ejecutando limpieza final... [DEBUG]")
        if cargador and hasattr(cargador, 'engine_mysql_bi'):
            try:
                cargador.engine_mysql_bi.dispose()
                logging.info("🔒 Engine de base de datos cerrado correctamente.")
            except Exception:
                pass
        print("🏁 FIN FUNCIÓN run_cargue [DEBUG]")


def ejecutar_mantenimiento_completo(cargador):
    """Ejecuta el mantenimiento completo post-cargue con múltiples métodos de respaldo."""
    print("🧹 === INICIANDO FUNCIÓN ejecutar_mantenimiento_completo [DEBUG] ===")
    logging.info("🧹 === INICIANDO MANTENIMIENTO POST-CARGUE ===")
    
    # Verificar registros antes del mantenimiento
    registros_antes = 0
    try:
        print("📊 Verificando registros antes del mantenimiento... [DEBUG]")
        conn = cargador.engine_mysql_bi.raw_connection()
        try:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT COUNT(*) FROM infoventas;")
                registros_antes = cursor.fetchone()[0]
                print(f"📊 Registros en infoventas ANTES: {registros_antes} [DEBUG]")
                logging.info(f"📊 Registros en infoventas ANTES del mantenimiento: {registros_antes}")
            finally:
                cursor.close()
        finally:
            conn.close()
    except Exception as e:
        print(f"❌ Error verificando registros antes: {e} [DEBUG]")
        logging.error(f"❌ Error verificando registros antes del mantenimiento: {e}")
        registros_antes = -1

    # Método 1: Intentar con conexión cruda
    mantenimiento_exitoso = False
    
    try:
        print("🔧 Método 1: Ejecutando con raw_connection y reintentos... [DEBUG]")
        logging.info("🔧 Método 1: Ejecutando con raw_connection y reintentos...")
        exito_raw, error_raw = ejecutar_procedimiento_con_reintentos(
            cargador,
            "CALL sp_infoventas_full_maintenance();",
            intentos=3,
            espera_segundos=60,
        )

        if not exito_raw:
            if error_raw:
                raise error_raw
            raise RuntimeError("No se pudo ejecutar el procedimiento, sin detalle adicional")

        mantenimiento_exitoso = True

    except Exception as e:
        print(f"❌ Error en Método 1: {e} [DEBUG]")
        logging.error(f"❌ Error en Método 1 (raw_connection): {e}")
        logging.error(f"❌ Tipo de error: {type(e).__name__}")
        
        # Método 2: Intentar con SQLAlchemy text()
        try:
            print("🔧 Método 2: Intentando con SQLAlchemy text()... [DEBUG]")
            logging.info("🔧 Método 2: Intentando con SQLAlchemy text()...")
            with cargador.engine_mysql_bi.begin() as connection:
                for comando in (
                    "SET SESSION wait_timeout = 7200",
                    "SET SESSION interactive_timeout = 7200",
                    "SET SESSION net_read_timeout = 600",
                    "SET SESSION net_write_timeout = 600",
                    "SET SESSION innodb_lock_wait_timeout = 900",
                ):
                    connection.exec_driver_sql(comando)

                print("📡 Ejecutando: CALL sp_infoventas_full_maintenance() con text() [DEBUG]")
                logging.info("📡 Ejecutando: CALL sp_infoventas_full_maintenance() con text()")
                result = connection.execute(text("CALL sp_infoventas_full_maintenance();"))
                print("✅ Procedimiento ejecutado con SQLAlchemy text() [DEBUG]")
                logging.info("✅ Procedimiento ejecutado con SQLAlchemy text()")
                
                # Verificar si hay resultados
                try:
                    cursor = getattr(result, "cursor", None)
                    if cursor is not None:
                        while True:
                            try:
                                rows = cursor.fetchall()
                                if rows:
                                    print(f"📋 Resultados: {rows} [DEBUG]")
                                    logging.info(f"📋 Resultados: {rows}")
                            except Exception:
                                pass

                            if not cursor.nextset():
                                break
                    else:
                        rows = result.fetchall()
                        if rows:
                            print(f"📋 Resultados: {rows} [DEBUG]")
                            logging.info(f"📋 Resultados: {rows}")
                except Exception as warn_err:
                    print(f"📋 Sin resultados específicos [DEBUG] ({warn_err})")
                    logging.info(f"📋 Sin resultados específicos ({warn_err})")
                finally:
                    try:
                        result.close()
                    except Exception:
                        pass
                
                mantenimiento_exitoso = True
                        
        except Exception as e2:
            print(f"❌ Error en Método 2: {e2} [DEBUG]")
            logging.error(f"❌ Error en Método 2 (SQLAlchemy text): {e2}")
            logging.error(f"❌ Tipo de error: {type(e2).__name__}")
            
            # Método 3: Verificar que el procedimiento existe y diagnosticar
            try:
                print("🔧 Método 3: Diagnóstico del procedimiento... [DEBUG]")
                logging.info("🔧 Método 3: Diagnóstico del procedimiento...")
                conn = cargador.engine_mysql_bi.raw_connection()
                try:
                    cursor = conn.cursor()
                    try:
                        cursor.execute("SHOW PROCEDURE STATUS WHERE Name = 'sp_infoventas_full_maintenance';")
                        proc_info = cursor.fetchall()
                        if proc_info:
                            print(f"✅ Procedimiento encontrado: {proc_info} [DEBUG]")
                            logging.info(f"✅ Procedimiento encontrado: {proc_info}")
                        else:
                            print("❌ Procedimiento sp_infoventas_full_maintenance NO existe [DEBUG]")
                            logging.error("❌ Procedimiento sp_infoventas_full_maintenance NO existe")
                            
                        # Intentar procedimiento simple para probar conectividad
                        cursor.execute("SELECT 'TEST_CONNECTION' as test;")
                        test_result = cursor.fetchone()
                        print(f"✅ Test de conexión exitoso: {test_result} [DEBUG]")
                        logging.info(f"✅ Test de conexión exitoso: {test_result}")
                    finally:
                        cursor.close()
                finally:
                    conn.close()
                        
            except Exception as e3:
                print(f"❌ Error en Método 3: {e3} [DEBUG]")
                logging.error(f"❌ Error en Método 3 (verificación): {e3}")

    # Verificar resultado final del mantenimiento
    try:
        print("📊 Verificando resultado final... [DEBUG]")
        conn = cargador.engine_mysql_bi.raw_connection()
        try:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT COUNT(*) FROM infoventas;")
                registros_despues = cursor.fetchone()[0]
                print(f"📊 Registros en infoventas DESPUÉS: {registros_despues} [DEBUG]")
                logging.info(f"📊 Registros en infoventas DESPUÉS del mantenimiento: {registros_despues}")
            finally:
                cursor.close()
        finally:
            conn.close()

        if registros_despues == 0:
            print("✅ Mantenimiento completado. Tabla infoventas limpia. [DEBUG]")
            logging.info("✅ Mantenimiento completado. Tabla infoventas limpia.")
            mantenimiento_exitoso = True
        elif registros_antes > 0 and registros_despues < registros_antes:
            print(f"✅ Mantenimiento parcial. Reducidos de {registros_antes} a {registros_despues} registros. [DEBUG]")
            logging.info(f"✅ Mantenimiento parcial. Reducidos de {registros_antes} a {registros_despues} registros.")
            mantenimiento_exitoso = True
        elif registros_antes > 0 and registros_despues == registros_antes:
            print(f"⚠️ Mantenimiento posiblemente no ejecutado. Registros sin cambios: {registros_despues} [DEBUG]")
            logging.warning(f"⚠️ Mantenimiento posiblemente no ejecutado. Registros sin cambios: {registros_despues}")
        else:
            print(f"📊 Estado post-mantenimiento: {registros_despues} registros [DEBUG]")
            logging.info(f"📊 Estado post-mantenimiento: {registros_despues} registros")
            
    except Exception as e:
        print(f"❌ Error verificando resultado final: {e} [DEBUG]")
        logging.error(f"❌ Error verificando resultado final: {e}")
    
    if mantenimiento_exitoso:
        print("🎉 === MANTENIMIENTO COMPLETADO EXITOSAMENTE === [DEBUG]")
        logging.info("🎉 === MANTENIMIENTO COMPLETADO EXITOSAMENTE ===")
    else:
        print("⚠️ === MANTENIMIENTO CON ERRORES - REVISAR LOGS === [DEBUG]")
        logging.warning("⚠️ === MANTENIMIENTO CON ERRORES - REVISAR LOGS ===")
    
    print("🏁 FIN FUNCIÓN ejecutar_mantenimiento_completo [DEBUG]")
    return mantenimiento_exitoso


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
