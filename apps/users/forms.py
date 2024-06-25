from django import forms
from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404

from captcha.fields import ReCaptchaField
from captcha.widgets import ReCaptchaV2Checkbox
#
from .models import User


class UserRegisterForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Contraseña",
        required=True,
        widget=forms.PasswordInput(attrs={"placeholder": "Contraseña"}),
    )
    password2 = forms.CharField(
        label="Contraseña",
        required=True,
        widget=forms.PasswordInput(attrs={"placeholder": "Repetir Contraseña"}),
    )

    class Meta:
        """Meta definition for Userform."""

        model = User
        fields = (
            "username",
            "email",
            "nombres",
            "apellidos",
            "genero",
        )

    def clean_password2(self):
        if self.cleaned_data["password1"] != self.cleaned_data["password2"]:
            self.add_error("password2", "Las contraseñas no son iguales")


class LoginForm(forms.Form):
    username = forms.CharField(
        label="Usuario",
        required=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Usuario",
            }
        ),
    )
    password = forms.CharField(
        label="Contraseña",
        required=True,
        widget=forms.PasswordInput(attrs={"placeholder": "Contraseña"}),
    )

    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox)
    def clean(self):
        cleaned_data = super(LoginForm, self).clean()
        username = self.cleaned_data["username"]
        password = self.cleaned_data["password"]

        if not authenticate(username=username, password=password):
            raise forms.ValidationError("Los datos de usuario no son correctos")

        return self.cleaned_data


class UpdatePasswordForm(forms.Form):
    password1 = forms.CharField(
        label="Contraseña",
        required=True,
        widget=forms.PasswordInput(attrs={"placeholder": "Contraseña Actual"}),
    )
    password2 = forms.CharField(
        label="Contraseña",
        required=True,
        widget=forms.PasswordInput(attrs={"placeholder": "Contraseña Nueva"}),
    )


class VerificationForm(forms.Form):
    codregistro = forms.CharField(required=True)

    def __init__(self, pk, *args, **kwargs):
        self.id_user = pk
        super(VerificationForm, self).__init__(*args, **kwargs)

    def clean_codregistro(self):
        codigo = self.cleaned_data["codregistro"]
        user = get_object_or_404(User, id=self.id_user)

        if len(codigo) == 6:
            # Verificamos si el código y el id de usuario son válidos:
            if user.codregistro == codigo:
                return codigo
            else:
                raise forms.ValidationError("El código es incorrecto")
        else:
            raise forms.ValidationError("El código debe tener 6 caracteres")