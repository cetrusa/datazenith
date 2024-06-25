from django import forms
from django.contrib import admin
from .models import Reporte

class ReporteAdminForm(forms.ModelForm):
    class Meta:
        model = Reporte
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(ReporteAdminForm, self).__init__(*args, **kwargs)
        self.fields['sql_text'].widget.attrs.update({'style': 'width: 600px; height: 200px;'})

class ReporteAdmin(admin.ModelAdmin):
    form = ReporteAdminForm
    list_display = ('id', 'nombre', 'descripcion')
    search_fields = ('nombre',)

admin.site.register(Reporte, ReporteAdmin)

