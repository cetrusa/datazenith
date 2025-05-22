# DataZenithBi – Documentación General

## Descripción General

**DataZenithBi** es una plataforma de administración y actualización de datos orientada a la gestión de archivos y procesos ETL, desarrollada en Django. El sistema está optimizado para la manipulación eficiente de archivos planos, temporales y de bases de datos, integrando automatización de limpieza, tareas asíncronas y una experiencia de usuario robusta tanto para operaciones manuales como automáticas.

## Arquitectura y Componentes

- **Backend:** Django 4.2, con apps modulares (`home`, `bi`, `cargues`, `permisos`, `users`).
- **Tareas Asíncronas:** RQ y django-rq para ejecución de tareas en segundo plano.
- **Scheduler:** django-rq-scheduler y rq-scheduler para programación periódica de tareas.
- **Frontend:** Templates Django con AJAX para operaciones interactivas.
- **Contenedores:** Docker y docker-compose para despliegue y orquestación de servicios (web, worker, scheduler, redis).
- **Almacenamiento:** Carpeta `media/` para archivos temporales y de usuario.

## Flujos Principales

### 1. Limpieza de Archivos Viejos en `media/`

- **Automática:**  
  Se ejecuta periódicamente mediante una tarea programada con django-rq-scheduler.
  El servicio `rqscheduler` en Docker se encarga de disparar la tarea según la configuración.
- **Manual:**  
  Desde la interfaz web, usuarios staff pueden lanzar la limpieza mediante un botón AJAX en el panel de actualización.
  También disponible como comando Django desde terminal.
- **Post-borrado:**  
  Cada vez que un usuario elimina manualmente un archivo desde la interfaz, se ejecuta automáticamente la limpieza de archivos viejos.

### 2. Gestión de Archivos

- Subida, descarga y eliminación de archivos planos y temporales.
- Registro de auditoría y logs para todas las operaciones críticas.
- Integración con procesos ETL y generación de reportes.

## Estructura de Carpetas Relevante

```
adminbi/
  apps/
    home/
      views.py
      tasks.py
      utils.py      # Función central de limpieza
      urls.py
      apps.py
    ...
  requirements.txt
  requirements-docker.txt
  docker-compose.rq.yml
  Dockerfile
media/
```

## Automatización y Tareas Programadas

- **Función central:** `clean_old_media_files` en `apps/home/utils.py`
- **Tareas RQ:** Definidas en `apps/home/tasks.py`
- **Programación periódica:** Configurada en `apps/home/apps.py` usando django-rq-scheduler.
- **Servicio Docker:** `rqscheduler` en `docker-compose.rq.yml`

## Instalación y Despliegue

### Requisitos

- Python 3.12+
- Docker y Docker Compose
- Redis

### Instalación local

```bash
pip install -r requirements.txt
```

### Despliegue con Docker

```powershell
docker compose -f docker-compose.rq.yml build
docker compose -f docker-compose.rq.yml up -d
```

Esto levanta los servicios web, worker, redis y scheduler.

### Migraciones y superusuario

```bash
python manage.py migrate
python manage.py createsuperuser
```

## Uso de la Limpieza de Archivos

- **Manual desde web:**  
  Accede al panel de actualización y usa el botón "Limpiar archivos viejos".
- **Manual desde terminal:**  
  ```bash
  python manage.py clean_media_files
  ```
- **Automática:**  
  Se ejecuta periódicamente según la configuración del scheduler.

## Seguridad y Acceso

- Las vistas críticas están protegidas por autenticación y permisos staff.
- Los logs de auditoría registran todas las operaciones sensibles.

## Notas y Buenas Prácticas

- Mantén actualizados los requirements en todos los archivos usados por Docker.
- Si agregas nuevas extensiones de archivo a limpiar, actualiza la función en `utils.py`.
- Revisa los logs para monitorear la actividad de limpieza y posibles errores.
