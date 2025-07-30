#!/usr/bin/env python
"""
Monitor de rendimiento simple para DataZenith BI
Uso: python manage.py shell < scripts/performance_monitor.py
"""

def check_performance():
    """Verificar el rendimiento del sistema"""
    print("🚀 MONITOR DE RENDIMIENTO DATAZENITH BI")
    print("=" * 50)
    
    # 1. Verificar configuración de sesiones
    from django.conf import settings
    print("📋 CONFIGURACIÓN:")
    print(f"  SESSION_ENGINE: {getattr(settings, 'SESSION_ENGINE', 'No configurado')}")
    print(f"  SESSION_SAVE_EVERY_REQUEST: {getattr(settings, 'SESSION_SAVE_EVERY_REQUEST', 'No configurado')}")
    print(f"  MIDDLEWARE con GZip: {'django.middleware.gzip.GZipMiddleware' in settings.MIDDLEWARE}")
    
    # 2. Verificar Redis
    try:
        from django.core.cache import cache
        cache.set('test_key', 'test_value', 10)
        result = cache.get('test_key')
        if result == 'test_value':
            print("  ✅ Redis funcionando correctamente")
        else:
            print("  ❌ Redis: problema de lectura/escritura")
        cache.delete('test_key')
    except Exception as e:
        print(f"  ❌ Redis error: {e}")
    
    # 3. Verificar base de datos
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            if result:
                print("  ✅ Base de datos MySQL conectada")
    except Exception as e:
        print(f"  ❌ MySQL error: {e}")
    
    # 4. Estadísticas de usuarios
    try:
        from apps.users.models import User
        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        print(f"  👥 Usuarios totales: {total_users}")
        print(f"  👥 Usuarios activos: {active_users}")
    except Exception as e:
        print(f"  ❌ Error usuarios: {e}")
    
    # 5. Estadísticas de empresas
    try:
        from apps.permisos.models import ConfEmpresas
        total_companies = ConfEmpresas.objects.count()
        print(f"  🏢 Empresas configuradas: {total_companies}")
    except Exception as e:
        print(f"  ❌ Error empresas: {e}")
    
    print("\n💡 RECOMENDACIONES:")
    print("  1. Reiniciar contenedores cada semana")
    print("  2. Monitorear logs de errores")
    print("  3. Limpiar caché si hay lentitud")
    print("  4. Verificar espacio en disco")
    print("\n✅ Monitor completado!")

# Ejecutar el monitor
if __name__ == "__main__":
    check_performance()
else:
    check_performance()
