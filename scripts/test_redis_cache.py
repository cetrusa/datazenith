#!/usr/bin/env python3
"""
Script de pruebas para Redis y RQ en DataZenith BI
Funciona tanto desde host (localhost) como desde Docker (redis)
"""

import redis
import time
import json
from datetime import datetime
import sys
import os

try:
    import rq
    from rq import Queue
    RQ_AVAILABLE = True
except ImportError:
    RQ_AVAILABLE = False
    print("⚠️  RQ no está disponible - algunas pruebas serán omitidas")

def test_redis_connection():
    """Prueba la conexión a Redis."""
    print(f"🔍 [{datetime.now().strftime('%H:%M:%S')}] Probando conexión a Redis...")
    
    # Intentar primero localhost (desde host), luego redis (desde Docker)
    redis_hosts = ['localhost', 'redis']
    
    for host in redis_hosts:
        try:
            print(f"   Intentando conectar a {host}:6379...")
            # Intentar conectar a las 3 bases de datos Redis configuradas
            redis_configs = [
                {"db": 1, "name": "Cache General"},
                {"db": 2, "name": "Cache Queries"},
                {"db": 3, "name": "Cache Sessions"}
            ]
            
            success_count = 0
            for config in redis_configs:
                try:
                    client = redis.Redis(host=host, port=6379, db=config['db'], 
                                       decode_responses=True, socket_connect_timeout=5)
                    # Intentar un ping
                    client.ping()
                    print(f"✅ {config['name']} (DB {config['db']}): CONECTADO")
                    
                    # Probar escribir y leer
                    test_key = f"test_key_{config['db']}"
                    test_value = f"test_value_{int(time.time())}"
                    
                    client.set(test_key, test_value, ex=60)  # Expira en 60 segundos
                    retrieved = client.get(test_key)
                    
                    if retrieved == test_value:
                        print(f"   📝 Escritura/Lectura: OK")
                        success_count += 1
                    else:
                        print(f"   ❌ Escritura/Lectura: FALLO")
                    
                    # Limpiar
                    client.delete(test_key)
                    
                except Exception as e:
                    print(f"❌ {config['name']} (DB {config['db']}): ERROR - {e}")
            
            if success_count > 0:
                print(f"✅ Redis conectado exitosamente en {host}:6379")
                print()
                return success_count == len(redis_configs)
            
        except Exception as e:
            print(f"   No se pudo conectar a {host}: {e}")
            continue
    
    print("❌ No se pudo conectar a Redis en ningún host")
    print("   💡 ¿Está Redis ejecutándose en Docker o localmente?")
    print()
    return False

def test_redis_performance():
    """Prueba el rendimiento básico de Redis."""
    print(f"🚀 [{datetime.now().strftime('%H:%M:%S')}] Probando rendimiento de Redis...")
    
    # Intentar primero localhost (desde host), luego redis (desde Docker)
    redis_hosts = ['localhost', 'redis']
    
    for host in redis_hosts:
        try:
            print(f"   Probando rendimiento en {host}:6379...")
            client = redis.Redis(host=host, port=6379, db=1, decode_responses=True, socket_connect_timeout=5)
            
            # Verificar conexión primero
            client.ping()
            
            # Prueba de escritura en lote
            start_time = time.time()
            pipe = client.pipeline()
            
            for i in range(100):
                pipe.set(f"perf_test_{i}", f"valor_{i}", ex=60)
            
            pipe.execute()
            write_time = time.time() - start_time
            
            # Prueba de lectura en lote
            start_time = time.time()
            pipe = client.pipeline()
            
            for i in range(100):
                pipe.get(f"perf_test_{i}")
            
            results = pipe.execute()
            read_time = time.time() - start_time
            
            print(f"📊 Escritura de 100 claves: {write_time:.3f}s ({100/write_time:.1f} ops/seg)")
            print(f"📊 Lectura de 100 claves: {read_time:.3f}s ({100/read_time:.1f} ops/seg)")
            
            # Limpiar
            keys_to_delete = [f"perf_test_{i}" for i in range(100)]
            if keys_to_delete:
                client.delete(*keys_to_delete)
            
            if write_time < 0.1 and read_time < 0.1:
                print("✅ Rendimiento: EXCELENTE")
                print()
                return True
            elif write_time < 0.5 and read_time < 0.5:
                print("⚠️  Rendimiento: ACEPTABLE")
                print()
                return True
            else:
                print("❌ Rendimiento: LENTO")
                print()
                return False
            
        except Exception as e:
            print(f"   No se pudo probar rendimiento en {host}: {e}")
            continue
    
    print("❌ No se pudo probar el rendimiento de Redis en ningún host")
    print()
    return False

def test_redis_memory():
    """Verifica el uso de memoria de Redis."""
    print(f"💾 [{datetime.now().strftime('%H:%M:%S')}] Verificando memoria Redis...")
    
    # Intentar primero localhost (desde host), luego redis (desde Docker)
    redis_hosts = ['localhost', 'redis']
    
    for host in redis_hosts:
        try:
            print(f"   Verificando memoria en {host}:6379...")
            client = redis.Redis(host=host, port=6379, db=1, socket_connect_timeout=5)
            info = client.info('memory')
            
            used_memory = info.get('used_memory_human', 'N/A')
            used_memory_peak = info.get('used_memory_peak_human', 'N/A')
            
            print(f"📈 Memoria usada: {used_memory}")
            print(f"📈 Pico de memoria: {used_memory_peak}")
            
            # Verificar que Redis tenga suficiente memoria
            used_bytes = info.get('used_memory', 0)
            if used_bytes < 100 * 1024 * 1024:  # Menos de 100MB
                print("✅ Uso de memoria: NORMAL")
                print()
                return True
            elif used_bytes < 500 * 1024 * 1024:  # Menos de 500MB
                print("⚠️  Uso de memoria: ALTO")
                print()
                return True
            else:
                print("❌ Uso de memoria: CRÍTICO")
                print()
                return False
            
        except Exception as e:
            print(f"   No se pudo verificar memoria en {host}: {e}")
            continue
    
    print("❌ No se pudo verificar la memoria de Redis en ningún host")
    print()
    return False

def simulate_cache_usage():
    """Simula el uso típico del caché de la aplicación."""
    print(f"🎭 [{datetime.now().strftime('%H:%M:%S')}] Simulando uso típico del caché...")
    
    # Intentar primero localhost (desde host), luego redis (desde Docker)
    redis_hosts = ['localhost', 'redis']
    
    for host in redis_hosts:
        try:
            print(f"   Simulando caché en {host}:6379...")
            success_count = 0
            
            # Cache general (DB 1)
            cache_general = redis.Redis(host=host, port=6379, db=1, decode_responses=True, socket_connect_timeout=5)
            
            # Simular caché de datos de usuario
            user_data = {
                "user_id": 123,
                "databases": [
                    {"name": "empresa1", "nmEmpresa": "Empresa Test 1"},
                    {"name": "empresa2", "nmEmpresa": "Empresa Test 2"}
                ],
                "cached_at": datetime.now().isoformat()
            }
            
            cache_key = "user_databases_123"
            cache_general.setex(cache_key, 3600, json.dumps(user_data))  # 1 hora
            
            # Verificar que se guardó
            cached_data = cache_general.get(cache_key)
            if cached_data:
                retrieved_data = json.loads(cached_data)
                print(f"✅ Cache de usuario: {len(retrieved_data['databases'])} empresas guardadas")
                success_count += 1
            
            # Cache de consultas (DB 2)
            cache_queries = redis.Redis(host=host, port=6379, db=2, decode_responses=True, socket_connect_timeout=5)
            
            query_result = {
                "query": "SELECT COUNT(*) FROM tabla_ejemplo",
                "result": 15420,
                "execution_time": 2.34,
                "cached_at": datetime.now().isoformat()
            }
            
            query_key = "query_cache_example"
            cache_queries.setex(query_key, 3600, json.dumps(query_result))
            
            if cache_queries.get(query_key):
                print("✅ Cache de consulta: Resultado guardado")
                success_count += 1
            
            # Cache de sesiones (DB 3)
            cache_sessions = redis.Redis(host=host, port=6379, db=3, socket_connect_timeout=5)
            
            session_data = {
                "user_id": 123,
                "database_name": "empresa1",
                "last_activity": datetime.now().isoformat()
            }
            
            session_key = "session_123456"
            cache_sessions.setex(session_key, 86400, json.dumps(session_data))  # 24 horas
            
            if cache_sessions.get(session_key):
                print("✅ Cache de sesión: Datos guardados")
                success_count += 1
            
            # Limpiar datos de prueba
            cache_general.delete(cache_key)
            cache_queries.delete(query_key)
            cache_sessions.delete(session_key)
            
            print("🧹 Datos de prueba limpiados")
            print()
            if success_count == 3:
                return True
                
        except Exception as e:
            print(f"   No se pudo simular caché en {host}: {e}")
            continue
    
    print("❌ No se pudo simular el uso de caché en ningún host")
    print()
    return False

def test_rq_queue():
    """Prueba RQ (Redis Queue) si está disponible."""
    print(f"⚙️  [{datetime.now().strftime('%H:%M:%S')}] Probando RQ (Redis Queue)...")
    
    if not RQ_AVAILABLE:
        print("❌ RQ no está instalado - saltando pruebas de cola")
        print()
        return False
    
    # Intentar primero localhost (desde host), luego redis (desde Docker)
    redis_hosts = ['localhost', 'redis']
    
    for host in redis_hosts:
        try:
            print(f"   Probando RQ en {host}:6379...")
            # Conectar a Redis para RQ
            conn = redis.Redis(host=host, port=6379, db=0, socket_connect_timeout=5)
            conn.ping()
            
            # Crear una cola
            q = Queue('test_queue', connection=conn)
            
            # Función simple para testear
            def simple_job(name):
                return f"Hola {name} desde RQ!"
            
            # Encolar un trabajo
            job = q.enqueue(simple_job, 'DataZenith')
            print(f"✅ Trabajo encolado: {job.id}")
            
            # Verificar estado
            print(f"📋 Estado del trabajo: {job.get_status()}")
            print(f"📊 Trabajos en cola: {len(q)}")
            
            # Limpiar
            job.delete()
            
            print("✅ RQ funciona correctamente")
            print()
            return True
            
        except Exception as e:
            print(f"   No se pudo probar RQ en {host}: {e}")
            continue
    
    print("❌ No se pudo probar RQ en ningún host")
    print()
    return False

def main():
    """Función principal del test."""
    print("=" * 60)
    print("🧪 PRUEBAS DE REDIS Y RQ - DataZenith BI")
    print("=" * 60)
    print()
    
    # Lista de pruebas
    tests = [
        ("Conexión Redis", test_redis_connection),
        ("Rendimiento Redis", test_redis_performance),
        ("Memoria Redis", test_redis_memory),
        ("Simulación de Caché", simulate_cache_usage),
        ("RQ Queue", test_rq_queue),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"🏃 Ejecutando: {test_name}")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name}: PASÓ")
            else:
                print(f"❌ {test_name}: FALLÓ")
        except Exception as e:
            print(f"💥 {test_name}: ERROR - {e}")
        
        print("-" * 40)
    
    # Resumen final
    print()
    print("=" * 60)
    print("📊 RESUMEN DE PRUEBAS")
    print("=" * 60)
    print(f"✅ Pruebas exitosas: {passed}/{total}")
    print(f"❌ Pruebas fallidas: {total - passed}/{total}")
    
    if passed == total:
        print("🎉 ¡TODAS LAS PRUEBAS PASARON!")
        print("   Redis y RQ están funcionando correctamente.")
    elif passed > total // 2:
        print("⚠️  La mayoría de pruebas pasaron.")
        print("   Revisa las que fallaron para optimizar el rendimiento.")
    else:
        print("🚨 Muchas pruebas fallaron.")
        print("   Verifica la configuración de Redis y Docker.")
    
    print()
    print("💡 Para optimizar más, revisa:")
    print("   - Configuración de Redis en settings.py")
    print("   - Conexiones de red entre Docker y host")
    print("   - Logs de Redis para errores específicos")
    print()
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
