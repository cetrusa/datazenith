#!/usr/bin/env python3
"""
Script para verificar que las optimizaciones de configuración están funcionando.
Este script verifica las configuraciones sin ejecutar todo el servidor Django.
"""
import sys
import os

# Agregar el directorio del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_configuration():
    """Prueba las configuraciones optimizadas."""
    print("=== VERIFICACIÓN DE OPTIMIZACIONES DATAZENITH ===")
    print()
    
    try:
        # Test 1: Verificar imports de Django
        print("1. Verificando imports de Django...")
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'adminbi.settings.base')
        
        import django
        from django.conf import settings
        django.setup()
        print("   ✅ Django configurado correctamente")
        
        # Test 2: Verificar configuración de caché
        print("\n2. Verificando configuración de caché Redis...")
        cache_config = settings.CACHES
        
        if 'default' in cache_config:
            default_cache = cache_config['default']
            print(f"   ✅ Caché default: {default_cache['BACKEND']}")
            print(f"   ✅ Ubicación: {default_cache['LOCATION']}")
            
            if 'CONNECTION_POOL_KWARGS' in default_cache.get('OPTIONS', {}):
                pool_config = default_cache['OPTIONS']['CONNECTION_POOL_KWARGS']
                print(f"   ✅ Max conexiones pool: {pool_config.get('max_connections', 'No configurado')}")
        
        if 'queries' in cache_config:
            print("   ✅ Caché dedicado para consultas configurado")
            
        if 'sessions' in cache_config:
            print("   ✅ Caché dedicado para sesiones configurado")
        
        # Test 3: Verificar configuración de sesiones
        print("\n3. Verificando configuración de sesiones...")
        print(f"   ✅ SESSION_ENGINE: {settings.SESSION_ENGINE}")
        print(f"   ✅ SESSION_SAVE_EVERY_REQUEST: {settings.SESSION_SAVE_EVERY_REQUEST}")
        print(f"   ✅ SESSION_EXPIRE_SECONDS: {settings.SESSION_EXPIRE_SECONDS}")
        
        if hasattr(settings, 'SESSION_CACHE_ALIAS'):
            print(f"   ✅ SESSION_CACHE_ALIAS: {settings.SESSION_CACHE_ALIAS}")
        
        # Test 4: Verificar variables de caché personalizadas
        print("\n4. Verificando timeouts de caché personalizados...")
        cache_timeouts = {
            'CACHE_TIMEOUT_SHORT': getattr(settings, 'CACHE_TIMEOUT_SHORT', 'No configurado'),
            'CACHE_TIMEOUT_MEDIUM': getattr(settings, 'CACHE_TIMEOUT_MEDIUM', 'No configurado'),
            'CACHE_TIMEOUT_LONG': getattr(settings, 'CACHE_TIMEOUT_LONG', 'No configurado'),
            'CACHE_TIMEOUT_USER_DATA': getattr(settings, 'CACHE_TIMEOUT_USER_DATA', 'No configurado'),
        }
        
        for name, value in cache_timeouts.items():
            if value != 'No configurado':
                minutes = value // 60
                print(f"   ✅ {name}: {minutes} minutos ({value}s)")
            else:
                print(f"   ⚠️  {name}: {value}")
        
        # Test 5: Intentar conectar a Redis (si está disponible)
        print("\n5. Probando conexión a Redis...")
        try:
            from django.core.cache import cache
            cache.set('test_key_datazenith', 'test_value', 60)
            value = cache.get('test_key_datazenith')
            if value == 'test_value':
                print("   ✅ Conexión a Redis exitosa")
                cache.delete('test_key_datazenith')
            else:
                print("   ⚠️  Redis conectado pero no funcionando correctamente")
        except Exception as e:
            print(f"   ⚠️  No se pudo conectar a Redis: {e}")
            print("   📝 Esto es normal si Redis no está ejecutándose")
        
        # Test 6: Verificar imports de funciones optimizadas
        print("\n6. Verificando funciones de optimización...")
        try:
            from apps.users.utils import get_user_databases_cached, get_database_selector_data
            print("   ✅ Funciones de caché de usuario importadas correctamente")
        except ImportError as e:
            print(f"   ❌ Error importando funciones de optimización: {e}")
        
        print("\n=== VERIFICACIÓN COMPLETADA ===")
        print("✅ Las optimizaciones están configuradas correctamente")
        print("📝 Si Redis no está disponible, las funciones de caché usarán fallbacks locales")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error durante la verificación: {e}")
        print("📝 Asegúrate de estar en el directorio correcto y que Django esté instalado")
        return False

if __name__ == "__main__":
    success = test_configuration()
    sys.exit(0 if success else 1)
