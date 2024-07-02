import os
import sys
from scripts.conexion import Conexion as con
import json
import pandas as pd
import ast
from sqlalchemy.sql import text
import logging
from django.contrib.auth import get_user_model
from apps.users.models import UserPermission

logging.basicConfig(
    filename="log.txt",
    level=logging.DEBUG,
    format="%(asctime)s %(message)s",
    filemode="w",
)
logging.info("Iniciando Proceso")

def get_secret(secret_name, secrets_file="secret.json"):
    try:
        with open(secrets_file) as f:
            secrets = json.loads(f.read())
        return secrets[secret_name]
    except KeyError:
        raise ValueError(f"La variable {secret_name} no existe.")
    except FileNotFoundError:
        raise ValueError(f"No se encontró el archivo de configuración {secrets_file}.")

class ConfigBasic:
    def __init__(self, database_name, user_id=None):
        print("aqui estoy en la clase de config")
        self.config = {}  # Diccionario para almacenar la configuración
        self.user_id = user_id  # ID del usuario
        try:
            self.setup_static_page(database_name)
            if self.user_id is not None:
                self.setup_user_permissions()
            else:
                logging.info("user_id is None, skipping user permissions setup")
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

    def setup_static_page(self, database_name):
        self.config["name"] = str(database_name)
        self.config["dir_actual"] = str("puente1dia")
        self.config["nmDt"] = self.config["dir_actual"]
        logging.info(f"Configurando para la base de datos: {self.config['name']}")

        self.fetch_database_config()
        self.setup_date_config()
        self.setup_server_config()
        self.powerbi_config()
        print("terminamos de configurar")

    def setup_user_permissions(self):
        try:
            User = get_user_model()
            user = User.objects.get(id=self.user_id)
            permissions = UserPermission.objects.filter(user=user, empresa__name=self.config["name"])

            if permissions.exists():
                permission = permissions.first()
                self.config["proveedores"] = ast.literal_eval(permission.proveedores) if permission.proveedores else []
                self.config["macrozonas"] = ast.literal_eval(permission.macrozonas) if permission.macrozonas else []
            else:
                self.config["proveedores"] = []
                self.config["macrozonas"] = []
        except User.DoesNotExist:
            logging.error(f"El usuario con id {self.user_id} no existe")
        except Exception as e:
            logging.error(f"Error al configurar los permisos de usuario: {e}")

    def execute_sql_query(self, sql_query):
        try:
            conectando = con.ConexionMariadb3(
                get_secret("DB_USERNAME"),
                get_secret("DB_PASS"),
                get_secret("DB_HOST"),
                int(get_secret("DB_PORT")),
                get_secret("DB_NAME"),
            )
            with conectando.connect() as connection:
                cursor = connection.execution_options(isolation_level="READ COMMITTED")
                result = pd.read_sql_query(sql=sql_query, con=cursor)
                if result.empty:
                    logging.warning(f"Consulta SQL no devolvió datos: {sql_query}")
                return result
        except Exception as e:
            logging.error(f"Error al ejecutar consulta SQL: {sql_query}, Error: {e}")
            return pd.DataFrame()

    def fetch_database_config(self):
        print(
            "aqui estoy en la clase de config en la configuración de la base de datos"
        )
        sql = f"SELECT * FROM powerbi_adm.conf_empresas WHERE name = '{self.config['name']}';"
        df = self.execute_sql_query(sql)
        if not df.empty:
            self.assign_static_page_attributes(df)

    def assign_static_page_attributes(self, df):
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
            "report_id_powerbi",
            "dataset_id_powerbi",
            "url_powerbi",
            "id_tsol",
        ]:  # Lista de campos a configurar
            if field in df:
                value = df[field].values[0] if not df[field].empty else None
                self.config[field] = value  # Asignar al diccionario
                # print(f"{field}: {self.config[field]}")
            else:
                logging.warning(
                    f"Campo {field} no encontrado en los resultados para {self.config['name']}"
                )

    def powerbi_config(self):
        sql = text("SELECT * FROM powerbi_adm.conf_tipo WHERE nbTipo = '3';")
        df = self.execute_sql_query(sql)
        if not df.empty:
            self.config["nmUsrPowerbi"] = str(df["nmUsr"].values[0])
            self.config["txPassPowerbi"] = str(df["txPass"].values[0])
        else:
            print("No se encontraron configuraciones de PowerBI.")

    def correo_config(self):
        sql = text("SELECT * FROM powerbi_adm.conf_tipo WHERE nbTipo = '6';")
        df = self.execute_sql_query(sql)
        if not df.empty:
            self.config["nmUsrCorreo"] = df["nmUsr"].iloc[0]
            self.config["txPassCorreo"] = df["txPass"].iloc[0]
        else:
            print("No se encontraron configuraciones de Correo.")

    def setup_date_config(self):
        date_config = self.fetch_date_config(self.config["nmDt"])
        if not date_config:
            date_config = self.fetch_date_config(str("puente1dia"))  # Valor por defecto

        # Actualiza el diccionario de configuración con los valores de date_config
        self.config.update(date_config)

    def fetch_date_config(self, nmDt):
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
        # Extraer y configurar la información del servidor
        self.assign_server_config(self.config["nbServerSidis"], "Out")
        self.assign_server_config(self.config["nbServerBi"], "In")

    def assign_server_config(self, server_name, suffix):
        print("Configurando servidor:", server_name)

        # Consulta para obtener la configuración del servidor
        server_sql = (
            f"SELECT * FROM powerbi_adm.conf_server WHERE nbServer = '{server_name}';"
        )
        server_df = self.execute_sql_query(server_sql)

        if not server_df.empty:
            # Consulta para obtener la configuración del tipo de servidor
            tipo_df = self.execute_sql_query(
                f"SELECT * FROM powerbi_adm.conf_tipo WHERE nbTipo = '{server_df['nbTipo'].values[0]}';"
            )

            if not tipo_df.empty:
                # Actualizar el diccionario de configuración
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

    def print_configuration(self):
        print("Configuración Actual:")
        for key, value in self.config.items():
            print(f"{key}: {value}")

# Ejemplo de uso
# try:
#     config = ConfigBasic("nombre_base_datos", user_id)
# except ImproperlyConfigured as e:
#     logging.error(f"Error de configuración: {e}")
