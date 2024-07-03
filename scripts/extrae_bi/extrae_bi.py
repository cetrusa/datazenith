import os
import pandas as pd
from sqlalchemy import create_engine, text
import logging
from scripts.conexion import Conexion as con
from scripts.config import ConfigBasic
import ast
import time
import sqlalchemy

# Configuración del logging
logging.basicConfig(
    filename="logExtractor.txt",
    level=logging.DEBUG,
    format="%(asctime)s %(message)s",
    filemode="w",
)

class DataBaseConnection:
    def __init__(self, config, mysql_engine=None, sqlite_engine=None):
        self.config = config
        self.engine_mysql_bi = mysql_engine if mysql_engine else self.create_engine_mysql_bi()
        self.engine_mysql_out = mysql_engine if mysql_engine else self.create_engine_mysql_out()
        self.engine_sqlite = sqlite_engine if sqlite_engine else create_engine("sqlite:///mydata.db")

    def create_engine_mysql_bi(self):
        user, password, host, port, database = (
            self.config.get("nmUsrIn"),
            self.config.get("txPassIn"),
            self.config.get("hostServerIn"),
            self.config.get("portServerIn"),
            self.config.get("dbBi"),
        )
        return con.ConexionMariadb3(str(user), str(password), str(host), int(port), str(database))

    def create_engine_mysql_out(self):
        user, password, host, port, database = (
            self.config.get("nmUsrOut"),
            self.config.get("txPassOut"),
            self.config.get("hostServerOut"),
            self.config.get("portServerOut"),
            self.config.get("dbSidis"),
        )
        return con.ConexionMariadb3(str(user), str(password), str(host), int(port), str(database))

class Extrae_Bi:
    def __init__(self, database_name, IdtReporteIni, IdtReporteFin):
        self.database_name = database_name
        self.IdtReporteIni = IdtReporteIni
        self.IdtReporteFin = IdtReporteFin
        self.configurar(database_name)

    def configurar(self, database_name):
        try:
            self.config_basic = ConfigBasic(database_name)
            self.config = self.config_basic.config
            self.db_connection = DataBaseConnection(config=self.config)
            self.engine_sqlite = self.db_connection.engine_sqlite
            self.engine_mysql_bi = self.db_connection.engine_mysql_bi
            self.engine_mysql_out = self.db_connection.engine_mysql_out
            print("Configuraciones preliminares de actualización terminadas")
        except Exception as e:
            logging.error(f"Error al inicializar Actualización: {e}")
            raise

    def extractor(self):
        print("Iniciando extractor")
        try:
            txProcedureExtrae = self.config.get("txProcedureExtrae", [])
            if isinstance(txProcedureExtrae, str):
                txProcedureExtrae = ast.literal_eval(txProcedureExtrae)
            for a in txProcedureExtrae:
                print("Procesando:", a)
                sql = text(f"SELECT * FROM powerbi_adm.conf_sql WHERE nbSql = :a")
                result = self.config_basic.execute_sql_query(sql, {"a": a})
                df = result

                if not df.empty:
                    self.txTabla = df["txTabla"].iloc[0]
                    self.nmReporte = df["nmReporte"].iloc[0]
                    self.nmProcedure_out = df["nmProcedure_out"].iloc[0]
                    self.nmProcedure_in = df["nmProcedure_in"].iloc[0]
                    self.txSql = df["txSql"].iloc[0]
                    self.txSqlExtrae = df["txSqlExtrae"].iloc[0]

                    logging.info(f"Se va a procesar {self.nmReporte}")

                    try:
                        self.procedimiento_a_sql()
                        logging.info(f"La información se generó con éxito de {self.nmReporte}")
                    except Exception as e:
                        logging.info(f"No fue posible extraer la información de {self.nmReporte} por {e}")
                        print(f"Error al ejecutar procedimiento_a_sql para {self.nmReporte}: {e}")
                else:
                    logging.warning(f"No se encontraron resultados para nbSql = {a}")
                    print(f"No se encontraron resultados para nbSql = {a}")
            print("Extracción completada con éxito")
            return {"success": True}
        except Exception as e:
            print(f"Error general en el extractor: {e}")
            return {"success": False, "error": str(e)}
        finally:
            logging.info("Finalizado el procedimiento de ejecución SQL.")

    def insertar_sql(self, resultado_out):
        with self.engine_mysql_bi.connect() as connectionin:
            cursorbi = connectionin.execution_options(isolation_level="READ COMMITTED")
            resultado_out.to_sql(
                name=self.txTabla,
                con=cursorbi,
                if_exists="append",
                index=False,
                index_label=None,
            )
            return logging.info("Los datos se han insertado correctamente")

    def consulta_sql_out_extrae(self):
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                with self.engine_mysql_out.connect() as connection:
                    cursorout = connection.execution_options(isolation_level="READ COMMITTED")
                    sqlout = text(self.txSqlExtrae)
                    resultado = pd.read_sql_query(
                        sql=sqlout,
                        con=cursorout,
                        params={"fi": self.IdtReporteIni, "ff": self.IdtReporteFin},
                    )
                    return resultado
            except sqlalchemy.exc.IntegrityError as e:
                logging.error(f"Error de integridad: {e}")
                retry_count += 1
                time.sleep(1)
            except sqlalchemy.exc.ProgrammingError as e:
                logging.error(f"Error de programación: {e}")
                retry_count += 1
                time.sleep(1)
            except Exception as e:
                logging.error(f"Error desconocido: {e}")
                retry_count += 1
                time.sleep(1)
        return None

    def consulta_sql_bi(self):
        """
        Ejecuta una consulta SQL en la base de datos BI y borra los datos correspondientes.

        Returns:
            int: Número de filas borradas.
        """
        try:
            # Establecer conexión con la base de datos BI
            with self.engine_mysql_bi.connect() as connection:
                # Iniciar una transacción manualmente
                trans = connection.begin()
                try:
                    # Preparar y ejecutar la consulta SQL
                    sqldelete = text(self.txSql)
                    result = connection.execute(
                        sqldelete, {"fi": self.IdtReporteIni, "ff": self.IdtReporteFin}
                    )
                    # Obtener el número de filas afectadas y hacer commit manualmente
                    rows_deleted = result.rowcount
                    trans.commit()  # Confirmar los cambios explícitamente
                    
                    # Registrar el éxito de la operación
                    logging.info(f"Datos borrados correctamente. Filas afectadas: {rows_deleted} {self.txSql}")
                    print(f"Datos borrados correctamente. Filas afectadas: {rows_deleted} {self.txSql}")
                    
                    # Devolver el número de filas borradas
                    return rows_deleted
                    
                except Exception as e:
                    # En caso de error, hacer rollback de la transacción
                    trans.rollback()
                    logging.error(f"Error en consulta_sql_bi durante el commit: {e}")
                    raise
                    
        except Exception as e:
            # Registrar y manejar cualquier excepción
            logging.error(f"Error al borrar datos en consulta_sql_bi: {e}")
            raise


    def procedimiento_a_sql(self):
        for intento in range(3):  # Intentar la conexión hasta tres veces
            try:
                # Verificar directamente si txSqlExtrae tiene un valor adecuado y no es "None"
                if self.txSqlExtrae and self.txSqlExtrae != "None":
                    resultado_out = self.consulta_sql_out_extrae()
                    if resultado_out is not None and not resultado_out.empty:
                        rows_deleted = self.consulta_sql_bi()
                        if rows_deleted > 0:
                            self.insertar_sql(resultado_out=resultado_out)
                        else:
                            logging.warning("No se borraron filas en consulta_sql_bi, inserción cancelada.")
                    else:
                        logging.warning("No se obtuvieron resultados en consulta_sql_out_extrae, inserción cancelada.")
                else:
                    rows_deleted = self.consulta_sql_bi()
                    if rows_deleted > 0:
                        self.insertar_sql(pd.DataFrame())
                    else:
                        logging.warning("No se borraron filas en consulta_sql_bi, inserción cancelada.")

                logging.info(f"Proceso completado para {self.txTabla}.")
                return  # Sale del bucle después de completar el proceso con éxito

            except Exception as e:
                logging.error(f"Error en procedimiento_a_sql (Intento {intento + 1}/3): {e}")
                if intento >= 2:
                    logging.error("Se agotaron los intentos. No se pudo ejecutar el procedimiento.")
                    break  # Sale del bucle si se alcanza el máximo de intentos
                else:
                    logging.info(f"Reintentando procedimiento (Intento {intento + 1}/3)...")
                    time.sleep(5)  # Espera antes de reintentar

