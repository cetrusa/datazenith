#!/usr/bin/env python
"""
Script para optimizar el rendimiento de DataZenith BI
"""
import os
import sys
import django
import time
from django.core.cache import cache
from django.db import connection
from django.conf import settings

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'adminbi.settings.base')
django.setup()

def clear_all_caches():
    """Limpia todas las cachés del sistema"""
    print("🧹 Limpiando cachés...")
    try:
        cache.clear()
        print("✅ Cachés limpiadas exitosamente")
    except Exception as e:
        print(f"❌ Error al limpiar cachés: {e}")

def check_database_connections():
    """Verifica las conexiones a la base de datos"""
    print("🔍 Verificando conexiones de base de datos...")
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            if result:
                print("✅ Conexión a base de datos MySQL OK")
    except Exception as e:
        print(f"❌ Error en conexión MySQL: {e}")

def check_redis_connection():
    """Verifica la conexión a Redis"""
    print("🔍 Verificando conexión a Redis...")
    try:
        import redis
        r = redis.Redis.from_url("redis://redis:6379/1")
        r.ping()
        print("✅ Conexión a Redis OK")
        
        # Información de Redis
        info = r.info()
        print(f"📊 Redis - Memoria usada: {info.get('used_memory_human', 'N/A')}")
        print(f"📊 Redis - Conexiones: {info.get('connected_clients', 'N/A')}")
        
    except Exception as e:
        print(f"❌ Error en conexión Redis: {e}")

def check_session_configuration():
    """Verifica la configuración de sesiones"""
    print("🔍 Verificando configuración de sesiones...")
    
    print(f"📝 SESSION_ENGINE: {settings.SESSION_ENGINE}")
    print(f"📝 SESSION_SAVE_EVERY_REQUEST: {settings.SESSION_SAVE_EVERY_REQUEST}")
    print(f"📝 SESSION_COOKIE_AGE: {settings.SESSION_COOKIE_AGE}")
    
    if settings.SESSION_SAVE_EVERY_REQUEST:
        print("⚠️  ADVERTENCIA: SESSION_SAVE_EVERY_REQUEST=True puede afectar el rendimiento")
    else:
        print("✅ SESSION_SAVE_EVERY_REQUEST optimizado")

def optimize_database_queries():
    """Optimiza las consultas de base de datos"""
    print("🚀 Ejecutando optimizaciones de base de datos...")
    
    try:
        with connection.cursor() as cursor:
            # Analizar tablas principales
            tables_to_analyze = [
                'users_user',
                'permisos_confempresas',
                'django_session'
            ]
            
            for table in tables_to_analyze:
                cursor.execute(f"ANALYZE TABLE {table}")
                print(f"✅ Tabla {table} analizada")
                
    except Exception as e:
        print(f"❌ Error en optimización de BD: {e}")

def check_static_files():
    """Verifica la configuración de archivos estáticos"""
    print("🔍 Verificando archivos estáticos...")
    
    if hasattr(settings, 'STATICFILES_STORAGE'):
        print(f"📝 STATICFILES_STORAGE: {settings.STATICFILES_STORAGE}")
    
    if 'whitenoise' in settings.MIDDLEWARE:
        print("✅ WhiteNoise configurado para archivos estáticos")
    else:
        print("⚠️  WhiteNoise no encontrado en MIDDLEWARE")

def performance_recommendations():
    """Muestra recomendaciones de rendimiento"""
    print("\n🎯 RECOMENDACIONES DE RENDIMIENTO:")
    print("=" * 50)
    
    recommendations = [
        "1. Usar REDIS para sesiones (django_redis.sessions)",
        "2. SESSION_SAVE_EVERY_REQUEST = False",
        "3. Implementar caché de bases de datos por más tiempo (15 min)",
        "4. Usar select_related() en consultas ORM",
        "5. Comprimir respuestas con GZIP",
        "6. Optimizar JavaScript para evitar duplicación de opciones",
        "7. Usar índices en columnas de búsqueda frecuente",
        "8. Configurar CONN_MAX_AGE para conexiones persistentes",
    ]
    
    for rec in recommendations:
        print(f"💡 {rec}")

def main():
    """Función principal"""
    print("🚀 DATAZENITH BI - OPTIMIZADOR DE RENDIMIENTO")
    print("=" * 50)
    
    start_time = time.time()
    
    # Ejecutar verificaciones
    clear_all_caches()
    check_database_connections()
    check_redis_connection()
    check_session_configuration()
    optimize_database_queries()
    check_static_files()
    
    # Mostrar recomendaciones
    performance_recommendations()
    
    end_time = time.time()
    print(f"\n⏱️  Tiempo total de optimización: {end_time - start_time:.2f} segundos")
    print("✅ Optimización completada!")

if __name__ == "__main__":
    main()
