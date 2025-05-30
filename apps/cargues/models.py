from django.db import models


class Infoventas(models.Model):
    id = models.CharField(
        max_length=255, primary_key=True, db_column="id"
    )  # Artificial PK
    cod_cliente = models.CharField(max_length=30, db_column="Cod. cliente")
    nom_cliente = models.TextField(db_column="Nom. Cliente")
    cod_vendedor = models.CharField(max_length=30, db_column="Cod. vendedor")
    nombre = models.TextField(db_column="Nombre")
    cod_productto = models.CharField(max_length=30, db_column="Cod. productto")
    descripcion = models.TextField(db_column="Descripción")
    fecha = models.DateField(db_column="Fecha")
    fac_numero = models.CharField(max_length=30, db_column="Fac. numero")
    cantidad = models.FloatField(db_column="Cantidad")
    vta_neta = models.FloatField(db_column="Vta neta")
    tipo = models.CharField(max_length=30, db_column="Tipo")
    costo = models.FloatField(db_column="Costo")
    unidad = models.CharField(max_length=30, db_column="Unidad", blank=True, null=True)
    pedido = models.CharField(max_length=30, db_column="Pedido", blank=True, null=True)
    proveedor = models.TextField(db_column="Proveedor", blank=True, null=True)
    empresa = models.CharField(
        max_length=100, db_column="Empresa", blank=True, null=True
    )
    lider = models.TextField(db_column="Líder", blank=True, null=True)
    area = models.TextField(db_column="Área", blank=True, null=True)
    codigo_bodega = models.CharField(
        max_length=30, db_column="Codigo bodega", blank=True, null=True
    )
    bodega = models.CharField(max_length=100, db_column="Bodega", blank=True, null=True)
    categoria = models.TextField(db_column="Categoría", blank=True, null=True)
    tipo_prod = models.TextField(db_column="Tipo Prod", blank=True, null=True)
    cod_barra = models.CharField(
        max_length=50, db_column="Cod. Barra", blank=True, null=True
    )
    nbLinea = models.FloatField(db_column="nbLinea", blank=True, null=True)

    class Meta:
        db_table = "infoventas"
        managed = False  # No genera migraciones ni crea/modifica la tabla

    def save(self, *args, **kwargs):
        # Poblar el campo id concatenando los valores de las claves compuestas
        self.id = f"{self.cod_cliente}_{self.cod_vendedor}_{self.cod_productto}_{self.fac_numero}_{self.tipo}_{self.nbLinea}"
        super().save(*args, **kwargs)
