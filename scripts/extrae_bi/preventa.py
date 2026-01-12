import os
import time
import logging
from typing import Any, Callable, Dict, List, Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.elements import TextClause

from scripts.conexion import Conexion as con
from scripts.config import ConfigBasic

logger = logging.getLogger(__name__)


class PreventaReport:
    """Ejecución del Dashboard de Preventa (Fact Preventa Diaria).

    Responsable de:
    - Ejecutar el procedimiento almacenado sp_reporte_preventa_diaria.
    - Volcar resultados a un Excel server-side.
    """

    DEFAULT_CHUNK_SIZE = 20000
    PROCEDURE_NAME = "sp_reporte_preventa_diaria"

    def __init__(
        self,
        database_name: str,
        ceves_code: str,
        fecha_ini: str,
        fecha_fin: str,
        user_id: int,
        progress_callback: Optional[Callable[..., None]] = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> None:
        self.database_name = database_name
        self.ceves_code = ceves_code
        self.fecha_ini = fecha_ini
        self.fecha_fin = fecha_fin
        self.user_id = user_id
        self.progress_callback = progress_callback
        self.chunk_size = chunk_size or self.DEFAULT_CHUNK_SIZE

        self.engine_mysql: Optional[Engine] = None
        self.file_path: Optional[str] = None
        self.file_name: Optional[str] = None
        self.total_records = 0
        self.start_time = time.time()

    # --- Helpers internos ---
    def _update_progress(self, stage: str, progress_percent: int) -> None:
        if self.progress_callback:
            safe_value = max(0, min(100, int(progress_percent)))
            try:
                self.progress_callback(stage, safe_value, self.total_records, None)
            except Exception as exc:
                logger.warning("No se pudo reportar progreso: %s", exc)

    def _validate_inputs(self) -> None:
        if not self.ceves_code:
            raise ValueError("El agente (CEVES) es obligatorio")
        if not self.fecha_ini or not self.fecha_fin:
             raise ValueError("El rango de fechas es obligatorio")

    def _configure_connection(self) -> None:
        config_basic = ConfigBasic(self.database_name, self.user_id)
        config = config_basic.config
        required_keys = ["nmUsrIn", "txPassIn", "hostServerIn", "portServerIn", "dbBi"]
        if not all(config.get(key) for key in required_keys):
            raise ValueError("Configuración de conexión incompleta para Preventa")
        self.engine_mysql = con.ConexionMariadb3(
            str(config["nmUsrIn"]),
            str(config["txPassIn"]),
            str(config["hostServerIn"]),
            int(config["portServerIn"]),
            str(config["dbBi"]),
        )

    def _build_call(self) -> TextClause:
        # El SP recibe p_ceve, p_fecha_ini, p_fecha_fin
        call_sql = f"CALL {self.PROCEDURE_NAME}(:p_ceve, :p_fecha_ini, :p_fecha_fin)"
        try:
            logger.info("[preventa][sql] %s", call_sql)
            print(f"[preventa][sql] {call_sql}", flush=True)
        except Exception:
            pass
        return text(call_sql)

    def _run_to_excel(self, query: TextClause) -> None:
        assert self.engine_mysql is not None
        os.makedirs("media", exist_ok=True)
        date_str = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
        self.file_name = f"preventa_{self.ceves_code}_{date_str}.xlsx"
        self.file_path = os.path.join("media", self.file_name)

        params = {
            "p_ceve": int(self.ceves_code) if str(self.ceves_code).isdigit() else self.ceves_code,
            "p_fecha_ini": self.fecha_ini,
            "p_fecha_fin": self.fecha_fin,
        }

        self._update_progress("Ejecutando consulta en base de datos...", 10)

        # Usamos pandas con chunks si soporta multiples result sets (StoredProcedures pueden ser tricky en pandas)
        # SQLAlchemy con MariaDB/MySQL stored procedures a veces requiere manejo especial (multi=True en raw driver).
        # Sin embargo, pandas read_sql a menudo funciona si el SP devuelve 1 result set.
        try:
            with self.engine_mysql.connect() as conn:
                # Pandas read_sql con SQLAlchemy connection
                # Nota: read_sql_query a veces falla con CALL. 
                # Ejecutamos con execute y convertimos.
                result = conn.execute(query, params)
                # Fetchall
                rows = result.fetchall()
                if not rows:
                     self._update_progress("No se encontraron registros", 100)
                     # Crear excel vacio con headers? O error?
                     # Mejor dataframe vacio
                     df = pd.DataFrame()
                else:
                    self.total_records = len(rows)
                    self._update_progress(f"Procesando {self.total_records} registros...", 30)
                    df = pd.DataFrame(rows, columns=result.keys())
                
                self._update_progress("Generando archivo Excel...", 70)
                df.to_excel(self.file_path, index=False)
                
        except Exception as e:
            logger.error(f"Error ejecutando SP Preventa: {e}")
            raise

        self._update_progress("Completado", 100)

    def execute(self) -> Dict[str, Any]:
        """Orquesta la ejecución completa."""
        try:
            self._validate_inputs()
            self._update_progress("Configurando conexión...", 5)
            self._configure_connection()
            
            query = self._build_call()
            self._run_to_excel(query)

            return {
                "success": True,
                "file_name": self.file_name,
                "file_path": self.file_path,
                "metadata": {
                    "execution_time": time.time() - self.start_time,
                    "total_records": self.total_records
                }
            }

        except Exception as exc:
            logger.exception("Error en PreventaReport.execute")
            return {
                "success": False,
                "error": str(exc)
            }
