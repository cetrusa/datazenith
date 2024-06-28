# Usamos la imagen oficial de Python 3.12 como imagen base
FROM python:3.12

# Crea un usuario y un grupo para ejecutar la aplicación
RUN groupadd -r interfacegroup && useradd -r -g interfacegroup adminuser

# Establecemos /code como el directorio de trabajo dentro del contenedor
WORKDIR /code

# Configuramos variables de entorno
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copiamos requirements-docker.txt a /code en el contenedor
COPY ./requirements-docker.txt .

# Instalamos las dependencias de Python desde requirements-docker.txt
RUN pip install --no-cache-dir -r requirements-docker.txt

# Copiamos todos los archivos y directorios al directorio de trabajo en el contenedor
COPY . .

# Ajustamos la zona horaria del contenedor
RUN ln -sf /usr/share/zoneinfo/America/Bogota /etc/localtime

# Ejecutamos el comando collectstatic de Django
RUN python manage.py collectstatic --no-input

# Cambiamos la propiedad y los permisos de los archivos estáticos
RUN chown -R adminuser:interfacegroup /code/staticfiles
RUN chmod -R 755 /code/staticfiles

# Crea la carpeta media y establece permisos adecuados
RUN mkdir -p /code/mediafiles
RUN chown -R adminuser:interfacegroup /code/mediafiles
RUN chmod -R 755 /code/mediafiles

# Cambiar al usuario no root
USER adminuser

# Comando para iniciar la aplicación
CMD ["gunicorn", "--bind", "0.0.0.0:4084", "--timeout", "28800", "adminbi.wsgi:application"]
