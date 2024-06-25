import os
import pandas as pd
from sqlalchemy import create_engine
import logging
from scripts.conexion import Conexion as con
from scripts.config import ConfigBasic
import ast
import json
import sqlalchemy
import time
from sqlalchemy import text

# Configuración del logging
logging.basicConfig(
    filename="logExtractor.txt",
    level=logging.DEBUG,
    format="%(asctime)s %(message)s",
    filemode="w",
)


class DataBaseConnection:
    def __init__(self, config, mysql_engine=None):
        self.config = config
        # Asegurarse de que los engines son instancias de conexión válidas y no cadenas
        self.engine_mysql_bi = (
            mysql_engine if mysql_engine else self.create_engine_mysql_bi()
        )
        self.engine_mysql_out = (
            mysql_engine if mysql_engine else self.create_engine_mysql_out()
        )

    def create_engine_mysql_bi(self):
        # Simplificación en la obtención de los parámetros de configuración
        user, password, host, port, database = (
            self.config.get("nmUsrIn"),
            self.config.get("txPassIn"),
            self.config.get("hostServerIn"),
            self.config.get("portServerIn"),
            self.config.get("dbBi"),
        )
        return con.ConexionMariadb3(
            str(user), str(password), str(host), int(port), str(database)
        )

    def create_engine_mysql_out(self):
        # Simplificación en la obtención de los parámetros de configuración
        user, password, host, port, database = (
            self.config.get("nmUsrOut"),
            self.config.get("txPassOut"),
            self.config.get("hostServerOut"),
            self.config.get("portServerOut"),
            self.config.get("dbSidis"),
        )
        return con.ConexionMariadb3(
            str(user), str(password), str(host), int(port), str(database)
        )


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

                sql = text(f"SELECT * FROM powerbi_adm.conf_sql WHERE nbSql = {a}")
                result = self.config_basic.execute_sql_query(sql)
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
                        logging.info(
                            f"La información se generó con éxito de {self.nmReporte}"
                        )
                    except Exception as e:
                        logging.info(
                            f"No fue posible extraer la información de {self.nmReporte} por {e}"
                        )
                        print(
                            f"Error al ejecutar procedimiento_a_sql para {self.nmReporte}: {e}"
                        )
                else:
                    logging.warning(f"No se encontraron resultados para nbSql = {a}")
                    print(f"No se encontraron resultados para nbSql = {a}")
            print("Extracción completada con éxito")
            return {"success": True}
        except Exception as e:
            print(f"Error general en el extractor: {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logging.error(
                f"Error durante la ejecución de la lista de procedimientos con nbSql = {a}: {e}"
            )
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
            return logging.info("los datos se han insertado correctamente")

    def consulta_sql_out_extrae(self):
        max_retries = 3  # Define aquí el número máximo de reintentos
        retry_count = 0

        while retry_count < max_retries:
            try:
                with self.engine_mysql_out.connect() as connection:
                    cursorout = connection.execution_options(
                        isolation_level="READ COMMITTED"
                    )
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
                time.sleep(1)  # Espera antes de reintentar

            except sqlalchemy.exc.ProgrammingError as e:
                logging.error(f"Error de programación: {e}")
                retry_count += 1
                time.sleep(1)  # Espera antes de reintentar

            except Exception as e:
                logging.error(f"Error desconocido: {e}")
                retry_count += 1
                time.sleep(1)  # Espera antes de reintentar

        return None

    def consulta_sql_bi(self):
        try:
            with self.engine_mysql_bi.connect() as connection:
                trans = connection.begin()

                try:
                    sqldelete = text(self.txSql)
                    result = connection.execute(
                        sqldelete, {"fi": self.IdtReporteIni, "ff": self.IdtReporteFin}
                    )

                    rows_deleted = result.rowcount
                    trans.commit()

                    logging.info(
                        f"Datos borrados correctamente. Filas afectadas: {rows_deleted} {self.txSql}"
                    )
                    print(
                        f"Datos borrados correctamente. Filas afectadas: {rows_deleted} {self.txSql}"
                    )

                    return rows_deleted

                except:
                    trans.rollback()
                    raise

        except Exception as e:
            logging.error(f"Error al borrar datos: {e}")
            raise

    def procedimiento_a_sql(self):
        for intento in range(3):
            try:
                if self.txSqlExtrae and self.txSqlExtrae != "None":
                    print("estamos ingresando a buscar un resultado")
                    resultado_out = self.consulta_sql_out_extrae()
                    if resultado_out is not None and not resultado_out.empty:
                        self.consulta_sql_bi()
                        self.insertar_sql(resultado_out=resultado_out)
                else:
                    self.consulta_sql_bi()

                logging.info(f"Proceso completado para {self.txTabla}.")
                return

            except Exception as e:
                logging.error(
                    f"Error en procedimiento_a_sql (Intento {intento + 1}/3): {e}"
                )
                if intento >= 2:
                    logging.error(
                        "Se agotaron los intentos. No se pudo ejecutar el procedimiento."
                    )
                    break
                else:
                    logging.info(
                        f"Reintentando procedimiento (Intento {intento + 1}/3)..."
                    )
                    time.sleep(5)
