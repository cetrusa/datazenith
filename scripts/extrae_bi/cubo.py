# scripts/extrae_bi/cubo.py

import os
import pandas as pd
from sqlalchemy import create_engine, text
from openpyxl import Workbook
from openpyxl.cell.cell import WriteOnlyCell
import logging
from scripts.StaticPage import StaticPage
from scripts.conexion import Conexion as con
from scripts.config import ConfigBasic
import ast
import xlsxwriter
from apps.home.models import Reporte

# Configuración del logging
logging.basicConfig(
    filename="logCubo.txt",
    level=logging.DEBUG,
    format="%(asctime)s %(message)s",
    filemode="w",
)

class DataBaseConnection:
    """
    Clase para manejar conexiones a bases de datos MySQL y SQLite.

    Atributos:
        config (dict): Configuración para las conexiones a las bases de datos.
        engine_mysql (sqlalchemy.engine.base.Engine): Motor SQLAlchemy para la base de datos MySQL.
        engine_sqlite (sqlalchemy.engine.base.Engine): Motor SQLAlchemy para la base de datos SQLite.
    """

    def __init__(self, config, mysql_engine=None, sqlite_engine=None):
        """
        Inicializa la instancia de DataBaseConnection con la configuración proporcionada.

        Args:
            config (dict): Configuración para las conexiones a las bases de datos.
            mysql_engine (sqlalchemy.engine.base.Engine, opcional): Motor SQLAlchemy para la base de datos MySQL.
            sqlite_engine (sqlalchemy.engine.base.Engine, opcional): Motor SQLAlchemy para la base de datos SQLite.
        """
        self.config = config
        self.engine_mysql = mysql_engine if mysql_engine else self.create_engine_mysql()
        print(f"MySQL engine: {self.engine_mysql}")
        self.engine_sqlite = sqlite_engine if sqlite_engine else create_engine("sqlite:///mydata.db")
        print(f"SQLite engine: {self.engine_sqlite}")

    def create_engine_mysql(self):
        """
        Crea un motor SQLAlchemy para la conexión a la base de datos MySQL.

        Returns:
            sqlalchemy.engine.base.Engine: Motor SQLAlchemy para la base de datos MySQL.
        """
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

    def execute_query_mysql(self, query, chunksize=None):
        """
        Ejecuta una consulta SQL en la base de datos MySQL.

        Args:
            query (str): Consulta SQL a ejecutar.
            chunksize (int, opcional): Tamaño del fragmento para la consulta.

        Returns:
            pd.DataFrame: Resultados de la consulta.
        """
        with self.create_engine_mysql().connect() as connection:
            cursor = connection.execution_options(isolation_level="READ COMMITTED")
            return pd.read_sql_query(query, cursor, chunksize=chunksize)

    def execute_sql_sqlite(self, sql, params=None):
        """
        Ejecuta una consulta SQL en la base de datos SQLite.

        Args:
            sql (str): Consulta SQL a ejecutar.
            params (dict, opcional): Parámetros para la consulta.

        Returns:
            sqlalchemy.engine.ResultProxy: Resultados de la consulta.
        """
        with self.engine_sqlite.connect() as connection:
            return connection.execute(sql, params)

    def execute_query_mysql_chunked(self, query, table_name, chunksize=50000, params=None):
        """
        Ejecuta una consulta SQL en la base de datos MySQL y guarda los resultados en una tabla SQLite en fragmentos.

        Args:
            query (str): Consulta SQL a ejecutar.
            table_name (str): Nombre de la tabla en SQLite donde se almacenarán los resultados.
            chunksize (int, opcional): Tamaño del fragmento para la consulta.
            params (dict, opcional): Parámetros para la consulta.

        Returns:
            int: Número total de registros almacenados en la tabla SQLite.
        """
        try:
            self.eliminar_tabla_sqlite(table_name)
            with self.engine_mysql.connect() as connection:
                cursor = connection.execution_options(isolation_level="READ COMMITTED")
                table_created = False
                for chunk in pd.read_sql_query(query, con=cursor, chunksize=chunksize, params=params):
                    chunk.to_sql(
                        name=table_name,
                        con=self.engine_sqlite,
                        if_exists="append",
                        index=False,
                    )
                    if not table_created:
                        table_created = True
                        print(f"Table {table_name} created successfully")

                if not table_created:
                    raise Exception(f"Table {table_name} was not created")

                with self.engine_sqlite.connect() as connection:
                    total_records = connection.execute(
                        text(f"SELECT COUNT(*) FROM {table_name}")
                    ).fetchone()[0]
                print(f"Total records in {table_name}: {total_records}")
                return total_records

        except Exception as e:
            print(f"Error al ejecutar el query: {e}")
            logging.error(f"Error al ejecutar el query: {e}")
            raise

    def eliminar_tabla_sqlite(self, table_name):
        """
        Elimina una tabla en la base de datos SQLite si existe.

        Args:
            table_name (str): Nombre de la tabla a eliminar.
        """
        sql = text(f"DROP TABLE IF EXISTS {table_name}")
        with self.engine_sqlite.connect() as connection:
            connection.execute(sql)
        print(f"Table {table_name} deleted successfully")

class CuboVentas:
    """
    Clase para manejar el proceso de creación de cubos de ventas.

    Atributos:
        database_name (str): Nombre de la base de datos.
        IdtReporteIni (str): Fecha de inicio del reporte.
        IdtReporteFin (str): Fecha de fin del reporte.
        user_id (int): ID del usuario.
        reporte_id (int): ID del reporte.
        config (dict): Configuración para las conexiones a las bases de datos.
        proveedores (list): Lista de proveedores.
        macrozonas (list): Lista de macrozonas.
        db_connection (DataBaseConnection): Objeto de conexión a bases de datos.
        engine_sqlite (sqlalchemy.engine.base.Engine): Motor SQLAlchemy para la base de datos SQLite.
        engine_mysql (sqlalchemy.engine.base.Engine): Motor SQLAlchemy para la base de datos MySQL.
        file_path (str): Ruta del archivo generado.
        archivo_cubo_ventas (str): Nombre del archivo generado.
    """

    def __init__(self, database_name, IdtReporteIni, IdtReporteFin, user_id, reporte_id):
        """
        Inicializa la instancia de CuboVentas.

        Args:
            database_name (str): Nombre de la base de datos.
            IdtReporteIni (str): Fecha de inicio del reporte.
            IdtReporteFin (str): Fecha de fin del reporte.
            user_id (int): ID del usuario.
            reporte_id (int): ID del reporte.
        """
        self.database_name = database_name
        self.IdtReporteIni = IdtReporteIni
        self.IdtReporteFin = IdtReporteFin
        self.user_id = user_id  # ID del usuario
        self.reporte_id = reporte_id  # ID del reporte para Cubo de Ventas
        self.configurar(database_name, user_id)
        
        self.file_path = None
        self.archivo_cubo_ventas = None

    def configurar(self, database_name, user_id):
        """
        Configura las conexiones a las bases de datos y establece las variables de entorno necesarias.

        Args:
            database_name (str): Nombre de la base de datos.
            user_id (int): ID del usuario.

        Raises:
            Exception: Propaga cualquier excepción que ocurra durante la configuración.
        """
        try:
            config_basic = ConfigBasic(database_name, user_id)
            self.config = config_basic.config
            self.proveedores = self.config.get('proveedores', [])
            self.macrozonas = self.config.get('macrozonas', [])
            self.db_connection = DataBaseConnection(config=self.config)
            self.engine_sqlite = self.db_connection.engine_sqlite
            self.engine_mysql = self.db_connection.engine_mysql
        except Exception as e:
            print(f"Error al inicializar CuboVentas: {e}")
            logging.error(f"Error al inicializar CuboVentas: {e}")
            raise

    def generate_sqlout(self):
        """
        Genera la consulta SQL para obtener los datos del reporte.

        Returns:
            sqlalchemy.sql.elements.TextClause: Consulta SQL generada.

        Raises:
            ValueError: Si no se encuentra el reporte con el ID especificado.
        """
        try:
            reporte = Reporte.objects.get(pk=self.reporte_id)
            base_sql = reporte.sql_text
            
            if self.config.get('proveedores'):
                proveedores_list = ', '.join(map(lambda x: f"'{x}'", self.config['proveedores']))
                base_sql += f" AND idProveedor IN ({proveedores_list})"
            if self.config.get('macrozonas'):
                macrozonas_list = ', '.join(map(lambda x: f"'{x}'", self.config['macrozonas']))
                base_sql += f" AND macrozona_id IN ({macrozonas_list})"
            
            base_sql += ";"
            print(f"Generated SQL: {base_sql}")
            logging.debug(f"Generated SQL: {base_sql}")
            
            return text(base_sql)
        except Reporte.DoesNotExist:
            print(f"Reporte con ID {self.reporte_id} no encontrado")
            logging.error(f"Reporte con ID {self.reporte_id} no encontrado")
            raise ValueError(f"Reporte con ID {self.reporte_id} no encontrado")
        
    def guardar_datos(self, table_name, file_path, hoja, total_records, wb):
        """
        Guarda los datos en un archivo según el número total de registros.

        Args:
            table_name (str): Nombre de la tabla en SQLite donde se almacenan los datos.
            file_path (str): Ruta del archivo generado.
            hoja (str): Nombre de la hoja en el archivo.
            total_records (int): Número total de registros en la tabla.
            wb (openpyxl.Workbook): Libro de trabajo de Excel.
        """
        if total_records > 1000000:
            self.guardar_datos_csv(table_name, file_path)
        elif total_records > 250000:
            self.guardar_datos_excel_xlsxwriter2(table_name, hoja, wb)
        else:
            self.guardar_datos_excel_xlsxwriter2(table_name, hoja, wb)

    def generar_nombre_archivo(self, hoja, ext=".xlsx"):
        """
        Genera el nombre del archivo y la ruta para guardar los datos.

        Args:
            hoja (str): Nombre de la hoja en el archivo.
            ext (str, opcional): Extensión del archivo. Por defecto es ".xlsx".

        Returns:
            tuple: Nombre del archivo y ruta del archivo.
        """
        self.archivo_cubo_ventas = f"{hoja}_{self.database_name.upper()}_de_{self.IdtReporteIni}_a_{self.IdtReporteFin}_user_{self.user_id}{ext}"
        self.file_path = os.path.join("media", self.archivo_cubo_ventas)
        print(f"Generated file path: {self.file_path}")
        logging.debug(f"Generated file path: {self.file_path}")
        return self.archivo_cubo_ventas, self.file_path

    def guardar_datos_csv(self, table_name, file_path):
        """
        Guarda los datos en un archivo CSV.

        Args:
            table_name (str): Nombre de la tabla en SQLite donde se almacenan los datos.
            file_path (str): Ruta del archivo CSV generado.
        """
        chunksize = 50000  # Define el tamaño de cada bloque de datos

        with self.engine_sqlite.connect() as connection:
            for chunk in pd.read_sql_query(
                f"SELECT * FROM {table_name}", self.engine_sqlite, chunksize=chunksize
            ):
                chunk.to_csv(file_path, mode="a", index=False)
        print(f"CSV file {file_path} generated successfully")
        logging.debug(f"CSV file {file_path} generated successfully")

    def guardar_datos_excel_xlsxwriter(self, table_name, file_path, hoja):
        """
        Guarda los datos en un archivo Excel usando xlsxwriter.

        Args:
            table_name (str): Nombre de la tabla en SQLite donde se almacenan los datos.
            file_path (str): Ruta del archivo Excel generado.
            hoja (str): Nombre de la hoja en el archivo.
        """
        chunksize = 50000

        with pd.ExcelWriter(file_path, engine="xlsxwriter") as writer:
            with self.engine_sqlite.connect() as connection:
                startrow = 0
                for chunk in pd.read_sql_query(
                    f"SELECT * FROM {table_name}",
                    self.engine_sqlite,
                    chunksize=chunksize,
                ):
                    print(f"Processing chunk of size: {len(chunk)}")
                    logging.debug(f"Processing chunk of size: {len(chunk)}")
                    chunk.to_excel(
                        writer,
                        sheet_name=hoja,
                        startrow=startrow,
                        index=False,
                        header=not bool(startrow),
                    )
                    startrow += len(chunk)
                    print(f"Next startrow: {startrow}")
                    logging.debug(f"Next startrow: {startrow}")

    def guardar_datos_excel_xlsxwriter2(self, table_name, hoja, wb):
        """
        Guarda los datos en un archivo Excel usando openpyxl.

        Args:
            table_name (str): Nombre de la tabla en SQLite donde se almacenan los datos.
            hoja (str): Nombre de la hoja en el archivo.
            wb (openpyxl.Workbook): Libro de trabajo de Excel.
        """
        chunksize = 50000

        ws = wb.create_sheet(title=hoja)

        headers = pd.read_sql_query(
            f"SELECT * FROM {table_name} LIMIT 0", self.engine_sqlite
        ).columns.tolist()
        ws.append(headers)

        for chunk in pd.read_sql_query(
            f"SELECT * FROM {table_name}", self.engine_sqlite, chunksize=chunksize
        ):
            for index, row in chunk.iterrows():
                cells = [WriteOnlyCell(ws, value=value) for value in row]
                ws.append(cells)

    def guardar_datos_excel_openpyxl(self, table_name, file_path, hoja):
        """
        Guarda los datos en un archivo Excel completo usando openpyxl.

        Args:
            table_name (str): Nombre de la tabla en SQLite donde se almacenan los datos.
            file_path (str): Ruta del archivo Excel generado.
            hoja (str): Nombre de la hoja en el archivo.
        """
        chunksize = 50000

        wb = Workbook(write_only=True)
        ws = wb.create_sheet(title=hoja)

        with self.engine_sqlite.connect() as connection:
            first_chunk = True
            for chunk in pd.read_sql_table(
                table_name, con=connection, chunksize=chunksize
            ):
                if first_chunk:
                    ws.append(chunk.columns.tolist())
                    first_chunk = False

                for row in chunk.itertuples(index=False, name=None):
                    ws.append(row)

        wb.save(file_path)
        print(f"Excel file {file_path} generated successfully")
        logging.debug(f"Excel file {file_path} generated successfully")

    def guardar_datos_excel_completo(self, table_name, file_path, hoja):
        """
        Guarda todos los datos en un archivo Excel completo.

        Args:
            table_name (str): Nombre de la tabla en SQLite donde se almacenan los datos.
            file_path (str): Ruta del archivo Excel generado.
            hoja (str): Nombre de la hoja en el archivo.
        """
        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            with self.engine_sqlite.connect() as connection:
                df = pd.read_sql_table(table_name, con=connection)
                df.to_excel(writer, index=False, sheet_name=hoja)

    def procesar_hoja(self, hoja, wb):
        """
        Procesa los datos para una hoja específica.

        Args:
            hoja (str): Nombre de la hoja a procesar.
            wb (openpyxl.Workbook): Libro de trabajo de Excel.

        Returns:
            dict or bool: Diccionario con información de éxito o False si ocurre un error.
        """
        try:
            sqlout = self.generate_sqlout()
            print(f"SQL Output: {sqlout}")
            logging.debug(f"SQL Output: {sqlout}")
            table_name = f"my_table_{self.database_name}_{self.user_id}_{hoja}"
            params = {"fi": self.IdtReporteIni, "ff": self.IdtReporteFin, "empresa": self.database_name.upper()}
            total_records = self.db_connection.execute_query_mysql_chunked(
                query=sqlout, table_name=table_name, params=params
            )

            print(f"Total records in {table_name}: {total_records}")
            logging.debug(f"Total records in {table_name}: {total_records}")

            archivo_cubo_ventas, file_path = self.generar_nombre_archivo(
                hoja, ext=".csv" if total_records > 1000000 else ".xlsx"
            )
            print(f"Generated file path: {file_path}")
            logging.debug(f"Generated file path: {file_path}")
            self.guardar_datos(table_name, file_path, hoja, total_records, wb)
            print(f"File {archivo_cubo_ventas} generated successfully")
            logging.debug(f"File {archivo_cubo_ventas} generated successfully")

            print(f"Processing of sheet {hoja} completed")
            logging.debug(f"Processing of sheet {hoja} completed")
            return True
        except Exception as e:
            print(f"Error processing sheet {hoja}: {e}")
            logging.error(f"Error processing sheet {hoja}: {e}")
            return {
                "success": False,
                "error_message": f"Error processing sheet {hoja}: {e}",
            }

    def procesar_datos(self):
        """
        Procesa los datos para el cubo de ventas y guarda los resultados en un archivo.

        Returns:
            dict: Diccionario con información de éxito o error.
        """
        wb = Workbook(write_only=True)
        reporte = Reporte.objects.get(pk=self.reporte_id)
        hoja = reporte.nombre
        print(f"Processing sheet {hoja}")
        logging.debug(f"Processing sheet {hoja}")
        if not self.procesar_hoja(hoja, wb):
            return {
                "success": False,
                "error_message": f"Error processing sheet {hoja}",
            }
        wb.save(self.file_path)
        print(f"Process completed")
        logging.debug(f"Process completed")
        return {
            "success": True,
            "file_path": self.file_path,
            "file_name": self.archivo_cubo_ventas,
        }

    def get_data(self):
        """
        Obtiene los datos procesados del cubo de ventas.

        Returns:
            dict: Diccionario con encabezados y filas de los datos.
        """
        reporte = Reporte.objects.get(pk=self.reporte_id)
        table_name = f"my_table_{self.database_name}_{self.user_id}_{reporte.nombre}"
        with self.engine_sqlite.connect() as connection:
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", connection)
            headers = df.columns.tolist()
            rows = df.values.tolist()
        print(f"Data fetched from {table_name}")
        logging.debug(f"Data fetched from {table_name}")
        # Eliminar la tabla después de obtener los datos
        self.db_connection.eliminar_tabla_sqlite(table_name)
        logging.info(f"Tabla {table_name} eliminada después de obtener los datos")
        return {
            "headers": headers,
            "rows": rows
        }
