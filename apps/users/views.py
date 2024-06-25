from django.shortcuts import render, get_object_or_404
from django.core.mail import send_mail
from django.urls import reverse_lazy, reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import permission_required
from django.utils.decorators import method_decorator
from django.contrib.auth import get_user_model
from django.contrib import messages

# from apps.users.decorators import registrar_auditoria
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from scripts.StaticPage import StaticPage
from .utils import code_generator


from django.views.generic import (
    View,
    CreateView,
    ListView,
    TemplateView,
)

from django.views.generic.edit import (
    FormView,
)

from .forms import UserRegisterForm, LoginForm, UpdatePasswordForm, VerificationForm

#
from .models import User
from apps.permisos.models import ConfEmpresas

#
User = get_user_model()

class UserVerificationView(View):
    template_name = 'users/verification.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, {'user_id': kwargs['pk']})

    def post(self, request, *args, **kwargs):
        user = get_object_or_404(User, pk=kwargs['pk'])
        codigo = request.POST.get('codigo')
        if user.codregistro == codigo:
            user.is_active = True
            user.codregistro = ''  # Limpiamos el código de verificación
            user.save()
            return HttpResponseRedirect(reverse('users_app:user-login'))
        else:
            return render(request, self.template_name, {'error': 'Código incorrecto', 'user_id': kwargs['pk']})
        
        
class UserRegisterView(FormView):
    template_name = "users/register.html"
    form_class = UserRegisterForm
    success_url = reverse_lazy("users_app:user-login")

    def form_valid(self, form):
        # Generar el código
        codigo = code_generator()
        
        user = User.objects.create_user(
            form.cleaned_data["username"],
            form.cleaned_data["email"],
            form.cleaned_data["password1"],
            nombres=form.cleaned_data["nombres"],
            apellidos=form.cleaned_data["apellidos"],
            genero=form.cleaned_data["genero"],
            codregistro=codigo
        )
        # Enviar el código al email del usuario
        asunto = 'Confirmación de email'
        mensaje = f'Código de verificación: {codigo}'
        email_remitente = 'torredecontrolamovil@gmail.com'
        send_mail(asunto, mensaje, email_remitente, [form.cleaned_data['email']])
        
        # Redirigir a la pantalla de validación
        return HttpResponseRedirect(
            reverse('users_app:user-verification', kwargs={'pk': user.id})
        )


class LoginUser(FormView):
    template_name = "users/login.html"
    form_class = LoginForm
    success_url = reverse_lazy("home_app:panel_cubo")

    def form_valid(self, form):
        user = authenticate(
            username=form.cleaned_data["username"],
            password=form.cleaned_data["password"],
        )
        login(self.request, user)
        return super(LoginUser, self).form_valid(form)


class LogoutView(View):
    def get(self, request, *args, **kargs):
        logout(request)
        return HttpResponseRedirect(reverse("users_app:user-login"))


class CodeVerificationView(FormView):
    template_name = "users/verification.html"
    form_class = VerificationForm
    success_url = reverse_lazy("users_app:user-login")

    def get_form_kwargs(self):
        kwargs = super(CodeVerificationView, self).get_form_kwargs()
        kwargs.update({"pk": self.kwargs["pk"]})
        return kwargs

    def form_valid(self, form):
        user = get_object_or_404(User, id=self.kwargs["pk"])
        user.is_active = True
        user.codregistro = ""  # Limpiar el código de verificación
        user.save()

        # Verificar si el usuario está activo
        if user.is_active:
            # Agregar un mensaje flash
            messages.success(self.request, 'Señor usuario ha confirmado correctamente, debe esperar que sea asignada la empresa')
            # Redirigir al inicio de sesión con un mensaje
            return HttpResponseRedirect(reverse('users_app:user-login'))
        else:
            messages.error(self.request, 'Hubo un error al activar su cuenta. Por favor, intente nuevamente.')
            return super().form_invalid(form)


class BaseView(TemplateView):
    template_name = "base.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        databases = self.request.user.conf_empresas.all().order_by("nmEmpresa")
        database_list = [
            {"name": database.name, "nmEmpresa": database.nmEmpresa}
            for database in databases
        ]
        sorted_database_list = sorted(database_list, key=lambda x: x["nmEmpresa"])
        database_name = self.request.session.get(
            "database_name"
        ) or self.request.POST.get("database_select")
        context["database_list"] = sorted_database_list
        context["database_name"] = database_name
        return context

    def post(self, request, *args, **kwargs):
        database_name = request.POST.get("database_select")
        print(f"Received database_name: {database_name}")
        if database_name:
            request.session["database_name"] = database_name
            return JsonResponse(
                {"status": "success", "message": "Database name updated in session."}
            )
        else:
            return JsonResponse(
                {"status": "error", "message": "Invalid database name provided."},
                status=400,
            )


class DatabaseListView(ListView):
    model = ConfEmpresas
    context_object_name = "databases"
    template_name = "includes/database_list.html"

    def get_queryset(self):
        return self.request.user.conf_empresas.all().order_by("nmEmpresa")


def database_list(request):
    databases = request.user.conf_empresas.all().order_by("nmEmpresa")
    database_list = [
        {"database_name": database.name, "database_nmEmpresa": database.nmEmpresa}
        for database in databases
    ]
    return JsonResponse({"database_list": database_list})


def home(request):
    return render(request, "index.html")
