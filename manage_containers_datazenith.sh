#!/bin/bash

# Detener contenedores específicos
docker stop datazenith_rqworker_1 datazenith_web_1 datazenith_redis_1

# Eliminar contenedores específicos
docker rm datazenith_rqworker_1 datazenith_web_1 datazenith_redis_1

# Limpiar el sistema Docker sin confirmación
docker system prune -f

# Navegar al directorio del proyecto
cd /var/www/datazenith

# Eliminar la base de datos SQLite
rm -f mydata.db

# Activar el entorno virtual de Python
source /venv/bin/activate

# Levantar los servicios con docker-compose
docker-compose -f docker-compose.rq.yml up -d --build
