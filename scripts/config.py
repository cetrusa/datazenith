# scripts/config.py

import os
import json
import pandas as pd
import logging
import time
from sqlalchemy.sql import text
from scripts.conexion import Conexion as con

# Configuración del logging
logging.basicConfig(
    filename="log.txt",
    level=logging.DEBUG,
    format="%(asctime)s %(message)s",
    filemode="w",
)
logging.info("Iniciando Proceso")


def get_secret(secret_name, secrets_file="secret.json"):
    """
    Obtiene un secreto del archivo de configuración.

    Args:
        secret_name (str): Nombre del secreto a obtener.
        secrets_file (str): Ruta del archivo de secretos.

    Returns:
        str: Valor del secreto.

    Raises:
        ValueError: Si el secreto no existe o no se encuentra el archivo.
    """
    try:
        with open(secrets_file) as f:
            secrets = json.loads(f.read())
        return secrets[secret_name]
    except KeyError:
        raise ValueError(f"La variable {secret_name} no existe.")
    except FileNotFoundError:
        raise ValueError(f"No se encontró el archivo de configuración {secrets_file}.")


class ConfigBasic:
    # Cache para almacenar configuraciones por base de datos y usuario
    _config_cache = {}
    _cache_timeout = 300  # 5 minutos en segundos
    _last_cache_time = {}

    def __init__(self, database_name, user_id=None):
        """
        Inicializa la configuración básica.

        Args:
            database_name (str): Nombre de la base de datos.
            user_id (int, optional): ID del usuario. Por defecto es None.
        """
        self.start_time = time.time()
        logging.debug(
            f"Iniciando ConfigBasic para database: {database_name}, user: {user_id}"
        )

        self.config = {}  # Diccionario para almacenar la configuración
        self.user_id = user_id  # ID del usuario
        self.database_name = database_name

        # Crear clave de caché única para esta combinación de base de datos y usuario
        cache_key = f"{database_name}_{user_id}"

        # Verificar si los datos están en caché y no han expirado
        current_time = time.time()
        if (
            cache_key in self._config_cache
            and (current_time - self._last_cache_time.get(cache_key, 0))
            < self._cache_timeout
        ):
            logging.debug(f"Usando configuración en caché para {cache_key}")
            self.config = self._config_cache[cache_key]
            logging.debug(
                f"ConfigBasic inicializada desde caché en {time.time() - self.start_time:.4f}s"
            )
            return

        try:
            self.setup_static_page(database_name)
            if self.user_id is not None:
                self.setup_user_permissions()
            else:
                logging.info("Omitiendo configuración de permisos de usuario")

            # Guardar en caché
            self._config_cache[cache_key] = self.config.copy()
            self._last_cache_time[cache_key] = current_time
            logging.debug(f"Configuración guardada en caché para {cache_key}")

        except json.JSONDecodeError as e:
            logging.error(f"Error al decodificar JSON: {e}")
        except KeyError as e:
            logging.error(f"Clave no encontrada en el archivo de configuración: {e}")
        except FileNotFoundError as e:
            logging.error(f"Archivo no encontrado: {e}")
        except pd.errors.EmptyDataError as e:
            logging.error(f"No se encontraron datos en la consulta SQL: {e}")
        except IndexError as e:
            logging.error(f"Índice fuera de rango en el DataFrame: {e}")
        except Exception as e:
            logging.error(f"Error desconocido en ConfigBasic: {e}")

        logging.debug(
            f"ConfigBasic inicializada en {time.time() - self.start_time:.4f}s"
        )

    @classmethod
    def clear_cache(cls, database_name=None, user_id=None):
        """
        Limpia la caché de configuración.

        Args:
            database_name (str, optional): Si se proporciona, solo se limpia la caché para esta base de datos
            user_id (int, optional): Si se proporciona, solo se limpia la caché para este usuario
        """
        if database_name and user_id:
            # Limpiar caché específica
            cache_key = f"{database_name}_{user_id}"
            if cache_key in cls._config_cache:
                del cls._config_cache[cache_key]
                if cache_key in cls._last_cache_time:
                    del cls._last_cache_time[cache_key]
                logging.debug(f"Caché limpiada para {cache_key}")
        elif database_name:
            # Limpiar caché para toda la base de datos
            keys_to_delete = [
                k for k in cls._config_cache if k.startswith(f"{database_name}_")
            ]
            for key in keys_to_delete:
                del cls._config_cache[key]
                if key in cls._last_cache_time:
                    del cls._last_cache_time[key]
            logging.debug(f"Caché limpiada para database: {database_name}")
        else:
            # Limpiar toda la caché
            cls._config_cache.clear()
            cls._last_cache_time.clear()
            logging.debug("Caché de configuración limpiada completamente")

    def setup_static_page(self, database_name):
        """
        Configura la página estática con la información de la base de datos.

        Args:
            database_name (str): Nombre de la base de datos.
        """
        start_time = time.time()
        self.config["name"] = str(database_name)
        self.config["dir_actual"] = str("puente1dia")
        self.config["nmDt"] = self.config["dir_actual"]
        logging.debug(f"Configurando para la base de datos: {self.config['name']}")

        self.fetch_database_config()
        self.setup_date_config()
        self.setup_server_config()
        self.powerbi_config()
        logging.debug(
            f"setup_static_page completado en {time.time() - start_time:.4f}s"
        )

    def setup_user_permissions(self):
        """
        Configura los permisos del usuario basado en Django.
        """
        start_time = time.time()
        try:
            import ast
            from django.contrib.auth import get_user_model
            from apps.users.models import UserPermission

            User = get_user_model()

            # Consulta eficiente usando select_related
            permissions = (
                UserPermission.objects.filter(
                    user_id=self.user_id, empresa__name=self.config["name"]
                )
                .select_related("empresa")
                .first()
            )

            if permissions:
                self.config["proveedores"] = (
                    ast.literal_eval(permissions.proveedores)
                    if permissions.proveedores
                    else []
                )
                self.config["macrozonas"] = (
                    ast.literal_eval(permissions.macrozonas)
                    if permissions.macrozonas
                    else []
                )
            else:
                self.config["proveedores"] = []
                self.config["macrozonas"] = []

            logging.debug(
                f"Permisos cargados: {len(self.config.get('proveedores', []))} proveedores, {len(self.config.get('macrozonas', []))} macrozonas"
            )

        except Exception as e:
            logging.error(f"Error al configurar los permisos de usuario: {e}")
            self.config["proveedores"] = []
            self.config["macrozonas"] = []

        logging.debug(
            f"setup_user_permissions completado en {time.time() - start_time:.4f}s"
        )

    # Caché para la conexión a BD
    _db_connection = None
    _db_connection_timestamp = 0
    _db_connection_timeout = 60  # 1 minuto para reutilizar conexión

    def get_db_connection(self):
        """
        Obtiene una conexión a la base de datos, reutilizándola si es posible.

        Returns:
            Connection: Objeto de conexión a la base de datos.
        """
        current_time = time.time()

        # Si no hay conexión o ha expirado, crear nueva
        if (
            ConfigBasic._db_connection is None
            or (current_time - ConfigBasic._db_connection_timestamp)
            > ConfigBasic._db_connection_timeout
        ):

            logging.debug("Creando nueva conexión a la base de datos")
            ConfigBasic._db_connection = con.ConexionMariadb3(
                get_secret("DB_USERNAME"),
                get_secret("DB_PASS"),
                get_secret("DB_HOST"),
                int(get_secret("DB_PORT")),
                get_secret("DB_NAME"),
            )
            ConfigBasic._db_connection_timestamp = current_time

        return ConfigBasic._db_connection

    def execute_sql_query(self, sql_query, params=None):
        """
        Ejecuta una consulta SQL.

        Args:
            sql_query (str): Consulta SQL a ejecutar.
            params (dict, optional): Parámetros para la consulta

        Returns:
            DataFrame: Resultados de la consulta SQL.
        """
        start_time = time.time()

        # Crear clave de caché para la consulta
        cache_key = f"{sql_query}_{str(params)}" if params else sql_query
        cache_key = str(cache_key).replace(" ", "")[:100]  # Limitar tamaño de clave

        if hasattr(self, "_query_cache") and cache_key in self._query_cache:
            logging.debug(f"Resultado de consulta obtenido de caché: {cache_key}")
            return self._query_cache[cache_key]

        if not hasattr(self, "_query_cache"):
            self._query_cache = {}

        try:
            conectando = self.get_db_connection()
            with conectando.connect() as connection:
                cursor = connection.execution_options(isolation_level="READ COMMITTED")
                result = pd.read_sql_query(sql=sql_query, con=cursor, params=params)

                if result.empty:
                    logging.warning(f"Consulta SQL no devolvió datos: {sql_query}")

                # Guardar en caché el resultado
                self._query_cache[cache_key] = result
                logging.debug(
                    f"execute_sql_query completado en {time.time() - start_time:.4f}s"
                )
                return result

        except Exception as e:
            logging.error(f"Error al ejecutar consulta SQL: {sql_query}, Error: {e}")
            return pd.DataFrame()

    # Resto de métodos, solo actualizando con medición de tiempo

    def fetch_database_config(self):
        start_time = time.time()
        sql = f"SELECT * FROM powerbi_adm.conf_empresas WHERE name = '{self.config['name']}';"
        df = self.execute_sql_query(sql)
        if not df.empty:
            self.assign_static_page_attributes(df)
        logging.debug(
            f"fetch_database_config completado en {time.time() - start_time:.4f}s"
        )

    def assign_static_page_attributes(self, df):
        """
        Asigna atributos estáticos desde el DataFrame de configuración de la base de datos.

        Args:
            df (DataFrame): DataFrame con la configuración de la base de datos.
        """
        for field in [
            "id",
            "nmEmpresa",
            "name",
            "nbServerSidis",
            "dbSidis",
            "nbServerBi",
            "dbBi",
            "txProcedureExtrae",
            "txProcedureCargue",
            "nmProcedureExcel",
            "txProcedureExcel",
            "nmProcedureInterface",
            "txProcedureInterface",
            "nmProcedureExcel2",
            "txProcedureExcel2",
            "nmProcedureCsv",
            "txProcedureCsv",
            "nmProcedureCsv2",
            "txProcedureCsv2",
            "nmProcedureSql",
            "txProcedureSql",
            "group_id_powerbi",
            "report_id_powerbi",
            "dataset_id_powerbi",
            "url_powerbi",
            "id_tsol",
        ]:
            if field in df:
                value = df[field].values[0] if not df[field].empty else None
                self.config[field] = value
            else:
                logging.warning(
                    f"Campo {field} no encontrado en los resultados para {self.config['name']}"
                )

    def powerbi_config(self):
        start_time = time.time()
        sql = text("SELECT * FROM powerbi_adm.conf_tipo WHERE nbTipo = '3';")
        df = self.execute_sql_query(sql)
        if not df.empty:
            self.config["nmUsrPowerbi"] = str(df["nmUsr"].values[0])
            self.config["txPassPowerbi"] = str(df["txPass"].values[0])
        logging.debug(f"powerbi_config completado en {time.time() - start_time:.4f}s")

    def correo_config(self):
        """
        Configura la información del correo.
        """
        sql = text("SELECT * FROM powerbi_adm.conf_tipo WHERE nbTipo = '11';")
        df = self.execute_sql_query(sql)
        if not df.empty:
            self.config["nmUsrCorreo"] = df["nmUsr"].iloc[0]
            self.config["txPassCorreo"] = df["txPass"].iloc[0]
        else:
            print("No se encontraron configuraciones de Correo.")

    def setup_date_config(self):
        start_time = time.time()
        date_config = self.fetch_date_config(self.config["nmDt"])
        if not date_config:
            date_config = self.fetch_date_config(str("puente1dia"))

        self.config.update(date_config)
        logging.debug(
            f"setup_date_config completado en {time.time() - start_time:.4f}s"
        )

    def fetch_date_config(self, nmDt):
        """
        Obtiene la configuración de fechas desde la base de datos.

        Args:
            nmDt (str): Nombre de la fecha de configuración.

        Returns:
            dict: Configuración de fechas.
        """
        sql = f"SELECT * FROM powerbi_adm.conf_dt WHERE nmDt = '{nmDt}';"
        df = self.execute_sql_query(sql)
        if not df.empty:
            txDtIni = str(df["txDtIni"].values[0])
            txDtFin = str(df["txDtFin"].values[0])

            report_date_df_ini = self.execute_sql_query(txDtIni)
            report_date_df_fin = self.execute_sql_query(txDtFin)
            if not report_date_df_ini.empty and not report_date_df_fin.empty:
                return {
                    "IdtReporteIni": str(report_date_df_ini["IdtReporteIni"].values[0]),
                    "IdtReporteFin": str(report_date_df_fin["IdtReporteFin"].values[0]),
                }
        return None

    def setup_server_config(self):
        start_time = time.time()
        self.assign_server_config(self.config.get("nbServerSidis"), "Out")
        self.assign_server_config(self.config.get("nbServerBi"), "In")
        logging.debug(
            f"setup_server_config completado en {time.time() - start_time:.4f}s"
        )

    def assign_server_config(self, server_id, suffix):
        """
        Asigna la configuración del servidor.

        Args:
            server_name (str): Nombre del servidor.
            suffix (str): Sufijo para la configuración del servidor (Out o In).
        """
        if not server_id:
            print(
                f"{suffix} está vacío o nulo, omitiendo configuración del servidor {suffix}."
            )
            return

        print("Configurando servidor:", server_id)
        server_sql = (
            f"SELECT * FROM powerbi_adm.conf_server WHERE nbServer = {server_id};"
        )
        server_df = self.execute_sql_query(server_sql)

        if not server_df.empty:
            tipo_df = self.execute_sql_query(
                f"SELECT * FROM powerbi_adm.conf_tipo WHERE nbTipo = '{server_df['nbTipo'].values[0]}';"
            )

            if not tipo_df.empty:
                self.config[f"hostServer{suffix}"] = server_df["hostServer"].values[0]
                self.config[f"portServer{suffix}"] = server_df["portServer"].values[0]
                self.config[f"nmUsr{suffix}"] = tipo_df["nmUsr"].values[0]
                self.config[f"txPass{suffix}"] = tipo_df["txPass"].values[0]
                print(
                    f"Configuración del servidor {suffix} actualizada en el diccionario de configuración."
                )
            else:
                print(
                    f"No se encontraron datos para el tipo de servidor {server_df['nbTipo'].values[0]}"
                )
        else:
            print(f"No se encontraron datos para el servidor {server_name}")

        logging.info(f"Configuración del servidor {suffix}: {self.config}")

    def print_configuration(self):
        """
        Imprime la configuración actual.
        """
        print("Configuración Actual:")
        for key, value in self.config.items():
            print(f"{key}: {value}")


# Ejemplo de uso
# try:
#     config = ConfigBasic("nombre_base_datos", user_id)
# except ImproperlyConfigured as e:
#     logging.error(f"Error de configuración: {e}")
