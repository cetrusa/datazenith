from django.contrib import messages
import subprocess
from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
import os
from django.http import HttpResponse, FileResponse, JsonResponse
import io
from django.views.generic import View
from django.utils.decorators import method_decorator
from apps.users.decorators import registrar_auditoria
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponseRedirect
from scripts.conexion import Conexion
from scripts.config import ConfigBasic
from scripts.StaticPage import StaticPage, DinamicPage
from scripts.extrae_bi.extrae_bi_call import Extrae_Bi
from scripts.extrae_bi.interface import InterfaceContable
from django.contrib.auth.mixins import UserPassesTestMixin
from .tasks import cubo_ventas_task, interface_task, plano_task, extrae_bi_task
from django.http import JsonResponse
from django.views import View
from apps.users.models import UserPermission

# importaciones para celery
# from celery.result import AsyncResult

# importaciones para rq
from django_rq import get_queue
from rq.job import Job
from rq.job import NoSuchJobError
from django_rq import get_connection

from django.views.generic import TemplateView
from apps.users.views import BaseView
import logging

logger = logging.getLogger(__name__)


class HomePanelCuboPage(LoginRequiredMixin, BaseView):
    template_name = "home/panel_cubo.html"

    login_url = reverse_lazy("users_app:user-login")

    def post(self, request, *args, **kwargs):
        request.session["template_name"] = self.template_name
        database_name = request.POST.get("database_select")
        if not database_name:
            return redirect("home_app:panel_cubo")

        request.session["database_name"] = database_name
        StaticPage.name = database_name

        return redirect("home_app:panel_cubo")

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_url"] = "home_app:panel_cubo"
        return context


class HomePanelBiPage(LoginRequiredMixin, BaseView):
    template_name = "home/panel_bi.html"

    login_url = reverse_lazy("users_app:user-login")

    def post(self, request, *args, **kwargs):
        request.session["template_name"] = self.template_name
        database_name = request.POST.get("database_select")
        if not database_name:
            return redirect("home_app:panel_bi")

        request.session["database_name"] = database_name
        StaticPage.name = database_name

        return redirect("home_app:panel_bi")

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_url"] = "home_app:panel_bi"
        return context


class HomePanelActualizacionPage(LoginRequiredMixin, BaseView):
    template_name = "home/panel_actualizacion.html"

    login_url = reverse_lazy("users_app:user-login")

    def post(self, request, *args, **kwargs):
        request.session["template_name"] = self.template_name
        database_name = request.POST.get("database_select")
        if not database_name:
            return redirect("home_app:panel_actualizacion")

        request.session["database_name"] = database_name
        StaticPage.name = database_name

        return redirect("home_app:panel_actualizacion")

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_url"] = "home_app:panel_actualizacion"
        return context


class HomePanelInterfacePage(LoginRequiredMixin, BaseView):
    template_name = "home/panel_interface.html"

    login_url = reverse_lazy("users_app:user-login")

    def post(self, request, *args, **kwargs):
        request.session["template_name"] = self.template_name
        database_name = request.POST.get("database_select")
        if not database_name:
            return redirect("home_app:panel_interface")

        request.session["database_name"] = database_name
        StaticPage.name = database_name

        return redirect("home_app:panel_interface")

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_url"] = "home_app:panel_interface"
        return context


class DownloadFileView(View):
    login_url = reverse_lazy("users_app:user-login")

    def get(self, request):
        template_name = request.session.get("template_name", "home/panel_cubo.html")
        file_path = request.session.get("file_path")
        file_name = request.session.get("file_name")

        if file_path and file_name:
            try:
                f = open(file_path, "rb")
                response = FileResponse(f)
                response["Content-Disposition"] = f'attachment; filename="{file_name}"'
                response["Content-Length"] = os.path.getsize(file_path)
                return response
            except IOError:
                messages.error(request, "Error al abrir el archivo")
        else:
            messages.error(request, "Archivo no encontrado")
        return render(request, "home/panel_cubo.html", {"template_name": template_name})


class DeleteFileView(View):
    login_url = reverse_lazy("users_app:user-login")

    def post(self, request):
        template_name = request.session.get("template_name")
        file_path = request.session.get("file_path")

        if file_path is None:
            return JsonResponse(
                {"success": False, "error_message": "No hay archivo para eliminar."}
            )

        try:
            os.remove(file_path)
            del request.session["file_path"]
            del request.session["file_name"]
            return JsonResponse({"success": True})
        except FileNotFoundError:
            return JsonResponse(
                {"success": False, "error_message": "El archivo no existe."}
            )
        except Exception as e:
            return JsonResponse(
                {
                    "success": False,
                    "error_message": f"Error: no se pudo ejecutar el script. Razón: {str(e)}",
                }
            )


class CheckTaskStatusView(BaseView):
    """
    Vista para comprobar el estado de una tarea asincrónica y recuperar su resultado.

    Esta vista espera recibir un ID de tarea y devuelve el estado de la tarea,
    así como su resultado si la tarea ha finalizado correctamente.
    """

    def post(self, request, *args, **kwargs):
        """
        Maneja la solicitud POST para comprobar el estado de una tarea asincrónica.

        :param request: Objeto HttpRequest.
        :return: JsonResponse con el estado de la tarea o un mensaje de error.
        """
        task_id = request.POST.get("task_id")
        if not task_id:
            return JsonResponse({"error": "No task ID provided"}, status=400)

        connection = get_connection()
        try:
            job = Job.fetch(task_id, connection=connection)
            if job.is_finished:
                return self.handle_finished_job(request, job)
            elif job.is_failed:
                return JsonResponse(
                    {"status": "failed", "result": job.result}, status=500
                )
            else:
                return JsonResponse({"status": job.get_status()})

        except NoSuchJobError:
            return JsonResponse({"status": "notfound", "error": "Task not found"})

    def handle_finished_job(self, request, job):
        """
        Maneja el caso cuando una tarea ha finalizado.

        :param request: Objeto HttpRequest.
        :param job: Objeto Job que representa la tarea finalizada.
        :return: JsonResponse con el resultado de la tarea o un mensaje de error.
        """
        resultado = job.result
        if resultado is None:
            return JsonResponse({"error": "Task finished with no result"}, status=500)

        response_data = {"status": "finished", "result": resultado}

        # Si el resultado fue exitoso, agregamos los detalles necesarios
        if resultado.get("success"):
            # Solo agrega file_path y file_name a la sesión si están presentes
            if "file_path" in resultado and "file_name" in resultado:
                request.session["file_path"] = resultado["file_path"]
                request.session["file_name"] = resultado["file_name"]
                # Podrías querer incluir también esta información en la respuesta
                response_data.update(
                    {
                        "file_path": resultado["file_path"],
                        "file_name": resultado["file_name"],
                    }
                )

            # Agregar datos de tabla a la sesión si están presentes
            if "data" in resultado:
                request.session["data_headers"] = resultado["data"]["headers"]
                request.session["data_rows"] = resultado["data"]["rows"]

            return JsonResponse(response_data)

        # Si el resultado no fue exitoso o no cumple con las expectativas
        return JsonResponse(
            {"error": "Task completed but result is not as expected"}, status=500
        )


class CuboPage(LoginRequiredMixin, BaseView):
    """
    Vista para la página de generación del Cubo de Ventas.

    Esta vista maneja la solicitud del usuario para generar un cubo de ventas,
    iniciando una tarea en segundo plano y devolviendo el ID de dicha tarea.
    """

    template_name = "home/cubo.html"
    login_url = reverse_lazy("users_app:user-login")

    @method_decorator(registrar_auditoria)
    @method_decorator(permission_required("permisos.cubo", raise_exception=True))
    def dispatch(self, request, *args, **kwargs):
        """
        Método para despachar la solicitud, aplicando decoradores de auditoría y permisos requeridos.
        """
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """
        Maneja la solicitud POST para iniciar el proceso de generación del cubo de ventas.

        Recoge los datos del formulario, valida la entrada y, si es válida,
        inicia una tarea asincrónica para generar el cubo de ventas.
        """
        database_name = request.POST.get("database_select")
        IdtReporteIni = request.POST.get("IdtReporteIni")
        IdtReporteFin = request.POST.get("IdtReporteFin")
        user_id = request.user.id
        request.session["template_name"] = self.template_name

        if not all([database_name, IdtReporteIni, IdtReporteFin]):
            return JsonResponse(
                {
                    "success": False,
                    "error_message": "Se debe seleccionar la base de datos y las fechas.",
                },
                status=400,
            )

        try:
            report_id = 1  # CUBO DE VENTAS
            task = cubo_ventas_task.delay(
                database_name, IdtReporteIni, IdtReporteFin, user_id, report_id
            )
            request.session["task_id"] = task.id
            return JsonResponse({"success": True, "task_id": task.id})
        except Exception as e:
            return JsonResponse(
                {"success": False, "error_message": f"Error: {str(e)}"}, status=500
            )

    def get(self, request, *args, **kwargs):
        """
        Maneja la solicitud GET, devolviendo la plantilla de la página del cubo de ventas.
        """
        database_name = request.session.get("database_name")
        if not database_name:
            messages.warning(
                request, "Debe seleccionar una empresa antes de continuar."
            )
            return redirect("home_app:panel_cubo")

        context = self.get_context_data(**kwargs)
        context["data"] = None
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        """
        Obtiene el contexto necesario para la plantilla.

        :return: Contexto que incluye la URL del formulario y los filtros de permisos.
        """
        context = super().get_context_data(**kwargs)
        context["form_url"] = "home_app:cubo"

        # Obtener permisos de macrozona y proveedor para el usuario
        user_id = self.request.user.id
        database_name = self.request.session.get("database_name")
        if database_name:
            config = ConfigBasic(database_name, user_id)
            context["proveedores"] = config.config.get("proveedores", [])
            context["macrozonas"] = config.config.get("macrozonas", [])

        return context

    # def get_data_from_task(self, request):
    #     """
    #     Obtiene los datos de la tarea almacenados en la sesión.
    #     """
    #     task_id = request.session.get("task_id")
    #     if not task_id:
    #         return None

    #     connection = get_connection()
    #     try:
    #         job = Job.fetch(task_id, connection=connection)
    #         if job.is_finished and job.result:
    #             return job.result.get("data", None)
    #     except NoSuchJobError:
    #         return None


class ProveedorPage(LoginRequiredMixin, BaseView):
    """
    Vista para la página de generación del Cubo de Ventas.

    Esta vista maneja la solicitud del usuario para generar un cubo de ventas,
    iniciando una tarea en segundo plano y devolviendo el ID de dicha tarea.
    """

    template_name = "home/proveedor.html"
    login_url = reverse_lazy("users_app:user-login")

    @method_decorator(registrar_auditoria)
    @method_decorator(permission_required("permisos.proveedor", raise_exception=True))
    def dispatch(self, request, *args, **kwargs):
        """
        Método para despachar la solicitud, aplicando decoradores de auditoría y permisos requeridos.
        """
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """
        Maneja la solicitud POST para iniciar el proceso de generación del cubo de ventas.

        Recoge los datos del formulario, valida la entrada y, si es válida,
        inicia una tarea asincrónica para generar el cubo de ventas.
        """
        database_name = request.POST.get("database_select")
        IdtReporteIni = request.POST.get("IdtReporteIni")
        IdtReporteFin = request.POST.get("IdtReporteFin")
        user_id = request.user.id
        request.session["template_name"] = self.template_name

        if not all([database_name, IdtReporteIni, IdtReporteFin]):
            return JsonResponse(
                {
                    "success": False,
                    "error_message": "Se debe seleccionar la base de datos y las fechas.",
                },
                status=400,
            )

        try:
            report_id = 2  # PROVEEDORES
            task = cubo_ventas_task.delay(
                database_name, IdtReporteIni, IdtReporteFin, user_id, report_id
            )
            request.session["task_id"] = task.id
            return JsonResponse({"success": True, "task_id": task.id})
        except Exception as e:
            return JsonResponse(
                {"success": False, "error_message": f"Error: {str(e)}"}, status=500
            )

    def get(self, request, *args, **kwargs):
        """
        Maneja la solicitud GET, devolviendo la plantilla de la página del cubo de ventas.
        """
        database_name = request.session.get("database_name")
        if not database_name:
            messages.warning(
                request, "Debe seleccionar una empresa antes de continuar."
            )
            return redirect("home_app:panel_cubo")

        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        """
        Obtiene el contexto necesario para la plantilla.

        :return: Contexto que incluye la URL del formulario y los filtros de permisos.
        """
        context = super().get_context_data(**kwargs)
        context["form_url"] = "home_app:proveedor"

        # Obtener permisos de macrozona y proveedor para el usuario
        user_id = self.request.user.id
        database_name = self.request.session.get("database_name")
        if database_name:
            config = ConfigBasic(database_name, user_id)
            context["proveedores"] = config.config.get("proveedores", [])
            context["macrozonas"] = config.config.get("macrozonas", [])

        return context


class InterfacePage(LoginRequiredMixin, BaseView):
    """
    Vista para la página de generación de Interface Contable.

    Esta vista maneja la solicitud del usuario para generar una interface contable,
    iniciando una tarea en segundo plano y devolviendo el ID de dicha tarea.
    """

    # Nombre de la plantilla a utilizar para renderizar la vista
    template_name = "home/interface.html"

    # URL para redirigir en caso de que el usuario no esté autenticado
    login_url = reverse_lazy("users_app:user-login")
    print("aqui estoy en interfacepage")

    @method_decorator(registrar_auditoria)
    @method_decorator(permission_required("permisos.interface", raise_exception=True))
    def dispatch(self, request, *args, **kwargs):
        """
        Método para despachar la solicitud, aplicando decoradores de auditoría y
        permisos requeridos.
        """
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """
        Maneja la solicitud POST para iniciar el proceso de generación de la interface.

        Recoge los datos del formulario, valida la entrada y, si es válida,
        inicia una tarea asincrónica para generar el cubo de ventas.
        """
        database_name = request.POST.get("database_select")
        IdtReporteIni = request.POST.get("IdtReporteIni")
        IdtReporteFin = request.POST.get("IdtReporteFin")
        request.session["template_name"] = self.template_name
        print("aqui estoy en interfacepage en el post")
        if not all([database_name, IdtReporteIni, IdtReporteFin]):
            return JsonResponse(
                {
                    "success": False,
                    "error_message": "Se debe seleccionar la base de datos y las fechas.",
                },
                status=400,
            )

        try:
            print(
                "aqui estoy en interfacepage en el try antes de task = interface_task.delay"
            )
            task = interface_task.delay(database_name, IdtReporteIni, IdtReporteFin)
            print(
                "aqui estoy en interfacepage en el try despues de task = interface_task.delay"
            )
            request.session["task_id"] = task.id
            return JsonResponse({"success": True, "task_id": task.id})
        except Exception as e:
            return JsonResponse(
                {"success": False, "error_message": f"Error: {str(e)}"}, status=500
            )

    def get(self, request, *args, **kwargs):
        """
        Maneja la solicitud GET, devolviendo la plantilla de la página del cubo de ventas.
        """
        database_name = request.session.get("database_name")
        if not database_name:
            messages.warning(
                request, "Debe seleccionar una empresa antes de continuar."
            )
            return redirect("home_app:panel_cubo")

        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        """
        Obtiene el contexto necesario para la plantilla.

        :return: Contexto que incluye la URL del formulario y los filtros de permisos.
        """
        context = super().get_context_data(**kwargs)
        context["form_url"] = "home_app:interface"

        # Obtener permisos de macrozona y proveedor para el usuario
        user_id = self.request.user.id
        database_name = self.request.session.get("database_name")
        if database_name:
            config = ConfigBasic(database_name, user_id)
            context["proveedores"] = config.config.get("proveedores", [])
            context["macrozonas"] = config.config.get("macrozonas", [])

        return context


class PlanoPage(LoginRequiredMixin, BaseView):
    """
    Vista para la página de generación de Interface Contable.

    Esta vista maneja la solicitud del usuario para generar una interface contable,
    iniciando una tarea en segundo plano y devolviendo el ID de dicha tarea.
    """

    # Nombre de la plantilla a utilizar para renderizar la vista
    template_name = "home/plano.html"

    # URL para redirigir en caso de que el usuario no esté autenticado
    login_url = reverse_lazy("users_app:user-login")

    @method_decorator(registrar_auditoria)
    @method_decorator(permission_required("permisos.plano", raise_exception=True))
    def dispatch(self, request, *args, **kwargs):
        """
        Método para despachar la solicitud, aplicando decoradores de auditoría y
        permisos requeridos.
        """
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """
        Maneja la solicitud POST para iniciar el proceso de generación de la interface.

        Recoge los datos del formulario, valida la entrada y, si es válida,
        inicia una tarea asincrónica para generar el cubo de ventas.
        """
        database_name = request.POST.get("database_select")
        IdtReporteIni = request.POST.get("IdtReporteIni")
        IdtReporteFin = request.POST.get("IdtReporteFin")
        request.session["template_name"] = self.template_name

        if not all([database_name, IdtReporteIni, IdtReporteFin]):
            return JsonResponse(
                {
                    "success": False,
                    "error_message": "Se debe seleccionar la base de datos y las fechas.",
                },
                status=400,
            )

        try:
            task = plano_task.delay(database_name, IdtReporteIni, IdtReporteFin)
            request.session["task_id"] = task.id
            return JsonResponse({"success": True, "task_id": task.id})
        except Exception as e:
            return JsonResponse(
                {"success": False, "error_message": f"Error: {str(e)}"}, status=500
            )

    def get(self, request, *args, **kwargs):
        """
        Maneja la solicitud GET, devolviendo la plantilla de la página del cubo de ventas.
        """
        database_name = request.session.get("database_name")
        if not database_name:
            messages.warning(
                request, "Debe seleccionar una empresa antes de continuar."
            )
            return redirect("home_app:panel_cubo")

        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        """
        Obtiene el contexto necesario para la plantilla.

        :return: Contexto que incluye la URL del formulario y los filtros de permisos.
        """
        context = super().get_context_data(**kwargs)
        context["form_url"] = "home_app:plano"

        # Obtener permisos de macrozona y proveedor para el usuario
        user_id = self.request.user.id
        database_name = self.request.session.get("database_name")
        if database_name:
            config = ConfigBasic(database_name, user_id)
            context["proveedores"] = config.config.get("proveedores", [])
            context["macrozonas"] = config.config.get("macrozonas", [])

        return context


class ActualizacionPage(LoginRequiredMixin, BaseView):
    template_name = "home/actualizacion.html"
    login_url = reverse_lazy("users_app:user-login")

    @method_decorator(registrar_auditoria)
    @method_decorator(
        permission_required("permisos.actualizar_base", raise_exception=True)
    )
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        request.session["template_name"] = self.template_name
        database_name = request.POST.get("database_select")
        IdtReporteIni = request.POST.get("IdtReporteIni")
        IdtReporteFin = request.POST.get("IdtReporteFin")

        if not all([database_name, IdtReporteIni, IdtReporteFin]):
            return JsonResponse(
                {
                    "success": False,
                    "error_message": "Se debe seleccionar la base de datos y las fechas.",
                },
                status=400,
            )

        try:
            task = extrae_bi_task.delay(database_name, IdtReporteIni, IdtReporteFin)
            request.session["task_id"] = task.id
            return JsonResponse(
                {
                    "success": True,
                    "task_id": task.id,
                }
            )
        except Exception as e:
            return JsonResponse({"success": False, "error_message": f"Error: {str(e)}"})

    def get(self, request, *args, **kwargs):
        database_name = request.session.get("database_name")
        if not database_name:
            messages.warning(
                request, "Debe seleccionar una empresa antes de continuar."
            )
            return redirect("home_app:panel_cubo")

        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_url"] = "home_app:actualizacion"

        user_id = self.request.user.id
        database_name = self.request.session.get("database_name")
        if database_name:
            config = ConfigBasic(database_name, user_id)
            context["proveedores"] = config.config.get("proveedores", [])
            context["macrozonas"] = config.config.get("macrozonas", [])

        return context


class PruebaPage(LoginRequiredMixin, BaseView):
    template_name = "home/prueba.html"

    login_url = reverse_lazy("users_app:user-login")

    def post(self, request, *args, **kwargs):
        request.session["template_name"] = self.template_name
        # database_name = request.session.get('database_name') or request.POST.get('database_select')
        database_name = request.POST.get("database_select")
        if not database_name:
            return redirect("home_app:panel_cubo")

        request.session["database_name"] = database_name
        StaticPage.name = database_name
        if not database_name:
            return JsonResponse(
                {
                    "success": False,
                    "error_message": "Debe seleccionar una base de datos.",
                }
            )

    def get(self, request, *args, **kwargs):
        """
        Maneja la solicitud GET, devolviendo la plantilla de la página del cubo de ventas.
        """
        database_name = request.session.get("database_name")
        if not database_name:
            messages.warning(
                request, "Debe seleccionar una empresa antes de continuar."
            )
            return redirect("home_app:panel_cubo")

        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        """
        Obtiene el contexto necesario para la plantilla.

        :return: Contexto que incluye la URL del formulario y los filtros de permisos.
        """
        context = super().get_context_data(**kwargs)
        context["form_url"] = "home_app:prueba"

        # Obtener permisos de macrozona y proveedor para el usuario
        user_id = self.request.user.id
        database_name = self.request.session.get("database_name")
        if database_name:
            config = ConfigBasic(database_name, user_id)
            context["proveedores"] = config.config.get("proveedores", [])
            context["macrozonas"] = config.config.get("macrozonas", [])

        return context


class AmovildeskPage(LoginRequiredMixin, BaseView):
    """
    Vista para la página de generación del Cubo de Ventas.

    Esta vista maneja la solicitud del usuario para generar un cubo de ventas,
    iniciando una tarea en segundo plano y devolviendo el ID de dicha tarea.
    """

    template_name = "home/cubo.html"
    login_url = reverse_lazy("users_app:user-login")

    @method_decorator(registrar_auditoria)
    @method_decorator(permission_required("permisos.cubo", raise_exception=True))
    def dispatch(self, request, *args, **kwargs):
        """
        Método para despachar la solicitud, aplicando decoradores de auditoría y permisos requeridos.
        """
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """
        Maneja la solicitud POST para iniciar el proceso de generación del cubo de ventas.

        Recoge los datos del formulario, valida la entrada y, si es válida,
        inicia una tarea asincrónica para generar el cubo de ventas.
        """
        database_name = request.POST.get("database_select")
        IdtReporteIni = request.POST.get("IdtReporteIni")
        IdtReporteFin = request.POST.get("IdtReporteFin")
        user_id = request.user.id
        request.session["template_name"] = self.template_name

        if not all([database_name, IdtReporteIni, IdtReporteFin]):
            return JsonResponse(
                {
                    "success": False,
                    "error_message": "Se debe seleccionar la base de datos y las fechas.",
                },
                status=400,
            )

        try:
            report_id = 3  # AMOVILDESK
            task = cubo_ventas_task.delay(
                database_name, IdtReporteIni, IdtReporteFin, user_id, report_id
            )
            request.session["task_id"] = task.id
            return JsonResponse({"success": True, "task_id": task.id})
        except Exception as e:
            return JsonResponse(
                {"success": False, "error_message": f"Error: {str(e)}"}, status=500
            )

    def get(self, request, *args, **kwargs):
        """
        Maneja la solicitud GET, devolviendo la plantilla de la página del cubo de ventas.
        """
        database_name = request.session.get("database_name")
        if not database_name:
            messages.warning(
                request, "Debe seleccionar una empresa antes de continuar."
            )
            return redirect("home_app:panel_cubo")

        context = self.get_context_data(**kwargs)
        context["data"] = None
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        """
        Obtiene el contexto necesario para la plantilla.

        :return: Contexto que incluye la URL del formulario y los filtros de permisos.
        """
        context = super().get_context_data(**kwargs)
        context["form_url"] = "home_app:cubo"

        # Obtener permisos de macrozona y proveedor para el usuario
        user_id = self.request.user.id
        database_name = self.request.session.get("database_name")
        if database_name:
            config = ConfigBasic(database_name, user_id)
            context["proveedores"] = config.config.get("proveedores", [])
            context["macrozonas"] = config.config.get("macrozonas", [])

        return context
