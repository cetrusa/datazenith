import os
import pandas as pd
from sqlalchemy import create_engine, text
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
import logging
from scripts.StaticPage import StaticPage
from scripts.conexion import Conexion as con
from scripts.config import ConfigBasic
import ast
import xlsxwriter
import zipfile
from zipfile import ZipFile

# Configuración del logging
logging.basicConfig(
    filename="logInterface.txt",
    level=logging.DEBUG,
    format="%(asctime)s %(message)s",
    filemode="w",
)


class InterfacePlano:
    """
    Clase para la generación de archivos planos comprimidos en ZIP, similar en estructura a Interface.
    """

    def __init__(
        self,
        database_name,
        IdtReporteIni,
        IdtReporteFin,
        user_id=None,
        reporte_id=None,
        progress_callback=None,
    ):
        self.database_name = database_name
        self.IdtReporteIni = IdtReporteIni
        self.IdtReporteFin = IdtReporteFin
        self.user_id = user_id
        self.reporte_id = reporte_id
        self.config = None
        self.engine_mysql = None
        self.engine_sqlite = None
        self.file_path = None
        self.archivo_plano = None
        self.progress_callback = progress_callback
        self._setup()

    def _setup(self):
        config_basic = ConfigBasic(self.database_name)
        self.config = config_basic.config
        self.engine_mysql = con.ConexionMariadb3(
            str(self.config.get("nmUsrIn")),
            str(self.config.get("txPassIn")),
            str(self.config.get("hostServerIn")),
            int(self.config.get("portServerIn")),
            str(self.config.get("dbBi")),
        )
        self.engine_sqlite = create_engine("sqlite:///mydata.db")

    def _generate_sql(self, hoja, proc_key):
        sql = self.config[proc_key]
        if self.config["dbBi"] == "powerbi_tym_eje":
            return text(
                f"CALL {sql}('{self.IdtReporteIni}','{self.IdtReporteFin}','','{str(hoja)}',0,0,0);"
            )
        return text(
            f"CALL {sql}('{self.IdtReporteIni}','{self.IdtReporteFin}','','{str(hoja)}');"
        )

    def _guardar_datos_csv(
        self,
        table_name,
        buffer,
        sep="|",
        float_fmt="%.2f",
        header=True,
        hoja=None,
        total_records=None,
    ):
        chunksize = 50000
        processed = 0
        for chunk in pd.read_sql_query(
            f"SELECT * FROM {table_name}", self.engine_sqlite, chunksize=chunksize
        ):
            if not chunk.empty:
                chunk.to_csv(
                    buffer, sep=sep, index=False, float_format=float_fmt, header=header
                )
                processed += len(chunk)
                if self.progress_callback and total_records:
                    percent = min(99, int((processed / total_records) * 100))
                    self.progress_callback(
                        f"Procesando hoja {hoja}", percent, processed, total_records
                    )

    def _ejecutar_query_mysql_chunked(self, query, table_name, chunksize=50000):
        # Elimina la tabla si existe
        with self.engine_sqlite.connect() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
        with self.engine_mysql.connect() as connection:
            cursor = connection.execution_options(isolation_level="READ COMMITTED")
            for chunk in pd.read_sql_query(query, con=cursor, chunksize=chunksize):
                chunk.to_sql(
                    name=table_name,
                    con=self.engine_sqlite,
                    if_exists="append",
                    index=False,
                )
        with self.engine_sqlite.connect() as conn:
            total_records = conn.execute(
                text(f"SELECT COUNT(*) FROM {table_name}")
            ).fetchone()[0]
        return total_records

    def _procesar_hoja(self, hoja, buffer, proc_key, sep, float_fmt, header):
        try:
            if self.progress_callback:
                self.progress_callback(f"Iniciando hoja {hoja}", 0)
            sqlout = self._generate_sql(hoja, proc_key)
            table_name = f"my_table_{self.database_name}_{hoja}"
            total_records = self._ejecutar_query_mysql_chunked(sqlout, table_name)
            self._guardar_datos_csv(
                table_name,
                buffer,
                sep=sep,
                float_fmt=float_fmt,
                header=header,
                hoja=hoja,
                total_records=total_records,
            )
            with self.engine_sqlite.connect() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
            if self.progress_callback:
                self.progress_callback(
                    f"Finalizada hoja {hoja}", 100, total_records, total_records
                )
            return True
        except Exception as e:
            logging.error(f"Error al procesar la hoja {hoja}: {e}")
            return {
                "success": False,
                "error_message": f"Error al procesar la hoja {hoja}: {e}",
            }

    def _generar_nombre_archivo(self, ext=".zip"):
        self.archivo_plano = f"Interface_Contable_{self.database_name}_de_{self.IdtReporteIni}_a_{self.IdtReporteFin}{ext}"
        self.file_path = os.path.join("media", self.archivo_plano)
        return self.archivo_plano, self.file_path

    def _obtener_lista_hojas(self, config_key):
        hojas_str = self.config.get(config_key, "")
        if isinstance(hojas_str, str):
            try:
                return ast.literal_eval(hojas_str)
            except Exception as e:
                logging.error(f"Error al convertir {config_key} a lista: {e}")
        return []

    def run(self):
        hojas1 = self._obtener_lista_hojas("txProcedureCsv")
        hojas2 = self._obtener_lista_hojas("txProcedureCsv2")
        total_hojas = len(hojas1) if hojas1 else len(hojas2)
        if self.progress_callback:
            self.progress_callback("Iniciando generación de plano", 0)
        if not hojas1 and not hojas2:
            return {"success": False, "error_message": "La empresa no maneja planos"}
        if hojas1:
            result = self._procesar(
                hojas1,
                "nmProcedureCsv",
                sep="|",
                float_fmt="%.2f",
                header=True,
                total_hojas=total_hojas,
            )
        else:
            result = self._procesar(
                hojas2,
                "nmProcedureCsv2",
                sep=",",
                float_fmt="%.0f",
                header=False,
                total_hojas=total_hojas,
            )
        if self.progress_callback:
            self.progress_callback("Plano finalizado", 100)
        return result

    def _procesar(self, hojas, proc_key, sep, float_fmt, header, total_hojas):
        self._generar_nombre_archivo()
        hoja_idx = 0
        with zipfile.ZipFile(self.file_path, "w") as zf:
            for hoja in hojas:
                hoja_idx += 1
                with zf.open(hoja + ".txt", "w") as buffer:
                    result = self._procesar_hoja(
                        hoja, buffer, proc_key, sep, float_fmt, header
                    )
                    if result is not True:
                        return result
                if self.progress_callback:
                    percent = int((hoja_idx / total_hojas) * 100)
                    self.progress_callback(
                        f"Progreso global: {hoja_idx}/{total_hojas} hojas", percent
                    )
        return {
            "success": True,
            "file_path": self.file_path,
            "file_name": self.archivo_plano,
        }
