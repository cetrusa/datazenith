#!/bin/bash

# Script de despliegue para servidor DataZenith BI
# Puerto: 30000

set -e

echo "🚀 INICIANDO DESPLIEGUE EN SERVIDOR - PUERTO 30000"
echo "=================================================="

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Función para mostrar mensajes
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

# Verificar si Docker está corriendo
if ! docker info > /dev/null 2>&1; then
    error "Docker no está corriendo. Por favor, inicia Docker primero."
    exit 1
fi

# Verificar si Docker Compose está disponible
if ! command -v docker-compose > /dev/null 2>&1; then
    error "Docker Compose no está instalado."
    exit 1
fi

log "✅ Docker y Docker Compose están disponibles"

# Cargar variables de entorno
if [ -f .env.server ]; then
    log "📄 Cargando variables de entorno desde .env.server"
    export $(cat .env.server | grep -v '#' | xargs)
else
    warn "Archivo .env.server no encontrado. Usando valores por defecto."
fi

# Verificar puertos disponibles
log "🔍 Verificando disponibilidad del puerto 30000..."
if lsof -Pi :30000 -sTCP:LISTEN -t >/dev/null ; then
    warn "Puerto 30000 ya está en uso. Deteniendo servicios existentes..."
    docker-compose -f docker-compose-server.yml down --remove-orphans
fi

# Crear directorios necesarios
log "📁 Creando directorios necesarios..."
mkdir -p logs staticfiles media

# Limpiar contenedores e imágenes anteriores
log "🧹 Limpiando contenedores e imágenes anteriores..."
docker-compose -f docker-compose-server.yml down --volumes --remove-orphans || true
docker system prune -f || true

# Construir imágenes
log "🔨 Construyendo imágenes desde cero..."
docker-compose -f docker-compose-server.yml build --no-cache --force-rm

# Verificar construcción exitosa
if [ $? -eq 0 ]; then
    log "✅ Imágenes construidas exitosamente"
else
    error "❌ Error al construir las imágenes"
    exit 1
fi

# Iniciar servicios
log "🚀 Iniciando servicios..."
docker-compose -f docker-compose-server.yml up -d

# Esperar a que los servicios estén listos
log "⏳ Esperando a que los servicios estén listos..."
sleep 30

# Verificar estado de los servicios
log "🔍 Verificando estado de los servicios..."
docker-compose -f docker-compose-server.yml ps

# Health check
log "🏥 Realizando health check..."
max_attempts=10
attempt=1

while [ $attempt -le $max_attempts ]; do
    if curl -f http://localhost:30000/health/ > /dev/null 2>&1; then
        log "✅ Aplicación está respondiendo correctamente en puerto 30000"
        break
    else
        warn "Intento $attempt/$max_attempts: Aplicación aún no responde..."
        sleep 10
        ((attempt++))
    fi
done

if [ $attempt -gt $max_attempts ]; then
    error "❌ La aplicación no respondió después de $max_attempts intentos"
    log "📋 Mostrando logs para diagnóstico..."
    docker-compose -f docker-compose-server.yml logs --tail=50
    exit 1
fi

# Mostrar información final
log "🎉 DESPLIEGUE COMPLETADO EXITOSAMENTE"
echo "=================================================="
echo -e "${BLUE}📊 INFORMACIÓN DEL DESPLIEGUE:${NC}"
echo -e "${BLUE}   🌐 URL: http://localhost:30000${NC}"
echo -e "${BLUE}   🐳 Contenedores activos:${NC}"
docker-compose -f docker-compose-server.yml ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo -e "${BLUE}📋 COMANDOS ÚTILES:${NC}"
echo -e "${BLUE}   Ver logs: docker-compose -f docker-compose-server.yml logs -f${NC}"
echo -e "${BLUE}   Detener: docker-compose -f docker-compose-server.yml down${NC}"
echo -e "${BLUE}   Reiniciar: docker-compose -f docker-compose-server.yml restart${NC}"
echo -e "${BLUE}   Estado: docker-compose -f docker-compose-server.yml ps${NC}"

log "✅ Despliegue finalizado correctamente"
