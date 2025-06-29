from django.contrib import messages
import subprocess
from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy, reverse
import os, time
import time  # Para medición de tiempos
import logging
import traceback
from django.http import HttpResponse, FileResponse, JsonResponse
import io
from django.views.generic import View, TemplateView
from django.utils.decorators import method_decorator
from apps.users.decorators import registrar_auditoria
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponseRedirect
from scripts.conexion import Conexion
from scripts.config import ConfigBasic
from scripts.StaticPage import StaticPage, DinamicPage
from scripts.extrae_bi.extrae_bi_insert import ExtraeBiConfig, ExtraeBiExtractor
from scripts.extrae_bi.interface import InterfaceContable
from scripts.extrae_bi.cubo import CuboVentas  # Importación para LoadDataPageView
from .tasks import (
    cubo_ventas_task,
    interface_task,
    plano_task,
    extrae_bi_task,
)
from apps.users.models import UserPermission
from django.views.decorators.cache import cache_page
from django.core.cache import cache
from apps.users.views import BaseView
from apps.home.models import Reporte

# importaciones para rq
from django_rq import get_queue
from rq.job import Job
from rq.job import NoSuchJobError
from django_rq import get_connection
from django.utils.translation import gettext_lazy as _
from .utils import clean_old_media_files

logger = logging.getLogger(__name__)

# Constantes globales para optimización
CACHE_TIMEOUT_SHORT = 60 * 5  # 5 minutos
CACHE_TIMEOUT_MEDIUM = 60 * 15  # 15 minutos
CACHE_TIMEOUT_LONG = 60 * 60  # 1 hora
BATCH_SIZE_DEFAULT = 50000  # Tamaño por defecto para procesamiento por lotes


class HomePanelCuboPage(BaseView):
    """
    Vista para la página principal del panel de cubos.
    Optimizada para mejorar rendimiento con caché y carga diferida.
    """

    template_name = "home/panel_cubo.html"
    login_url = reverse_lazy("users_app:user-login")

    # Añadimos caché para esta vista
    # @method_decorator(cache_page(60 * 5))  # Caché de 5 minutos
    def dispatch(self, request, *args, **kwargs):
        """
        Método para despachar la solicitud con caché para mejorar rendimiento.
        """
        # Solo aplicamos caché si no hay parámetros POST
        if request.method == "GET":
            return super().dispatch(request, *args, **kwargs)
        return super(LoginRequiredMixin, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """
        Maneja la solicitud POST para seleccionar base de datos.
        Optimizado para respuesta inmediata.
        """
        start_time = time.time()  # Medición de tiempo para análisis de rendimiento

        try:
            request.session["template_name"] = self.template_name
            database_name = request.POST.get("database_select")

            if not database_name:
                logger.warning(
                    f"Intento de selección de base de datos vacía por usuario {request.user.id}"
                )
                return redirect("home_app:panel_cubo")

            # Validar el nombre de la base de datos (prevenir inyección)
            if not self._validate_database_name(database_name):
                logger.warning(
                    f"Intento de uso de nombre de base de datos inválido: {database_name} por usuario {request.user.id}"
                )
                messages.error(request, "Nombre de base de datos no válido")
                return redirect("home_app:panel_cubo")

            # Usar modificación eficiente de sesión
            request.session["database_name"] = database_name
            request.session.modified = True  # Marcar la sesión como modificada
            request.session.save()  # Forzar guardado de la sesión
            StaticPage.name = database_name

            # Invalidar caché específica para este usuario y sesión
            session_key = request.session.session_key or "anonymous"
            cache_key = f"panel_cubo_{request.user.id}_{session_key}"
            cache.delete(cache_key)

            # Limpiar caché de configuración para este usuario y base de datos
            ConfigBasic.clear_cache(
                database_name=database_name, user_id=request.user.id
            )

            logger.debug(
                f"HomePanelCuboPage.post completado en {time.time() - start_time:.2f}s"
            )

            return redirect("home_app:panel_cubo")

        except Exception as e:
            logger.error(f"Error en HomePanelCuboPage.post: {str(e)}")
            messages.error(request, "Error al procesar la selección de base de datos")
            return redirect("home_app:panel_cubo")

    def get(self, request, *args, **kwargs):
        """
        Maneja la solicitud GET, devolviendo la plantilla con datos optimizados.
        Compatible con modo incógnito al verificar la validez de la sesión.
        """
        start_time = time.time()  # Medición de tiempo para análisis de rendimiento

        try:
            # Asegurar que la sesión tenga session_key única antes de cachear
            if not request.session.session_key:
                request.session.save()
            user_id = request.user.id
            session_key = request.session.session_key
            cache_key = f"panel_cubo_{user_id}_{session_key}"
            cached_response = cache.get(cache_key)

            if cached_response:
                logger.debug(
                    f"HomePanelCuboPage.get (desde caché) completado en {time.time() - start_time:.2f}s"
                )
                return cached_response

            # Si no hay datos en caché, procesamos normalmente
            response = super().get(request, *args, **kwargs)

            # Almacenamos en caché solo si la respuesta es exitosa
            if response.status_code == 200:
                response.render()
                cache_timeout = 60 * 5  # 5 minutos por defecto
                if not request.user.is_authenticated:
                    cache_timeout = 60 * 2  # 2 minutos para usuarios no autenticados
                cache.set(cache_key, response, cache_timeout)

            logger.debug(
                f"HomePanelCuboPage.get (generado) completado en {time.time() - start_time:.2f}s"
            )
            return response

        except Exception as e:
            logger.error(f"Error en HomePanelCuboPage.get: {str(e)}")
            messages.error(request, "Error al cargar la página")
            return redirect("home_app:panel_cubo")

    def get_context_data(self, **kwargs):
        """
        Obtiene el contexto necesario para la plantilla.
        Optimizado para cargar solo datos esenciales y usar carga diferida.
        """
        start_time = time.time()  # Medición de tiempo

        try:
            context = super().get_context_data(**kwargs)
            context["form_url"] = "home_app:panel_cubo"

            # Añadimos bandera para carga diferida
            context["use_lazy_loading"] = True

            # Añadimos información de optimización para JavaScript
            context["optimization"] = {
                "cache_timeout": 300,  # 5 minutos en segundos
                "use_compression": True,
            }

            # Obtenemos datos de usuario si hay una base de datos seleccionada
            user_id = self.request.user.id
            database_name = self.request.session.get("database_name")

            if database_name:
                context_data = self._get_cached_user_context(user_id, database_name)
                context.update(context_data)

            logger.debug(
                f"HomePanelCuboPage.get_context_data completado en {time.time() - start_time:.2f}s"
            )
            return context

        except Exception as e:
            logger.error(f"Error en HomePanelCuboPage.get_context_data: {str(e)}")
            # Devolver contexto mínimo en caso de error
            return {"form_url": "home_app:panel_cubo", "error": True}

    def _get_cached_user_context(self, user_id, database_name):
        """
        Obtiene el contexto del usuario desde caché si está disponible,
        o lo crea si no existe.
        """
        # session_key = self.request.session.session_key or "anonymous"  # Comentado
        cache_key = f"user_cubo_context_{database_name}"
        user_context = cache.get(cache_key)

        if user_context:
            logger.debug(
                f"Contexto obtenido desde caché para {database_name} (sin user/session)"
            )
            return user_context

        # Si no está en caché, crear el contexto
        try:
            # user_id = self.request.user.id  # Comentado: ya no se usa user_id
            config = ConfigBasic(database_name)  # Solo database_name
            user_context = {
                "proveedores": config.config.get("proveedores", []),
                "macrozonas": config.config.get("macrozonas", []),
                "ultimo_reporte": config.config.get("ultima_actualizacion", ""),
            }

            # Guardar en caché
            cache.set(cache_key, user_context, 60 * 15)  # 15 minutos

            return user_context

        except Exception as e:
            logger.error(f"Error al obtener contexto: {str(e)}")
            # Devolver diccionario vacío o con valores por defecto
            return {
                "proveedores": [],
                "macrozonas": [],
                "ultimo_reporte": None,
            }

    def _validate_database_name(self, database_name):
        """
        Valida que el nombre de la base de datos sea seguro.
        Previene inyecciones y caracteres no permitidos.
        """
        if not database_name:
            return False

        # Patrón para nombres de bases de datos válidos (alfanuméricos, guiones y guiones bajos)
        import re

        pattern = re.compile(r"^[a-zA-Z0-9_\-]+$")
        return bool(pattern.match(database_name))


class HomePanelBiPage(BaseView):
    """
    Vista para la página principal del panel BI.
    Optimizada para mejorar rendimiento con caché y carga diferida.
    Compatible con modo incógnito.
    """

    template_name = "home/panel_bi.html"
    login_url = reverse_lazy("users_app:user-login")

    # Añadimos caché para esta vista
    # @method_decorator(cache_page(60 * 5))  # Caché de 5 minutos
    def dispatch(self, request, *args, **kwargs):
        """
        Método para despachar la solicitud con caché para mejorar rendimiento.
        """
        # Solo aplicamos caché si no hay parámetros POST
        if request.method == "GET":
            return super().dispatch(request, *args, **kwargs)
        return super(LoginRequiredMixin, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """
        Maneja la solicitud POST para seleccionar base de datos.
        Optimizado para respuesta inmediata.
        """
        start_time = time.time()  # Medición de tiempo para análisis de rendimiento

        try:
            request.session["template_name"] = self.template_name
            database_name = request.POST.get("database_select")

            if not database_name:
                logger.warning(
                    f"Intento de selección de base de datos vacía por usuario {request.user.id}"
                )
                return redirect("home_app:panel_bi")

            # Validar el nombre de la base de datos (prevenir inyección)
            if not self._validate_database_name(database_name):
                logger.warning(
                    f"Intento de uso de nombre de base de datos inválido: {database_name} por usuario {request.user.id}"
                )
                messages.error(request, "Nombre de base de datos no válido")
                return redirect("home_app:panel_bi")

            # Usar modificación eficiente de sesión
            request.session["database_name"] = database_name
            request.session.modified = True
            request.session.save()
            StaticPage.name = database_name

            # Invalidar caché específica para este usuario y sesión
            # Incluir ID de sesión para manejar modo incógnito
            session_key = request.session.session_key or "anonymous"
            cache_key = f"panel_bi_{request.user.id}_{session_key}"
            cache.delete(cache_key)

            # Limpiar caché de configuración para este usuario y base de datos
            ConfigBasic.clear_cache(
                database_name=database_name, user_id=request.user.id
            )

            logger.debug(
                f"HomePanelBiPage.post completado en {time.time() - start_time:.2f}s"
            )

            return redirect("home_app:panel_bi")

        except Exception as e:
            logger.error(f"Error en HomePanelBiPage.post: {str(e)}")
            messages.error(request, "Error al procesar la selección de base de datos")
            return redirect("home_app:panel_bi")

    def get(self, request, *args, **kwargs):
        """
        Maneja la solicitud GET, devolviendo la plantilla con datos optimizados.
        Compatible con modo incógnito al incluir ID de sesión en la clave de caché.
        """
        start_time = time.time()  # Medición de tiempo para análisis de rendimiento

        try:
            # Asegurar que la sesión tenga session_key única antes de cachear
            if not request.session.session_key:
                request.session.save()
            user_id = request.user.id
            session_key = request.session.session_key
            cache_key = f"panel_bi_{user_id}_{session_key}"
            cached_response = cache.get(cache_key)

            if cached_response:
                logger.debug(
                    f"HomePanelBiPage.get (desde caché) completado en {time.time() - start_time:.2f}s"
                )
                return cached_response

            # Si no hay datos en caché, procesamos normalmente
            response = super().get(request, *args, **kwargs)

            # Almacenamos en caché solo si la respuesta es exitosa
            if response.status_code == 200:
                # Calcular tiempo de caché basado en si el usuario está autenticado
                cache_timeout = 60 * 5  # 5 minutos por defecto
                if not request.user.is_authenticated:
                    cache_timeout = 60 * 2  # 2 minutos para usuarios no autenticados

                # Renderizar la respuesta antes de guardarla en caché
                response.render()
                cache.set(cache_key, response, cache_timeout)

            logger.debug(
                f"HomePanelBiPage.get (generado) completado en {time.time() - start_time:.2f}s"
            )
            return response

        except Exception as e:
            logger.error(f"Error en HomePanelBiPage.get: {str(e)}")
            messages.error(request, "Error al cargar la página")
            return redirect("home_app:panel_bi")

    def get_context_data(self, **kwargs):
        """
        Obtiene el contexto necesario para la plantilla.
        Optimizado para cargar solo datos esenciales y usar carga diferida.
        """
        start_time = time.time()  # Medición de tiempo

        try:
            context = super().get_context_data(**kwargs)
            context["form_url"] = "home_app:panel_bi"

            # Añadimos bandera para carga diferida
            context["use_lazy_loading"] = True

            # Información sobre el modo de navegación
            context["is_incognito_probable"] = self._is_likely_incognito(self.request)

            # Añadimos información de optimización
            context["optimization"] = {
                "cache_timeout": 300,  # 5 minutos en segundos
                "use_compression": True,
            }

            # Obtenemos datos de usuario si hay una base de datos seleccionada
            user_id = self.request.user.id
            database_name = self.request.session.get("database_name")

            if database_name:
                context_data = self._get_cached_user_context(user_id, database_name)
                context.update(context_data)

            logger.debug(
                f"HomePanelBiPage.get_context_data completado en {time.time() - start_time:.2f}s"
            )
            return context

        except Exception as e:
            logger.error(f"Error en HomePanelBiPage.get_context_data: {str(e)}")
            # Devolver contexto mínimo en caso de error
            return {"form_url": "home_app:panel_bi", "error": True}

    def _get_cached_user_context(self, user_id, database_name):
        """
        Obtiene el contexto del usuario desde caché si está disponible,
        o lo crea si no existe.
        """
        session_key = self.request.session.session_key or "anonymous"
        cache_key = f"user_context_{user_id}_{database_name}_{session_key}"
        user_context = cache.get(cache_key)

        if user_context:
            return user_context

        config = ConfigBasic(database_name, user_id)
        user_context = {
            "proveedores": config.config.get("proveedores", []),
            "macrozonas": config.config.get("macrozonas", []),
        }

        cache.set(cache_key, user_context, 60 * 15)  # 15 minutos

        return user_context

    def _validate_database_name(self, database_name):
        """
        Valida que el nombre de la base de datos sea seguro.
        Previene inyecciones y caracteres no permitidos.
        """
        if not database_name:
            return False

        # Patrón para nombres de bases de datos válidos (alfanuméricos, guiones y guiones bajos)
        import re

        pattern = re.compile(r"^[a-zA-Z0-9_\-]+$")
        return bool(pattern.match(database_name))

    def _is_likely_incognito(self, request):
        """
        Intenta detectar si el usuario probablemente está usando modo incógnito
        basado en heurísticas simples.
        """
        # Si no hay una sesión persistente pero el usuario está autenticado
        # O si hay cookies de sesión pero no cookies persistentes
        # Es probable que esté en modo incógnito

        session_key = request.session.session_key
        has_persistent_cookies = (
            len(request.COOKIES) > 1
        )  # Más allá de la cookie de sesión

        if (request.user.is_authenticated and not session_key) or (
            session_key and not has_persistent_cookies
        ):
            return True

        return False


class HomePanelActualizacionPage(BaseView):
    """
    Vista para la página principal del panel de actualización.
    Optimizada para mejorar rendimiento con caché y carga diferida.
    """

    template_name = "home/panel_actualizacion.html"
    login_url = reverse_lazy("users_app:user-login")

    # Añadimos caché para esta vista
    # @method_decorator(cache_page(60 * 5))  # Caché de 5 minutos
    def dispatch(self, request, *args, **kwargs):
        """
        Método para despachar la solicitud con caché para mejorar rendimiento.
        """
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """
        Maneja la solicitud POST para seleccionar base de datos.
        Optimizado para respuesta inmediata.
        """
        start_time = time.time()  # Medición de tiempo para análisis de rendimiento

        request.session["template_name"] = self.template_name
        database_name = request.POST.get("database_select")

        if not database_name:
            return redirect("home_app:panel_actualizacion")

        # Usar modificación eficiente de sesión
        request.session["database_name"] = database_name
        StaticPage.name = database_name

        # Invalidar caché específica para este usuario y sesión
        session_key = request.session.session_key or "anonymous"
        cache_key = f"panel_actualizacion_{request.user.id}_{session_key}"
        cache.delete(cache_key)

        logger.debug(
            f"HomePanelActualizacionPage.post completado en {time.time() - start_time:.2f}s"
        )

        return redirect("home_app:panel_actualizacion")

    def get(self, request, *args, **kwargs):
        """
        Maneja la solicitud GET, devolviendo la plantilla con datos optimizados.
        """
        start_time = time.time()  # Medición de tiempo para análisis de rendimiento

        # Asegurar que la sesión tenga session_key única antes de cachear
        if not request.session.session_key:
            request.session.save()
        session_key = request.session.session_key
        cache_key = f"panel_actualizacion_{request.user.id}_{session_key}"
        cached_response = cache.get(cache_key)

        if cached_response:
            logger.debug(
                f"HomePanelActualizacionPage.get (desde caché) completado en {time.time() - start_time:.2f}s"
            )
            return cached_response

        # Si no hay datos en caché, procesamos normalmente
        response = super().get(request, *args, **kwargs)

        # Almacenamos en caché solo si la respuesta es exitosa
        if response.status_code == 200:
            # Forzar renderizado de la respuesta antes de guardarla en caché
            response.render()
            cache.set(cache_key, response, 60 * 5)  # 5 minutos

        logger.debug(
            f"HomePanelActualizacionPage.get (generado) completado en {time.time() - start_time:.2f}s"
        )
        return response

    def get_context_data(self, **kwargs):
        """
        Obtiene el contexto necesario para la plantilla.
        Optimizado para cargar solo datos esenciales y usar carga diferida.
        """
        start_time = time.time()  # Medición de tiempo

        context = super().get_context_data(**kwargs)
        context["form_url"] = "home_app:panel_actualizacion"

        # Añadimos bandera para carga diferida
        context["use_lazy_loading"] = True

        # Añadimos información de optimización para JavaScript
        context["optimization"] = {
            "cache_timeout": 300,  # 5 minutos en segundos
            "use_compression": True,
        }

        # Obtenemos datos una sola vez por solicitud
        user_id = self.request.user.id
        database_name = self.request.session.get("database_name")

        # Solo cargar configuración si es necesario
        if database_name:
            # Usar una versión ligera de la configuración si solo necesitamos proveedores y macrozonas
            context_data = self._get_cached_user_context(user_id, database_name)
            context.update(context_data)

        logger.debug(
            f"HomePanelActualizacionPage.get_context_data completado en {time.time() - start_time:.2f}s"
        )
        return context

    def _get_cached_user_context(self, user_id, database_name):
        """
        Obtiene el contexto del usuario desde caché si está disponible,
        o lo crea si no existe.
        """
        session_key = self.request.session.session_key or "anonymous"
        cache_key = f"user_context_{user_id}_{database_name}_{session_key}"
        user_context = cache.get(cache_key)

        if user_context:
            return user_context

        config = ConfigBasic(database_name, user_id)
        user_context = {
            "proveedores": config.config.get("proveedores", []),
            "macrozonas": config.config.get("macrozonas", []),
        }

        cache.set(cache_key, user_context, 60 * 15)  # 15 minutos

        return user_context

    def _validate_database_name(self, database_name):
        """
        Valida que el nombre de la base de datos sea seguro.
        Previene inyecciones y caracteres no permitidos.
        """
        if not database_name:
            return False

        # Patrón para nombres de bases de datos válidos (alfanuméricos, guiones y guiones bajos)
        import re

        pattern = re.compile(r"^[a-zA-Z0-9_\-]+$")
        return bool(pattern.match(database_name))


class HomePanelInterfacePage(BaseView):
    """
    Vista para la página principal del panel de interface.
    Optimizada para mejorar rendimiento con caché y carga diferida.
    """

    template_name = "home/panel_interface.html"
    login_url = reverse_lazy("users_app:user-login")

    # Añadimos caché para esta vista
    # @method_decorator(cache_page(60 * 5))  # Caché de 5 minutos
    def dispatch(self, request, *args, **kwargs):
        """
        Método para despachar la solicitud con caché para mejorar rendimiento.
        """
        # Solo aplicamos caché si no hay parámetros POST
        if request.method == "GET":
            return super().dispatch(request, *args, **kwargs)
        return super(LoginRequiredMixin, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """
        Maneja la solicitud POST para seleccionar base de datos.
        Optimizado para respuesta inmediata.
        """
        start_time = time.time()  # Medición de tiempo para análisis de rendimiento

        request.session["template_name"] = self.template_name
        database_name = request.POST.get("database_select")

        if not database_name:
            return redirect("home_app:panel_interface")

        # Usar modificación eficiente de sesión
        request.session["database_name"] = database_name
        StaticPage.name = database_name

        # Invalidar caché específica para este usuario y sesión
        session_key = request.session.session_key or "anonymous"
        cache_key = f"panel_interface_{request.user.id}_{session_key}"
        cache.delete(cache_key)

        # Limpiar caché de configuración para este usuario y base de datos
        ConfigBasic.clear_cache(database_name=database_name, user_id=request.user.id)

        logger.debug(
            f"HomePanelInterfacePage.post completado en {time.time() - start_time:.2f}s"
        )

        return redirect("home_app:panel_interface")

    def get(self, request, *args, **kwargs):
        """
        Maneja la solicitud GET, devolviendo la plantilla con datos optimizados.
        """
        start_time = time.time()  # Medición de tiempo para análisis de rendimiento

        # Asegurar que la sesión tenga session_key única antes de cachear
        if not request.session.session_key:
            request.session.save()
        session_key = request.session.session_key
        cache_key = f"panel_interface_{request.user.id}_{session_key}"
        cached_response = cache.get(cache_key)

        if cached_response:
            logger.debug(
                f"HomePanelInterfacePage.get (desde caché) completado en {time.time() - start_time:.2f}s"
            )
            return cached_response

        # Si no hay datos en caché, procesamos normalmente
        response = super().get(request, *args, **kwargs)

        # Almacenamos en caché solo si la respuesta es exitosa
        if response.status_code == 200:
            # Forzar renderizado de la respuesta antes de guardarla en caché
            response.render()
            cache.set(cache_key, response, 60 * 5)  # 5 minutos

        logger.debug(
            f"HomePanelInterfacePage.get (generado) completado en {time.time() - start_time:.2f}s"
        )
        return response

    def get_context_data(self, **kwargs):
        """
        Obtiene el contexto necesario para la plantilla.
        Optimizado para cargar solo datos esenciales y usar carga diferida.
        """
        start_time = time.time()  # Medición de tiempo

        context = super().get_context_data(**kwargs)
        context["form_url"] = "home_app:panel_interface"

        # Añadimos bandera para carga diferida
        context["use_lazy_loading"] = True

        # Añadimos información de optimización para JavaScript
        context["optimization"] = {
            "cache_timeout": 300,  # 5 minutos en segundos
            "use_compression": True,
        }

        # Obtenemos datos una sola vez por solicitud
        user_id = self.request.user.id
        database_name = self.request.session.get("database_name")

        # Solo cargar configuración si es necesario
        if database_name:
            # Usar una versión ligera de la configuración si solo necesitamos proveedores y macrozonas
            context_data = self._get_cached_user_context(user_id, database_name)
            context.update(context_data)

        logger.debug(
            f"HomePanelInterfacePage.get_context_data completado en {time.time() - start_time:.2f}s"
        )
        return context

    def _get_cached_user_context(self, user_id, database_name):
        """
        Obtiene el contexto del usuario desde caché si está disponible,
        o lo crea si no existe.
        """
        session_key = self.request.session.session_key or "anonymous"
        cache_key = f"user_interface_context_{user_id}_{database_name}_{session_key}"
        user_context = cache.get(cache_key)

        if user_context:
            logger.debug(
                f"Contexto de usuario obtenido desde caché para {user_id} en {database_name} (session {session_key})"
            )
            return user_context

        config = ConfigBasic(database_name, user_id)
        user_context = {
            "proveedores": config.config.get("proveedores", []),
            "macrozonas": config.config.get("macrozonas", []),
            "interfaces_disponibles": self._obtener_interfaces_disponibles(config),
        }

        cache.set(cache_key, user_context, 60 * 15)  # 15 minutos

        return user_context

    def _obtener_interfaces_disponibles(self, config):
        """
        Método optimizado para obtener las interfaces disponibles.
        """
        # Este método puede ampliarse para obtener información específica
        # sobre las interfaces disponibles para el usuario
        interfaces = []
        try:
            # Si hay configuración específica de interfaces en la configuración,
            # podemos obtenerla aquí
            if config.config.get("nmProcedureInterface"):
                interfaces.append(
                    {
                        "nombre": config.config.get(
                            "nmProcedureInterface", "Interfaz Contable"
                        ),
                        "id": "interface_contable",
                    }
                )

            # Aquí podríamos añadir otras interfaces según la configuración

        except Exception as e:
            logger.error(f"Error al obtener interfaces disponibles: {e}")

        return interfaces


class DownloadFileView(LoginRequiredMixin, View):
    """
    Vista optimizada para la descarga segura y eficiente de archivos.
    Implementa streaming de archivos, caché, compresión y registro de actividad.
    """

    login_url = reverse_lazy("users_app:user-login")
    chunk_size = 998192  # 8KB para streaming eficiente
    allowed_extensions = [
        ".xlsx",
        ".csv",
        ".txt",
        ".zip",
        ".pdf",
        ".xls",
    ]  # Extensiones permitidas

    def get(self, request):
        """
        Maneja la solicitud GET para descargar un archivo.
        Implementa transmisión por chunks para archivos grandes y validación de seguridad.
        """
        start_time = time.time()  # Medición de tiempo para diagnóstico
        template_name = request.session.get("template_name", "home/panel_cubo.html")
        file_path = request.session.get("file_path")
        file_name = request.session.get("file_name")
        user_id = request.user.id

        # Validación inicial de parámetros
        if not file_path or not file_name:
            messages.error(
                request, "Archivo no encontrado o no especificado correctamente"
            )
            logger.warning(
                f"Intento de descarga sin archivo especificado por usuario {user_id}"
            )
            # Redirect to cubo panel on error
            return redirect("home_app:panel_cubo")

        # Validaciones de seguridad
        try:
            # Normalizar la ruta para evitar ataques de path traversal
            file_path = os.path.normpath(file_path)

            # Validar que el archivo existe y está en una ubicación permitida
            if not os.path.exists(file_path) or not os.path.isfile(file_path):
                messages.error(request, "El archivo no existe")
                logger.warning(
                    f"Intento de descarga de archivo inexistente: {file_path} por usuario {user_id}"
                )
                return redirect("home_app:panel_cubo")

            # Validar extensión del archivo
            _, extension = os.path.splitext(file_path)
            if extension.lower() not in self.allowed_extensions:
                messages.error(request, "Tipo de archivo no permitido")
                logger.warning(
                    f"Intento de descarga de archivo no permitido: {file_path} por usuario {user_id}"
                )
                return redirect("home_app:panel_cubo")

            # Comprobar tamaño del archivo
            file_size = os.path.getsize(file_path)
            if file_size > 100 * 1024 * 1024:  # 100MB
                logger.info(
                    f"Archivo grande ({file_size/1024/1024:.2f}MB) descargado: {file_path} por usuario {user_id}"
                )

            # Servir el archivo de manera eficiente usando streaming
            response = FileResponse(
                open(file_path, "rb"), as_attachment=True, filename=file_name
            )

            # Optimizar cabeceras para mejor rendimiento de descarga
            response["Content-Length"] = file_size
            response["Content-Type"] = self._get_content_type(file_name)

            # Añadir cabeceras de caché para clientes
            response["Cache-Control"] = (
                "private, max-age=300"  # 5 minutos de caché para el cliente
            )

            # Añadir cabeceras para mejorar la seguridad
            response["X-Content-Type-Options"] = "nosniff"

            # Registro de actividad y tiempo para diagnóstico
            logger.info(
                f"Archivo descargado: {file_path} ({file_size/1024:.2f}KB) por usuario {user_id} en {time.time() - start_time:.2f}s"
            )

            return response

        except IOError as e:
            messages.error(request, f"Error al abrir el archivo: {str(e)}")
            logger.error(f"Error de E/S al descargar {file_path}: {str(e)}")
            # On unexpected exception, redirect to cubo panel
            return redirect("home_app:panel_cubo")
        except Exception as e:
            messages.error(request, f"Error inesperado: {str(e)}")
            logger.error(f"Error inesperado al descargar {file_path}: {str(e)}")
            # On unexpected exception, redirect to cubo panel
            return redirect("home_app:panel_cubo")

    def _get_content_type(self, filename):
        """Determina el tipo MIME basado en la extensión del archivo."""
        extension = os.path.splitext(filename)[1].lower()

        content_types = {
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".xls": "application/vnd.ms-excel",
            ".csv": "text/csv",
            ".txt": "text/plain",
            ".pdf": "application/pdf",
            ".zip": "application/zip",
        }

        return content_types.get(extension, "application/octet-stream")

    def _validate_date_format(self, date_str):
        """
        Valida que el formato de fecha sea correcto.
        Acepta formato YYYY-MM-DD únicamente.
        """
        if not date_str:
            raise ValueError("La fecha no puede estar vacía")

        import re

        pattern = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
        if not pattern.match(date_str):
            raise ValueError(
                f"El formato de fecha '{date_str}' es incorrecto. Use YYYY-MM-DD."
            )

        # Retornar fecha con guiones para procesamiento interno
        return date_str

    def post(self, request):
        """
        Maneja la solicitud POST para eliminar un archivo.
        Implementa validaciones de seguridad y registro detallado.
        """
        start_time = time.time()  # Medición de tiempo para diagnóstico
        template_name = request.session.get("template_name")
        file_path = request.session.get("file_path")
        file_name = request.session.get("file_name")
        user_id = request.user.id

        # Validación inicial
        if file_path is None:
            logger.warning(
                f"Intento de eliminar archivo sin ruta especificada por usuario {user_id}"
            )
            return JsonResponse(
                {"success": False, "error_message": "No hay archivo para eliminar."}
            )

        try:
            # Normalizar la ruta para evitar ataques de path traversal
            file_path = os.path.normpath(file_path)

            # Validar extensión del archivo
            _, extension = os.path.splitext(file_path)
            if extension.lower() not in self.allowed_extensions:
                logger.warning(
                    f"Intento de eliminar tipo de archivo no permitido: {file_path} por usuario {user_id}"
                )
                return JsonResponse(
                    {"success": False, "error_message": "Tipo de archivo no permitido."}
                )

            # Validar que el archivo existe
            if not os.path.exists(file_path):
                logger.warning(
                    f"Intento de eliminar archivo inexistente: {file_path} por usuario {user_id}"
                )
                return JsonResponse(
                    {"success": False, "error_message": "El archivo no existe."}
                )

            # Validar que es un archivo regular (no directorio, enlace simbólico, etc.)
            if not os.path.isfile(file_path):
                logger.warning(
                    f"Intento de eliminar algo que no es un archivo: {file_path} por usuario {user_id}"
                )
                return JsonResponse(
                    {
                        "success": False,
                        "error_message": "La ruta no corresponde a un archivo.",
                    }
                )

            # Comprobar permisos del archivo
            if not os.access(file_path, os.W_OK):
                logger.warning(
                    f"Sin permisos para eliminar archivo: {file_path} por usuario {user_id}"
                )
                return JsonResponse(
                    {
                        "success": False,
                        "error_message": "Sin permisos para eliminar el archivo.",
                    }
                )

            # Registrar información del archivo antes de eliminarlo
            file_size = os.path.getsize(file_path)
            file_mod_time = os.path.getmtime(file_path)

            # Eliminar el archivo
            os.remove(file_path)

            # Limpiar la sesión
            del request.session["file_path"]
            del request.session["file_name"]

            # Registrar la eliminación exitosa
            logger.info(
                f"Archivo eliminado: {file_path} ({file_size/1024:.2f}KB, modificado: {time.ctime(file_mod_time)}) por usuario {user_id} en {time.time() - start_time:.2f}s"
            )

            # Limpieza automática de archivos viejos tras cada borrado manual
            removed_auto = clean_old_media_files(hours=4)
            return JsonResponse({"success": True, "auto_cleaned_files": removed_auto})

        except FileNotFoundError:
            logger.warning(
                f"Archivo no encontrado al intentar eliminar: {file_path} por usuario {user_id}"
            )
            return JsonResponse(
                {"success": False, "error_message": "El archivo no existe."}
            )
        except PermissionError as e:
            logger.error(
                f"Error de permisos al eliminar {file_path}: {str(e)} por usuario {user_id}"
            )
            return JsonResponse(
                {"success": False, "error_message": f"Error de permisos: {str(e)}"}
            )
        except OSError as e:
            logger.error(
                f"Error del sistema de archivos al eliminar {file_path}: {str(e)} por usuario {user_id}"
            )
            return JsonResponse(
                {
                    "success": False,
                    "error_message": f"Error del sistema de archivos: {str(e)}",
                }
            )
        except Exception as e:
            logger.error(
                f"Error inesperado al eliminar {file_path}: {str(e)} por usuario {user_id}"
            )
            return JsonResponse(
                {
                    "success": False,
                    "error_message": f"Error: no se pudo eliminar el archivo. Razón: {str(e)}",
                }
            )
        finally:
            # In case of any fallback, ensure redirect to cubo panel
            pass


class DeleteFileView(BaseView):
    """
    Vista optimizada para eliminar archivos de manera segura.
    Implementa validaciones de seguridad, registro de actividad y manejo mejorado de errores.
    """

    login_url = reverse_lazy("users_app:user-login")
    allowed_extensions = [
        ".xlsx",
        ".csv",
        ".txt",
        ".zip",
        ".pdf",
        ".xls",
    ]  # Extensiones permitidas

    def post(self, request):

        start_time = time.time()
        user_id = request.user.id

        # Obtener el nombre del archivo desde POST o sesión
        file_name = request.POST.get("file_name") or request.session.get("file_name")
        logger.info(f"[DeleteFileView] file_name recibido: {file_name}")
        # Construir la ruta segura (solo permite archivos en media/)
        file_path = os.path.join("media", file_name) if file_name else None
        logger.info(f"[DeleteFileView] file_path construido: {file_path}")
        # Validar que el archivo esté dentro de media/
        media_root = os.path.abspath("media")
        abs_file_path = os.path.abspath(file_path) if file_path else None
        logger.info(
            f"[DeleteFileView] abs_file_path: {abs_file_path}, media_root: {media_root}"
        )
        if not abs_file_path.startswith(media_root):
            logger.warning(
                f"Intento de eliminar archivo fuera de media/: {abs_file_path} por usuario {user_id}"
            )
            return JsonResponse(
                {"success": False, "error_message": "Ruta de archivo no permitida."}
            )

        # Validar extensión
        _, extension = os.path.splitext(file_path)
        if extension.lower() not in self.allowed_extensions:
            logger.warning(
                f"Intento de eliminar tipo de archivo no permitido: {file_path} por usuario {user_id}"
            )
            return JsonResponse(
                {"success": False, "error_message": "Tipo de archivo no permitido."}
            )

        # Validar existencia y permisos
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            logger.warning(
                f"Intento de eliminar archivo inexistente: {file_path} por usuario {user_id}"
            )
            return JsonResponse(
                {"success": False, "error_message": "El archivo no existe."}
            )
        if not os.access(file_path, os.W_OK):
            logger.warning(
                f"Sin permisos para eliminar archivo: {file_path} por usuario {user_id}"
            )
            return JsonResponse(
                {
                    "success": False,
                    "error_message": "Sin permisos para eliminar el archivo.",
                }
            )

        # Eliminar el archivo
        try:
            logger.info(f"[DeleteFileView] Intentando eliminar archivo: {file_path}")
            file_size = os.path.getsize(file_path)
            file_mod_time = os.path.getmtime(file_path)
            os.remove(file_path)
            logger.info(f"[DeleteFileView] Archivo eliminado exitosamente: {file_path}")
            # Limpiar la sesión solo si coincide
            if request.session.get("file_name") == file_name:
                request.session.pop("file_path", None)
                request.session.pop("file_name", None)
            logger.info(
                f"Archivo eliminado: {file_path} ({file_size/1024:.2f}KB, modificado: {time.ctime(file_mod_time)}) por usuario {user_id} en {time.time() - start_time:.2f}s"
            )
            # Limpieza automática de archivos viejos tras cada borrado manual
            removed_auto = clean_old_media_files(hours=4)
            return JsonResponse({"success": True, "auto_cleaned_files": removed_auto})
        except Exception as e:
            logger.error(
                f"Error al eliminar archivo {file_path}: {str(e)} por usuario {user_id}"
            )
            return JsonResponse({"success": False, "error_message": f"Error: {str(e)}"})


class CheckTaskStatusView(BaseView):
    """
    Vista optimizada para comprobar el estado de tareas asincrónicas y recuperar resultados.
    Proporciona información detallada sobre el proceso y resúmenes de operaciones.
    """

    def post(self, request, *args, **kwargs):
        print("[CheckTaskStatusView] Inicio POST")
        task_id = request.POST.get("task_id") or request.session.get("task_id")
        print(f"[CheckTaskStatusView] task_id recibido: {task_id}")

        if not task_id:
            print("[CheckTaskStatusView] No task_id proporcionado")
            return JsonResponse({"error": "No task ID provided"}, status=400)

        connection = get_connection()
        try:
            print("[CheckTaskStatusView] Intentando fetch del job...")
            job = Job.fetch(task_id, connection=connection)
            print(f"[CheckTaskStatusView] Job encontrado: {job}")

            if job.is_finished:
                print(f"[CheckTaskStatusView] Job {task_id} terminado")
                result = job.result
                print(f"[CheckTaskStatusView] Resultado del job: {result}")

                task_name = (
                    job.func_name.split(".")[-1]
                    if "." in job.func_name
                    else job.func_name
                )

                # --- ALINEACIÓN PARA cubo_ventas_task ---
                if task_name == "cubo_ventas_task" and isinstance(result, dict):
                    # Asegura que todas las claves esperadas existan
                    if "success" not in result:
                        result["success"] = False
                    if "file_path" not in result:
                        result["file_path"] = ""
                    if "file_name" not in result:
                        result["file_name"] = ""
                    if "message" not in result:
                        result["message"] = ""
                    if "metadata" not in result:
                        result["metadata"] = {}
                    if "performance_report" not in result["metadata"]:
                        result["metadata"]["performance_report"] = ""
                    if "preview_headers" not in result:
                        result["preview_headers"] = []
                    if "preview_sample" not in result:
                        result["preview_sample"] = []

                # Si la tarea es interface_task y success es False, devolver error y NO mostrar link de descarga
                if (
                    task_name in ["interface_task", "plano_task"]
                    and isinstance(result, dict)
                    and not result.get("success", True)
                ):
                    error_message = (
                        result.get("error_message")
                        or result.get("message")
                        or "Error en la tarea de interface."
                    )
                    logger.warning(f"Tarea interface_task fallida: {error_message}")
                    return JsonResponse(
                        {
                            "status": "failed",
                            "result": result,
                            "error_message": error_message,
                            "summary": self._generate_summary(job, result),
                        },
                        status=200,
                    )

                # Lógica especial SOLO para la tarea de actualización de BI (actualiza_bi_task)
                if task_name == "actualiza_bi_task":
                    powerbi_status = None
                    if isinstance(result, dict):
                        powerbi_status = result.get("powerbi_status")
                        # Si el estado es Unknown tras agotar intentos, mostrar mensaje claro
                        if powerbi_status == "Unknown":
                            # Mensaje claro para el usuario
                            return JsonResponse(
                                {
                                    "status": "unknown",
                                    "result": result,
                                    "error_message": "El estado de actualización de Power BI es desconocido tras varios intentos. El proceso puede seguir en curso. Por favor, reintente en unos minutos o verifique manualmente en el portal de Power BI.",
                                    "summary": self._generate_summary(job, result),
                                },
                                status=200,
                            )

                if (
                    isinstance(result, dict)
                    and result.get("success")
                    and "file_path" in result
                    and "file_name" in result
                ):
                    print(
                        f"[CheckTaskStatusView] Guardando file_path y file_name en sesión: {result['file_path']}, {result['file_name']}"
                    )
                    request.session["file_path"] = result["file_path"]
                    request.session["file_name"] = result["file_name"]

                job_info = {
                    "execution_time": result.get("execution_time", 0),
                    "completed_at": time.time(),
                    "started_at": (
                        job.started_at.timestamp() if job.started_at else None
                    ),
                    "enqueued_at": (
                        job.enqueued_at.timestamp() if job.enqueued_at else None
                    ),
                    "task_name": job.func_name,
                    "task_args": job.args,
                }

                if isinstance(result, dict):
                    result.update(
                        {
                            "job_info": job_info,
                            "summary": result.get(
                                "summary", self._generate_summary(job, result)
                            ),
                        }
                    )

                # Si es la tarea de BI y hay estado Power BI, incluirlo en la respuesta principal
                if task_name == "actualiza_bi_task" and result.get("powerbi_status"):
                    print(
                        f"[CheckTaskStatusView] Estado Power BI detectado: {result['powerbi_status']}"
                    )
                    return JsonResponse(
                        {
                            "status": "completed",
                            "result": result,
                            "progress": 100,
                            "meta": result.get("metadata", {}),
                            "powerbi_status": result["powerbi_status"],
                        }
                    )

                print(
                    f"[CheckTaskStatusView] Devolviendo respuesta de éxito para {task_id}"
                )
                logger.info(f"Tarea {task_id} completada exitosamente: {result}")
                return JsonResponse(
                    {
                        "status": "completed",
                        "result": result,
                        "progress": 100,
                        "meta": result.get("metadata", {}),
                    }
                )

            elif job.is_failed:
                print(f"[CheckTaskStatusView] Job {task_id} fallido")
                error_info = {
                    "job_id": job.id,
                    "exception": (
                        str(job.exc_info)
                        if hasattr(job, "exc_info") and job.exc_info
                        else "Error desconocido"
                    ),
                    "started_at": (
                        job.started_at.timestamp() if job.started_at else None
                    ),
                    "enqueued_at": (
                        job.enqueued_at.timestamp() if job.enqueued_at else None
                    ),
                }
                print(f"[CheckTaskStatusView] Error info: {error_info}")
                logger.error(f"Tarea {task_id} fallida: {error_info}")
                return JsonResponse(
                    {
                        "status": "failed",
                        "result": job.result,
                        "error_info": error_info,
                    },
                    status=500,
                )

            else:
                print(f"[CheckTaskStatusView] Job {task_id} en progreso")
                progress = 0
                stage = "En cola"
                meta = {}

                if hasattr(job, "meta") and job.meta:
                    meta = job.meta.copy()
                    if "progress" in job.meta:
                        progress = job.meta.get("progress")
                    if "stage" in job.meta:
                        stage = job.meta.get("stage")
                    if "status" in job.meta:
                        stage = job.meta.get("status")

                file_ready = False
                if hasattr(job, "meta") and job.meta and "file_path" in job.meta:
                    file_path = job.meta.get("file_path")
                    if file_path and os.path.exists(file_path):
                        file_ready = True
                        if "file_name" in job.meta:
                            print(
                                f"[CheckTaskStatusView] Archivo parcial listo: {file_path}"
                            )
                            request.session["file_path"] = file_path
                            request.session["file_name"] = job.meta.get("file_name")
                            meta["file_ready"] = True

                elapsed_time = 0
                if job.started_at:
                    elapsed_time = time.time() - job.started_at.timestamp()

                eta = None
                if progress > 5 and elapsed_time > 0:
                    try:
                        eta = (elapsed_time / progress) * (100 - progress)
                    except:
                        eta = None

                meta["last_update"] = time.time()

                if file_ready and progress >= 95 and meta.get("file_ready"):
                    print(
                        f"[CheckTaskStatusView] Éxito parcial, archivo listo para descarga"
                    )
                    status_data = {
                        "status": "partial_success",
                        "progress": 100,
                        "stage": "Archivo generado, procesando metadatos",
                        "meta": meta,
                        "elapsed_time": elapsed_time,
                        "eta": eta,
                        "estado": "Éxito parcial - Archivo listo para descarga",
                    }
                else:
                    status_data = {
                        "status": job.get_status(),
                        "progress": progress,
                        "stage": stage,
                        "meta": meta,
                        "elapsed_time": elapsed_time,
                        "eta": eta,
                        "estado": self._get_readable_status(job.get_status()),
                        "enqueued_at": (
                            job.enqueued_at.timestamp() if job.enqueued_at else None
                        ),
                        "started_at": (
                            job.started_at.timestamp() if job.started_at else None
                        ),
                    }
                print(f"[CheckTaskStatusView] Estado actual: {status_data}")
                return JsonResponse(status_data)

        except NoSuchJobError:
            print(f"[CheckTaskStatusView] NoSuchJobError para {task_id}")
            return JsonResponse(
                {
                    "status": "notfound",
                    "error": "Tarea no encontrada. Puede que haya expirado o se haya completado hace mucho tiempo.",
                }
            )

        except Exception as e:
            print(f"[CheckTaskStatusView] Excepción: {str(e)}")
            logger.error(
                f"Error al comprobar estado de tarea {task_id}: {str(e)}\n{traceback.format_exc()}"
            )
            return JsonResponse({"status": "error", "error": str(e)}, status=500)

    def _get_readable_status(self, status):
        """Convierte el estado de la tarea en un texto más amigable"""
        status_map = {
            "queued": "En cola",
            "started": "En proceso",
            "deferred": "Pospuesta",
            "finished": "Completada",
            "failed": "Fallida",
            "stopped": "Detenida",
            "scheduled": "Programada",
        }
        return status_map.get(status, status)

    def _generate_summary(self, job, result):
        """
        Genera un resumen legible para el usuario basado en el tipo de tarea y su resultado.
        """
        # Obtener nombre de la tarea sin prefijos
        task_name = (
            job.func_name.split(".")[-1] if "." in job.func_name else job.func_name
        )
        logger.info(f"Resumen: func_name={job.func_name}, task_name={task_name}")
        print(f"Resumen: func_name={job.func_name}, task_name={task_name}")

        if task_name == "actualiza_bi_task":
            # Para actualización de BI
            db_name = job.args[0] if len(job.args) > 0 else "desconocida"
            fecha_ini = job.args[1] if len(job.args) > 1 else "desconocida"
            fecha_fin = job.args[2] if len(job.args) > 2 else "desconocida"

            # Calcular duración
            started = job.started_at.timestamp() if job.started_at else 0
            ended = time.time()
            duration = ended - started if started > 0 else 0

            # Lógica especial: incluir estado Power BI si existe
            powerbi_status = result.get("powerbi_status") or result.get(
                "metadata", {}
            ).get("powerbi_status")
            resumen = {
                "tipo_proceso": "Actualización de datos BI",
                "base_datos": db_name,
                "periodo": f"{fecha_ini} - {fecha_fin}",
                "duracion": f"{duration:.2f} segundos",
                "resultado": (
                    "Proceso completado correctamente"
                    if result.get("success", False)
                    else "Proceso completado con errores"
                ),
                "detalles": result.get("message", "Sin detalles adicionales"),
                "tiempo_ejecucion": f"{result.get('execution_time', 0):.2f} segundos",
            }
            if powerbi_status:
                resumen["estado_powerbi"] = powerbi_status
            return resumen

        elif task_name == "extrae_bi_task":
            # Para actualización de BI
            db_name = job.args[0] if len(job.args) > 0 else "desconocida"
            fecha_ini = job.args[1] if len(job.args) > 1 else "desconocida"
            fecha_fin = job.args[2] if len(job.args) > 2 else "desconocida"

            # Calcular duración
            started = job.started_at.timestamp() if job.started_at else 0
            ended = time.time()
            duration = ended - started if started > 0 else 0

            return {
                "tipo_proceso": "Actualización de datos BI",
                "base_datos": db_name,
                "periodo": f"{fecha_ini} - {fecha_fin}",
                "duracion": f"{duration:.2f} segundos",
                "resultado": (
                    "Proceso completado correctamente"
                    if result.get("success", False)
                    else "Proceso completado con errores"
                ),
                "detalles": result.get("message", "Sin detalles adicionales"),
                "tiempo_ejecucion": f"{result.get('execution_time', 0):.2f} segundos",
            }

        elif task_name in ["interface_task", "plano_task"]:
            # Resumen especial para Interface Contable
            db_name = job.args[0] if len(job.args) > 0 else "desconocida"
            fecha_ini = job.args[1] if len(job.args) > 1 else "desconocida"
            fecha_fin = job.args[2] if len(job.args) > 2 else "desconocida"
            resumen = {
                "tipo_proceso": "Interface Contable",
                "base_datos": db_name,
                "periodo": f"{fecha_ini} - {fecha_fin}",
                "archivo_generado": result.get("file_name", "No se generó archivo"),
                "registros_procesados": result.get("metadata", {}).get(
                    "total_records", "Desconocido"
                ),
                "resultado": (
                    "Archivo generado correctamente"
                    if result.get("success", False)
                    else (
                        result.get("error_message")
                        if result.get("error_message")
                        else "Proceso completado con errores"
                    )
                ),
            }
            return resumen

        elif task_name in ["cubo_ventas_task"]:
            # Para reportes de Cubo o Proveedores
            db_name = job.args[0] if len(job.args) > 0 else "desconocida"
            fecha_ini = job.args[1] if len(job.args) > 1 else "desconocida"
            fecha_fin = job.args[2] if len(job.args) > 2 else "desconocida"
            report_id = job.args[4] if len(job.args) > 4 else 0

            tipo_reporte = "Cubo de Ventas"
            if report_id == 2:
                tipo_reporte = "Informe de Proveedores"
            elif report_id == 3:
                tipo_reporte = "Reporte Amovildesk"

            return {
                "tipo_proceso": tipo_reporte,
                "base_datos": db_name,
                "periodo": f"{fecha_ini} - {fecha_fin}",
                "archivo_generado": result.get("file_name", "No se generó archivo"),
                "registros_procesados": result.get("metadata", {}).get(
                    "total_records", "Desconocido"
                ),
                "resultado": (
                    "Archivo generado correctamente"
                    if result.get("success", False)
                    else (
                        result.get("error_message")
                        if result.get("error_message")
                        else "Proceso completado con errores"
                    )
                ),
            }

        elif task_name == "cargue_infoventas_task":
            # Para cargue masivo de ventas
            db_name = job.args[1] if len(job.args) > 1 else "desconocida"
            fecha_ini = job.args[2] if len(job.args) > 2 else "desconocida"
            fecha_fin = job.args[3] if len(job.args) > 3 else "desconocida"

            return {
                "tipo_proceso": "Cargue Masivo de Ventas",
                "base_datos": db_name,
                "periodo": f"{fecha_ini} - {fecha_fin}",
                "registros_procesados": result.get(
                    "registros_procesados", "Desconocido"
                ),
                "registros_insertados": result.get(
                    "registros_insertados", "Desconocido"
                ),
                "registros_descartados": result.get(
                    "registros_descartados", "Desconocido"
                ),
                "advertencias": len(result.get("warnings", [])),
                "resultado": (
                    "Carga completada exitosamente"
                    if result.get("success", False)
                    else "Carga completada con errores"
                ),
                "detalles": result.get("message", "Sin detalles adicionales"),
            }

        # Para otros tipos de tareas
        return {
            "tipo_proceso": task_name,
            "resultado": (
                "Proceso completado correctamente"
                if result.get("success", False)
                else "Proceso completado con errores"
            ),
            "detalles": result.get("message", "Sin detalles adicionales"),
        }


class ReporteGenericoPage(BaseView):
    """
    Vista genérica para reportes tipo Cubo y Proveedor.
    Permite unificar la lógica cambiando solo el id_reporte, plantilla, permiso y task.
    """

    template_name = None
    login_url = reverse_lazy("users_app:user-login")
    permiso = None
    id_reporte = None
    form_url = None
    task_func = None
    batch_size_default = 50000

    @classmethod
    def as_view_with_params(cls, **initkwargs):
        print(f"[ReporteGenericoPage] as_view_with_params: initkwargs={initkwargs}")

        def view(*args, **kwargs):
            print(
                f"[ReporteGenericoPage] as_view_with_params.view: args={args}, kwargs={kwargs}"
            )
            self = cls(**initkwargs)
            return self.dispatch(*args, **kwargs)

        return view

    @method_decorator(registrar_auditoria)
    def dispatch(self, request, *args, **kwargs):
        print(
            f"[ReporteGenericoPage] dispatch: method={request.method}, user={request.user}, args={args}, kwargs={kwargs}"
        )
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        print(
            f"[ReporteGenericoPage] post: POST={request.POST}, user={request.user}, args={args}, kwargs={kwargs}"
        )
        database_name = request.POST.get("database_select")
        IdtReporteIni = request.POST.get("IdtReporteIni")
        IdtReporteFin = request.POST.get("IdtReporteFin")
        batch_size = int(request.POST.get("batch_size", self.batch_size_default))
        user_id = request.user.id
        request.session["template_name"] = self.template_name
        id_reporte = self.id_reporte
        if id_reporte is None:
            id_reporte = request.POST.get("reporte_id")
        # Permitir actualización solo de base de datos (AJAX o selector)
        if database_name and not (IdtReporteIni and IdtReporteFin):
            request.session["database_name"] = database_name
            print(
                "[ReporteGenericoPage] post: Solo cambio de base de datos, actualizado en sesión."
            )
            return JsonResponse(
                {
                    "success": True,
                    "message": f"Base de datos actualizada a: {database_name}",
                }
            )
        if not all([database_name, IdtReporteIni, IdtReporteFin]):
            print("[ReporteGenericoPage] post: Faltan datos requeridos")
            return JsonResponse(
                {
                    "success": False,
                    "error_message": "Se debe seleccionar la base de datos y las fechas.",
                },
                status=400,
            )
        try:
            print(
                f"[ReporteGenericoPage] post: Llamando a task_func.delay con database_name={database_name}, IdtReporteIni={IdtReporteIni}, IdtReporteFin={IdtReporteFin}, user_id={user_id}, id_reporte={self.id_reporte}, batch_size={batch_size}"
            )
            task = self.task_func.delay(
                database_name,
                IdtReporteIni,
                IdtReporteFin,
                user_id,
                id_reporte,
                batch_size,
            )
            print(f"[ReporteGenericoPage] post: Tarea lanzada con task_id={task.id}")
            return JsonResponse({"success": True, "task_id": task.id})
        except Exception as e:
            print(
                f"[ReporteGenericoPage] post: Error al iniciar la tarea de reporte: {e}"
            )
            logger.error(f"Error al iniciar la tarea de reporte: {e}")
            return JsonResponse(
                {"success": False, "error_message": f"Error: {str(e)}"}, status=500
            )

    def get(self, request, *args, **kwargs):
        print(
            f"[ReporteGenericoPage] get: user={request.user}, args={args}, kwargs={kwargs}"
        )
        database_name = request.session.get("database_name")
        if not database_name:
            print(
                "[ReporteGenericoPage] get: No hay database_name en sesión, redirigiendo."
            )
            messages.warning(
                request, "Debe seleccionar una empresa antes de continuar."
            )
            return redirect("home_app:panel_cubo")
        context = self.get_context_data(**kwargs)
        context["data"] = None
        print(
            f"[ReporteGenericoPage] get: Renderizando respuesta con context={context}"
        )
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        print(f"[ReporteGenericoPage] get_context_data: kwargs={kwargs}")
        context = super().get_context_data(**kwargs)
        context["form_url"] = self.form_url
        user_id = self.request.user.id
        database_name = self.request.session.get("database_name")
        if database_name:
            config = ConfigBasic(database_name, user_id)
            context["proveedores"] = config.config.get("proveedores", [])
            context["macrozonas"] = config.config.get("macrozonas", [])
        file_name = self.request.session.get("file_name")
        file_path = self.request.session.get("file_path")
        if file_name:
            context["file_name"] = file_name
        if file_path:
            context["file_path"] = file_path
            # Agregar file_size para el botón de descarga
            import os

            if os.path.exists(file_path):
                context["file_size"] = os.path.getsize(file_path)
            else:
                context["file_size"] = None
        print(f"[ReporteGenericoPage] get_context_data: context={context}")
        return context

    def get_reporte_preview(
        self,
        database_name,
        IdtReporteIni,
        IdtReporteFin,
        user_id,
        id_reporte,
        start_row=0,
        chunk_size=100,
        search=None,
    ):
        """
        Utilidad para obtener headers, rows y resultado (lista de dicts) de un reporte tipo Cubo/Proveedor.
        """
        from scripts.extrae_bi.cubo_sin_sqlite import CuboVentas

        cubo = CuboVentas(
            database_name, IdtReporteIni, IdtReporteFin, user_id, id_reporte
        )
        preview = cubo.get_data(
            start_row=start_row, chunk_size=chunk_size, search=search
        )
        headers = preview.get("headers", [])
        rows = preview.get("rows", [])
        resultado = [dict(zip(headers, row)) for row in rows]
        return headers, rows, resultado, preview


class CuboPage(ReporteGenericoPage):
    template_name = "home/cubo.html"
    permiso = "permisos.cubo"
    id_reporte = 1
    form_url = "home_app:cubo"
    task_func = cubo_ventas_task

    @method_decorator(permission_required("permisos.cubo", raise_exception=True))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


class ProveedorPage(ReporteGenericoPage):
    template_name = "home/proveedor.html"
    permiso = "permisos.proveedor"
    id_reporte = 2
    form_url = "home_app:proveedor"
    task_func = cubo_ventas_task

    @method_decorator(permission_required("permisos.proveedor", raise_exception=True))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


class AmovildeskPage(ReporteGenericoPage):
    template_name = "home/amovildesk.html"
    permiso = "permisos.amovildesk"
    id_reporte = 3
    form_url = "home_app:amovildesk"
    task_func = cubo_ventas_task

    @method_decorator(permission_required("permisos.amovildesk", raise_exception=True))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


class InterfacePage(ReporteGenericoPage):
    template_name = "home/interface.html"
    permiso = "permisos.interface"
    id_reporte = 0  # Si aplica, puedes asignar un id específico
    form_url = "home_app:interface"
    task_func = interface_task

    @method_decorator(permission_required("permisos.interface", raise_exception=True))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


class PlanoPage(ReporteGenericoPage):
    template_name = "home/plano.html"
    permiso = "permisos.plano"
    id_reporte = 0  # Si aplica, puedes asignar un id específico
    form_url = "home_app:plano"
    task_func = plano_task

    @method_decorator(permission_required("permisos.interface", raise_exception=True))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


class ActualizacionBdPage(ReporteGenericoPage):

    template_name = "home/actualizacion.html"
    permiso = "permisos.actualizar_base"
    id_reporte = 0  # Puedes ajustar este ID si tienes uno específico para actualización
    form_url = "home_app:actualizacion"
    task_func = extrae_bi_task

    @method_decorator(
        permission_required("permisos.actualizar_base", raise_exception=True)
    )
    @method_decorator(registrar_auditoria)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


class ReporteadorPage(ReporteGenericoPage):
    template_name = "home/reporteador.html"
    permiso = "permisos.reportes"
    id_reporte = None  # Se selecciona dinámicamente
    form_url = "home_app:reporteador"
    task_func = cubo_ventas_task

    @method_decorator(permission_required("permisos.reportes", raise_exception=True))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


class ReporteListView(View):
    """
    Vista para obtener la lista de reportes activos en formato JSON.
    """

    def get(self, request, *args, **kwargs):
        try:
            reportes = Reporte.objects.filter(activo=True).order_by("nombre")
            reportes_list = [
                {
                    "id": reporte.id,
                    "nombre": reporte.nombre,
                    "descripcion": reporte.descripcion,
                }
                for reporte in reportes
            ]
            return JsonResponse({"status": "success", "reportes_list": reportes_list})
        except Exception as e:
            print(f"Error en ReporteListView: {e}")
            return JsonResponse(
                {
                    "status": "error",
                    "message": _("Error al obtener la lista de reportes."),
                },
                status=500,
            )


class ReporteadorDataAjaxView(ReporteGenericoPage):
    """
    AJAX endpoint para DataTables server-side processing en el reporteador.
    Devuelve datos paginados y filtrados del reporte generado.
    """

    def get(self, request, *args, **kwargs):
        try:
            draw = int(request.GET.get("draw", 1))
            start = int(request.GET.get("start", 0))
            length = int(request.GET.get("length", 100))
            search_value = request.GET.get("search[value]", "")
            id_reporte = request.GET.get("reporte_id") or request.session.get(
                "reporte_id"
            )
            database_name = request.GET.get("database_select") or request.session.get(
                "database_name"
            )
            IdtReporteIni = request.GET.get("IdtReporteIni") or request.session.get(
                "IdtReporteIni"
            )
            IdtReporteFin = request.GET.get("IdtReporteFin") or request.session.get(
                "IdtReporteFin"
            )
            user_id = request.user.id
            headers, rows, resultado, preview = self.get_reporte_preview(
                database_name,
                IdtReporteIni,
                IdtReporteFin,
                user_id,
                id_reporte,
                start_row=start,
                chunk_size=length,
                search=search_value,
            )
            total_records = preview.get("total_records", 0)
            filtered_records = preview.get("filtered_records", total_records)
            return JsonResponse(
                {
                    "draw": draw,
                    "recordsTotal": total_records,
                    "recordsFiltered": filtered_records,
                    "data": resultado,
                }
            )
        except Exception as e:
            import traceback

            return JsonResponse(
                {
                    "error": str(e),
                    "trace": traceback.format_exc(),
                    "draw": request.GET.get("draw", 1),
                    "recordsTotal": 0,
                    "recordsFiltered": 0,
                    "data": [],
                },
                status=500,
            )


def clean_old_media_files(hours=4):
    """
    Elimina archivos en la carpeta media/ con extensiones permitidas
    (.xlsx, .db, .zip, .csv, .txt) que tengan más de 'hours' horas de modificados.
    """
    import os
    import time
    from pathlib import Path

    MEDIA_DIR = Path("media")
    EXTENSIONS = {".xlsx", ".db", ".zip", ".csv", ".txt"}
    now = time.time()
    removed = []
    for file in MEDIA_DIR.iterdir():
        if file.is_file() and file.suffix.lower() in EXTENSIONS:
            mtime = file.stat().st_mtime
            age_hours = (now - mtime) / 3600

            if age_hours > hours:
                try:
                    file.unlink()
                    removed.append(str(file))
                    logger.info(
                        f"[clean_old_media_files] Archivo eliminado: {file} (antigüedad: {age_hours:.2f}h)"
                    )
                except Exception as e:
                    logger.error(
                        f"[clean_old_media_files] Error al eliminar {file}: {e}"
                    )
    return removed


from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.contrib.admin.views.decorators import staff_member_required


@method_decorator(
    [login_required, staff_member_required, require_POST], name="dispatch"
)
class CleanMediaView(View):
    """
    Vista protegida para lanzar la limpieza manual de archivos viejos en media/.
    Solo accesible para usuarios staff autenticados.
    Devuelve JSON con archivos eliminados o error.
    """

    def post(self, request, *args, **kwargs):
        try:
            hours = int(request.POST.get("hours", 4))
            removed = clean_old_media_files(hours=hours)
            return JsonResponse(
                {
                    "success": True,
                    "removed_files": removed,
                    "message": f"{len(removed)} archivos eliminados de media/",
                }
            )
        except Exception as e:
            logger.error(f"[CleanMediaView] Error: {e}")
            return JsonResponse({"success": False, "error_message": str(e)}, status=500)
