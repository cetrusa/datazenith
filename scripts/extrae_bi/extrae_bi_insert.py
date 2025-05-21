import logging
from typing import Optional, Callable
import pandas as pd
from sqlalchemy import text
import time
import ast
import numpy as np
from scripts.conexion import Conexion as con
from scripts.config import ConfigBasic

# Configuración global de logging
logging.basicConfig(
    filename="logExtractor.txt",
    level=logging.DEBUG,
    format="%(asctime)s %(message)s",
    filemode="w",
)


class ExtraeBiConfig:
    """Clase para manejar la configuración y conexiones a bases de datos."""

    def __init__(self, database_name: str):
        self.config_basic = ConfigBasic(database_name)
        self.config = self.config_basic.config
        self.engine_mysql_bi = self._create_engine_mysql_bi()
        self.engine_mysql_out = self._create_engine_mysql_out()
        import os

        db_path = os.path.join("media", "mydata.db")
        self.engine_sqlite = con.ConexionSqlite(db_path)

    def _create_engine_mysql_bi(self):
        c = self.config
        return con.ConexionMariadb3(
            str(c.get("nmUsrIn")),
            str(c.get("txPassIn")),
            str(c.get("hostServerIn")),
            int(c.get("portServerIn")),
            str(c.get("dbBi")),
        )

    def _create_engine_mysql_out(self):
        c = self.config
        return con.ConexionMariadb3(
            str(c.get("nmUsrOut")),
            str(c.get("txPassOut")),
            str(c.get("hostServerOut")),
            int(c.get("portServerOut")),
            str(c.get("dbSidis")),
        )


class ExtraeBiExtractor:
    """Clase principal para la extracción e inserción de datos BI."""

    def __init__(
        self,
        config: ExtraeBiConfig,
        IdtReporteIni: str,
        IdtReporteFin: str,
        user_id: Optional[int] = None,
        id_reporte: Optional[int] = None,
        batch_size: Optional[int] = None,
        progress_callback: Optional[Callable] = None,
    ):
        self.config = config.config
        self.config_basic = config.config_basic
        self.engine_mysql_bi = config.engine_mysql_bi
        self.engine_mysql_out = config.engine_mysql_out
        self.engine_sqlite = config.engine_sqlite
        self.IdtReporteIni = IdtReporteIni
        self.IdtReporteFin = IdtReporteFin
        self.user_id = user_id
        self.id_reporte = id_reporte
        self.batch_size = batch_size
        self.progress_callback = progress_callback
        # Variables de proceso
        self.txTabla = None
        self.nmReporte = None
        self.nmProcedure_out = None
        self.nmProcedure_in = None
        self.txSql = None
        self.txSqlExtrae = None

    def run(self):
        """Método principal para ejecutar el proceso completo."""
        return self.extractor()

    def extractor(self):
        logging.info("Iniciando extractor")
        errores_tablas = []  # Lista para recolectar errores por tabla
        try:
            txProcedureExtrae = self.config.get("txProcedureExtrae", [])
            if isinstance(txProcedureExtrae, str):
                txProcedureExtrae = ast.literal_eval(txProcedureExtrae)
            total = len(txProcedureExtrae)
            for idx, a in enumerate(txProcedureExtrae, 1):
                sql = text("SELECT * FROM powerbi_adm.conf_sql WHERE nbSql = :a")
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
                    if self.progress_callback:
                        progress_percent = int((idx - 1) / total * 100)
                        self.progress_callback(
                            {
                                "stage": f"Procesando {a}",
                                "tabla": self.txTabla,
                                "nmReporte": self.nmReporte,
                                "progress": progress_percent,
                            },
                            progress_percent,
                        )
                    try:
                        self.procedimiento_a_sql()
                        logging.info(
                            f"La información se generó con éxito de {self.nmReporte}"
                        )
                    except Exception as e:
                        logging.error(
                            f"No fue posible extraer la información de {self.nmReporte} por {e}"
                        )
                        errores_tablas.append(
                            {
                                "tabla": self.txTabla,
                                "nmReporte": self.nmReporte,
                                "error": str(e),
                            }
                        )
                else:
                    logging.warning(f"No se encontraron resultados para nbSql = {a}")
                    errores_tablas.append(
                        {
                            "tabla": None,
                            "nmReporte": a,
                            "error": f"No se encontraron resultados para nbSql = {a}",
                        }
                    )
            if self.progress_callback:
                self.progress_callback(
                    {
                        "stage": "Extracción completada",
                        "tabla": None,
                        "nmReporte": None,
                        "progress": 100,
                    },
                    100,
                )
            logging.info("Extracción completada con éxito")
            return {
                "status": "completed",
                "success": True,
                "message": "Extracción completada con éxito",
                "errores_tablas": errores_tablas,
                "tablas_procesadas": (
                    [
                        {
                            "tabla": getattr(self, "txTabla", None),
                            "nmReporte": getattr(self, "nmReporte", None),
                        }
                    ]
                    if hasattr(self, "txTabla") and hasattr(self, "nmReporte")
                    else []
                ),
            }
        except Exception as e:
            logging.error(f"Error general en el extractor: {e}")
            errores_tablas.append({"tabla": None, "nmReporte": None, "error": str(e)})
            return {
                "status": "completed",
                "success": False,
                "message": f"Error general en el extractor: {e}",
                "errores_tablas": errores_tablas,
                "error": str(e),
            }
        finally:
            logging.info("Finalizado el procedimiento de ejecución SQL.")

    def procedimiento_a_sql(self):
        for intento in range(3):
            try:
                rows_deleted = self.consulta_sql_bi()
                if rows_deleted == 0:
                    logging.warning(
                        "No se borraron filas en consulta_sql_bi, pero se continuará con la inserción de datos."
                    )
                if self.txSqlExtrae:
                    resultado_out = self.consulta_sql_out_extrae()
                    if resultado_out is not None and not resultado_out.empty:
                        self.insertar_sql(resultado_out=resultado_out)
                    else:
                        logging.warning(
                            "No se obtuvieron resultados en consulta_sql_out_extrae, inserción cancelada."
                        )
                        continue
                else:
                    logging.warning(
                        "Se intentó insertar sin un SQL de extracción definido. Proceso cancelado."
                    )
                    break
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
                logging.info(f"Reintentando procedimiento (Intento {intento + 1}/3)...")
                time.sleep(5)

    def consulta_sql_bi(self) -> int:
        if not self.txSql:
            logging.warning(
                "La variable txSql no contiene ninguna consulta SQL válida."
            )
            return 0
        for intento in range(3):
            try:
                with self.engine_mysql_bi.connect().execution_options(
                    isolation_level="AUTOCOMMIT"
                ) as connection:
                    sqldelete = text(self.txSql)
                    result = connection.execute(
                        sqldelete, {"fi": self.IdtReporteIni, "ff": self.IdtReporteFin}
                    )
                    rows_deleted = result.rowcount
                    logging.info(
                        f"Datos borrados correctamente. Filas afectadas: {rows_deleted} {self.txSql}"
                    )
                    return rows_deleted
            except Exception as e:
                logging.error(
                    f"Error al borrar datos en consulta_sql_bi (Intento {intento + 1}/3): {e}"
                )
                if intento >= 2:
                    logging.error(
                        "Se agotaron los intentos. No se pudo ejecutar la consulta_sql_bi."
                    )
                    break
                logging.info(
                    f"Reintentando consulta_sql_bi (Intento {intento + 1}/3)..."
                )
                time.sleep(5)
        return 0

    def consulta_sql_out_extrae(self) -> Optional[pd.DataFrame]:
        max_retries = 3
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
            except Exception as e:
                logging.error(
                    f"Error en consulta_sql_out_extrae (Intento {retry_count + 1}/3): {e}"
                )
                if retry_count == max_retries - 1:
                    logging.error(
                        "Se agotaron los intentos en consulta_sql_out_extrae."
                    )
                    return None
                logging.info(
                    f"Reintentando consulta_sql_out_extrae (Intento {retry_count + 1}/{max_retries})..."
                )
                time.sleep(1)

    def insertar_sql(self, resultado_out: pd.DataFrame):
        if resultado_out.empty:
            logging.warning(
                "Intento de insertar un DataFrame vacío. Inserción cancelada."
            )
            return
        numeric_columns = ["latitud_cl", "longitud_cl"]
        for col in numeric_columns:
            if col in resultado_out.columns:
                resultado_out[col] = pd.to_numeric(resultado_out[col], errors="coerce")
        if "macrozona_id" in resultado_out.columns:
            resultado_out["macrozona_id"] = resultado_out["macrozona_id"].fillna(0)
            resultado_out["macrozona_id"] = resultado_out["macrozona_id"].replace(
                {"": 0}
            )
        if "macro" in resultado_out.columns:
            resultado_out["macro"] = pd.to_numeric(
                resultado_out["macro"], errors="coerce"
            )
            resultado_out["macro"] = resultado_out["macro"].fillna(0)
            resultado_out["macro"] = resultado_out["macro"].replace({"": 0})
        resultado_out = resultado_out.replace({np.nan: None, "": None})
        if len(resultado_out) > 0:
            registros_originales = len(resultado_out)
            resultado_out = resultado_out.drop_duplicates()
            registros_sin_duplicados = len(resultado_out)
            if registros_sin_duplicados < registros_originales:
                logging.info(
                    f"Se eliminaron {registros_originales - registros_sin_duplicados} duplicados del dataframe antes de insertar"
                )
        CHUNK_THRESHOLD = 5000
        CHUNK_SIZE = 5000
        primary_keys = self.obtener_claves_primarias()
        if primary_keys:
            self.insertar_con_on_duplicate_key(
                resultado_out, CHUNK_THRESHOLD, CHUNK_SIZE
            )
        else:
            self.insertar_con_ignore(resultado_out, CHUNK_THRESHOLD, CHUNK_SIZE)
        logging.info(
            f"Se han insertado {len(resultado_out)} registros en {self.txTabla} correctamente."
        )

    def obtener_claves_primarias(self):
        query = text(
            f"""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = '{self.config.get("dbBi")}' 
            AND TABLE_NAME = '{self.txTabla}'
            AND CONSTRAINT_NAME = 'PRIMARY';
        """
        )
        try:
            with self.engine_mysql_bi.connect() as connection:
                resultado = connection.execute(query)
                return [row[0] for row in resultado.fetchall()]
        except Exception as e:
            logging.error(f"Error obteniendo claves primarias de {self.txTabla}: {e}")
            return []

    def insertar_con_on_duplicate_key(self, df, chunk_threshold, chunk_size):
        data_list = df.to_dict(orient="records")
        total_rows = len(data_list)
        logging.info(
            f"Se preparan {total_rows} registros para insertar con ON DUPLICATE KEY en {self.txTabla}."
        )
        if not data_list:
            logging.warning(f"No hay registros para insertar en {self.txTabla}")
            return
        columnas = list(df.columns)
        columnas_str = ", ".join(columnas)
        placeholders = ", ".join([f":{col}" for col in columnas])
        update_columns = ", ".join([f"{col}=VALUES({col})" for col in columnas])
        insert_query = f"""
            INSERT INTO {self.txTabla} ({columnas_str})
            VALUES ({placeholders})
            ON DUPLICATE KEY UPDATE {update_columns};
        """
        with self.engine_mysql_bi.begin() as connection:
            if total_rows > chunk_threshold:
                logging.info(
                    f"Más de {chunk_threshold} registros, usando inserciones en chunks de {chunk_size}."
                )
                for start_idx in range(0, total_rows, chunk_size):
                    chunk = data_list[start_idx : start_idx + chunk_size]
                    connection.execute(text(insert_query), chunk)
                    logging.debug(
                        f"Insertado chunk desde {start_idx} hasta {start_idx + len(chunk)} filas."
                    )
            else:
                connection.execute(text(insert_query), data_list)

    def insertar_con_ignore(self, df, chunk_threshold, chunk_size):
        data_list = df.to_dict(orient="records")
        total_rows = len(data_list)
        logging.info(
            f"Se preparan {total_rows} registros para insertar con INSERT IGNORE en {self.txTabla}."
        )
        if not data_list:
            logging.warning(f"No hay registros para insertar en {self.txTabla}")
            return
        columnas = list(df.columns)
        columnas_str = ", ".join(columnas)
        placeholders = ", ".join([f":{col}" for col in columnas])
        insert_query = f"""
            INSERT IGNORE INTO {self.txTabla} ({columnas_str})
            VALUES ({placeholders});
        """
        with self.engine_mysql_bi.begin() as connection:
            if total_rows > chunk_threshold:
                logging.info(
                    f"Más de {chunk_threshold} registros, usando inserciones en chunks de {chunk_size}."
                )
                for start_idx in range(0, total_rows, chunk_size):
                    chunk = data_list[start_idx : start_idx + chunk_size]
                    connection.execute(text(insert_query), chunk)
                    logging.debug(
                        f"Insertado chunk desde {start_idx} hasta {start_idx + len(chunk)} filas."
                    )
            else:
                connection.execute(text(insert_query), data_list)


# Si se desea ejecutar como script independiente
if __name__ == "__main__":
    # Aquí podrías parsear argumentos y ejecutar el proceso
    # Ejemplo:
    # config = ExtraeBiConfig(database_name="mi_db")
    # extractor = ExtraeBiExtractor(config, "20250101", "20250131")
    # extractor.run()
    pass
