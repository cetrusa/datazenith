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
        self.engine_mysql_bi = (
            mysql_engine if mysql_engine else self.create_engine_mysql_bi()
        )
        self.engine_mysql_out = (
            mysql_engine if mysql_engine else self.create_engine_mysql_out()
        )
        self.engine_sqlite = (
            sqlite_engine if sqlite_engine else create_engine("sqlite:///mydata.db")
        )

    def create_engine_mysql_bi(self):
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
        finally:
            logging.info("Finalizado el procedimiento de ejecución SQL.")

    def insertar_sql(self, resultado_out):
        """
        Inserta los datos de 'resultado_out' en la tabla 'self.txTabla'
        usando ON DUPLICATE KEY UPDATE.
        Si la cantidad de registros supera CHUNK_THRESHOLD, se insertan en chunks.
        """
        if resultado_out.empty:
            logging.warning("Intento de insertar un DataFrame vacío. Inserción cancelada.")
            return

        # Convertir columnas numéricas (si existen) a tipo numérico
        numeric_columns = ["latitud_cl", "longitud_cl"]
        for col in numeric_columns:
            if col in resultado_out.columns:
                resultado_out[col] = pd.to_numeric(resultado_out[col], errors="coerce")
        
        # Rellenar valores nulos o cadenas vacías para 'macrozona_id'
        if "macrozona_id" in resultado_out.columns:
            # Por ejemplo, asignar 0 a los registros que no tengan macrozona_id
            resultado_out["macrozona_id"] = resultado_out["macrozona_id"].fillna(0)
            resultado_out["macrozona_id"] = resultado_out["macrozona_id"].replace({'': 0})   
            
        if "macro" in resultado_out.columns:
            # Convertir la columna a numérico (si es el caso) y asignar 0 en caso de valores nulos o cadenas vacías
            resultado_out["macro"] = pd.to_numeric(resultado_out["macro"], errors="coerce")
            resultado_out["macro"] = resultado_out["macro"].fillna(0)
            resultado_out["macro"] = resultado_out["macro"].replace({'': 0})    

        # Reemplazar valores NaN y cadenas vacías por None para que se inserten como NULL
        import numpy as np
        resultado_out = resultado_out.replace({np.nan: None, '': None})

        # Definir umbral y tamaño de chunk
        CHUNK_THRESHOLD = 5000
        CHUNK_SIZE = 5000  # Ajusta según tus necesidades

        # Preparar la consulta de inserción
        columnas = list(resultado_out.columns)
        columnas_str = ",".join(columnas)
        placeholders = ",".join([f":{col}" for col in columnas])
        update_columns = ",".join([f"{col}=VALUES({col})" for col in columnas])

        insert_query = f"""
            INSERT INTO {self.txTabla} ({columnas_str})
            VALUES ({placeholders})
            ON DUPLICATE KEY UPDATE {update_columns};
        """

        data_list = resultado_out.to_dict(orient="records")
        total_rows = len(data_list)
        logging.info(f"Se recibieron {total_rows} registros para insertar en {self.txTabla}.")

        # Usar engine.begin() para asegurar que se haga commit al finalizar el bloque
        with self.engine_mysql_bi.begin() as connection:
            if total_rows > CHUNK_THRESHOLD:
                logging.info(f"Más de {CHUNK_THRESHOLD} registros, usando inserciones en chunks de {CHUNK_SIZE}.")
                for start_idx in range(0, total_rows, CHUNK_SIZE):
                    chunk = data_list[start_idx: start_idx + CHUNK_SIZE]
                    connection.execute(text(insert_query), chunk)
                    logging.debug(f"Insertado chunk desde {start_idx} hasta {start_idx + len(chunk)} filas.")
            else:
                connection.execute(text(insert_query), data_list)

        logging.info(f"Se han insertado {total_rows} registros en {self.txTabla} correctamente.")


    def consulta_sql_out_extrae(self):
        """
        Ejecuta una consulta SQL en la base de datos de salida con el nivel de aislamiento adecuado.
        - Usa AUTOCOMMIT si la consulta es un INSERT o CALL (procedimiento almacenado).
        - Usa READ COMMITTED para consultas SELECT.
        
        Retorna:
            DataFrame con los datos extraídos o None si falla.
        """
        max_retries = 3

        # Determinar el nivel de aislamiento adecuado
        if self.txSqlExtrae:
            txSqlUpper = self.txSqlExtrae.strip().upper()
            if txSqlUpper.startswith("INSERT") or txSqlUpper.startswith("CALL"):
                isolation_level = "AUTOCOMMIT"
            else:
                isolation_level = "READ COMMITTED"
        else:
            logging.warning("La variable txSqlExtrae está vacía.")
            return None

        for retry_count in range(max_retries):
            try:
                with self.engine_mysql_out.connect().execution_options(
                    isolation_level=isolation_level
                ) as connection:
                    sqlout = text(self.txSqlExtrae)
                    resultado = pd.read_sql_query(
                        sql=sqlout,
                        con=connection,
                        params={"fi": self.IdtReporteIni, "ff": self.IdtReporteFin},
                    )
                    logging.info(f"Consulta ejecutada con éxito en {isolation_level}.")
                    return resultado

            except sqlalchemy.exc.IntegrityError as e:
                logging.error(f"Error de integridad en consulta_sql_out_extrae: {e}")
            except sqlalchemy.exc.ProgrammingError as e:
                logging.error(f"Error de programación en consulta_sql_out_extrae: {e}")
            except Exception as e:
                logging.error(f"Error desconocido en consulta_sql_out_extrae: {e}")

            if retry_count == max_retries - 1:
                logging.error("Se agotaron los intentos en consulta_sql_out_extrae.")
                return None

            logging.info(f"Reintentando consulta_sql_out_extrae (Intento {retry_count + 1}/{max_retries})...")
            time.sleep(1)  # Espera antes de reintentar


    def consulta_sql_bi(self):
        """
        Ejecuta una consulta SQL en la base de datos BI para borrar datos según self.txSql,
        reintentando hasta 3 veces en caso de error.

        Returns:
            int: Número de filas borradas.
        """
        # Verificar si txSql tiene una consulta válida
        if not self.txSql:
            logging.warning("La variable txSql no contiene ninguna consulta SQL válida.")
            return 0

        for intento in range(3):
            try:
                # Usar connect() con autocommit para operaciones DDL (TRUNCATE/DELETE)
                with self.engine_mysql_bi.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
                    sqldelete = text(self.txSql)
                    result = connection.execute(
                        sqldelete,
                        {"fi": self.IdtReporteIni, "ff": self.IdtReporteFin}
                    )
                    rows_deleted = result.rowcount
                    logging.info(
                        f"Datos borrados correctamente. Filas afectadas: {rows_deleted} {self.txSql}"
                    )
                    print(f"Datos borrados correctamente. Filas afectadas: {rows_deleted} {self.txSql}")
                    return rows_deleted

            except Exception as e:
                logging.error(f"Error al borrar datos en consulta_sql_bi (Intento {intento + 1}/3): {e}")
                if intento >= 2:
                    logging.error("Se agotaron los intentos. No se pudo ejecutar la consulta_sql_bi.")
                    break
                logging.info(f"Reintentando consulta_sql_bi (Intento {intento + 1}/3)...")
                time.sleep(5)
        return 0



    def procedimiento_a_sql(self):
        for intento in range(3):  # Intentar la conexión hasta tres veces
            try:
                # Ejecutar la consulta para borrar datos
                rows_deleted = self.consulta_sql_bi()

                if rows_deleted == 0:
                    logging.warning(
                        "No se borraron filas en consulta_sql_bi, pero se continuará con la inserción de datos."
                    )

                if self.txSqlExtrae:  # Verificar si txSqlExtrae tiene un valor válido
                    resultado_out = self.consulta_sql_out_extrae()
                    if resultado_out.empty:
                        logging.warning(
                            "No se obtuvieron resultados en consulta_sql_out_extrae, inserción cancelada."
                        )
                        continue  # Saltar al siguiente intento si no hay resultados
                    # Insertar los datos obtenidos
                    self.insertar_sql(resultado_out=resultado_out)
                else:
                    logging.warning(
                        "Se intentó insertar sin un SQL de extracción definido. Proceso cancelado."
                    )
                    break  # Detener el proceso si esto no debería ocurrir

                logging.info(f"Proceso completado para {self.txTabla}.")
                return  # Sale del bucle después de completar el proceso con éxito

            except Exception as e:
                logging.error(
                    f"Error en procedimiento_a_sql (Intento {intento + 1}/3): {e}"
                )
                if intento >= 2:
                    logging.error(
                        "Se agotaron los intentos. No se pudo ejecutar el procedimiento."
                    )
                    break  # Sale del bucle si se alcanza el máximo de intentos
                logging.info(f"Reintentando procedimiento (Intento {intento + 1}/3)...")
                time.sleep(
                    5
                )  # Espera antes de reintentar, pero solo si no es el último intento
