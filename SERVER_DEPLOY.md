# 🚀 DataZenith BI - Despliegue en Servidor

Este README explica cómo desplegar DataZenith BI en un servidor usando Docker con puerto 30000.

## 📋 Requisitos Previos

- Docker y Docker Compose instalados
- Git instalado
- Puerto 30000 disponible
- Acceso a base de datos MySQL/MariaDB

## 🔒 Configuración de Seguridad

### Archivos que NO están en Git (por seguridad):
- `.env.server` - Configuraciones sensibles del servidor
- `secret.json` - Claves secretas
- `logs/` - Archivos de log
- `media/` - Archivos subidos por usuarios
- `*.db` - Bases de datos locales

## 🚀 Instalación Paso a Paso

### 1. Clonar el repositorio
```bash
git clone https://github.com/cetrusa/datazenith.git
cd datazenith/adminbi
```

### 2. Configurar el servidor
```bash
# Hacer ejecutable el script de configuración
chmod +x configure-server.sh

# Ejecutar configuración inicial
./configure-server.sh
```

### 3. Editar configuraciones
```bash
# Editar el archivo de configuración con tus datos reales
nano .env.server
```

**Configuraciones CRÍTICAS que debes cambiar:**
```env
# Base de datos
DB_HOST=tu-servidor-mysql
DB_NAME=tu-base-de-datos
DB_USER=tu-usuario
DB_PASSWORD=tu-password-seguro

# Django
DJANGO_SECRET_KEY=genera-una-clave-super-segura-de-50-caracteres
DJANGO_ALLOWED_HOSTS=tu-dominio.com,www.tu-dominio.com,123.456.789.123

# Email
EMAIL_HOST_USER=tu-email@gmail.com
EMAIL_HOST_PASSWORD=tu-password-de-aplicacion
```

### 4. Desplegar
```bash
# Hacer ejecutable el script de despliegue
chmod +x deploy-server.sh

# Ejecutar despliegue
./deploy-server.sh
```

### 5. Verificar
```bash
# Verificar que la aplicación responde
curl http://localhost:30000/health/

# Ver logs
./view_logs.sh
```

## 🔧 Comandos Útiles

### Gestión de contenedores:
```bash
# Ver estado
docker-compose -f docker-compose-server.yml ps

# Ver logs en tiempo real
docker-compose -f docker-compose-server.yml logs -f

# Reiniciar todos los servicios
docker-compose -f docker-compose-server.yml restart

# Reiniciar solo la aplicación web
docker-compose -f docker-compose-server.yml restart web

# Detener todos los servicios
docker-compose -f docker-compose-server.yml down

# Reconstruir y reiniciar
docker-compose -f docker-compose-server.yml up -d --build
```

### Gestión de datos:
```bash
# Hacer backup de configuración
./backup_config.sh

# Acceder al contenedor de la aplicación
docker-compose -f docker-compose-server.yml exec web bash

# Ejecutar comandos Django
docker-compose -f docker-compose-server.yml exec web python manage.py migrate
docker-compose -f docker-compose-server.yml exec web python manage.py createsuperuser
docker-compose -f docker-compose-server.yml exec web python manage.py collectstatic
```

## 🌐 Acceso a la Aplicación

- **URL Principal:** http://tu-servidor:30000
- **Health Check:** http://tu-servidor:30000/health/
- **Admin Django:** http://tu-servidor:30000/admin/

## 🔍 Solución de Problemas

### La aplicación no responde:
```bash
# Ver logs de la aplicación
docker-compose -f docker-compose-server.yml logs web

# Verificar estado de contenedores
docker-compose -f docker-compose-server.yml ps

# Reiniciar la aplicación
docker-compose -f docker-compose-server.yml restart web
```

### Error de base de datos:
```bash
# Verificar configuración de BD en .env.server
cat .env.server | grep DB_

# Probar conexión a la BD desde el contenedor
docker-compose -f docker-compose-server.yml exec web python manage.py dbshell
```

### Problemas de permisos:
```bash
# Verificar permisos de archivos
ls -la logs/ staticfiles/ media/

# Corregir permisos si es necesario
sudo chown -R $USER:$USER logs/ staticfiles/ media/
chmod 755 logs/ staticfiles/ media/
```

### Limpiar y empezar desde cero:
```bash
# Detener y limpiar todo
docker-compose -f docker-compose-server.yml down --volumes --remove-orphans

# Limpiar imágenes
docker system prune -a -f

# Volver a desplegar
./deploy-server.sh
```

## 📊 Monitoreo

### Logs importantes:
- `logs/access.log` - Logs de acceso HTTP
- `logs/error.log` - Logs de errores de la aplicación
- `logs/django.log` - Logs específicos de Django

### Métricas de sistema:
```bash
# Uso de recursos por contenedor
docker stats

# Espacio en disco
df -h

# Uso de memoria
free -h
```

## 🛡️ Seguridad

### Headers de seguridad configurados:
- X-Frame-Options: SAMEORIGIN
- X-Content-Type-Options: nosniff
- X-XSS-Protection: 1; mode=block
- Referrer-Policy: strict-origin-when-cross-origin

### Rate limiting:
- Login: 5 requests/minuto
- API: 100 requests/minuto

### Recomendaciones adicionales:
1. Usar HTTPS en producción
2. Configurar firewall para limitar acceso al puerto 30000
3. Hacer backups regulares de la base de datos
4. Mantener actualizadas las imágenes Docker
5. Rotar las claves secretas periódicamente

## 📞 Soporte

Si tienes problemas:
1. Revisa los logs: `./view_logs.sh`
2. Verifica la configuración: `cat .env.server`
3. Prueba el health check: `curl http://localhost:30000/health/`
4. Reinicia los servicios: `docker-compose -f docker-compose-server.yml restart`
