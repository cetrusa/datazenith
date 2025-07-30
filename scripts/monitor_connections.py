#!/usr/bin/env python3
"""
Script mejorado para monitorear conexiones MySQL y identificar leaks de conexiones.
Este script está adaptado para un entorno Docker donde Python corre en contenedor.

Ejecutar cada 5 minutos para detectar problemas de conexiones colgadas.
"""
import pymysql
import time
import json
from datetime import datetime
import logging
import os

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('connection_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_secret(secret_name, secrets_file="secret.json"):
    """Lee configuración desde secret.json"""
    try:
        with open(secrets_file) as f:
            secrets = json.loads(f.read())
        return secrets[secret_name]
    except KeyError:
        logger.error(f"La variable {secret_name} no existe en {secrets_file}")
        return None
    except FileNotFoundError:
        logger.error(f"No se encontró el archivo {secrets_file}")
        return None

def check_mysql_connections():
    """Verifica conexiones activas en MySQL."""
    
    # Obtener configuración desde secret.json (configuración de Docker)
    try:
        host = get_secret("DB_HOST")  # Probablemente algo como 'mysql-server' en Docker
        user = get_secret("DB_USERNAME")
        password = get_secret("DB_PASS")
        port = int(get_secret("DB_PORT", 3306))
        
        if not all([host, user, password]):
            logger.error("Faltan credenciales de MySQL en secret.json")
            return
            
    except Exception as e:
        logger.error(f"Error leyendo configuración: {e}")
        return
    
    try:
        # Conectar al servidor MySQL
        logger.info(f"Conectando a MySQL: {user}@{host}:{port}")
        connection = pymysql.connect(
            host=host, 
            user=user, 
            password=password, 
            port=port,
            connect_timeout=10
        )
        
        with connection.cursor() as cursor:
            # Obtener procesos activos
            cursor.execute("SHOW PROCESSLIST")
            processes = cursor.fetchall()
            
            # Analizar conexiones por usuario de la aplicación
            app_connections = []
            app_users = []  # Usuarios de la aplicación
            
            # Identificar usuarios de la aplicación (no root, mysql, etc.)
            for process in processes:
                process_user = process[1]
                if process_user not in ['root', 'mysql', 'debian-sys-maint', 'mysql.session', 'mysql.sys']:
                    app_users.append(process_user)
            
            app_users = list(set(app_users))  # Eliminar duplicados
            
            # Filtrar conexiones problemáticas de usuarios de aplicación
            for process in processes:
                process_id = process[0]
                process_user = process[1]
                process_host = process[2] if process[2] else 'localhost'
                process_db = process[3] if process[3] else 'NULL'
                process_command = process[4]
                process_time = process[5]
                process_state = process[6] if process[6] else 'NULL'
                process_info = process[7] if process[7] else 'NULL'
                
                # Identificar conexiones problemáticas
                is_app_user = process_user in app_users
                is_sleep = process_command == 'Sleep'
                is_long_running = process_time > 300  # >5 minutos
                
                if is_app_user and is_sleep and is_long_running:
                    app_connections.append({
                        'id': process_id,
                        'user': process_user,
                        'host': process_host,
                        'db': process_db,
                        'command': process_command,
                        'time': process_time,
                        'state': process_state,
                        'info': process_info
                    })
            
            # Estadísticas generales
            total_connections = len(processes)
            app_total = len([p for p in processes if p[1] in app_users])
            sleep_connections = len([p for p in processes if p[4] == 'Sleep'])
            problematic_connections = len(app_connections)
            
            # Reporte
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            logger.info(f"🔍 [{timestamp}] REPORTE DE CONEXIONES MySQL:")
            logger.info(f"   📊 Total conexiones: {total_connections}")
            logger.info(f"   👥 Conexiones de aplicación: {app_total}")
            logger.info(f"   😴 Conexiones en SLEEP: {sleep_connections}")
            logger.info(f"   🚨 Conexiones problemáticas (SLEEP >5min): {problematic_connections}")
            
            if app_users:
                logger.info(f"   👤 Usuarios de aplicación detectados: {', '.join(app_users)}")
            
            # Detalles de conexiones problemáticas
            if app_connections:
                logger.warning(f"\n⚠️  CONEXIONES PROBLEMÁTICAS DETECTADAS:")
                for conn in app_connections[:15]:  # Mostrar máximo 15
                    time_minutes = conn['time'] // 60
                    logger.warning(
                        f"   🔴 ID: {conn['id']}, Usuario: {conn['user']}, "
                        f"DB: {conn['db']}, Tiempo: {time_minutes}min ({conn['time']}s), "
                        f"Host: {conn['host']}"
                    )
                
                # Alertas críticas
                if problematic_connections > 20:
                    logger.critical(f"🚨 ALERTA CRÍTICA: {problematic_connections} conexiones colgadas!")
                    logger.critical("   Posible leak de conexiones detectado")
                    
                elif problematic_connections > 10:
                    logger.warning(f"⚠️  ALERTA: {problematic_connections} conexiones colgadas")
                    logger.warning("   Monitorear de cerca el sistema")
            
            else:
                logger.info("✅ No se detectaron conexiones problemáticas")
            
            # Información adicional útil
            cursor.execute("SHOW VARIABLES LIKE 'max_connections'")
            max_conn = cursor.fetchone()
            if max_conn:
                max_connections = int(max_conn[1])
                usage_percent = (total_connections / max_connections) * 100
                logger.info(f"   📈 Uso de conexiones: {usage_percent:.1f}% ({total_connections}/{max_connections})")
                
                if usage_percent > 80:
                    logger.warning(f"⚠️  USO ALTO DE CONEXIONES: {usage_percent:.1f}%")
                elif usage_percent > 90:
                    logger.critical(f"🚨 USO CRÍTICO DE CONEXIONES: {usage_percent:.1f}%")
            
            # Guardar estadísticas para análisis histórico
            save_statistics({
                'timestamp': timestamp,
                'total_connections': total_connections,
                'app_connections': app_total,
                'sleep_connections': sleep_connections,
                'problematic_connections': problematic_connections,
                'app_users': app_users,
                'details': app_connections[:5]  # Solo guardar primeras 5 para espacio
            })
        
        connection.close()
        logger.info("✅ Análisis completado")
        
    except Exception as e:
        logger.error(f"❌ Error conectando a MySQL: {e}")
        logger.error(f"   Host: {host}, Puerto: {port}, Usuario: {user}")

def save_statistics(stats):
    """Guarda estadísticas en archivo JSON para análisis histórico."""
    stats_file = 'connection_stats.json'
    
    try:
        # Leer estadísticas existentes
        if os.path.exists(stats_file):
            with open(stats_file, 'r') as f:
                all_stats = json.load(f)
        else:
            all_stats = []
        
        # Agregar nueva estadística
        all_stats.append(stats)
        
        # Mantener solo últimas 100 entradas para no llenar el disco
        if len(all_stats) > 100:
            all_stats = all_stats[-100:]
        
        # Guardar
        with open(stats_file, 'w') as f:
            json.dump(all_stats, f, indent=2, default=str)
            
    except Exception as e:
        logger.error(f"Error guardando estadísticas: {e}")

def analyze_historical_data():
    """Analiza datos históricos para identificar patrones."""
    stats_file = 'connection_stats.json'
    
    if not os.path.exists(stats_file):
        logger.info("No hay datos históricos disponibles")
        return
    
    try:
        with open(stats_file, 'r') as f:
            all_stats = json.load(f)
        
        if len(all_stats) < 2:
            logger.info("Datos históricos insuficientes para análisis")
            return
        
        # Análisis de tendencias
        recent_stats = all_stats[-10:]  # Últimas 10 mediciones
        avg_problematic = sum(s['problematic_connections'] for s in recent_stats) / len(recent_stats)
        
        if avg_problematic > 15:
            logger.warning(f"📈 TENDENCIA PREOCUPANTE: Promedio de conexiones problemáticas: {avg_problematic:.1f}")
        elif avg_problematic > 5:
            logger.info(f"📊 Promedio de conexiones problemáticas: {avg_problematic:.1f}")
        else:
            logger.info(f"✅ Promedio de conexiones problemáticas bajo: {avg_problematic:.1f}")
            
    except Exception as e:
        logger.error(f"Error analizando datos históricos: {e}")

if __name__ == "__main__":
    logger.info("🚀 Iniciando monitor de conexiones MySQL")
    logger.info("=" * 60)
    
    # Verificar configuración
    if not os.path.exists("secret.json"):
        logger.error("❌ Archivo secret.json no encontrado")
        exit(1)
    
    # Ejecutar análisis
    check_mysql_connections()
    
    # Análisis histórico
    analyze_historical_data()
    
    logger.info("=" * 60)
    logger.info("✅ Monitor completado")
