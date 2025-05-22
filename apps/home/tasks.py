import os
import time
import logging
import traceback
from functools import wraps
from typing import Dict, Any, Optional, Callable, TypeVar

# RQ Imports
from django_rq import job
from rq import get_current_job

# Project Script Imports
from scripts.extrae_bi.cubo import CuboVentas
from scripts.config import ConfigBasic
from scripts.extrae_bi.cargue_zip import CargueZip
from scripts.extrae_bi.interface import InterfaceContable
from scripts.extrae_bi.plano import InterfacePlano

# from scripts.StaticPage import StaticPage # No parece usarse
from scripts.extrae_bi.cargue_plano_tsol import CarguePlano
from scripts.extrae_bi.extrae_bi_insert import ExtraeBiConfig, ExtraeBiExtractor
from apps.home.utils import clean_old_media_files

# Configuración de logging
logger = logging.getLogger(__name__)

# --- Constantes y Tipos (Ajustar según necesidad) ---
DEFAULT_TIMEOUT = 7200  # 2 horas (Aumentado para tareas potencialmente largas)
DEFAULT_BATCH_SIZE = 50000
# DEFAULT_RETRY_COUNT = 3 # No usado directamente
# JOB_PROGRESS_KEY_PREFIX = "job_progress_" # No usado directamente
# JOB_META_KEY_PREFIX = "job_meta_" # No usado directamente

# Tipos para tipado
T = TypeVar("T")
ResultDict = Dict[str, Any]


# --- Funciones Helper y Decoradores para RQ ---


def update_job_progress(
    job_id: Optional[str],  # Job ID puede ser None si se llama fuera de contexto
    progress: int,
    status: str = "processing",  # Cambiado default a 'processing'
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Actualiza el progreso y metadatos de un trabajo RQ en ejecución.
    Intenta obtener el job actual si no se proporciona job_id.
    """
    current_job = get_current_job()
    target_job_id = job_id or (current_job.id if current_job else None)

    if not target_job_id:
        logger.warning(
            "update_job_progress llamado sin job_id y fuera de un contexto de job RQ."
        )
        return

    # Si estamos dentro de un job, usar el objeto job directamente es más eficiente
    job_to_update = (
        current_job if current_job and current_job.id == target_job_id else None
    )

    print(
        f"[update_job_progress] job_id={job_id}, progress={progress}, status={status}, meta={meta}"
    )
    if job_to_update:
        if not meta:
            meta = {}
        print(f"[update_job_progress] Updating job meta for job_id={target_job_id}")
        # Asegurar que 'status' y 'progress' estén en meta para RQ
        # Usar meta.get para evitar sobreescribir valores existentes si no se proporcionan nuevos
        current_meta = job_to_update.meta or {}
        updated_meta = {
            **current_meta,  # Mantener meta existente
            **meta,  # Añadir/Sobreescribir con nuevos meta
            "progress": max(0, min(100, progress)),
            "status": status,
            "updated_at": time.time(),
        }
        job_to_update.meta.update(updated_meta)
        try:
            job_to_update.save_meta()
            print(
                f"[update_job_progress] Meta saved for job_id={target_job_id}: progress={updated_meta.get('progress')}% status={status}"
            )
            logger.debug(
                f"RQ Job {target_job_id} progress updated: {status} - {updated_meta.get('progress')}%"
            )
        except Exception as e:
            print(
                f"[update_job_progress] Error saving meta for job_id={target_job_id}: {e}"
            )
            logger.error(f"Error al guardar meta para RQ Job {target_job_id}: {e}")
    else:
        print(
            f"[update_job_progress] No job found to update for job_id={target_job_id}"
        )
        # Si no estamos en el job actual (poco común para progreso), necesitaríamos fetch el job
        # Esto es menos eficiente y generalmente no necesario para updates de progreso
        logger.warning(
            f"Intento de actualizar progreso para Job {target_job_id} fuera de su contexto directo."
        )
        # Podría implementarse fetching el job por ID si es estrictamente necesario


def task_handler(f: Callable[..., T]) -> Callable[..., ResultDict]:
    """
    Decorador que estandariza el manejo de errores y resultados para tareas RQ.
    Proporciona logging, manejo de excepciones, formato de respuesta y tiempo de ejecución.
    """

    @wraps(f)
    def wrapper(*args, **kwargs) -> ResultDict:
        start_time = time.time()
        job = get_current_job()
        task_name = f.__name__
        job_id = job.id if job else "N/A"

        # Inicializa el progreso
        if job:
            update_job_progress(
                job_id, 0, "starting", meta={"stage": "Inicializando tarea"}
            )

        logger.info(
            f"Iniciando tarea RQ {task_name} (Job ID: {job_id}) con args={args}, kwargs={kwargs}"
        )

        try:
            # Ejecuta la función original
            if job:
                update_job_progress(
                    job_id,
                    5,
                    "processing",
                    meta={"stage": "Ejecutando lógica principal"},
                )
            result = f(*args, **kwargs)  # La función decorada debe devolver ResultDict

            # Validar formato del resultado
            if not isinstance(result, dict):
                logger.error(
                    f"Tarea RQ {task_name} (Job ID: {job_id}) devolvió formato incorrecto: {type(result)}"
                )
                result = {
                    "success": False,
                    "error_message": "Formato de resultado interno incorrecto.",
                }

            execution_time = time.time() - start_time
            result["execution_time"] = execution_time  # Añadir tiempo de ejecución

            # Actualizar estado final basado en 'success'
            if result.get("success", False):
                final_stage = result.get("metadata", {}).get(
                    "stage", "Completado"
                )  # Usar stage final si existe
                logger.info(
                    f"Tarea RQ {task_name} (Job ID: {job_id}) completada exitosamente en {execution_time:.2f}s."
                )
                if job:
                    update_job_progress(
                        job_id,
                        100,
                        "completed",
                        meta={"result": result, "stage": final_stage},
                    )
            else:
                final_stage = result.get("metadata", {}).get(
                    "stage", "Fallido"
                )  # Usar stage final si existe
                logger.warning(
                    f"Tarea RQ {task_name} (Job ID: {job_id}) finalizada con error en {execution_time:.2f}s. Mensaje: {result.get('error_message', 'N/A')}"
                )
                if job:
                    update_job_progress(
                        job_id,
                        100,
                        "failed",
                        meta={"result": result, "stage": final_stage},
                    )

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            error_details = traceback.format_exc()
            error_msg = (
                f"Error inesperado en tarea RQ {task_name} (Job ID: {job_id}): {str(e)}"
            )
            logger.error(f"{error_msg}\n{error_details}")

            final_result = {
                "success": False,
                "error_message": error_msg,
                "error_details": error_details,  # Incluir traceback para depuración
                "execution_time": execution_time,
            }
            if job:
                update_job_progress(
                    job_id,
                    100,
                    "failed",
                    meta={"error": str(e), "stage": "Error Crítico"},
                )
            return final_result

    return wrapper


# --- Tareas RQ ---

from django.db import connection


@job("default", timeout=DEFAULT_TIMEOUT)  # Usar cola 'default' o una específica
@task_handler  # Aplicar decorador estándar
def cubo_ventas_task(
    database_name,
    IdtReporteIni,
    IdtReporteFin,
    user_id,
    report_id,
    batch_size=DEFAULT_BATCH_SIZE,
):
    """
    Tarea RQ para generar el Cubo de Ventas, reportando progreso detallado.
    Optimizada para grandes volúmenes de datos.
    """
    # Cerrar conexión Django antes de iniciar procesamiento pesado
    try:
        connection.close()
    except Exception:
        pass
    job = get_current_job()
    job_id = job.id if job else None
    logger.info(
        f"Iniciando cubo_ventas_task (RQ Job ID: {job_id}) para DB: {database_name}, Periodo: {IdtReporteIni}-{IdtReporteFin}"
    )

    print(
        f"[cubo_ventas_task] INICIO: database_name={database_name}, IdtReporteIni={IdtReporteIni}, IdtReporteFin={IdtReporteFin}, user_id={user_id}, report_id={report_id}, batch_size={batch_size}"
    )

    # Estimación inicial de pasos (puede ajustarse en CuboVentas si es necesario)
    # total_steps_estimate = 5 # No usado directamente aquí

    def rq_update_progress(stage, progress_percent, current_rec=None, total_rec=None):
        """Callback para actualizar el estado de la tarea RQ."""
        # Construir meta data
        meta = {
            "stage": stage,
            # 'current_step': current_step, # Podría añadirse si CuboVentas lo reporta
            # 'total_steps': total_steps_estimate,
        }
        if current_rec is not None:
            meta["records_processed"] = current_rec
        if total_rec is not None:
            meta["total_records_estimate"] = total_rec

        # Llamar a la función helper de RQ
        update_job_progress(
            job_id, int(progress_percent), status="processing", meta=meta
        )

    print("[cubo_ventas_task] Instanciando CuboVentas...")
    # Instanciar y ejecutar la lógica principal, pasando el callback adaptado para RQ
    cubo_processor = CuboVentas(
        database_name,
        IdtReporteIni,
        IdtReporteFin,
        user_id,
        report_id,
        progress_callback=rq_update_progress,  # <-- Pasar callback adaptado
    )

    # Si CuboVentas soporta batch_size, pásalo aquí o configúralo internamente
    if hasattr(cubo_processor, "batch_size"):
        cubo_processor.batch_size = batch_size

    print("[cubo_ventas_task] Ejecutando run() de CuboVentas...")
    # run() ahora usa el callback internamente y devuelve el resultado final
    # El decorador @task_handler se encargará del manejo de errores y formato final
    result_data = cubo_processor.run()

    # --- Asegurar que el progreso final se reporte correctamente para el frontend ---
    job = get_current_job()
    job_id = job.id if job else None
    # Si la tarea fue exitosa, reportar 100% y status 'completed' en meta
    if result_data.get("success"):
        update_job_progress(
            job_id,
            100,
            status="completed",
            meta={"stage": "Completado", "file_ready": True},
        )
    else:
        update_job_progress(job_id, 100, status="failed", meta={"stage": "Fallido"})

    # Obtener muestra de datos para previsualización (solo si el proceso fue exitoso)
    if result_data.get("success"):
        try:
            preview = cubo_processor.get_data(start_row=0, chunk_size=100)
            headers = preview.get("headers", [])
            rows = preview.get("rows", [])
            muestra = [dict(zip(headers, row)) for row in rows]
            result_data["preview_headers"] = headers
            result_data["preview_sample"] = muestra
        except Exception as e:
            logger.warning(f"No se pudo obtener previsualización: {e}")
            result_data["preview_headers"] = []
            result_data["preview_sample"] = []

    print(f"[cubo_ventas_task] RESULTADO: {result_data}")

    # Cerrar conexión Django después de finalizar procesamiento pesado
    try:
        connection.close()
    except Exception:
        pass

    print("[cubo_ventas_task] FIN")
    # Devolver directamente el resultado de CuboVentas.run()
    # El decorador @task_handler añadirá execution_time y manejará el estado final.
    return result_data


@job("default", timeout=DEFAULT_TIMEOUT)
@task_handler
def interface_task(
    database_name,
    IdtReporteIni,
    IdtReporteFin,
    user_id,
    report_id,
    batch_size=DEFAULT_BATCH_SIZE,
):
    """
    Tarea RQ para generar Interface Contable, reportando progreso detallado.
    Optimizada para grandes volúmenes de datos.
    """
    try:
        connection.close()
    except Exception:
        pass
    job = get_current_job()
    job_id = job.id if job else None
    logger.info(
        f"Iniciando interface_task (RQ Job ID: {job_id}) para DB: {database_name}, Periodo: {IdtReporteIni}-{IdtReporteFin}"
    )
    print(
        f"[interface_task] INICIO: database_name={database_name}, IdtReporteIni={IdtReporteIni}, IdtReporteFin={IdtReporteFin}, user_id={user_id}, report_id={report_id}, batch_size={batch_size}"
    )

    def rq_update_progress(
        stage,
        progress_percent,
        current_rec=None,
        total_rec=None,
        hoja_idx=None,
        total_hojas=None,
    ):
        meta = {"stage": stage}
        if current_rec is not None:
            meta["records_processed"] = current_rec
        if total_rec is not None:
            meta["total_records_estimate"] = total_rec
        if hoja_idx is not None and total_hojas is not None:
            meta["hoja_actual"] = hoja_idx
            meta["total_hojas"] = total_hojas
            global_percent = int((hoja_idx / total_hojas) * 100)
        else:
            global_percent = progress_percent
        print(
            f"[interface_task][progreso] stage={stage}, hoja_idx={hoja_idx}, total_hojas={total_hojas}, global_percent={global_percent}"
        )
        update_job_progress(job_id, int(global_percent), status="processing", meta=meta)

    print("[interface_task] Instanciando InterfaceContable...")
    # Instanciar y ejecutar la lógica principal, pasando el callback adaptado para RQ
    interface_processor = InterfaceContable(
        database_name,
        IdtReporteIni,
        IdtReporteFin,
        user_id,
        report_id,
        progress_callback=rq_update_progress,  # <-- Pasar callback adaptado
    )

    # Si interface soporta batch_size, pásalo aquí o configúralo internamente
    if hasattr(interface_processor, "batch_size"):
        interface_processor.batch_size = batch_size

    print("[interface_task] Ejecutando run() de InterfaceContable...")
    # run() ahora usa el callback internamente y devuelve el resultado final
    # El decorador @task_handler se encargará del manejo de errores y formato final
    result_data = (
        interface_processor.run()
    )  # batch_size se pasa en __init__ o se usa default

    print(f"[interface_task] RESULTADO: {result_data}")

    # Cerrar conexión Django después de finalizar procesamiento pesado
    try:
        connection.close()
    except Exception:
        pass

    print("[interface_task] FIN")
    # Devolver directamente el resultado de CuboVentas.run()
    # El decorador @task_handler añadirá execution_time y manejará el estado final.
    return result_data


@job("default", timeout=DEFAULT_TIMEOUT)
@task_handler
def plano_task(
    database_name,
    IdtReporteIni,
    IdtReporteFin,
    user_id,
    report_id,
    batch_size=DEFAULT_BATCH_SIZE,
):
    """
    Tarea RQ: Genera archivos planos a partir de datos (InterfacePlano).
    """
    job = get_current_job()
    job_id = job.id if job else None

    print(
        f"[plano_task] INICIO: database_name={database_name}, IdtReporteIni={IdtReporteIni}, IdtReporteFin={IdtReporteFin}, user_id={user_id}, report_id={report_id}, batch_size={batch_size}"
    )
    print(f"[plano_task] Working directory: {os.getcwd()}")
    print(
        f"[plano_task] media/mydata.db exists? {os.path.exists(os.path.join('media', 'mydata.db'))}"
    )
    print(f"[plano_task] media/ dir exists? {os.path.exists('media')}")
    print(f"[plano_task] User: {os.environ.get('USERNAME') or os.environ.get('USER')}")

    # Callback robusto y uniforme para progreso
    def rq_update_progress(
        stage,
        progress_percent,
        current_rec=None,
        total_rec=None,
        hoja_idx=None,
        total_hojas=None,
        status=None,
        meta=None,
        **kwargs,
    ):
        meta_dict = {"stage": stage}
        if current_rec is not None:
            meta_dict["records_processed"] = current_rec
        if total_rec is not None:
            meta_dict["total_records_estimate"] = total_rec
        if hoja_idx is not None and total_hojas is not None:
            meta_dict["hoja_actual"] = hoja_idx
            meta_dict["total_hojas"] = total_hojas
            global_percent = int((hoja_idx / total_hojas) * 100)
        else:
            global_percent = progress_percent
        if status is not None:
            meta_dict["status"] = status
        if meta is not None:
            meta_dict.update(meta)
        print(
            f"[plano_task][progreso] stage={stage}, hoja_idx={hoja_idx}, total_hojas={total_hojas}, global_percent={global_percent}, status={status}, meta={meta}"
        )
        update_job_progress(
            job_id, int(global_percent), status=(status or "processing"), meta=meta_dict
        )

    print("[plano_task] Instanciando InterfacePlano...")
    update_job_progress(job_id, 10, meta={"stage": "Iniciando InterfacePlano"})
    interface = InterfacePlano(
        database_name,
        IdtReporteIni,
        IdtReporteFin,
        user_id,
        report_id,
        progress_callback=rq_update_progress,
    )
    print("[plano_task] Ejecutando run() de InterfacePlano...")
    update_job_progress(
        job_id, 30, meta={"stage": "Evaluando y procesando datos para plano"}
    )
    resultado = interface.run()
    print(f"[plano_task] RESULTADO: {resultado}")

    # --- Asegurar que el resultado siempre tenga 'metadata' relevante ---
    if "metadata" not in resultado or not isinstance(resultado.get("metadata"), dict):
        # Intentar obtener info relevante de InterfacePlano si existe
        total_hojas = None
        hojas_con_datos = None
        if hasattr(interface, "config"):
            hojas1 = getattr(interface, "_obtener_lista_hojas", lambda x: [])(
                "txProcedureCsv"
            )
            hojas2 = getattr(interface, "_obtener_lista_hojas", lambda x: [])(
                "txProcedureCsv2"
            )
            total_hojas = len(hojas1) if hojas1 else len(hojas2)
        # Si el resultado tiene éxito, estimar hojas_con_datos como 1 (mínimo) si no hay info
        if resultado.get("success"):
            hojas_con_datos = 1
        else:
            hojas_con_datos = 0
        resultado["metadata"] = {
            "total_hojas": total_hojas,
            "hojas_con_datos": hojas_con_datos,
        }

    # Reportar progreso final y estado global según éxito o error
    if not resultado.get("success", True):
        update_job_progress(
            job_id,
            100,
            status="failed",
            meta={"stage": "Finalizado con error", "result": resultado},
        )
    else:
        update_job_progress(
            job_id,
            100,
            status="completed",
            meta={"stage": "Finalizado", "result": resultado},
        )
    print("[plano_task] FIN")
    return resultado


@job("default", timeout=DEFAULT_TIMEOUT)
@task_handler
def cargue_zip_task(database_name: str, zip_file_path: str) -> ResultDict:
    """
    Tarea RQ: Procesa un archivo ZIP para carga de datos.
    """
    job = get_current_job()
    job_id = job.id if job else None

    print(
        f"[cargue_zip_task] INICIO: database_name={database_name}, zip_file_path={zip_file_path}"
    )

    # Validar que el archivo exista ANTES de llamar a la lógica principal
    if not os.path.exists(zip_file_path):
        print(f"[cargue_zip_task] Archivo ZIP no encontrado: {zip_file_path}")
        logger.error(f"Archivo ZIP no encontrado en cargue_zip_task: {zip_file_path}")
        # Devolver error directamente, el decorador lo manejará
        return {
            "success": False,
            "error_message": f"El archivo ZIP no existe en la ruta: {zip_file_path}",
        }

    print("[cargue_zip_task] Instanciando CargueZip...")
    update_job_progress(job_id, 10, meta={"stage": "Iniciando CargueZip"})

    cargue_zip = CargueZip(database_name, zip_file_path)
    print("[cargue_zip_task] Ejecutando procesar_zip()...")
    update_job_progress(job_id, 30, meta={"stage": "Procesando archivo ZIP"})

    # Asume que procesar_zip devuelve ResultDict o puede fallar
    resultado = cargue_zip.procesar_zip()
    print(f"[cargue_zip_task] RESULTADO: {resultado}")
    update_job_progress(job_id, 90, meta={"stage": "Finalizando procesamiento ZIP"})
    print("[cargue_zip_task] FIN")
    return resultado


@job("default", timeout=DEFAULT_TIMEOUT)
@task_handler
def cargue_plano_task(database_name: str) -> ResultDict:
    """
    Tarea RQ: Procesa archivos planos para cargar datos (TSOL).
    """
    job = get_current_job()
    job_id = job.id if job else None

    print(f"[cargue_plano_task] INICIO: database_name={database_name}")

    print("[cargue_plano_task] Instanciando CarguePlano...")
    update_job_progress(job_id, 10, meta={"stage": "Iniciando CarguePlano"})

    cargue_plano = CarguePlano(database_name)  # Asume CarguePlano es para TSOL
    print("[cargue_plano_task] Ejecutando procesar_plano()...")
    update_job_progress(job_id, 30, meta={"stage": "Procesando archivos planos"})

    # Asume que procesar_plano devuelve ResultDict o puede fallar
    resultado = cargue_plano.procesar_plano()
    print(f"[cargue_plano_task] RESULTADO: {resultado}")
    update_job_progress(job_id, 90, meta={"stage": "Finalizando carga de planos"})
    print("[cargue_plano_task] FIN")
    return resultado


@job("default", timeout=DEFAULT_TIMEOUT)
@task_handler
def extrae_bi_task(
    database_name: str,
    IdtReporteIni: str,
    IdtReporteFin: str,
    user_id: Optional[int] = None,
    id_reporte: Optional[int] = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
):
    """
    Tarea RQ: Ejecuta la extracción y procesamiento de datos BI (Extrae_Bi).
    """
    job = get_current_job()
    job_id = job.id if job else None

    print(
        f"[extrae_bi_task] INICIO: database_name={database_name}, IdtReporteIni={IdtReporteIni}, IdtReporteFin={IdtReporteFin}, user_id={user_id}, id_reporte={id_reporte}, batch_size={batch_size}"
    )

    def rq_update_progress(meta_dict, progress_percent):
        # meta_dict contiene: stage, tabla, nmReporte, progress
        update_job_progress(job_id, int(progress_percent), meta=meta_dict)

    print("[extrae_bi_task] Instanciando ExtraeBiConfig y ExtraeBiExtractor...")
    update_job_progress(job_id, 5, meta={"stage": "Iniciando Extrae_Bi"})
    logger.info(
        f"Iniciando extrae_bi_task (RQ Job: {job_id}) para {database_name}, Periodo: {IdtReporteIni}-{IdtReporteFin}, user_id={user_id}, id_reporte={id_reporte}, batch_size={batch_size}"
    )
    config = ExtraeBiConfig(database_name)
    extractor = ExtraeBiExtractor(
        config,
        IdtReporteIni,
        IdtReporteFin,
        user_id=user_id,
        id_reporte=id_reporte,
        batch_size=batch_size,
        progress_callback=rq_update_progress,
    )
    print("[extrae_bi_task] Ejecutando run() de ExtraeBiExtractor...")
    update_job_progress(job_id, 15, meta={"stage": "Ejecutando extractor principal"})
    result = extractor.run()
    print(f"[extrae_bi_task] RESULTADO: {result}")
    update_job_progress(job_id, 95, meta={"stage": "Finalizando extracción BI"})
    print("[extrae_bi_task] FIN")
    return result


def clean_media_periodic(hours=4):
    """
    Tarea periódica para limpiar archivos viejos en media/.
    """
    removed = clean_old_media_files(hours=hours)
    logger.info(f"[clean_media_periodic] Archivos eliminados: {removed}")
    return removed
