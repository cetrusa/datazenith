from datetime import datetime
import time
import pandas as pd
import logging
from sqlalchemy import create_engine, text, tuple_
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, Float, String, Date
from scripts.config import ConfigBasic
from scripts.conexion import Conexion as con
import json
from django.core.exceptions import ImproperlyConfigured

# Configuración del logging
logging.basicConfig(
    filename="cargueinfoventas.txt",
    level=logging.DEBUG,
    format="%(asctime)s %(message)s",
    filemode="w",
)
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
logging.info("Iniciando Proceso CargueZip")

def get_secret(secret_name, secrets_file="secret.json"):
    try:
        with open(secrets_file) as f:
            secrets = json.loads(f.read())
        return secrets[secret_name]
    except KeyError:
        raise ImproperlyConfigured(f"La variable {secret_name} no existe")
    except FileNotFoundError:
        raise ImproperlyConfigured(f"No se encontró el archivo de configuración {secrets_file}")

class DataBaseConnection:
    def __init__(self, config):
        print("Inicializando DataBaseConnection")
        self.config = config
        self.engine_mysql_bi = self.create_engine_mysql_bi()
        self.engine_sqlite = create_engine("sqlite:///mydata.db")

    def create_engine_mysql_bi(self):
        print("Creando engine para MySQL BI")
        user = self.config.get("nmUsrIn")
        password = self.config.get("txPassIn")
        host = self.config.get("hostServerIn")
        port = self.config.get("portServerIn")
        database = self.config.get("dbBi")

        if not all([user, password, host, port, database]):
            raise ValueError("Faltan parámetros de configuración para la conexión MySQL BI")

        return con.ConexionMariadb3(
            str(user), str(password), str(host), int(port), str(database)
        )

    def execute_query_mysql_chunked(self, query, table_name, chunksize=50000):
        print(f"Ejecutando consulta en MySQL de manera chunked para la tabla {table_name}")
        try:
            self.eliminar_tabla_sqlite(table_name)
            with self.engine_mysql_bi.connect() as connection:
                cursor = connection.execution_options(isolation_level="READ COMMITTED")
                for chunk in pd.read_sql_query(query, con=cursor, chunksize=chunksize):
                    print(f"Insertando chunk de datos en la tabla {table_name}")
                    chunk.to_sql(
                        name=table_name,
                        con=self.engine_sqlite,
                        if_exists="append",
                        index=False,
                    )
            with self.engine_sqlite.connect() as connection:
                total_records = connection.execute(
                    text(f"SELECT COUNT(*) FROM {table_name}")
                ).fetchone()[0]
            print(f"Total de registros insertados en la tabla {table_name}: {total_records}")
            return total_records

        except Exception as e:
            logging.error(f"Error al ejecutar el query: {e}")
            print(f"Error al ejecutar el query: {e}")
            raise

    def eliminar_tabla_sqlite(self, table_name):
        print(f"Eliminando tabla {table_name} en SQLite")
        sql = text(f"DROP TABLE IF EXISTS {table_name}")
        with self.engine_sqlite.connect() as connection:
            connection.execute(sql)
        print(f"Tabla {table_name} eliminada exitosamente")
        logging.info(f"Tabla {table_name} eliminada exitosamente")

Base = declarative_base()

class FactVentasItems(Base):
    __tablename__ = "fact_ventas_items"
    
    empresa = Column(String(30), primary_key=True)
    tipo_documento = Column(String(30), primary_key=True)
    zona_id = Column(String(30))
    cliente_id = Column(String(30))
    fecha_factura = Column(Date)
    fecha_planilla = Column(Date)
    fecha_cierre_planilla = Column(Date)
    factura_prefijo = Column(String(30), primary_key=True, default=' ')
    factura_id = Column(String(30), primary_key=True)
    planilla_id = Column(String(30))
    pedido_id = Column(String(30))
    ordencompra_id = Column(String(30))
    producto_id = Column(String(10), primary_key=True)
    nro_linea = Column(String(10), primary_key=True)
    bodega_id = Column(String(10), primary_key=True)
    tplinea_id = Column(String(1), primary_key=True)
    virtual_id = Column(String(10))
    cantidad = Column(Float, default=0)
    costo_unitario = Column(Float, default=0)
    vlrbruto = Column(Float, default=0)
    por_iva = Column(Float)
    valor_iva = Column(Float)
    descuentos = Column(Float)
    consumo = Column(Float)
    nota_id = Column(Integer)
    motivo_id = Column(String(10))
    motivo_descripcion = Column(String(50))
    afecta_venta = Column(String(10))
    formapago_id = Column(String(10))
    formapago_nombre = Column(String(50))
    ruta_id = Column(String(10))
    ruta_nombre = Column(String(50))
    placa_vehiculo = Column(String(10))
    transportador_id = Column(String(10))
    transportador_nombre = Column(String(50))
    auxiliar1_id = Column(String(10))
    auxiliar1_nombre = Column(String(50))
    auxiliar2_id = Column(String(10))
    auxiliar2_nombre = Column(String(50))

class TmpInfoVentas(Base):
    __tablename__ = "tmp_infoventas"
    Cod_cliente = Column("Cod. cliente", String(30), primary_key=True, nullable=False)
    Cod_vendedor = Column("Cod. vendedor", String(30), primary_key=True, nullable=False)
    Cod_producto = Column("Cod. productto", String(30), primary_key=True, nullable=False)
    Fecha = Column("Fecha", Date)
    Fac_numero = Column("Fac. numero", String(30), primary_key=True, nullable=False)
    Cantidad = Column("Cantidad", Integer)
    Vta_neta = Column("Vta neta", Float)
    Tipo = Column("Tipo", String(30), primary_key=True, nullable=False)
    Costo = Column("Costo", Float)
    Unidad = Column("Unidad", String(30))
    Pedido = Column("Pedido", String(30))
    Codigo_bodega = Column("Codigo bodega", String(30))
    nbLinea = Column("nbLinea", String(5), primary_key=True, nullable=False, default="1")
    procesado = Column("procesado", Integer, default=0)

class CargueInfoVentas:
    def __init__(self, IdtReporteIni, IdtReporteFin, database_name, user_id=None):
        print(f"Inicializando CargueInfoVentas para las fechas {IdtReporteIni} - {IdtReporteFin}")
        self.IdtReporteIni = IdtReporteIni
        self.IdtReporteFin = IdtReporteFin
        self.database_name = database_name
        self.user_id = user_id
        self.configurar()
        self.empresa = self.obtener_id_empresa()

    def configurar(self):
        print("Configurando CargueInfoVentas")
        try:
            config_basic = ConfigBasic(self.database_name, self.user_id)
            self.config = config_basic.config
            print("Configuración del servidor:")
            print(self.config)
            self.db_connection = DataBaseConnection(config=self.config)
            self.engine_sqlite = self.db_connection.engine_sqlite
            self.engine_mysql_bi = self.db_connection.engine_mysql_bi
        except Exception as e:
            logging.error(f"Error al inicializar Interface: {e}")
            raise

    def obtener_id_empresa(self):
        print("Obteniendo ID de la empresa")
        try:
            with self.engine_mysql_bi.connect() as connection:
                result = connection.execute(text("SELECT id FROM dim_empresa LIMIT 1;"))
                empresa_id = result.scalar()
                logging.debug(f"ID de la empresa obtenida: {empresa_id}")
                return empresa_id
        except OperationalError as e:
            logging.error(f"Error al obtener el ID de la empresa: {e}")
            raise

    def preparar_datos(self, empresa, IdtReporteIni, IdtReporteFin):
        print(f"Preparando datos para la empresa {empresa} en las fechas {IdtReporteIni} - {IdtReporteFin}")
        parametros = {
            "empresa": empresa,
            "IdtReporteIni": IdtReporteIni,
            "IdtReporteFin": IdtReporteFin,
        }
        logging.debug(f"Parámetros de la consulta: {parametros}")
        sqltemporal = text("""
            SELECT 
                :empresa AS empresa, 
                t.`Cod. cliente` AS cliente_id, 
                t.`Cod. vendedor` AS zona_id, 
                t.Fecha AS fecha_factura, 
                t.`Fac. numero` AS factura_id, 
                t.`Cod. productto` AS producto_id, 
                t.`nbLinea` AS nro_linea, 
                t.`Codigo bodega` AS bodega_id, 
                t.`Tipo` AS tplinea_id, 
                NULL AS virtual_id,  
                t.`Cantidad` AS cantidad, 
                t.`Costo` AS costo_unitario, 
                t.`Vta neta` AS vlrbruto,
                '' AS fecha_planilla,
                '' AS fecha_cierre_planilla,
                '' AS planilla_id,
                t.`Pedido` AS pedido_id,
                '' AS ordencompra_id,
                NULL AS por_iva,
                NULL AS valor_iva,
                NULL AS descuentos,
                NULL AS consumo,
                NULL AS nota_id,
                '' AS motivo_id,
                '' AS motivo_descripcion,
                '' AS afecta_venta,
                '' AS formapago_id,
                '' AS formapago_nombre,
                '' AS ruta_id,
                '' AS ruta_nombre,
                '' AS placa_vehiculo,
                '' AS transportador_id,
                '' AS transportador_nombre,
                '' AS auxiliar1_id,
                '' AS auxiliar1_nombre,
                '' AS auxiliar2_id,
                '' AS auxiliar2_nombre
            FROM tmp_infoventas t 
            WHERE t.Fecha BETWEEN :IdtReporteIni AND :IdtReporteFin;
        """)
        try:
            df_temporal = pd.read_sql(sqltemporal, self.engine_mysql_bi, params=parametros)
            print(f"Datos temporales obtenidos: {df_temporal.shape[0]} registros")
            logging.debug(f"Datos temporales obtenidos para {IdtReporteIni} - {IdtReporteFin}: {df_temporal.shape[0]} registros.")
            return df_temporal
        except Exception as e:
            logging.error(f"Error al ejecutar la consulta SQL: {e}")
            print(f"Error al ejecutar la consulta SQL: {e}")
            raise

    def insertar_registros_ignore(self, modelo, data_to_insert):
        print(f"Insertando registros en {modelo.__tablename__}")
        inicio = time.time()
        try:
            with self.engine_mysql_bi.connect() as connection:
                nuevos_registros = self.filtrar_nuevos_registros(modelo, data_to_insert, connection)
                if nuevos_registros:
                    print(f"Insertando {len(nuevos_registros)} nuevos registros en {modelo.__tablename__}")
                    for chunk in self.chunk_data(nuevos_registros, batch_size=50000):
                        chunk_df = pd.DataFrame(chunk)
                        chunk_df.to_sql(
                            name=modelo.__tablename__,
                            con=self.engine_sqlite,
                            if_exists="append",
                            index=False,
                        )
                    logging.info(f"{len(nuevos_registros)} registros insertados en {modelo.__tablename__}.")
                else:
                    logging.info(f"No hay nuevos registros para insertar en {modelo.__tablename__}.")
                    print(f"No hay nuevos registros para insertar en {modelo.__tablename__}.")
        except IntegrityError as e:
            logging.error(f"Error de integridad al insertar registros en {modelo.__tablename__}: {e}")
            print(f"Error de integridad al insertar registros en {modelo.__tablename__}: {e}")
        except SQLAlchemyError as e:
            logging.error(f"Error de SQLAlchemy al insertar registros en {modelo.__tablename__}: {e}")
            print(f"Error de SQLAlchemy al insertar registros en {modelo.__tablename__}: {e}")
        finally:
            fin = time.time()
            tiempo_transcurrido = fin - inicio
            logging.info(f"Tiempo transcurrido en insertar_registros_ignore: {tiempo_transcurrido} segundos.")
            print(f"Tiempo transcurrido en insertar_registros_ignore: {tiempo_transcurrido} segundos.")

    def filtrar_nuevos_registros(self, modelo, data_to_insert, connection):
        print(f"Filtrando nuevos registros para {modelo.__tablename__}")
        inicio = time.time()
        claves_unicas = self.obtener_claves_unicas(modelo)
        todos_nuevos_registros = []

        for batch in self.chunk_data(data_to_insert, batch_size=50000):
            batch = [record for record in batch if all(key in record for key in claves_unicas)]
            if not batch:
                continue

            keys_to_check = [self.construct_key(record, claves_unicas) for record in batch]

            existing_records_query = connection.execute(
                text(f"SELECT * FROM {modelo.__tablename__} WHERE ({', '.join(claves_unicas)}) IN ({', '.join(['%s'] * len(claves_unicas))})"),
                keys_to_check
            ).fetchall()

            existing_records_keys = {self.construct_key(record, claves_unicas) for record in existing_records_query}

            nuevos_registros = [
                record for record in batch
                if self.construct_key(record, claves_unicas) not in existing_records_keys
            ]

            todos_nuevos_registros.extend(nuevos_registros)
        final = time.time()
        tiempo_transcurrido = final - inicio
        logging.info(f"Tiempo transcurrido en filtrar nuevos registros: {tiempo_transcurrido} segundos.")
        print(f"Tiempo transcurrido en filtrar nuevos registros: {tiempo_transcurrido} segundos.")
        return todos_nuevos_registros

    def obtener_claves_unicas(self, modelo):
        return [
            columna.name
            for columna in modelo.__table__.columns
            if columna.primary_key or columna.unique
        ]

    def construct_key(self, record, key_columns):
        if not record:
            raise ValueError("El registro no puede estar vacío.")
        if not key_columns:
            raise ValueError("Debe proporcionar al menos una columna clave.")

        if isinstance(record, dict):
            return tuple(record.get(key) for key in key_columns)
        else:
            return tuple(getattr(record, key, None) for key in key_columns)

    def chunk_data(self, data, batch_size):
        for i in range(0, len(data), batch_size):
            yield data[i : i + batch_size]

    def marcar_registros_como_procesados(self):
        print("Marcando registros como procesados")
        inicio = time.time()
        try:
            with self.engine_mysql_bi.connect() as connection:
                facturas_items_ids = {tuple(row) for row in connection.execute(
                    text("""
                        SELECT 
                            factura_id, 
                            producto_id, 
                            tplinea_id, 
                            nro_linea 
                        FROM fact_ventas_items
                    """)
                ).fetchall()}
                combined_ids = facturas_items_ids

                if combined_ids:
                    connection.execute(
                        text(f"""
                            UPDATE tmp_infoventas
                            SET procesado = 1
                            WHERE ({', '.join(['Fac_numero', 'Cod_producto', 'Tipo', 'nbLinea'])}) IN ({', '.join(['%s'] * 4)})
                        """),
                        combined_ids
                    )
            logging.info("Registros marcados como procesados.")
        except Exception as e:
            logging.error(f"Error al marcar registros como procesados: {e}")
            print(f"Error al marcar registros como procesados: {e}")
        finally:
            final = time.time()
            tiempo_transcurrido = final - inicio
            logging.info(f"Tiempo transcurrido en marcar registros procesados: {tiempo_transcurrido} segundos.")
            print(f"Tiempo transcurrido en marcar registros procesados: {tiempo_transcurrido} segundos.")

    def eliminar_registros_procesados(self):
        print("Eliminando registros procesados")
        inicio = time.time()
        try:
            with self.engine_mysql_bi.connect() as connection:
                connection.execute(
                    text("""
                        DELETE FROM tmp_infoventas
                        WHERE procesado = 1
                    """)
                )
            logging.info("Registros procesados eliminados exitosamente de 'tmp_infoventas'.")
            print("Registros procesados eliminados exitosamente de 'tmp_infoventas'.")
        except Exception as e:
            logging.error(f"Error al eliminar registros procesados: {e}")
            print(f"Error al eliminar registros procesados: {e}")
        finally:
            final = time.time()
            tiempo_transcurrido = final - inicio
            logging.info(f"Tiempo transcurrido en eliminar registros procesados: {tiempo_transcurrido} segundos.")
            print(f"Tiempo transcurrido en eliminar registros procesados: {tiempo_transcurrido} segundos.")

    def procesar_cargue_ventas(self):
        print(f"Procesando cargue de ventas para las fechas {self.IdtReporteIni} - {self.IdtReporteFin}")
        inicio = time.time()
        empresa = self.obtener_id_empresa()

        for fecha in pd.date_range(start=self.IdtReporteIni, end=self.IdtReporteFin):
            fecha_str = fecha.strftime("%Y-%m-%d")
            logging.debug(f"Procesando datos para la fecha: {fecha_str}")
            print(f"Procesando datos para la fecha: {fecha_str}")
            df_temporal = self.preparar_datos(empresa, fecha_str, fecha_str)

            if df_temporal.empty:
                logging.info(f"No hay datos para procesar en la fecha {fecha_str}. Continuando con la siguiente fecha.")
                print(f"No hay datos para procesar en la fecha {fecha_str}. Continuando con la siguiente fecha.")
                continue

            self.insertar_registros_ignore(FactVentasItems, df_temporal.to_dict("records"))

            self.marcar_registros_como_procesados()
            self.eliminar_registros_procesados()

        final = time.time()
        tiempo_transcurrido = final - inicio
        logging.info(f"Tiempo transcurrido en proceso cargue de ventas: {tiempo_transcurrido} segundos.")
        print(f"Tiempo transcurrido en proceso cargue de ventas: {tiempo_transcurrido} segundos.")

