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

### Arranque rápido con script (Windows)

Se incluye `start_server.bat` para levantar el stack y, si Docker Desktop no está activo, iniciarlo y esperar hasta que esté listo.

Uso (desde la carpeta del repo):

```powershell
./start_server.bat rq          # usa docker-compose.rq.yml
./start_server.bat server      # usa docker-compose.server.yml (abre http://localhost:30000)
./start_server.bat local       # usa docker-compose.local.yml
./start_server.bat rq --logs   # levanta y sigue logs
```

Detalles:
- Detecta automáticamente `docker compose` o `docker-compose`.
- Si Docker Desktop no responde, intenta abrirlo y espera hasta 120s.
- Con perfil `server` abre el navegador en el puerto 30000.

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

### Timeouts para tareas largas (RQ/Nginx/Gunicorn)

- Las tareas RQ usan un timeout configurable por entorno `RQ_TASK_TIMEOUT` (por defecto 28800s en server) y toman como fallback `RQ_QUEUES['default']['DEFAULT_TIMEOUT']`.
- En `adminbi/settings/prod.py` los timeouts de RQ están parametrizados vía variables de entorno (`RQ_DEFAULT_TIMEOUT`, `RQ_RESULT_TTL`, `RQ_FAILURE_TTL`).
- En `nginx.conf` se ampliaron los `proxy_read_timeout`/`proxy_send_timeout` para rutas generales, evitando cortes en respuestas lentas. Ajusta según tu necesidad.
- Gunicorn ya está configurado con `--timeout 28800` en `docker-compose.server.yml`.

Si una tarea se corta en producción pero no en local, verifica:
- Que el timeout del decorador `@job(..., timeout=...)` no sea menor al configurado.
- Valores de `RQ_DEFAULT_TIMEOUT` y `RQ_TASK_TIMEOUT` en el entorno de server.
- Los timeouts de Nginx (`proxy_read_timeout`) para la ruta usada por la vista.

### Calidad: bloqueo de archivos de 0 bytes

Se incluye un verificador `scripts/check_zero_byte_files.py` y un hook de git en `.githooks/pre-commit`.

Activación del hook:

1. Configura la ruta de hooks local:
   - Windows (PowerShell):
     - `git config core.hooksPath .githooks`
   - Linux/Mac:
     - `git config core.hooksPath .githooks`
2. Asegura permisos de ejecución (Linux/Mac): `chmod +x .githooks/pre-commit`

Ejecución manual del verificador:
- Todos los archivos: `python scripts/check_zero_byte_files.py --all`
- Solo stageados (modo pre-commit): `python scripts/check_zero_byte_files.py`

### Commit asistido con verificación (Windows .bat)

Se incluye un script para facilitar commits con control previo de archivos de 0 bytes:

- Ubicación: `commit_with_check.bat`
- Requisitos: Git y Python en el PATH.
- Qué hace:
  1) Ejecuta `scripts/check_zero_byte_files.py` sobre archivos stageados.
  2) Si todo está OK, hace `git add -A` y `git commit` con marca de tiempo `[fecha hora]` + tu comentario.

Uso (PowerShell o CMD):

```powershell
./commit_with_check.bat "Descripción corta del cambio (qué se agrega principalmente)"
```

Notas:
- Si no indicas comentario, usa "Actualizacion menor" por defecto.
- Si el verificador encuentra archivos de 0 bytes no permitidos, el commit se bloquea y se listan.
- Para auditar todo el repo (no solo stageados): `python scripts/check_zero_byte_files.py --all`
