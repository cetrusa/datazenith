import paramiko
import logging
import os
from dotenv import load_dotenv
import time

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# Configuración de Logging
logging.basicConfig(filename='log.txt', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Configuración del servidor SSH
HOST = "10.0.142.29"
PORT = 22
USERNAME = "admon"
PASSWORD = os.getenv("SSH_PASSWORD")  # Utiliza la variable de entorno cargada

# Comandos a ejecutar (sin pedir contraseña)
CHMOD_COMMAND = "sudo -n chmod +x /var/www/datazenith/manage_data_datazenith.sh"
COMMAND = "sudo -n /var/www/datazenith/manage_data_datazenith.sh"

def execute_ssh_command(host, port, username, password, command):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(host, port=port, username=username, password=password)
        logger.info(f"Conexión establecida con {host}:{port} como {username}")

        # Ejecutar comando sin perfil de usuario cargado
        stdin, stdout, stderr = ssh.exec_command(command)

        # Leer la salida
        out = stdout.read().decode('utf-8')
        err = stderr.read().decode('utf-8')

        if out:
            logger.debug(f"STDOUT: {out}")
        if err:
            logger.error(f"STDERR: {err}")

    except paramiko.AuthenticationException:
        logger.error("Fallo de autenticación")
    except paramiko.SSHException as e:
        logger.error(f"Error en la conexión SSH: {e}")
    except Exception as e:
        logger.error(f"Error inesperado: {e}")
    finally:
        ssh.close()
        logger.info("Conexión SSH cerrada")

# Ejecutar comandos
logger.info("Cambiando permisos del script")
execute_ssh_command(HOST, PORT, USERNAME, PASSWORD, CHMOD_COMMAND)

logger.info("Ejecutando el script de administración de datos")
execute_ssh_command(HOST, PORT, USERNAME, PASSWORD, COMMAND)