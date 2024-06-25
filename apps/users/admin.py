from django import forms
from django.contrib import admin
from .models import User, RegistroAuditoria, UserProfile, UserPermission
from django.contrib.auth.models import Permission
from apps.permisos.models import ConfEmpresas
import ast

class UserProfileInline(admin.StackedInline):
    model = UserProfile

class UserAdminForm(forms.ModelForm):
    conf_empresas = forms.ModelMultipleChoiceField(
        queryset=ConfEmpresas.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    select_all_empresas = forms.BooleanField(
        required=False, label="Seleccionar todas las empresas"
    )

    class Meta:
        model = User
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super(UserAdminForm, self).__init__(*args, **kwargs)
        if self.instance.pk and self.instance.conf_empresas.count() == ConfEmpresas.objects.count():
            self.fields['select_all_empresas'].initial = True

    def clean_conf_empresas(self):
        select_all_empresas = self.cleaned_data.get('select_all_empresas')
        if select_all_empresas:
            return ConfEmpresas.objects.all()
        return self.cleaned_data['conf_empresas']

    def save(self, commit=True):
        instance = super(UserAdminForm, self).save(commit=False)
        select_all_empresas = self.cleaned_data.get('select_all_empresas')
        if commit:
            instance.save()
            if select_all_empresas:
                instance.conf_empresas.set(ConfEmpresas.objects.all())
            self.save_m2m()
        return instance

class UserAdmin(admin.ModelAdmin):
    form = UserAdminForm
    list_display = (
        "username",
        "email",
        "nombres",
        "apellidos",
        "genero",
        "codregistro",
    )
    filter_horizontal = ("conf_empresas",)

    class Media:
        js = ('admin/select_all.js',)

class UserPermissionForm(forms.ModelForm):
    class Meta:
        model = UserPermission
        fields = '__all__'

    def clean_proveedores(self):
        data = self.cleaned_data['proveedores']
        try:
            return ast.literal_eval(data)
        except ValueError:
            raise forms.ValidationError("Ingrese un JSON válido para proveedores.")

    def clean_macrozona(self):
        data = self.cleaned_data['macrozona']
        try:
            return ast.literal_eval(data)
        except ValueError:
            raise forms.ValidationError("Ingrese un JSON válido para macrozona.")

class UserPermissionAdmin(admin.ModelAdmin):
    form = UserPermissionForm
    list_display = ('user', 'empresa', 'proveedores', 'macrozonas')
    search_fields = ('user__username', 'empresa__nmEmpresa')
    list_filter = ('empresa',)

admin.site.register(UserPermission, UserPermissionAdmin)
admin.site.register(RegistroAuditoria)
admin.site.register(User, UserAdmin)
admin.site.register(Permission)
