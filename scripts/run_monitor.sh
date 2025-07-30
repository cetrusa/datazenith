#!/bin/bash
# Script para instalar y ejecutar el monitor de conexiones en Docker
# Este script debe ejecutarse desde el host Docker o dentro del contenedor

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Monitor de Conexiones DataZenith ===${NC}"
echo "Preparando entorno de monitoreo..."

# Verificar si estamos en Docker
if [ -f /.dockerenv ]; then
    echo -e "${YELLOW}Ejecutándose dentro de contenedor Docker${NC}"
    INSIDE_DOCKER=true
else
    echo -e "${YELLOW}Ejecutándose en host (fuera de Docker)${NC}"
    INSIDE_DOCKER=false
fi

# Función para instalar dependencias
install_dependencies() {
    echo "Instalando dependencias de Python..."
    if [ "$INSIDE_DOCKER" = true ]; then
        # Dentro del contenedor Docker
        pip install pymysql psutil
    else
        # En el host - usar el Python del proyecto
        pip install -r scripts/monitor_requirements.txt
    fi
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Dependencias instaladas correctamente${NC}"
    else
        echo -e "${RED}❌ Error instalando dependencias${NC}"
        exit 1
    fi
}

# Función para verificar archivo secret.json
check_secrets() {
    if [ ! -f "secret.json" ]; then
        echo -e "${RED}❌ Error: No se encontró secret.json${NC}"
        echo "Por favor, asegúrate de que secret.json existe en el directorio actual"
        echo "El archivo debe contener: DB_HOST, DB_USERNAME, DB_PASS, DB_PORT"
        exit 1
    fi
    echo -e "${GREEN}✅ Archivo secret.json encontrado${NC}"
}

# Función para ejecutar el monitor
run_monitor() {
    echo "Ejecutando monitor de conexiones..."
    python scripts/monitor_connections.py
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Monitor ejecutado correctamente${NC}"
    else
        echo -e "${RED}❌ Error ejecutando monitor${NC}"
        exit 1
    fi
}

# Función para configurar cron job (solo en Linux/host)
setup_cron() {
    if [ "$INSIDE_DOCKER" = false ] && command -v crontab >/dev/null 2>&1; then
        echo "¿Quieres configurar el monitor para ejecutarse automáticamente cada 5 minutos? (y/n)"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            # Crear entrada de cron
            SCRIPT_DIR=$(pwd)
            CRON_COMMAND="*/5 * * * * cd $SCRIPT_DIR && bash scripts/run_monitor.sh"
            
            # Agregar a crontab
            (crontab -l 2>/dev/null; echo "$CRON_COMMAND") | crontab -
            echo -e "${GREEN}✅ Cron job configurado - el monitor se ejecutará cada 5 minutos${NC}"
        fi
    fi
}

# Función principal
main() {
    # Verificar prerrequisitos
    check_secrets
    
    # Instalar dependencias
    install_dependencies
    
    # Ejecutar monitor
    run_monitor
    
    # Configurar ejecución automática (opcional)
    setup_cron
    
    echo -e "${GREEN}=== Monitor de Conexiones Completado ===${NC}"
    echo "Archivos generados:"
    echo "  - connection_monitor.log: Log detallado"
    echo "  - connection_stats.json: Estadísticas históricas"
    echo ""
    echo "Para ejecutar manualmente: python scripts/monitor_connections.py"
}

# Ejecutar función principal
main
