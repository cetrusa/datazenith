import sys
import time
import logging
import sqlalchemy
import pymysql
from sqlalchemy.pool import QueuePool
from threading import Lock


class Conexion:
    """
    Clase para gestionar conexiones a bases de datos con optimizaciones de rendimiento.
    Implementa un pool de conexiones y caché para mejorar el tiempo de respuesta.
    """

    # Caché de conexiones para reutilizar engines entre llamadas
    _connection_cache = {}
    _cache_timeout = 1800  # 30 minutos en segundos
    _last_connection_time = {}
    _cache_lock = Lock()  # Lock para operaciones thread-safe en la caché

    @staticmethod
    def ConexionMariadb3(user, password, host, port, database):
        """
        Crea una conexión optimizada a MariaDB/MySQL con pool de conexiones.

        Args:
            user (str): Nombre de usuario para la conexión.
            password (str): Contraseña del usuario.
            host (str): Host donde se encuentra la base de datos.
            port (int): Puerto para la conexión.
            database (str): Nombre de la base de datos.

        Returns:
            Engine: Objeto Engine de SQLAlchemy para ejecutar consultas.
        """
        import os
        # Permitir configuración dinámica por variables de entorno
        pool_size = int(os.getenv("DB_POOL_SIZE", 20))
        max_overflow = int(os.getenv("DB_MAX_OVERFLOW", 25))
        pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", 120))
        pool_recycle = int(os.getenv("DB_POOL_RECYCLE", 3600))
        read_timeout_env = int(os.getenv("DB_READ_TIMEOUT", 300))
        write_timeout_env = int(os.getenv("DB_WRITE_TIMEOUT", 300))

        # Crear una clave única para esta conexión
        connection_key = f"{user}@{host}:{port}/{database}"
        current_time = time.time()

        # Usar lock para asegurar que no haya conflictos de escritura en la caché
        with Conexion._cache_lock:
            # Verificar si ya existe una conexión en caché y no ha expirado
            if (
                connection_key in Conexion._connection_cache
                and (
                    current_time - Conexion._last_connection_time.get(connection_key, 0)
                )
                < Conexion._cache_timeout
            ):
                logging.debug(f"Reutilizando conexión existente para {connection_key}")
                # Hacer ping para verificar conexión antes de retornarla
                try:
                    engine = Conexion._connection_cache[connection_key]
                    # Intentar una consulta simple para verificar conexión
                    with engine.connect() as conn:
                        conn.execute(sqlalchemy.text("SELECT 1"))
                    # Actualizar timestamp para extender vida de la conexión
                    Conexion._last_connection_time[connection_key] = current_time
                    return engine
                except Exception as e:
                    logging.warning(
                        f"Conexión en caché inválida para {connection_key}: {e}"
                    )
                    # Eliminar conexión fallida de la caché
                    Conexion.clear_connection_cache(connection_key)
                    # Continuar para crear una nueva

            # Si no hay conexión en caché, ha expirado o falló, crear una nueva
            logging.debug(f"Creando nueva conexión para {connection_key}")
            try:
                # Configuración optimizada para conexiones
                connect_args = {
                    "charset": "utf8mb4",
                    "autocommit": True,
                    # Optimizaciones para reducir latencia
                    "client_flag": pymysql.constants.CLIENT.MULTI_STATEMENTS,
                    # Configuración de timeout para evitar conexiones bloqueadas
                    "connect_timeout": 60,
                    "read_timeout": read_timeout_env,  # por defecto 5 minutos (ajustable)
                    "write_timeout": write_timeout_env,  # por defecto 5 minutos (ajustable)
                }

                # Crear engine con configuración optimizada para conexiones frecuentes
                engine = sqlalchemy.create_engine(
                    sqlalchemy.engine.url.URL.create(
                        drivername="mysql+pymysql",
                        username=user,
                        password=password,
                        host=host,
                        port=port,
                        database=database,
                    ),
                    connect_args=connect_args,
                    # Configuración optimizada del pool de conexiones
                    poolclass=QueuePool,  # Especificar explícitamente QueuePool para mejor control
                    pool_size=pool_size,  # Dinámico por entorno
                    max_overflow=max_overflow,  # Dinámico por entorno
                    pool_timeout=pool_timeout,  # Dinámico por entorno
                    pool_recycle=pool_recycle,  # Dinámico por entorno
                    pool_pre_ping=True,  # Verificar si las conexiones están activas
                    echo=False,  # No mostrar SQL en logs (optimiza rendimiento)
                    echo_pool=False,  # No mostrar actividad del pool en logs
                    future=True,  # Usar funcionalidades más recientes y optimizadas
                    pool_reset_on_return="commit",  # Comportamiento más seguro para el estado de conexiones
                )
                # Guardar la conexión en caché
                Conexion._connection_cache[connection_key] = engine
                Conexion._last_connection_time[connection_key] = current_time
                return engine
            except Exception as e:
                logging.error(
                    f"Error al conectar con la base de datos {database} en {host}: {e}"
                )
                print(
                    f"Error al conectar con la base de datos {database} en {host}: {e}"
                )
                raise

    @staticmethod
    def export_pool_metrics():
        """
        Devuelve un resumen de los pools activos para monitoreo externo (por ejemplo, Prometheus).
        """
        with Conexion._cache_lock:
            metrics = []
            for key, engine in Conexion._connection_cache.items():
                pool = getattr(engine, "pool", None)
                pool_data = {}
                if pool and hasattr(pool, "size") and hasattr(pool, "checkedin"):
                    pool_data = {
                        "size": pool.size(),
                        "checked_in": pool.checkedin(),
                        "checked_out": pool.checkedout(),
                        "overflow": pool.overflow(),
                    }
                metrics.append({
                    "connection_key": key,
                    "pool": pool_data
                })
            return metrics

    @staticmethod
    def ConexionSqlite(db_path: str = "mydata.db"):
        """
        Crea una conexión optimizada a SQLite con pool de conexiones y caché.

        Args:
            db_path (str): Ruta al archivo de la base de datos SQLite.

        Returns:
            Engine: Objeto Engine de SQLAlchemy para ejecutar consultas.
        """
        connection_key = f"sqlite:///{db_path}"
        current_time = time.time()
        with Conexion._cache_lock:
            if (
                connection_key in Conexion._connection_cache
                and (
                    current_time - Conexion._last_connection_time.get(connection_key, 0)
                )
                < Conexion._cache_timeout
            ):
                try:
                    engine = Conexion._connection_cache[connection_key]
                    with engine.connect() as conn:
                        conn.execute(sqlalchemy.text("SELECT 1"))
                    Conexion._last_connection_time[connection_key] = current_time
                    return engine
                except Exception as e:
                    logging.warning(f"Conexión SQLite en caché inválida: {e}")
                    Conexion.clear_connection_cache(connection_key)
            # Crear nueva conexión SQLite
            try:
                engine = sqlalchemy.create_engine(
                    f"sqlite:///{db_path}",
                    connect_args={
                        "timeout": 60,
                        "check_same_thread": False,
                        "isolation_level": None,
                    },
                    poolclass=QueuePool,
                    pool_size=5,
                    max_overflow=10,
                    pool_timeout=60,
                    pool_recycle=1800,
                    pool_pre_ping=True,
                    echo=False,
                    future=True,
                )
                Conexion._connection_cache[connection_key] = engine
                Conexion._last_connection_time[connection_key] = current_time
                return engine
            except Exception as e:
                logging.error(f"Error al conectar con SQLite {db_path}: {e}")
                print(f"Error al conectar con SQLite {db_path}: {e}")
                raise

    @staticmethod
    def create_connection_with_retry(
        user, password, host, port, database, max_retries=3
    ):
        """
        Intenta crear una conexión con reintentos en caso de fallos temporales.

        Args:
            user (str): Nombre de usuario para la conexión.
            password (str): Contraseña del usuario.
            host (str): Host donde se encuentra la base de datos.
            port (int): Puerto para la conexión.
            database (str): Nombre de la base de datos.
            max_retries (int): Número máximo de reintentos.

        Returns:
            Engine: Objeto Engine de SQLAlchemy para ejecutar consultas.

        Raises:
            Exception: Si agotan los reintentos y no se puede establecer la conexión.
        """
        retry_count = 0
        last_error = None

        while retry_count < max_retries:
            try:
                engine = Conexion.ConexionMariadb3(user, password, host, port, database)
                # Probar la conexión con una consulta simple
                with engine.connect() as conn:
                    conn.execute(sqlalchemy.text("SELECT 1"))
                return engine
            except Exception as e:
                last_error = e
                retry_count += 1
                wait_time = 2**retry_count  # Backoff exponencial
                logging.warning(
                    f"Intento {retry_count}/{max_retries} falló. Reintentando en {wait_time}s. Error: {e}"
                )
                time.sleep(wait_time)

        # Si llegamos aquí, todos los reintentos fallaron
        logging.error(f"Fallaron todos los reintentos de conexión: {last_error}")
        raise last_error  # Re-lanzar el último error

    @staticmethod
    def clear_connection_cache(connection_key=None):
        """
        Limpia la caché de conexiones.

        Args:
            connection_key (str, optional): Clave específica de conexión a limpiar.
                Si no se proporciona, se limpian todas las conexiones.
        """
        with Conexion._cache_lock:
            if connection_key and connection_key in Conexion._connection_cache:
                # Cerrar explícitamente la conexión antes de eliminarla
                try:
                    Conexion._connection_cache[connection_key].dispose()
                    logging.info(
                        f"Conexión {connection_key} cerrada y eliminada de la caché"
                    )
                except Exception as e:
                    logging.warning(f"Error al cerrar conexión {connection_key}: {e}")

                del Conexion._connection_cache[connection_key]
                if connection_key in Conexion._last_connection_time:
                    del Conexion._last_connection_time[connection_key]
            elif not connection_key:
                # Cerrar todas las conexiones
                for key, engine in list(Conexion._connection_cache.items()):
                    try:
                        engine.dispose()
                        logging.info(f"Conexión {key} cerrada")
                    except Exception as e:
                        logging.warning(f"Error al cerrar conexión {key}: {e}")

                Conexion._connection_cache.clear()
                Conexion._last_connection_time.clear()
                logging.info("Caché de conexiones limpiada completamente")

    @staticmethod
    def get_connection_status():
        """
        Devuelve información sobre el estado actual de las conexiones en caché.

        Returns:
            dict: Información sobre conexiones actuales y su tiempo de vida.
        """
        with Conexion._cache_lock:
            current_time = time.time()
            status = {
                "total_connections": len(Conexion._connection_cache),
                "connections": {},
            }

            for key in Conexion._connection_cache:
                age = current_time - Conexion._last_connection_time.get(
                    key, current_time
                )
                engine = Conexion._connection_cache[key]

                # Intentar obtener métricas del pool si está disponible
                pool_status = {}
                try:
                    pool = engine.pool
                    if hasattr(pool, "size") and hasattr(pool, "checkedin"):
                        pool_status = {
                            "size": pool.size(),
                            "checked_in": pool.checkedin(),
                            "overflow": pool.overflow(),
                            "checkedout": pool.checkedout(),
                        }
                except:
                    pass

                status["connections"][key] = {
                    "age_seconds": round(age, 2),
                    "expires_in": (
                        round(Conexion._cache_timeout - age, 2)
                        if age < Conexion._cache_timeout
                        else "expired"
                    ),
                    "pool": pool_status,
                }

            return status

    @staticmethod
    def check_pool_health():
        """
        Verifica la salud de los pools de conexiones y cierra aquellos que podrían tener problemas.
        """
        with Conexion._cache_lock:
            for key, engine in list(Conexion._connection_cache.items()):
                try:
                    pool = engine.pool
                    # Detectar posibles condiciones problemáticas
                    if (
                        pool.overflow() > 10  # Muchas conexiones en overflow
                        or pool.checkedout()
                        > pool.size() * 0.9  # Más del 90% del pool en uso
                    ):
                        logging.warning(
                            f"Pool posiblemente en estado de saturación para {key}: "
                            f"overflow={pool.overflow()}, checkedout={pool.checkedout()}. Reiniciando."
                        )
                        # Eliminar y recrear esta conexión
                        Conexion.clear_connection_cache(key)
                except Exception as e:
                    logging.warning(
                        f"Error al verificar estado del pool para {key}: {e}"
                    )
