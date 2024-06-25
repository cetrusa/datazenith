from django.db import models


class Reporte(models.Model):
    nombre = models.CharField(max_length=100, verbose_name="Nombre del Reporte")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    sql_text = models.TextField(blank=True, verbose_name="Texto de SQLAlchemy")

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Reporte"
        verbose_name_plural = "Reportes"
