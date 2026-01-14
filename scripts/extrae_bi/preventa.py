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

    def _calculate_dashboard_data(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calcula KPIs y Matriz para el Dashboard usando columnas del SP."""
        if df.empty:
            return {
                "kpis": {
                    "total_pedidos": 0,
                    "clientes_atendidos": 0,
                    "clientes_nuevos": 0,
                    "valor_total": 0,
                    "valor_promedio": 0,
                    "tiempo_promedio": "00:00"
                },
                "matrix": []
            }

        # Mapeo de columnas según sp_reporte_preventa_diaria
        # Columnas: fecha, zona_id, zona_nm, clientescom, totalpedidos, pedidos_ruta, pedidos_extraruta, totalpendientes, horai, horaf, tiempo_prom, TotalCLi, ValorT, ValorC, pednuevo
        
        # Totales Globales
        total_pedidos = df['totalpedidos'].sum() if 'totalpedidos' in df.columns else 0
        clientes_atendidos = df['TotalCLi'].sum() if 'TotalCLi' in df.columns else (df['clientescom'].sum() if 'clientescom' in df.columns else 0)
        clientes_nuevos = df['pednuevo'].sum() if 'pednuevo' in df.columns else 0
        valor_total = df['ValorT'].sum() if 'ValorT' in df.columns else 0
        valor_promedio = valor_total / total_pedidos if total_pedidos > 0 else 0
        
        # Tiempo promedio (asumiendo que tiempo_prom está en algún formato manejable o segundos)
        tiempo_promedio_str = "00:00"
        if 'tiempo_prom' in df.columns:
            try:
                # Si es numérico (segundos)
                if pd.api.types.is_numeric_dtype(df['tiempo_prom']):
                    avg_seconds = df['tiempo_prom'].mean()
                    mins, secs = divmod(int(avg_seconds), 60)
                    tiempo_promedio_str = f"{mins:02d}:{secs:02d}"
                else:
                    # Si ya viene como string o timedelta
                    tiempo_promedio_str = str(df['tiempo_prom'].iloc[0])[:5] 
            except:
                pass

        # Matriz por Zona (zona_nm)
        # Queremos Zona (ID - Nombre), Clientes Programados, Atendidos, Cobertura, Pedidos (Ruta, Extra), Valor Total, Promedio, Cambio, Horas
        
        # Preparar columnas compuestas
        # "que la zona tenga el código del vendedor" => Usar codigo_agente si existe
        if 'zona_nm' in df.columns:
            code_col = 'codigo_agente' if 'codigo_agente' in df.columns else ('zona_id' if 'zona_id' in df.columns else None)
            
            if code_col:
                df['ZonaLabel'] = df[code_col].astype(str) + " - " + df['zona_nm'].astype(str)
                col_zona = 'ZonaLabel'
            else:
                col_zona = 'zona_nm'
        else:
            col_zona = 'zona_id' if 'zona_id' in df.columns else 'fecha'

        # Preparar etiqueta de Fecha para agrupación visual
        if 'fecha' in df.columns:
             # Formato string seguro
             df['FechaStr'] = df['fecha'].astype(str)
             if 'dia_semana' in df.columns:
                 df['FechaDisplay'] = df['FechaStr'] + " (" + df['dia_semana'].astype(str) + ")"
             else:
                 df['FechaDisplay'] = df['FechaStr']
        else:
             df['FechaDisplay'] = 'General'

        # Helper para agregación de tiempos (min/max)
        # El usuario solicita NO AGRUPAR/ACUMULAR cuando se seleccionan varios días.
        # "Mantener la estructura de la tabla". Por lo tanto, usamos el DF tal cual viene del SP.
        
        matrix_df = df.copy()

        # Cálculos derivados en la matriz (fila a fila)
        matrix_df['Cobertura'] = 0.0
        if 'TotalCLi' in matrix_df.columns and 'clientescom' in matrix_df.columns:
            matrix_df['Cobertura'] = matrix_df.apply(lambda x: (x['TotalCLi'] / x['clientescom'] * 100) if x['clientescom'] > 0 else 0, axis=1)

        matrix_df['TicketPromedio'] = 0.0
        if 'ValorT' in matrix_df.columns and 'totalpedidos' in matrix_df.columns:
             matrix_df['TicketPromedio'] = matrix_df.apply(lambda x: (x['ValorT'] / x['totalpedidos']) if x['totalpedidos'] > 0 else 0, axis=1)

        # Calcular Tiempo Total
        # Convertimos las columnas horai/horaf a timedelta para restar
        matrix_df['Tiempo Total'] = '-'
        if 'horai' in matrix_df.columns and 'horaf' in matrix_df.columns:
            try:
                # Convertir a cadena y luego a timedelta
                # Nota: si vienen nulos o NaT, to_timedelta con errors='coerce' devuelve NaT
                start_deltas = pd.to_timedelta(matrix_df['horai'].astype(str), errors='coerce')
                end_deltas = pd.to_timedelta(matrix_df['horaf'].astype(str), errors='coerce')
                
                diffs = end_deltas - start_deltas
                
                # Convertir a string HH:MM:SS (eliminando '0 days ' si aparece)
                # components devuelve dataframe con days, hours, minutes, seconds...
                # Una forma rápida es usar str accesors después de astype(str)
                matrix_df['Tiempo Total'] = diffs.astype(str).str.replace('0 days ', '').str.split('.').str[0]
                matrix_df['Tiempo Total'] = matrix_df['Tiempo Total'].replace({'NaT': '-', 'nan': '-'})
            except Exception:
                pass


        # Renombrar para JS
        rename_map = {
            col_zona: 'Zona',
            'clientescom': 'Programados',
            'TotalCLi': 'Atendidos',
            'totalpedidos': 'Pedidos',
            'pednuevo': 'Cl. Nuevos',
            'ValorT': 'Valor Total',
            'ValorC': 'Valor Cambio',
            'pedidos_ruta': 'Pedidos Ruta',
            'pedidos_extraruta': 'P. Extra Ruta',
            'totalpendientes': 'Pendientes',
            'horai': 'Hora Inicio',
            'horaf': 'Hora Fin'
        }
        matrix_df.rename(columns=rename_map, inplace=True)
        
        # Formateo de Tiempos (timedelta a str si es necesario)
        for col in ['Hora Inicio', 'Hora Fin']:
            if col in matrix_df.columns:
                matrix_df[col] = matrix_df[col].astype(str).str.replace('0 days ', '').str[:8] # Simple cleanup

        matrix_df = matrix_df.where(pd.notnull(matrix_df), 0)
        matrix_data = matrix_df.to_dict(orient='records')

        return {
            "kpis": {
                "total_pedidos": int(total_pedidos),
                "clientes_atendidos": int(clientes_atendidos),
                "clientes_nuevos": int(clientes_nuevos),
                "valor_total": float(valor_total),
                "valor_promedio": float(valor_promedio),
                "tiempo_promedio": tiempo_promedio_str
            },
            "matrix": matrix_data
        }

    def _run_to_excel(self, query: TextClause) -> pd.DataFrame:
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

        try:
            with self.engine_mysql.connect() as conn:
                result = conn.execute(query, params)
                rows = result.fetchall()
                if not rows:
                     self._update_progress("No se encontraron registros", 100)
                     df = pd.DataFrame()
                else:
                    self.total_records = len(rows)
                    self._update_progress(f"Procesando {self.total_records} registros...", 30)
                    df = pd.DataFrame(rows, columns=result.keys())
                
                if not df.empty:
                    self._update_progress("Generando archivo Excel...", 70)
                    df.to_excel(self.file_path, index=False)
                
                return df
                
        except Exception as e:
            logger.error(f"Error ejecutando SP Preventa: {e}")
            raise

    def execute(self) -> Dict[str, Any]:
        """Orquesta la ejecución completa."""
        try:
            self._validate_inputs()
            self._update_progress("Configurando conexión...", 5)
            self._configure_connection()
            
            query = self._build_call()
            df = self._run_to_excel(query)

            # Calcular datos del Dashboard
            dashboard_data = self._calculate_dashboard_data(df)

            return {
                "success": True,
                "file_name": self.file_name,
                "file_path": self.file_path,
                "dashboard": dashboard_data,
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
