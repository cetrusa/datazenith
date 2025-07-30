#!/bin/bash

# Script para configurar el servidor con variables de entorno
# Este script se ejecuta en el servidor para crear las configuraciones necesarias

set -e

echo "🔧 CONFIGURANDO SERVIDOR DATAZENITH BI"
echo "====================================="

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

# Verificar si estamos en el directorio correcto
if [ ! -f "docker-compose-server.yml" ]; then
    error "No se encontró docker-compose-server.yml. Ejecuta este script desde el directorio del proyecto."
    exit 1
fi

# Verificar si .env.server existe
if [ ! -f ".env.server" ]; then
    log "📋 Creando archivo .env.server desde plantilla..."
    
    if [ -f ".env.example" ]; then
        cp .env.example .env.server
        warn "⚠️  Se ha creado .env.server desde .env.example"
        warn "⚠️  IMPORTANTE: Edita .env.server con tus configuraciones reales antes de continuar"
        echo ""
        echo "Configuraciones que DEBES cambiar:"
        echo "  - DB_HOST, DB_NAME, DB_USER, DB_PASSWORD"
        echo "  - DJANGO_SECRET_KEY"
        echo "  - DJANGO_ALLOWED_HOSTS"
        echo "  - EMAIL_HOST_USER, EMAIL_HOST_PASSWORD"
        echo ""
        read -p "¿Has configurado .env.server con tus valores reales? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            error "Configura .env.server primero y luego ejecuta este script nuevamente."
            exit 1
        fi
    else
        error "No se encontró .env.example. No se puede crear .env.server automáticamente."
        exit 1
    fi
fi

# Cargar variables de entorno
log "📄 Cargando configuración desde .env.server..."
set -a  # automatically export all variables
source .env.server
set +a

# Validar configuraciones críticas
log "🔍 Validando configuraciones críticas..."

if [ -z "$DB_PASSWORD" ] || [ "$DB_PASSWORD" = "tu_password_super_seguro" ]; then
    error "DB_PASSWORD no está configurado o usa el valor por defecto"
    exit 1
fi

if [ -z "$DJANGO_SECRET_KEY" ] || [ "$DJANGO_SECRET_KEY" = "cambia-esta-clave-por-una-super-segura-de-50-caracteres-minimo" ]; then
    error "DJANGO_SECRET_KEY no está configurado o usa el valor por defecto"
    exit 1
fi

if [ "$DJANGO_ALLOWED_HOSTS" = "tu-dominio.com,www.tu-dominio.com,ip-del-servidor" ]; then
    warn "DJANGO_ALLOWED_HOSTS usa valores por defecto. Considera configurarlo para mayor seguridad."
fi

log "✅ Configuraciones básicas validadas"

# Crear directorios necesarios
log "📁 Creando directorios necesarios..."
mkdir -p logs staticfiles media backup

# Configurar permisos
log "🔒 Configurando permisos..."
chmod 755 logs staticfiles media
chmod 600 .env.server

# Generar secret key si es necesario
if [ -z "$DJANGO_SECRET_KEY" ]; then
    log "🔑 Generando nueva SECRET_KEY..."
    NEW_SECRET=$(python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
    sed -i "s/DJANGO_SECRET_KEY=.*/DJANGO_SECRET_KEY=$NEW_SECRET/" .env.server
    log "✅ Nueva SECRET_KEY generada"
fi

# Crear script de respaldo de configuración
log "💾 Creando script de respaldo..."
cat > backup_config.sh << 'EOF'
#!/bin/bash
# Script para hacer backup de la configuración
BACKUP_DIR="backup/$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR
cp .env.server $BACKUP_DIR/
cp docker-compose-server.yml $BACKUP_DIR/
cp nginx.conf $BACKUP_DIR/
echo "Backup creado en: $BACKUP_DIR"
EOF
chmod +x backup_config.sh

# Crear script de logs
log "📋 Creando script de monitoreo de logs..."
cat > view_logs.sh << 'EOF'
#!/bin/bash
echo "📋 LOGS DE DATAZENITH BI"
echo "========================="
echo "1. Logs de aplicación:"
echo "   docker-compose -f docker-compose-server.yml logs -f web"
echo ""
echo "2. Logs de worker:"
echo "   docker-compose -f docker-compose-server.yml logs -f rqworker"
echo ""
echo "3. Logs de Redis:"
echo "   docker-compose -f docker-compose-server.yml logs -f redis"
echo ""
echo "4. Logs de Nginx:"
echo "   docker-compose -f docker-compose-server.yml logs -f nginx"
echo ""
echo "5. Todos los logs:"
echo "   docker-compose -f docker-compose-server.yml logs -f"
echo ""
read -p "¿Qué logs quieres ver? (1-5): " choice
case $choice in
    1) docker-compose -f docker-compose-server.yml logs -f web ;;
    2) docker-compose -f docker-compose-server.yml logs -f rqworker ;;
    3) docker-compose -f docker-compose-server.yml logs -f redis ;;
    4) docker-compose -f docker-compose-server.yml logs -f nginx ;;
    5) docker-compose -f docker-compose-server.yml logs -f ;;
    *) echo "Opción inválida" ;;
esac
EOF
chmod +x view_logs.sh

# Información final
log "✅ CONFIGURACIÓN COMPLETADA"
echo "=============================="
echo ""
echo "📋 ARCHIVOS CREADOS:"
echo "   ✅ .env.server (configuración del servidor)"
echo "   ✅ backup_config.sh (script de respaldo)"
echo "   ✅ view_logs.sh (script para ver logs)"
echo ""
echo "📋 PRÓXIMOS PASOS:"
echo "   1. Revisar .env.server y ajustar configuraciones si es necesario"
echo "   2. Ejecutar: ./deploy-server.sh"
echo "   3. Verificar: curl http://localhost:30000/health/"
echo ""
echo "📋 COMANDOS ÚTILES:"
echo "   🔍 Ver logs: ./view_logs.sh"
echo "   💾 Backup: ./backup_config.sh"
echo "   🔄 Reiniciar: docker-compose -f docker-compose-server.yml restart"
echo "   ⏹️  Detener: docker-compose -f docker-compose-server.yml down"

log "🎉 Servidor listo para desplegar"
