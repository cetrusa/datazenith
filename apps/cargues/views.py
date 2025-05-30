import logging
from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse_lazy
import zipfile
import os
from django.contrib.auth.mixins import LoginRequiredMixin
import sqlalchemy
from apps.home.tasks import cargue_zip_task, cargue_plano_task, cargue_infoventas_task
from scripts.config import ConfigBasic
from scripts.StaticPage import StaticPage, DinamicPage
import re
from django.conf import settings
from sqlalchemy import create_engine, text
from apps.users.views import BaseView
from django.utils.decorators import method_decorator
from apps.users.decorators import registrar_auditoria
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.http import request
from scripts.extrae_bi.cargue_zip import CargueZip
from .forms import CargueInfoVentasForm
from scripts.cargue.cargue_infoproveedor import CargueInfoVentas
from django_rq import get_queue


class UploadZipView(BaseView):
    template_name = "cargues/cargue.html"
    login_url = reverse_lazy("users_app:user-login")

    @method_decorator(registrar_auditoria)
    # @method_decorator(permission_required("permisos.cubo", raise_exception=True))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        request.session["template_name"] = self.template_name
        database_name = request.POST.get("database_select")
        zip_file = request.FILES.get("zip_file")

        if not zip_file:
            return JsonResponse(
                {"success": False, "error_message": "No se subió ningún archivo."},
                status=400,
            )

        if not database_name:
            return JsonResponse(
                {
                    "success": False,
                    "error_message": "Se debe seleccionar la base de datos.",
                }
            )

        # Guarda el archivo en el servidor
        file_path = self.save_zip_file(zip_file)
        zip_file_path = file_path

        if not database_name:
            return redirect("home_app:panel_cubo")

        if not database_name:
            return JsonResponse(
                {
                    "success": False,
                    "error_message": "Se debe seleccionar la base de datos.",
                }
            )

        request.session["database_name"] = database_name
        try:
            # cargue_zip = CargueZip(database_name)
            # cargue_zip.procesar_zip()
            print("aqui estoy listo para iniciar la tarea asicrona")
            task = cargue_zip_task.delay(database_name, zip_file_path)

            # Guardamos el ID de la tarea en la sesión del usuario
            request.session["task_id"] = task.id
            return JsonResponse(
                {
                    "success": True,
                    "task_id": task.id,
                }
            )  # Devuelve el ID de la tarea al frontend
        except Exception as e:
            return JsonResponse({"success": False, "error_message": f"Error: {str(e)}"})

    def save_zip_file(self, zip_file):
        media_path = os.path.join("media", zip_file.name)
        with open(media_path, "wb+") as destination:
            for chunk in zip_file.chunks():
                destination.write(chunk)
        return media_path

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
        context["form_url"] = "cargues_app:cargue"

        # Obtener permisos de macrozona y proveedor para el usuario
        user_id = self.request.user.id
        database_name = self.request.session.get("database_name")
        if database_name:
            config = ConfigBasic(database_name, user_id)
            context["proveedores"] = config.config.get("proveedores", [])
            context["macrozonas"] = config.config.get("macrozonas", [])

        return context


class UploadPlanoFilesView(BaseView):
    template_name = "cargues/cargue_planos_tsol.html"
    login_url = reverse_lazy("users_app:user-login")

    @method_decorator(registrar_auditoria)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        request.session["template_name"] = self.template_name
        database_name = request.POST.get("database_select")
        plano_files = request.FILES.getlist("plano_files")  # Obtener múltiples archivos

        if not plano_files:
            return JsonResponse(
                {"success": False, "error_message": "No se subieron archivos."},
                status=400,
            )
        else:
            # Guarda los archivos en el servidor
            for file in plano_files:
                try:
                    self.save_plano_file(database_name, file)
                except Exception as e:
                    return JsonResponse(
                        {
                            "success": False,
                            "error_message": f"Error al procesar archivo {file.name}: {str(e)}",
                        }
                    )

        if not database_name:
            return JsonResponse(
                {
                    "success": False,
                    "error_message": "Se debe seleccionar la base de datos.",
                }
            )

        request.session["database_name"] = database_name

        try:
            print("aqui estoy listo para iniciar la tarea asicrona")
            task = cargue_plano_task.delay(database_name)
            # Guardamos el ID de la tarea en la sesión del usuario
            request.session["task_id"] = task.id
            return JsonResponse(
                {
                    "success": True,
                    "task_id": task.id,
                }
            )  # Devuelve el ID de la tarea al frontend
        except Exception as e:
            return JsonResponse({"success": False, "error_message": f"Error: {str(e)}"})

    def save_plano_file(self, database_name, file):
        # Construir la ruta del archivo. Se crea una carpeta dentro de 'media' con el nombre de la base de datos
        # y una subcarpeta 'plano_files' para almacenar los archivos.
        media_path = os.path.join("media", database_name, file.name)

        # Asegurarse de que las carpetas existan o crearlas
        os.makedirs(os.path.dirname(media_path), exist_ok=True)

        # Escribir el archivo en el sistema de archivos
        with open(media_path, "wb+") as destination:
            for chunk in file.chunks():
                destination.write(chunk)

        # Devolver la ruta del archivo guardado
        return media_path

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
        context["form_url"] = "cargues_app:cargue_planos_tsol"

        # Obtener permisos de macrozona y proveedor para el usuario
        user_id = self.request.user.id
        database_name = self.request.session.get("database_name")
        if database_name:
            config = ConfigBasic(database_name, user_id)
            context["proveedores"] = config.config.get("proveedores", [])
            context["macrozonas"] = config.config.get("macrozonas", [])

        return context


class ReporteGenericoCarguePage(BaseView):
    """
    Vista genérica para cargues masivos tipo InfoVentas.
    Permite unificar la lógica cambiando solo el template, permisos y task.
    """

    template_name = None
    login_url = reverse_lazy("users_app:user-login")
    permiso = None
    form_url = None
    task_func = None

    @classmethod
    def as_view_with_params(cls, **initkwargs):
        def view(*args, **kwargs):
            self = cls(**initkwargs)
            return self.dispatch(*args, **kwargs)

        return view

    @method_decorator(registrar_auditoria)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        job_id = None  # Siempre inicializar job_id
        # Detectar si es una petición AJAX
        is_ajax = (
            request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or request.content_type.startswith("application/json")
            or "application/json" in request.headers.get("Accept", "")
        )
        print("[CARGUE] POST recibido en ReporteGenericoCarguePage.post")
        print(f"[CARGUE] Usuario: {request.user} (ID: {request.user.id})")
        print(f"[CARGUE] is_ajax: {is_ajax}")
        print(f"[CARGUE] POST: {request.POST}")
        print(f"[CARGUE] FILES: {request.FILES}")
        print(f"[CARGUE] request.FILES keys: {list(request.FILES.keys())}")
        print(f"[CARGUE] request.POST keys: {list(request.POST.keys())}")
        print(f"[CARGUE] request.POST items: {dict(request.POST)}")
        print(f"[CARGUE] request.content_type: {request.content_type}")
        print(f"[CARGUE] Headers: {dict(request.headers)}")

        # Manejar peticiones del database_selector
        if "database_select" in request.POST and "excel_file" not in request.FILES:
            print("[CARGUE] Petición del database_selector detectada")
            database_name = request.POST.get("database_select")
            print(f"[CARGUE] Actualizando database_name en sesión: {database_name}")

            # Actualizar la sesión con la nueva base de datos
            request.session["database_name"] = database_name

            # Responder según el tipo de petición
            if is_ajax:
                return JsonResponse(
                    {
                        "success": True,
                        "message": f"Base de datos actualizada a: {database_name}",
                    }
                )
            else:
                # Para peticiones no-AJAX, redirigir a la misma página
                return redirect(request.path)

        # Debug adicional para multipart
        if hasattr(request, "_body") and request._body:
            print(f"[CARGUE] Request body length: {len(request._body)}")
            print(f"[CARGUE] Request body preview: {str(request._body[:200])}")
        form = CargueInfoVentasForm(request.POST, request.FILES)
        if not form.is_valid():
            print("[CARGUE][ERROR] Formulario inválido. Errores:", form.errors)
            error_message = form.errors.as_text()
            if is_ajax:
                return JsonResponse(
                    {"success": False, "error_message": error_message}, status=400
                )
            messages.error(request, error_message)
            context = self.get_context_data(form=form, resultado=None, job_id=None)
            return self.render_to_response(context)

        # Formulario válido - procesar datos
        excel_file = form.cleaned_data["excel_file"]
        database_name = request.POST.get("database_name") or form.cleaned_data.get(
            "database_name"
        )
        IdtReporteIni = request.POST.get("IdtReporteIni")
        IdtReporteFin = request.POST.get("IdtReporteFin")

        print(
            f"[CARGUE] Formulario válido. database_name={database_name}, IdtReporteIni={IdtReporteIni}, IdtReporteFin={IdtReporteFin}"
        )

        # Validaciones adicionales
        if not database_name:
            error_message = "Debe seleccionar una base de datos."
            if is_ajax:
                return JsonResponse(
                    {"success": False, "error_message": error_message}, status=400
                )
            messages.error(request, error_message)
            context = self.get_context_data(form=form, resultado=None, job_id=None)
            return self.render_to_response(context)

        if not IdtReporteIni or not IdtReporteFin:
            error_message = "Debe seleccionar las fechas inicial y final."
            if is_ajax:
                return JsonResponse(
                    {"success": False, "error_message": error_message}, status=400
                )
            messages.error(request, error_message)
            context = self.get_context_data(form=form, resultado=None, job_id=None)
            return self.render_to_response(context)

        # Guardar archivo temporal
        temp_path = os.path.join("media", "temp", excel_file.name)
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)

        try:
            with open(temp_path, "wb+") as dest:
                for chunk in excel_file.chunks():
                    dest.write(chunk)
            print(f"[CARGUE] Archivo guardado temporalmente en: {temp_path}")
            del excel_file  # Eliminar referencia para evitar problemas de pickle

            # Lanzar tarea asíncrona
            task = self.task_func.delay(
                temp_path,
                database_name,
                IdtReporteIni,
                IdtReporteFin,
                request.user.id,
            )
            job_id = task.id
            print(f"[CARGUE] Tarea encolada with job_id={job_id}")

            success_message = f"Carga en proceso. ID de tarea: {job_id}"

            if is_ajax:
                return JsonResponse(
                    {"success": True, "task_id": job_id, "message": success_message}
                )

            messages.info(request, success_message)
            context = self.get_context_data(
                form=form, resultado=success_message, job_id=job_id
            )
            return self.render_to_response(context)

        except Exception as e:
            print(f"[CARGUE][ERROR] Error al procesar el cargue: {e}")
            error_message = f"Error al procesar el cargue: {str(e)}"

            # Limpiar archivo temporal si existe
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass

            if is_ajax:
                return JsonResponse(
                    {"success": False, "error_message": error_message}, status=500
                )

            messages.error(request, error_message)
            context = self.get_context_data(form=form, resultado=None, job_id=None)
            return self.render_to_response(context)

    def get(self, request, *args, **kwargs):
        form = CargueInfoVentasForm()
        context = self.get_context_data(form=form, resultado=None, job_id=None)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_url"] = self.form_url
        user_id = self.request.user.id
        database_name = self.request.session.get("database_name")
        if database_name:
            config = ConfigBasic(database_name, user_id)
            context["proveedores"] = config.config.get("proveedores", [])
            context["macrozonas"] = config.config.get("macrozonas", [])
            context["ultimo_reporte"] = config.config.get("ultima_actualizacion", "")
        context.update(kwargs)
        return context


class CargueInfoVentasPage(ReporteGenericoCarguePage):
    template_name = "cargues/cargue_infoventas.html"
    permiso = "permisos.cargue_infoproveedor"
    form_url = "cargues_app:cargue_infoventas"
    task_func = cargue_infoventas_task

    @method_decorator(
        permission_required("permisos.cargue_infoproveedor", raise_exception=True)
    )
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
